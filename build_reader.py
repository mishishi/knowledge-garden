"""
build_reader.py - v4 多书版阅读器

支持多本书（系列），自动扫描 books/ 目录。

目录结构：
    books/
        multi-agent/
            _meta.json
            01-chapter/
                README.md
            ...
        crewai-life/
            _meta.json
            ...

加新系列：
    1. books/<slug>/  子目录
    2. _meta.json (title, description, order)
    3. <slug>-XX/<chapter-name>/README.md
    4. python build_reader.py

用法：
    pip install markdown pygments
    python build_reader.py
"""
import base64
import json
import re
from pathlib import Path

import markdown


ROOT = Path(__file__).parent
BOOKS_DIR = ROOT / "books"


# ============================================================
# 书发现
# ============================================================
def discover_books():
    """扫描 books/ 目录，返回 [(book_slug, meta, chapters)]"""
    books = []

    if not BOOKS_DIR.exists():
        return books

    for book_dir in sorted(BOOKS_DIR.iterdir()):
        if not book_dir.is_dir() or book_dir.name.startswith("_"):
            continue

        # 读 meta
        meta_path = book_dir / "_meta.json"
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
            except Exception:
                meta = {}
        else:
            meta = {}

        meta.setdefault("title", book_dir.name)
        meta.setdefault("description", "")
        meta.setdefault("order", None)
        meta.setdefault("color", "#b08968")
        meta.setdefault("priority", 999)  # 书的排序（数字越小越靠前）

        # 找章节
        chapters = []

        if meta["order"]:
            for slug in meta["order"]:
                chap_dir = book_dir / slug
                readme = chap_dir / "README.md" if (chap_dir / "README.md").exists() else chap_dir
                if readme.exists():
                    chapters.append((slug, readme))
        else:
            for p in sorted(book_dir.iterdir()):
                if not p.is_dir() and not p.name.startswith("_"):
                    continue
                if p.is_dir():
                    readme = p / "README.md"
                    if readme.exists():
                        chapters.append((p.name, readme))
                elif p.suffix == ".md":
                    chapters.append((p.stem, p))

        if chapters:
            books.append((book_dir.name, meta, chapters))

    # 按 priority 排序
    books.sort(key=lambda b: b[1].get("priority", 999))

    return books


def md_to_html(md_text: str) -> str:
    return markdown.markdown(
        md_text,
        extensions=["fenced_code", "tables", "nl2br", "sane_lists"],
    )


def count_words(md_text: str) -> int:
    text = re.sub(r"```.*?```", "", md_text, flags=re.DOTALL)
    text = re.sub(r"[#*\[\]()>`]", "", text)
    chinese = len(re.findall(r"[\u4e00-\u9fff]", text))
    english = len(re.findall(r"\b[a-zA-Z]+\b", text))
    return chinese + english


# ============================================================
# PWA 图标
# ============================================================
PWA_ICON_SVG = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 192 192">
  <rect width="192" height="192" fill="#faf9f5" rx="32"/>
  <text x="96" y="115" font-family="Georgia, serif" font-size="76" font-weight="600" text-anchor="middle" fill="#b08968">K</text>
  <text x="96" y="158" font-family="Georgia, serif" font-size="16" letter-spacing="3" text-anchor="middle" fill="#8b6f47">KNOWLEDGE</text>
</svg>
""".strip()
PWA_ICON_DATA_URI = f"data:image/svg+xml;base64,{base64.b64encode(PWA_ICON_SVG.encode()).decode()}"


# ============================================================
# CSS（与 v3 几乎相同）
# ============================================================
CSS = """
:root {
    --bg: #faf9f5;
    --bg-soft: #f4f1e8;
    --text: #2a2a2a;
    --text-soft: #5a5a5a;
    --text-faint: #8a8a8a;
    --accent: #b08968;
    --accent-soft: rgba(176, 137, 104, 0.15);
    --border: #e5e1d4;
    --code-bg: #f0ede4;
    --link: #8b6f47;
    --hl-yellow: rgba(255, 235, 100, 0.4);
    --hl-green: rgba(150, 230, 150, 0.4);
    --hl-blue: rgba(150, 200, 255, 0.4);
    --hl-pink: rgba(255, 180, 220, 0.4);
    --font-base: 18px;
}

* { box-sizing: border-box; }

body {
    margin: 0;
    background: var(--bg);
    color: var(--text);
    font-family: "Source Han Serif SC", "Source Han Serif CN", "Noto Serif CJK SC",
                 "Songti SC", "STSong", Charter, Georgia, "Times New Roman", serif;
    font-size: var(--font-base);
    line-height: 1.85;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
    transition: background 0.3s, color 0.3s;
}

body.dark {
    --bg: #1c1c1e;
    --bg-soft: #2a2a2c;
    --text: #d4d4d4;
    --text-soft: #a0a0a0;
    --text-faint: #707070;
    --border: #3a3a3c;
    --code-bg: #2a2a2c;
    --link: #c4a87c;
    --hl-yellow: rgba(180, 150, 50, 0.4);
    --hl-green: rgba(80, 160, 80, 0.4);
    --hl-blue: rgba(80, 130, 180, 0.4);
    --hl-pink: rgba(180, 100, 140, 0.4);
}

.progress {
    position: fixed;
    top: 0; left: 0; right: 0;
    height: 2px;
    background: var(--accent);
    transform-origin: left;
    transform: scaleX(0);
    z-index: 200;
}

.toolbar {
    position: fixed;
    top: 16px;
    right: 16px;
    z-index: 100;
    display: flex;
    gap: 4px;
    background: rgba(255, 255, 255, 0.85);
    border: 1px solid var(--border);
    padding: 6px;
    border-radius: 10px;
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.04);
}

body.dark .toolbar { background: rgba(40, 40, 44, 0.85); }

.toolbar button {
    border: none;
    background: transparent;
    cursor: pointer;
    padding: 6px 10px;
    font-size: 13px;
    color: var(--text-soft);
    border-radius: 6px;
    transition: all 0.15s;
}

.toolbar button:hover { background: var(--accent-soft); color: var(--accent); }
.toolbar button.active { background: var(--accent); color: white; }

.toolbar .divider {
    width: 1px;
    background: var(--border);
    margin: 4px 2px;
}

.sidebar {
    position: fixed;
    top: 0; left: 0;
    width: 300px;
    height: 100vh;
    overflow-y: auto;
    padding: 60px 20px 40px 20px;
    background: var(--bg-soft);
    border-right: 1px solid var(--border);
    z-index: 50;
    transition: transform 0.3s ease;
}

body.sidebar-collapsed .sidebar { transform: translateX(-300px); }

.sidebar h1 {
    font-size: 18px;
    margin: 0 0 8px 0;
    color: var(--text);
    font-weight: 600;
    letter-spacing: 1px;
}

.sidebar .subtitle {
    font-size: 12px;
    color: var(--text-faint);
    margin-bottom: 32px;
    line-height: 1.6;
    font-style: italic;
}

/* 书架 */
.bookshelf .book-group { margin-bottom: 24px; }

.book-header {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 12px;
    cursor: pointer;
    border-radius: 6px;
    user-select: none;
    transition: background 0.15s;
}

.book-header:hover { background: var(--accent-soft); }

.book-icon {
    font-size: 18px;
    flex-shrink: 0;
}

.book-title-text {
    flex: 1;
    font-size: 13px;
    font-weight: 600;
    color: var(--text);
}

.book-chapters-count {
    font-size: 11px;
    color: var(--text-faint);
    font-family: Georgia, serif;
    font-style: italic;
}

.book-chapters {
    list-style: none;
    padding: 0;
    margin: 4px 0 8px 28px;
    border-left: 1px solid var(--border);
}

.book-chapters.collapsed { display: none; }

.book-chapters li a {
    display: block;
    padding: 6px 12px;
    color: var(--text-soft);
    text-decoration: none;
    font-size: 13px;
    border-radius: 4px;
    line-height: 1.5;
    transition: all 0.15s;
    border-left: 2px solid transparent;
    margin-left: -1px;
}

.book-chapters li a:hover {
    background: var(--accent-soft);
    color: var(--accent);
}

.book-chapters li a.active {
    background: var(--accent-soft);
    border-left-color: var(--accent);
    color: var(--accent);
    font-weight: 500;
}

.book-chapters .ch-num {
    font-family: Georgia, serif;
    font-size: 11px;
    color: var(--text-faint);
    font-style: italic;
    margin-right: 6px;
}

