#!/usr/bin/env python3
"""
知识花园 — 系列文章自动化生成器

Usage:
  python tools/generate_series.py --topic "Prompt Caching 实战" --chapters 8
  python tools/generate_series.py --topic "..." --dry-run          # 只生成 meta + outline
  python tools/generate_series.py --topic "..." --auto-build       # 生成完跑 build_reader.py
  python tools/generate_series.py --topic "..." --model MiniMax-M2.7

[依赖]
- mmx (MiniMax text generation CLI): https://github.com/m1guelpf/mmx-cli
  或 npm i -g mmx
- _fix_ai_flavor.py 规则已固化在 docs/STYLE.md (单一 source-of-truth)

[生成流程]
1. Slug auto-gen from topic
2. LLM: 生成书 description
3. LLM: 生成 N 章 outline (titles + 1-line each)
4. LLM (per chapter): 生成章节 README.md, 注入 STYLE 规则 prompt
5. 写 _meta.json
6. 写 code/ stub (README.md + requirements.txt)
7. AI-味 验证 (按 STYLE.md 规则)
8. 可选: --auto-build 跑 build_reader.py

[输出]
- books/<slug>/_meta.json
- books/<slug>/<NN>-<chapter-slug>/README.md
- books/<slug>/<NN>-<chapter-slug>/code/README.md
- books/<slug>/<NN>-<chapter-slug>/code/requirements.txt
"""
import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional

# 路径常量
ROOT = Path(__file__).resolve().parents[1]
BOOKS_DIR = ROOT / "books"
STYLE_DOC = ROOT / "docs" / "STYLE.md"

# ============================================================
# 资源池 (从 build_reader.py ICONS dict 和现有书的元信息提取)
# ============================================================

ICON_POOL = [
    "agents", "sparkles", "bot", "database", "layers", "share", "brain",
    "stack", "terminal", "network", "pen-tool", "zap", "wind", "rocket",
    "coin", "bookmark", "qr", "disc", "book",
]

# 已用 icon (避免重复)
USED_ICONS = {
    "network", "coin", "sparkles", "pen-tool", "terminal", "zap", "stack",
    "bot", "layers", "rocket", "brain", "agents", "database", "wind", "book",
}

# 主题 → 候选色 + 候选 icon
TOPIC_HINTS = {
    "严肃": {"colors": ["#0d9488", "#0891b2", "#4f46e5", "#059669"], "icons": ["stack", "database", "terminal", "layers"]},
    "创意": {"colors": ["#ec4899", "#d97706", "#f59e0b", "#dc2626"], "icons": ["sparkles", "pen-tool", "rocket", "zap"]},
    "入门": {"colors": ["#5b8c85", "#7c3aed", "#0ea5e9"], "icons": ["book", "bot", "bookmark"]},
    "工具": {"colors": ["#0d9488", "#7c3aed", "#4f46e5"], "icons": ["terminal", "qr", "stack"]},
    "经济": {"colors": ["#f59e0b", "#dc2626", "#d97706"], "icons": ["coin", "rocket"]},
    "网络": {"colors": ["#0ea5e9", "#4f46e5", "#0891b2"], "icons": ["network", "share"]},
    "记忆": {"colors": ["#f59e0b", "#7c3aed", "#ec4899"], "icons": ["brain", "stack"]},
    "系统": {"colors": ["#059669", "#0d9488", "#0891b2"], "icons": ["stack", "layers", "terminal"]},
    "生成": {"colors": ["#ec4899", "#d97706", "#dc2626"], "icons": ["sparkles", "pen-tool", "zap"]},
    "开发": {"colors": ["#0891b2", "#4f46e5", "#059669"], "icons": ["terminal", "stack", "code"]},
    "中文": {"colors": ["#dc2626", "#d97706", "#f59e0b"], "icons": ["zap", "rocket", "pen-tool"]},
}

FALLBACK_COLORS = ["#b08968", "#0d9488", "#7c3aed", "#0891b2", "#4f46e5",
                   "#059669", "#dc2626", "#d97706", "#ec4899", "#5b8c85"]


# ============================================================
# Slug + 元信息 工具
# ============================================================

