# 10. 从零造一个 Harness：把前 9 章串起来

> 前 9 章讲了 harness 的 9 个组件。这一章把它们组合起来——给一个完整的项目结构、reference implementation、以及 prototype 演进到 production 的路径。

## 项目结构

我自己用的 production harness 结构：

```
my_harness/
├── pyproject.toml
├── README.md
├── harness/
│   ├── __init__.py
│   ├── agent.py           # 主 agent loop
│   ├── tools/             # 工具定义
│   │   ├── __init__.py
│   │   ├── base.py        # Tool 基类
│   │   ├── bash.py        # bash tool (with sandbox)
│   │   ├── file_ops.py    # read/write/edit
│   │   └── search.py      # grep / web search
│   ├── memory/
│   │   ├── __init__.py
│   │   ├── working.py     # messages 数组管理
│   │   ├── episodic.py    # SQLite append-only log
│   │   ├── semantic.py    # Chroma vector DB
│   │   └── procedural.py  # markdown + git
│   ├── recovery/
│   │   ├── __init__.py
│   │   ├── retry.py       # exponential backoff
│   │   ├── checkpoint.py  # git stash checkpoint
│   │   └── classifier.py  # failure 4-类分类
│   ├── permissions/
│   │   ├── __init__.py
│   │   ├── sandbox.py     # firejail / Docker
│   │   ├── allowlist.py   # regex allowlist
│   │   └── confirm.py     # 用户确认 UI
│   ├── context/
│   │   ├── __init__.py
│   │   ├── compact.py     # 4 种 compact 策略
│   │   └── cache.py       # prompt cache wrapper
│   └── observability/
│       ├── __init__.py
│       ├── trajectory.py  # 完整 step-by-step log
│       └── replay.py      # trajectory 重跑
├── eval/
│   ├── golden_set/        # YAML test cases
│   │   ├── simple_queries.yaml
│   │   ├── multi_step.yaml
│   │   └── edge_cases.yaml
│   ├── run_eval.py        # 跑全套
│   ├── judge.py           # LLM-as-judge
│   └── history/           # 历次 eval 结果
├── procedures/            # procedural memory (markdown)
│   ├── deploy-app.md
│   ├── github-pr.md
│   └── ...
├── checkpoints/           # git stash backups
├── trajectories.db        # SQLite episodic memory
├── chroma_data/           # vector DB
├── .env                   # API keys (gitignore)
└── docker-compose.yml     # Docker sandbox config
```

目录组织按"harness 组件"切分——每个组件一个子包，独立可测。

## Reference Implementation：800 行核心 agent loop

不是完整实现（完整会 5000+ 行），是简化到能展示关键设计的 800 行：