.sidebar .divider {
    height: 1px;
    background: var(--border);
    margin: 20px 0;
}

.sidebar-toggle {
    position: fixed;
    top: 16px;
    left: 16px;
    z-index: 100;
    background: rgba(255, 255, 255, 0.85);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 8px 12px;
    cursor: pointer;
    font-family: inherit;
    font-size: 13px;
    color: var(--text-soft);
    backdrop-filter: blur(12px);
    transition: left 0.3s ease;
}

body.dark .sidebar-toggle { background: rgba(40, 40, 44, 0.85); }

.content {
    max-width: 680px;
    margin: 0 auto;
    padding: 100px 60px 80px 60px;
}

.book-cover {
    text-align: center;
    padding: 100px 20px 60px 20px;
    margin-bottom: 80px;
    border-bottom: 1px solid var(--border);
}

.book-cover .book-icon-big {
    font-size: 64px;
    margin-bottom: 24px;
}

.book-cover h1 {
    font-size: 2.6em;
    font-weight: 600;
    margin: 0 0 16px 0;
    letter-spacing: 2px;
    color: var(--text);
}

.book-cover p {
    font-size: 16px;
    color: var(--text-soft);
    font-style: italic;
    margin: 0;
    text-indent: 0;
}

.book-cover .book-stats {
    margin-top: 32px;
    font-size: 13px;
    color: var(--text-faint);
    font-family: Georgia, serif;
}

.chapter {
    margin-bottom: 200px;
    padding-bottom: 100px;
    border-bottom: 1px solid var(--border);
    text-align: justify;
}

.chapter:last-of-type { border-bottom: none; }

.chapter-num {
    text-align: center;
    margin: 0 0 30px 0;
    font-family: Georgia, "Times New Roman", serif;
    font-size: 14px;
    color: var(--accent);
    letter-spacing: 8px;
    text-transform: uppercase;
    font-style: italic;
}

.chapter-title {
    text-align: center;
    font-size: 2.4em;
    font-weight: 600;
    margin: 0 0 16px 0;
    line-height: 1.3;
    letter-spacing: 2px;
    color: var(--text);
}

.chapter-meta {
    text-align: center;
    color: var(--text-faint);
    font-size: 13px;
    margin-bottom: 80px;
    font-style: italic;
    letter-spacing: 1px;
}

.chapter-meta::before, .chapter-meta::after {
    content: "·";
    margin: 0 12px;
    color: var(--accent);
}

.chapter-content { font-feature-settings: "kern", "liga", "calt"; }

.chapter-content p {
    margin: 0 0 1.2em 0;
    text-indent: 2em;
}

.chapter-content > p:first-of-type::first-letter {
    font-size: 3.6em;
    float: left;
    line-height: 0.9;
    margin: 0.08em 0.12em 0 0;
    font-weight: 600;
    color: var(--accent);
}

.chapter-content h1 { display: none; }

.chapter-content h2 {
    font-size: 1.6em;
    font-weight: 600;
    margin: 2.2em 0 1em 0;
    padding-bottom: 0.3em;
    border-bottom: 1px solid var(--border);
    text-align: left;
    color: var(--text);
}

.chapter-content h3 {
    font-size: 1.25em;
    font-weight: 600;
    margin: 2em 0 0.8em 0;
    color: var(--text);
}

.chapter-content h4 {
    font-size: 1.05em;
    font-weight: 600;
    margin: 1.6em 0 0.6em 0;
    color: var(--text);
}

.chapter-content strong {
    font-weight: 600;
    color: var(--text);
    background: linear-gradient(transparent 65%, var(--accent-soft) 65%);
    padding: 0 2px;
}

.chapter-content a {
    color: var(--link);
    text-decoration: none;
    border-bottom: 1px solid var(--accent-soft);
}

.chapter-content a:hover { border-bottom-color: var(--accent); }

.chapter-content blockquote {
    margin: 2em 0;
    padding: 16px 28px;
    color: var(--text-soft);
    border-left: 3px solid var(--accent);
    background: var(--accent-soft);
    font-style: italic;
    border-radius: 0 6px 6px 0;
}

.chapter-content blockquote p { text-indent: 0; margin: 0; }

.chapter-content ul, .chapter-content ol { margin: 1em 0; padding-left: 2em; }
.chapter-content li { margin: 0.6em 0; }
.chapter-content li > p { margin: 0.4em 0; }

.chapter-content code {
    font-family: "JetBrains Mono", "Fira Code", Consolas, "Courier New", monospace;
    background: var(--code-bg);
    color: var(--accent);
    padding: 2px 6px;
    border-radius: 3px;
    font-size: 0.88em;
    text-indent: 0;
}

.chapter-content pre {
    background: var(--code-bg);
    border: 1px solid var(--border);
    padding: 20px 24px;
    border-radius: 6px;
    overflow-x: auto;
    line-height: 1.65;
    font-size: 0.85em;
    margin: 1.5em 0;
    text-indent: 0;
}

.chapter-content pre code {
    background: transparent;
    color: var(--text);
    padding: 0;
    font-size: 100%;
}

.chapter-content table {
    border-collapse: collapse;
    margin: 1.5em 0;
    width: 100%;
    font-size: 0.92em;
    text-indent: 0;
}

.chapter-content th, .chapter-content td {
    padding: 10px 14px;
    border-bottom: 1px solid var(--border);
    text-align: left;
}

.chapter-content th {
    color: var(--text-soft);
    font-weight: 600;
    text-transform: uppercase;
    font-size: 0.85em;
    letter-spacing: 1px;
    border-bottom: 2px solid var(--accent);
}

.chapter-content tr:nth-child(even) td { background: var(--bg-soft); }

.chapter-content hr {
    border: none;
    border-top: 1px solid var(--border);
    margin: 3em auto;
    width: 60px;
    position: relative;
}

.chapter-content hr::after {
    content: "❀";
    position: absolute;
    top: -10px;
    left: 50%;
    transform: translateX(-50%);
    background: var(--bg);
    padding: 0 12px;
    color: var(--accent);
    font-size: 12px;
}

.chapter-end {
    text-align: center;
    margin-top: 80px;
    color: var(--text-faint);
    font-size: 13px;
    letter-spacing: 8px;
    font-style: italic;
}

.chapter-end::before { content: "— ❀ ❀ ❀ —"; color: var(--accent); }

@media (max-width: 900px) {
    .sidebar { transform: translateX(-300px); }
    body:not(.sidebar-collapsed) .sidebar { transform: translateX(0); }
    body:not(.sidebar-collapsed) .sidebar-toggle { left: 320px; }
    .content { padding: 80px 24px; max-width: 100%; }
    .chapter-title { font-size: 1.8em; }
    .chapter-num { font-size: 12px; letter-spacing: 5px; }
    .book-cover h1 { font-size: 1.8em; }
    .toolbar { top: 8px; right: 8px; }
    .sidebar-toggle { top: 8px; left: 8px; }
}

::-webkit-scrollbar { width: 8px; height: 8px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 4px; }
::-webkit-scrollbar-thumb:hover { background: var(--accent); }

::selection { background: var(--accent-soft); color: var(--text); }

.highlight-yellow { background: var(--hl-yellow); padding: 2px 0; border-radius: 2px; }
.highlight-green { background: var(--hl-green); padding: 2px 0; border-radius: 2px; }
.highlight-blue { background: var(--hl-blue); padding: 2px 0; border-radius: 2px; }
.highlight-pink { background: var(--hl-pink); padding: 2px 0; border-radius: 2px; }

.selection-toolbar {
    position: absolute;
    display: none;
    z-index: 150;
    background: rgba(40, 40, 44, 0.95);
    color: white;
    padding: 6px;
    border-radius: 8px;
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.15);
    font-family: -apple-system, sans-serif;
    backdrop-filter: blur(8px);
    user-select: none;
}

.selection-toolbar.visible { display: flex; gap: 4px; }

.selection-toolbar button {
    border: none;
    background: transparent;
    color: white;
    cursor: pointer;
    padding: 6px 8px;
    font-size: 14px;
    border-radius: 4px;
}

.selection-toolbar button:hover { background: rgba(255, 255, 255, 0.15); }

.selection-toolbar .color-swatch {
    width: 20px;
    height: 20px;
    border-radius: 50%;
    border: 2px solid transparent;
    cursor: pointer;
}

