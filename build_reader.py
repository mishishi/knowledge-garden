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
from io import BytesIO
from pathlib import Path

import markdown
import qrcode


ROOT = Path(__file__).parent
BOOKS_DIR = ROOT / "books"

# 部署地址（用于生成扫码阅读的 QR 码）
# 改这里后重新 build 即可，无需修改其他代码
SITE_URL = "https://mishishi.github.io/knowledge-garden/"


def make_qr_data_url(url: str, box_size: int = 8, border: int = 2) -> str:
    """生成 QR 码 PNG 的 base64 data URL，用于内联到 HTML。"""
    qr = qrcode.QRCode(
        version=None,   # 自动选 version
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=box_size,
        border=border,
    )
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = BytesIO()
    img.save(buf, format="PNG", optimize=True)
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{b64}"


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


# ============================================================
# SVG Icons（替换 emoji，统一线条风格，stroke=currentColor）
# ============================================================
ICONS = {
    # Toolbar
    'menu':     '<line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/>',
    'music':    '<path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/>',
    'notes':    '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="8" y1="13" x2="16" y2="13"/><line x1="8" y1="17" x2="14" y2="17"/>',
    'progress': '<circle cx="12" cy="12" r="10"/><polyline points="8 12 11 15 16 9"/>',
    'moon':     '<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>',
    'search':   '<circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>',

    # Sidebar
    'book':     '<path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/>',

    # Music scenes
    'mute':     '<polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><line x1="23" y1="9" x2="17" y2="15"/><line x1="17" y1="9" x2="23" y2="15"/>',
    'wave':     '<path d="M2 12c2-3 4-3 6 0s4 3 6 0 4-3 6 0 4 3 6 0"/>',
    'rain':     '<path d="M20 16.2A4.5 4.5 0 0 0 17.5 8h-1.8A7 7 0 1 0 4 14.9"/><line x1="16" y1="14" x2="16" y2="20"/><line x1="8" y1="14" x2="8" y2="20"/><line x1="12" y1="18" x2="12" y2="22"/>',
    'flame':    '<path d="M8.5 14.5A2.5 2.5 0 0 0 11 12c0-1.38-.5-2-1-3-1.072-2.143-.224-4.054 2-6 .5 2.5 2 4.9 4 6.5 2 1.6 3 3.5 3 5.5a7 7 0 1 1-14 0c0-1.153.433-2.294 1-3a2.5 2.5 0 0 0 2.5 2.5z"/>',

    # Data ops
    'download': '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>',
    'upload':   '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/>',
    'trash':    '<polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/>',

    # Panels
    'calendar': '<rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/>',
    'pwa':      '<rect x="5" y="2" width="14" height="20" rx="2" ry="2"/><line x1="12" y1="18" x2="12.01" y2="18"/>',
    'plus':     '<line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>',

    # Common
    'check':    '<polyline points="20 6 9 17 4 12"/>',
    'close':    '<line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>',
    'volume':   '<polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14"/><path d="M15.54 8.46a5 5 0 0 1 0 7.07"/>',

    # Book covers（按系列主题区分）
    'agents':   '<circle cx="6" cy="6" r="2.5"/><circle cx="18" cy="6" r="2.5"/><circle cx="12" cy="18" r="2.5"/><line x1="7.7" y1="7.7" x2="11" y2="16.3"/><line x1="16.3" y1="7.7" x2="13" y2="16.3"/><line x1="8.5" y1="6" x2="15.5" y2="6"/>',
    'sparkles': '<path d="M12 3l1.7 5.2a2 2 0 0 0 1.1 1.1L20 11l-5.2 1.7a2 2 0 0 0-1.1 1.1L12 19l-1.7-5.2a2 2 0 0 0-1.1-1.1L4 11l5.2-1.7a2 2 0 0 0 1.1-1.1z"/><path d="M5 3v3"/><path d="M3 5h3"/><path d="M19 17v3"/><path d="M17 19h3"/>',
    'bot':      '<path d="M12 8V4H8"/><rect width="16" height="12" x="4" y="8" rx="2"/><path d="M2 14h2"/><path d="M20 14h2"/><path d="M15 13v2"/><path d="M9 13v2"/>',
    'bookmark': '<path d="m19 21-7-4-7 4V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v16z"/>',
    'database': '<ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M3 5v14a9 3 0 0 0 18 0V5"/><path d="M3 12a9 3 0 0 0 18 0"/>',
    'qr':       '<rect width="5" height="5" x="3" y="3" rx="1"/><rect width="5" height="5" x="16" y="3" rx="1"/><rect width="5" height="5" x="3" y="16" rx="1"/><path d="M5 5h.01"/><path d="M19 5h.01"/><path d="M5 19h.01"/><line x1="10" y1="5" x2="14" y2="5"/><line x1="10" y1="19" x2="14" y2="19"/><line x1="19" y1="10" x2="19" y2="14"/><line x1="5" y1="10" x2="5" y2="14"/><line x1="10" y1="10" x2="14" y2="10"/><line x1="10" y1="14" x2="14" y2="14"/><line x1="14" y1="10" x2="14" y2="14"/><line x1="10" y1="14" x2="10" y2="10"/>',
    'disc':     '<circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="3"/><path d="M6 12c0-1.7 1.3-3 3-3"/>',
}


def svg_icon(name, size=16, stroke_width=1.5, classes=""):
    """生成 SVG icon HTML。颜色跟随 currentColor。"""
    if name not in ICONS:
        return ''
    cls = f' class="icon {classes}"' if classes else ' class="icon"'
    return (
        f'<svg{cls} width="{size}" height="{size}" viewBox="0 0 24 24" '
        f'fill="none" stroke="currentColor" stroke-width="{stroke_width}" '
        f'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
        f'{ICONS[name]}</svg>'
    )


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
.icon {
    display: inline-block;
    vertical-align: middle;
    flex-shrink: 0;
}

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
    --done: #6b9b76;
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

/* Focus mode：隐藏侧栏 / 工具栏 / 进度条，纯净阅读 */
body.focus-mode .sidebar,
body.focus-mode .sidebar-toggle,
body.focus-mode .toolbar,
body.focus-mode #more-btn,
body.focus-mode .reading-progress,
body.focus-mode .page-flip { display: none !important; }

body.focus-mode .content {
    max-width: 760px;
    padding: 60px 32px;
    margin-left: auto;
    margin-right: auto;
}

body.focus-mode .focus-exit { display: flex; }

.focus-exit {
    position: fixed;
    top: 16px;
    right: 16px;
    background: rgba(0, 0, 0, 0.5);
    color: white;
    border: none;
    width: 36px;
    height: 36px;
    border-radius: 50%;
    cursor: pointer;
    display: none;
    align-items: center;
    justify-content: center;
    z-index: 200;
    backdrop-filter: blur(8px);
}
.focus-exit:hover { background: rgba(0, 0, 0, 0.7); }

.reading-progress {
    position: fixed;
    top: 0;
    left: 0;
    height: 2px;
    background: var(--accent);
    width: 0%;
    z-index: 200;
    transition: width 0.05s linear;
    pointer-events: none;
}
body.dark .reading-progress { background: #c4a87c; }

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
    --done: #7ba888;
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
    align-items: center;
}

#more-btn {
    width: 40px;
    height: 40px;
    border-radius: 50%;
    background: rgba(255, 255, 255, 0.85);
    border: 1px solid var(--border);
    color: var(--text-soft);
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.04);
    transition: all 0.15s;
}
#more-btn:hover {
    color: var(--accent);
    background: var(--accent-soft);
    border-color: var(--accent);
}
#more-btn.open {
    color: white;
    background: var(--accent);
    border-color: var(--accent);
}
body.dark #more-btn { background: rgba(40, 40, 44, 0.85); }

.toolbar-menu {
    position: absolute;
    top: 48px;
    right: 0;
    min-width: 200px;
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 6px;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.08);
    display: none;
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
}
.toolbar-menu.visible { display: block; }
body.dark .toolbar-menu { background: rgba(28, 28, 30, 0.95); }

.toolbar-section { padding: 4px 0; }
.toolbar-section .section-label {
    display: block;
    color: var(--text-faint);
    font-size: 10px;
    padding: 6px 12px 4px;
    letter-spacing: 0.8px;
    text-transform: uppercase;
}
.toolbar-section.font-sizes {
    display: flex;
    gap: 2px;
    padding: 4px 6px;
}
.toolbar-section.font-sizes button {
    flex: 1;
    padding: 6px 0;
    text-align: center;
}

.toolbar-divider {
    height: 1px;
    background: var(--border);
    margin: 4px 6px;
}

.toolbar-actions {
    display: flex;
    flex-direction: column;
    gap: 1px;
}

.toolbar-actions button,
.toolbar-section button {
    display: flex;
    align-items: center;
    gap: 10px;
    width: 100%;
    text-align: left;
    padding: 8px 12px;
    border: none;
    background: transparent;
    border-radius: 6px;
    cursor: pointer;
    color: var(--text);
    font-size: 13px;
    transition: all 0.15s;
}
.toolbar-actions button:hover,
.toolbar-section button:hover {
    background: var(--accent-soft);
    color: var(--accent);
}
.toolbar-actions button.active {
    background: var(--accent);
    color: white;
}
.toolbar-actions button kbd {
    margin-left: auto;
    font-family: ui-monospace, "SF Mono", monospace;
    font-size: 10px;
    color: var(--text-faint);
    background: var(--bg-soft);
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 1px 5px;
}
body.dark .toolbar-actions button kbd { background: rgba(255, 255, 255, 0.05); }
.toolbar-actions button:hover kbd,
.toolbar-actions button.active kbd { color: inherit; opacity: 0.7; }

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

