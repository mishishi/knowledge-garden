"""
09-code-review-project / tools/file_reader.py

读文件内容的工具
"""
from pathlib import Path

from crewai.tools import tool


@tool("Read File")
def read_file(file_path: str) -> str:
    """读取指定路径的文件内容。

    Args:
        file_path: 文件绝对路径或相对路径

    Returns:
        文件内容
    """
    try:
        path = Path(file_path)
        if not path.exists():
            return f"错误：文件不存在 {file_path}"
        if path.stat().st_size > 1_000_000:
            return f"错误：文件过大 ({path.stat().st_size} bytes)，请用其他方式"
        return path.read_text()
    except Exception as e:
        return f"错误：读取失败 {e}"


@tool("List Changed Files")
def list_changed_files(diff: str) -> str:
    """从 diff 中提取改动的文件列表。

    Args:
        diff: Git diff 文本

    Returns:
        文件列表（每行一个）
    """
    files = []
    for line in diff.split("\n"):
        if line.startswith("diff --git"):
            # 格式: diff --git a/path/to/file b/path/to/file
            parts = line.split()
            if len(parts) >= 4:
                files.append(parts[2][2:])  # 去掉 "a/" 前缀
    return "\n".join(files) if files else "没有改动文件"