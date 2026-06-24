"""
Run golden set against harness-minimal demo.

Loads evals/golden_set.json, runs each case, checks expectations, prints pass rate.

Usage:
    export ANTHROPIC_API_KEY=sk-ant-xxx
    python evals/run_eval.py
"""
import json
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).parent.parent
sys.path.insert(0, str(HERE))

import agent  # noqa: E402


def check_expectation(result: dict, trajectory: list, expected: dict) -> tuple[bool, str]:
    """Return (passed, reason)."""
    tools_called = [s["tool"] for s in trajectory if s.get("type") == "tool_call"]

    for tool in expected.get("must_call_tools", []):
        if tool not in tools_called:
            return False, f"expected to call {tool}, called {tools_called}"

    for tool in expected.get("must_not_call_tools", []):
        if tool in tools_called:
            return False, f"should not call {tool}"

    if "max_cost_usd" in expected:
        if result["total_cost"] > expected["max_cost_usd"]:
            return False, f"cost ${result['total_cost']:.4f} > ${expected['max_cost_usd']}"

    if "max_steps" in expected:
        if result["total_steps"] > expected["max_steps"]:
            return False, f"steps {result['total_steps']} > {expected['max_steps']}"

    output = result["output"]
    for phrase in expected.get("must_contain", []):
        if phrase.lower() not in output.lower():
            return False, f"output missing '{phrase}'"

    for phrase in expected.get("output_must_contain", []):
        if phrase not in output and phrase.lower() not in output.lower():
            # Check trajectory tool outputs as fallback
            tool_outputs = " ".join(
                s.get("output_preview", "") for s in trajectory if s.get("type") == "tool_call"
            )
            if phrase.lower() not in tool_outputs.lower():
                return False, f"output + tools missing '{phrase}'"

    pattern = expected.get("output_must_contain_pattern")
    if pattern:
        if not re.search(pattern, output, re.MULTILINE):
            tool_outputs = " ".join(
                s.get("output_preview", "") for s in trajectory if s.get("type") == "tool_call"
            )
            if not re.search(pattern, tool_outputs, re.MULTILINE):
                return False, f"no match for pattern '{pattern}'"

    return True, "OK"


def main():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: set ANTHROPIC_API_KEY first", file=sys.stderr)
        sys.exit(1)

    golden_path = HERE / "evals" / "golden_set.json"
    golden = json.loads(golden_path.read_text(encoding="utf-8"))

    client = agent.anthropic.Anthropic()

    results = []
    for case in golden["cases"]:
        print(f"\n[{case['id']}] {case['task']}")
        result = agent.run_agent(case["task"], client)
        passed, reason = check_expectation(result, result["trajectory"], case["expected"])
        status = "PASS" if passed else "FAIL"
        print(f"  → {status}: {reason}")
        print(f"     cost=${result['total_cost']:.4f} steps={result['total_steps']} status={result['status']}")
        results.append({"id": case["id"], "passed": passed, "reason": reason,
                        "cost": result["total_cost"], "steps": result["total_steps"]})

    passed_count = sum(1 for r in results if r["passed"])
    total_cost = sum(r["cost"] for r in results)
    print(f"\n=== Summary ===")
    print(f"Pass rate: {passed_count}/{len(results)} ({100*passed_count/len(results):.0f}%)")
    print(f"Total cost: ${total_cost:.4f}")

    if passed_count == len(results):
        print("\nAll cases passed.")
        sys.exit(0)
    else:
        print(f"\n{len(results) - passed_count} case(s) failed.")
        sys.exit(1)


if __name__ == "__main__":
    main()