.sidebar-bookmarks {
    margin-top: 24px;
    padding-top: 16px;
    border-top: 1px solid var(--border);
}
.sidebar-bookmarks .sb-title {
    font-size: 11px;
    color: var(--text-soft);
    text-transform: uppercase;
    letter-spacing: 0.6px;
    margin-bottom: 8px;
    display: flex;
    justify-content: space-between;
    align-items: center;
}
.sidebar-bookmarks .sb-count {
    background: var(--accent-soft);
    color: var(--accent);
    padding: 1px 7px;
    border-radius: 10px;
    font-size: 10px;
}
.sidebar-bookmarks .sb-item {
    background: var(--bg-soft);
    border-left: 2px solid var(--accent);
    border-radius: 4px;
    padding: 6px 10px;
    margin-bottom: 6px;
    cursor: pointer;
    position: relative;
    transition: all 0.15s;
}
.sidebar-bookmarks .sb-item:hover {
    background: var(--accent-soft);
}
.sidebar-bookmarks .sb-chapter {
    font-size: 10px;
    color: var(--text-faint);
    margin-bottom: 2px;
    font-family: ui-monospace, "SF Mono", Menlo, monospace;
}
.sidebar-bookmarks .sb-text {
    font-size: 12px;
    color: var(--text);
    line-height: 1.5;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
}
.sidebar-bookmarks .sb-delete {
    position: absolute;
    top: 4px;
    right: 4px;
    background: transparent;
    border: none;
    color: var(--text-faint);
    cursor: pointer;
    font-size: 14px;
    line-height: 1;
    padding: 2px 6px;
    opacity: 0;
    transition: opacity 0.15s;
}
.sidebar-bookmarks .sb-item:hover .sb-delete { opacity: 1; }
.sidebar-bookmarks .sb-delete:hover { color: var(--accent); }
.sidebar-bookmarks .sb-empty {
    font-size: 12px;
    color: var(--text-faint);
    padding: 12px 0;
    text-align: center;
    font-style: italic;
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
    flex-shrink: 0;
    width: 16px;
    height: 16px;
    color: var(--text-soft);
    display: inline-flex;
    align-items: center;
    justify-content: center;
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
    display: flex;
    align-items: center;
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

.book-chapters .ch-read-pct {
    margin-left: auto;
    font-size: 10px;
    color: var(--accent);
    font-variant-numeric: tabular-nums;
    flex-shrink: 0;
}
.book-chapters li a.completed .ch-read-pct { color: var(--done); }

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
    width: 72px;
    height: 72px;
    margin: 0 auto 24px auto;
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--book-color, var(--accent));
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
    content: "—";
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

.chapter-end::before { content: "———"; color: var(--accent); letter-spacing: 8px; }