def topic_to_slug(topic: str) -> str:
    """'Prompt Caching 实战' → 'prompt-caching' (去掉 '实战'/'入门'/'基础' 等通用词)"""
    # 中文 → 拼音映射 (够用就行, 不全)
    cn_map = {
        "实战": "", "入门": "", "基础": "", "进阶": "", "精通": "",
        "教程": "", "指南": "", "手册": "", "全栈": "", "深入": "",
        "系统": "", "完整": "", "全面": "", "从零到": "", "生产级": "",
    }
    s = topic.strip()
    for k, v in cn_map.items():
        s = s.replace(k, v)
    # 转小写, 空格 → -, 去标点
    s = re.sub(r"[\s_]+", "-", s.lower())
    s = re.sub(r"[^a-z0-9\-]", "", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s or "untitled"


def slugify_chapter(title: str) -> str:
    """'为什么需要 Multi-Agent' → 'why-multi-agent' (中文用拼音没法, 退化用 hex)"""
    cn_map = {
        "为什么": "why", "怎么": "how", "什么": "what", "如何": "how",
        "基础": "basics", "入门": "intro", "实战": "in-practice", "案例": "cases",
        "工具": "tools", "模式": "patterns", "框架": "framework",
        "性能": "perf", "测试": "testing", "部署": "deploy", "上线": "deploy",
        "回顾": "recap", "小结": "recap", "总结": "recap", "展望": "future",
    }
    s = title.strip().lower()
    for k, v in cn_map.items():
        s = s.replace(k, v)
    s = re.sub(r"[\s_]+", "-", s)
    s = re.sub(r"[^a-z0-9\-]", "", s)
    s = re.sub(r"-+", "-", s).strip("-")
    if not s:
        # 纯中文 → 用 Pinyin 太复杂, 用 topic 长度 + hash 兜底
        s = re.sub(r"\s+", "-", title[:20]).lower()
        s = re.sub(r"[^a-z0-9\-]", "", s)
    return s or "chapter"


def pick_color_icon(topic: str) -> tuple[str, str]:
    """根据 topic 关键词 选 color + icon. 都用 hash 兜底."""
    color, icon = None, None
    for kw, hint in TOPIC_HINTS.items():
        if kw in topic:
            color = hint["colors"][hash(topic + "color") % len(hint["colors"])]
            icon = hint["icons"][hash(topic + "icon") % len(hint["icons"])]
            break
    if not color:
        color = FALLBACK_COLORS[hash(topic) % len(FALLBACK_COLORS)]
    if not icon or icon in USED_ICONS:
        avail = [i for i in ICON_POOL if i not in USED_ICONS]
        icon = avail[hash(topic) % len(avail)] if avail else ICON_POOL[hash(topic) % len(ICON_POOL)]
    return color, icon


def already_exists(slug: str) -> bool:
    return (BOOKS_DIR / slug).exists()


# ============================================================
# LLM 调用 (mmx CLI 封装)
# ============================================================

def _find_mmx() -> str:
    """在 PATH 里找 mmx 绝对路径, 找不到返回 'mmx' (走 fallback)."""
    import shutil
    p = shutil.which("mmx")
    if p:
        return p
    # Windows: 走 where.exe 再试
    import subprocess as sp
    try:
        r = sp.run(["where.exe", "mmx"], capture_output=True, text=True, shell=True)
        for line in r.stdout.splitlines():
            line = line.strip()
            if line and Path(line).exists():
                return line
    except Exception:
        pass
    return "mmx"


def llm_chat(prompt: str, system: str = "", model: str = "abab6.5s-chat",
             max_tokens: int = 4096) -> str:
    """调 mmx text chat, 返回生成内容.
    mmx 返回结构: {"content": [{"type": "thinking", ...}, {"type": "text", "text": "..."}]}.
    - 只取 type="text" 部分
    - prompt 过长 (Windows CLI 限制 ~8KB) 时改用 --messages-file 临时文件
    - 失败抛 RuntimeError"""
    import tempfile
    mmx = _find_mmx()
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    # 始终用 --messages-file (数组格式), 避开 Windows CLI 长度限制 + mmx --message 中文长字符串解析 bug
    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8", dir=tempfile.gettempdir()
    )
    json.dump(messages, tmp, ensure_ascii=False)
    tmp.close()
    cmd = [mmx, "text", "chat", "--model", model, "--max-tokens", str(max_tokens),
           "--messages-file", tmp.name]
    use_file = True
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    except FileNotFoundError:
        raise RuntimeError("mmx CLI 未安装. 跑 `npm i -g mmx` 安装.")
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"mmx 超过 300s timeout. prompt: {prompt[:100]}...")
    finally:
        if use_file:
            try:
                os.unlink(tmp.name)
            except OSError:
                pass
    if r.returncode != 0:
        raise RuntimeError(f"mmx 退出 {r.returncode}: {r.stderr.strip()[:500]}")
    try:
        data = json.loads(r.stdout)
    except json.JSONDecodeError:
        return r.stdout.strip()
    content_items = data.get("content", [])
    if isinstance(content_items, list):
        text_parts = [c.get("text", "") for c in content_items if c.get("type") == "text"]
        content = "\n".join([p for p in text_parts if p])
    else:
        content = (
            data.get("text")
            or data.get("message", {}).get("content")
            or data.get("choices", [{}])[0].get("message", {}).get("content")
            or ""
        )
    if not content or not content.strip():
        stop = data.get("stop_reason", "?")
        usage = data.get("usage", {})
        raise RuntimeError(
            f"mmx 返回空 content. stop_reason={stop}, "
            f"output_tokens={usage.get('output_tokens')}, "
            f"data: {json.dumps(data)[:300]}"
        )
    return content.strip()