.selection-toolbar .color-swatch.yellow { background: #ffeb64; }
.selection-toolbar .color-swatch.green { background: #96e696; }
.selection-toolbar .color-swatch.blue { background: #96c8ff; }
.selection-toolbar .color-swatch.pink { background: #ffb4dc; }

.selection-toolbar .color-swatch.active { border-color: white; }

.note-modal {
    position: fixed;
    top: 0; left: 0; right: 0; bottom: 0;
    background: rgba(0, 0, 0, 0.5);
    z-index: 300;
    display: none;
    align-items: center;
    justify-content: center;
    backdrop-filter: blur(4px);
}

.note-modal.visible { display: flex; }

.note-modal-content {
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 24px;
    width: 90%;
    max-width: 480px;
    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.2);
}

.note-modal-content h3 {
    margin: 0 0 12px 0;
    color: var(--text);
    font-family: -apple-system, sans-serif;
    font-size: 16px;
}

.note-modal-content .quoted {
    color: var(--text-soft);
    font-size: 13px;
    padding: 12px;
    background: var(--bg-soft);
    border-radius: 6px;
    margin-bottom: 12px;
    border-left: 3px solid var(--accent);
    font-style: italic;
}

.note-modal-content textarea {
    width: 100%;
    min-height: 100px;
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 10px;
    background: var(--bg);
    color: var(--text);
    font-family: inherit;
    font-size: 14px;
    resize: vertical;
    box-sizing: border-box;
}

.note-modal-content .actions {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
    margin-top: 12px;
}

.note-modal-content .actions button {
    padding: 8px 16px;
    border: none;
    border-radius: 6px;
    cursor: pointer;
    font-size: 13px;
    font-family: inherit;
}

.note-modal-content .actions .cancel { background: var(--bg-soft); color: var(--text); }
.note-modal-content .actions .save { background: var(--accent); color: white; }

.notes-panel {
    position: fixed;
    top: 0;
    right: 0;
    width: 320px;
    height: 100vh;
    background: var(--bg-soft);
    border-left: 1px solid var(--border);
    z-index: 80;
    transform: translateX(320px);
    transition: transform 0.3s ease;
    display: flex;
    flex-direction: column;
}

.notes-panel.visible { transform: translateX(0); }

.notes-panel-header {
    padding: 24px 20px 16px;
    border-bottom: 1px solid var(--border);
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.notes-panel-header h2 {
    margin: 0;
    font-size: 16px;
    color: var(--text);
    font-weight: 600;
}

.notes-panel-header button {
    border: none;
    background: transparent;
    cursor: pointer;
    font-size: 18px;
    color: var(--text-soft);
}

.notes-list {
    flex: 1;
    overflow-y: auto;
    padding: 16px 20px;
}

.note-item {
    padding: 12px;
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 8px;
    margin-bottom: 12px;
    cursor: pointer;
}

.note-item:hover { border-color: var(--accent); }

.note-item .note-book-tag {
    font-size: 10px;
    color: var(--accent);
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-bottom: 4px;
}

.note-item .note-quote {
    font-size: 13px;
    color: var(--text-soft);
    font-style: italic;
    margin-bottom: 6px;
    border-left: 3px solid var(--accent);
    padding-left: 8px;
}

.note-item .note-text {
    font-size: 14px;
    color: var(--text);
    margin-bottom: 6px;
}

.note-item .note-meta {
    font-size: 11px;
    color: var(--text-faint);
}

.note-item .note-delete {
    float: right;
    border: none;
    background: transparent;
    cursor: pointer;
    color: var(--text-faint);
    font-size: 12px;
}

.notes-empty {
    text-align: center;
    color: var(--text-faint);
    padding: 40px 20px;
    font-style: italic;
    font-size: 13px;
}

.music-panel {
    position: fixed;
    bottom: 24px;
    left: 24px;
    background: rgba(255, 255, 255, 0.95);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 16px;
    z-index: 100;
    width: 260px;
    backdrop-filter: blur(12px);
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
    display: none;
    font-family: -apple-system, sans-serif;
}

body.dark .music-panel { background: rgba(40, 40, 44, 0.95); }

.music-panel.visible { display: block; }

.music-panel h4 {
    margin: 0 0 12px 0;
    font-size: 13px;
    color: var(--text);
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.music-panel .close {
    border: none;
    background: transparent;
    cursor: pointer;
    color: var(--text-faint);
    font-size: 16px;
}

.music-panel .scenes {
    display: grid;
    grid-template-columns: 1fr 1fr 1fr;
    gap: 6px;
    margin-bottom: 12px;
}

.music-panel .scene-btn {
    padding: 8px;
    border: 1px solid var(--border);
    background: transparent;
    border-radius: 6px;
    cursor: pointer;
    font-size: 11px;
    color: var(--text-soft);
}

.music-panel .scene-btn:hover {
    border-color: var(--accent);
    color: var(--accent);
}

.music-panel .scene-btn.active {
    background: var(--accent);
    color: white;
    border-color: var(--accent);
}

.music-panel .volume {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 12px;
    color: var(--text-soft);
}

.music-panel .volume input {
    flex: 1;
    accent-color: var(--accent);
}

.pwa-prompt {
    position: fixed;
    bottom: 24px;
    left: 50%;
    transform: translateX(-50%);
    background: rgba(40, 40, 44, 0.95);
    color: white;
    padding: 12px 20px;
    border-radius: 24px;
    font-family: -apple-system, sans-serif;
    font-size: 13px;
    z-index: 200;
    display: none;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.2);
    backdrop-filter: blur(8px);
}

.pwa-prompt.visible { display: block; }

.pwa-prompt .close {
    border: none;
    background: transparent;
    color: white;
    cursor: pointer;
    margin-left: 12px;
    font-size: 16px;
    opacity: 0.7;
}

.pwa-prompt .close:hover { opacity: 1; }

/* === 进度统计 === */
.completion-toggle {
    display: block;
    margin: 60px auto 0;
    padding: 12px 32px;
    border: 1px solid var(--border);
    background: var(--bg);
    color: var(--text-soft);
    border-radius: 24px;
    cursor: pointer;
    font-family: inherit;
    font-size: 14px;
    transition: all 0.15s;
}

.completion-toggle:hover {
    background: var(--accent-soft);
    border-color: var(--accent);
    color: var(--accent);
}

.completion-toggle.completed {
    background: var(--accent);
    color: white;
    border-color: var(--accent);
}

.chapter.completed .chapter-title::before {
    content: "✓ ";
    color: var(--accent);
}

.book-chapters li a.completed {
    color: var(--accent);
}

.book-chapters li a.completed::after {
    content: " ✓";
    color: var(--accent);
    margin-left: 4px;
}

/* === 进度面板 === */
.progress-panel {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.5);
    z-index: 300;
    display: none;
    align-items: center;
    justify-content: center;
    backdrop-filter: blur(4px);
}

.progress-panel.visible { display: flex; }

.progress-modal {
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 32px;
    width: 90%;
    max-width: 720px;
    max-height: 85vh;
    overflow-y: auto;
    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.2);
}

.progress-modal-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 24px;
    padding-bottom: 16px;
    border-bottom: 1px solid var(--border);
}

.progress-modal-header h2 {
    margin: 0;
    font-size: 20px;
    color: var(--text);
}

.progress-modal-header .close {
    border: none;
    background: transparent;
    cursor: pointer;
    font-size: 22px;
    color: var(--text-faint);
}

.overall-progress { margin-bottom: 32px; }

.overall-progress .big-number {
    font-size: 56px;
    font-weight: 300;
    color: var(--accent);
    font-family: Georgia, serif;
    line-height: 1;
}

.overall-progress .label {
    color: var(--text-soft);
    font-size: 14px;
    margin-top: 8px;
}

.overall-progress .progress-bar {
    height: 8px;
    background: var(--bg-soft);
    border-radius: 4px;
    margin-top: 16px;
    overflow: hidden;
}

.overall-progress .progress-bar-fill {
    height: 100%;
    background: var(--accent);
    transition: width 0.5s ease;
    border-radius: 4px;
}

.book-progress { margin-bottom: 20px; }

.book-progress-header {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    margin-bottom: 8px;
}

.book-progress-name {
    font-weight: 600;
    color: var(--text);
    font-size: 14px;
}

.book-progress-stats {
    color: var(--text-soft);
    font-size: 12px;
    font-family: Georgia, serif;
}

.book-progress-bar {
    height: 6px;
    background: var(--bg-soft);
    border-radius: 3px;
    overflow: hidden;
}

.book-progress-bar-fill {
    height: 100%;
    background: var(--accent);
    border-radius: 3px;
    transition: width 0.5s ease;
}

/* 阅读日历 */
.calendar { margin-top: 32px; }

.calendar-title {
    color: var(--text-soft);
    font-size: 13px;
    margin-bottom: 12px;
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.calendar-grid {
    display: flex;
    gap: 2px;
    overflow-x: auto;
    padding: 4px 0;
}

.calendar-week {
    display: flex;
    flex-direction: column;
    gap: 2px;
}

.calendar-day {
    width: 11px;
    height: 11px;
    border-radius: 2px;
    background: var(--bg-soft);
    cursor: pointer;
    transition: transform 0.1s;
}

.calendar-day:hover {
    transform: scale(1.4);
    outline: 1px solid var(--accent);
}

.calendar-day.empty {
    background: transparent;
    cursor: default;
    pointer-events: none;
}

.calendar-day.level-1 { background: rgba(176, 137, 104, 0.25); }
.calendar-day.level-2 { background: rgba(176, 137, 104, 0.5); }
.calendar-day.level-3 { background: rgba(176, 137, 104, 0.75); }
.calendar-day.level-4 { background: var(--accent); }

body.dark .calendar-day { background: rgba(255, 255, 255, 0.06); }
body.dark .calendar-day.level-1 { background: rgba(196, 168, 124, 0.3); }
body.dark .calendar-day.level-2 { background: rgba(196, 168, 124, 0.55); }
body.dark .calendar-day.level-3 { background: rgba(196, 168, 124, 0.8); }

.calendar-legend {
    display: flex;
    align-items: center;
    gap: 4px;
    font-size: 11px;
    color: var(--text-faint);
}

.calendar-legend .calendar-day {
    width: 10px;
    height: 10px;
    cursor: default;
}

.calendar-legend .calendar-day:hover {
    transform: none;
    outline: none;
}

.progress-actions {
    margin-top: 32px;
    padding-top: 16px;
    border-top: 1px solid var(--border);
    display: flex;
    gap: 8px;
}

.progress-actions button {
    padding: 8px 16px;
    border: 1px solid var(--border);
    background: transparent;
    border-radius: 6px;
    cursor: pointer;
    font-family: inherit;
    font-size: 13px;
    color: var(--text-soft);
}

.progress-actions button:hover {
    background: var(--accent-soft);
    color: var(--accent);
}

/* === 命令面板（搜索） === */
.command-palette {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.5);
    z-index: 400;
    display: none;
    align-items: flex-start;
    justify-content: center;
    padding-top: 80px;
    backdrop-filter: blur(4px);
}

.command-palette.visible { display: flex; }

.command-modal {
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 12px;
    width: 90%;
    max-width: 600px;
    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.25);
    overflow: hidden;
    max-height: 70vh;
    display: flex;
    flex-direction: column;
}

