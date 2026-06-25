"""AI-flavor scan that excludes code blocks. Reports per chapter."""
import os, re, json, sys
ROOT = r"D:\workspaces\mcode\knowledge-garden\books\claude-code"
PATTERNS = {
    "h3": r"(?m)^### ",
    "h2": r"(?m)^## ",
    "emoji": r"[⚠️💡✅❌🎯🔥✨🚀📋📊]",
    "硬编号": r"(?m)^\s*\d+[、.]\s*[\u4e00-\u9fff]",  # 1. xxx / 一、xxx
    "教学模板": r"^## (本章核心|这一章要回答的问题|下篇|小结|总结|核心原则)",
    "表格行": r"(?m)^\|",
}
def strip_codeblocks(text):
    # remove fenced ```...``` blocks
    text = re.sub(r"```[\s\S]*?```", "", text)
    # remove inline code
    text = re.sub(r"`[^`]+`", "", text)
    return text
def scan_one(path):
    with open(path, encoding="utf-8") as f:
        c = f.read()
    c2 = strip_codeblocks(c)
    lines = c.count("\n") + 1
    return {
        "lines": lines,
        "scores": {k: len(re.findall(p, c2)) for k, p in PATTERNS.items()},
        "h3_list": [m.group(0) for m in re.finditer(PATTERNS["h3"], c2)][:8],
    }
for d in sorted(os.listdir(ROOT)):
    full = os.path.join(ROOT, d, "README.md")
    if not os.path.isfile(full):
        continue
    r = scan_one(full)
    s = r["scores"]
    flags = [k for k, v in s.items() if v > 0 and k != "h2"]
    # h3 limit
    if s["h3"] > 3:
        flags.append(f"h3={s['h3']}")
    print(f"{d}: L={r['lines']}, " + ", ".join(f"{k}={v}" for k, v in s.items() if v > 0) + (f"  ⚠️  FLAGS: {','.join(flags)}" if flags else ""))