@media (max-width: 900px) {
    .sidebar { transform: translateX(-300px); }
    body:not(.sidebar-collapsed) .sidebar { transform: translateX(0); }
    body:not(.sidebar-collapsed) .sidebar-toggle { left: 320px; }
    .content { padding: 80px 24px; max-width: 100%; }
    .chapter-title { font-size: 1.8em; }
    .chapter-num { font-size: 12px; letter-spacing: 5px; }
    .book-cover h1 { font-size: 1.8em; }
    .toolbar { top: 8px; right: 8px; }
    #more-btn { width: 36px; height: 36px; }
    .toolbar-menu { min-width: 180px; }
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

/* === QR 扫码弹窗 === */
.qr-modal-backdrop {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.5);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 10001;
    opacity: 0;
    pointer-events: none;
    transition: opacity 0.2s;
}
.qr-modal-backdrop.visible {
    opacity: 1;
    pointer-events: auto;
}
.qr-modal {
    background: var(--card-bg, #ffffff);
    border-radius: 12px;
    padding: 32px 28px 24px 28px;
    width: min(360px, calc(100vw - 32px));
    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.25);
    text-align: center;
    color: var(--text, #2d2d2d);
    position: relative;
}
body.dark .qr-modal { background: #2a2a2e; color: #e8e8e8; }
.qr-modal h3 {
    margin: 0 0 6px 0;
    font-size: 16px;
    font-weight: 600;
}
.qr-modal .qr-hint {
    font-size: 13px;
    color: var(--text-soft, #666);
    margin-bottom: 18px;
}
body.dark .qr-modal .qr-hint { color: #a0a0a0; }
.qr-modal img {
    width: 240px;
    height: 240px;
    display: block;
    margin: 0 auto;
    border-radius: 6px;
    background: #fff;
    padding: 8px;
}
.qr-modal .qr-url {
    margin-top: 16px;
    font-size: 12px;
    color: var(--text-faint, #999);
    word-break: break-all;
    font-family: ui-monospace, "SF Mono", Menlo, monospace;
    background: var(--bg-soft, rgba(0, 0, 0, 0.04));
    border-radius: 6px;
    padding: 8px 10px;
    user-select: all;
}
body.dark .qr-modal .qr-url { background: rgba(255, 255, 255, 0.05); }
.qr-modal .qr-actions {
    margin-top: 16px;
    display: flex;
    gap: 8px;
    justify-content: center;
}
.qr-modal .qr-actions button {
    border: 1px solid var(--border, #e0e0e0);
    background: var(--card-bg, #ffffff);
    color: var(--text, #2d2d2d);
    border-radius: 6px;
    padding: 6px 14px;
    font-size: 13px;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    gap: 4px;
}
body.dark .qr-modal .qr-actions button {
    background: #2a2a2e;
    color: #e8e8e8;
    border-color: #444;
}
.qr-modal .qr-actions button:hover {
    background: var(--accent-soft, rgba(91, 140, 133, 0.1));
    border-color: var(--accent, #5b8c85);
    color: var(--accent, #5b8c85);
}
.qr-modal .qr-actions button.copied {
    background: var(--accent, #5b8c85);
    color: white;
    border-color: var(--accent, #5b8c85);
}
.qr-modal-close {
    position: absolute;
    top: 10px;
    right: 12px;
    background: none;
    border: none;
    font-size: 20px;
    color: var(--text-faint, #999);
    cursor: pointer;
    line-height: 1;
    padding: 4px 8px;
}
.qr-modal-close:hover { color: var(--text, #2d2d2d); }

.resume-toast {
    position: fixed;
    bottom: 24px;
    left: 50%;
    transform: translateX(-50%);
    background: var(--card-bg, #ffffff);
    color: var(--text, #2d2d2d);
    border: 1px solid var(--border, #e0e0e0);
    border-radius: 12px;
    padding: 12px 14px;
    display: flex;
    align-items: center;
    gap: 12px;
    box-shadow: 0 8px 28px rgba(0, 0, 0, 0.12);
    backdrop-filter: blur(12px);
    z-index: 200;
    max-width: 92vw;
    animation: resume-toast-in 0.3s ease-out;
}
@keyframes resume-toast-in {
    from { opacity: 0; transform: translateX(-50%) translateY(20px); }
    to { opacity: 1; transform: translateX(-50%) translateY(0); }
}
body.dark .resume-toast { background: #2a2a2e; border-color: #444; }
.resume-toast-text { display: flex; flex-direction: column; gap: 2px; }
.resume-toast-title { font-size: 13px; font-weight: 500; }
.resume-toast-meta { font-size: 11px; color: var(--text-faint); }
.resume-toast-go {
    background: var(--accent);
    color: white;
    border: none;
    padding: 6px 14px;
    border-radius: 6px;
    font-size: 12px;
    cursor: pointer;
    font-family: inherit;
}
.resume-toast-go:hover { opacity: 0.9; }
.resume-toast-close {
    background: transparent;
    border: none;
    color: var(--text-faint);
    font-size: 16px;
    cursor: pointer;
    line-height: 1;
    padding: 0 4px;
}
.resume-toast-close:hover { color: var(--text); }

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
    content: "";
    display: inline-block;
    width: 14px;
    height: 14px;
    margin-right: 6px;
    vertical-align: -2px;
    background: var(--done);
    -webkit-mask: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='3' stroke-linecap='round' stroke-linejoin='round'><polyline points='20 6 9 17 4 12'/></svg>") center/contain no-repeat;
    mask: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='3' stroke-linecap='round' stroke-linejoin='round'><polyline points='20 6 9 17 4 12'/></svg>") center/contain no-repeat;
}

.book-chapters li a.completed {
    color: var(--text-soft);
    opacity: 0.55;
    text-decoration: line-through;
    text-decoration-color: var(--done);
    text-decoration-thickness: 1.5px;
}

.book-chapters li a.completed::after {
    content: "";
    display: inline-block;
    width: 12px;
    height: 12px;
    margin-left: 6px;
    vertical-align: -1px;
    background: var(--done);
    opacity: 1;
    -webkit-mask: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='3' stroke-linecap='round' stroke-linejoin='round'><polyline points='20 6 9 17 4 12'/></svg>") center/contain no-repeat;
    mask: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='3' stroke-linecap='round' stroke-linejoin='round'><polyline points='20 6 9 17 4 12'/></svg>") center/contain no-repeat;
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

.help-panel {
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
.help-panel.visible { display: flex; }

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

.help-modal {
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 28px;
    width: 90%;
    max-width: 480px;
    max-height: 85vh;
    overflow-y: auto;
    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.2);
}
.help-modal h2 {
    font-size: 1.3em;
    margin: 0 0 20px 0;
    display: flex;
    align-items: center;
    gap: 8px;
}
.help-modal .help-section { margin-bottom: 18px; }
.help-modal .help-section-title {
    color: var(--text-soft);
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    margin-bottom: 6px;
}
.help-modal .help-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 5px 0;
    font-size: 13px;
}
.help-modal .help-row kbd {
    font-family: ui-monospace, "SF Mono", Menlo, monospace;
    font-size: 11px;
    color: var(--text);
    background: var(--bg-soft);
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 2px 8px;
    min-width: 24px;
    text-align: center;
}
body.dark .help-modal .help-row kbd { background: rgba(255, 255, 255, 0.06); }
.help-modal .help-close {
    position: absolute;
    top: 16px;
    right: 16px;
    background: transparent;
    border: none;
    cursor: pointer;
    font-size: 20px;
    color: var(--text-faint);
    line-height: 1;
}
.help-modal .help-close:hover { color: var(--text); }

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

.overall-progress { margin-bottom: 24px; }

.stats-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
    gap: 10px;
    margin-bottom: 28px;
}
.stat-card {
    background: var(--bg-soft);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 14px 16px;
}
.stat-card .stat-value {
    font-size: 22px;
    font-weight: 500;
    color: var(--text);
    font-variant-numeric: tabular-nums;
    line-height: 1.2;
}
.stat-card .stat-value-unit {
    font-size: 13px;
    color: var(--text-soft);
    font-weight: 400;
    margin-left: 2px;
}
.stat-card .stat-label {
    font-size: 10px;
    color: var(--text-soft);
    text-transform: uppercase;
    letter-spacing: 0.6px;
    margin-top: 6px;
}
.stat-card .stat-sub {
    font-size: 11px;
    color: var(--text-faint);
    margin-top: 2px;
}

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

.overall-progress .time-stat {
    color: var(--text-faint);
    font-size: 12px;
    margin-top: 10px;
    font-variant-numeric: tabular-nums;
}
.overall-progress .time-stat strong {
    color: var(--text);
    font-weight: 500;
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

.calendar-chart {
    display: flex;
    flex-direction: column;
}

.calendar-months-row {
    display: flex;
    align-items: flex-end;
    height: 16px;
    margin-bottom: 4px;
}
.calendar-weekday-spacer { width: 28px; flex-shrink: 0; }
.calendar-months {
    position: relative;
    flex: 1;
    height: 16px;
    overflow: hidden;
}
.calendar-months .month-label {
    position: absolute;
    top: 0;
    font-size: 10px;
    color: var(--text-soft);
    white-space: nowrap;
    letter-spacing: 0.5px;
}

.calendar-body-row { display: flex; }

.calendar-weekdays {
    display: grid;
    grid-template-rows: repeat(7, 11px);
    gap: 2px;
    width: 28px;
    flex-shrink: 0;
    margin-right: 6px;
}
.calendar-weekdays .weekday-label {
    font-size: 9px;
    color: var(--text-faint);
    line-height: 11px;
    text-align: right;
    align-self: center;
}
.calendar-weekdays .weekday-label.spacer { visibility: hidden; }

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

.calendar-tooltip {
    position: fixed;
    background: var(--card-bg, #ffffff);
    color: var(--text, #2d2d2d);
    border: 1px solid var(--border, #e0e0e0);
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 12px;
    pointer-events: none;
    z-index: 10000;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
    white-space: nowrap;
    line-height: 1.5;
    opacity: 0;
    transition: opacity 0.1s;
}
body.dark .calendar-tooltip { background: #2a2a2e; color: #e8e8e8; border-color: #444; }
.calendar-tooltip.visible { opacity: 1; }
.calendar-tooltip .tt-date { font-weight: 600; }
.calendar-tooltip .tt-count { color: var(--text-soft, #666); }
body.dark .calendar-tooltip .tt-count { color: #a0a0a0; }

.calendar-recent {
    margin-top: 16px;
    max-height: 320px;
    overflow-y: auto;
    border-top: 1px solid var(--border, #e0e0e0);
    padding-top: 12px;
}
.calendar-recent-title {
    color: var(--text-soft, #666);
    font-size: 12px;
    margin-bottom: 8px;
}
.calendar-recent-month {
    color: var(--text-soft);
    font-size: 11px;
    font-weight: 500;
    padding: 12px 0 4px;
    letter-spacing: 0.5px;
    border-top: 1px dashed var(--border);
}
.calendar-recent-month:first-child {
    border-top: none;
    padding-top: 4px;
}
body.dark .calendar-recent-title { color: #a0a0a0; }
.calendar-recent-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 4px 0;
    font-size: 12px;
    color: var(--text, #2d2d2d);
    border-bottom: 1px dashed var(--border-soft, #eee);
}
body.dark .calendar-recent-item { color: #e8e8e8; border-color: #333; }
.calendar-recent-item:last-child { border-bottom: none; }
.calendar-recent-item .ri-date { font-family: ui-monospace, "SF Mono", Menlo, monospace; }
.calendar-recent-item .ri-weekday { color: var(--text-faint, #999); margin-left: 8px; font-size: 11px; }
.calendar-recent-item .ri-count {
    color: var(--accent, #b08968);
    font-weight: 600;
}
.calendar-recent-empty { color: var(--text-faint, #999); font-size: 12px; padding: 8px 0; }

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

.command-filters {
    display: flex;
    gap: 6px;
    padding: 10px 16px 8px;
    flex-wrap: wrap;
}
.command-chip {
    border: 1px solid var(--border);
    background: transparent;
    color: var(--text-soft);
    font-family: inherit;
    font-size: 11px;
    padding: 3px 10px;
    border-radius: 12px;
    cursor: pointer;
    transition: all 0.15s;
}
.command-chip:hover {
    border-color: var(--accent);
    color: var(--accent);
}
.command-chip.active {
    background: var(--accent);
    color: white;
    border-color: var(--accent);
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

mark.search-highlight {
    background: rgba(255, 235, 100, 0.5);
    color: inherit;
    padding: 0;
    border-radius: 2px;
}
mark.search-highlight.search-highlight-active {
    background: rgba(255, 200, 50, 0.85);
    box-shadow: 0 0 0 3px rgba(255, 200, 50, 0.4);
    animation: search-pulse 2s ease-out;
}
@keyframes search-pulse {
    0% { box-shadow: 0 0 0 8px rgba(255, 200, 50, 0.9); }
    100% { box-shadow: 0 0 0 3px rgba(255, 200, 50, 0.4); }
}

.match-indicator {
    position: fixed;
    top: 80px;
    right: 24px;
    background: var(--card-bg, #fff);
    color: var(--text, #2d2d2d);
    border: 1px solid var(--border, #e0e0e0);
    border-radius: 24px;
    padding: 6px 6px 6px 16px;
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 13px;
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.1);
    z-index: 200;
    backdrop-filter: blur(8px);
}
.match-indicator button {
    border: none;
    background: transparent;
    color: var(--text-soft);
    cursor: pointer;
    width: 28px;
    height: 28px;
    border-radius: 50%;
    font-size: 14px;
    line-height: 1;
}
.match-indicator button:hover {
    background: var(--accent-soft);
    color: var(--accent);
}
.match-indicator .match-close {
    background: transparent;
    color: var(--text-faint);
}
body.dark .match-indicator { background: #2a2a2e; border-color: #444; }

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

// === QR 扫码弹窗 ===
const qrModal = document.getElementById('qr-modal');
const qrBtn = document.getElementById('qr-btn');
const qrClose = document.getElementById('qr-modal-close');
const qrCopyBtn = document.getElementById('qr-copy-btn');
const qrUrl = document.getElementById('qr-url');

function openQr() {
    qrModal.classList.add('visible');
}
function closeQr() {
    qrModal.classList.remove('visible');
    qrCopyBtn.classList.remove('copied');
    qrCopyBtn.innerHTML = qrCopyBtn.dataset.originalHtml || qrCopyBtn.innerHTML;
}

if (qrBtn) qrBtn.addEventListener('click', openQr);
if (qrClose) qrClose.addEventListener('click', closeQr);
qrModal.addEventListener('click', (e) => { if (e.target === qrModal) closeQr(); });

if (qrCopyBtn) {
    qrCopyBtn.dataset.originalHtml = qrCopyBtn.innerHTML;
    qrCopyBtn.addEventListener('click', async () => {
        const url = qrUrl.textContent.trim();
        try {
            await navigator.clipboard.writeText(url);
        } catch (e) {
            // fallback for older browsers / non-https
            const ta = document.createElement('textarea');
            ta.value = url;
            document.body.appendChild(ta);
            ta.select();
            try { document.execCommand('copy'); } catch (e2) {}
            document.body.removeChild(ta);
        }
        qrCopyBtn.classList.add('copied');
        qrCopyBtn.innerHTML = '<svg class="icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg> 已复制';
        setTimeout(() => {
            qrCopyBtn.classList.remove('copied');
            qrCopyBtn.innerHTML = qrCopyBtn.dataset.originalHtml;
        }, 1500);
    });
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

    if (scene === 'woju') {
        // 真实录音：用 <audio> 元素 + WebAudio GainNode 控制音量
        const audioEl = document.getElementById('woju-audio');
        if (!audioEl || !audioEl.querySelector('source, [src]') && !audioEl.src) {
            console.log('woju scene: audio file not found, fallback to off');
            return;
        }
        const source = ctx.createMediaElementSource(audioEl);
        source.connect(mainGain);
        audioEl.volume = volume;
        audioEl.currentTime = 0;
        audioEl.play().catch(e => console.log('audio play failed:', e));
        musicNodes = { source: audioEl, gain: mainGain, isAudio: true };
    }
    localStorage.setItem('musicScene', scene);
}

function stopMusic() {
    if (!musicNodes) return;
    try {
        if (musicNodes.isAudio) {
            musicNodes.source.pause();
            musicNodes.source.currentTime = 0;
        } else if (musicNodes.source.stop) {
            musicNodes.source.stop();
        }
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
    if (musicNodes) {
        if (musicNodes.isAudio) {
            musicNodes.source.volume = volume;
        } else {
            musicNodes.gain.gain.value = volume;
        }
    }
    localStorage.setItem('volume', volume);
});

document.querySelector('.volume input').value = volume * 100;
// 进入页面：默认开背景音（首次访问/之前选过 woju 都自动开；只有用户明确选过「静音」才不开）
const savedScene = localStorage.getItem('musicScene') || 'woju';
if (savedScene !== 'off') {
    startMusic(savedScene);
    // 浏览器 autoplay policy：play() 可能被静默拦截
    // 兜底：监听首次用户交互，resume audioCtx + 再 play 一次
    if (musicNodes && musicNodes.isAudio && musicNodes.source.paused) {
        const handler = () => {
            if (audioCtx && audioCtx.state === 'suspended') {
                audioCtx.resume().catch(() => {});
            }
            if (musicNodes && musicNodes.isAudio) {
                musicNodes.source.play().catch(() => {});
            }
        };
        document.addEventListener('click', handler, { once: true });
        document.addEventListener('keydown', handler, { once: true });
    }
    document.querySelectorAll('.scene-btn').forEach(b => b.classList.toggle('active', b.dataset.scene === savedScene));
} else {
    document.querySelector('.scene-btn[data-scene="off"]').classList.add('active');
}

// 检查 woju 录音文件是否存在，不存在则隐藏按钮（部署到 GitHub Pages 时不会带 mp3）
fetch('assets/audio/woju_low.mp3', { method: 'HEAD' }).then(r => {
    if (!r.ok) {
        const btn = document.querySelector('.scene-btn[data-scene="woju"]');
        if (btn) btn.style.display = 'none';
        // 如果之前选的是 woju，重置为 off
        if (localStorage.getItem('musicScene') === 'woju') {
            localStorage.setItem('musicScene', 'off');
        }
    }
}).catch(() => {
    // 网络错误也隐藏
    const btn = document.querySelector('.scene-btn[data-scene="woju"]');
    if (btn) btn.style.display = 'none';
});

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

// ============================================================
// 段落书签（localStorage 'bookmarks'）
// 结构：{ [chapterId]: [{text, timestamp, idx}, ...] }
// ============================================================
let bookmarks = JSON.parse(localStorage.getItem('bookmarks') || '{}');

function saveBookmarks() {
    localStorage.setItem('bookmarks', JSON.stringify(bookmarks));
}

function addBookmark(info) {
    if (!bookmarks[info.chapterId]) bookmarks[info.chapterId] = [];
    bookmarks[info.chapterId].push({
        text: info.text,
        timestamp: Date.now(),
    });
    saveBookmarks();
    renderBookmarksList();
}

function deleteBookmark(chapterId, idx) {
    if (bookmarks[chapterId]) {
        bookmarks[chapterId].splice(idx, 1);
        if (bookmarks[chapterId].length === 0) delete bookmarks[chapterId];
        saveBookmarks();
        renderBookmarksList();
    }
}

document.querySelector('.selection-toolbar .bookmark-btn').addEventListener('click', () => {
    const info = getSelectionInfo();
    if (!info) return;
    addBookmark(info);
    hideSelectionToolbar();
    window.getSelection().removeAllRanges();
});

function renderBookmarksList() {
    const container = document.getElementById('sidebar-bookmarks');
    if (!container) return;

    const allBookmarks = [];
    for (const [chapterId, list] of Object.entries(bookmarks)) {
        list.forEach((bm, idx) => {
            allBookmarks.push({ chapterId, idx, ...bm });
        });
    }
    // 按 timestamp 倒序
    allBookmarks.sort((a, b) => b.timestamp - a.timestamp);

    const total = allBookmarks.length;
    let html = `<div class="sb-title"><span>书签</span><span class="sb-count">${total}</span></div>`;

    if (total === 0) {
        html += `<div class="sb-empty">选中文本 → 工具栏 → 收藏</div>`;
        container.innerHTML = html;
        return;
    }

    // 最近 8 条
    const recent = allBookmarks.slice(0, 8);
    recent.forEach(bm => {
        const article = document.getElementById(bm.chapterId);
        const chapTitle = article?.querySelector('.chapter-title')?.textContent || bm.chapterId;
        const text = bm.text.length > 80 ? bm.text.slice(0, 80) + '…' : bm.text;
        html += `
            <div class="sb-item" data-chapter="${bm.chapterId}" data-idx="${bm.idx}">
                <button class="sb-delete" title="删除">×</button>
                <div class="sb-chapter">${chapTitle}</div>
                <div class="sb-text">${text}</div>
            </div>
        `;
    });
    container.innerHTML = html;

    container.querySelectorAll('.sb-item').forEach(item => {
        const chapterId = item.dataset.chapter;
        const idx = parseInt(item.dataset.idx);
        item.addEventListener('click', (e) => {
            if (e.target.classList.contains('sb-delete')) return;
            jumpToBookmark(chapterId, idx);
        });
        item.querySelector('.sb-delete').addEventListener('click', (e) => {
            e.stopPropagation();
            deleteBookmark(chapterId, idx);
        });
    });
}

function jumpToBookmark(chapterId, idx) {
    const article = document.getElementById(chapterId);
    if (!article) return;
    article.scrollIntoView({ behavior: 'smooth', block: 'start' });
    history.pushState(null, '', '#' + chapterId);
    const bm = bookmarks[chapterId]?.[idx];
    if (!bm) return;
    clearSearchHighlights();
    const content = article.querySelector('.chapter-content');
    if (!content) return;
    highlightAllMatches(content, bm.text);
    if (searchMatches.length > 0) {
        searchMatches[0].classList.add('search-highlight-active');
        searchMatches[0].scrollIntoView({ behavior: 'smooth', block: 'center' });
        setTimeout(() => clearSearchHighlights(), 4000);
    }
}

renderBookmarksList();

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
        list.innerHTML = '<div class="notes-empty">还没有笔记<br><br>选中正文中的文字后<br>点击弹出的浮动工具栏添加</div>';
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

    if (e.key === '?' || (e.shiftKey && e.key === '/')) {
        e.preventDefault();
        document.querySelector('.help-panel').classList.add('visible');
        return;
    }
    if (e.key === 'f' || e.key === 'F') {
        e.preventDefault();
        toggleFocusMode();
        return;
    }
    if (e.key === 'g' || e.key === 'G') {
        // 简单实现：单按 g 跳顶，连按 g 跳底（500ms 内）
        if (!window._lastG) window._lastG = 0;
        const now = Date.now();
        if (now - window._lastG < 500) {
            // 第二次 g → 跳到底
            window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' });
            window._lastG = 0;
            return;
        }
        // 单按 g → 跳顶
        window.scrollTo({ top: 0, behavior: 'smooth' });
        window._lastG = now;
        return;
    }

    if (e.key === 'd' || e.key === 'D') toggleDark();
    if (e.key === 's' || e.key === 'S') document.getElementById('sidebar-toggle').click();
    if (e.key === 'm' || e.key === 'M') document.getElementById('music-btn').click();
    if (e.key === 'n' || e.key === 'N') document.getElementById('notes-btn').click();
    if (e.key === 'p' || e.key === 'P') document.getElementById('progress-btn').click();
    if (e.key === 'q' || e.key === 'Q') document.getElementById('qr-btn').click();
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
        document.querySelector('.help-panel').classList.remove('visible');
        document.querySelector('.music-panel').classList.remove('visible');
        document.querySelector('.notes-panel').classList.remove('visible');
        document.querySelector('.note-modal').classList.remove('visible');
        document.querySelector('.progress-panel').classList.remove('visible');
        document.getElementById('toolbar-menu').classList.remove('visible');
        document.getElementById('more-btn').classList.remove('open');
    }
});

// ============================================================
// 工具栏溢出菜单
// ============================================================
const moreBtn = document.getElementById('more-btn');
const toolbarMenu = document.getElementById('toolbar-menu');

function setToolbarOpen(open) {
    toolbarMenu.classList.toggle('visible', open);
    moreBtn.classList.toggle('open', open);
}

moreBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    setToolbarOpen(!toolbarMenu.classList.contains('visible'));
});

// 点菜单外面关闭
document.addEventListener('click', (e) => {
    if (!toolbarMenu.contains(e.target) && !moreBtn.contains(e.target)) {
        setToolbarOpen(false);
    }
});

// 点了任何工具按钮后关闭（音乐/笔记/进度/QR/暗色/字号）
toolbarMenu.querySelectorAll('button').forEach(btn => {
    btn.addEventListener('click', () => setToolbarOpen(false));
});

// 帮助面板：X 按钮 + 点击 backdrop 关闭
const helpPanel = document.querySelector('.help-panel');
document.getElementById('help-close').addEventListener('click', () => {
    helpPanel.classList.remove('visible');
});
helpPanel.addEventListener('click', (e) => {
    if (e.target === helpPanel) helpPanel.classList.remove('visible');
});

// ============================================================
// 进度统计
// ============================================================
let progress = JSON.parse(localStorage.getItem('progress') || '{}');
if (!progress.completed) progress = { completed: {} };
if (!progress.timeSpent) progress.timeSpent = {};
if (!progress.readPct) progress.readPct = {};
if (!progress.dailyTime) progress.dailyTime = {};
if (!progress.lastRead) progress.lastRead = null;

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
        btn.innerHTML = isCompleted
            ? '<svg class="icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-2px;margin-right:4px"><polyline points="20 6 9 17 4 12"/></svg>已读 (点击撤销)'
            : '<svg class="icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-2px;margin-right:4px"><rect x="3" y="3" width="18" height="18" rx="2"/></svg>标记为已读';
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

function refreshReadPctUI() {
    document.querySelectorAll('.ch-read-pct').forEach(el => {
        const id = el.dataset.chapter;
        const pct = progress.readPct[id] || 0;
        const isCompleted = !!progress.completed[id];
        if (isCompleted) {
            el.innerHTML = '<svg class="icon" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>';
        } else if (pct > 0 && pct < 100) {
            el.textContent = pct + '%';
        } else {
            el.textContent = '';
        }
    });
}

document.querySelectorAll('.completion-toggle').forEach(btn => {
    btn.addEventListener('click', () => toggleChapter(btn.dataset.chapter));
});

// ============================================================
// 自动标记：滚到「本章完」+ 停留 5 秒 → 自动标为已读
// 手动按钮仍可 toggle / 撤销
// 5s 内滚走 → 计时清零，不会误标
// 已标章节不重复标；手动撤销后滚走再回 5s → 重新自动标
// ============================================================
const autoMarkTimers = new WeakMap(); // chapterEndEl -> timerId

function setupAutoMark() {
    document.querySelectorAll('.chapter-end').forEach(endEl => {
        const article = endEl.closest('.chapter');
        if (!article || !article.id) return;
        const chapterId = article.id;
        const originalText = endEl.textContent;

        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    if (progress.completed[chapterId]) return;
                    if (autoMarkTimers.has(endEl)) return;
                    const timer = setTimeout(() => {
                        if (!progress.completed[chapterId]) {
                            progress.completed[chapterId] = Date.now();
                            saveProgress();
                            refreshCompletionUI();
                        }
                        endEl.textContent = originalText;
                        autoMarkTimers.delete(endEl);
                    }, 5000);
                    autoMarkTimers.set(endEl, timer);
                    endEl.textContent = originalText + ' · 5秒后自动标记已读';
                } else {
                    const timer = autoMarkTimers.get(endEl);
                    if (timer) {
                        clearTimeout(timer);
                        autoMarkTimers.delete(endEl);
                        endEl.textContent = originalText;
                    }
                }
            });
        }, { threshold: 0 });

        observer.observe(endEl);
    });
}

setupAutoMark();

// ============================================================
// 阅读时长 + 章节滚动百分比追踪
// 两者都靠 IntersectionObserver 监听每章可见性：
//   - 章入视 50% → 开始计时
//   - 章离视    → 累加 elapsed 到 timeSpent[chapterId]
//   - 滚动事件：每章计算「已滚过的比例」，保存最大值到 readPct[chapterId]
// ============================================================
let readTimerStart = null;
let readTimerChapter = null;

function setupReadingTracker() {
    document.querySelectorAll('.chapter').forEach(article => {
        const chapterId = article.id;
        const io = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.intersectionRatio >= 0.5) {
                    if (readTimerChapter && readTimerChapter !== chapterId) {
                        commitReadTime();
                    }
                    if (chapterId !== readTimerChapter) {
                        readTimerStart = Date.now();
                        readTimerChapter = chapterId;
                    }
                } else if (readTimerChapter === chapterId) {
                    commitReadTime();
                }
            });
        }, { threshold: [0, 0.5, 1] });
        io.observe(article);
    });
}

function commitReadTime() {
    if (!readTimerStart || !readTimerChapter) return;
    const elapsed = Math.floor((Date.now() - readTimerStart) / 1000);
    if (elapsed >= 1) {
        progress.timeSpent[readTimerChapter] = (progress.timeSpent[readTimerChapter] || 0) + elapsed;
        const todayKey = localDateKey(new Date());
        progress.dailyTime[todayKey] = (progress.dailyTime[todayKey] || 0) + elapsed;
        saveProgress();
    }
    readTimerStart = null;
    readTimerChapter = null;
}

// 关闭/切走时落盘
window.addEventListener('beforeunload', commitReadTime);
document.addEventListener('visibilitychange', () => {
    if (document.hidden) commitReadTime();
});

// 滚动事件：每章计算「已滚过」最大百分比
let scrollSaveTimer = null;
function updateReadPct() {
    const winH = window.innerHeight;
    document.querySelectorAll('.chapter').forEach(article => {
        const rect = article.getBoundingClientRect();
        if (rect.height === 0) return;
        let pct;
        if (rect.bottom <= winH) {
            pct = 100;
        } else if (rect.top >= winH) {
            pct = 0;
        } else {
            pct = Math.round(((winH - rect.top) / rect.height) * 100);
            pct = Math.max(0, Math.min(100, pct));
        }
        if (pct > (progress.readPct[article.id] || 0)) {
            progress.readPct[article.id] = pct;
        }
    });
    refreshReadPctUI();
    // 记录当前阅读位置（chapterId + scrollY）
    const inView = document.querySelector('.chapter');
    if (inView) {
        const top = inView.getBoundingClientRect().top;
        if (top < window.innerHeight && top > -inView.offsetHeight) {
            progress.lastRead = {
                chapterId: inView.id,
                scrollY: window.scrollY,
                timestamp: Date.now(),
            };
            saveProgress();
        }
    }
    if (scrollSaveTimer) clearTimeout(scrollSaveTimer);
    scrollSaveTimer = setTimeout(() => saveProgress(), 200);
}
window.addEventListener('scroll', updateReadPct, { passive: true });

setupReadingTracker();
updateReadPct();
refreshReadPctUI();

// Continue reading toast：页面加载时检查 lastRead，弹小提示
function showResumeToast() {
    const last = progress.lastRead;
    if (!last || !last.chapterId) return;
    const article = document.getElementById(last.chapterId);
    if (!article) return;
    // 已经在该章节就不弹
    if (window.location.hash === '#' + last.chapterId) return;
    if (window.scrollY > 0) return;  // 用户已经在滚动了，不打扰
    // 距离上次 < 5 分钟不打扰（说明是连续阅读）
    if (Date.now() - last.timestamp < 5 * 60 * 1000) return;

    const title = article.querySelector('.chapter-title')?.textContent || last.chapterId;
    const ago = formatRelativeTime(last.timestamp);
    const toast = document.createElement('div');
    toast.className = 'resume-toast';
    toast.innerHTML = `
        <div class="resume-toast-text">
            <div class="resume-toast-title">继续读：${escapeHtml(title)}</div>
            <div class="resume-toast-meta">上次阅读：${ago}</div>
        </div>
        <button class="resume-toast-go">继续</button>
        <button class="resume-toast-close">×</button>
    `;
    document.body.appendChild(toast);

    toast.querySelector('.resume-toast-go').addEventListener('click', () => {
        article.scrollIntoView({ behavior: 'smooth', block: 'start' });
        window.scrollTo({ top: last.scrollY, behavior: 'smooth' });
        history.pushState(null, '', '#' + last.chapterId);
        toast.remove();
    });
    toast.querySelector('.resume-toast-close').addEventListener('click', () => toast.remove());

    // 12 秒自动消失
    setTimeout(() => toast.remove(), 12000);
}

function formatRelativeTime(ts) {
    const diff = Date.now() - ts;
    const min = Math.floor(diff / 60000);
    if (min < 60) return `${min} 分钟前`;
    const hr = Math.floor(min / 60);
    if (hr < 24) return `${hr} 小时前`;
    const day = Math.floor(hr / 24);
    if (day < 30) return `${day} 天前`;
    return new Date(ts).toLocaleDateString('zh-CN');
}

function escapeHtml(s) {
    return s.replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
}

showResumeToast();

// Focus mode 切换
function toggleFocusMode() {
    document.body.classList.toggle('focus-mode');
}
document.getElementById('focus-exit').addEventListener('click', toggleFocusMode);

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
    const allChapters = Array.from(document.querySelectorAll('.chapter')).map(c => {
        const bookEl = document.querySelector(`[data-book="${c.dataset.book}"] .book-title-text`);
        return {
            id: c.id,
            book: c.dataset.book,
            bookTitle: bookEl?.textContent || c.dataset.book,
        };
    });

    // 按书分组
    const bookStats = {};
    allChapters.forEach(c => {
        if (!bookStats[c.book]) {
            bookStats[c.book] = { title: c.bookTitle, total: 0, completed: 0 };
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

    // 累计阅读时长
    const totalSeconds = Object.values(progress.timeSpent).reduce((a, b) => a + (b || 0), 0);
    const timeStatEl = document.getElementById('time-stat');
    if (totalSeconds === 0) {
        timeStatEl.innerHTML = '还没开始记录阅读时长';
    } else {
        const hours = Math.floor(totalSeconds / 3600);
        const mins = Math.floor((totalSeconds % 3600) / 60);
        timeStatEl.innerHTML = `总阅读 <strong>${hours > 0 ? hours + ' 小时 ' : ''}${mins} 分</strong>`;
    }

    // 4 张统计卡片
    // 最长连续（按 progress.completed 的日期算）
    const completedDates = Object.values(progress.completed)
        .map(ts => localDateKey(new Date(ts)))
        .sort();
    const uniqueDates = [...new Set(completedDates)];
    let longestStreak = 0, curStreak = 0, prevDate = null;
    for (const dk of uniqueDates) {
        if (prevDate === null) {
            curStreak = 1;
        } else {
            const diff = Math.round((new Date(dk) - new Date(prevDate)) / 86400000);
            curStreak = (diff === 1) ? curStreak + 1 : 1;
        }
        longestStreak = Math.max(longestStreak, curStreak);
        prevDate = dk;
    }
    // 今日阅读（来自 progress.dailyTime）
    const todayKey = localDateKey(new Date());
    const todaySeconds = progress.dailyTime[todayKey] || 0;
    // 平均每次 = 总时长 / 阅读天数
    const daysWithReading = Math.max(uniqueDates.length, 1);
    const avgSeconds = Math.round(totalSeconds / daysWithReading);

    document.getElementById('stat-streak').textContent = longestStreak;
    document.getElementById('stat-today').textContent = Math.round(todaySeconds / 60);
    document.getElementById('stat-avg').textContent = Math.round(avgSeconds / 60);
    document.getElementById('stat-days').textContent = uniqueDates.length;

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

function weekdayName(date) {
    const weekdays = ['周日', '周一', '周二', '周三', '周四', '周五', '周六'];
    return weekdays[date.getDay()];
}

// 本地日期 key（YYYY-MM-DD），避开 toISOString 的 UTC 时区陷阱
function localDateKey(d) {
    return d.getFullYear() + '-' +
        String(d.getMonth() + 1).padStart(2, '0') + '-' +
        String(d.getDate()).padStart(2, '0');
}

function renderCalendar() {
    const monthsEl = document.getElementById('calendar-months');
    const weekdaysEl = document.getElementById('calendar-weekdays');
    const grid = document.getElementById('calendar-grid');
    const tooltip = document.getElementById('calendar-tooltip');
    const recent = document.getElementById('calendar-recent');
    monthsEl.innerHTML = '';
    weekdaysEl.innerHTML = '';
    grid.innerHTML = '';

    // weekday 标签（只显 Mon/Wed/Fri —— GitHub 风格，省空间）
    const weekdayLabels = ['周日', '周一', '周二', '周三', '周四', '周五', '周六'];
    const visibleIdx = new Set([1, 3, 5]);
    for (let i = 0; i < 7; i++) {
        const lbl = document.createElement('div');
        lbl.className = 'weekday-label' + (visibleIdx.has(i) ? '' : ' spacer');
        lbl.textContent = weekdayLabels[i];
        weekdaysEl.appendChild(lbl);
    }

    // 每天的完成数（本地日期，避免 UTC 跨日错位）
    const daily = {};
    Object.values(progress.completed).forEach(ts => {
        const date = localDateKey(new Date(ts));
        daily[date] = (daily[date] || 0) + 1;
    });

    // 当年 1/1 至今
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const startDate = new Date(today.getFullYear(), 0, 1);

    // 调整到最近的周日
    let currentDate = new Date(startDate);
    currentDate.setDate(currentDate.getDate() - currentDate.getDay());

    // 月份首次出现的列索引（用于顶部月份标签定位）
    const monthStartCol = {};
    const monthNames = ['1月', '2月', '3月', '4月', '5月', '6月', '7月', '8月', '9月', '10月', '11月', '12月'];
    const STRIDE = 11 + 2; // 单元格宽 + 列间隙

    while (currentDate <= today) {
        const week = document.createElement('div');
        week.className = 'calendar-week';

        for (let i = 0; i < 7; i++) {
            const day = document.createElement('div');
            day.className = 'calendar-day';

            // 记录本月首次出现的列（仅当年内的日期）
            if (currentDate >= startDate && currentDate <= today) {
                const m = currentDate.getMonth();
                if (monthStartCol[m] === undefined) {
                    monthStartCol[m] = grid.children.length;
                }
            }

            if (currentDate > today || currentDate < startDate) {
                day.classList.add('empty');
            } else {
                const dateKey = localDateKey(currentDate);
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

                // 自定义 tooltip（不用 native title，体验差）
                day.addEventListener('mouseenter', (e) => {
                    tooltip.innerHTML = `<span class="tt-date">${dateKey}</span> · ${weekdayName(currentDate)}<br><span class="tt-count">${count === 0 ? '未阅读' : count + ' 章'}</span>`;
                    tooltip.classList.add('visible');
                });
                day.addEventListener('mousemove', (e) => {
                    tooltip.style.left = (e.clientX + 12) + 'px';
                    tooltip.style.top = (e.clientY + 12) + 'px';
                });
                day.addEventListener('mouseleave', () => {
                    tooltip.classList.remove('visible');
                });
            }

            week.appendChild(day);
            currentDate.setDate(currentDate.getDate() + 1);
        }

        grid.appendChild(week);
    }

    // 渲染顶部月份标签（用 left = 列索引 × 步长 定位到对应列上方）
    Object.keys(monthStartCol).sort((a, b) => parseInt(a) - parseInt(b)).forEach(m => {
        const lbl = document.createElement('span');
        lbl.className = 'month-label';
        lbl.textContent = monthNames[parseInt(m)];
        lbl.style.left = (monthStartCol[m] * STRIDE) + 'px';
        monthsEl.appendChild(lbl);
    });

    // 完整阅读历史：所有有记录的日期，按日期倒序，按月分组
    const todayKey = localDateKey(today);
    const historyDays = Object.entries(daily)
        .filter(([k, c]) => c > 0)
        .map(([key, count]) => ({ key, count, date: new Date(key) }))
        .sort((a, b) => b.key.localeCompare(a.key));

    if (historyDays.length === 0) {
        recent.innerHTML = '<div class="calendar-recent-title">完整阅读历史</div><div class="calendar-recent-empty">还没有阅读记录。读一章试试。</div>';
    } else {
        recent.innerHTML = `<div class="calendar-recent-title">完整阅读历史 · ${historyDays.length} 天</div>`;
        let lastYM = '';
        historyDays.forEach(({ key, count, date }) => {
            const ym = key.slice(0, 7);
            if (ym !== lastYM) {
                const monthHeader = document.createElement('div');
                monthHeader.className = 'calendar-recent-month';
                monthHeader.textContent = `${date.getFullYear()} 年 ${date.getMonth() + 1} 月`;
                recent.appendChild(monthHeader);
                lastYM = ym;
            }
            const item = document.createElement('div');
            item.className = 'calendar-recent-item';
            const todayFlag = key === todayKey ? ' · 今天' : '';
            item.innerHTML = `
                <div>
                    <span class="ri-date">${key}</span>
                    <span class="ri-weekday">${weekdayName(date)}${todayFlag}</span>
                </div>
                <span class="ri-count">${count} 章</span>
            `;
            recent.appendChild(item);
        });
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

// 导出笔记 + 书签为 Markdown
document.getElementById('export-notes-md').addEventListener('click', () => {
    const md = buildNotesMarkdown(notes, bookmarks);
    const blob = new Blob([md], { type: 'text/markdown;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `knowledge-garden-notes-${new Date().toISOString().slice(0, 10)}.md`;
    a.click();
    URL.revokeObjectURL(url);
});

function getChapterMeta(chapterId) {
    const article = document.getElementById(chapterId);
    if (!article) return { title: chapterId, book: '' };
    return {
        title: article.querySelector('.chapter-title')?.textContent.trim() || chapterId,
        book: article.dataset.book || '',
    };
}

function buildNotesMarkdown(notesArr, bookmarksObj) {
    const lines = [];
    const today = new Date().toLocaleDateString('zh-CN');
    lines.push('# 知识花园 · 笔记导出');
    lines.push('');
    lines.push(`导出日期：${today}`);
    lines.push('');

    // 按章节分组
    const grouped = new Map();
    notesArr.forEach(note => {
        if (!grouped.has(note.chapterId)) grouped.set(note.chapterId, { notes: [], bookmarks: [] });
        grouped.get(note.chapterId).notes.push(note);
    });
    for (const [chapterId, list] of Object.entries(bookmarksObj)) {
        if (!grouped.has(chapterId)) grouped.set(chapterId, { notes: [], bookmarks: [] });
        list.forEach(bm => grouped.get(chapterId).bookmarks.push(bm));
    }

    if (grouped.size === 0) {
        lines.push('_暂无笔记或书签_');
        return lines.join('\\n');
    }

    grouped.forEach((data, chapterId) => {
        const meta = getChapterMeta(chapterId);
        lines.push(`## ${meta.title}`);
        if (meta.book) {
            const bookEl = document.querySelector(`[data-book="${meta.book}"] .book-title-text`);
            const bookTitle = bookEl?.textContent || meta.book;
            lines.push(`_${bookTitle}_`);
        }
        lines.push('');

        if (data.bookmarks.length > 0) {
            lines.push('### 书签');
            data.bookmarks.forEach((bm, i) => {
                const dt = new Date(bm.timestamp).toLocaleString('zh-CN');
                lines.push(`${i + 1}. ${dt}`);
                lines.push(`   > ${bm.text.replace(/\\n/g, '\\n   > ')}`);
                lines.push('');
            });
        }

        if (data.notes.length > 0) {
            lines.push('### 高亮与笔记');
            data.notes.forEach((note, i) => {
                const dt = new Date(note.timestamp).toLocaleString('zh-CN');
                lines.push(`${i + 1}. ${dt} · ${note.type === 'highlight' ? '高亮' : '笔记'}`);
                if (note.quote || note.text) {
                    const q = (note.quote || '').replace(/\\n/g, '\\n   > ');
                    lines.push(`   > ${q}`);
                }
                if (note.type === 'note' && note.text) {
                    lines.push('');
                    lines.push(`   ${note.text}`);
                }
                lines.push('');
            });
        }
        lines.push('---');
        lines.push('');
    });

    return lines.join('\\n');
}

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
                    alert('数据导入成功');
                }
            } catch (err) {
                alert('错误：文件格式不正确 - ' + err.message);
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
let activeFilter = 'all';

// chip 点击切换
document.querySelectorAll('.command-chip').forEach(chip => {
    chip.addEventListener('click', () => {
        document.querySelectorAll('.command-chip').forEach(c => c.classList.remove('active'));
        chip.classList.add('active');
        activeFilter = chip.dataset.filter;
        performSearch(commandInput.value.trim());
    });
});

function highlightSnippet(text, query, len = 100) {
    const lower = text.toLowerCase();
    const idx = lower.indexOf(query);
    if (idx < 0) return text.slice(0, len) + (text.length > len ? '…' : '');

    const start = Math.max(0, idx - 30);
    const end = Math.min(text.length, idx + query.length + len - 30);
    let snippet = text.slice(start, end);
    if (start > 0) snippet = '…' + snippet;
    if (end < text.length) snippet = snippet + '…';

    // 用 split + join 高亮（不依赖 regex，避免转义问题）
    return snippet.split(query).join('<mark>' + query + '</mark>');
}

function performSearch(query) {
    commandResults.innerHTML = '';
    activeCommandIdx = -1;

    if (!query) return;

    const q = query.toLowerCase();
    const results = [];

    for (const item of searchIndex) {
        if (activeFilter !== 'all' && item.book !== activeFilter) continue;
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
        item.addEventListener('click', () => jumpToCommand(item.dataset.chapter, q));
        item.addEventListener('mouseenter', () => {
            commandResults.querySelectorAll('.command-item').forEach(el => el.classList.remove('active'));
            item.classList.add('active');
            activeCommandIdx = parseInt(item.dataset.idx);
        });
    });

    activeCommandIdx = 0;
    commandResults.querySelector('.command-item')?.classList.add('active');
}

let searchMatches = [];   // 当前章节高亮的 mark 列表
let activeMatchIdx = -1;  // 当前激活的（第几个）

function clearSearchHighlights() {
    document.querySelectorAll('mark.search-highlight').forEach(el => {
        const text = el.textContent;
        el.replaceWith(document.createTextNode(text));
    });
    searchMatches = [];
    activeMatchIdx = -1;
}

function highlightAllMatches(contentEl, searchTerm) {
    const term = searchTerm.toLowerCase();
    const walker = document.createTreeWalker(contentEl, NodeFilter.SHOW_TEXT);
    const textNodes = [];
    let n;
    while ((n = walker.nextNode())) textNodes.push(n);

    for (const textNode of textNodes) {
        const text = textNode.textContent;
        const lower = text.toLowerCase();
        if (!lower.includes(term)) continue;

        const fragment = document.createDocumentFragment();
        let lastIdx = 0;
        let idx;
        while ((idx = lower.indexOf(term, lastIdx)) >= 0) {
            if (idx > lastIdx) {
                fragment.appendChild(document.createTextNode(text.slice(lastIdx, idx)));
            }
            const mark = document.createElement('mark');
            mark.className = 'search-highlight';
            mark.textContent = text.slice(idx, idx + term.length);
            fragment.appendChild(mark);
            lastIdx = idx + term.length;
        }
        if (lastIdx < text.length) {
            fragment.appendChild(document.createTextNode(text.slice(lastIdx)));
        }
        textNode.parentNode.replaceChild(fragment, textNode);
    }
    searchMatches = Array.from(contentEl.querySelectorAll('mark.search-highlight'));
}

function jumpToMatch(direction) {
    if (searchMatches.length === 0) return;
    searchMatches[activeMatchIdx]?.classList.remove('search-highlight-active');
    if (direction === 'next') {
        activeMatchIdx = (activeMatchIdx + 1) % searchMatches.length;
    } else {
        activeMatchIdx = (activeMatchIdx - 1 + searchMatches.length) % searchMatches.length;
    }
    searchMatches[activeMatchIdx].classList.add('search-highlight-active');
    searchMatches[activeMatchIdx].scrollIntoView({ behavior: 'smooth', block: 'center' });
}

function jumpToCommand(chapterId, query) {
    commandPalette.classList.remove('visible');
    const searchTerm = query || commandInput.value;
    commandInput.value = '';

    clearSearchHighlights();

    const target = document.getElementById(chapterId);
    if (!target) return;
    history.pushState(null, '', '#' + chapterId);

    if (searchTerm) {
        const content = target.querySelector('.chapter-content');
        if (content) {
            highlightAllMatches(content, searchTerm);
            if (searchMatches.length > 0) {
                activeMatchIdx = 0;
                searchMatches[0].classList.add('search-highlight-active');
                searchMatches[0].scrollIntoView({ behavior: 'smooth', block: 'center' });
                // 显示匹配数（如果 >1）
                if (searchMatches.length > 1) {
                    showMatchIndicator(searchMatches.length);
                }
            } else {
                target.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
        }
    } else {
        target.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
}

function showMatchIndicator(count) {
    const ind = document.createElement('div');
    ind.className = 'match-indicator';
    ind.innerHTML = `
        <span>找到 <strong>${count}</strong> 处匹配</span>
        <button class="match-prev" title="上一处 (Shift+N)">←</button>
        <button class="match-next" title="下一处 (N)">→</button>
        <button class="match-close" title="关闭 (Esc)">×</button>
    `;
    document.body.appendChild(ind);
    ind.querySelector('.match-next').addEventListener('click', () => jumpToMatch('next'));
    ind.querySelector('.match-prev').addEventListener('click', () => jumpToMatch('prev'));
    ind.querySelector('.match-close').addEventListener('click', () => {
        clearSearchHighlights();
        ind.remove();
    });
    setTimeout(() => ind.remove(), 8000);
}

// N / Shift+N 在结果之间跳转
document.addEventListener('keydown', (e) => {
    if (searchMatches.length === 0) return;
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
    if (e.key === 'n' || e.key === 'N') {
        e.preventDefault();
        jumpToMatch(e.shiftKey ? 'prev' : 'next');
    }
});

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
            if (active) jumpToCommand(active.dataset.chapter, commandInput.value.trim());
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
        print("警告：没找到任何书。请在 books/ 目录下创建子目录。")
        return

    # 构建内容
    bookshelf_html_parts = []
    content_parts = []
    total_chars = 0
    total_chapters = 0

    book_icons = {}  # slug -> svg (sidebar 小图标，16px)
    book_icons_big = {}  # slug -> svg (封面大图标，72px)

    for book_idx, (book_slug, meta, chapters) in enumerate(books):
        icon_name = meta.get("icon", "book")
        book_icons[book_slug] = svg_icon(icon_name, size=16)
        book_icons_big[book_slug] = svg_icon(icon_name, size=72)
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
            # 尝试从 README 第一个 # 标题取，并剥掉「01.」「1、」这类序号前缀
            # （sidebar 已有 ch-num 序号，标题里再带一次会重复）
            first_heading = re.search(r"^#\s+(.+)$", md_text, re.MULTILINE)
            if first_heading:
                display_title = re.sub(
                    r"^\s*\d+[\.\u3001\)\]\uff09]\s*", "", first_heading.group(1).strip()
                )

            # 章节锚点：bookSlug__chapterSlug
            anchor = f"{book_slug}__{chap_slug}"

            chapter_items.append(
                f'<li><a href="#{anchor}">'
                f'<span class="ch-num">{chap_idx:02d}</span>'
                f'<span>{display_title}</span>'
                f'<span class="ch-read-pct" data-chapter="{anchor}"></span>'
                f'</a></li>'
            )

            book_chapters_html_parts.append(
                f'<article id="{anchor}" class="chapter" data-book="{book_slug}" data-chap="{chap_slug}">'
                f'<div class="chapter-num">CHAPTER {chap_idx:02d}</div>'
                f'<h1 class="chapter-title">{display_title}</h1>'
                f'<div class="chapter-meta">约 {minutes} 分钟 · {chars} 字</div>'
                f'<div class="chapter-content">{content_html}</div>'
                f'<div class="chapter-end">本章完</div>'
                f'<button class="completion-toggle" data-chapter="{anchor}">'
                f'<svg class="icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-2px;margin-right:4px"><rect x="3" y="3" width="18" height="18" rx="2"/></svg>'
                f'标记为已读</button>'
                f'</article>'
            )

            total_chapters += 1

        # 书的章节数
        chap_count = len(chapters)

        # 书架 HTML
        bookshelf_html_parts.append(
            f'<div class="book-group" data-book="{book_slug}">'
            f'<div class="book-header">'
            f'<span class="book-icon">{book_icons[book_slug]}</span>'
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
            f'<div class="book-cover" style="--book-color: {book_color}">'
            f'<div class="book-icon-big">{book_icons_big[book_slug]}</div>'
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
    <button class="focus-exit" id="focus-exit" title="退出专注模式 (F)">{svg_icon('close', size=18)}</button>

    <button class="sidebar-toggle" id="sidebar-toggle" title="目录 (S)">{svg_icon('menu')} 书架</button>

    <aside class="sidebar">
        <h1>个人知识库</h1>
        <div class="subtitle">{len(books)} 个系列 · {total_chapters} 章 · 约 {total_minutes} 分钟</div>
        <div class="bookshelf">
            {''.join(bookshelf_html_parts)}
        </div>
        <div class="sidebar-bookmarks" id="sidebar-bookmarks"></div>
    </aside>

    <div class="toolbar">
        <button id="more-btn" title="工具">{svg_icon('menu')}</button>
        <div class="toolbar-menu" id="toolbar-menu">
            <div class="toolbar-section font-sizes">
                <button class="font-btn" data-size="small" title="小字号 (-)">A−</button>
                <button class="font-btn" data-size="medium" title="中字号">A</button>
                <button class="font-btn" data-size="large" title="大字号 (+)">A+</button>
            </div>
            <div class="toolbar-divider"></div>
            <div class="toolbar-actions">
                <button id="music-btn">{svg_icon('music')}<span>背景音乐</span><kbd>M</kbd></button>
                <button id="notes-btn">{svg_icon('notes')}<span>笔记</span><kbd>N</kbd></button>
                <button id="progress-btn">{svg_icon('progress')}<span>阅读进度</span><kbd>P</kbd></button>
                <button id="qr-btn">{svg_icon('qr')}<span>扫码阅读</span><kbd>Q</kbd></button>
                <button id="dark-btn">{svg_icon('moon')}<span>暗色模式</span><kbd>D</kbd></button>
            </div>
        </div>
    </div>

    <div class="selection-toolbar">
        <div class="color-swatch yellow active" data-color="yellow"></div>
        <div class="color-swatch green" data-color="green"></div>
        <div class="color-swatch blue" data-color="blue"></div>
        <div class="color-swatch pink" data-color="pink"></div>
        <div class="divider" style="background: rgba(255,255,255,0.2);"></div>
            <button class="note-btn">{svg_icon('plus')} 笔记</button>
            <button class="bookmark-btn" title="加书签">{svg_icon('bookmark', size=14)} 收藏</button>
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
            <h2>{svg_icon('notes')} 我的笔记</h2>
            <button class="close">×</button>
        </div>
        <div class="notes-list"></div>
    </aside>

    <div class="music-panel">
        <h4>背景音 <button class="close">×</button></h4>
        <div class="scenes">
            <button class="scene-btn" data-scene="off">{svg_icon('mute')} 静音</button>
            <button class="scene-btn" data-scene="woju">{svg_icon('disc')} 且听风吟</button>
        </div>
        <div class="volume">{svg_icon('volume')} <input type="range" min="0" max="100" value="30"> {svg_icon('volume', size=18)}</div>
    </div>

    <div class="pwa-prompt">
        {svg_icon('pwa')} 添加到主屏幕，离线可用
        <button class="close">×</button>
    </div>

    <!-- QR 扫码弹窗 -->
    <div class="qr-modal-backdrop" id="qr-modal">
        <div class="qr-modal" role="dialog" aria-label="扫码在手机上打开">
            <button class="qr-modal-close" id="qr-modal-close" aria-label="关闭">×</button>
            <h3>用手机扫码阅读</h3>
            <p class="qr-hint">微信 / 浏览器 / 相机 扫一扫即可</p>
            <img src="{make_qr_data_url(SITE_URL)}" alt="QR code" id="qr-img">
            <div class="qr-url" id="qr-url">{SITE_URL}</div>
            <div class="qr-actions">
                <button id="qr-copy-btn">
                    {svg_icon('check', size=14)} 复制链接
                </button>
            </div>
        </div>
    </div>

    <!-- 背景音乐 - 真实录音（且听风吟，电视剧《蜗居》钢琴插曲，3:08） -->
    <!-- 文件不入 git，本地 build 才有；部署到 GitHub Pages 时不存在，scene 按钮自动隐藏 -->
    <audio id="woju-audio" src="assets/audio/woju_low.mp3" loop preload="auto"></audio>

    <!-- 进度面板 -->
    <div class="progress-panel">
        <div class="progress-modal">
            <div class="progress-modal-header">
                <h2>{svg_icon('progress')} 阅读进度</h2>
                <button class="close">×</button>
            </div>

            <div class="overall-progress">
                <div class="big-number"><span id="overall-percent">0</span>%</div>
                <div class="label"><span id="overall-stats">0 / 0 章</span></div>
                <div class="progress-bar">
                    <div class="progress-bar-fill" id="overall-fill" style="width: 0%"></div>
                </div>
                <div class="time-stat" id="time-stat">还没开始记录阅读时长</div>
            </div>

            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-value"><span id="stat-streak">0</span><span class="stat-value-unit">天</span></div>
                    <div class="stat-label">最长连续</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value"><span id="stat-today">0</span><span class="stat-value-unit">分</span></div>
                    <div class="stat-label">今日阅读</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value"><span id="stat-avg">0</span><span class="stat-value-unit">分</span></div>
                    <div class="stat-label">平均每次</div>
                    <div class="stat-sub" id="stat-avg-sub">每天平均</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value"><span id="stat-days">0</span><span class="stat-value-unit">天</span></div>
                    <div class="stat-label">阅读天数</div>
                </div>
            </div>

            <div id="book-progress-list"></div>

            <div class="calendar">
                <div class="calendar-title">
                    <span>{svg_icon('calendar')} 阅读日历（本年至今）</span>
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
                <div class="calendar-chart">
                    <div class="calendar-months-row">
                        <div class="calendar-weekday-spacer"></div>
                        <div class="calendar-months" id="calendar-months"></div>
                    </div>
                    <div class="calendar-body-row">
                        <div class="calendar-weekdays" id="calendar-weekdays"></div>
                        <div class="calendar-grid" id="calendar-grid"></div>
                    </div>
                </div>
                <div class="calendar-tooltip" id="calendar-tooltip"></div>
                <div class="calendar-recent" id="calendar-recent"></div>
            </div>

            <div class="progress-actions">
                <button id="export-progress">{svg_icon('download')} 导出数据</button>
                <button id="export-notes-md">{svg_icon('bookmark')} 导出笔记 (Markdown)</button>
                <button id="import-progress">{svg_icon('upload')} 导入数据</button>
                <button id="reset-progress">{svg_icon('trash')} 重置进度</button>
            </div>
        </div>
    </div>

    <!-- 快捷键帮助 -->
    <div class="help-panel">
        <div class="help-modal">
            <button class="help-close" id="help-close">×</button>
            <h2>{svg_icon('search')} 快捷键</h2>
            <div class="help-section">
                <div class="help-section-title">导航</div>
                <div class="help-row"><span>搜索章节 / 内容</span><span><kbd>Ctrl</kbd> <kbd>K</kbd></span></div>
                <div class="help-row"><span>切换侧栏</span><span><kbd>S</kbd></span></div>
                <div class="help-row"><span>专注模式</span><span><kbd>F</kbd></span></div>
                <div class="help-row"><span>跳到顶部</span><span><kbd>G</kbd> <kbd>G</kbd></span></div>
                <div class="help-row"><span>跳到底部</span><span><kbd>G</kbd> <kbd>G</kbd> <kbd>G</kbd></span></div>
            </div>
            <div class="help-section">
                <div class="help-section-title">工具</div>
                <div class="help-row"><span>背景音乐</span><span><kbd>M</kbd></span></div>
                <div class="help-row"><span>笔记</span><span><kbd>N</kbd></span></div>
                <div class="help-row"><span>阅读进度</span><span><kbd>P</kbd></span></div>
                <div class="help-row"><span>扫码阅读</span><span><kbd>Q</kbd></span></div>
                <div class="help-row"><span>暗色模式</span><span><kbd>D</kbd></span></div>
                <div class="help-row"><span>字号 + / -</span><span><kbd>+</kbd> / <kbd>-</kbd></span></div>
                <div class="help-row"><span>工具菜单</span><span><kbd>Esc</kbd></span></div>
            </div>
            <div class="help-section">
                <div class="help-section-title">本面板</div>
                <div class="help-row"><span>显示本帮助</span><span><kbd>?</kbd></span></div>
                <div class="help-row"><span>关闭任何面板</span><span><kbd>Esc</kbd></span></div>
            </div>
        </div>
    </div>

    <!-- 命令面板（搜索） -->
    <div class="command-palette">
        <div class="command-modal">
            <input type="text" class="command-input" placeholder="搜索章节标题或内容...">
            <div class="command-filters" id="command-filters">
                <button class="command-chip active" data-filter="all">全部</button>
                {''.join(f'<button class="command-chip" data-filter="{slug}">{title}</button>' for slug, title, _ in books)}
            </div>
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
    print(f"生成 {output}")
    print(f"  大小: {len(html):,} 字符 ({len(html) / 1024:.1f} KB)")
    print(f"  系列: {len(books)} | 总章节: {total_chapters} | 总字数: {total_chars:,}")
    for slug, meta, chs in books:
        print(f"    {meta['title']} ({len(chs)} 章)")


if __name__ == "__main__":
    build_html()