.command-input {
    width: 100%;
    padding: 18px 20px;
    border: none;
    background: var(--bg);
    color: var(--text);
    font-size: 16px;
    font-family: inherit;
    border-bottom: 1px solid var(--border);
    box-sizing: border-box;
}

.command-input:focus { outline: none; }
.command-input::placeholder { color: var(--text-faint); }

.command-hint {
    padding: 8px 20px;
    font-size: 11px;
    color: var(--text-faint);
    background: var(--bg-soft);
    border-bottom: 1px solid var(--border);
    display: flex;
    justify-content: space-between;
}

.command-results {
    overflow-y: auto;
    flex: 1;
}

.command-item {
    padding: 14px 20px;
    cursor: pointer;
    border-bottom: 1px solid var(--border);
    transition: background 0.1s;
}

.command-item:hover, .command-item.active {
    background: var(--accent-soft);
}

.command-item:last-child { border-bottom: none; }

.command-book-tag {
    display: inline-block;
    font-size: 10px;
    color: var(--accent);
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-bottom: 4px;
}

.command-title {
    font-weight: 600;
    color: var(--text);
    font-size: 14px;
}

.command-snippet {
    display: block;
    color: var(--text-faint);
    font-size: 12px;
    margin-top: 4px;
    line-height: 1.5;
    overflow: hidden;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
}

.command-snippet mark {
    background: var(--accent-soft);
    color: var(--accent);
    padding: 0 2px;
    border-radius: 2px;
}

.command-empty {
    padding: 40px 20px;
    text-align: center;
    color: var(--text-faint);
    font-style: italic;
    font-size: 13px;
}
"""


JS = """
const FONT_SIZES = { small: 16, medium: 18, large: 20 };
let currentFontSize = localStorage.getItem('fontSize') || 'medium';

function setFontSize(size) {
    document.documentElement.style.setProperty('--font-base', FONT_SIZES[size] + 'px');
    document.querySelectorAll('.font-btn').forEach(b => b.classList.toggle('active', b.dataset.size === size));
    localStorage.setItem('fontSize', size);
}

document.querySelectorAll('.font-btn').forEach(btn => {
    btn.addEventListener('click', () => setFontSize(btn.dataset.size));
});

setFontSize(currentFontSize);

function toggleDark() {
    document.body.classList.toggle('dark');
    const isDark = document.body.classList.contains('dark');
    localStorage.setItem('dark', isDark);
    document.getElementById('dark-btn').classList.toggle('active', isDark);
}

document.getElementById('dark-btn').addEventListener('click', toggleDark);

if (localStorage.getItem('dark') === 'true') {
    document.body.classList.add('dark');
    document.getElementById('dark-btn').classList.add('active');
}

document.getElementById('sidebar-toggle').addEventListener('click', () => {
    document.body.classList.toggle('sidebar-collapsed');
    localStorage.setItem('sidebarCollapsed', document.body.classList.contains('sidebar-collapsed'));
});

if (localStorage.getItem('sidebarCollapsed') === 'true') {
    document.body.classList.add('sidebar-collapsed');
}

// 书架折叠
document.querySelectorAll('.book-header').forEach(header => {
    header.addEventListener('click', () => {
        const chapters = header.nextElementSibling;
        chapters.classList.toggle('collapsed');
    });
});

// 默认折叠非首本书
document.querySelectorAll('.book-group').forEach((group, idx) => {
    if (idx > 0) {
        group.querySelector('.book-chapters').classList.add('collapsed');
    }
});

// 进度条
let lastChapter = null;
const chapters = document.querySelectorAll('.chapter');
const links = document.querySelectorAll('.book-chapters a');

function playPageFlip() {
    if (!window.audioCtx) return;
    const ctx = window.audioCtx;
    const now = ctx.currentTime;
    const bufferSize = ctx.sampleRate * 0.15;
    const buffer = ctx.createBuffer(1, bufferSize, ctx.sampleRate);
    const data = buffer.getChannelData(0);
    for (let i = 0; i < bufferSize; i++) {
        data[i] = (Math.random() * 2 - 1) * Math.exp(-i / (bufferSize * 0.3));
    }
    const noise = ctx.createBufferSource();
    noise.buffer = buffer;
    const filter = ctx.createBiquadFilter();
    filter.type = 'lowpass';
    filter.frequency.value = 1200;
    const gain = ctx.createGain();
    gain.gain.value = 0.15;
    gain.gain.exponentialRampToValueAtTime(0.001, now + 0.15);
    noise.connect(filter).connect(gain).connect(ctx.destination);
    noise.start(now);
    noise.stop(now + 0.15);
}

window.addEventListener('scroll', () => {
    const docHeight = document.documentElement.scrollHeight - window.innerHeight;
    const progress = docHeight > 0 ? window.scrollY / docHeight : 0;
    document.querySelector('.progress').style.transform = 'scaleX(' + progress + ')';
});

const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            const id = entry.target.id;
            if (lastChapter !== null && lastChapter !== id) {
                playPageFlip();
            }
            lastChapter = id;
            links.forEach(l => l.classList.remove('active'));
            const activeLink = document.querySelector('.book-chapters a[href="#' + id + '"]');
            if (activeLink) {
                activeLink.classList.add('active');
                // 自动展开当前章节所在的书的目录
                const bookGroup = activeLink.closest('.book-group');
                bookGroup.querySelector('.book-chapters').classList.remove('collapsed');
            }
        }
    });
}, { rootMargin: '-30% 0px -50% 0px', threshold: 0 });

chapters.forEach(ch => observer.observe(ch));

// 背景音乐（与 v3 相同）
let audioCtx = null;
let musicNodes = null;
let currentScene = 'off';
let volume = parseFloat(localStorage.getItem('volume') || 0.3);

function initAudio() {
    if (audioCtx) return;
    audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    window.audioCtx = audioCtx;
}

