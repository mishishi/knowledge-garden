"""
09-code-review-project / tools/git_diff.py

读 Git diff 的工具
"""
import subprocess

from crewai.tools import tool


@tool("Get Git Diff")
def get_git_diff(commit: str = "HEAD") -> str:
    """获取指定 commit 的 Git diff。

    Args:
        commit: commit hash 或 ref，默认 HEAD

    Returns:
        diff 文本
    """
    try:
        result = subprocess.run(
            ["git", "diff", commit],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        return f"错误：无法获取 diff: {e.stderr}"


@tool("Get Current Branch Diff")
def get_current_branch_diff() -> str:
    """获取当前分支相对于 main 的 diff。

    Returns:
        diff 文本
    """
    try:
        result = subprocess.run(
            ["git", "diff", "main...HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        return f"错误：无法获取 diff: {e.stderr}"