```python
# harness/agent.py
import anthropic
import json
import os
import subprocess
import time
import logging
from dataclasses import dataclass, field, asdict
from typing import Optional
from uuid import uuid4

from harness.tools import TOOL_REGISTRY, execute_tool
from harness.memory import WorkingMemory, EpisodicMemory, SemanticMemory
from harness.recovery import retry_with_backoff, classify_failure
from harness.permissions import check_permission, ask_user
from harness.context import maybe_compact
from harness.observability import TrajectoryCollector

logger = logging.getLogger(__name__)

# === Config ===
MAX_STEPS = 25
MAX_COST_USD = 1.0
MAX_CONTEXT_TOKENS = 180_000  # Claude Sonnet 4
COMPACT_THRESHOLD = 0.75

# === Main Agent ===
@dataclass
class AgentResult:
    output: str
    trajectory_id: str
    total_cost: float
    total_steps: int
    status: str

class Agent:
    def __init__(self, user_id: str, model: str = "claude-sonnet-4"):
        self.user_id = user_id
        self.model = model
        self.client = anthropic.Anthropic()
        self.working = WorkingMemory()
        self.episodic = EpisodicMemory("./trajectories.db")
        self.semantic = SemanticMemory("./chroma_data")
        self.system_prompt = self._build_system_prompt()
    
    def _build_system_prompt(self) -> str:
        # 召回 user profile + recent episodes
        user_facts = self.semantic.recall(self.user_id, limit=10)
        recent_episodes = self.episodic.search(self.user_id, days=7, limit=5)
        
        return f"""You are a personal assistant for user {self.user_id}.

User profile (always remember):
{chr(10).join(f'- {f}' for f in user_facts)}

Recent context (last 7 days):
{chr(10).join(episodes)}

Task constraints:
- Use tools when needed, don't hallucinate
- For dangerous operations (delete/write/send), confirm with user first
- Stop when task is complete, don't loop unnecessarily
"""
    
    def run(self, task: str) -> AgentResult:
        trace = TrajectoryCollector(user_id=self.user_id, task=task)
        self.working.add({"role": "user", "content": task})
        
        cost = 0.0
        try:
            for step in range(MAX_STEPS):
                # Cost gate
                if cost >= MAX_COST_USD:
                    return self._abort(trace, f"Cost ceiling ${MAX_COST_USD}", "cost_exceeded")
                
                # Context compact
                if self._context_too_big():
                    self.working.messages = maybe_compact(self.working.messages)
                
                # LLM call with retry
                try:
                    response = retry_with_backoff(
                        lambda: self.client.messages.create(
                            model=self.model,
                            system=self.system_prompt,
                            tools=list(TOOL_REGISTRY.values()),
                            messages=self.working.messages,
                            max_tokens=4096,
                        )
                    )
                except Exception as e:
                    return self._abort(trace, str(e), "llm_failure")
                
                # Track cost + record step
                cost += self._calc_cost(response)
                trace.record_llm(self.model, self.working.messages, response, cost)
                
                # Append assistant message
                self.working.add({"role": "assistant", "content": response.content})
                
                # Done?
                if response.stop_reason != "tool_use":
                    final_text = next(b.text for b in response.content if hasattr(b, "text"))
                    trace.save(status="completed")
                    self.episodic.record(self.user_id, task, "completed", trace.trace_id)
                    return AgentResult(
                        output=final_text,
                        trajectory_id=trace.trace_id,
                        total_cost=cost,
                        total_steps=step + 1,
                        status="completed",
                    )
                
                # Execute tool calls (parallel where possible)
                tool_results = self._execute_tools(response.content, trace)
                self.working.add({"role": "user", "content": tool_results})
            
            return self._abort(trace, f"Max steps {MAX_STEPS} reached", "max_steps")
        
        except Exception as e:
            return self._abort(trace, str(e), "error")
    
    def _execute_tools(self, content, trace):
        """Execute all tool_use blocks, parallel where safe"""
        import asyncio
        
        tool_uses = [b for b in content if b.type == "tool_use"]
        results = []
        
        for use in tool_uses:
            # Permission check
            allowed, reason = check_permission(use.name, use.input)
            if not allowed:
                if reason == "needs_confirmation":
                    user_approved, deny_reason = ask_user(use.name, use.input)
                    if not user_approved:
                        results.append({
                            "type": "tool_result",
                            "tool_use_id": use.id,
                            "content": f"Error: user denied. {deny_reason or ''}",
                            "is_error": True,
                        })
                        continue
                else:
                    results.append({
                        "type": "tool_result",
                        "tool_use_id": use.id,
                        "content": f"Error: blocked - {reason}",
                        "is_error": True,
                    })
                    continue
            
            # Execute with retry + checkpoint
            try:
                result = execute_tool(use.name, use.input)
                trace.record_tool(use.name, use.input, result)
                results.append({
                    "type": "tool_result",
                    "tool_use_id": use.id,
                    "content": result if isinstance(result, str) else json.dumps(result),
                })
            except Exception as e:
                # Classify failure
                category = classify_failure(e, {"state_changed": True})
                if category.value == "transient":
                    # Retry
                    result = retry_with_backoff(lambda: execute_tool(use.name, use.input))
                    results.append({
                        "type": "tool_result",
                        "tool_use_id": use.id,
                        "content": str(result),
                    })
                else:
                    results.append({
                        "type": "tool_result",
                        "tool_use_id": use.id,
                        "content": f"Error: {type(e).__name__}: {e}",
                        "is_error": True,
                    })
        
        return results
    
    def _context_too_big(self) -> bool:
        # 估算 tokens（粗略）
        total_chars = sum(len(str(m.get("content", ""))) for m in self.working.messages)
        est_tokens = total_chars / 3  # 粗估
        return est_tokens > MAX_CONTEXT_TOKENS * COMPACT_THRESHOLD
    
    def _calc_cost(self, response) -> float:
        # Anthropic pricing
        prices = {
            "claude-sonnet-4": (0.000003, 0.000015),  # input, output per token
            "claude-opus-4": (0.000015, 0.000075),
        }
        in_price, out_price = prices.get(self.model, (0.000003, 0.000015))
        return (
            response.usage.input_tokens * in_price +
            response.usage.output_tokens * out_price
        )
    
    def _abort(self, trace, reason, status) -> AgentResult:
        trace.save(status=status)
        self.episodic.record(self.user_id, trace.task, status, trace.trace_id)
        return AgentResult(
            output=f"Aborted: {reason}",
            trajectory_id=trace.trace_id,
            total_cost=0,
            total_steps=0,
            status=status,
        )

# === Entry point ===
if __name__ == "__main__":
    import sys
    user_id = os.getenv("USER_ID", "default")
    task = sys.argv[1] if len(sys.argv) > 1 else input("Task: ")
    
    agent = Agent(user_id=user_id)
    result = agent.run(task)
    
    print(f"\n=== Result ===")
    print(result.output)
    print(f"\nCost: ${result.total_cost:.4f} | Steps: {result.total_steps} | Status: {result.status}")
    print(f"Trace: {result.trajectory_id}")
```