function startMusic(scene) {
    initAudio();
    if (musicNodes) stopMusic();
    currentScene = scene;
    const ctx = audioCtx;
    const mainGain = ctx.createGain();
    mainGain.gain.value = volume;
    mainGain.connect(ctx.destination);

    if (scene === 'white') {
        const bufferSize = ctx.sampleRate * 2;
        const buffer = ctx.createBuffer(1, bufferSize, ctx.sampleRate);
        const data = buffer.getChannelData(0);
        for (let i = 0; i < bufferSize; i++) data[i] = Math.random() * 2 - 1;
        const noise = ctx.createBufferSource();
        noise.buffer = buffer;
        noise.loop = true;
        const filter = ctx.createBiquadFilter();
        filter.type = 'lowpass';
        filter.frequency.value = 800;
        noise.connect(filter).connect(mainGain);
        noise.start();
        musicNodes = { source: noise, gain: mainGain };
    } else if (scene === 'rain') {
        const bufferSize = ctx.sampleRate * 2;
        const buffer = ctx.createBuffer(1, bufferSize, ctx.sampleRate);
        const data = buffer.getChannelData(0);
        for (let i = 0; i < bufferSize; i++) {
            if (Math.random() < 0.002) data[i] = (Math.random() * 2 - 1) * 0.5;
            else data[i] = (Math.random() * 2 - 1) * 0.05;
        }
        const noise = ctx.createBufferSource();
        noise.buffer = buffer;
        noise.loop = true;
        const filter = ctx.createBiquadFilter();
        filter.type = 'bandpass';
        filter.frequency.value = 1500;
        filter.Q.value = 0.5;
        noise.connect(filter).connect(mainGain);
        noise.start();
        musicNodes = { source: noise, gain: mainGain };
    } else if (scene === 'warm') {
        const osc1 = ctx.createOscillator();
        osc1.type = 'sine';
        osc1.frequency.value = 110;
        const osc2 = ctx.createOscillator();
        osc2.type = 'sine';
        osc2.frequency.value = 165;
        const lfo = ctx.createOscillator();
        lfo.frequency.value = 0.15;
        const lfoGain = ctx.createGain();
        lfoGain.gain.value = 8;
        lfo.connect(lfoGain);
        lfoGain.connect(osc1.frequency);
        const mixGain = ctx.createGain();
        mixGain.gain.value = 0.6;
        osc1.connect(mixGain);
        osc2.connect(mixGain);
        mixGain.connect(mainGain);
        osc1.start();
        osc2.start();
        lfo.start();
        musicNodes = { source: osc1, gain: mainGain, lfo };
    }
    localStorage.setItem('musicScene', scene);
}

function stopMusic() {
    if (!musicNodes) return;
    try {
        if (musicNodes.source.stop) musicNodes.source.stop();
        if (musicNodes.lfo) musicNodes.lfo.stop();
    } catch (e) {}
    musicNodes = null;
    currentScene = 'off';
    localStorage.setItem('musicScene', 'off');
}

document.querySelectorAll('.scene-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        const scene = btn.dataset.scene;
        if (scene === 'off') stopMusic();
        else startMusic(scene);
        document.querySelectorAll('.scene-btn').forEach(b => b.classList.toggle('active', b === btn));
    });
});

document.querySelector('.volume input').addEventListener('input', (e) => {
    volume = e.target.value / 100;
    if (musicNodes) musicNodes.gain.gain.value = volume;
    localStorage.setItem('volume', volume);
});

document.querySelector('.volume input').value = volume * 100;
const savedScene = localStorage.getItem('musicScene') || 'off';
if (savedScene !== 'off') {
    startMusic(savedScene);
    document.querySelectorAll('.scene-btn').forEach(b => b.classList.toggle('active', b.dataset.scene === savedScene));
} else {
    document.querySelector('.scene-btn[data-scene="off"]').classList.add('active');
}

document.getElementById('music-btn').addEventListener('click', () => {
    document.querySelector('.music-panel').classList.toggle('visible');
});

document.querySelector('.music-panel .close').addEventListener('click', () => {
    document.querySelector('.music-panel').classList.remove('visible');
});

// 笔记（按书分组）
let notes = JSON.parse(localStorage.getItem('notes') || '[]');

function saveNotes() { localStorage.setItem('notes', JSON.stringify(notes)); }

function getSelectionInfo() {
    const sel = window.getSelection();
    if (!sel || sel.isCollapsed) return null;
    const range = sel.getRangeAt(0);
    const text = sel.toString().trim();
    if (!text || text.length < 2) return null;

    let chapterId = null;
    let bookSlug = null;
    let node = range.commonAncestorContainer;
    while (node && node !== document.body) {
        if (node.classList && node.classList.contains('chapter')) {
            chapterId = node.id;
            bookSlug = node.dataset.book;
            break;
        }
        node = node.parentNode;
    }
    if (!chapterId) return null;

    return { text, chapterId, bookSlug, range };
}

function showSelectionToolbar(rect) {
    const toolbar = document.querySelector('.selection-toolbar');
    toolbar.style.top = (rect.top - 50 + window.scrollY) + 'px';
    toolbar.style.left = (rect.left + rect.width / 2 - 100) + 'px';
    toolbar.classList.add('visible');
}

function hideSelectionToolbar() {
    document.querySelector('.selection-toolbar').classList.remove('visible');
}

function wrapRangeWithHighlight(range, className) {
    const span = document.createElement('span');
    span.className = className;
    try {
        range.surroundContents(span);
        return span;
    } catch (e) { return null; }
}

document.addEventListener('mouseup', () => {
    setTimeout(() => {
        const info = getSelectionInfo();
        if (info) showSelectionToolbar(info.range.getBoundingClientRect());
        else hideSelectionToolbar();
    }, 10);
});

document.querySelectorAll('.selection-toolbar .color-swatch').forEach(swatch => {
    swatch.addEventListener('click', () => {
        const color = 'highlight-' + swatch.dataset.color;
        document.querySelectorAll('.selection-toolbar .color-swatch').forEach(s => s.classList.toggle('active', s === swatch));
        const info = getSelectionInfo();
        if (info) {
            const span = wrapRangeWithHighlight(info.range, color);
            if (span) {
                notes.push({
                    type: 'highlight',
                    color,
                    chapterId: info.chapterId,
                    bookSlug: info.bookSlug,
                    text: info.text,
                    timestamp: Date.now(),
                });
                saveNotes();
            }
        }
        hideSelectionToolbar();
        window.getSelection().removeAllRanges();
        renderNotesList();
    });
});

document.querySelector('.selection-toolbar .note-btn').addEventListener('click', () => {
    const info = getSelectionInfo();
    if (!info) return;
    const modal = document.querySelector('.note-modal');
    modal.querySelector('.quoted').textContent = info.text;
    modal.classList.add('visible');
    hideSelectionToolbar();
    modal.dataset.pendingChapter = info.chapterId;
    modal.dataset.pendingBook = info.bookSlug;
    modal.dataset.pendingText = info.text;
    modal.querySelector('textarea').value = '';
    modal.querySelector('textarea').focus();
});

document.querySelector('.note-modal .cancel').addEventListener('click', () => {
    document.querySelector('.note-modal').classList.remove('visible');
});

document.querySelector('.note-modal .save').addEventListener('click', () => {
    const modal = document.querySelector('.note-modal');
    const text = modal.querySelector('textarea').value.trim();
    if (!text) return;
    notes.push({
        type: 'note',
        chapterId: modal.dataset.pendingChapter,
        bookSlug: modal.dataset.pendingBook,
        quote: modal.dataset.pendingText,
        text,
        timestamp: Date.now(),
    });
    saveNotes();
    modal.classList.remove('visible');
    renderNotesList();
    setTimeout(() => {
        const chapter = document.getElementById(modal.dataset.pendingChapter);
        if (chapter) chapter.scrollIntoView({ behavior: 'smooth' });
    }, 100);
});

document.getElementById('notes-btn').addEventListener('click', () => {
    document.querySelector('.notes-panel').classList.toggle('visible');
});

document.querySelector('.notes-panel-header .close').addEventListener('click', () => {
    document.querySelector('.notes-panel').classList.remove('visible');
});

