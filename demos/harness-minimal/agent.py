"""
Harness Minimal — ~200 lines of real, runnable agent harness.

Implements the core loop from Harness Engineering ch 10 with these components:
- Agent loop with cost ceiling + step limit
- 2 tools (bash + read_file) with allowlist + timeout
- Working memory pruning at 80% of context window
- Trajectory logging to JSONL
- Exponential backoff on transient errors

Run: python demo.py
"""
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

try:
    import anthropic
except ImportError:
    print("ERROR: pip install -r requirements.txt first", file=sys.stderr)
    sys.exit(1)


# === Config ===
MAX_STEPS = 8
MAX_COST_USD = 0.10
MAX_CONTEXT_CHARS = 120_000  # ~ 30k tokens, conservative for Sonnet 4
PRUNE_THRESHOLD = 0.8
DEFAULT_MODEL = "claude-haiku-4-5"  # cheap + fast for demo
TRAJECTORY_FILE = Path(__file__).parent / "trajectory.jsonl"


# === Tool definitions ===
TOOLS = [
    {
        "name": "read_file",
        "description": (
            "Read a text file. Returns content (truncated to 3000 chars). "
            "Use when you need to inspect a specific file."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative path to file"}
            },
            "required": ["path"]
        }
    },
    {
        "name": "bash",
        "description": (
            "Run a shell command. Returns stdout/stderr/exit_code. "
            "Use for: ls, cat, grep, wc, head, tail, python scripts. "
            "Do NOT use for: rm, mv, chmod, sudo, anything that modifies state."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "cmd": {"type": "string", "description": "Shell command to run"}
            },
            "required": ["cmd"]
        }
    },
]

# Bash allowlist — read-only commands + a few safe writers
BASH_ALLOWLIST = [
    r"^ls\b", r"^dir\b", r"^cat\b", r"^head\b", r"^tail\b", r"^grep\b", r"^wc\b",
    r"^find\s+(?!.*-(delete|exec)\b)", r"^stat\b", r"^file\b",
    r"^python\s+[\w./-]+\.py\s*$",
    r"^pwd$",
]
BASH_BLOCKED = [
    r"\brm\b", r"\bmv\b", r"\bcp\b", r"\bchmod\b", r"\bchown\b",
    r"\bsudo\b", r"\bsu\b", r"\bdd\b", r"\bmkfs\b",
    r">\s*/", r">>\s*/", r"\bshutdown\b", r"\breboot\b",
]


# === Tool execution ===
def execute_tool(name: str, args: dict) -> str:
    """Run a tool. Returns string result for LLM. Raises on hard error."""
    if name == "read_file":
        return _run_read_file(args["path"])
    elif name == "bash":
        return _run_bash(args["cmd"])
    raise ValueError(f"unknown tool: {name}")


def _run_read_file(path: str) -> str:
    """Read file, restrict to .md/.txt/.py, cap at 3000 chars."""
    if not re.search(r"\.(md|txt|py|json|yaml|yml)$", path):
        return f"Error: file type not allowed (only .md/.txt/.py/.json/.yaml): {path}"
    try:
        content = Path(path).read_text(encoding="utf-8")
    except FileNotFoundError:
        return f"Error: file not found: {path}"
    except Exception as e:
        return f"Error: {type(e).__name__}: {e}"
    if len(content) > 3000:
        return content[:3000] + f"\n\n[truncated, original was {len(content)} chars]"
    return content


def _run_bash(cmd: str) -> str:
    """Run bash with allowlist + timeout + cwd restriction."""
    # Hard blocks first
    for pattern in BASH_BLOCKED:
        if re.search(pattern, cmd):
            return f"Error: blocked (matches '{pattern}')"
    # Allowlist check
    if not any(re.match(p, cmd) for p in BASH_ALLOWLIST):
        return f"Error: command not in allowlist. Try: ls / cat / grep / wc / python <file>.py"
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True,
            timeout=10, cwd=os.getcwd(),
        )
        return f"exit={result.returncode}\nstdout={result.stdout[:1500]}\nstderr={result.stderr[:500]}"
    except subprocess.TimeoutExpired:
        return "Error: timeout after 10s"
    except Exception as e:
        return f"Error: {type(e).__name__}: {e}"


# === Cost calculation ===
MODEL_PRICING = {
    "claude-haiku-4-5": (0.000001, 0.000005),   # input, output per token
    "claude-sonnet-4": (0.000003, 0.000015),
}

def calc_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    in_p, out_p = MODEL_PRICING.get(model, (0.000003, 0.000015))
    return input_tokens * in_p + output_tokens * out_p


