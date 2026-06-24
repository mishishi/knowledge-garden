"""
Demo: real agent task using the minimal harness.

Task: read demos/harness-minimal/README.md, summarize in 3 bullets.

Usage:
    export ANTHROPIC_API_KEY=sk-ant-xxx
    python demo.py
"""
import os
import sys
from pathlib import Path

# Add this directory to path so we can import agent
HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

import agent  # noqa: E402


def main():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: set ANTHROPIC_API_KEY first", file=sys.stderr)
        sys.exit(1)

    client = agent.anthropic.Anthropic()
    task = (
        "Use the read_file tool to read 'demos/harness-minimal/README.md', "
        "then summarize it in exactly 3 bullet points. "
        "(On Windows, use python -c instead of ls/dir for listing files.)"
    )

    print(f"Task: {task}\n")
    print("Running agent...\n")

    def on_step(step_num, tool_name, tool_input):
        print(f"  [step {step_num}] {tool_name}({tool_input})")

    result = agent.run_agent(task, client, on_step=on_step)

    print("\n=== Final answer ===")
    print(result["output"])
    print(f"\n=== Stats ===")
    print(f"Cost:    ${result['total_cost']:.6f}")
    print(f"Steps:   {result['total_steps']}")
    print(f"Status:  {result['status']}")
    print(f"\nTrajectory appended to {agent.TRAJECTORY_FILE}")


if __name__ == "__main__":
    main()