# ============================================================
# Prompts
# ============================================================

def style_rules_block() -> str:
    """从 docs/STYLE.md 抽 '不写' + '要写' 块, 作为 system prompt 注入."""
    return """\
你是知识花园的作者, 给技术读者写 3000-5000 字的深度章节.

[硬规则 — 违反就失败]
- 不出现 ⚠️💡✅❌🎯 等装饰 emoji (任何位置都不行)
- 不出现 "## 本章核心" / "## 本章小结" / "## 这一章要回答的问题" / "## 下篇" / "## 下章" 单独成段
- ≤ 3 个 ### 子标题 (建议用 ## 替代或直接段落)
- ≤ 1 个对比表 (markdown | 表格)
- 段首不放 "核心原则: ..." / "为什么 X 重要: ..." 这种总结句
- 末尾不放硬编号 "误区 1/2/3" / "步骤 1/2/3"

[人味原则 — 必须遵守]
- 第一人称叙述 ("我" / "我们")
- 短长段交替: 3-5 句紧接 1-2 段长的 (举例 / 推演)
- 口语连接词: "等下" / "其实" / "换句话说" / "我踩过的坑"
- 具体数字: "3.2x 提升" / "省 47 秒" 优于 "显著提升"
- 真实细节: 报错信息 / API 名称 / 用过的工具
- ≥ 2 段代码, 每段 ≤ 30 行, 必须可运行或接近可运行
- 代码用 ```python 包裹, 注释用中文

[输出格式]
- 文件首行: # NN. 标题
- 第二行: > 一句话副标题 (≤ 60 字)
- 不要 frontmatter, 不要 _meta.json
- 不要在末尾写 "## 下篇" 段, 用单行 [下一章](<相对路径>) 收尾
- 输出纯 markdown, 不要任何解释 / "好的以下是..." / "Here is the chapter"
"""


def prompt_description(topic: str) -> str:
    return f"""为主题 "{topic}" 生成 1 句话系列描述, 30 字以内, 不要 emoji 不要感叹号.

要求: 说清"谁读" + "读完会什么". 例: "从零到生产: 手把手教你构建 Multi-Agent 系统"

只输出描述本身, 1 行, 不要任何标头/解释."""


def prompt_outline(topic: str, n: int) -> str:
    return f"""为主题 "{topic}" 设计 {n} 个章节大纲.

只输出 {n} 行, 严格每行格式:
NN. 标题 — 一句话核心问题

约束:
- NN 是 2 位数字 (01, 02, ..., {n:02d})
- 标题 6-15 字, 简洁
- 破折号是 " — " (空格 + 破折号 + 空格), 不是 "-"
- 一句话核心问题 ≤ 30 字
- 不输出任何 # 标题 / ## 子标题 / 列表 / 解释 / 前缀
- 章节顺序有递进 (why → what → how → 实战 → 避坑)

例:
01. 工具链搭建 — 开发环境配置和依赖安装
02. 核心概念 — 解释底层原理和关键术语
03. 实战案例 — 从零做一个最小可运行示例

现在开始 (只输出 {n} 行):"""