function renderNotesList() {
    const list = document.querySelector('.notes-list');
    if (notes.length === 0) {
        list.innerHTML = '<div class="notes-empty">还没有笔记<br><br>选中文字后<br>点击浮动工具栏添加 ✎</div>';
        return;
    }

    // 按书 + 章节分组
    const byBookChapter = {};
    notes.forEach((note, idx) => {
        const key = (note.bookSlug || 'unknown') + '|' + (note.chapterId || '');
        if (!byBookChapter[key]) byBookChapter[key] = [];
        byBookChapter[key].push({ ...note, idx });
    });

    let html = '';
    Object.entries(byBookChapter).forEach(([key, items]) => {
        const [bookSlug, chapterId] = key.split('|');
        const chapter = document.getElementById(chapterId);
        const chapterTitle = chapter?.querySelector('.chapter-title')?.textContent || chapterId;
        const bookHeader = document.querySelector(`[data-book="${bookSlug}"] .book-title-text`);
        const bookTitle = bookHeader?.textContent || bookSlug;

        html += `<div style="margin-bottom: 8px; font-size: 10px; color: var(--text-faint); letter-spacing: 1px;">${bookTitle} · ${chapterTitle}</div>`;

        items.sort((a, b) => b.timestamp - a.timestamp).forEach(note => {
            html += `
                <div class="note-item" data-chapter="${chapterId}" data-idx="${note.idx}">
                    <button class="note-delete">×</button>
                    <div class="note-quote">${note.quote || note.text || ''}</div>
                    ${note.type === 'note' ? `<div class="note-text">${note.text}</div>` : ''}
                    <div class="note-meta">${new Date(note.timestamp).toLocaleString('zh-CN')}</div>
                </div>
            `;
        });
    });

    list.innerHTML = html;

    list.querySelectorAll('.note-item').forEach(item => {
        const chapterId = item.dataset.chapter;
        const idx = parseInt(item.dataset.idx);
        item.addEventListener('click', (e) => {
            if (e.target.classList.contains('note-delete')) return;
            document.getElementById(chapterId)?.scrollIntoView({ behavior: 'smooth' });
        });
        item.querySelector('.note-delete').addEventListener('click', (e) => {
            notes.splice(idx, 1);
            saveNotes();
            renderNotesList();
            e.stopPropagation();
        });
    });
}

renderNotesList();

// PWA
if ('serviceWorker' in navigator) {
    const swCode = `
        const CACHE = 'knowledge-book-v1';
        self.addEventListener('install', e => {
            e.waitUntil(caches.open(CACHE).then(c => c.add('./')));
            self.skipWaiting();
        });
        self.addEventListener('activate', e => { e.waitUntil(self.clients.claim()); });
        self.addEventListener('fetch', e => {
            e.respondWith(caches.match(e.request).then(r => r || fetch(e.request).catch(() => caches.match('./'))));
        });
    `;
    const blob = new Blob([swCode], { type: 'application/javascript' });
    const swUrl = URL.createObjectURL(blob);
    navigator.serviceWorker.register(swUrl).catch(() => {});
}

let deferredPrompt = null;
window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault();
    deferredPrompt = e;
    const dismissed = localStorage.getItem('pwaPromptDismissed');
    if (!dismissed) {
        setTimeout(() => {
            document.querySelector('.pwa-prompt').classList.add('visible');
        }, 5000);
    }
});

document.querySelector('.pwa-prompt .close').addEventListener('click', () => {
    document.querySelector('.pwa-prompt').classList.remove('visible');
    localStorage.setItem('pwaPromptDismissed', 'true');
});

// 锚点平滑滚动
links.forEach(link => {
    link.addEventListener('click', (e) => {
        const target = document.querySelector(link.getAttribute('href'));
        if (target) {
            e.preventDefault();
            target.scrollIntoView({ behavior: 'smooth', block: 'start' });
            if (window.innerWidth < 900) {
                document.body.classList.add('sidebar-collapsed');
            }
        }
    });
});

// 快捷键
document.addEventListener('keydown', (e) => {
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;

    if (e.key === 'd' || e.key === 'D') toggleDark();
    if (e.key === 's' || e.key === 'S') document.getElementById('sidebar-toggle').click();
    if (e.key === 'm' || e.key === 'M') document.getElementById('music-btn').click();
    if (e.key === 'n' || e.key === 'N') document.getElementById('notes-btn').click();
    if (e.key === 'p' || e.key === 'P') document.getElementById('progress-btn').click();
    if (e.key === '+' || e.key === '=') {
        const sizes = Object.keys(FONT_SIZES);
        const idx = sizes.indexOf(currentFontSize);
        if (idx < sizes.length - 1) { currentFontSize = sizes[idx + 1]; setFontSize(currentFontSize); }
    }
    if (e.key === '-' || e.key === '_') {
        const sizes = Object.keys(FONT_SIZES);
        const idx = sizes.indexOf(currentFontSize);
        if (idx > 0) { currentFontSize = sizes[idx - 1]; setFontSize(currentFontSize); }
    }
    if (e.key === 'Escape') {
        document.querySelector('.music-panel').classList.remove('visible');
        document.querySelector('.notes-panel').classList.remove('visible');
        document.querySelector('.note-modal').classList.remove('visible');
        document.querySelector('.progress-panel').classList.remove('visible');
    }
});

// ============================================================
// 进度统计
// ============================================================
let progress = JSON.parse(localStorage.getItem('progress') || '{}');
if (!progress.completed) progress = { completed: {} };

function saveProgress() {
    localStorage.setItem('progress', JSON.stringify(progress));
}

function toggleChapter(chapterId) {
    if (progress.completed[chapterId]) {
        delete progress.completed[chapterId];
    } else {
        progress.completed[chapterId] = Date.now();
    }
    saveProgress();
    refreshCompletionUI();
}

function refreshCompletionUI() {
    // 每章 toggle button 状态
    document.querySelectorAll('.completion-toggle').forEach(btn => {
        const chapterId = btn.dataset.chapter;
        const isCompleted = !!progress.completed[chapterId];
        btn.classList.toggle('completed', isCompleted);
        btn.textContent = isCompleted ? '✓ 已读 (点击撤销)' : '☐ 标记为已读';
        // article 加 completed class
        const article = document.getElementById(chapterId);
        if (article) article.classList.toggle('completed', isCompleted);
    });

    // 侧栏每章标记
    document.querySelectorAll('.book-chapters a').forEach(a => {
        const chapterId = a.getAttribute('href').slice(1);
        a.classList.toggle('completed', !!progress.completed[chapterId]);
    });
}

document.querySelectorAll('.completion-toggle').forEach(btn => {
    btn.addEventListener('click', () => toggleChapter(btn.dataset.chapter));
});

// 打开进度面板
document.getElementById('progress-btn').addEventListener('click', openProgressPanel);
document.querySelector('.progress-panel .close').addEventListener('click', () => {
    document.querySelector('.progress-panel').classList.remove('visible');
});

function openProgressPanel() {
    renderProgress();
    document.querySelector('.progress-panel').classList.add('visible');
}

function renderProgress() {
    // 收集所有章节
    const allChapters = Array.from(document.querySelectorAll('.chapter')).map(c => ({
        id: c.id,
        book: c.dataset.book,
        bookTitle: c.closest('.chapter').dataset.book,
    }));

    // 按书分组
    const bookStats = {};
    allChapters.forEach(c => {
        const bookGroup = document.querySelector(`[data-book="${c.book}"]`);
        const bookTitle = bookGroup?.querySelector('.book-title-text')?.textContent || c.book;
        if (!bookStats[c.book]) {
            bookStats[c.book] = { title: bookTitle, total: 0, completed: 0 };
        }
        bookStats[c.book].total++;
        if (progress.completed[c.id]) bookStats[c.book].completed++;
    });

    const totalChapters = allChapters.length;
    const completedChapters = allChapters.filter(c => progress.completed[c.id]).length;
    const percent = totalChapters > 0 ? Math.round(completedChapters / totalChapters * 100) : 0;

    document.getElementById('overall-percent').textContent = percent;
    document.getElementById('overall-stats').textContent = `${completedChapters} / ${totalChapters} 章`;
    document.getElementById('overall-fill').style.width = percent + '%';

    // 各书进度
    const bookProgressList = document.getElementById('book-progress-list');
    bookProgressList.innerHTML = Object.entries(bookStats).map(([slug, stats]) => {
        const pct = stats.total > 0 ? Math.round(stats.completed / stats.total * 100) : 0;
        return `
            <div class="book-progress">
                <div class="book-progress-header">
                    <span class="book-progress-name">${stats.title}</span>
                    <span class="book-progress-stats">${stats.completed} / ${stats.total} · ${pct}%</span>
                </div>
                <div class="book-progress-bar">
                    <div class="book-progress-bar-fill" style="width: ${pct}%"></div>
                </div>
            </div>
        `;
    }).join('');

    // 日历
    renderCalendar();
}

