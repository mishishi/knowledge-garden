"""
09-code-review-project / main.py

入口脚本：读取 diff → 启动 CodeReviewer Multi-Agent → 输出报告

运行：
    export OPENAI_API_KEY=sk-xxx
    python main.py
    python main.py --diff "$(git diff HEAD~1)"
"""
import argparse
import sys
from pathlib import Path

from crew import create_review_crew


def load_diff(source: str) -> str:
    """加载 diff：可以是文件、stdin 或 git 命令"""
    if source.startswith("git "):
        import subprocess
        result = subprocess.run(source.split(), capture_output=True, text=True)
        return result.stdout
    elif Path(source).exists():
        return Path(source).read_text()
    else:
        return source


def main():
    parser = argparse.ArgumentParser(description="Code Reviewer Multi-Agent")
    parser.add_argument(
        "--diff",
        default="data/sample_diff.txt",
        help="diff 来源：文件路径、git 命令、或 diff 字符串",
    )
    parser.add_argument(
        "--output",
        default="output/review_report.md",
        help="报告输出路径",
    )
    args = parser.parse_args()

    diff = load_diff(args.diff)
    print(f"[Main] 加载 diff：{len(diff)} 字符")

    print("[Main] 启动 CodeReviewer Multi-Agent...")
    crew = create_review_crew()
    result = crew.kickoff(inputs={"diff": diff})

    # 保存报告
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(result.raw if hasattr(result, "raw") else str(result))

    print(f"\n[Main] 评审报告已保存到 {output_path}")
    print("\n" + "=" * 60)
    print(str(result))


if __name__ == "__main__":
    main()