800 行代码包含 9 个组件的最小可用实现。production 版本会扩到 5000+ 行（更多 tool、更多 memory 类型、更复杂 recovery），但核心循环不变。

## Prototype → Production 演进

我自己的演进路径（4 个阶段）：

**Stage 1：单文件 prototype（300 行）**

```python
# harness_v1.py - 全部逻辑在一个文件
import anthropic

client = anthropic.Anthropic()
messages = [{"role": "user", "content": input("Task: ")}]

while True:
    resp = client.messages.create(model="claude-sonnet-4", messages=messages, max_tokens=4096)
    print(resp.content[0].text)
    messages.append({"role": "assistant", "content": resp.content})
    if input("Continue? [y/N] ").lower() != "y":
        break
    messages.append({"role": "user", "content": input("Next: ")})
```

适用：demo / 个人小工具 / 验证 idea。**别 ship 这版**——任何 tool 调用都可能让你删错文件。

**Stage 2：加 tools + permissions（800 行）**

把 tool 系统拆出来，加 sandbox 和 permission check。可以 ship 给早期用户（trusted users）。

**Stage 3：加 memory + observability（2000 行）**

加 working / episodic / semantic memory，加 trajectory logging，加 basic recovery。production beta 版。

**Stage 4：加 eval + recovery + checkpoint（5000+ 行）**

完整 harness，加 golden set + CI eval + checkpoint + 完整 sandbox。production stable。

每个 stage 通常 2-4 周。**不要跳过 stage 1 直接做 stage 4**——跳过意味着 5000 行里 80% 是无用的猜测代码。

## 跟其他 stack 对比

我用过 3 个 mainstream agent stack 的实操感受：

**LangGraph（LangChain 生态）**

- 优势：state graph 抽象清晰、可视化 debug、LangSmith 集成好
- 劣势：vendor lock-in、抽象层多（harness 改起来要 wrap LangChain 接口）、自部署复杂
- 适合：multi-agent 编排复杂场景、需要 graph 可视化、LangChain 团队

**Claude Agent SDK（Anthropic 官方）**

- 优势：Anthropic 内部 harness 抽出来、稳定、permission system 现成
- 劣势：跟 Claude API 深度绑定（其他模型要 hack）、定制空间有限
- 适合：Claude 单一模型、快速 production、不需要高度定制

**自研 harness（这章讲的）**

- 优势：完全可控、可学可改、跨模型、无 vendor lock-in
- 劣势：开发成本高（5000 行 + eval）、维护成本高（harness 升级要自己搞）
- 适合：教学 / research / 不想 vendor lock-in / harness 本身就是产品

我自己的 production 项目一半用 Claude Agent SDK（快速迭代），一半自研（核心 learning + 不被 vendor 绑架）。

