"""
批量修 AI 味 — 处理 22 章 pending:
1. 去装饰 emoji (⚠️💡✅❌🎯) - 替换为纯文字描述
2. 删教学大纲模板段 (## 本章核心 / ## 下篇 / ## 这一章要回答的问题)
3. 减少 ### 子标题 (合并到段落, 用 ## 替换)
4. 砍冗余对比表

跑: python _fix_ai_flavor.py [--dry-run]
"""
import re
import sys
from pathlib import Path

BOOKS_DIR = Path("D:/workspaces/mcode/knowledge-garden/books")
HARNESS_SERIES = {"harness-engineering"}

# 装饰 emoji 替换为文字
EMOJI_REPLACEMENTS = {
    "⚠️ ": "",       # warning 装饰, 直接删
    "💡 ": "",       # tip 装饰
    "✅ ": "",       # check 装饰
    "❌ ": "",       # cross 装饰
    "🎯 ": "",       # target 装饰
    "⚠️": "", "💡": "", "✅": "", "❌": "", "🎯": "",
}

# 教学大纲模板 - 删除整个段落 (从 ## 标题到下一个 ## 或文件末尾)
TEACHING_PATTERNS = [
    re.compile(r"^##\s+(本章核心|这一章要回答的问题|下篇|下章|本章小结|本章回顾)[^\n]*\n(?:(?!^## ).*\n?)*", re.M),
]

# 章节内的 "## 下篇" 段要替换成简洁单行 (保留链接)
def simplify_next_link(content: str) -> str:
    """把 ## 下篇 + 段描述 + 链接 简化成单行 next: [title](link)"""
    pattern = re.compile(
        r"^##\s+(?:下篇|下章|下一篇)[^\n]*\n+"
        r"(?:.*?\n)*?"
        r"\[([^\]]+)\]\(([^)]+)\)[^\n]*\n?",
        re.M
    )
    return pattern.sub(r"[下一章](\2)\n", content)


def fix_file(path: Path, dry_run=True) -> tuple[str, list[str]]:
    """Apply fixes, return (new_content, list_of_changes)."""
    content = path.read_text(encoding="utf-8")
    changes = []
    new = content

    # 1. 去装饰 emoji
    for emoji, replacement in EMOJI_REPLACEMENTS.items():
        if emoji in new:
            count = new.count(emoji)
            new = new.replace(emoji, replacement)
            changes.append(f"去 emoji '{emoji}' x{count}")

    # 2. 删教学大纲模板段
    for pattern in TEACHING_PATTERNS:
        matches = pattern.findall(new)
        if matches:
            new = pattern.sub("", new)
            for m in matches:
                changes.append(f"删教学段: '{m.split(chr(10))[0][:40]}...'")

    # 3. 简化 ## 下篇 为单行链接
    if re.search(r"^##\s+(下篇|下章)", new, re.M):
        new = simplify_next_link(new)
        changes.append("简化 ## 下篇 为单行链接")

    # 4. 砍冗余对比表 (保留 1 个最有信息密度的, 删其余)
    # 这个复杂, 不自动做 — 留给手动

    if new != content:
        if not dry_run:
            path.write_text(new, encoding="utf-8")

    return new, changes


def main():
    dry_run = "--dry-run" in sys.argv

    if dry_run:
        print("=== DRY RUN (no files written) ===\n")

    targets = []
    for series_dir in sorted(BOOKS_DIR.iterdir()):
        if not series_dir.is_dir() or series_dir.name in HARNESS_SERIES:
            continue
        for chapter_dir in sorted(series_dir.iterdir()):
            if not chapter_dir.is_dir():
                continue
            readme = chapter_dir / "README.md"
            if not readme.exists():
                continue
            targets.append(readme)

    print(f"扫描 {len(targets)} 章节\n")
    for path in targets:
        _, changes = fix_file(path, dry_run=dry_run)
        if changes:
            rel = path.relative_to(BOOKS_DIR.parent)
            print(f"--- {rel}")
            for c in changes:
                print(f"  {c}")


if __name__ == "__main__":
    main()