# === Retry with exponential backoff ===
def retry_with_backoff(fn, max_attempts=4):
    """Retry transient errors (rate limit / connection) with backoff."""
    for attempt in range(max_attempts):
        try:
            return fn()
        except anthropic.RateLimitError as e:
            if attempt == max_attempts - 1:
                raise
            wait = 2 ** attempt
            print(f"  [retry {attempt+1}/{max_attempts}] rate limit, waiting {wait}s")
            time.sleep(wait)
        except (anthropic.APIConnectionError, anthropic.APITimeoutError) as e:
            if attempt == max_attempts - 1:
                raise
            wait = 2 ** attempt
            print(f"  [retry {attempt+1}/{max_attempts}] connection error, waiting {wait}s")
            time.sleep(wait)


# === Working memory management ===
def total_chars(messages: list) -> int:
    return sum(len(str(m.get("content", ""))) for m in messages)

def maybe_prune(messages: list) -> list:
    """If over threshold, keep first + last 6, drop middle."""
    if total_chars(messages) < MAX_CONTEXT_CHARS * PRUNE_THRESHOLD:
        return messages
    if len(messages) <= 8:
        return messages
    return [messages[0]] + [{"role": "user", "content": "[earlier messages pruned for brevity]"}] + messages[-6:]


# === Main agent run ===
def run_agent(task: str, client, model: str = DEFAULT_MODEL, on_step=None) -> dict:
    """Run the agent loop. Returns {output, total_cost, total_steps, status}."""
    system_prompt = (
        "You are a careful assistant with file-reading and bash tools. "
        "Use tools when needed, don't hallucinate file contents. "
        "When you have enough information, give a concise final answer."
    )
    messages = [{"role": "user", "content": task}]
    trajectory = []
    total_cost = 0.0

    for step in range(MAX_STEPS):
        messages = maybe_prune(messages)
        try:
            response = retry_with_backoff(lambda: client.messages.create(
                model=model,
                system=system_prompt,
                tools=TOOLS,
                messages=messages,
                max_tokens=2048,
            ))
        except Exception as e:
            trajectory.append({"step": step, "type": "error", "error": str(e)})
            return {"output": f"[error] {type(e).__name__}: {e}",
                    "total_cost": total_cost, "total_steps": step,
                    "status": "failed", "trajectory": trajectory}

        in_t = response.usage.input_tokens
        out_t = response.usage.output_tokens
        cost = calc_cost(model, in_t, out_t)
        total_cost += cost

        trajectory.append({
            "step": step, "type": "llm_call",
            "model": model, "input_tokens": in_t, "output_tokens": out_t,
            "cost_usd": round(cost, 6),
            "stop_reason": response.stop_reason,
        })

        messages.append({"role": "assistant", "content": response.content})

        if total_cost > MAX_COST_USD:
            return {"output": f"[abort] cost ceiling ${MAX_COST_USD} hit",
                    "total_cost": total_cost, "total_steps": step + 1,
                    "status": "cost_exceeded", "trajectory": trajectory}

        if response.stop_reason != "tool_use":
            # Final answer
            text = next((b.text for b in response.content if hasattr(b, "text")), "")
            return {"output": text, "total_cost": total_cost,
                    "total_steps": step + 1, "status": "completed",
                    "trajectory": trajectory}

        # Execute all tool calls in parallel-ish (sequential is fine for demo)
        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            if on_step:
                on_step(step + 1, block.name, block.input)
            try:
                result = execute_tool(block.name, block.input)
                trajectory.append({
                    "step": step, "type": "tool_call",
                    "tool": block.name, "input": block.input,
                    "output_preview": result[:200],
                })
            except Exception as e:
                result = f"Error: {type(e).__name__}: {e}"
                trajectory.append({"step": step, "type": "tool_error",
                                   "tool": block.name, "error": str(e)})
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": result,
            })
        messages.append({"role": "user", "content": tool_results})

    return {"output": f"[abort] max steps {MAX_STEPS} reached",
            "total_cost": total_cost, "total_steps": MAX_STEPS,
            "status": "max_steps", "trajectory": trajectory}


def save_trajectory(task: str, result: dict) -> None:
    """Append trajectory to JSONL for later analysis."""
    record = {
        "timestamp": datetime.now().isoformat(),
        "task": task[:200],
        "status": result["status"],
        "total_cost_usd": round(result["total_cost"], 6),
        "total_steps": result["total_steps"],
        "steps": result["trajectory"],
    }
    with open(TRAJECTORY_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