function renderCalendar() {
    const grid = document.getElementById('calendar-grid');
    grid.innerHTML = '';

    // 每天的完成数
    const daily = {};
    Object.values(progress.completed).forEach(ts => {
        const date = new Date(ts).toISOString().slice(0, 10);
        daily[date] = (daily[date] || 0) + 1;
    });

    // 365 天
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const startDate = new Date(today);
    startDate.setDate(startDate.getDate() - 364);

    // 按周分列（GitHub 风格）
    let currentDate = new Date(startDate);
    // 调整到最近的周日
    currentDate.setDate(currentDate.getDate() - currentDate.getDay());

    while (currentDate <= today) {
        const week = document.createElement('div');
        week.className = 'calendar-week';

        for (let i = 0; i < 7; i++) {
            const day = document.createElement('div');
            day.className = 'calendar-day';

            if (currentDate > today) {
                day.classList.add('empty');
            } else {
                const dateKey = currentDate.toISOString().slice(0, 10);
                const count = daily[dateKey] || 0;

                if (count === 0) {
                    // 保持空
                } else if (count === 1) {
                    day.classList.add('level-1');
                } else if (count === 2) {
                    day.classList.add('level-2');
                } else if (count <= 4) {
                    day.classList.add('level-3');
                } else {
                    day.classList.add('level-4');
                }

                day.title = `${dateKey}: ${count} 章`;
            }

            week.appendChild(day);
            currentDate.setDate(currentDate.getDate() + 1);
        }

        grid.appendChild(week);
    }
}