def prompt_chapter(topic: str, chapter_idx: int, total: int,
                   chapter_title: str, one_liner: str,
                   next_chapter_path: Optional[str]) -> str:
    next_link = ""
    if next_chapter_path:
        next_link = f"\n\n末尾一行: [下一章]({next_chapter_path})"
    return f"""写 "{topic}" 系列的第 {chapter_idx}/{total} 章.

章标题: {chapter_title}
核心问题: {one_liner}

要求:
- 严格遵守硬规则 + 人味原则
- 字数 3000-5000 字
- 结构: 第一节 (hook + 场景) → 第二节 (核心 + 1-2 段代码) → 第三节 (陷阱 / 边界 / 经验)
- 数字具体: 拒绝"显著提升", 用 "3.2x 提升" "省 47 秒" "失败率从 12% → 1.8%"
- ≥ 2 段代码, 每段 ≤ 30 行, 代码包裹 ```python ... ```
- 不要 _meta.json / frontmatter / "好的以下是"
- 文件首行: # {chapter_idx:02d}. {chapter_title}
- 第二行: > 一句话副标题 (≤ 60 字, 不要 emoji){next_link}

直接输出 markdown, 1 段不漏."""


# ============================================================
# AI-味 验证 (按 STYLE.md 规则)
# ============================================================

EMOJI_BLACKLIST = re.compile(r"[⚠️💡✅❌🎯]")
TEACHING_HEADERS = re.compile(
    r"^##\s+(本章核心|本章小结|本章回顾|这一章要回答的问题|下篇|下章|下一篇|小结|总结|回顾)\s*$",
    re.M
)


def check_ai_flavor(md_text: str) -> list[str]:
    """返回问题列表. [] = 通过."""
    issues = []
    # 1. 装饰 emoji
    matches = EMOJI_BLACKLIST.findall(md_text)
    if matches:
        issues.append(f"含装饰 emoji ({len(matches)} 处): {''.join(set(matches))}")
    # 2. 教学模板段
    teaching = TEACHING_HEADERS.findall(md_text)
    if teaching:
        issues.append(f"教学模板段 ({len(teaching)} 处): {teaching}")
    # 3. ### 子标题数
    h3_count = len(re.findall(r"^###\s+", md_text, re.M))
    if h3_count > 3:
        issues.append(f"### 子标题数 {h3_count} > 3 (建议用 ## 替代)")
    # 4. 表格数 (粗略: 算 |---| 行)
    table_count = len(re.findall(r"^\|[\s\-:|]+\|\s*$", md_text, re.M))
    if table_count > 1:
        issues.append(f"对比表 {table_count} 个 > 1")
    # 5. 字数
    # 去 markdown 标记粗略字数
    plain = re.sub(r"```.*?```", "", md_text, flags=re.S)
    plain = re.sub(r"[#*`>|\-\[\]()]+\s*", "", plain)
    plain = re.sub(r"\s+", "", plain)
    cn_chars = len(re.findall(r"[\u4e00-\u9fff]", plain))
    if cn_chars < 1500:
        issues.append(f"字数 {cn_chars} < 1500 (建议 3000-5000)")
    elif cn_chars > 6000:
        issues.append(f"字数 {cn_chars} > 6000 (可能太长)")
    # 6. 代码块
    code_blocks = len(re.findall(r"```\w+", md_text))
    if code_blocks < 1:
        issues.append(f"代码块 {code_blocks} 个, 建议 ≥ 2")
    return issues


# ============================================================
# 主流程
# ============================================================

def gen_description(topic: str, model: str) -> str:
    """LLM 生成书描述."""
    out = llm_chat(prompt_description(topic), model=model, max_tokens=300)
    # 清理: 取第一行
    out = out.strip().strip('"').strip("'")
    return out.split("\n")[0][:60]


def gen_outline(topic: str, n: int, model: str) -> list[tuple[str, str]]:
    """返回 [(title, one_liner), ...]. 兼容多种输出格式."""
    out = llm_chat(prompt_outline(topic, n), model=model, max_tokens=1500)
    if os.environ.get("KG_DEBUG_OUTLINE"):
        print(f"[debug] outline raw output:\n{out}\n---")
    chapters = []
    for line in out.split("\n"):
        line = line.strip()
        if not line:
            continue
        # 去 markdown 标题前缀 (# ## ###)
        line = re.sub(r"^#+\s*", "", line)
        # 去列表符号 (- * +)
        line = re.sub(r"^[-*+]\s*", "", line)
        # 1) "01. 标题 — 一句话" (主格式)
        m = re.match(r"^\d+\.\s*([^—\-]+?)\s*[—\-]\s*(.+)$", line)
        if m:
            chapters.append((m.group(1).strip(), m.group(2).strip()))
            continue
        # 2) "01. 标题" (退化)
        m2 = re.match(r"^\d+\.\s*(.+)$", line)
        if m2:
            chapters.append((m2.group(1).strip(), ""))
            continue
        # 3) "01、 标题 — 一句话" (中文顿号)
        m3 = re.match(r"^\d+[、.]\s*([^—\-]+?)\s*[—\-]\s*(.+)$", line)
        if m3:
            chapters.append((m3.group(1).strip(), m3.group(2).strip()))
            continue
    if len(chapters) < n:
        print(f"⚠ outline 只生成 {len(chapters)}/{n} 章, 补齐...")
        while len(chapters) < n:
            chapters.append((f"补充章节 {len(chapters)+1}", ""))
    return chapters[:n]