## 这章踩过的关键坑

**Stage 1 直接 ship**——"我都跑通了为啥不发布"。修：prototype 只用来 demo 和 learning，不 ship 任何 stage 1 代码给真实用户。

**Stage 4 一次性写完 5000 行**——结果 60% 是错的（后来发现真正需要的功能只占 40%）。修：stage 2 → stage 3 → stage 4，每个 stage 之间有真实用户反馈。

**不写 eval 就升级 harness**——每次升级 prompt / tool / memory schema 都没跑测试。修：stage 3 开始必须有 eval，stage 4 完整 CI。

**Memory schema 升级没 migration**——semantic memory schema 改了，旧 user facts 全废。修：所有 schema 升级必须有 migration script + backfill。

**Trajectory 数据没 retention 策略**——半年后 100GB trajectory 数据。修：每 90 天压缩老 trajectory 成 summary。

## 整个系列回顾

10 章覆盖了 harness 的 9 个核心组件：

1. 什么是 harness + 为什么是 first-class
2. Agent loop 8 种变体
3. Tool 设计原则（schema / error / retry / parallel）
4. Context 管理（compact / cache / long doc）
5. Permissions / Sandbox（4 层防御 + prompt injection）
6. Observability（trajectory / cost / latency）
7. Memory 分层（working / episodic / semantic / procedural）
8. Failure recovery（retry / rollback / checkpoint）
9. Eval-driven development（golden set + LLM-as-judge + regression）
10. 从零造一个 harness（reference impl + 演进路径）

每一章都是独立的，可以单独读。但顺序读能建立完整 mental model。

下一步建议：
- **做**：用 Stage 2 模板写一个 800 行 harness 跑你的实际任务（取代你重复劳动的部分）
- **学**：读 Claude Code / Devin / Cursor 的源码（它们是这系列概念的 production 实现）
- **避坑**：不要一开始就做 stage 4——harness 的复杂度会让你 80% 时间在 debug harness 而不是用 harness

如果你读完整个系列还是觉得 harness 太复杂——可能你不需要自研，用 Claude Agent SDK / LangGraph 就够了。Harness engineering 是给需要高度定制或不愿 vendor lock-in 的人，不是给所有 agent 用户。

## 真能跑的 demo

章节里那个 800 行 reference implementation 是结构化伪代码。我把它简化成 **270 行真能跑的 Python** 放在 [`demos/harness-minimal/`](../../demos/harness-minimal/)：

- `agent.py` — 完整的最小 harness（agent loop + 2 tools + allowlist + retry + trajectory）
- `demo.py` — 真实任务演示（读 README → 3 段总结）
- `evals/golden_set.json` + `run_eval.py` — 5 个 golden set case + 自动评分

跑起来：

```bash
cd demos/harness-minimal
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-xxx
python demo.py
```

实际输出（用 Haiku 4.5 单次跑的样本）：

```
Task: Use the read_file tool to read 'demos/harness-minimal/README.md'...
Running agent...
  [step 1] read_file({'path': 'demos/harness-minimal/README.md'})
  [step 2] bash({'cmd': 'python -c "import os; print(len(open(...).readlines()))"'})

=== Final answer ===
Summary of demos/harness-minimal/README.md:
- Harness Minimal Demo: a runnable 270-line agent harness based on ch 10
- Demonstrates 7 of 9 components (skips vector memory + checkpoint for brevity)
- Setup: pip install + export ANTHROPIC_API_KEY + python demo.py

Cost: $0.0031 | Steps: 2 | Status: completed
```

干跑（没有 API key）会失败，但工具函数本身可以本地测：

```bash
python -c "
import sys; sys.path.insert(0, 'demos/harness-minimal')
import agent
print(agent.execute_tool('bash', {'cmd': 'dir demos'}))
print(agent.execute_tool('read_file', {'path': 'demos/harness-minimal/README.md'})[:100])
"
```

期望看到 `dir` 命令的输出和 README 前 100 字符——证明 tool 层工作正常。

这套 demo 是把 ch 10 从「读得懂」变成「跑得起来」的最小桥。读 chapter 学概念，跑 demo 验证概念，两件事都做了这系列才闭环。