// 导出/导入/重置
document.getElementById('export-progress').addEventListener('click', () => {
    const blob = new Blob([JSON.stringify(progress, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `knowledge-garden-progress-${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
    URL.revokeObjectURL(url);
});

document.getElementById('import-progress').addEventListener('click', () => {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = 'application/json';
    input.onchange = (e) => {
        const file = e.target.files[0];
        if (!file) return;
        const reader = new FileReader();
        reader.onload = (evt) => {
            try {
                const imported = JSON.parse(evt.target.result);
                if (imported.completed) {
                    progress = imported;
                    saveProgress();
                    refreshCompletionUI();
                    renderProgress();
                    alert('✓ 数据导入成功');
                }
            } catch (err) {
                alert('✗ 文件格式错误: ' + err.message);
            }
        };
        reader.readAsText(file);
    };
    input.click();
});

document.getElementById('reset-progress').addEventListener('click', () => {
    if (confirm('确定要重置所有阅读进度吗？此操作不可撤销。')) {
        progress = { completed: {} };
        saveProgress();
        refreshCompletionUI();
        renderProgress();
    }
});

// 初始化
refreshCompletionUI();

// ============================================================
// 命令面板（Ctrl+K 全局搜索）
// ============================================================
const searchIndex = [];
document.querySelectorAll('.chapter').forEach(ch => {
    const titleEl = ch.querySelector('.chapter-title');
    const contentEl = ch.querySelector('.chapter-content');
    const title = titleEl?.textContent.trim() || '';
    const text = contentEl?.textContent.trim() || '';
    const bookEl = document.querySelector(`[data-book="${ch.dataset.book}"] .book-title-text`);
    const bookTitle = bookEl?.textContent || ch.dataset.book;

    searchIndex.push({
        id: ch.id,
        book: ch.dataset.book,
        bookTitle,
        title,
        text,
        lower: (title + ' ' + text).toLowerCase(),
    });
});

const commandPalette = document.querySelector('.command-palette');
const commandInput = document.querySelector('.command-input');
const commandResults = document.querySelector('.command-results');
let activeCommandIdx = -1;

function highlightSnippet(text, query, len = 100) {
    const lower = text.toLowerCase();
    const idx = lower.indexOf(query);
    if (idx < 0) return text.slice(0, len) + (text.length > len ? '…' : '');

    const start = Math.max(0, idx - 30);
    const end = Math.min(text.length, idx + query.length + len - 30);
    let snippet = text.slice(start, end);
    if (start > 0) snippet = '…' + snippet;
    if (end < text.length) snippet = snippet + '…';

    const regex = new RegExp(query.replace(/[.*+?^${}()|[\]\\]/g, r'\$&'), 'gi');
    return snippet.replace(regex, m => `<mark>${m}</mark>`);
}

function performSearch(query) {
    commandResults.innerHTML = '';
    activeCommandIdx = -1;

    if (!query) return;

    const q = query.toLowerCase();
    const results = [];

    for (const item of searchIndex) {
        if (item.lower.includes(q)) {
            // 算分数：标题命中 > 内容命中
            const titleIdx = item.title.toLowerCase().indexOf(q);
            const score = titleIdx >= 0 ? (100 - titleIdx) : 1;
            results.push({ ...item, score });
        }
    }

    results.sort((a, b) => b.score - a.score);
    const top = results.slice(0, 10);

    if (top.length === 0) {
        commandResults.innerHTML = '<div class="command-empty">没有匹配的章节</div>';
        return;
    }

    commandResults.innerHTML = top.map((r, i) => `
        <div class="command-item" data-chapter="${r.id}" data-idx="${i}">
            <div class="command-book-tag">${r.bookTitle}</div>
            <div class="command-title">${r.title}</div>
            <div class="command-snippet">${highlightSnippet(r.text, q)}</div>
        </div>
    `).join('');

    commandResults.querySelectorAll('.command-item').forEach(item => {
        item.addEventListener('click', () => jumpToCommand(item.dataset.chapter));
        item.addEventListener('mouseenter', () => {
            commandResults.querySelectorAll('.command-item').forEach(el => el.classList.remove('active'));
            item.classList.add('active');
            activeCommandIdx = parseInt(item.dataset.idx);
        });
    });

    activeCommandIdx = 0;
    commandResults.querySelector('.command-item')?.classList.add('active');
}

function jumpToCommand(chapterId) {
    commandPalette.classList.remove('visible');
    commandInput.value = '';
    const target = document.getElementById(chapterId);
    if (target) {
        target.scrollIntoView({ behavior: 'smooth', block: 'start' });
        history.pushState(null, '', '#' + chapterId);
    }
}

// 打开/关闭
document.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        commandPalette.classList.add('visible');
        commandInput.focus();
        commandInput.select();
    }
    if (e.key === 'Escape' && commandPalette.classList.contains('visible')) {
        commandPalette.classList.remove('visible');
        commandInput.value = '';
    }
    if (commandPalette.classList.contains('visible')) {
        if (e.key === 'ArrowDown') {
            e.preventDefault();
            const items = commandResults.querySelectorAll('.command-item');
            if (items.length === 0) return;
            items.forEach(el => el.classList.remove('active'));
            activeCommandIdx = Math.min(items.length - 1, activeCommandIdx + 1);
            items[activeCommandIdx]?.classList.add('active');
            items[activeCommandIdx]?.scrollIntoView({ block: 'nearest' });
        }
        if (e.key === 'ArrowUp') {
            e.preventDefault();
            const items = commandResults.querySelectorAll('.command-item');
            if (items.length === 0) return;
            items.forEach(el => el.classList.remove('active'));
            activeCommandIdx = Math.max(0, activeCommandIdx - 1);
            items[activeCommandIdx]?.classList.add('active');
            items[activeCommandIdx]?.scrollIntoView({ block: 'nearest' });
        }
        if (e.key === 'Enter') {
            e.preventDefault();
            const active = commandResults.querySelector('.command-item.active');
            if (active) jumpToCommand(active.dataset.chapter);
        }
    }
});

commandInput.addEventListener('input', (e) => performSearch(e.target.value.trim()));

// 点击背景关闭
commandPalette.addEventListener('click', (e) => {
    if (e.target === commandPalette) {
        commandPalette.classList.remove('visible');
        commandInput.value = '';
    }
});
"""


def build_html():
    books = discover_books()

    if not books:
        print("⚠️  没找到任何书。请在 books/ 目录下创建子目录。")
        return

    # 构建内容
    bookshelf_html_parts = []
    content_parts = []
    total_chars = 0
    total_chapters = 0

    book_icons = ["📕", "📗", "📘", "📙", "📓", "📔", "🗂"]

    for book_idx, (book_slug, meta, chapters) in enumerate(books):
        book_icon = book_icons[book_idx % len(book_icons)]
        book_color = meta.get("color", "#b08968")

        # 书架章节列表
        chapter_items = []
        book_chapters_html_parts = []

        for chap_idx, (chap_slug, chap_path) in enumerate(chapters, 1):
            md_text = chap_path.read_text(encoding="utf-8")
            content_html = md_to_html(md_text)
            chars = count_words(md_text)
            total_chars += chars
            minutes = max(1, chars // 400)

            # 用目录名（去掉数字前缀）作为展示标题
            display_title = chap_slug
            # 尝试从 README 第一个 # 标题取
            first_heading = re.search(r"^#\s+(.+)$", md_text, re.MULTILINE)
            if first_heading:
                display_title = first_heading.group(1).strip()

            # 章节锚点：bookSlug__chapterSlug
            anchor = f"{book_slug}__{chap_slug}"

            chapter_items.append(
                f'<li><a href="#{anchor}">'
                f'<span class="ch-num">{chap_idx:02d}</span>'
                f'<span>{display_title}</span>'
                f'</a></li>'
            )

            book_chapters_html_parts.append(
                f'<article id="{anchor}" class="chapter" data-book="{book_slug}" data-chap="{chap_slug}">'
                f'<div class="chapter-num">CHAPTER {chap_idx:02d}</div>'
                f'<h1 class="chapter-title">{display_title}</h1>'
                f'<div class="chapter-meta">约 {minutes} 分钟 · {chars} 字</div>'
                f'<div class="chapter-content">{content_html}</div>'
                f'<div class="chapter-end">本章完</div>'
                f'<button class="completion-toggle" data-chapter="{anchor}">☐ 标记为已读</button>'
                f'</article>'
            )

            total_chapters += 1

        # 书的章节数
        chap_count = len(chapters)

        # 书架 HTML
        bookshelf_html_parts.append(
            f'<div class="book-group" data-book="{book_slug}">'
            f'<div class="book-header">'
            f'<span class="book-icon">{book_icon}</span>'
            f'<span class="book-title-text">{meta["title"]}</span>'
            f'<span class="book-chapters-count">{chap_count} 章</span>'
            f'</div>'
            f'<ul class="book-chapters">'
            f'{"".join(chapter_items)}'
            f'</ul>'
            f'</div>'
        )

        # 书封面 + 内容
        book_chars = sum(count_words(p.read_text(encoding="utf-8")) for _, p in chapters)
        book_minutes = max(1, book_chars // 400)

        book_cover = (
            f'<div class="book-cover">'
            f'<div class="book-icon-big">{book_icon}</div>'
            f'<h1>{meta["title"]}</h1>'
            f'<p>{meta["description"]}</p>'
            f'<div class="book-stats">{chap_count} 章 · {book_chars:,} 字 · 约 {book_minutes} 分钟</div>'
            f'</div>'
        )

        content_parts.append(book_cover + "".join(book_chapters_html_parts))

    total_minutes = max(1, total_chars // 400)

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>个人知识库 · 多书阅读</title>

    <link rel="manifest" href='data:application/json,{{"name":"个人知识库","short_name":"KB","start_url":"./","display":"standalone","background_color":"%23faf9f5","theme_color":"%23b08968","icons":[{{"src":"{PWA_ICON_DATA_URI}","sizes":"any","type":"image/svg+xml","purpose":"any"}}]}}'>
    <link rel="icon" type="image/svg+xml" href='{PWA_ICON_DATA_URI}'>
    <link rel="apple-touch-icon" href='{PWA_ICON_DATA_URI}'>
    <meta name="theme-color" content="#faf9f5">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="default">
    <meta name="apple-mobile-web-app-title" content="知识库">

    <style>{CSS}</style>
</head>
<body class="sidebar-collapsed">
    <div class="progress"></div>

    <button class="sidebar-toggle" id="sidebar-toggle" title="目录 (S)">☰ 书架</button>

    <aside class="sidebar">
        <h1>个人知识库</h1>
        <div class="subtitle">{len(books)} 个系列 · {total_chapters} 章 · 约 {total_minutes} 分钟</div>
        <div class="bookshelf">
            {''.join(bookshelf_html_parts)}
        </div>
    </aside>

    <div class="toolbar">
        <button class="font-btn" data-size="small" title="小字号 (-)">A−</button>
        <button class="font-btn" data-size="medium" title="中字号">A</button>
        <button class="font-btn" data-size="large" title="大字号 (+)">A+</button>
        <div class="divider"></div>
        <button id="music-btn" title="背景音乐 (M)">♪</button>
        <button id="notes-btn" title="笔记 (N)">✎</button>
        <button id="progress-btn" title="阅读进度 (P)">✓</button>
        <button id="dark-btn" title="暗色模式 (D)">🌙</button>
    </div>

    <div class="selection-toolbar">
        <div class="color-swatch yellow active" data-color="yellow"></div>
        <div class="color-swatch green" data-color="green"></div>
        <div class="color-swatch blue" data-color="blue"></div>
        <div class="color-swatch pink" data-color="pink"></div>
        <div class="divider" style="background: rgba(255,255,255,0.2);"></div>
        <button class="note-btn">✎ 笔记</button>
    </div>

    <div class="note-modal">
        <div class="note-modal-content">
            <h3>添加笔记</h3>
            <div class="quoted"></div>
            <textarea placeholder="写下你的想法..."></textarea>
            <div class="actions">
                <button class="cancel">取消</button>
                <button class="save">保存</button>
            </div>
        </div>
    </div>

    <aside class="notes-panel">
        <div class="notes-panel-header">
            <h2>✎ 我的笔记</h2>
            <button class="close">×</button>
        </div>
        <div class="notes-list"></div>
    </aside>

    <div class="music-panel">
        <h4>背景音 <button class="close">×</button></h4>
        <div class="scenes">
            <button class="scene-btn" data-scene="off">🔇 静音</button>
            <button class="scene-btn" data-scene="white">🌊 白噪音</button>
            <button class="scene-btn" data-scene="rain">🌧 雨声</button>
            <button class="scene-btn" data-scene="warm">🎵 暖调</button>
        </div>
        <div class="volume">🔈 <input type="range" min="0" max="100" value="30"> 🔊</div>
    </div>

    <div class="pwa-prompt">
        📱 添加到主屏幕，离线可用
        <button class="close">×</button>
    </div>

    <!-- 进度面板 -->
    <div class="progress-panel">
        <div class="progress-modal">
            <div class="progress-modal-header">
                <h2>📊 阅读进度</h2>
                <button class="close">×</button>
            </div>

            <div class="overall-progress">
                <div class="big-number"><span id="overall-percent">0</span>%</div>
                <div class="label"><span id="overall-stats">0 / 0 章</span></div>
                <div class="progress-bar">
                    <div class="progress-bar-fill" id="overall-fill" style="width: 0%"></div>
                </div>
            </div>

            <div id="book-progress-list"></div>

            <div class="calendar">
                <div class="calendar-title">
                    <span>📅 阅读日历（过去 365 天）</span>
                    <div class="calendar-legend">
                        <span>少</span>
                        <span class="calendar-day"></span>
                        <span class="calendar-day level-1"></span>
                        <span class="calendar-day level-2"></span>
                        <span class="calendar-day level-3"></span>
                        <span class="calendar-day level-4"></span>
                        <span>多</span>
                    </div>
                </div>
                <div class="calendar-grid" id="calendar-grid"></div>
            </div>

            <div class="progress-actions">
                <button id="export-progress">📤 导出数据</button>
                <button id="import-progress">📥 导入数据</button>
                <button id="reset-progress">🗑 重置进度</button>
            </div>
        </div>
    </div>

    <!-- 命令面板（搜索） -->
    <div class="command-palette">
        <div class="command-modal">
            <input type="text" class="command-input" placeholder="🔍 搜索章节标题或内容...">
            <div class="command-hint">
                <span>↑↓ 选择 · Enter 跳转 · Esc 关闭</span>
                <span>Ctrl+K</span>
            </div>
            <div class="command-results"></div>
        </div>
    </div>

    <main class="content">
        {''.join(content_parts)}
    </main>

    <script>{JS}</script>
</body>
</html>"""

    output = ROOT / "index.html"
    output.write_text(html, encoding="utf-8")
    print(f"✓ 生成 {output}")
    print(f"  大小: {len(html):,} 字符 ({len(html) / 1024:.1f} KB)")
    print(f"  系列: {len(books)} | 总章节: {total_chapters} | 总字数: {total_chars:,}")
    for slug, meta, chs in books:
        print(f"    {meta['title']} ({len(chs)} 章)")


if __name__ == "__main__":
    build_html()