def gen_chapter(topic: str, idx: int, total: int, title: str, one_liner: str,
                next_path: Optional[str], model: str) -> str:
    system = style_rules_block()
    prompt = prompt_chapter(topic, idx, total, title, one_liner, next_path)
    # 章节要 3000-5000 字, max_tokens 给足, 留 buffer 给 thinking (M2.7 模型)
    is_thinking_model = "M2.7" in model or "MiniMax" in model
    max_tokens = 8000 if is_thinking_model else 6000
    return llm_chat(prompt, system=system, model=model, max_tokens=max_tokens)


def write_chapter_files(book_dir: Path, idx: int, title: str, content: str,
                        next_path: Optional[str], dry_run: bool) -> tuple[Path, list[str]]:
    chap_slug = slugify_chapter(title)
    chap_dir = book_dir / f"{idx:02d}-{chap_slug}"
    readme = chap_dir / "README.md"
    code_readme = chap_dir / "code" / "README.md"
    code_req = chap_dir / "code" / "requirements.txt"

    issues = check_ai_flavor(content)

    if not dry_run:
        chap_dir.mkdir(parents=True, exist_ok=True)
        (chap_dir / "code").mkdir(exist_ok=True)
        # 末行确保是 next link
        if next_path and "[下一章]" not in content:
            content = content.rstrip() + f"\n\n[下一章]({next_path})\n"
        readme.write_text(content, encoding="utf-8")
        # code/ stub
        code_readme.write_text(
            f"# {title} — 代码说明\n\n这一章的代码示例在 `code/` 目录. 详见各 .py 文件顶部注释.\n",
            encoding="utf-8"
        )
        code_req.write_text("# 这一章的 Python 依赖\n# pip install -r requirements.txt\n", encoding="utf-8")
    return chap_dir, issues


def write_meta(book_dir: Path, slug: str, title: str, description: str,
               icon: str, color: str, priority: int, level: int,
               level_name: str, chapter_slugs: list[str], dry_run: bool):
    if dry_run:
        return
    meta = {
        "title": title,
        "description": description,
        "icon": icon,
        "color": color,
        "priority": priority,
        "level": level,
        "level_name": level_name,
        "order": chapter_slugs,
    }
    book_dir.mkdir(parents=True, exist_ok=True)
    (book_dir / "_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def main():
    p = argparse.ArgumentParser(
        description="知识花园 — 系列文章自动化生成器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--topic", required=True, help="系列主题, 例: 'Prompt Caching 实战'")
    p.add_argument("--slug", help="目录名 slug, 留空从 topic 自动生成")
    p.add_argument("--title", help="书标题, 留空用 topic")
    p.add_argument("--description", help="1 句话描述, 留空用 LLM 生成")
    p.add_argument("--icon", help=f"icon 名, 留空按 topic 选. 可选: {', '.join(ICON_POOL)}")
    p.add_argument("--color", help="hex 色值, 留空按 topic 选")
    p.add_argument("--priority", type=int, default=1, help="排序优先级, 数字越小越靠前 (默认 1)")
    p.add_argument("--level", type=int, default=3, help="1=入门 / 2=中级 / 3=进阶 / 4=专家 (默认 3)")
    p.add_argument("--level-name", default="进阶", help="level 对应的中文标签")
    p.add_argument("--chapters", type=int, default=10, help="章节数 (默认 10)")
    p.add_argument("--model", default="abab6.5s-chat", help="mmx 模型 (默认 abab6.5s-chat — 不输出 thinking, token 友好; M2.7 系列会浪费 token 在 thinking 上)")
    p.add_argument("--dry-run", action="store_true", help="只生成 meta + outline, 不写文件")
    p.add_argument("--skip-content", action="store_true", help="跳过章节正文生成 (只要 outline)")
    p.add_argument("--auto-build", action="store_true", help="生成完跑 build_reader.py")
    p.add_argument("--skip-verify", action="store_true", help="跳过 AI-味 验证")
    p.add_argument("--yes", "-y", action="store_true", help="跳过确认, 覆盖已存在目录")
    args = p.parse_args()

    # 1. Slug
    slug = args.slug or topic_to_slug(args.topic)
    if already_exists(slug) and not args.yes and not args.dry_run:
        print(f"❌ books/{slug}/ 已存在. 用 --slug <other> 改名, 或 --yes 覆盖 (会清空).")
        sys.exit(1)
    book_dir = BOOKS_DIR / slug
    title = args.title or args.topic
    print(f"📚 主题: {args.topic}")
    print(f"   slug: {slug}")
    print(f"   chapters: {args.chapters}")
    print(f"   model: {args.model}")
    print(f"   dry-run: {args.dry_run}")
    print()

    # 2. Icon + color
    if args.icon:
        icon = args.icon
    if args.color:
        color = args.color
    if not args.icon or not args.color:
        auto_color, auto_icon = pick_color_icon(args.topic)
        color = args.color or auto_color
        icon = args.icon or auto_icon
    print(f"   icon: {icon}, color: {color}")

    # 3. Description
    if args.description:
        description = args.description
    else:
        print("\n🤖 生成 description ...")
        description = gen_description(args.topic, args.model)
        print(f"   → {description}")

    # 4. Outline
    print(f"\n🤖 生成 {args.chapters} 章 outline ...")
    outline = gen_outline(args.topic, args.chapters, args.model)
    for i, (t, ol) in enumerate(outline, 1):
        print(f"   {i:02d}. {t}  —  {ol}")
    if args.skip_content:
        print("\n⏭ --skip-content, 不生成章节正文")
        return

    # 5. Chapters
    print(f"\n🤖 生成 {args.chapters} 章内容 (这会比较慢, 每章 ~30-60s) ...")
    chapter_slugs = []
    all_issues = []
    for i, (chap_title, one_liner) in enumerate(outline, 1):
        next_idx = i + 1
        next_path = None
        if next_idx <= len(outline):
            next_chap_slug = slugify_chapter(outline[next_idx - 1][0])
            next_path = f"./{next_idx:02d}-{next_chap_slug}.md"
        print(f"   [{i:02d}/{args.chapters}] {chap_title} ...", end=" ", flush=True)
        try:
            content = gen_chapter(args.topic, i, args.chapters, chap_title, one_liner,
                                  next_path, args.model)
        except RuntimeError as e:
            print(f"❌ {e}")
            if not args.dry_run:
                sys.exit(1)
            continue
        chap_dir, issues = write_chapter_files(
            book_dir, i, chap_title, content, next_path, args.dry_run
        )
        chap_slug = f"{i:02d}-{slugify_chapter(chap_title)}"
        chapter_slugs.append(chap_slug)
        if issues and not args.skip_verify:
            all_issues.append((chap_slug, issues))
            print(f"⚠ {len(issues)} issues")
            for it in issues:
                print(f"     - {it}")
        else:
            print("✓")
    print(f"\n   章节 slug 顺序: {chapter_slugs}")

    # 6. _meta.json
    print("\n📝 写 _meta.json ...")
    write_meta(book_dir, slug, title, description, icon, color,
               args.priority, args.level, args.level_name, chapter_slugs, args.dry_run)

    # 7. 总结
    print("\n" + "=" * 60)
    if args.dry_run:
        print(f"✅ Dry-run 完成 (未写文件). 真实跑去掉 --dry-run.")
    else:
        print(f"✅ 生成完成 → books/{slug}/")
    if all_issues:
        print(f"\n⚠ {len(all_issues)} 章有 AI-味 警告:")
        for slug_, iss in all_issues:
            print(f"   {slug_}:")
            for i in iss:
                print(f"     - {i}")
        print("\n建议: 手动编辑, 或重跑 python tools/generate_series.py ...")

    # 8. Auto-build
    if args.auto_build and not args.dry_run:
        print(f"\n🏗 跑 build_reader.py ...")
        env = os.environ.copy()
        env.setdefault("SKIP_DENSE", "1")
        r = subprocess.run([sys.executable, str(ROOT / "build_reader.py")],
                           env=env, cwd=str(ROOT))
        if r.returncode != 0:
            print(f"❌ build_reader.py 失败 exit={r.returncode}")
            sys.exit(1)
        print("✓ build done")


if __name__ == "__main__":
    main()
