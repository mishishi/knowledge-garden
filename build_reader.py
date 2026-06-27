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
import time
import os
import numpy as _np
from io import BytesIO
from pathlib import Path
from datetime import datetime, timezone

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
    'layers':   '<polygon points="12 2 2 7 12 12 22 7 12 2"/><polyline points="2 17 12 22 22 17"/><polyline points="2 12 12 17 22 12"/>',
    'share':    '<circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><line x1="8.59" y1="13.51" x2="15.42" y2="17.49"/><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"/>',
    'brain':    '<path d="M9.5 2A2.5 2.5 0 0 1 12 4.5v15a2.5 2.5 0 0 1-4.96.44 2.5 2.5 0 0 1-2.96-3.08 3 3 0 0 1-.34-5.58 2.5 2.5 0 0 1 1.32-4.24 2.5 2.5 0 0 1 1.98-3A2.5 2.5 0 0 1 9.5 2"/><path d="M14.5 2A2.5 2.5 0 0 0 12 4.5v15a2.5 2.5 0 0 0 4.96.44 2.5 2.5 0 0 0 2.96-3.08 3 3 0 0 0 .34-5.58 2.5 2.5 0 0 0-1.32-4.24 2.5 2.5 0 0 0-1.98-3A2.5 2.5 0 0 0 14.5 2"/>',
    'volume':   '<polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M15.54 8.46a5 5 0 0 1 0 7.07"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14"/>',
    'volume-x': '<polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><line x1="23" y1="9" x2="17" y2="15"/><line x1="17" y1="9" x2="23" y2="15"/>',
    'qr':       '<rect width="5" height="5" x="3" y="3" rx="1"/><rect width="5" height="5" x="16" y="3" rx="1"/><rect width="5" height="5" x="3" y="16" rx="1"/><path d="M5 5h.01"/><path d="M19 5h.01"/><path d="M5 19h.01"/><line x1="10" y1="5" x2="14" y2="5"/><line x1="10" y1="19" x2="14" y2="19"/><line x1="19" y1="10" x2="19" y2="14"/><line x1="5" y1="10" x2="5" y2="14"/><line x1="10" y1="10" x2="14" y2="10"/><line x1="10" y1="14" x2="14" y2="14"/><line x1="14" y1="10" x2="14" y2="14"/><line x1="10" y1="14" x2="10" y2="10"/>',
    'disc':     '<circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="3"/><path d="M6 12c0-1.7 1.3-3 3-3"/>',
    'coin':     '<circle cx="12" cy="12" r="9"/><path d="M12 6v12"/><path d="M15.5 9.5C15.5 8.5 14 8 12 8s-3.5.5-3.5 1.8c0 1.3 1.5 1.7 3.5 1.9 2 .2 3.5.6 3.5 1.9 0 1.3-1.5 2-3.5 2s-3.5-.7-3.5-2"/>',
    'rocket':   '<path d="M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 0 0-2.91-.09z"/><path d="M12 15l-3-3a22 22 0 0 1 2-3.95A12.88 12.88 0 0 1 22 2c0 2.72-.78 7.5-6 11a22.35 22.35 0 0 1-4 2z"/><path d="M9 12H4s.55-3.03 2-4c1.62-1.08 5 0 5 0"/><path d="M12 15v5s3.03-.55 4-2c1.08-1.62 0-5 0-5"/>',
    'stack':    '<rect x="3" y="3" width="18" height="6" rx="1"/><rect x="3" y="9" width="18" height="6" rx="1"/><rect x="3" y="15" width="18" height="6" rx="1"/>',
    'sparkles': '<path d="M12 3l1.9 5.7 5.7 1.9-5.7 1.9L12 18l-1.9-5.7L4.4 10.6l5.7-1.9L12 3z"/><path d="M19 16l.9 2.6 2.6.9-2.6.9L19 23l-.9-2.6L15.5 19.5l2.6-.9L19 16z"/><path d="M5 14l.6 1.8 1.8.6-1.8.6L5 19l-.6-1.8L2.6 16.6l1.8-.6L5 14z"/>',
    'terminal': '<polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x2="20" y2="19"/>',
    'network':  '<circle cx="12" cy="12" r="3"/><circle cx="4" cy="4" r="2"/><circle cx="20" cy="4" r="2"/><circle cx="4" cy="20" r="2"/><circle cx="20" cy="20" r="2"/><line x1="6" y1="6" x2="9.5" y2="9.5"/><line x1="18" y1="6" x2="14.5" y2="9.5"/><line x1="6" y1="18" x2="9.5" y2="14.5"/><line x1="18" y1="18" x2="14.5" y2="14.5"/>',
    'pen-tool': '<path d="M15.707 21.293a1 1 0 0 1-1.414 0l-1.586-1.586a1 1 0 0 1 0-1.414l8.586-8.586a1 1 0 0 1 1.414 0l1.586 1.586a1 1 0 0 1 0 1.414z"/><path d="m18 13-1.5-7.5L2 2l3.5 14.5L13 18l5-5z"/><path d="m2 2 7.586 7.586"/><circle cx="11" cy="11" r="2"/>',
    'zap':      '<polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>',
    'wind':     '<path d="M9.59 4.59A2 2 0 1 1 11 8H2m10.59 11.41A2 2 0 1 0 14 16H2m15.73-8.27A2.5 2.5 0 1 1 19.5 12H2"/>',
}


def build_per_chapter_pages(books) -> int:
    """为每本书的每章生成 1 个静态 HTML 入口页.

    设计: 真实 URL (`/books/<slug>/<chapter>.html`), 含专属 OG meta + meta refresh
    跳转回 index.html#anchor. 用户访问时立刻 302 到 SPA, 但 Google 看到的是独立
    URL + 该章 OG (转发到 V2EX/推特时显示对应书色卡).
    """
    from html import escape as _esc

    pages_dir = ROOT / "books_pages"
    # 清理旧产物 — 重新生成时避免遗留文件
    if pages_dir.exists():
        import shutil
        shutil.rmtree(pages_dir)
    pages_dir.mkdir(parents=True, exist_ok=True)

    total = 0
    for book_slug, meta, chapters in books:
        book_title = meta.get("title", book_slug)
        for chap_slug, chap_path in chapters:
            md_text = chap_path.read_text(encoding="utf-8")
            display_title = chapter_display_title(md_text, chap_slug)

            # 抽首段做 og:description
            first_para = ""
            for line in md_text.split("\n"):
                line = line.strip()
                if not line or line.startswith("#") or line.startswith("```"):
                    continue
                if line.startswith("!") or line.startswith("[") or line.startswith("-"):
                    continue
                plain = re.sub(r"[*_`\[\]()>]", "", line)
                if len(plain) > 30:
                    first_para = plain[:180].strip()
                    break

            anchor = f"{book_slug}__{chap_slug}"
            page_url = f"{SITE_URL}books_pages/{book_slug}/{chap_slug}.html"
            target_url = f"{SITE_URL}index.html#{anchor}"
            og_image = f"{SITE_URL}assets/og-{book_slug}.png"
            full_title = f"{display_title} · {book_title} · 个人知识库"

            html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{_esc(full_title)}</title>
<meta http-equiv="refresh" content="0; url={_esc(target_url)}">
<link rel="canonical" href="{_esc(page_url)}">
<meta property="og:type" content="article">
<meta property="og:url" content="{_esc(page_url)}">
<meta property="og:title" content="{_esc(full_title)}">
<meta property="og:description" content="{_esc(first_para or book_title)}">
<meta property="og:image" content="{_esc(og_image)}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:locale" content="zh_CN">
<meta property="og:site_name" content="个人知识库">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{_esc(full_title)}">
<meta name="twitter:description" content="{_esc(first_para or book_title)}">
<meta name="twitter:image" content="{_esc(og_image)}">
<style>
body {{ font-family: -apple-system, "PingFang SC", sans-serif; max-width: 600px; margin: 80px auto; padding: 0 20px; text-align: center; color: #5a5a5a; }}
a {{ color: #b08968; }}
</style>
</head>
<body>
<p>正在跳转到 <a href="{_esc(target_url)}">{_esc(display_title)}</a> …</p>
<script>window.location.replace({target_url!r});</script>
</body>
</html>
'''
            out_dir = pages_dir / book_slug
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / f"{chap_slug}.html").write_text(html, encoding="utf-8")
            total += 1

    print(f"生成 {pages_dir}/  ({total} 章静态页, 每章 ~3KB)")
    return total


def build_sitemap(books) -> None:
    """生成 sitemap.xml (SEO 用). 每章一条真实 URL (per-chapter 静态页),
    主站单条.

    改造前: 每条都是 SITE_URL#hash_anchor, Google 当成 1 个 URL.
    改造后: 每章 1 个独立 URL, 100 章 = 100 条可索引页面.
    """
    today = datetime.now().strftime("%Y-%m-%d")
    lines = ['<?xml version="1.0" encoding="UTF-8"?>']
    lines.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')
    # 主站
    lines.append("  <url>")
    lines.append(f"    <loc>{SITE_URL}</loc>")
    lines.append(f"    <lastmod>{today}</lastmod>")
    lines.append("    <changefreq>weekly</changefreq>")
    lines.append("    <priority>1.0</priority>")
    lines.append("  </url>")
    # 每本书
    for book_slug, meta, chapters in books:
        lines.append("  <url>")
        lines.append(f"    <loc>{SITE_URL}books_pages/{book_slug}/</loc>")
        lines.append(f"    <lastmod>{today}</lastmod>")
        lines.append("    <changefreq>weekly</changefreq>")
        lines.append("    <priority>0.9</priority>")
        lines.append("  </url>")
        # 每章
        for chap_slug, _ in chapters:
            lines.append("  <url>")
            lines.append(f"    <loc>{SITE_URL}books_pages/{book_slug}/{chap_slug}.html</loc>")
            lines.append(f"    <lastmod>{today}</lastmod>")
            lines.append("    <priority>0.8</priority>")
            lines.append("  </url>")
    lines.append('</urlset>')

    output = ROOT / "sitemap.xml"
    output.write_text("\n".join(lines), encoding="utf-8")
    print(f"生成 {output} ({sum(len(c) for _, _, c in books) + len(books) + 1} URLs)")


def build_rss(books) -> None:
    """生成 rss.xml, 每章一条 item. link 用真实 per-chapter 静态页 URL."""
    from email.utils import format_datetime
    import html as _html

    now = format_datetime(datetime.now(timezone.utc))
    lines = ['<?xml version="1.0" encoding="UTF-8"?>']
    lines.append('<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">')
    lines.append('<channel>')
    lines.append('  <title>个人知识库</title>')
    lines.append(f'  <link>{SITE_URL}</link>')
    total_chapters = sum(len(c) for _, _, c in books)
    lines.append(f'  <description>{len(books)} 个系列 · {total_chapters} 章 · Multi-Agent / LLM Prompt / CrewAI / RAG / Harness Engineering / Cost / Indie / Context / Skills / Claude Code</description>')
    lines.append(f'  <lastBuildDate>{now}</lastBuildDate>')
    lines.append(f'  <atom:link href="{SITE_URL}rss.xml" rel="self" type="application/rss+xml"/>')

    for book_slug, meta, chapters in books:
        for chap_slug, chap_path in chapters:
            md_text = chap_path.read_text(encoding="utf-8")
            display_title = chapter_display_title(md_text, chap_slug)

            # description: 抽第一段纯文本 (去 markdown 标记)
            first_para = ""
            for line in md_text.split("\n"):
                line = line.strip()
                if not line or line.startswith("#") or line.startswith("```"):
                    continue
                if line.startswith("!") or line.startswith("[") or line.startswith("-"):
                    continue
                # 简单去标点
                plain = re.sub(r"[*_`\[\]()>]", "", line)
                if len(plain) > 30:
                    first_para = plain[:200].strip()
                    break

            item_title = f"{meta['title']} · {display_title}"
            item_link = f"{SITE_URL}books_pages/{book_slug}/{chap_slug}.html"
            lines.append('  <item>')
            lines.append(f'    <title>{_html.escape(item_title)}</title>')
            lines.append(f'    <link>{item_link}</link>')
            lines.append(f'    <guid isPermaLink="true">{item_link}</guid>')
            lines.append(f'    <pubDate>{now}</pubDate>')
            if first_para:
                lines.append(f'    <description>{_html.escape(first_para)}</description>')
            lines.append('  </item>')

    lines.append('</channel>')
    lines.append('</rss>')

    output = ROOT / "rss.xml"
    output.write_text("\n".join(lines), encoding="utf-8")
    print(f"生成 {output} ({sum(len(c) for _, _, c in books)} items)")


def build_robots() -> None:
    """生成 robots.txt — 允许全部 + 指 sitemap."""
    output = ROOT / "robots.txt"
    content = f"""# robots.txt — knowledge-garden
User-agent: *
Allow: /

Sitemap: {SITE_URL}sitemap.xml
"""
    output.write_text(content, encoding="utf-8")
    print(f"生成 {output}")


def build_sw() -> None:
    """生成 sw.js (PWA Service Worker).

    - 安装时缓存根 index.html
    - 激活时清掉旧 cache
    - fetch 时 cache-on-demand: assets/ 目录下的 book JSON 首次下载后缓存, 二次访问秒开
    - 离线时回退到根 index (PWA app shell)
    """
    output = ROOT / "sw.js"
    sw_code = """// Knowledge Garden Service Worker
// Bump CACHE version on every release to invalidate stale entries.
const CACHE = 'knowledge-book-v3';

self.addEventListener('install', e => {
    e.waitUntil(
        caches.open(CACHE).then(c => c.addAll(['./']))
    );
    self.skipWaiting();
});

self.addEventListener('activate', e => {
    e.waitUntil(
        caches.keys()
            .then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
            .then(() => self.clients.claim())
    );
});

self.addEventListener('fetch', e => {
    const req = e.request;
    if (req.method !== 'GET') return;
    const url = new URL(req.url);
    // Cache same-origin GET only (skip cross-origin like CDN fonts).
    if (url.origin !== self.location.origin) return;
    // 哪些路径值得缓存: assets/ (book JSONs + search index + Q&A dense) + index.html + root
    const isCacheable =
        url.pathname.includes('/assets/') ||
        url.pathname.endsWith('.html') ||
        url.pathname === '/' || url.pathname.endsWith('/');
    if (!isCacheable) return; // 非 cacheable 请求走默认网络
    e.respondWith(
        caches.match(req).then(cached => {
            if (cached) return cached;
            return fetch(req).then(resp => {
                if (resp && resp.ok) {
                    const clone = resp.clone();
                    caches.open(CACHE).then(c => c.put(req, clone)).catch(() => {});
                }
                return resp;
            }).catch(() => {
                // 离线 fallback: SPA app shell
                return caches.match('./');
            });
        })
    );
});
"""
    output.write_text(sw_code, encoding="utf-8")
    print(f"生成 {output}")


def chapter_display_title(md_text: str, fallback_slug: str) -> str:
    """从 markdown 第一个 # 标题取展示名，剥掉序号前缀。复用 build_html 内的逻辑。"""
    display = fallback_slug
    first_heading = re.search(r"^#\s+(.+)$", md_text, re.MULTILINE)
    if first_heading:
        display = first_heading.group(1).strip()
        # 剥掉 "1." / "1、" / "1)" / "1）" 等数字前缀
        display = re.sub(r"^\s*\d+[\.\u3001\)\]\uff09]\s*", "", display)
        # 剥掉 "第 N 章：" / "第 N 章" 前缀（中英文章序号）
        display = re.sub(r"^\s*第\s*\d+\s*章[\s\uff1a\:]\s*", "", display)
    return display


# ============================================================
# 知识问答：TF-IDF 向量 + chunk 索引
# - 每个 chapter 切成 ~500 字 (overlap 80 字)
# - tokenize: CJK char 1-gram + 2-gram, ASCII word
# - 每个 chunk 存 {id, text, term_freq} (sparse dict)
# - 全局存 {idf, avgDocLen, N, totalChars}
# - 浏览器侧：cosine 相似度 top-5
# ============================================================
import re as _re_kb
import math as _math_kb
import json as _json_kb
from collections import Counter as _Counter_kb


def _kb_strip_markdown(text: str) -> str:
    """剥 markdown 标记，只留 plain text."""
    # 去掉 frontmatter
    text = _re_kb.sub(r"^---.*?---\s*", "", text, flags=_re_kb.DOTALL)
    # 去掉 code block
    text = _re_kb.sub(r"```.*?```", " ", text, flags=_re_kb.DOTALL)
    # 去掉 inline code
    text = _re_kb.sub(r"`[^`]+`", " ", text)
    # 去掉图片
    text = _re_kb.sub(r"!\[[^\]]*\]\([^)]+\)", " ", text)
    # 链接只留文字
    text = _re_kb.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    # heading 标记
    text = _re_kb.sub(r"^#+\s*", "", text, flags=_re_kb.MULTILINE)
    # bold/italic
    text = _re_kb.sub(r"[*_]{1,3}(\S+?)[*_]{1,3}", r"\1", text)
    # blockquote
    text = _re_kb.sub(r"^>\s*", "", text, flags=_re_kb.MULTILINE)
    # list marker
    text = _re_kb.sub(r"^[\s]*[-*+]\s+", "", text, flags=_re_kb.MULTILINE)
    text = _re_kb.sub(r"^[\s]*\d+\.\s+", "", text, flags=_re_kb.MULTILINE)
    # 表格分隔行
    text = _re_kb.sub(r"^\|?[\s:|-]+\|?[\s:|-]*$", "", text, flags=_re_kb.MULTILINE)
    text = text.replace("|", " ")
    # 折叠空白
    text = _re_kb.sub(r"\s+", " ", text).strip()
    return text


def _kb_chunk_text(text: str, size: int = 500, overlap: int = 80) -> list:
    """切片：在句末标点或换行处优先断开."""
    if len(text) <= size:
        return [text] if text else []
    chunks = []
    start = 0
    n = len(text)
    while start < n:
        end = min(start + size, n)
        if end < n:
            # 尝试在 [start+size-100, end] 范围内找最后一个句末标点
            window_lo = start + max(100, size - 100)
            best = -1
            for sep in ["。", "！", "？", "\n", ". ", "! ", "? "]:
                idx = text.rfind(sep, window_lo, end)
                if idx > best:
                    best = idx + len(sep)
            if best > start + 100:
                end = best
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= n:
            break
        start = max(end - overlap, start + 1)
    return chunks


def _kb_tokenize(text: str) -> list:
    """CJK char 1-gram + 2-gram, ASCII word 整词."""
    terms = []
    # 先抽 ASCII word
    for m in _re_kb.finditer(r"[A-Za-z0-9]+", text):
        terms.append(m.group(0).lower())
    # 抽 CJK 段
    cjk = _re_kb.sub(r"[A-Za-z0-9\s]+", " ", text)
    # 1-gram
    for c in cjk:
        if "\u4e00" <= c <= "\u9fff":
            terms.append(c)
    # 2-gram
    for i in range(len(cjk) - 1):
        c1, c2 = cjk[i], cjk[i + 1]
        if "\u4e00" <= c1 <= "\u9fff" and "\u4e00" <= c2 <= "\u9fff":
            terms.append(c1 + c2)
    return terms


# ============================================================
# 章节标题跨语言别名映射
# - 章节标题常含英文术语（Agent / Claude Code / Harness ...）
# - 用户用中文搜（"智能体 怎么写"）时，TF-IDF 算不出英文 title 的相关性
# - 这里把英文术语在 title 里命中时，对应中文别名 term 加权注入 chunk TF
# - 效果：'智能体 怎么写' 的 chunk 能命中 '你的第一个 Agent' 章节
# ============================================================
_TITLE_EN_TO_ZH = {
    'agent': '智能体',
    'agents': '智能体',
    'agentic': '智能体',
    'multi-agent': '多智能体',
    'multi agent': '多智能体',
    'claude code': 'claude code 实战',
    'harness': '脚手架',
    'a2a': 'a2a 协议',
    'mcp': 'mcp 协议',
    'vibe coding': '氛围编程',
    'cot': '思维链',
    'rag': '检索增强生成',
    'embedding': '向量',
    'prompt': '提示词',
    'llm': '大模型',
    'scaffold': '脚手架',
}


def _kb_title_aliases(chapter_title: str) -> list:
    """从章节标题抽取中文别名 term."""
    if not chapter_title:
        return []
    title_lower = chapter_title.lower()
    out = []
    for en, zh in _TITLE_EN_TO_ZH.items():
        # word-boundary 匹配，避免 'a2a' 误匹配 'a2aa'
        if _re_kb.search(r'(^|[^a-z0-9])' + _re_kb.escape(en) + r'($|[^a-z0-9])', title_lower):
            out.append(zh)
    # 去重保序
    seen = set()
    return [x for x in out if not (x in seen or seen.add(x))]


def build_knowledge_index(books) -> None:
    """生成 assets/knowledge_index.json — 浏览器 cosine 搜索用."""
    chunks = []
    for slug, meta, chapters in books:
        for chap_slug, chap_path in chapters:
            raw = chap_path.read_text(encoding="utf-8")
            text = _kb_strip_markdown(raw)
            if not text:
                continue
            chap_chunks = _kb_chunk_text(text, size=500, overlap=80)
            chapter_title = chapter_display_title(raw, chap_slug)
            # 章节标题里的英文术语 → 中文别名（注入到 chunk TF，让 TF-IDF 跨语言命中）
            aliases = _kb_title_aliases(chapter_title)
            alias_tokens = []
            for a in aliases:
                alias_tokens.extend(_kb_tokenize(a))
            for i, ct in enumerate(chap_chunks):
                tokens = _kb_tokenize(ct)
                if not tokens:
                    continue
                tf = _Counter_kb(tokens)
                # 别名 term 注入 TF，权重 +3（模拟 title 命中，跨语言 TF-IDF 命中）
                for term in alias_tokens:
                    tf[term] = tf.get(term, 0) + 3
                chunks.append({
                    "id": f"{slug}__{chap_slug}__{i}",
                    "chapterId": f"{slug}__{chap_slug}",
                    "chapterTitle": chapter_title,
                    "bookSlug": slug,
                    "bookTitle": meta.get("title", slug),
                    "text": ct,
                    "tf": dict(tf),
                    "len": sum(tf.values()),
                })

    if not chunks:
        print("WARN: no chunks to index")
        return

    # 计算 IDF
    df = _Counter_kb()
    for c in chunks:
        for t in set(c["tf"].keys()):
            df[t] += 1
    N = len(chunks)
    # BM25 风格 IDF (带 +1 防 log(0)) — round 到 3 位小数，存小
    idf = {t: round(_math_kb.log((N - df[t] + 0.5) / (df[t] + 0.5) + 1), 3) for t in df}
    avg_doc_len = sum(c["len"] for c in chunks) / N

    # 每个 chunk 算 TF-IDF 向量 + norm；只保留 top-20 高权重 term
    # (top-20 对 ~500 字 chunk 已足够；cosine 相似度用稀疏 dot 不受影响)
    TOP_K = 20
    PREVIEW_LEN = 200  # index 里只存 200 字预览，full chunk 在 #anchor 章节里
    final_chunks = []
    for c in chunks:
        vec = {}
        for t, f in c["tf"].items():
            w = idf.get(t, 0) * f
            vec[t] = w
        # top-K 剪枝
        if len(vec) > TOP_K:
            top = sorted(vec.items(), key=lambda x: -x[1])[:TOP_K]
            vec = dict(top)
        norm = _math_kb.sqrt(sum(w * w for w in vec.values())) or 1.0
        # preview 截到 PREVIEW_LEN
        preview = c["text"] if len(c["text"]) <= PREVIEW_LEN else c["text"][:PREVIEW_LEN] + "…"
        final_chunks.append({
            "id": c["id"],
            "chapterId": c["chapterId"],
            "chapterTitle": c["chapterTitle"],
            "bookSlug": c["bookSlug"],
            "bookTitle": c["bookTitle"],
            "text": preview,
            "vec": vec,
            "norm": round(norm, 4),
        })

    index = {
        "version": 1,
        "N": N,
        "avgDocLen": round(avg_doc_len, 2),
        "chunkSize": 500,
        "overlap": 80,
        "idf": idf,
        "chunks": final_chunks,
    }

    out = ROOT / "assets" / "knowledge_index.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        _json_kb.dump(index, f, ensure_ascii=False, separators=(",", ":"))

    import os as _os_kb
    size_kb = _os_kb.path.getsize(out) / 1024
    print(f"生成 {out} ({N} chunks, {size_kb:.1f} KB)")


def build_dense_index(books) -> None:
    """生成 assets/knowledge_dense.json — BGE 中文 dense embedding.

    - 用 sentence-transformers BAAI/bge-small-zh-v1.5 (512-dim, Chinese-specialized)
    - 浏览器侧用 Xenova/bge-small-zh-v1.5 (transformers.js, 24MB int8 量化)
    - chunk 切片复用 _kb_chunk_text + _kb_strip_markdown, ID 格式跟 TF-IDF 一致 (book__chap__i)
    - 文件存 chunks[i].embedding = [512 floats]，JSON 格式，浏览器侧 fetch 解析
    """
    print("加载 BAAI/bge-small-zh-v1.5 (首次下载约 400MB,之后缓存)...")
    from sentence_transformers import SentenceTransformer
    t0 = time.time()
    model = SentenceTransformer("BAAI/bge-small-zh-v1.5")
    print(f"  模型加载 {time.time() - t0:.1f}s, dim={model.get_sentence_embedding_dimension()}")

    # 切片（跟 TF-IDF 用同一函数，ID 格式一致）
    chunks = []
    for slug, meta, chapters in books:
        for chap_slug, chap_path in chapters:
            raw = chap_path.read_text(encoding="utf-8")
            text = _kb_strip_markdown(raw)
            if not text:
                continue
            chap_chunks = _kb_chunk_text(text, size=500, overlap=80)
            chapter_title = chapter_display_title(raw, chap_slug)
            for i, ct in enumerate(chap_chunks):
                chunks.append({
                    "id": f"{slug}__{chap_slug}__{i}",
                    "chapterId": f"{slug}__{chap_slug}",
                    "chapterTitle": chapter_title,
                    "bookSlug": slug,
                    "bookTitle": meta.get("title", slug),
                    "text": ct,
                })

    if not chunks:
        print("WARN: no chunks to embed")
        return

    print(f"  embedding {len(chunks)} chunks (batch 32)...")
    t0 = time.time()
    texts = [c["text"] for c in chunks]
    # BGE 中文模型推荐 query 加 "为这个句子生成表示以用于检索相关文章：" prefix
    # 但这里 chunk 不是 query,是文档侧,不需要 prefix
    embeddings = model.encode(
        texts,
        batch_size=32,
        show_progress_bar=True,
        normalize_embeddings=True,  # L2 归一 → cosine = dot product
        convert_to_numpy=True,
    )
    print(f"  embedding {time.time() - t0:.1f}s")

    # 只存 id + embedding (base64-encoded float32)。text/title/bookSlug 在 TF-IDF 索引里有,
    # 浏览器通过 id 关联获取。
    # 用紧凑数组格式 [id1, emb1, id2, emb2, ...] 比 [{id, embedding}, ...] 小 ~15%
    import base64 as _base64_dense
    chunks_array = []
    for i, c in enumerate(chunks):
        emb_bytes = embeddings[i].astype("<f4").tobytes()  # 512 × 4 = 2048 bytes
        emb_b64 = _base64_dense.b64encode(emb_bytes).decode("ascii")
        chunks_array.append(c["id"])
        chunks_array.append(emb_b64)

    # 章节级平均 embedding (for "相关章节" feature)
    # 175 章 × 512-dim = 350KB extra，base64 后 ~470KB
    chapter_groups = {}  # chapterId -> { bookSlug, bookTitle, chapterTitle, vecs: [numpy arrays] }
    for i, c in enumerate(chunks):
        cid = c["chapterId"]
        if cid not in chapter_groups:
            chapter_groups[cid] = {
                "bookSlug": c["bookSlug"],
                "bookTitle": c["bookTitle"],
                "chapterTitle": c["chapterTitle"],
                "vecs": [],
            }
        chapter_groups[cid]["vecs"].append(embeddings[i])
    chapters_array = []
    for cid, info in chapter_groups.items():
        # mean-pool: 平均所有 chunk 向量 (已经 L2-normalize, mean 近似保留语义)
        stacked = _np.vstack(info["vecs"])
        avg = stacked.mean(axis=0)
        # 重新 L2 normalize
        norm = _np.linalg.norm(avg)
        if norm > 0:
            avg = avg / norm
        avg_bytes = avg.astype("<f4").tobytes()
        avg_b64 = _base64_dense.b64encode(avg_bytes).decode("ascii")
        chapters_array.append({
            "id": cid,
            "bookSlug": info["bookSlug"],
            "bookTitle": info["bookTitle"],
            "chapterTitle": info["chapterTitle"],
            "embedding": avg_b64,
        })

    index = {
        "version": 2,
        "model": "BAAI/bge-small-zh-v1.5",
        "dim": model.get_sentence_embedding_dimension(),
        "encoding": "float32-base64",  # chunks 是 [id1, emb1, id2, emb2, ...] 紧凑数组
        "N": len(chunks),
        "chunkSize": 500,
        "overlap": 80,
        "chunks": chunks_array,
        "chapters": chapters_array,  # 175 个章节级 mean-pooled embedding
    }

    out = ROOT / "assets" / "knowledge_dense.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        _json_kb.dump(index, f, ensure_ascii=False, separators=(",", ":"))

    import os as _os_kb
    size_kb = _os_kb.path.getsize(out) / 1024
    print(f"生成 {out} ({len(chunks)} chunks × {index['dim']}-dim, {size_kb:.1f} KB)")


def build_overview_html(books, total_chapters, total_chars, total_minutes) -> str:
    """生成 <section id="overview"> HTML.

    落地视图：顶部 stats + 继续阅读（由 JS 在运行时填），底下 5 个 series 卡片，
    每张卡有进度条 + 章节列表。章节 marker (✓ ◐ ○) 由 JS 在运行时根据
    localStorage 的 progress 渲染 — 这里只生成空 span 占位。
    """
    parts = ['<section id="overview" class="overview">']

    # ---- 顶部 hero ----
    parts.append('<div class="overview-hero">')
    parts.append(f'  <h1 class="overview-title">个人知识库</h1>')
    parts.append(
        f'  <p class="overview-subtitle">'
        f'{len(books)} 个系列 · {total_chapters} 章 · 约 {total_minutes} 分钟'
        f'</p>'
    )
    # stats 行：4 个数
    parts.append('  <div class="overview-stats">')
    parts.append(f'    <div class="overview-stat"><span class="num">{len(books)}</span><span class="lbl">系列</span></div>')
    parts.append(f'    <div class="overview-stat"><span class="num">{total_chapters}</span><span class="lbl">章节</span></div>')
    parts.append(f'    <div class="overview-stat"><span class="num">{total_chars:,}</span><span class="lbl">字</span></div>')
    parts.append('    <div class="overview-stat"><span class="num" id="overview-read-pct">0</span><span class="lbl">已读</span></div>')
    parts.append('  </div>')
    # 继续阅读 carousel（运行时由 JS 填，没数据就隐藏整个 wrap）
    parts.append(
        '  <div class="resume-carousel" id="resume-carousel" style="display:none">'
        '<div class="resume-carousel-track" id="resume-carousel-track"></div>'
        '</div>'
    )
    parts.append('</div>')

    # ---- 个人数据看板（运行时由 JS 填） ----
    parts.append('<div class="personal-dashboard" id="personal-dashboard">')
    parts.append('<h2 class="dashboard-title">我的阅读</h2>')
    parts.append('<div class="dashboard-grid">')
    parts.append('<div class="dashboard-card"><div class="d-num" id="d-read-count">0</div><div class="d-lbl">已读章节</div></div>')
    parts.append('<div class="dashboard-card"><div class="d-num" id="d-reading-count">0</div><div class="d-lbl">在读</div></div>')
    parts.append('<div class="dashboard-card"><div class="d-num" id="d-time-spent">0</div><div class="d-lbl">累计分钟</div></div>')
    parts.append('<div class="dashboard-card"><div class="d-num" id="d-notes-count">0</div><div class="d-lbl">笔记数</div></div>')
    parts.append('<div class="dashboard-card"><div class="d-num" id="d-bookmarks-count">0</div><div class="d-lbl">书签数</div></div>')
    parts.append('<div class="dashboard-card"><div class="d-num" id="d-streak-days">0</div><div class="d-lbl">连续天数</div></div>')
    parts.append('</div>')
    parts.append('<div class="dashboard-streak" id="dashboard-streak"></div>')
    parts.append('<div class="weekly-goal" id="weekly-goal">')
    parts.append('<div class="weekly-goal-header"><span class="weekly-goal-title">本周阅读目标</span>')
    parts.append('<button class="weekly-goal-edit" id="weekly-goal-edit" title="调整目标">编辑</button></div>')
    parts.append('<div class="weekly-goal-progress">')
    parts.append('<div class="weekly-goal-bar"><div class="weekly-goal-fill" id="weekly-goal-fill"></div></div>')
    parts.append('<div class="weekly-goal-text"><span id="weekly-goal-current">0 分钟</span> · <span id="weekly-goal-percent">0%</span> · <span id="weekly-goal-target">目标 3 小时</span></div>')
    parts.append('<div class="review-queue" id="review-queue" style="display:none"></div>')
    parts.append('</div>')
    parts.append('</div>')
    # Streak 热度图 (GitHub-style) — 过去 16 周
    parts.append('<div class="streak-heatmap" id="streak-heatmap"></div>')
    # 里程碑 / 成就
    parts.append('<div class="achievements" id="achievements"></div>')
    parts.append('</div>')

    # ---- 5 个 series 卡片 ----
    for book_idx, (book_slug, meta, chapters) in enumerate(books):
        icon_name = meta.get("icon", "book")
        color = meta.get("color", "#b08968")
        chap_count = len(chapters)
        book_chars = sum(count_words(p.read_text(encoding="utf-8")) for _, p in chapters)
        book_minutes = max(1, book_chars // 400)

        parts.append(
            f'<article class="overview-card" data-book="{book_slug}" '
            f'style="--book-color: {color}">'
        )
        parts.append('  <header class="overview-card-head">')
        parts.append(f'    <div class="overview-card-icon">{svg_icon(icon_name, size=28)}</div>')
        parts.append('    <div class="overview-card-meta">')
        parts.append(f'      <h2 class="overview-card-title">{meta["title"]}</h2>')
        parts.append(f'      <p class="overview-card-desc">{meta["description"]}</p>')
        parts.append(
            f'      <div class="overview-card-stats">'
            f'{chap_count} 章 · {book_chars:,} 字 · 约 {book_minutes} 分钟'
            f'</div>'
        )
        parts.append('    </div>')
        # 进度条（运行时由 JS 填宽度）
        parts.append(
            '    <div class="overview-card-progress">'
            '<div class="progress-bar"><div class="progress-bar-fill" data-book-fill="'
            + book_slug + '" style="width:0%"></div></div>'
            '<div class="progress-label" data-book-label="' + book_slug + '">0 / '
            + str(chap_count) + '</div>'
            '</div>'
        )
        parts.append('  </header>')

        # 章节列表
        parts.append('  <ol class="overview-chapters">')
        for chap_idx, (chap_slug, chap_path) in enumerate(chapters, 1):
            md_text = chap_path.read_text(encoding="utf-8")
            display_title = chapter_display_title(md_text, chap_slug)
            anchor = f"{book_slug}__{chap_slug}"
            chars = count_words(md_text)
            minutes = max(1, chars // 400)
            parts.append(
                f'    <li><a href="#{anchor}">'
                f'<span class="ov-ch-num">{chap_idx:02d}</span>'
                f'<span class="ov-ch-title">{display_title}</span>'
                f'<span class="ov-ch-time">~{minutes} 分钟</span>'
                f'<span class="ov-ch-marker" data-chapter="{anchor}"></span>'
                f'</a></li>'
            )
        parts.append('  </ol>')
        parts.append('</article>')

    # ============================================================
    # D2 学习路径 — 运行时由 JS 基于 reading history 生成
    #  - 老用户：个性化 5 章（in-progress / 同系列下一章 / 主题 RELATED / 7 天书签 / 7 天笔记）
    #  - 新用户（无 history）：按 priority 取前 5 系列的首章
    # ============================================================
    parts.append('<div class="learning-path" id="learning-path"></div>')

    # ============================================================
    # D3 每周回顾（运行时由 JS 填）
    # ============================================================
    parts.append('<div class="weekly-recap" id="weekly-recap">')
    parts.append('<div class="recap-tabs">')
    parts.append('<button class="recap-tab active" data-range="week">本周</button>')
    parts.append('<button class="recap-tab" data-range="month">本月</button>')
    parts.append('<button class="recap-tab" data-range="year">今年</button>')
    parts.append('<button class="recap-export" id="recap-export" title="复制 Markdown 摘要">复制</button>')
    parts.append('</div>')
    parts.append('<div class="recap-summary" id="recap-summary"></div>')
    parts.append('<div class="weekly-grid" id="weekly-grid"></div>')
    parts.append('</div>')

    # ============================================================
    # D4 系列对比表
    # ============================================================
    parts.append('<div class="series-compare">')
    parts.append('<h2 class="section-h2">系列对比</h2>')
    parts.append('<p class="section-desc">10 个系列的难度、篇幅、适合谁。先看这张表选你的下一步。</p>')
    parts.append('<div class="compare-table-wrap">')
    parts.append('<table class="compare-table">')
    parts.append('<thead><tr><th>系列</th><th>难度</th><th>章节</th><th>字数</th><th>预计</th><th>适合谁</th></tr></thead>')
    parts.append('<tbody>')
    AUDIENCE = {
        "multi-agent": "做 multi-agent 系统的工程师",
        "llm-prompt": "所有用 LLM 的人",
        "crewai": "想用框架快速搭建 agent 的人",
        "rag": "做知识库 / 文档问答的工程师",
        "harness-engineering": "严肃做 agent 基础设施的人",
        "agent-cost": "关心成本和性能上限的人",
        "indie-ai-product": "独立开发 / 产品经理",
        "context-engineering": "做长 context agent 的人",
        "agent-skills": "想给 LLM 装可复用能力的人",
        "claude-code": "用 Claude Code / CLI 的人",
        "vibe-coding": "想用自然语言写代码的非程序员",
        "a2a-multi-agent": "做多 agent 协作架构的人",
        "memory-architecture": "做长期记忆 / RAG 的人",
        "embodied-agent": "机器人 / 具身智能研究者",
        "ai-content-economy": "创作者 / 内容运营",
        "codex-cases": "用 Codex 写代码的人",
        "cn-codex": "用国产 AI 编程工具的人",
    }
    for slug, meta, chapters in books:
        chars = sum(count_words(p.read_text(encoding="utf-8")) for _, p in chapters)
        mins = max(1, chars // 400)
        level = meta.get("level", 3)
        level_dots = "●" * level + "○" * (5 - level)
        audience = AUDIENCE.get(slug, "")
        # 章节展开列表
        chap_items = []
        for ci, (cs, cp) in enumerate(chapters, 1):
            md = cp.read_text(encoding="utf-8")
            ctitle = chapter_display_title(md, cs)
            cchars = count_words(md)
            cmins = max(1, cchars // 400)
            chap_items.append(
                f'<li><a href="#{slug}__{cs}"><span class="compare-ch-num">{ci:02d}</span>'
                f'<span class="compare-ch-title">{ctitle}</span>'
                f'<span class="compare-ch-time">{cmins} 分钟</span></a></li>'
            )
        parts.append(
            f'<tr class="compare-row" data-slug="{slug}">'
            f'<td data-label="系列">'
            f'<button class="compare-expand" data-target="ch-{slug}" aria-label="展开章节">+</button>'
            f'<a href="#{slug}__{chapters[0][0]}" class="compare-book">'
            f'<span class="compare-icon" style="color:{meta.get("color","#b08968")}">{svg_icon(meta.get("icon","book"), size=16)}</span>'
            f'{meta["title"]}'
            f'</a></td>'
            f'<td class="compare-level" data-level="{level}" data-label="难度"><span class="compare-dots">{level_dots}</span></td>'
            f'<td data-label="章节">{len(chapters)}</td>'
            f'<td data-label="字数">{chars:,}</td>'
            f'<td data-label="预计">{mins} 分钟</td>'
f'<td data-label="适合谁">{audience}</td>'
f'</tr>'
            f'<tr class="compare-chapters" id="ch-{slug}" hidden><td colspan="6"><ul class="compare-ch-list">'
            + ''.join(chap_items) + '</ul></td></tr>'
        )
    parts.append('</tbody></table>')
    parts.append('</div>')
    parts.append('</section>')
    return "\n".join(parts)


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
    html = markdown.markdown(
        md_text,
        extensions=["fenced_code", "tables", "nl2br", "sane_lists", "toc"],
    )
    # 长代码块 (>10 行) 自动加行号
    import re as _re_ln
    def _add_lines(m):
        body = m.group(3)
        if body.count("\n") < 10:
            return m.group(0)
        lines = body.split("\n")
        if lines and lines[-1] == "":
            lines = lines[:-1]
        new_body = "\n".join(f'<span class="line"><span class="ln"></span>{ln}</span>' for ln in lines)
        # 从 <code class="language-X"> 提取 X，拼到 pre 的 class
        code_attrs = m.group(2) or ''
        lang_match = _re_ln.search(r'class="language-([A-Za-z0-9_+-]+)"', code_attrs)
        lang = lang_match.group(1) if lang_match else ''
        lang_cls = (' ' + lang) if lang else ''
        pre_attrs = m.group(1) or ''
        return f'<pre{pre_attrs} class="with-lines{lang_cls}"><code class="language-{lang}">{new_body}\n</code></pre>' if lang else f'<pre{pre_attrs} class="with-lines"><code>{new_body}\n</code></pre>'
    html = _re_ln.sub(r'<pre([^>]*)>\s*<code([^>]*)>([\s\S]*?)</code>\s*</pre>', _add_lines, html)
    return html


def extract_toc(content_html: str) -> list[dict]:
    """从已渲染的 HTML 提取 h2/h3，生成章节内 TOC。

    markdown.toc 扩展给 heading 加了 id="..." 属性。返回:
    [{"level": 2, "text": "通信的 3 个层次", "id": "通信-的-3-个-层次"}, ...]
    """
    import re as _re
    items = []
    for m in _re.finditer(r'<(h[23])[^>]*\bid="([^"]+)"[^>]*>([^<]+)</\1>', content_html):
        level = int(m.group(1)[1])
        text = _re.sub(r"<[^>]+>", "", m.group(3)).strip()
        if not text:
            continue
        items.append({"level": level, "text": text, "id": m.group(2)})
    return items


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
    font-family: var(--font-body, "Source Han Serif SC", "Source Han Serif CN", "Noto Serif CJK SC", "Songti SC", "STSong", Charter, Georgia, "Times New Roman", serif);
    font-size: var(--font-base);
    line-height: 1.85;
    -webkit-font-smoothing: antialiased;
    transition: background-color .35s ease, color .35s ease;
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

body.sepia {
    --bg: #f4ecd8;
    --bg-soft: #ebe2c7;
    --text: #3d2e1c;
    --text-soft: #6b5536;
    --text-faint: #99805a;
    --accent: #8b5a2b;
    --accent-soft: rgba(139, 90, 43, 0.15);
    --border: #d8c89a;
    --code-bg: #ebe2c7;
    --link: #6b3e0e;
    --done: #6b7a3e;
}

body.green {
    --bg: #cce8cf;
    --bg-soft: #b5d6b8;
    --text: #1f3a1f;
    --text-soft: #3e5e3e;
    --text-faint: #6a8a6a;
    --accent: #3d6b3d;
    --accent-soft: rgba(61, 107, 61, 0.18);
    --border: #94c095;
    --code-bg: #b5d6b8;
    --link: #2a5a2a;
    --done: #5a8a5a;
}

/* 字体族 */
:root { --font-serif: 'Source Serif Pro', 'Source Han Serif SC', 'Noto Serif CJK SC', 'Songti SC', Georgia, 'Times New Roman', serif; }
:root { --font-sans: 'Inter', -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Microsoft YaHei', 'Hiragino Sans GB', sans-serif; }
:root { --font-mono: 'JetBrains Mono', 'Fira Code', 'Cascadia Code', 'Source Code Pro', Consolas, Menlo, monospace; }
body.font-serif { --font-body: var(--font-serif); }
body.font-sans  { --font-body: var(--font-sans); }
body.font-mono  { --font-body: var(--font-mono); }

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
    width: 400px;
    max-width: calc(100vw - 32px);
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
/* 工具栏内的设置面板：2 行 × 2 组（字号/宽度，字体/主题） */
.toolbar-grid {
    padding: 10px 12px 6px;
    display: flex;
    flex-direction: column;
    gap: 8px;
}
.t-row {
    display: flex;
    align-items: stretch;
    gap: 10px;
}
.t-group {
    display: flex;
    align-items: center;
    gap: 8px;
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 6px 6px 6px 12px;
    min-width: 0;
    flex: 1 1 0;
}
.t-lbl {
    font-size: 11px;
    color: var(--text-faint);
    letter-spacing: 0.8px;
    flex-shrink: 0;
    min-width: 28px;
    text-align: left;
    text-transform: uppercase;
    font-weight: 500;
}
.t-btns {
    display: flex;
    gap: 4px;
    flex: 1;
    min-width: 0;
}
.opt-btn {
    flex: 1;
    min-width: 0;
    padding: 6px 10px;
    background: transparent;
    border: 1px solid transparent;
    border-radius: 4px;
    color: var(--text-soft);
    font-size: 13px;
    line-height: 1.3;
    cursor: pointer;
    text-align: center;
    transition: background .12s, color .12s;
    white-space: nowrap;
}
.opt-btn:hover { color: var(--text); background: var(--bg-soft); }
.opt-btn.active {
    background: var(--accent);
    color: var(--bg);
    border-color: var(--accent);
}
.toolbar-section .active,
button.active {
    background: var(--accent);
    color: var(--bg);
    border-color: var(--accent);
}

/* 阅读宽度 — 只影响 chapter-content（章节正文），不影响右侧 TOC */
body.width-narrow .chapter-content { max-width: 580px; }
body.width-medium .chapter-content { max-width: 700px; }
body.width-wide .chapter-content { max-width: 880px; }
.chapter-content { max-width: 700px; transition: max-width .25s ease; }

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
    transition: background-color .35s ease, border-color .35s ease;
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

/* 知识问答 — sidebar 按钮 + modal */
.kb-launcher {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    width: calc(100% - 32px);
    margin: 16px 16px 12px;
    padding: 10px 14px;
    border-radius: 8px;
    background: var(--bg-soft);
    border: 1px solid var(--border);
    color: var(--text);
    font-size: 13px;
    font-weight: 500;
    cursor: pointer;
    transition: border-color .15s, background .15s;
}
.kb-launcher:hover {
    border-color: var(--accent);
    background: var(--bg);
}
.kb-modal {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.5);
    display: none;
    align-items: flex-start;
    justify-content: center;
    z-index: 9999;
    padding-top: 10vh;
}
.kb-modal.visible { display: flex; }
.kb-modal-inner {
    width: 640px;
    max-width: 92vw;
    max-height: 78vh;
    background: var(--bg);
    border-radius: 12px;
    border: 1px solid var(--border);
    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.25);
    display: flex;
    flex-direction: column;
    overflow: hidden;
}
.kb-modal-header {
    padding: 18px 22px 12px;
    position: relative;
    border-bottom: 1px solid var(--border);
}
.kb-modal-header h3 { margin: 0; font-size: 16px; font-weight: 600; }
.kb-modal-desc { margin: 6px 0 0; font-size: 12px; color: var(--text-soft); }
.kb-close {
    position: absolute;
    top: 14px;
    right: 14px;
    background: none;
    border: none;
    font-size: 22px;
    cursor: pointer;
    color: var(--text-soft);
    line-height: 1;
    padding: 4px 8px;
}
.kb-close:hover { color: var(--text); }
.kb-input-row {
    display: flex;
    gap: 8px;
    padding: 14px 22px;
    border-bottom: 1px solid var(--border);
}
.kb-input {
    flex: 1;
    padding: 10px 14px;
    border: 1px solid var(--border);
    border-radius: 8px;
    background: var(--bg-soft);
    color: var(--text);
    font-size: 14px;
    font-family: inherit;
}
.kb-input:focus { outline: none; border-color: var(--accent); }
.kb-search-btn {
    display: flex;
    align-items: center;
    gap: 4px;
    padding: 0 16px;
    background: var(--accent);
    color: var(--bg);
    border: none;
    border-radius: 8px;
    cursor: pointer;
    font-size: 13px;
    font-weight: 500;
    font-family: inherit;
}
.kb-search-btn:hover { opacity: 0.9; }
.kb-options {
    padding: 0 22px 12px;
    border-bottom: 1px solid var(--border);
}
.kb-toggle {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    cursor: pointer;
    font-size: 12px;
    color: var(--text-soft);
    user-select: none;
}
.kb-toggle input { cursor: pointer; }
.kb-toggle-hint { color: var(--text-faint); font-size: 11px; }
.kb-results {
    flex: 1;
    overflow-y: auto;
    padding: 8px 0;
}
.kb-empty {
    text-align: center;
    color: var(--text-soft);
    padding: 32px 22px;
    font-size: 13px;
    line-height: 1.6;
}
.kb-loading {
    text-align: center;
    color: var(--text-soft);
    padding: 32px 22px;
    font-size: 13px;
}
.kb-result {
    display: block;
    padding: 14px 22px;
    text-decoration: none;
    color: var(--text);
    border-bottom: 1px solid var(--border);
    transition: background .12s;
}
.kb-result:last-child { border-bottom: none; }
.kb-result:hover { background: var(--bg-soft); }
.kb-result-meta {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 6px;
    flex-wrap: wrap;
}
.kb-result-book {
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.4px;
    padding: 2px 8px;
    border-radius: 4px;
    background: var(--bg-soft);
    border: 1px solid var(--border);
}
.kb-result-chapter { font-size: 13px; font-weight: 500; }
.kb-result-score {
    margin-left: auto;
    font-size: 11px;
    color: var(--text-faint);
    font-variant-numeric: tabular-nums;
}
.kb-result-text {
    font-size: 13px;
    line-height: 1.65;
    color: var(--text-soft);
}
.kb-result-text mark {
    background: rgba(180, 130, 50, 0.18);
    color: var(--text);
    padding: 1px 2px;
    border-radius: 2px;
}
/* Q&A 搜索建议下拉 */
.kb-suggestions {
    max-height: 280px;
    overflow-y: auto;
    border: 1px solid var(--border);
    border-radius: 8px;
    background: var(--bg);
    margin: 0 0 12px 0;
    box-shadow: 0 4px 16px rgba(0,0,0,0.06);
}
.kb-sug-row {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 10px 14px;
    cursor: pointer;
    border-bottom: 1px solid var(--border);
    transition: background .12s;
}
.kb-sug-row:last-child { border-bottom: none; }
.kb-sug-row:hover { background: var(--bg-soft); }
.kb-sug-book {
    font-size: 11px;
    color: var(--text-faint);
    background: var(--bg-soft);
    padding: 2px 8px;
    border-radius: 3px;
    flex-shrink: 0;
    max-width: 140px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}
.kb-sug-title {
    font-size: 13px;
    color: var(--text);
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}
/* Q&A 搜索历史 */
.kb-history-label {
    font-size: 11px;
    color: var(--text-faint);
    text-transform: uppercase;
    letter-spacing: 1px;
    padding: 12px 22px 6px;
}
.kb-history-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 10px 22px;
    cursor: pointer;
    border-bottom: 1px solid var(--border);
    transition: background .12s;
}
.kb-history-row:hover { background: var(--bg-soft); }
.kb-history-row:last-child { border-bottom: none; }
.kb-history-q {
    font-size: 13px;
    color: var(--text);
}
.kb-history-x {
    width: 22px;
    height: 22px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 999px;
    color: var(--text-faint);
    font-size: 14px;
    line-height: 1;
}
.kb-history-x:hover { background: var(--bg); color: var(--text); }
/* Q&A 跳章节时的黄色闪高亮 (2.5s 后自动拆掉) */
@keyframes kb-flash {
    0% { background: rgba(255, 215, 0, 0.85); }
    100% { background: rgba(255, 215, 0, 0); }
}
mark.kb-jump-flash {
    background: rgba(255, 215, 0, 0.85);
    color: inherit;
    padding: 2px 4px;
    border-radius: 3px;
    animation: kb-flash 2.5s ease-out forwards;
}

/* 首次访问引导 */
.welcome-modal {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.6);
    z-index: 99999;
    display: flex;
    align-items: center;
    justify-content: center;
}
.welcome-inner {
    background: var(--bg);
    border-radius: 16px;
    border: 1px solid var(--border);
    padding: 32px 36px 24px;
    max-width: 640px;
    width: 92vw;
    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
}
.welcome-hero h2 {
    margin: 0 0 8px;
    font-size: 22px;
    font-weight: 600;
}
.welcome-desc {
    margin: 0 0 24px;
    font-size: 14px;
    color: var(--text-soft);
    line-height: 1.6;
}
.welcome-tags {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-bottom: 16px;
}
.welcome-tag {
    padding: 8px 14px;
    border-radius: 999px;
    border: 1px solid var(--border);
    background: var(--bg-soft);
    color: var(--text);
    font-size: 13px;
    cursor: pointer;
    transition: all .15s;
    font-family: inherit;
}
.welcome-tag:hover {
    border-color: var(--accent);
    transform: translateY(-1px);
}
.welcome-tag.selected {
    background: var(--accent);
    color: var(--bg);
    border-color: var(--accent);
}
.welcome-hint {
    font-size: 12px;
    color: var(--text-soft);
    margin: 0 0 20px;
}
.welcome-actions {
    display: flex;
    justify-content: space-between;
    gap: 12px;
}
.welcome-skip {
    background: none;
    border: none;
    color: var(--text-soft);
    cursor: pointer;
    font-size: 13px;
    padding: 8px 12px;
    font-family: inherit;
}
.welcome-skip:hover { color: var(--text); }
.welcome-go {
    background: var(--accent);
    color: var(--bg);
    border: none;
    padding: 10px 20px;
    border-radius: 8px;
    font-size: 14px;
    font-weight: 500;
    cursor: pointer;
    font-family: inherit;
}
.welcome-go:disabled {
    opacity: 0.4;
    cursor: not-allowed;
}
.welcome-go:hover:not(:disabled) { opacity: 0.9; }
.welcome-results {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.7);
    z-index: 99999;
    display: flex;
    align-items: center;
    justify-content: center;
}
.welcome-results-inner {
    background: var(--bg);
    border-radius: 16px;
    padding: 28px 32px;
    max-width: 600px;
    width: 92vw;
    max-height: 80vh;
    overflow-y: auto;
    border: 1px solid var(--border);
}
.welcome-results-inner h3 {
    margin: 0 0 16px;
    font-size: 16px;
    font-weight: 600;
}
.welcome-results-list {
    display: flex;
    flex-direction: column;
    gap: 10px;
    margin-bottom: 20px;
}
.welcome-result-item {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px 14px;
    background: var(--bg-soft);
    border: 1px solid var(--border);
    border-radius: 8px;
    text-decoration: none;
    color: var(--text);
    transition: border-color .15s;
}
.welcome-result-item:hover { border-color: var(--accent); }
.welcome-result-step {
    width: 24px;
    height: 24px;
    border-radius: 999px;
    background: var(--accent);
    color: var(--bg);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 12px;
    font-weight: 600;
    flex-shrink: 0;
}
.welcome-result-body { flex: 1; }
.welcome-result-title { font-size: 14px; font-weight: 500; }
.welcome-result-book { font-size: 12px; color: var(--text-soft); margin-top: 2px; }
.welcome-close {
    width: 100%;
    padding: 10px;
    background: var(--accent);
    color: var(--bg);
    border: none;
    border-radius: 8px;
    font-size: 14px;
    font-weight: 500;
    cursor: pointer;
    font-family: inherit;
}
.welcome-close:hover { opacity: 0.9; }
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
.bookshelf .book-group.current-book .book-title-text { color: var(--accent); font-weight: 600; }
.bookshelf .book-group.current-book .book-icon { color: var(--accent); }
.bookshelf .book-group.current-book > .book-header { position: relative; }
.bookshelf .book-group.current-book > .book-header::before {
    content: "";
    position: absolute;
    left: -16px;
    top: 4px;
    bottom: 4px;
    width: 3px;
    background: var(--accent);
    border-radius: 2px;
}

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

.book-chevron {
    flex-shrink: 0;
    color: var(--text-faint);
    transition: transform 0.2s ease;
}

.book-header.collapsed .book-chevron { transform: rotate(-90deg); }

.book-progress-bar {
    height: 2px;
    background: var(--border);
    border-radius: 1px;
    margin: 6px 0 4px 28px;
    overflow: hidden;
    max-width: 220px;
}
.book-progress-bar-fill {
    height: 100%;
    background: var(--accent);
    transition: width 0.3s ease;
}
.book-progress-label {
    font-size: 10px;
    color: var(--text-faint);
    margin: 0 0 4px 28px;
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

/* ============================================================
   Homepage TOC (overview section)
   ============================================================ */
.overview {
    padding: 80px 20px 60px 20px;
    max-width: 920px;
    margin: 0 auto;
}

.overview-hero {
    text-align: center;
    padding-bottom: 50px;
    margin-bottom: 50px;
    border-bottom: 1px solid var(--border);
}

.overview-title {
    font-size: 2.4em;
    font-weight: 600;
    margin: 0 0 12px 0;
    letter-spacing: 2px;
    color: var(--text);
}

.overview-subtitle {
    font-size: 14px;
    color: var(--text-soft);
    font-family: Georgia, "Times New Roman", serif;
    font-style: italic;
    margin: 0 0 36px 0;
    text-indent: 0;
}

/* ============================================================
   Section 通用标题
   ============================================================ */
.section-h2 {
    font-size: 22px;
    font-weight: 500;
    color: var(--text);
    text-align: center;
    margin: 80px 0 8px;
    font-family: var(--font-body);
}
.section-desc {
    text-align: center;
    color: var(--text-faint);
    font-size: 14px;
    margin: 0 auto 32px;
    max-width: 600px;
}

/* ============================================================
   D2 编辑推荐 — 新人路线
   ============================================================ */
.recommended-path {
    max-width: 920px;
    margin: 0 auto;
    padding: 0 20px;
}
.rec-path-list {
    list-style: none;
    padding: 0;
    margin: 0;
    display: flex;
    flex-direction: column;
    gap: 10px;
}
.rec-path-item {
    display: grid;
    grid-template-columns: 36px 1fr;
    grid-template-rows: auto auto;
    column-gap: 16px;
    align-items: center;
    background: var(--bg-soft);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 16px 20px;
    transition: border-color .15s, transform .15s;
}
.rec-path-item:hover {
    border-color: var(--accent);
    transform: translateX(4px);
}
.rec-step {
    grid-row: 1 / 3;
    font-size: 20px;
    font-weight: 600;
    color: var(--accent);
    text-align: center;
    font-variant-numeric: tabular-nums;
}
.rec-link {
    display: flex;
    align-items: center;
    gap: 10px;
    text-decoration: none;
    color: var(--text);
    font-weight: 500;
}
.rec-link:hover .rec-title { color: var(--accent); }
.rec-icon { display: inline-flex; }
.rec-title { font-size: 15px; }
.rec-book {
    font-size: 11px;
    color: var(--text-faint);
    background: var(--bg);
    padding: 2px 8px;
    border-radius: 999px;
    border: 1px solid var(--border);
}
.rec-why {
    font-size: 13px;
    color: var(--text-soft);
    line-height: 1.6;
}

/* ============================================================
   D3 每周回顾
   ============================================================ */
.weekly-recap {
    max-width: 920px;
    margin: 0 auto;
    padding: 0 20px;
}
.recap-tabs {
    display: flex;
    gap: 4px;
    justify-content: center;
    margin-bottom: 14px;
}
.recap-tabs .recap-export {
    margin-left: auto;
    background: transparent;
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 4px 10px;
    font-size: 11px;
    color: var(--text-soft);
    cursor: pointer;
    transition: all .12s;
}
.recap-tabs .recap-export:hover {
    border-color: var(--accent);
    color: var(--accent);
}
.recap-tabs .recap-export.copied {
    background: var(--accent);
    color: var(--bg);
    border-color: var(--accent);
}
.recap-tab {
    background: transparent;
    border: none;
    padding: 8px 14px;
    font-size: 13px;
    color: var(--text-faint);
    cursor: pointer;
    font-family: inherit;
    border-bottom: 2px solid transparent;
    margin-bottom: -1px;
    transition: color 0.15s, border-color 0.15s;
}
.recap-tab:hover { color: var(--text); }
.recap-tab.active {
    color: var(--accent);
    border-bottom-color: var(--accent);
}
.recap-summary {
    font-size: 12.5px;
    color: var(--text-faint);
    margin-bottom: 8px;
    font-style: italic;
}
.recap-summary strong { color: var(--text); font-weight: 500; font-style: normal; }
.weekly-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    gap: 12px;
    background: var(--bg-soft);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 20px;
}
.weekly-cell {
    text-align: center;
}
.weekly-num {
    font-size: 24px;
    font-weight: 600;
    color: var(--accent);
    line-height: 1.2;
    font-variant-numeric: tabular-nums;
}
.weekly-lbl {
    font-size: 11px;
    color: var(--text-faint);
    margin-top: 4px;
    letter-spacing: 0.5px;
}
.weekly-empty {
    text-align: center;
    color: var(--text-faint);
    font-size: 13px;
    padding: 16px;
    font-style: italic;
}

/* ============================================================
   D4 系列对比表
   ============================================================ */
.series-compare {
    max-width: 1100px;
    margin: 0 auto;
    padding: 0 20px 80px;
}
.compare-table-wrap {
    overflow-x: auto;
    background: var(--bg-soft);
    border: 1px solid var(--border);
    border-radius: 8px;
}
.compare-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 14px;
}
.compare-table th {
    text-align: left;
    padding: 14px 16px;
    font-weight: 500;
    color: var(--text-faint);
    font-size: 12px;
    letter-spacing: 1px;
    text-transform: uppercase;
    border-bottom: 1px solid var(--border);
    background: var(--bg);
}
.compare-table td {
    padding: 14px 16px;
    border-bottom: 1px solid var(--border);
    color: var(--text);
    vertical-align: middle;
}
.compare-table tr:last-child td { border-bottom: none; }
.compare-table tr:hover td { background: var(--bg); }
.compare-table .compare-expand {
    width: 20px;
    height: 20px;
    border-radius: 50%;
    border: 1px solid var(--border);
    background: transparent;
    color: var(--text-soft);
    cursor: pointer;
    margin-right: 6px;
    font-size: 14px;
    line-height: 1;
    padding: 0;
    transition: all .12s;
}
.compare-table .compare-expand:hover { border-color: var(--accent); color: var(--accent); }
.compare-table .compare-expand.open { background: var(--accent); color: var(--bg); border-color: var(--accent); transform: rotate(45deg); }
.compare-table tr.compare-chapters td { padding: 0 12px 12px 36px; background: var(--bg-soft); }
.compare-table .compare-ch-list {
    list-style: none;
    padding: 0;
    margin: 0;
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 4px;
}
.compare-table .compare-ch-list li a {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px 10px;
    border-radius: 4px;
    text-decoration: none;
    color: var(--text);
    font-size: 12px;
    transition: background .12s;
}
.compare-table .compare-ch-list li a:hover { background: var(--bg); }
.compare-ch-num { color: var(--text-faint); font-family: Georgia, serif; min-width: 24px; }
.compare-ch-title { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.compare-ch-time { color: var(--text-faint); font-size: 11px; }

/* 系列对比表 - mobile 转卡片布局 */
@media (max-width: 640px) {
    .compare-table-wrap { background: transparent; border: none; border-radius: 0; }
    .compare-table thead { display: none; }
    .compare-table, .compare-table tbody, .compare-table tr, .compare-table td { display: block; width: 100%; }
    .compare-table tr {
        background: var(--bg-soft);
        border: 1px solid var(--border);
        border-radius: 8px;
        margin-bottom: 10px;
        padding: 14px 16px;
    }
    .compare-table td {
        padding: 4px 0;
        border-bottom: 1px dashed var(--border);
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 12px;
    }
    .compare-table td:last-child { border-bottom: none; }
    .compare-table td::before {
        content: attr(data-label);
        font-size: 11px;
        color: var(--text-faint);
        text-transform: uppercase;
        letter-spacing: 0.8px;
        flex-shrink: 0;
    }
    .compare-table td.compare-level { padding-top: 8px; border-top: 1px solid var(--border); }
}
.compare-book {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    text-decoration: none;
    color: var(--text);
    font-weight: 500;
}
.compare-book:hover { color: var(--accent); }
.compare-icon { display: inline-flex; }
.compare-dots { letter-spacing: 1px; font-size: 11px; }
.compare-level[data-level="1"] .compare-dots,
.compare-level[data-level="2"] .compare-dots { color: #16a34a; }
.compare-level[data-level="3"] .compare-dots { color: #d97706; }
.compare-level[data-level="4"] .compare-dots,
.compare-level[data-level="5"] .compare-dots { color: #dc2626; }
.compare-audience { color: var(--text-soft); font-size: 13px; }

/* 个性化推荐 */
.personal-recs { margin-top: 56px; }
.rec-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
    gap: 12px;
    margin-top: 16px;
}
.rec-card {
    display: flex;
    align-items: flex-start;
    gap: 12px;
    padding: 14px 16px;
    background: var(--bg-soft);
    border: 1px solid var(--border);
    border-left: 3px solid var(--book-color, var(--accent));
    border-radius: 8px;
    color: var(--text);
    text-decoration: none;
    transition: transform 0.15s, border-color 0.15s, box-shadow 0.15s;
}
.rec-card:hover {
    transform: translateY(-2px);
    border-color: var(--book-color, var(--accent));
    box-shadow: 0 6px 16px rgba(0, 0, 0, 0.08);
}
.rec-card-icon {
    flex-shrink: 0;
    width: 28px;
    height: 28px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--book-color, var(--accent));
    background: var(--bg);
    border-radius: 6px;
    margin-top: 2px;
}
.rec-card-body { flex: 1; min-width: 0; }
.rec-card-book {
    font-size: 11px;
    color: var(--text-faint);
    text-transform: uppercase;
    letter-spacing: 0.8px;
    margin-bottom: 2px;
}
.rec-card-title {
    font-size: 14px;
    font-weight: 500;
    color: var(--text);
    line-height: 1.4;
    margin-bottom: 6px;
    overflow: hidden;
    text-overflow: ellipsis;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
}
.rec-card-reason {
    font-size: 11.5px;
    color: var(--text-faint);
    line-height: 1.4;
    font-style: italic;
}

/* ============================================================
   个人数据看板
   ============================================================ */
.personal-dashboard {
    max-width: 920px;
    margin: 56px auto 0;
    padding: 0 20px;
}
.dashboard-title {
    font-size: 14px;
    font-weight: 500;
    color: var(--text-faint);
    text-align: center;
    letter-spacing: 4px;
    text-transform: uppercase;
    margin: 0 0 24px;
    font-style: normal;
}
.dashboard-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
    gap: 12px;
    margin-bottom: 16px;
}
.dashboard-card {
    background: var(--bg-soft);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 18px 12px;
    text-align: center;
    transition: transform .15s, border-color .15s;
}
.dashboard-card:hover {
    border-color: var(--accent);
    transform: translateY(-2px);
}
.d-num {
    font-size: 28px;
    font-weight: 600;
    color: var(--text);
    line-height: 1.2;
    font-family: var(--font-body);
    font-variant-numeric: tabular-nums;
}
.d-lbl {
    font-size: 12px;
    color: var(--text-faint);
    margin-top: 4px;
    letter-spacing: 0.5px;
}
.dashboard-streak {
    font-size: 12px;
    color: var(--text-faint);
    text-align: center;
    margin-top: 8px;
    min-height: 18px;
}
.dashboard-streak .flame {
    color: var(--accent);
    margin-right: 4px;
}

/* GitHub-style streak heatmap */
.streak-heatmap {
    margin: 8px auto 32px;
    max-width: 720px;
    padding: 14px 18px;
    background: var(--bg-soft);
    border: 1px solid var(--border);
    border-radius: 10px;
}
.streak-heatmap-title {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 12px;
    color: var(--text-soft);
    margin-bottom: 10px;
}
.streak-heatmap-title .left {
    font-weight: 600;
    color: var(--text);
    font-size: 13px;
}
.streak-heatmap-title .right {
    color: var(--text-faint);
    font-size: 11px;
}
.streak-heatmap-grid {
    display: flex;
    gap: 3px;
    overflow-x: auto;
    padding-bottom: 2px;
}
.streak-heatmap-col {
    display: flex;
    flex-direction: column;
    gap: 3px;
}
.streak-heatmap-cell {
    width: 12px;
    height: 12px;
    border-radius: 2px;
    background: var(--border);
    transition: transform .1s;
    cursor: default;
}
.streak-heatmap-cell:hover { transform: scale(1.4); }
.streak-heatmap-cell[data-level="0"] { background: var(--border); }
.streak-heatmap-cell[data-level="1"] { background: rgba(180, 130, 50, 0.25); }
.streak-heatmap-cell[data-level="2"] { background: rgba(180, 130, 50, 0.45); }
.streak-heatmap-cell[data-level="3"] { background: rgba(180, 130, 50, 0.7); }
.streak-heatmap-cell[data-level="4"] { background: var(--accent); }
.streak-heatmap-legend {
    display: flex;
    align-items: center;
    gap: 4px;
    font-size: 10px;
    color: var(--text-faint);
    margin-top: 8px;
    justify-content: flex-end;
}
.streak-heatmap-legend .cell {
    width: 10px;
    height: 10px;
    border-radius: 2px;
}
/* 里程碑 / 成就 */
.achievements {
    margin: 8px auto 32px;
    max-width: 720px;
    padding: 14px 18px;
    background: var(--bg-soft);
    border: 1px solid var(--border);
    border-radius: 10px;
}
.achievements-title {
    font-size: 13px;
    font-weight: 600;
    color: var(--text);
    margin-bottom: 12px;
}
.achievements-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
    gap: 8px;
}
.achievement {
    padding: 12px 10px;
    border-radius: 8px;
    background: var(--bg);
    border: 1px solid var(--border);
    text-align: center;
    transition: all .12s;
}
.achievement.locked { opacity: 0.45; }
.achievement:not(.locked):hover {
    border-color: var(--accent);
    transform: translateY(-1px);
}
.achievement .ac-icon {
    width: 36px;
    height: 36px;
    margin: 0 auto 6px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 50%;
    background: var(--bg-soft);
    color: var(--text-faint);
}
.achievement:not(.locked) .ac-icon {
    background: var(--accent);
    color: var(--bg);
}
.achievement .ac-icon svg { width: 22px; height: 22px; }
.achievement .ac-name {
    font-size: 12px;
    font-weight: 500;
    color: var(--text);
    margin-bottom: 2px;
}
.achievement.locked .ac-name { color: var(--text-faint); }
.achievement .ac-desc {
    font-size: 10px;
    color: var(--text-faint);
    line-height: 1.3;
}

/* 周阅读目标进度条 */
.weekly-goal {
    margin: 16px auto 32px;
    max-width: 480px;
    padding: 14px 18px;
    background: var(--bg-soft);
    border: 1px solid var(--border);
    border-radius: 10px;
}
.weekly-goal-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 10px;
}
.weekly-goal-title {
    font-size: 12px;
    font-weight: 600;
    color: var(--text-soft);
    letter-spacing: 1.2px;
    text-transform: uppercase;
}
.weekly-goal-edit {
    background: transparent;
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 3px 10px;
    font-size: 11px;
    color: var(--text-faint);
    cursor: pointer;
    font-family: inherit;
    transition: color 0.15s, border-color 0.15s;
}
.weekly-goal-edit:hover { color: var(--accent); border-color: var(--accent); }
.weekly-goal-bar {
    height: 8px;
    background: rgba(0, 0, 0, 0.06);
    border-radius: 4px;
    overflow: hidden;
    margin-bottom: 8px;
}
body.dark .weekly-goal-bar { background: rgba(255, 255, 255, 0.08); }
.weekly-goal-fill {
    height: 100%;
    background: linear-gradient(90deg, var(--accent), #d4a574);
    width: 0%;
    border-radius: 4px;
    transition: width 0.4s ease;
}
.weekly-goal-fill.complete {
    background: linear-gradient(90deg, #22c55e, #16a34a);
}
.weekly-goal-text {
    font-size: 12.5px;
    color: var(--text-soft);
    display: flex;
    justify-content: space-between;
    align-items: center;
}
.weekly-goal-text span:last-child { color: var(--text-faint); font-size: 12px; }

/* 今日复习 (间隔重复) */
.review-queue {
    margin: 14px auto 32px;
    max-width: 480px;
    padding: 12px 16px;
    background: var(--bg);
    border: 1px solid var(--accent);
    border-radius: 10px;
    display: flex;
    align-items: center;
    gap: 14px;
}
.review-queue-icon {
    flex-shrink: 0;
    width: 32px;
    height: 32px;
    background: var(--accent);
    color: #fff;
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
}
.review-queue-body { flex: 1; min-width: 0; }
.review-queue-title { font-size: 14px; font-weight: 600; color: var(--text); margin-bottom: 2px; }
.review-queue-desc { font-size: 12px; color: var(--text-faint); }
.review-queue-btn {
    flex-shrink: 0;
    background: var(--accent);
    color: #fff;
    border: none;
    padding: 6px 14px;
    border-radius: 5px;
    font-family: inherit;
    font-size: 13px;
    font-weight: 500;
    cursor: pointer;
}
.review-queue-btn:hover { filter: brightness(1.08); }

/* 复习全屏弹窗 */
.review-overlay { padding: 0; background: var(--bg); }
.review-container {
    width: 100%;
    height: 100vh;
    display: flex;
    flex-direction: column;
    background: var(--bg);
    color: var(--text);
}
.review-header {
    display: flex;
    align-items: center;
    gap: 16px;
    padding: 16px 28px;
    border-bottom: 1px solid var(--border);
}
.review-progress-bar {
    flex: 1;
    height: 6px;
    background: var(--bg-soft);
    border-radius: 3px;
    overflow: hidden;
}
.review-progress-fill {
    height: 100%;
    background: var(--accent);
    width: 0%;
    transition: width 0.3s;
}
.review-progress-text {
    font-size: 13px;
    color: var(--text-faint);
    font-family: ui-monospace, monospace;
    min-width: 60px;
    text-align: right;
}
.review-card-area {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 24px;
    overflow-y: auto;
}
.review-card {
    width: 100%;
    max-width: 640px;
    min-height: 320px;
    background: var(--bg-soft);
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 40px 44px;
    display: flex;
    flex-direction: column;
    justify-content: center;
    position: relative;
}
.review-card-hint {
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    color: var(--text-faint);
    margin-bottom: 24px;
    text-align: center;
}
.review-card-front {
    font-size: 22px;
    font-weight: 600;
    color: var(--text);
    line-height: 1.5;
    text-align: center;
    margin-bottom: 16px;
}
.review-card-source {
    font-size: 13px;
    color: var(--text-faint);
    text-align: center;
    margin-top: 16px;
}
.review-card-divider {
    height: 1px;
    background: var(--border);
    margin: 24px 0;
}
.review-card-back {
    font-size: 15.5px;
    line-height: 1.75;
    color: var(--text);
    white-space: pre-wrap;
    font-family: Georgia, serif;
}
.review-card-actions {
    display: flex;
    gap: 10px;
    justify-content: center;
    margin-top: 24px;
}
.review-show-btn {
    background: var(--accent);
    color: #fff;
    border: none;
    padding: 12px 36px;
    border-radius: 8px;
    font-family: inherit;
    font-size: 15px;
    font-weight: 500;
    cursor: pointer;
}
.review-show-btn:hover { filter: brightness(1.08); }
.review-grade-btn {
    flex: 1;
    background: var(--bg);
    border: 2px solid var(--border);
    border-radius: 8px;
    padding: 10px 8px;
    cursor: pointer;
    font-family: inherit;
    color: var(--text);
    transition: all 0.15s;
}
.review-grade-btn:hover { border-color: var(--accent); transform: translateY(-1px); }
.review-grade-btn .gg-label { font-size: 14px; font-weight: 500; display: block; }
.review-grade-btn .gg-interval { font-size: 11px; color: var(--text-faint); margin-top: 2px; }
.review-grade-btn.again { border-color: #ef4444; }
.review-grade-btn.again .gg-label { color: #ef4444; }
.review-grade-btn.hard { border-color: #f59e0b; }
.review-grade-btn.hard .gg-label { color: #f59e0b; }
.review-grade-btn.good { border-color: #10b981; }
.review-grade-btn.good .gg-label { color: #10b981; }
.review-grade-btn.easy { border-color: #3b82f6; }
.review-grade-btn.easy .gg-label { color: #3b82f6; }
.review-empty {
    text-align: center;
    padding: 60px 40px;
    color: var(--text-soft);
}
.review-empty h3 { font-size: 24px; margin: 0 0 12px; color: var(--text); }
.review-empty p { font-size: 14px; line-height: 1.6; margin: 0 0 20px; }
.review-summary {
    text-align: center;
    padding: 40px 32px;
    max-width: 480px;
    margin: 0 auto;
}
.review-summary h3 { font-size: 28px; margin: 0 0 12px; color: var(--text); }
.review-summary .score-num {
    font-size: 64px;
    font-weight: 700;
    background: linear-gradient(135deg, var(--accent), #d4a574);
    -webkit-background-clip: text;
    background-clip: text;
    -webkit-text-fill-color: transparent;
    line-height: 1;
    margin: 12px 0;
}
.review-summary .stats-row {
    display: flex;
    justify-content: center;
    gap: 32px;
    margin: 20px 0 28px;
}
.review-summary .stat-cell {
    text-align: center;
}
.review-summary .stat-cell .n { font-size: 22px; font-weight: 600; color: var(--text); }
.review-summary .stat-cell .l { font-size: 11px; color: var(--text-faint); text-transform: uppercase; letter-spacing: 0.8px; }
.review-next-due {
    font-size: 13px;
    color: var(--text-faint);
    margin-top: 12px;
}
body.dark .review-card { background: #1f1f24; border-color: #333; }
body.dark .review-grade-btn { background: #1f1f24; }

/* 章节分享按钮 */
.chapter-meta-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    flex-wrap: wrap;
    margin-bottom: 16px;
}
.chapter-meta-row .chapter-meta { margin-bottom: 0; }
.chapter-share-btn {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    margin-left: 12px;
    padding: 2px 10px;
    background: transparent;
    border: 1px solid var(--border);
    border-radius: 12px;
    font-size: 11.5px;
    color: var(--text-faint);
    cursor: pointer;
    font-family: inherit;
    vertical-align: middle;
    transition: color 0.15s, border-color 0.15s, background 0.15s;
}
.chapter-share-btn:hover { color: var(--accent); border-color: var(--accent); }
.chapter-share-btn.copied {
    color: #22c55e;
    border-color: #22c55e;
    background: rgba(34, 197, 94, 0.08);
}
.chapter-share-btn svg { display: block; }

/* TTS 朗读按钮 + 播放器 */
.chapter-tts-btn {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 2px 10px;
    background: transparent;
    border: 1px solid var(--border);
    border-radius: 12px;
    font-size: 11.5px;
    color: var(--text-faint);
    cursor: pointer;
    font-family: inherit;
    vertical-align: middle;
    transition: color 0.15s, border-color 0.15s, background 0.15s;
    margin-right: 6px;
}
.chapter-tts-btn:hover { color: var(--accent); border-color: var(--accent); }
.chapter-tts-btn.playing {
    color: #f59e0b;
    border-color: #f59e0b;
    background: rgba(245, 158, 11, 0.08);
}
.chapter-tts-btn svg { display: block; }
.chapter-tts-player {
    margin: 8px 0 0;
    padding: 0;
    background: var(--bg-soft, rgba(0,0,0,0.03));
    border: 1px solid var(--border);
    border-radius: 8px;
    overflow: hidden;
    transition: max-height 0.2s ease-out;
    max-height: 0;
}
.chapter-tts-player.open {
    max-height: 80px;
}
.chapter-tts-player audio {
    width: 100%;
    display: block;
    height: 50px;
    outline: none;
}
.chapter-tts-player audio::-webkit-media-controls-panel {
    background: transparent;
}

/* 周目标编辑弹窗 */
.weekly-goal-input {
    width: 100%;
    padding: 10px 14px;
    font-size: 16px;
    border: 1px solid var(--border);
    border-radius: 6px;
    background: var(--bg);
    color: var(--text);
    font-family: inherit;
    margin: 12px 0 4px;
    box-sizing: border-box;
}
.weekly-goal-input:focus { outline: 2px solid var(--accent); outline-offset: -1px; border-color: var(--accent); }
.weekly-goal-presets {
    display: flex;
    gap: 6px;
    margin-top: 8px;
    flex-wrap: wrap;
}
.weekly-goal-presets button {
    flex: 1;
    min-width: 50px;
    padding: 6px 0;
    background: var(--bg-soft);
    border: 1px solid var(--border);
    border-radius: 5px;
    font-size: 13px;
    color: var(--text);
    cursor: pointer;
    font-family: inherit;
}
.weekly-goal-presets button:hover { border-color: var(--accent); color: var(--accent); }
.weekly-goal-presets button.selected {
    background: var(--accent);
    color: #fff;
    border-color: var(--accent);
}
.modal-actions {
    display: flex;
    gap: 10px;
    justify-content: flex-end;
    margin-top: 18px;
}
.btn-secondary {
    background: var(--bg-soft);
    color: var(--text);
    border: 1px solid var(--border);
    padding: 8px 18px;
    border-radius: 6px;
    font-family: inherit;
    font-size: 14px;
    cursor: pointer;
}
.btn-secondary:hover { border-color: var(--accent); }

.overview-stats {    display: flex;
    justify-content: center;
    gap: 48px;
    flex-wrap: wrap;
    margin-bottom: 36px;
}

.overview-stat {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 6px;
}

.overview-stat .num {
    font-size: 2em;
    font-weight: 600;
    color: var(--accent);
    font-family: Georgia, serif;
    line-height: 1;
}

.overview-stat .lbl {
    font-size: 12px;
    color: var(--text-faint);
    letter-spacing: 2px;
    text-transform: uppercase;
}

.resume-carousel {
    margin: 18px auto 24px;
    max-width: 760px;
    padding: 0 4px;
}
.resume-carousel-track {
    display: flex;
    gap: 10px;
    overflow-x: auto;
    scroll-snap-type: x mandatory;
    -webkit-overflow-scrolling: touch;
    padding: 4px 2px 10px;
    scrollbar-width: thin;
}
.resume-carousel-track::-webkit-scrollbar { height: 4px; }
.resume-carousel-track::-webkit-scrollbar-thumb { background: var(--border); border-radius: 2px; }
.resume-card {
    flex: 0 0 auto;
    width: 260px;
    min-width: 260px;
    padding: 14px 18px;
    background: var(--accent-soft);
    border: 1px solid var(--border);
    border-radius: 10px;
    text-decoration: none;
    color: var(--text);
    display: flex;
    flex-direction: column;
    gap: 8px;
    scroll-snap-align: start;
    transition: all .18s;
    position: relative;
}
.resume-card:hover {
    background: var(--accent);
    color: var(--bg);
    border-color: var(--accent);
    transform: translateY(-1px);
    box-shadow: 0 6px 18px rgba(0,0,0,0.08);
}
.resume-card.primary { width: 300px; min-width: 300px; border-color: var(--accent); }
.resume-card-head {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 1.2px;
    color: var(--text-faint);
    font-weight: 600;
}
.resume-card:hover .resume-card-head { color: var(--bg); opacity: 0.85; }
.resume-card-head .dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--accent);
}
.resume-card.primary .resume-card-head .dot { animation: resume-pulse 2s ease-in-out infinite; }
@keyframes resume-pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }
.resume-card-book {
    font-size: 11px;
    color: var(--text-faint);
}
.resume-card:hover .resume-card-book { color: var(--bg); opacity: 0.7; }
.resume-card-title {
    font-size: 14px;
    font-weight: 600;
    line-height: 1.4;
    color: var(--text);
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
}
.resume-card:hover .resume-card-title { color: var(--bg); }
.resume-card-progress {
    height: 3px;
    background: var(--border);
    border-radius: 2px;
    overflow: hidden;
    margin-top: 2px;
}
.resume-card:hover .resume-card-progress { background: rgba(255,255,255,0.25); }
.resume-card-progress-fill {
    height: 100%;
    background: var(--accent);
    border-radius: 2px;
}
.resume-card:hover .resume-card-progress-fill { background: var(--bg); }
.resume-card-meta {
    font-size: 11px;
    color: var(--text-faint);
    display: flex;
    justify-content: space-between;
    align-items: center;
}
.resume-card:hover .resume-card-meta { color: var(--bg); opacity: 0.8; }
.resume-card .resume-arrow {
    position: absolute;
    top: 14px;
    right: 14px;
    color: var(--text-faint);
    transform: rotate(45deg);
}
.resume-card:hover .resume-arrow { color: var(--bg); }

.overview-card {
    margin-bottom: 48px;
    padding: 32px;
    background: var(--bg-soft);
    border: 1px solid var(--border);
    border-radius: 12px;
    border-left: 4px solid var(--book-color, var(--accent));
}

.overview-card-head {
    display: grid;
    grid-template-columns: auto 1fr auto;
    gap: 24px;
    align-items: start;
    margin-bottom: 24px;
    padding-bottom: 24px;
    border-bottom: 1px solid var(--border);
}

.overview-card-icon {
    color: var(--book-color, var(--accent));
    flex-shrink: 0;
    padding-top: 4px;
}

.overview-card-title {
    font-size: 1.4em;
    font-weight: 600;
    margin: 0 0 6px 0;
    color: var(--text);
    letter-spacing: 1px;
}

.overview-card-desc {
    font-size: 14px;
    color: var(--text-soft);
    margin: 0 0 8px 0;
    line-height: 1.6;
    text-indent: 0;
    font-style: italic;
}

.overview-card-stats {
    font-size: 12px;
    color: var(--text-faint);
    font-family: Georgia, serif;
}

.overview-card-progress {
    text-align: right;
    min-width: 140px;
}

.overview-card-progress .progress-bar {
    width: 120px;
    height: 6px;
    background: var(--border);
    border-radius: 3px;
    overflow: hidden;
    margin-bottom: 6px;
    margin-left: auto;
}

.overview-card-progress .progress-bar-fill {
    height: 100%;
    background: var(--book-color, var(--accent));
    transition: width 0.3s;
}

.overview-card-progress .progress-label {
    font-size: 12px;
    color: var(--text-faint);
    font-family: Georgia, serif;
}

.overview-chapters {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 4px 24px;
}

.overview-chapters li {
    min-width: 0;
}

.overview-chapters li a {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 8px 10px;
    color: var(--text);
    text-decoration: none;
    border-radius: 4px;
    text-indent: 0;
    font-size: 14px;
    line-height: 1.5;
    transition: background 0.1s;
    min-width: 0;
    overflow: hidden;
    max-width: 100%;
}

.overview-chapters li a:hover {
    background: rgba(0, 0, 0, 0.04);
}

.ov-ch-num {
    font-family: Georgia, serif;
    font-size: 12px;
    color: var(--text-faint);
    font-style: italic;
    min-width: 22px;
    text-align: right;
}

.ov-ch-title {
    flex: 1;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.ov-ch-time {
    flex-shrink: 0;
    font-size: 11px;
    color: var(--text-faint);
    font-family: Georgia, serif;
    font-style: italic;
    min-width: 50px;
    text-align: right;
}

.ov-ch-marker {
    flex-shrink: 0;
    width: 16px;
    height: 16px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    color: var(--text-faint);
}

.ov-ch-marker.is-done {
    color: var(--done);
}

.ov-ch-marker.is-progress {
    color: var(--accent);
}

/* overview-mode 切换：隐藏 chapters 和 book covers，只显示 overview */
body.overview-mode .book-cover,
body.overview-mode .chapter {
    display: none;
}

body.overview-mode .content {
    padding: 0;
}

@media (max-width: 640px) {
    .overview-stats { gap: 28px; }
    .overview-card { padding: 20px; }
    .overview-card-head {
        grid-template-columns: auto 1fr;
    }
    .overview-card-progress {
        grid-column: 1 / -1;
        text-align: left;
        margin-top: 12px;
    }
    .overview-card-progress .progress-bar {
        margin-left: 0;
    }
    .overview-chapters {
        grid-template-columns: 1fr;
    }
}

.chapter {
    margin-bottom: 200px;
    padding-bottom: 100px;
    border-bottom: 1px solid var(--border);
    text-align: justify;
}
.chapter-body {
    display: flex;
    align-items: flex-start;
    gap: 0;
}
/* Lazy-load 占位: 章节未加载时显示 */
.chapter-loading {
    flex: 1;
    padding: 80px 20px;
    text-align: center;
    color: var(--text-faint);
    font-size: 13px;
}
.chapter-loading::before {
    content: "";
    display: block;
    width: 24px;
    height: 24px;
    margin: 0 auto 12px;
    border: 2px solid var(--border);
    border-top-color: var(--accent);
    border-radius: 50%;
    animation: chapter-spin 0.8s linear infinite;
}
@keyframes chapter-spin {
    to { transform: rotate(360deg); }
}
.chapter-body.lazy-loaded .chapter-loading { display: none; }

.chapter:last-of-type { border-bottom: none; }

/* 章节顶部 ribbon (系列色 + icon + book 标题 + 章节号) */
.chapter-ribbon {
    display: flex;
    align-items: center;
    gap: 16px;
    max-width: 600px;
    margin: 0 auto 24px;
    padding: 12px 20px;
    background: linear-gradient(135deg, color-mix(in srgb, var(--book-color, var(--accent)) 12%, var(--bg-soft)), color-mix(in srgb, var(--book-color, var(--accent)) 4%, transparent));
    border-left: 3px solid var(--book-color, var(--accent));
    border-radius: 0 8px 8px 0;
}
.chapter-ribbon .ribbon-icon {
    color: var(--book-color, var(--accent));
    flex-shrink: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    width: 44px;
    height: 44px;
}
.chapter-ribbon .ribbon-icon svg {
    width: 32px;
    height: 32px;
}
.chapter-ribbon .ribbon-meta {
    display: flex;
    flex-direction: column;
    gap: 2px;
    min-width: 0;
}
.chapter-ribbon .ribbon-book {
    font-size: 13px;
    font-weight: 600;
    color: var(--text);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}
.chapter-ribbon .ribbon-num {
    font-family: Georgia, "Times New Roman", serif;
    font-size: 11px;
    color: var(--text-faint);
    letter-spacing: 2px;
}

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

/* 面包屑导航 */
.breadcrumb {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    font-size: 12px;
    color: var(--text-faint);
    margin: 0 0 18px 0;
    flex-wrap: wrap;
}
.breadcrumb a {
    color: var(--text-soft);
    text-decoration: none;
    padding: 3px 8px;
    border-radius: 4px;
    transition: all .15s;
}
.breadcrumb a:hover {
    color: var(--accent);
    background: var(--bg-soft);
}
.breadcrumb .bc-sep {
    color: var(--text-faint);
    font-size: 11px;
    opacity: 0.5;
}
.breadcrumb .bc-current {
    color: var(--text);
    font-weight: 500;
}

.chapter-meta {
    text-align: center;
    color: var(--text-faint);
    font-size: 13px;
    margin-bottom: 80px;
    font-style: italic;
    letter-spacing: 1px;
}

/* ============================================================
   难度标签
   ============================================================ */
.level-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 2px 10px;
    border-radius: 999px;
    background: var(--surface-2);
    font-style: normal;
    font-size: 12px;
    letter-spacing: 0.5px;
    color: var(--text-faint);
    margin-left: 8px;
    vertical-align: 2px;
}
.level-dots {
    font-size: 10px;
    letter-spacing: 1px;
}
.level-badge[data-level="1"] .level-dots,
.level-badge[data-level="2"] .level-dots {
    color: #16a34a;
}
.level-badge[data-level="3"] .level-dots {
    color: #d97706;
}
.level-badge[data-level="4"] .level-dots,
.level-badge[data-level="5"] .level-dots {
    color: #dc2626;
}
.level-name {
    font-weight: 500;
}

/* ============================================================
   章节顶部 progress 条
   ============================================================ */
.chap-progress {
    margin: 16px auto 28px;
    max-width: 480px;
}
.chap-progress-bar {
    height: 3px;
    background: var(--border);
    border-radius: 2px;
    overflow: hidden;
    margin-bottom: 8px;
}
.chap-progress-fill {
    height: 100%;
    background: linear-gradient(90deg, var(--accent) 0%, color-mix(in srgb, var(--accent) 70%, white) 100%);
    transition: width 0.3s ease;
}
.chap-progress-info {
    font-size: 12px;
    color: var(--text-faint);
    letter-spacing: 0.3px;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
}
.chap-progress-info b {
    color: var(--accent);
    font-weight: 600;
    font-style: normal;
}
.chap-progress-sep { opacity: 0.4; }

/* ============================================================
   系列导览（ch01 顶部）
   ============================================================ */
.series-intro {
    margin: 0 0 48px;
    padding: 24px 28px;
    background: var(--surface-2);
    border: 1px solid var(--border);
    border-left: 3px solid var(--accent);
    border-radius: 4px;
}
.series-intro-head {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 12px;
}
.series-intro-label {
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 2px;
    color: var(--accent);
    font-weight: 600;
}
.series-intro-count {
    font-size: 11px;
    color: var(--text-faint);
    font-family: Georgia, serif;
    font-style: italic;
}
.series-intro-toggle {
    margin-left: auto;
    background: transparent;
    border: 1px solid var(--border);
    color: var(--text-muted);
    font-size: 12px;
    padding: 4px 12px;
    border-radius: 4px;
    cursor: pointer;
    transition: all 0.15s ease;
}
.series-intro-toggle:hover {
    border-color: var(--accent);
    color: var(--accent);
}
.series-intro-toggle:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 2px;
}
.series-intro-desc {
    color: var(--text-muted);
    font-size: 15px;
    line-height: 1.7;
    margin: 0 0 16px;
}
.series-toc {
    list-style: none;
    padding: 0;
    margin: 0;
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 4px 24px;
}
.series-toc.collapsed { display: none; }
.series-toc li a {
    display: flex;
    align-items: baseline;
    gap: 10px;
    padding: 6px 0;
    text-decoration: none;
    color: var(--text);
    font-size: 14px;
    line-height: 1.4;
    transition: color 0.15s ease;
}
.series-toc li a:hover { color: var(--accent); }
.series-toc li a:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 2px;
    border-radius: 2px;
}
.series-toc-num {
    color: var(--text-faint);
    font-family: Georgia, serif;
    font-size: 12px;
    font-style: italic;
    min-width: 24px;
}
.series-toc-title { flex: 1; }
@media (max-width: 600px) {
    .series-toc { grid-template-columns: 1fr; }
}

.chapter-meta::before, .chapter-meta::after {
    content: "·";
    margin: 0 12px;
    color: var(--accent);
}

.chapter-content { font-feature-settings: "kern", "liga", "calt"; }

/* TL;DR 摘要卡 */
.tldr-card {
    background: linear-gradient(135deg, var(--accent-soft, #fdf6e3), transparent);
    border-left: 3px solid var(--accent, #b08968);
    padding: 14px 20px 16px;
    margin: 0 0 48px;
    border-radius: 0 8px 8px 0;
}
.tldr-label {
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 2px;
    color: var(--accent, #b08968);
    text-transform: uppercase;
    margin-bottom: 6px;
    font-style: normal;
}
.tldr-text {
    font-size: 15px;
    line-height: 1.75;
    color: var(--text);
    margin: 0;
    font-style: normal;
    text-indent: 0;
}
body.dark .tldr-card {
    background: linear-gradient(135deg, rgba(176, 137, 104, 0.12), transparent);
}

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

/* 交叉引用 — 「第 N 章」链接 */
.chapter-content a.chapter-ref {
    color: var(--accent);
    border-bottom: 1px dashed var(--accent);
    text-decoration: none;
    padding: 0 1px;
}
.chapter-content a.chapter-ref:hover {
    background: var(--accent-soft, rgba(176, 137, 104, 0.12));
    border-bottom-style: solid;
}

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
    position: relative;
}

.chapter-content pre code {
    background: transparent;
    color: var(--text);
    padding: 0;
    font-size: 100%;
}

/* 代码块：语言标签 + 复制按钮 */
.chapter-content pre .code-lang {
    position: absolute;
    top: 6px;
    left: 14px;
    font-size: 10px;
    letter-spacing: 1.5px;
    text-transform: uppercase;
    color: var(--text-faint);
    font-family: Georgia, serif;
    font-style: italic;
    opacity: 0.7;
    pointer-events: none;
    user-select: none;
}
.chapter-content pre .code-copy {
    position: absolute;
    top: 6px;
    right: 8px;
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 4px 10px;
    font-size: 11px;
    color: var(--text-soft);
    background: transparent;
    border: 1px solid transparent;
    border-radius: 4px;
    cursor: pointer;
    font-family: inherit;
    opacity: 0;
    transition: opacity 0.15s, background 0.15s, color 0.15s, border-color 0.15s;
}
.chapter-content pre:hover .code-copy { opacity: 1; }
.chapter-content pre .code-copy:hover {
    background: var(--bg-soft);
    border-color: var(--border);
    color: var(--text);
}
.chapter-content pre .code-copy:focus { opacity: 1; outline: none; }
.chapter-content pre .code-copy.copied {
    opacity: 1;
    color: var(--done);
    border-color: var(--done);
    background: transparent;
}
body.dark .chapter-content pre .code-copy:hover { background: #1f1f22; }

/* 代码跳转（Run/Explain） */
.chapter-content pre .code-jump {
    position: absolute;
    top: 8px;
    right: 76px;
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 4px 10px;
    background: var(--bg-soft);
    color: var(--text);
    border: 1px solid var(--border);
    border-radius: 4px;
    font-size: 11px;
    font-weight: 500;
    cursor: pointer;
    opacity: 0;
    transition: opacity .15s;
    text-decoration: none;
    font-family: var(--font-sans, -apple-system, sans-serif);
}
.chapter-content pre:hover .code-jump { opacity: 1; }
.chapter-content pre .code-jump:hover { background: var(--accent); color: var(--bg); border-color: var(--accent); }

/* 行号 */
.chapter-content pre.with-lines {
    padding-left: 56px;
    counter-reset: line;
    line-height: 1.55;
}
.chapter-content pre.with-lines code {
    line-height: 1.55;
    margin: 0;
    display: flex;
    flex-direction: column;
    white-space: normal;  /* 让 \n 文本节点不再产生行高 */
}
.chapter-content pre.with-lines .line {
    display: block;
    position: relative;
    line-height: 1.55;
    margin: 0;
    padding: 0;
    white-space: pre;  /* 单独保留缩进 */
}
.chapter-content pre.with-lines .ln {
    position: absolute;
    left: -48px;
    top: 0;
    width: 36px;
    text-align: right;
    color: var(--text-faint);
    font-size: 11px;
    user-select: none;
    pointer-events: none;
    border-right: 1px solid var(--border);
    padding-right: 8px;
    counter-increment: line;
}
.chapter-content pre.with-lines .ln::before {
    content: counter(line);
}
body.dark .chapter-content pre.with-lines .ln { color: #5a5a5e; border-right-color: #2a2a2e; }

/* Mermaid */
.mermaid {
    background: var(--bg-soft);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 20px;
    margin: 1.5em 0;
    text-align: center;
    overflow-x: auto;
}
body.dark .mermaid { background: #18181b; }

/* 图片 lightbox */
.lightbox {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.88);
    z-index: 9999;
    display: none;
    align-items: center;
    justify-content: center;
    flex-direction: column;
    padding: 40px 20px;
    box-sizing: border-box;
}
.lightbox.open { display: flex; }
.lightbox img {
    max-width: 100%;
    max-height: 80vh;
    object-fit: contain;
    box-shadow: 0 8px 40px rgba(0, 0, 0, 0.5);
    border-radius: 4px;
}
.lightbox-caption {
    color: #ccc;
    font-size: 13px;
    margin-top: 16px;
    text-align: center;
    max-width: 600px;
}
.lightbox-close {
    position: absolute;
    top: 20px;
    right: 28px;
    background: transparent;
    color: white;
    border: none;
    font-size: 32px;
    cursor: pointer;
    line-height: 1;
    padding: 0;
    width: 40px;
    height: 40px;
    opacity: 0.7;
    transition: opacity .15s;
}
.lightbox-close:hover { opacity: 1; }
.chapter-content img { max-width: 100%; }

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

/* 章节内目录（右侧 sticky） */
.chapter-toc {
    display: none;
    position: sticky;
    top: 80px;
    width: 220px;
    max-height: calc(100vh - 120px);
    overflow-y: auto;
    font-size: 12px;
    line-height: 1.6;
    flex-shrink: 0;
    margin-top: 60px;
    margin-left: 40px;
}
@media (min-width: 1200px) {
    .content { max-width: 1080px; }
    .chapter-toc { display: block; }
}
.chapter-toc .toc-title {
    color: var(--text-faint);
    font-size: 11px;
    letter-spacing: 2px;
    text-transform: uppercase;
    margin-bottom: 12px;
    padding-bottom: 8px;
    border-bottom: 1px dashed var(--border);
}
.chapter-toc .toc-list {
    list-style: none;
    padding: 0;
    margin: 0;
}
.chapter-toc .toc-list li {
    margin: 0;
}
.chapter-toc .toc-list a {
    display: block;
    color: var(--text-soft);
    text-decoration: none;
    padding: 4px 0 4px 10px;
    border-left: 2px solid transparent;
    transition: color 0.15s, border-color 0.15s;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}
.chapter-toc .toc-list a:hover { color: var(--text); }
.chapter-toc .toc-list a.active {
    color: var(--accent);
    border-left-color: var(--accent);
    font-weight: 600;
}
.chapter-toc .toc-list .toc-l3 a {
    padding-left: 24px;
    font-size: 11px;
}
body.dark .chapter-toc .toc-list a { color: #b0b0b4; }
body.dark .chapter-toc .toc-list a.active { color: var(--accent); }

.chapter-end::before { content: "———"; color: var(--accent); letter-spacing: 8px; }

/* 读完 CTA: 滚到章节末尾时底部弹 "继续读下一章" */
.next-chapter-cta {
    position: fixed;
    bottom: 24px;
    left: 50%;
    transform: translateX(-50%);
    background: var(--accent);
    color: var(--bg);
    padding: 12px 20px;
    border-radius: 999px;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.18);
    display: flex;
    align-items: center;
    gap: 12px;
    cursor: pointer;
    z-index: 100;
    font-size: 14px;
    font-weight: 500;
    max-width: 90vw;
    user-select: none;
    transition: transform 0.2s, opacity 0.2s;
    opacity: 0.95;
}
.next-chapter-cta:hover {
    transform: translateX(-50%) translateY(-2px);
    opacity: 1;
}
.next-cta-label {
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 1px;
    opacity: 0.7;
}
.next-cta-title {
    font-size: 14px;
    font-weight: 500;
    max-width: 280px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}
.next-cta-arrow {
    font-size: 18px;
    line-height: 1;
}

/* 章节底部"相关章节" */
.related-chapters {
    margin: 32px auto 24px;
    padding: 24px 0;
    max-width: 760px;
    border-top: 1px dashed var(--border);
}
.related-chapters h3 {
    font-size: 13px;
    color: var(--text-soft);
    text-transform: uppercase;
    letter-spacing: 1.5px;
    margin: 0 0 16px;
    font-weight: 600;
}
.related-tabs {
    display: flex;
    gap: 4px;
    margin: 0 0 14px 0;
}
.related-tabs .related-tab {
    padding: 4px 12px;
    background: transparent;
    border: 1px solid var(--border);
    border-radius: 4px;
    color: var(--text-soft);
    font-size: 12px;
    cursor: pointer;
    transition: all .12s;
}
.related-tabs .related-tab.active {
    background: var(--accent);
    color: var(--bg);
    border-color: var(--accent);
}
.related-graph {
    display: block;
    margin: 0 auto;
    max-width: 100%;
}
.related-graph a:hover circle { stroke: var(--text); stroke-width: 3; }

.related-chapters-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
    gap: 12px;
}
.related-card {
    display: flex;
    flex-direction: column;
    padding: 12px 14px;
    background: var(--bg-soft);
    border: 1px solid var(--border);
    border-radius: 8px;
    text-decoration: none;
    color: var(--text);
    transition: border-color .15s, transform .15s;
}
.related-card:hover {
    border-color: var(--accent);
    transform: translateY(-1px);
}
.related-card-book {
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-bottom: 4px;
}
.related-card-title {
    font-size: 13px;
    font-weight: 500;
    line-height: 1.4;
    margin-bottom: 6px;
}
.related-card-score {
    font-size: 10px;
    color: var(--text-faint);
    font-variant-numeric: tabular-nums;
}

/* ============================================================
   章节底部 prev/next 导航
   ============================================================ */
.chap-nav {
    display: flex;
    flex-direction: column;
    gap: 12px;
    margin: 48px auto 32px;
    max-width: 760px;
}
.chap-nav-link {
    display: grid;
    grid-template-columns: auto 1fr auto;
    align-items: center;
    gap: 14px;
    padding: 18px 22px;
    border: 1px solid var(--border);
    border-radius: 8px;
    text-decoration: none;
    color: var(--text);
    background: var(--surface);
    transition: border-color 0.15s ease, transform 0.15s ease, background 0.15s ease;
}
.chap-nav-link:hover {
    border-color: var(--accent);
    background: var(--surface-hover, var(--surface-2));
    transform: translateY(-1px);
}
.chap-nav-link:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 2px;
}
.chap-nav-prev {
    grid-template-columns: auto 1fr;
    color: var(--text-muted);
    font-size: 14px;
}
.chap-nav-prev .chap-nav-arrow { display: none; }
.chap-nav-next {
    border-color: var(--accent);
    background: linear-gradient(135deg, var(--surface) 0%, var(--surface-2) 100%);
    font-weight: 500;
}
.chap-nav-overview {
    text-align: center;
}
.chap-nav-label {
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    color: var(--text-faint);
    margin-right: 8px;
    white-space: nowrap;
}
.chap-nav-num {
    font-family: Georgia, 'Noto Serif SC', serif;
    font-size: 12px;
    color: var(--text-faint);
    white-space: nowrap;
    font-style: italic;
}
.chap-nav-title {
    color: var(--text);
    line-height: 1.5;
    font-size: 16px;
}
.chap-nav-prev .chap-nav-title { color: var(--text-muted); font-size: 14px; }
.chap-nav-next .chap-nav-title { color: var(--text); font-weight: 500; }
.chap-nav-arrow {
    font-size: 20px;
    color: var(--accent);
    margin-left: 8px;
}
@media (min-width: 720px) {
    .chap-nav-link { grid-template-columns: 1fr auto; }
    .chap-nav-prev { grid-template-columns: auto 1fr; }
}
@media (prefers-color-scheme: dark) {
    .chap-nav-next { background: linear-gradient(135deg, var(--surface) 0%, rgba(217, 119, 6, 0.08) 100%); }
}

/* ============================================================
   a11y: skip link, focus ring, reduced motion
   ============================================================ */
.skip-link {
    position: absolute;
    top: -100px;
    left: 16px;
    padding: 10px 16px;
    background: var(--accent);
    color: var(--bg);
    text-decoration: none;
    text-indent: 0;
    border-radius: 4px;
    font-size: 14px;
    font-weight: 600;
    z-index: 1000;
    transition: top 0.15s;
}
.skip-link:focus,
.skip-link:focus-visible {
    top: 16px;
    outline: 2px solid var(--text);
    outline-offset: 2px;
}

/* 键盘 focus ring — 鼠标点击不显示 */
*:focus { outline: none; }
*:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 2px;
    border-radius: 2px;
}
button:focus-visible,
a:focus-visible {
    outline-color: var(--accent);
}

/* 高对比度模式加深焦点 */
@media (prefers-contrast: more) {
    *:focus-visible {
        outline-width: 3px;
    }
}

/* 减弱动画 — OS 设置 / 系统级偏好 */
@media (prefers-reduced-motion: reduce) {
    *, *::before, *::after {
        animation-duration: 0.01ms !important;
        animation-iteration-count: 1 !important;
        transition-duration: 0.01ms !important;
        scroll-behavior: auto !important;
    }
    html { scroll-behavior: auto; }
}

/* ============================================================
   打印模式 — 用户打印单章节成书, 保留代码块高亮
   ============================================================ */
@media print {
    body { background: #fff !important; color: #000 !important; transition: none !important; font-size: 12pt; }
    .sidebar, .toolbar, .bookshelf-sidebar, .command-palette, .kb-modal,
    .selection-toolbar, .chapter-toc, .related-chapters, .completion-toggle,
    .chap-nav, .chapter-end, .chapter-share-btn, .chapter-tts-btn,
    .chapter-ribbon, .breadcrumb, .resume-carousel, .streak-heatmap,
    .weekly-recap, .series-compare, .achievements, .kb-launcher,
    .reading-progress, .navbar, .toast, .modal-backdrop {
        display: none !important;
    }
    .chapter { break-inside: avoid; page-break-before: always; padding: 0; max-width: 100%; }
    .chapter:first-of-type { page-break-before: avoid; }
    .chapter-content { max-width: 100% !important; }
    .chapter-title { font-size: 22pt !important; color: #000 !important; letter-spacing: 0 !important; }
    .tldr-card { border: 1px solid #999 !important; background: #f5f5f5 !important; padding: 8px !important; break-inside: avoid; }
    pre, code { white-space: pre-wrap !important; word-break: break-word !important; background: #f5f5f5 !important; color: #000 !important; border: 1px solid #ccc !important; }
    .chapter-content pre code { color: #000 !important; }
    .chapter-content pre .code-lang, .chapter-content pre .code-copy { display: none !important; }
    a { color: #000 !important; text-decoration: underline !important; }
    a[href^="http"]::after { content: " (" attr(href) ")"; font-size: 90%; color: #666; }
    h1, h2, h3, h4 { break-after: avoid; page-break-after: avoid; color: #000 !important; }
    pre, blockquote, table { break-inside: avoid; }
}

/* ============================================================
   开发者彩蛋热力图（5×? 触发）
   ============================================================ */
.dev-panel {
    position: fixed;
    top: 80px;
    right: 24px;
    width: 360px;
    max-height: calc(100vh - 120px);
    overflow: auto;
    background: var(--surface, #fff);
    border: 1px solid var(--border);
    border-radius: 8px;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.18);
    padding: 20px;
    z-index: 9999;
    opacity: 0;
    transform: translateY(-8px);
    pointer-events: none;
    transition: opacity 0.2s ease, transform 0.2s ease;
    font-family: 'Inter', system-ui, -apple-system, sans-serif;
}
.dev-panel.visible {
    opacity: 1;
    transform: translateY(0);
    pointer-events: auto;
}
.dev-panel-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 16px;
    padding-bottom: 12px;
    border-bottom: 1px solid var(--border);
}
.dev-panel-eyebrow {
    font-size: 10px;
    letter-spacing: 2px;
    color: var(--accent);
    font-weight: 600;
    margin-right: 8px;
    font-family: Georgia, serif;
    font-style: italic;
}
.dev-panel-title {
    font-size: 13px;
    color: var(--text);
    display: flex;
    align-items: baseline;
    gap: 8px;
}
.dev-panel-close {
    background: transparent;
    border: none;
    color: var(--text-faint);
    cursor: pointer;
    font-size: 22px;
    line-height: 1;
    padding: 0 4px;
    transition: color 0.15s ease;
}
.dev-panel-close:hover { color: var(--accent); }
.dev-panel-close:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
.dev-heatmap {
    display: flex;
    flex-direction: column;
    gap: 8px;
    margin-bottom: 16px;
}
.dev-row {
    display: flex;
    align-items: center;
    gap: 10px;
}
.dev-row-label {
    font-size: 10px;
    color: var(--text-faint);
    flex: 0 0 90px;
    text-align: right;
    line-height: 1.2;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}
.dev-row-cells {
    display: flex;
    gap: 3px;
    flex: 1;
}
.dev-cell {
    flex: 1;
    height: 14px;
    background: var(--border);
    border-radius: 2px;
    transition: transform 0.1s ease;
    display: block;
}
.dev-cell:hover { transform: scale(1.4); z-index: 1; }
.dev-cell.done { background: #10b981; }
.dev-cell.progress { background: #f59e0b; }
.dev-cell.unread { background: var(--border); }
.dev-panel-legend {
    display: flex;
    flex-wrap: wrap;
    gap: 12px;
    font-size: 11px;
    color: var(--text-faint);
    padding-top: 12px;
    border-top: 1px solid var(--border);
}
.dev-panel-legend span {
    display: flex;
    align-items: center;
    gap: 4px;
}
.dev-legend-cell {
    width: 10px;
    height: 10px;
    border-radius: 2px;
    display: inline-block;
}
.dev-legend-cell.done { background: #10b981; }
.dev-legend-cell.progress { background: #f59e0b; }
.dev-legend-cell.unread { background: var(--border); }
.dev-panel-hint {
    margin-left: auto;
    color: var(--text-faint);
    font-style: italic;
    font-family: Georgia, serif;
}

@media (max-width: 900px) {
    .sidebar { transform: translateX(-300px); }
    body:not(.sidebar-collapsed) .sidebar { transform: translateX(0); }
    body:not(.sidebar-collapsed) .sidebar-toggle { left: 8px; right: auto; background: var(--accent); color: #fff; border-color: var(--accent); }
    .content { padding: 80px 24px; max-width: 100%; }
    .chapter-title { font-size: 1.8em; }
    .chapter-num { font-size: 12px; letter-spacing: 5px; }
    .book-cover h1 { font-size: 1.8em; }
    .toolbar { top: 8px; right: 8px; }
    #more-btn { width: 36px; height: 36px; }
    .toolbar-menu { min-width: 320px; max-width: calc(100vw - 32px); }
    .sidebar-toggle { top: 8px; left: 8px; right: auto; }
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

.notes-search {
    width: 100%;
    padding: 8px 12px;
    margin: 0 0 10px 0;
    border: 1px solid var(--border);
    border-radius: 6px;
    background: var(--bg);
    color: var(--text);
    font-size: 13px;
    font-family: inherit;
}
.notes-search:focus { outline: none; border-color: var(--accent); }
.notes-list mark {
    background: rgba(180, 130, 50, 0.25);
    color: var(--text);
    padding: 0 1px;
    border-radius: 2px;
}
.notes-filter {
    display: flex;
    gap: 4px;
    flex-wrap: wrap;
    margin-bottom: 10px;
}
.notes-filter .nf-chip {
    padding: 3px 10px;
    border: 1px solid var(--border);
    border-radius: 12px;
    background: transparent;
    color: var(--text-soft);
    font-size: 11px;
    cursor: pointer;
    transition: all .12s;
}
.notes-filter .nf-chip:hover { border-color: var(--accent); color: var(--text); }
.notes-filter .nf-chip.active {
    background: var(--accent);
    color: var(--bg);
    border-color: var(--accent);
}
.notes-filter .nf-chip[data-tag="重要"]::before { content: "●"; color: var(--hl-yellow); margin-right: 4px; }
.notes-filter .nf-chip[data-tag="todo"]::before { content: "●"; color: var(--hl-green); margin-right: 4px; }
.notes-filter .nf-chip[data-tag="问题"]::before { content: "●"; color: var(--hl-blue); margin-right: 4px; }
.notes-filter .nf-chip[data-tag="想法"]::before { content: "●"; color: var(--hl-pink); margin-right: 4px; }
.notes-filter .nf-chip.active::before { color: var(--bg); }
.note-item .note-tag {
    display: inline-block;
    padding: 1px 6px;
    border-radius: 3px;
    font-size: 10px;
    margin-right: 6px;
    font-weight: 500;
}
.note-tag[data-tag="重要"] { background: var(--hl-yellow); color: #6b5a00; }
.note-tag[data-tag="todo"] { background: var(--hl-green); color: #2c5a2c; }
.note-tag[data-tag="问题"] { background: var(--hl-blue); color: #1e4d80; }
.note-tag[data-tag="想法"] { background: var(--hl-pink); color: #802a5e; }

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

/* 已完成对勾由 JS 注入 SVG，CSS 不再重复 ::after */

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

/* Anki 导出帮助弹窗 */
.modal-overlay {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.5);
    z-index: 1000;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 24px;
    opacity: 0;
    pointer-events: none;
    transition: opacity 0.2s;
}
.modal-overlay.visible { opacity: 1; pointer-events: auto; }
.modal-content {
    background: var(--bg);
    color: var(--text);
    border-radius: 12px;
    padding: 28px 32px;
    max-width: 540px;
    width: 100%;
    max-height: 90vh;
    overflow-y: auto;
    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
    position: relative;
}
.modal-content h3 { margin: 0 0 12px; font-size: 18px; font-weight: 600; }
.modal-close {
    position: absolute;
    top: 12px;
    right: 16px;
    background: transparent;
    border: none;
    font-size: 24px;
    line-height: 1;
    cursor: pointer;
    color: var(--text-faint);
    padding: 4px 8px;
}
.modal-close:hover { color: var(--text); }
.anki-msg {
    padding: 10px 14px;
    border-radius: 6px;
    margin-bottom: 16px;
    font-size: 14px;
    line-height: 1.5;
}
.anki-msg-success { background: rgba(34, 197, 94, 0.1); color: #16a34a; border: 1px solid rgba(34, 197, 94, 0.3); }
.anki-msg-warn { background: rgba(234, 179, 8, 0.1); color: #ca8a04; border: 1px solid rgba(234, 179, 8, 0.3); }
body.dark .anki-msg-success { color: #4ade80; }
body.dark .anki-msg-warn { color: #fbbf24; }
.anki-steps {
    margin: 0 0 16px;
    padding-left: 20px;
    font-size: 14px;
    line-height: 1.7;
    color: var(--text);
}
.anki-steps li { margin-bottom: 6px; }
.anki-steps code, .anki-steps strong {
    background: var(--bg-soft);
    padding: 1px 6px;
    border-radius: 3px;
    font-family: ui-monospace, 'Cascadia Code', monospace;
    font-size: 12.5px;
}
.anki-steps a { color: var(--accent); }
.anki-steps ul { margin: 4px 0 0; padding-left: 18px; }
.anki-tip {
    background: var(--bg-soft);
    border-left: 3px solid var(--accent);
    padding: 10px 14px;
    border-radius: 0 6px 6px 0;
    font-size: 13.5px;
    line-height: 1.6;
    color: var(--text-soft);
    margin-bottom: 16px;
}
.btn-primary {
    background: var(--accent);
    color: #fff;
    border: none;
    padding: 8px 18px;
    border-radius: 6px;
    font-family: inherit;
    font-size: 14px;
    cursor: pointer;
    font-weight: 500;
}
.btn-primary:hover { filter: brightness(1.08); }

/* 笔记图谱全屏弹窗 */
.notes-graph-overlay {
    padding: 0;
    background: var(--bg);
}
.notes-graph-container {
    width: 100%;
    height: 100vh;
    display: flex;
    flex-direction: column;
    background: var(--bg);
    color: var(--text);
}
.notes-graph-header {
    display: flex;
    align-items: center;
    gap: 16px;
    padding: 16px 24px;
    border-bottom: 1px solid var(--border);
    background: var(--bg);
}
.notes-graph-header h3 {
    margin: 0;
    font-size: 18px;
    font-weight: 600;
}
.notes-graph-stats {
    color: var(--text-faint);
    font-size: 13px;
    font-family: ui-monospace, monospace;
    flex: 1;
}
.notes-graph-help {
    padding: 8px 24px 12px;
    font-size: 12px;
    color: var(--text-faint);
    line-height: 1.6;
    border-bottom: 1px solid var(--border);
}
.notes-graph-tip {
    margin-left: 12px;
    padding: 2px 8px;
    background: var(--bg-soft);
    border-radius: 3px;
    color: var(--text-soft);
}
#notes-graph-canvas {
    flex: 1;
    width: 100%;
    cursor: grab;
    background: var(--bg);
}
#notes-graph-canvas:active { cursor: grabbing; }
.notes-graph-tooltip {
    position: fixed;
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 8px 12px;
    font-size: 12px;
    pointer-events: none;
    opacity: 0;
    transition: opacity 0.15s;
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.15);
    z-index: 1001;
    max-width: 240px;
}
.notes-graph-tooltip.visible { opacity: 1; }
.notes-graph-tooltip .ngt-book {
    color: var(--text-faint);
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    margin-bottom: 2px;
}
.notes-graph-tooltip .ngt-title {
    font-weight: 500;
    color: var(--text);
    margin-bottom: 4px;
}
.notes-graph-tooltip .ngt-meta {
    color: var(--text-faint);
    font-size: 11px;
}
.graph-close { font-size: 28px !important; padding: 4px 12px !important; }
body.dark #notes-graph-canvas { background: #14141a; }

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

/* 章节完成祝贺 */
.celebration-toast {
    position: fixed;
    bottom: 32px;
    left: 50%;
    transform: translateX(-50%) translateY(20px);
    background: var(--text);
    color: var(--bg);
    padding: 16px 24px;
    border-radius: 12px;
    box-shadow: 0 12px 36px rgba(0,0,0,0.18);
    z-index: 9999;
    display: flex;
    align-items: center;
    gap: 14px;
    opacity: 0;
    pointer-events: none;
    transition: opacity .3s, transform .3s;
    max-width: 420px;
}
.celebration-toast.visible {
    opacity: 1;
    transform: translateX(-50%) translateY(0);
    pointer-events: auto;
}
.celebration-toast .icon { color: var(--accent); flex-shrink: 0; }
.celebration-toast .text { display: flex; flex-direction: column; gap: 2px; }
.celebration-toast .title { font-size: 14px; font-weight: 600; }
.celebration-toast .sub { font-size: 12px; opacity: 0.7; }
.celebration-toast .next-link {
    font-size: 12px;
    color: var(--accent);
    background: var(--bg);
    padding: 4px 10px;
    border-radius: 4px;
    text-decoration: none;
    white-space: nowrap;
    margin-left: 6px;
    font-weight: 500;
}

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
    color: var(--bg);
    border-color: var(--accent);
}
.command-chip-status {
    border-style: dashed;
    opacity: 0.85;
}
.command-chip-status.active {
    opacity: 1;
}

.command-results {
    overflow-y: auto;
    flex: 1;
    min-height: 240px;
    max-height: 50vh;
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
// Icon library: mirrors Python svg_icon() for use inside JS template literals.
// Injected from build time via __ICONS_JSON__ placeholder below.
const ICONS_LIB = __ICONS_JSON__;
function svg_icon(name, size) {
    if (!ICONS_LIB[name]) return '';
    size = size || 16;
    return '<svg class="icon" width="' + size + '" height="' + size + '" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + ICONS_LIB[name] + '</svg>';
}

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

// 阅读宽度
let currentWidth = localStorage.getItem('readingWidth') || 'medium';
function setWidth(width) {
    document.body.classList.remove('width-narrow', 'width-medium', 'width-wide');
    document.body.classList.add('width-' + width);
    document.querySelectorAll('.width-btn').forEach(b => b.classList.toggle('active', b.dataset.width === width));
    localStorage.setItem('readingWidth', width);
}
document.querySelectorAll('.width-btn').forEach(btn => {
    btn.addEventListener('click', () => setWidth(btn.dataset.width));
});
setWidth(currentWidth);

// ============================================================
// 图片 lightbox — 点击放大
// ============================================================
const _lightbox = document.createElement('div');
_lightbox.className = 'lightbox';
_lightbox.innerHTML = '<button class="lightbox-close" aria-label="关闭">×</button><img alt=""><div class="lightbox-caption"></div>';
document.body.appendChild(_lightbox);
const _lbImg = _lightbox.querySelector('img');
const _lbCap = _lightbox.querySelector('.lightbox-caption');
const _lbClose = _lightbox.querySelector('.lightbox-close');
_lbClose.addEventListener('click', () => _lightbox.classList.remove('open'));
_lightbox.addEventListener('click', (e) => { if (e.target === _lightbox) _lightbox.classList.remove('open'); });
document.addEventListener('keydown', (e) => { if (e.key === 'Escape') _lightbox.classList.remove('open'); });
function setupLightbox() {
    document.querySelectorAll('.chapter-content img').forEach(img => {
        if (img.dataset.lbReady) return;
        img.dataset.lbReady = '1';
        img.style.cursor = 'zoom-in';
        img.addEventListener('click', () => {
            _lbImg.src = img.src;
            _lbImg.alt = img.alt || '';
            _lbCap.textContent = img.alt || '';
            _lightbox.classList.add('open');
        });
    });
}
setupLightbox();


function toggleDark() {
    setTheme(document.body.classList.contains('dark') ? 'light' : 'dark');
}

document.getElementById('dark-btn').addEventListener('click', toggleDark);

// 主题切换：light / dark / sepia / green
function setTheme(theme) {
    document.body.classList.remove('dark', 'sepia', 'green');
    if (theme === 'dark') document.body.classList.add('dark');
    else if (theme === 'sepia') document.body.classList.add('sepia');
    else if (theme === 'green') document.body.classList.add('green');
    localStorage.setItem('theme', theme);
    const db = document.getElementById('dark-btn');
    if (db) db.classList.toggle('active', theme === 'dark');
    document.querySelectorAll('.theme-btn').forEach(b => b.classList.toggle('active', b.dataset.theme === theme));
}
document.querySelectorAll('.theme-btn').forEach(btn => {
    btn.addEventListener('click', () => setTheme(btn.dataset.theme));
});
const savedTheme = localStorage.getItem('theme');
if (savedTheme && savedTheme !== 'light') setTheme(savedTheme);
else if (localStorage.getItem('dark') === 'true') setTheme('dark');

// 字体族切换：serif / sans / mono
function setFontFam(fam) {
    document.body.classList.remove('font-serif', 'font-sans', 'font-mono');
    document.body.classList.add('font-' + fam);
    localStorage.setItem('fontFamily', fam);
    document.querySelectorAll('.fam-btn').forEach(b => b.classList.toggle('active', b.dataset.fam === fam));
}
document.querySelectorAll('.fam-btn').forEach(btn => {
    btn.addEventListener('click', () => setFontFam(btn.dataset.fam));
});
const savedFam = localStorage.getItem('fontFamily') || 'serif';
setFontFam(savedFam);

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
    const collapsed = document.body.classList.contains('sidebar-collapsed');
    localStorage.setItem('sidebarCollapsed', collapsed);
    document.getElementById('sidebar-toggle').setAttribute('aria-expanded', String(!collapsed));
});

if (localStorage.getItem('sidebarCollapsed') === 'true') {
    document.body.classList.add('sidebar-collapsed');
    document.getElementById('sidebar-toggle')?.setAttribute('aria-expanded', 'false');
} else {
    document.getElementById('sidebar-toggle')?.setAttribute('aria-expanded', 'true');
}

// 书架折叠（默认全部展开，header 点击可折叠）
document.querySelectorAll('.book-header').forEach(header => {
    header.addEventListener('click', (e) => {
        // 避免进度条点击时触发折叠
        if (e.target.closest('.book-progress-bar') || e.target.closest('.book-progress-label')) return;
        const group = header.closest('.book-group');
        const chapters = group.querySelector('.book-chapters');
        const collapsed = chapters.classList.toggle('collapsed');
        header.classList.toggle('collapsed', collapsed);
        // 持久化
        const slug = group.dataset.book;
        const set = JSON.parse(localStorage.getItem('booksCollapsed') || '[]');
        if (collapsed && !set.includes(slug)) set.push(slug);
        else if (!collapsed) {
            const i = set.indexOf(slug);
            if (i >= 0) set.splice(i, 1);
        }
        localStorage.setItem('booksCollapsed', JSON.stringify(set));
    });
});

// 默认全部展开；恢复用户上次手动折叠的
try {
    const collapsed = JSON.parse(localStorage.getItem('booksCollapsed') || '[]');
    document.querySelectorAll('.book-group').forEach(group => {
        if (collapsed.includes(group.dataset.book)) {
            group.querySelector('.book-chapters').classList.add('collapsed');
            group.querySelector('.book-header').classList.add('collapsed');
        }
    });
} catch (e) {}

// 系列导览（ch01 顶部）折叠/展开
document.querySelectorAll('.series-intro-toggle').forEach(btn => {
    btn.addEventListener('click', () => {
        const expanded = btn.getAttribute('aria-expanded') === 'true';
        const list = btn.closest('.series-intro').querySelector('.series-toc');
        btn.setAttribute('aria-expanded', String(!expanded));
        btn.textContent = expanded ? '\u5c55\u5f00' : '\u6536\u8d77';
        if (list) list.classList.toggle('collapsed', expanded);
    });
});

// 进度条
let lastChapter = null;
const chapters = document.querySelectorAll('.chapter');
const links = document.querySelectorAll('.book-chapters a');

// 彩蛋：连按 5 次 ? 打开开发者热力图
let devPressBuffer = [];
const DEV_KEY = '?';
const DEV_PRESSES = 5;
const DEV_WINDOW_MS = 2500;
window.addEventListener('keydown', (e) => {
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    if (e.target && /^(INPUT|TEXTAREA)$/.test(e.target.tagName)) return;
    if (e.key !== DEV_KEY) { devPressBuffer = []; return; }
    const now = Date.now();
    devPressBuffer = devPressBuffer.filter(t => now - t < DEV_WINDOW_MS);
    devPressBuffer.push(now);
    if (devPressBuffer.length >= DEV_PRESSES) {
        devPressBuffer = [];
        toggleDevPanel();
    }
});
function toggleDevPanel() {
    const panel = document.getElementById('dev-panel');
    if (!panel) return;
    if (panel.classList.contains('visible')) {
        panel.classList.remove('visible');
    } else {
        renderDevHeatmap();
        panel.classList.add('visible');
    }
}
function renderDevHeatmap() {
    const body = document.getElementById('dev-heatmap');
    if (!body) return;
    const books = document.querySelectorAll('.book-group');
    let html = '';
    let done = 0, inProgress = 0, total = 0;
    books.forEach(g => {
        const bookTitle = g.querySelector('.book-title-text')?.textContent || g.dataset.book;
        html += '<div class="dev-row"><div class="dev-row-label">' + bookTitle + '</div><div class="dev-row-cells">';
        g.querySelectorAll('.book-chapters a').forEach(a => {
            const id = a.getAttribute('href').slice(1);
            const isDone = !!progress.completed[id];
            const pct = progress.readPct[id] || 0;
            let cls = 'unread';
            if (isDone) { cls = 'done'; done++; }
            else if (pct > 0) { cls = 'progress'; inProgress++; }
            total++;
            html += '<a class="dev-cell ' + cls + '" href="#' + id + '" title="' + a.textContent.trim() + ' \u00b7 ' + (isDone ? '\u5df2\u8bfb' : pct + '%') + '"></a>';
        });
        html += '</div></div>';
    });
    body.innerHTML = html;
    const stats = document.getElementById('dev-stats');
    if (stats) stats.textContent = done + ' / ' + total + ' \u5df2\u8bfb  \u00b7  ' + inProgress + ' \u8fdb\u884c\u4e2d';
}

// dev panel 关闭：按钮 + ESC
document.querySelector('.dev-panel-close')?.addEventListener('click', () => {
    document.getElementById('dev-panel')?.classList.remove('visible');
});
window.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && document.getElementById('dev-panel')?.classList.contains('visible')) {
        document.getElementById('dev-panel').classList.remove('visible');
    }
});

// console 自测函数：标记 6 已读 + 2 进行中，刷新，打开 panel
window.__devTest = function() {
    const p = JSON.parse(localStorage.getItem('progress') || '{"completed":{},"readPct":{}}');
    p.completed = {};
    p.readPct = {};
    const links = document.querySelectorAll('.book-chapters a');
    const ids = Array.from(links).map(a => a.getAttribute('href').slice(1));
    for (let i = 0; i < 6 && i < ids.length; i++) p.completed[ids[i]] = Date.now();
    for (let i = 6; i < 8 && i < ids.length; i++) p.readPct[ids[i]] = 45;
    localStorage.setItem('progress', JSON.stringify(p));
    setTimeout(() => {
        location.reload();
        setTimeout(() => {
            for (let i = 0; i < 5; i++) window.dispatchEvent(new KeyboardEvent('keydown', { key: '?', bubbles: true }));
            console.log('__devTest: marked 6 done + 2 progress, panel opened. Stats: ' +
                (document.getElementById('dev-stats')?.textContent || 'unknown'));
        }, 800);
    }, 200);
    return 'queued: writing 6 completed + 2 progress, then reload + open dev panel';
};
console.log('%c Knowledge Garden dev tools ', 'background:#d97706;color:#fff;padding:2px 8px;border-radius:2px;',
    '\\n\u8c03\u8bd5\u5de5\u5177\uff1a\\n' +
    '  toggleDevPanel()  - \u6253\u5f00/\u5173\u95ed dev panel\\n' +
    '  renderDevHeatmap() - \u5f3a\u5236\u91cd\u7ed8\u70ed\u529b\u56fe\\n' +
    '  __devTest()       - \u4e00\u6b21\u6027\u6ce8\u5165 6 \u5df2\u8bfb + 2 \u8fdb\u884c\u4e2d\uff0c\u6253\u5f00 panel');

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

// 章节内进度条: 跟随当前可见 article 计算, 切章节自动重置
function updateChapterProgress() {
    const bar = document.querySelector('.progress');
    if (!bar) return;
    // 找当前最靠近视口中心的 chapter
    const chapters = document.querySelectorAll('article.chapter');
    if (!chapters.length) {
        bar.style.opacity = '0';
        return;
    }
    const center = window.scrollY + window.innerHeight / 2;
    let active = null;
    chapters.forEach(art => {
        const top = art.offsetTop;
        const bot = top + art.offsetHeight;
        if (center >= top && center < bot) active = art;
    });
    if (!active) {
        // 在 overview 模式时
        bar.style.opacity = '0';
        return;
    }
    bar.style.opacity = '1';
    const rect = active.getBoundingClientRect();
    const total = active.offsetHeight - window.innerHeight;
    const scrolled = -rect.top;
    const progress = total > 0 ? Math.max(0, Math.min(1, scrolled / total)) : 0;
    bar.style.transform = 'scaleX(' + progress + ')';
}
window.addEventListener('scroll', updateChapterProgress, { passive: true });
window.addEventListener('resize', updateChapterProgress, { passive: true });
setTimeout(updateChapterProgress, 100);

// ============================================================
// 章节底部"相关章节" — 复用 dense index 的 chapters 数组
// 每章 mean-pooled embedding + 其他章 cosine top-5
// 章节内显示 (但 TF-IDF 模式就能用 — 不需 AI 模型)
// ============================================================
async function loadRelatedChapters() {
    if (_kbDenseIndex && _kbDenseIndex.chapters) return _kbDenseIndex;
    try {
        const idx = await fetch('assets/knowledge_dense.json').then(r => r.json());
        _kbDenseIndex = idx;
        return idx;
    } catch (e) {
        return null;
    }
}

function kbDecodeChapterEmb(b64) {
    const bytes = Uint8Array.from(atob(b64), c => c.charCodeAt(0));
    return new Float32Array(bytes.buffer);
}

// 渲染相关章节 (卡片 / 图谱 切换)
async function renderRelatedChapters(chapterId) {
    const container = document.getElementById('related-chapters-' + chapterId);
    if (!container) return;
    const idx = await loadRelatedChapters();
    if (!idx || !idx.chapters) {
        container.style.display = 'none';
        return;
    }
    // 找当前 chapter 的 vector
    const me = idx.chapters.find(c => c.id === chapterId);
    if (!me) { container.style.display = 'none'; return; }
    const myEmb = kbDecodeChapterEmb(me.embedding);
    // 计算 top 5 (排除自己)
    const scored = [];
    for (const c of idx.chapters) {
        if (c.id === chapterId) continue;
        const e = kbDecodeChapterEmb(c.embedding);
        let dot = 0;
        for (let i = 0; i < 512; i++) dot += myEmb[i] * e[i];
        scored.push({ c, score: dot });
    }
    scored.sort((a, b) => b.score - a.score);
    const top = scored.slice(0, 5);
    if (top.length === 0) { container.style.display = 'none'; return; }
    const topScore = top[0].score || 1;
    const view = (container.dataset.view === 'graph') ? 'graph' : 'cards';
    const tabs = '<div class="related-tabs">' +
        '<button class="related-tab' + (view === 'cards' ? ' active' : '') + '" data-view="cards">卡片</button>' +
        '<button class="related-tab' + (view === 'graph' ? ' active' : '') + '" data-view="graph">图谱</button>' +
        '</div>';
    let body;
    if (view === 'graph') {
        // SVG 图谱: 当前章节在中心, 5 个相关在外圈, 边粗细 = 相关度
        const cx = 150, cy = 130, R = 95;
        const nodes = top.map(({ c, score }, i) => {
            const angle = (i / top.length) * Math.PI * 2 - Math.PI / 2;
            const x = cx + Math.cos(angle) * R;
            const y = cy + Math.sin(angle) * R;
            const bm = (BOOKS_META[c.bookSlug]) || {};
            const color = bm.color || '#b08968';
            return { x, y, c, score, color };
        });
        const meTitle = me.chapterTitle.length > 20 ? me.chapterTitle.slice(0, 18) + '…' : me.chapterTitle;
        const edges = nodes.map(n => '<line x1="' + cx + '" y1="' + cy + '" x2="' + n.x.toFixed(0) + '" y2="' + n.y.toFixed(0) + '" stroke="var(--accent)" stroke-width="' + (1 + (n.score / topScore) * 3).toFixed(1) + '" opacity="' + (0.3 + (n.score / topScore) * 0.5).toFixed(2) + '"/>').join('');
        const dots = nodes.map(n => {
            const title = n.c.chapterTitle.length > 16 ? n.c.chapterTitle.slice(0, 14) + '…' : n.c.chapterTitle;
            return '<a href="#' + n.c.id + '">' +
                '<circle cx="' + n.x.toFixed(0) + '" cy="' + n.y.toFixed(0) + '" r="22" fill="' + n.color + '" stroke="var(--bg)" stroke-width="2"/>' +
                '<text x="' + n.x.toFixed(0) + '" y="' + (n.y + 38).toFixed(0) + '" text-anchor="middle" font-size="10" fill="var(--text-soft)">' + escapeAttr(title) + '</text>' +
                '</a>';
        }).join('');
        body = '<svg class="related-graph" viewBox="0 0 300 280" width="300" height="280">' +
            edges +
            '<circle cx="' + cx + '" cy="' + cy + '" r="34" fill="var(--accent)" stroke="var(--bg)" stroke-width="3"/>' +
            '<text x="' + cx + '" y="' + (cy + 4) + '" text-anchor="middle" font-size="11" font-weight="600" fill="var(--bg)">本章</text>' +
            '<text x="' + cx + '" y="' + (cy + 50) + '" text-anchor="middle" font-size="9" fill="var(--text-faint)">' + escapeAttr(meTitle) + '</text>' +
            dots +
            '</svg>';
    } else {
        body = '<div class="related-chapters-grid">' +
            top.map(({ c, score }) => {
                const bm = (BOOKS_META[c.bookSlug]) || {};
                const color = bm.color || '#b08968';
                const rel = (score / topScore * 100).toFixed(0);
                return '<a class="related-card" href="#' + c.id + '">' +
                    '<span class="related-card-book" style="color:' + color + '">' + c.bookTitle + '</span>' +
                    '<span class="related-card-title">' + c.chapterTitle + '</span>' +
                    '<span class="related-card-score">相关度 ' + rel + '%</span>' +
                    '</a>';
            }).join('') + '</div>';
    }
    container.innerHTML = '<h3>相关章节</h3>' + tabs + body;
    container.querySelectorAll('.related-tab').forEach(tab => {
        tab.addEventListener('click', () => {
            container.dataset.view = tab.dataset.view;
            renderRelatedChapters(chapterId);
        });
    });
        '</div>';
}
// 当前 hash 改变时, 渲染对应章节的相关
function maybeRenderRelated() {
    const hash = window.location.hash;
    if (!hash) return;
    const m = hash.match(/^#([\w-]+(?:__[\w-]+)?)$/);
    if (m) renderRelatedChapters(m[1]);
}
setTimeout(maybeRenderRelated, 200);
window.addEventListener('hashchange', maybeRenderRelated);

const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            const id = entry.target.id;
            if (lastChapter !== null && lastChapter !== id) {
                playPageFlip();
            }
            lastChapter = id;
            links.forEach(l => { l.classList.remove('active'); l.removeAttribute('aria-current'); });
            const activeLink = document.querySelector('.book-chapters a[href="#' + id + '"]');
            if (activeLink) {
                activeLink.classList.add('active');
                activeLink.setAttribute('aria-current', 'true');
                // 标记当前章节所在的书为 current-book（高亮），不再自动折叠其他书
                const bookGroup = activeLink.closest('.book-group');
                document.querySelectorAll('.book-group').forEach(g => {
                    g.classList.toggle('current-book', g === bookGroup);
                });
            }
        }
    });
}, { rootMargin: '-30% 0px -50% 0px', threshold: 0 });

chapters.forEach(ch => observer.observe(ch));

// === 章节内 mini-TOC：监听 heading 滚动高亮 ===
(function() {
    const tocLinks = Array.from(document.querySelectorAll('.chapter-toc a[data-toc-id]'));
    if (tocLinks.length === 0) return;
    const idToLink = new Map();
    tocLinks.forEach(a => idToLink.set(a.dataset.tocId, a));
    const headings = Array.from(document.querySelectorAll('.chapter-content h2[id], .chapter-content h3[id]'));
    if (headings.length === 0) return;

    function setActive(id) {
        tocLinks.forEach(a => a.classList.remove('active'));
        const link = idToLink.get(id);
        if (link) link.classList.add('active');
    }
    // 点击平滑滚动 + hash 同步
    tocLinks.forEach(a => {
        a.addEventListener('click', (e) => {
            e.preventDefault();
            const id = a.dataset.tocId;
            const target = document.getElementById(id);
            if (!target) return;
            const top = target.getBoundingClientRect().top + window.scrollY - 70;
            window.scrollTo({ top, behavior: 'smooth' });
            history.replaceState(null, '', '#' + id);
            setActive(id);
        });
    });
    // 进入视口最上方的 heading 设为 active
    const tocObserver = new IntersectionObserver((entries) => {
        // 取所有当前在视口内的 headings
        const visible = entries
            .filter(e => e.isIntersecting)
            .map(e => ({ id: e.target.id, top: e.boundingClientRect.top }))
            .sort((a, b) => a.top - b.top);
        if (visible.length > 0) {
            setActive(visible[0].id);
        }
    }, { rootMargin: '-80px 0px -70% 0px', threshold: 0 });
    headings.forEach(h => tocObserver.observe(h));
})();

// === 代码块：复制按钮 + 语言标签 ===
(function() {
    const LANG_MAP = { py: 'python', js: 'javascript', ts: 'typescript', sh: 'bash', md: 'markdown', yml: 'yaml', json: 'json' };

    // ----- Mermaid：找到 mermaid 块，转 <div class="mermaid">，延迟加载 mermaid.js -----
    const mermaidBlocks = [];
    document.querySelectorAll('.chapter-content pre code.language-mermaid').forEach(code => {
        const pre = code.parentNode;
        const div = document.createElement('div');
        div.className = 'mermaid';
        div.textContent = code.textContent;
        pre.parentNode.replaceChild(div, pre);
        mermaidBlocks.push(div);
    });
    if (mermaidBlocks.length > 0) {
        const script = document.createElement('script');
        script.src = 'assets/mermaid.min.js';
        script.onload = () => {
            if (window.mermaid) {
                mermaid.initialize({ startOnLoad: false, theme: 'default', securityLevel: 'loose', flowchart: { useMaxWidth: true, htmlLabels: true } });
                mermaid.run({ nodes: mermaidBlocks });
            }
        };
        document.head.appendChild(script);
    }

    document.querySelectorAll('.chapter-content pre').forEach(pre => {
        const code = pre.querySelector('code');
        if (!code) return;
        // 提取语言：<code class="language-python"> → python
        let lang = '';
        const cls = code.className || '';
        const m = cls.match(/language-([A-Za-z0-9_+-]+)/);
        if (m) lang = LANG_MAP[m[1]] || m[1];
        if (lang) {
            const langEl = document.createElement('span');
            langEl.className = 'code-lang';
            langEl.textContent = lang;
            pre.appendChild(langEl);
        }
        // 复制按钮
        const btn = document.createElement('button');
        btn.className = 'code-copy';
        btn.type = 'button';
        btn.setAttribute('aria-label', '复制代码');
        btn.innerHTML = '<svg class="icon" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg><span>Copy</span>';
        pre.appendChild(btn);

        // 跳转按钮：python → Replit，bash → explainshell
        const langKey = (m && m[1]) ? m[1] : '';
        if (langKey === 'py' || langKey === 'python') {
            const runBtn = document.createElement('a');
            runBtn.className = 'code-jump';
            runBtn.href = 'https://replit.com/languages/python3';
            runBtn.target = '_blank';
            runBtn.rel = 'noopener';
            runBtn.title = '复制代码后在新标签打开 Replit';
            runBtn.innerHTML = '<svg class="icon" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="5 3 19 12 5 21 5 3"/></svg><span>Run</span>';
            runBtn.addEventListener('click', async () => {
                try { await navigator.clipboard.writeText(code.innerText); } catch(e) {}
            });
            pre.appendChild(runBtn);
        } else if (langKey === 'bash' || langKey === 'sh' || langKey === 'shell') {
            const runBtn = document.createElement('a');
            runBtn.className = 'code-jump';
            runBtn.href = 'https://explainshell.com/';
            runBtn.target = '_blank';
            runBtn.rel = 'noopener';
            runBtn.title = '复制命令到剪贴板后在新标签打开 explainshell';
            runBtn.innerHTML = '<svg class="icon" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg><span>Explain</span>';
            runBtn.addEventListener('click', async () => {
                try { await navigator.clipboard.writeText(code.innerText); } catch(e) {}
            });
            pre.appendChild(runBtn);
        }
        btn.addEventListener('click', async () => {
            const text = code.innerText;
            try {
                await navigator.clipboard.writeText(text);
            } catch (e) {
                // fallback
                const ta = document.createElement('textarea');
                ta.value = text;
                ta.style.position = 'fixed';
                ta.style.opacity = '0';
                document.body.appendChild(ta);
                ta.select();
                try { document.execCommand('copy'); } catch (e2) {}
                document.body.removeChild(ta);
            }
            btn.classList.add('copied');
            btn.innerHTML = '<svg class="icon" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg><span>已复制</span>';
            setTimeout(() => {
                btn.classList.remove('copied');
                btn.innerHTML = '<svg class="icon" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg><span>Copy</span>';
            }, 1800);
        });
    });
})();

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

// 高亮颜色 → 语义标签映射 (yellow=重要 / green=todo / blue=问题 / pink=想法)
function noteColorToTag(color) {
    if (!color) return null;
    if (color.endsWith('-yellow')) return '重要';
    if (color.endsWith('-green')) return 'todo';
    if (color.endsWith('-blue')) return '问题';
    if (color.endsWith('-pink')) return '想法';
    return null;
}
let _notesTagFilter = 'all';
function renderNotesList() {
    const list = document.querySelector('.notes-list');
    const searchInput = document.getElementById('notes-search');
    const query = (searchInput && searchInput.value || '').trim().toLowerCase();
    let filtered = notes;
    if (query) {
        filtered = filtered.filter(n =>
            (n.quote || '').toLowerCase().includes(query) ||
            (n.text || '').toLowerCase().includes(query)
        );
    }
    if (_notesTagFilter !== 'all') {
        filtered = filtered.filter(n => noteColorToTag(n.color) === _notesTagFilter);
    }
    if (filtered.length === 0) {
        const msg = query ? `没有包含 "${query}" 的笔记` : '还没有笔记<br><br>选中正文中的文字后<br>点击弹出的浮动工具栏添加';
        list.innerHTML = `<div class="notes-empty">${msg}</div>`;
        return;
    }

    // 按书 + 章节分组
    const byBookChapter = {};
    filtered.forEach((note, idx) => {
        const key = (note.bookSlug || 'unknown') + '|' + (note.chapterId || '');
        if (!byBookChapter[key]) byBookChapter[key] = [];
        // 找原始 idx (用于删除)
        const origIdx = notes.indexOf(note);
        byBookChapter[key].push({ ...note, idx: origIdx });
    });

    function escapeHtml(s) {
        return String(s || '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
    }
    function highlight(s) {
        const esc = escapeHtml(s);
        if (!query) return esc;
        // JS regex char class 双重转义坑 (Python source 里 \\ 处理): 用 per-char escape 函数避开
        const escQ = query.split('').map(c => '.*+?^${}()|[]'.indexOf(c) >= 0 ? String.fromCharCode(92) + c : c).join('');
        const re = new RegExp('(' + escQ + ')', 'gi');
        return esc.replace(re, '<mark>$1</mark>');
    }

    let html = '';
    Object.entries(byBookChapter).forEach(([key, items]) => {
        const [bookSlug, chapterId] = key.split('|');
        const chapter = document.getElementById(chapterId);
        const chapterTitle = chapter?.querySelector('.chapter-title')?.textContent || chapterId;
        const bookHeader = document.querySelector(`[data-book="${bookSlug}"] .book-title-text`);
        const bookTitle = bookHeader?.textContent || bookSlug;

        html += `<div style="margin-bottom: 8px; font-size: 10px; color: var(--text-faint); letter-spacing: 1px;">${escapeHtml(bookTitle)} · ${escapeHtml(chapterTitle)}</div>`;

        items.sort((a, b) => b.timestamp - a.timestamp).forEach(note => {
            const tag = noteColorToTag(note.color);
            const tagHtml = tag ? `<span class="note-tag" data-tag="${tag}">${tag}</span>` : '';
            html += `
                <div class="note-item" data-chapter="${chapterId}" data-idx="${note.idx}">
                    <button class="note-delete">×</button>
                    ${tagHtml}
                    <div class="note-quote">${highlight(note.quote || note.text || '')}</div>
                    ${note.type === 'note' ? `<div class="note-text">${highlight(note.text)}</div>` : ''}
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
            hideOverview();
            document.getElementById(chapterId)?.scrollIntoView({ behavior: 'smooth' });
        });
        item.querySelector('.note-delete').addEventListener('click', (e) => {
            notes.splice(idx, 1);
            saveNotes();
renderNotesList();
// 笔记搜索: input 时实时过滤
const notesSearchInput = document.getElementById('notes-search');
if (notesSearchInput) {
    let searchTimer = null;
    notesSearchInput.addEventListener('input', () => {
        clearTimeout(searchTimer);
        searchTimer = setTimeout(renderNotesList, 80);
    });
}
// 笔记 tag filter chip 点击切换
document.querySelectorAll('#notes-filter .nf-chip').forEach(chip => {
    chip.addEventListener('click', () => {
        document.querySelectorAll('#notes-filter .nf-chip').forEach(c => c.classList.remove('active'));
        chip.classList.add('active');
        _notesTagFilter = chip.dataset.tag;
        renderNotesList();
    });
});
// Cmd+Shift+F: 焦点到笔记搜索
document.addEventListener('keydown', (e) => {
    if ((e.metaKey || e.ctrlKey) && e.shiftKey && (e.key === 'F' || e.key === 'f')) {
        e.preventDefault();
        // 确保 notes panel 已打开
        const notesBtn = document.getElementById('notes-btn');
        if (notesBtn && !notesBtn.classList.contains('active')) notesBtn.click();
        setTimeout(() => {
            const si = document.getElementById('notes-search');
            if (si) { si.focus(); si.select(); }
        }, 100);
    }
});
            e.stopPropagation();
        });
    });
}

renderNotesList();

// PWA
if ('serviceWorker' in navigator) {
    // 同源文件 (build 阶段生成), 不用 blob URL (blob URL 不能作 SW, 旧版坏过)
    navigator.serviceWorker.register('./sw.js').then(reg => {
        console.log('[SW] registered, scope:', reg.scope);
    }).catch(err => {
        console.warn('[SW] registration failed:', err.message);
    });
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
            hideOverview();
            target.scrollIntoView({ behavior: 'smooth', block: 'start' });
            if (window.innerWidth < 900) {
                document.body.classList.add('sidebar-collapsed');
            }
        }
    });
});

// j/k 章节跳转：找视口里最顶部的 chapter, 跳到上一个/下一个
function jumpToAdjacentChapter(direction) {
    if (!CHAPTERS || CHAPTERS.length === 0) return;
    // 找当前最接近视口顶部的 chapter
    const viewportTop = window.scrollY + 80;  // 80px 缓冲, 避免误判
    let currentIdx = 0;
    for (let i = CHAPTERS.length - 1; i >= 0; i--) {
        const el = document.getElementById(CHAPTERS[i]);
        if (el && el.offsetTop <= viewportTop) {
            currentIdx = i;
            break;
        }
    }
    // 边界: 第一章按 k 跳到 overview, 最后一章按 j 不动
    const targetIdx = currentIdx + direction;
    if (targetIdx < 0) {
        showOverview();
        return;
    }
    if (targetIdx >= CHAPTERS.length) return;
    const targetId = CHAPTERS[targetIdx];
    const target = document.getElementById(targetId);
    if (!target) return;
    hideOverview();
    target.scrollIntoView({ behavior: 'smooth', block: 'start' });
    history.pushState(null, '', '#' + targetId);
    if (window.innerWidth < 900) {
        document.body.classList.add('sidebar-collapsed');
    }
}

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
    if (e.key === 'j' || e.key === 'J') {
        e.preventDefault();
        jumpToAdjacentChapter(1);
        return;
    }
    if (e.key === 'k' || e.key === 'K') {
        e.preventDefault();
        jumpToAdjacentChapter(-1);
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
// 章节顺序 (j/k 跳转用)
// ============================================================
const CHAPTERS = __CHAPTERS_JSON__;
const CHAPTER_REFS = __CHAPTER_REFS__;
const BOOKS_META = __BOOKS_META__;

// 章节 → 所属系列 (build 阶段计算 — 供"同系列下一章"用)
const CHAPTERS_BY_BOOK = {};
__CHAPTERS_BY_BOOK_INIT__;

// ============================================================
// 交叉引用：「第 N 章」自动转链接（同书内）
// ============================================================
function linkifyChapterRefs(root) {
    const article = root.closest ? root.closest('.chapter') : null;
    if (!article) return;
    const book = article.dataset.book;
    const refs = CHAPTER_REFS[book];
    if (!refs) return;
    // 合并：递归遍历 text node，跳过 a / code / pre
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
        acceptNode(n) {
            const p = n.parentNode;
            if (!p) return NodeFilter.FILTER_REJECT;
            const tag = p.nodeName;
            if (tag === 'A' || tag === 'CODE' || tag === 'PRE' || tag === 'SCRIPT' || tag === 'STYLE') {
                return NodeFilter.FILTER_REJECT;
            }
            return NodeFilter.FILTER_ACCEPT;
        }
    });
    const re = /第\\s*(\\d{1,2})\\s*章/g;
    const targets = [];
    let n;
    while ((n = walker.nextNode())) {
        if (re.test(n.nodeValue)) targets.push(n);
        re.lastIndex = 0;
    }
    targets.forEach(node => {
        const frag = document.createDocumentFragment();
        let last = 0;
        const text = node.nodeValue;
        let m;
        re.lastIndex = 0;
        while ((m = re.exec(text)) !== null) {
            const num = parseInt(m[1], 10);
            const ref = refs.find(r => r.num === num);
            if (!ref) continue;
            if (m.index > last) frag.appendChild(document.createTextNode(text.slice(last, m.index)));
            const a = document.createElement('a');
            a.href = '#' + ref.anchor;
            a.className = 'chapter-ref';
            a.title = '第 ' + num + ' 章 · ' + ref.title;
            a.textContent = m[0];
            frag.appendChild(a);
            last = m.index + m[0].length;
        }
        if (last === 0) return;
        if (last < text.length) frag.appendChild(document.createTextNode(text.slice(last)));
        node.parentNode.replaceChild(frag, node);
    });
}
document.querySelectorAll('.chapter-content').forEach(c => linkifyChapterRefs(c));

// ============================================================
// 章节内容 lazy loader — 按需加载 /assets/books/{slug}.json
// - IntersectionObserver: 视口 1.5x 距离触发
// - 缓存 Map, 同本书只 fetch 一次
// - 注入后: linkify chapter refs + 重新跑 mermaid/code 高亮 (如有)
// ============================================================
const _lazyBookCache = new Map();
const _lazyBookInFlight = new Map();
const _lazyLoaded = new WeakSet();
async function lazyLoadChapter(bookSlug, chapterId) {
    const body = document.querySelector('.chapter-body[data-load-book="' + bookSlug + '"][data-load-chapter="' + chapterId + '"]');
    if (!body || _lazyLoaded.has(body)) return;
    _lazyLoaded.add(body);
    // 取 book JSON (缓存 / in-flight 复用)
    let data = _lazyBookCache.get(bookSlug);
    if (!data) {
        if (_lazyBookInFlight.has(bookSlug)) {
            data = await _lazyBookInFlight.get(bookSlug);
        } else {
            const p = fetch('assets/books/' + bookSlug + '.json').then(r => {
                if (!r.ok) throw new Error('fetch ' + bookSlug + ' failed: ' + r.status);
                return r.json();
            });
            _lazyBookInFlight.set(bookSlug, p);
            try {
                data = await p;
                _lazyBookCache.set(bookSlug, data);
            } finally {
                _lazyBookInFlight.delete(bookSlug);
            }
        }
    }
    if (!data) return;
    const ch = (data.chapters || []).find(c => c.anchor === chapterId);
    if (!ch) { body.innerHTML = '<div class="chapter-loading">章节内容未找到。</div>'; return; }
    body.innerHTML = ch.body;
    body.classList.add('lazy-loaded');
    // 注入后再 linkify + 处理 mermaid/code (如果有)
    const content = body.querySelector('.chapter-content');
    if (content) linkifyChapterRefs(content);
    // 触发后处理 (mermaid / code highlight) — 派发事件, 由其它监听者接
    body.dispatchEvent(new CustomEvent('chapter-loaded', { bubbles: true }));
}
function setupLazyLoad() {
    if (!('IntersectionObserver' in window)) {
        // 回退: 立即加载所有
        document.querySelectorAll('.chapter-body[data-load-book]').forEach(b => {
            lazyLoadChapter(b.dataset.loadBook, b.dataset.loadChapter);
        });
        return;
    }
    const obs = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (!entry.isIntersecting) return;
            const b = entry.target;
            const bookSlug = b.dataset.loadBook;
            const chapterId = b.dataset.loadChapter;
            if (bookSlug && chapterId) lazyLoadChapter(bookSlug, chapterId);
            obs.unobserve(b);
        });
    }, { rootMargin: '600px 0px' });
    document.querySelectorAll('.chapter-body[data-load-book]').forEach(b => obs.observe(b));
}
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        setupLazyLoad();
        bootHashTarget();
    });
} else {
    setupLazyLoad();
    bootHashTarget();
}
// 初始 hash 直跳 (刷新到 #chapter-xxx): 加载目标章节
function bootHashTarget() {
    if (!window.location.hash) return;
    const id = window.location.hash.replace('#', '');
    const article = document.getElementById(id);
    if (!article) return;
    const body = article.querySelector('.chapter-body[data-load-book]');
    if (body) lazyLoadChapter(body.dataset.loadBook, id);
}


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

// 章节完成祝贺 — 底部 toast, 含下一章链接
function showCompletionCelebration(chapterId) {
    let toast = document.getElementById('celebration-toast');
    if (!toast) {
        toast = document.createElement('div');
        toast.id = 'celebration-toast';
        toast.className = 'celebration-toast';
        document.body.appendChild(toast);
    }
    const article = document.getElementById(chapterId);
    const title = article?.querySelector('.chapter-title')?.textContent || chapterId;
    const all = CHAPTERS || [];
    const idx = all.indexOf(chapterId);
    let nextId = null;
    if (idx >= 0 && idx + 1 < all.length) nextId = all[idx + 1];
    const checkSvg = '<svg class="icon" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>';
    toast.innerHTML = checkSvg +
        '<div class="text"><div class="title">已读完《' + title + '》</div>' +
        '<div class="sub">累计 ' + Object.keys(progress.completed).length + ' 章</div></div>' +
        (nextId ? '<a class="next-link" href="#' + nextId + '">下一章 →</a>' : '');
    toast.classList.add('visible');
    setTimeout(() => toast.classList.remove('visible'), 5000);
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

    // 整本书完成度（顶部 progress + 侧栏 book 进度）
    refreshBookProgressUI();
}

// ---- 周阅读目标 ----
function getWeeklyGoalMinutes() {
    // 用户可自定义，默认 180 分钟（3 小时）
    const v = parseInt(localStorage.getItem('weeklyGoalMinutes') || '180', 10);
    return Number.isFinite(v) && v >= 30 && v <= 1200 ? v : 180;
}

function setWeeklyGoalMinutes(min) {
    localStorage.setItem('weeklyGoalMinutes', String(min));
    const daily = (progress && progress.dailyTime) || {};
    refreshWeeklyGoal(daily);
}

function getWeekSeconds(daily) {
    const oneDay = 86400000;
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    // 本周从周一开始
    const day = today.getDay(); // 0=Sun, 1=Mon...
    const offsetToMonday = (day + 6) % 7;
    const weekStart = new Date(today.getTime() - offsetToMonday * oneDay);
    let sec = 0;
    for (let i = 0; i < 7; i++) {
        const d = new Date(weekStart.getTime() + i * oneDay);
        const k = d.toISOString().slice(0, 10);
        sec += daily[k] || 0;
    }
    return sec;
}

// GitHub-style 16 周阅读热度图 (按 daily 读秒数分级 0-4)
function renderStreakHeatmap(daily) {
    const wrap = document.getElementById('streak-heatmap');
    if (!wrap) return;
    const today = new Date(); today.setHours(0, 0, 0, 0);
    // 起始: 16 周前, 找那个周的周日
    const start = new Date(today);
    start.setDate(today.getDate() - 16 * 7 - today.getDay());
    // 找到 max 秒数, 用于分级
    let maxSec = 0;
    for (let i = 0; i < 16 * 7; i++) {
        const d = new Date(start);
        d.setDate(start.getDate() + i);
        const k = d.toISOString().slice(0, 10);
        if ((daily[k] || 0) > maxSec) maxSec = daily[k];
    }
    function level(sec) {
        if (!sec) return 0;
        if (maxSec <= 0) return 0;
        const pct = sec / maxSec;
        if (pct < 0.25) return 1;
        if (pct < 0.5) return 2;
        if (pct < 0.85) return 3;
        return 4;
    }
    // 渲染: 7 行 (周一到周日) × 16 列 (周)
    const monthNames = ['1月', '2月', '3月', '4月', '5月', '6月', '7月', '8月', '9月', '10月', '11月', '12月'];
    const html = ['<div class="streak-heatmap-title"><span class="left">过去 16 周阅读</span><span class="right">颜色越深读得越多</span></div>'];
    html.push('<div class="streak-heatmap-grid">');
    let lastMonth = -1;
    for (let col = 0; col < 16; col++) {
        html.push('<div class="streak-heatmap-col">');
        for (let row = 0; row < 7; row++) {
            const d = new Date(start);
            d.setDate(start.getDate() + col * 7 + row);
            if (d > today) {
                html.push('<span class="streak-heatmap-cell"></span>');
                continue;
            }
            const k = d.toISOString().slice(0, 10);
            const sec = daily[k] || 0;
            const lvl = level(sec);
            const min = Math.round(sec / 60);
            html.push('<span class="streak-heatmap-cell" data-level="' + lvl + '" title="' + k + ' · ' + min + ' 分钟"></span>');
        }
        html.push('</div>');
    }
    html.push('</div>');
    html.push('<div class="streak-heatmap-legend"><span>少</span>');
    for (let i = 0; i < 5; i++) html.push('<span class="cell" data-level="' + i + '"></span>');
    html.push('<span>多</span></div>');
    wrap.innerHTML = html.join('');
}

// 里程碑 / 成就系统
const ACHIEVEMENTS = [
    { id: 'first-read', name: '初读者', desc: '完成第 1 章', icon: 'book', test: () => Object.keys(progress.completed).length >= 1 },
    { id: 'ten-read', name: '10 章达成', desc: '累计读完 10 章', icon: 'flame', test: () => Object.keys(progress.completed).length >= 10 },
    { id: 'fifty-read', name: '50 章达成', desc: '累计读完 50 章', icon: 'sparkles', test: () => Object.keys(progress.completed).length >= 50 },
    { id: 'hundred-read', name: '百章里程碑', desc: '累计读完 100 章', icon: 'rocket', test: () => Object.keys(progress.completed).length >= 100 },
    { id: 'streak-3', name: '连续 3 天', desc: '3 天连续阅读', icon: 'flame', test: () => longestStreakDays() >= 3 },
    { id: 'streak-7', name: '连续 7 天', desc: '一周连续阅读', icon: 'zap', test: () => longestStreakDays() >= 7 },
    { id: 'streak-30', name: '连续 30 天', desc: '一个月连续阅读', icon: 'rocket', test: () => longestStreakDays() >= 30 },
    { id: 'notes-10', name: '10 条笔记', desc: '累计记 10 条笔记', icon: 'notes', test: () => notes.length >= 10 },
    { id: 'notes-50', name: '50 条笔记', desc: '累计记 50 条笔记', icon: 'brain', test: () => notes.length >= 50 },
    { id: 'bookmarks-5', name: '5 个书签', desc: '收藏 5 个段落', icon: 'bookmark', test: () => (progress.bookmarks ? Object.keys(progress.bookmarks).length : 0) >= 5 },
    { id: 'all-books', name: '博学家', desc: '访问过全部 17 系列', icon: 'layers', test: () => {
        const visited = new Set();
        Object.values(progress.lastRead || {}).forEach(r => {
            if (r && r.bookSlug) visited.add(r.bookSlug);
        });
        return visited.size >= 17;
    }},
    { id: 'half-pct', name: '半程英雄', desc: '已读 50% 章节', icon: 'star', test: () => {
        const total = document.querySelectorAll('.chapter[data-book]').length;
        if (!total) return false;
        return Object.keys(progress.completed).length / total >= 0.5;
    }},
];
function longestStreakDays() {
    const dates = new Set(Object.values(progress.completed || {}).map(ts => new Date(ts).toISOString().slice(0, 10)));
    if (dates.size === 0) return 0;
    const sorted = Array.from(dates).sort();
    let longest = 1, current = 1;
    for (let i = 1; i < sorted.length; i++) {
        const prev = new Date(sorted[i - 1]);
        const cur = new Date(sorted[i]);
        const diffDays = Math.round((cur - prev) / 86400000);
        if (diffDays === 1) { current++; if (current > longest) longest = current; }
        else current = 1;
    }
    return longest;
}
function renderAchievements() {
    const wrap = document.getElementById('achievements');
    if (!wrap) return;
    const unlockedAt = JSON.parse(localStorage.getItem('kg_achievements') || '{}');
    const newlyUnlocked = [];
    ACHIEVEMENTS.forEach(a => {
        try {
            if (a.test() && !unlockedAt[a.id]) {
                unlockedAt[a.id] = Date.now();
                newlyUnlocked.push(a);
            }
        } catch (e) { /* 测试函数可能依赖未初始化状态, 静默忽略 */ }
    });
    if (newlyUnlocked.length > 0) {
        localStorage.setItem('kg_achievements', JSON.stringify(unlockedAt));
    }
    const html = ['<div class="achievements-title">里程碑 (' + ACHIEVEMENTS.filter(a => unlockedAt[a.id]).length + '/' + ACHIEVEMENTS.length + ')</div>'];
    html.push('<div class="achievements-grid">');
    ACHIEVEMENTS.forEach(a => {
        const unlocked = !!unlockedAt[a.id];
        const cls = unlocked ? 'achievement' : 'achievement locked';
        const icon = (typeof ICONS_LIB !== 'undefined' && ICONS_LIB[a.icon]) ? ICONS_LIB[a.icon] : ICONS_LIB.book;
        html.push('<div class="' + cls + '" title="' + a.desc + '">');
        html.push('<div class="ac-icon"><svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">' + icon + '</svg></div>');
        html.push('<div class="ac-name">' + a.name + '</div>');
        html.push('<div class="ac-desc">' + a.desc + '</div>');
        html.push('</div>');
    });
    html.push('</div>');
    wrap.innerHTML = html.join('');
    // 新解锁的弹个 toast
    if (newlyUnlocked.length > 0) {
        newlyUnlocked.forEach(a => {
            setTimeout(() => showCompletionCelebration = showCompletionCelebration, 0); // noop
        });
    }
}

function refreshWeeklyGoal(daily) {
    const fill = document.getElementById('weekly-goal-fill');
    const current = document.getElementById('weekly-goal-current');
    const percent = document.getElementById('weekly-goal-percent');
    const target = document.getElementById('weekly-goal-target');
    if (!fill) return;
    const goalMin = getWeeklyGoalMinutes();
    const weekSec = getWeekSeconds(daily || {});
    const weekMin = Math.round(weekSec / 60);
    const pct = Math.min(100, Math.round(weekMin / goalMin * 100));
    fill.style.width = pct + '%';
    fill.classList.toggle('complete', pct >= 100);
    current.textContent = `本周已读 ${weekMin} 分钟`;
    percent.textContent = pct + '%';
    if (pct >= 100) {
        target.textContent = `🎯 目标 ${goalMin} 分钟 · 完成！`;
    } else {
        target.textContent = `目标 ${goalMin} 分钟`;
    }
}

// 周目标编辑弹窗
function openWeeklyGoalEditor() {
    let modal = document.getElementById('weekly-goal-modal');
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'weekly-goal-modal';
        modal.className = 'modal-overlay';
        document.body.appendChild(modal);
    }
    const current = getWeeklyGoalMinutes();
    modal.innerHTML = `
        <div class="modal-content" style="max-width:420px">
            <button class="modal-close">×</button>
            <h3>每周阅读目标</h3>
            <p style="color:var(--text-soft);font-size:13.5px;margin:0 0 4px;line-height:1.6">
                一周读多少分钟？30 - 1200 分钟（0.5 - 20 小时）。
                <br>建议起步 60-180 分钟，重在养成习惯。
            </p>
            <input type="number" class="weekly-goal-input" id="weekly-goal-input" 
                   min="30" max="1200" step="15" value="${current}" />
            <div class="weekly-goal-presets">
                <button data-min="60">1 小时</button>
                <button data-min="120">2 小时</button>
                <button data-min="180">3 小时</button>
                <button data-min="300">5 小时</button>
                <button data-min="600">10 小时</button>
            </div>
            <div class="modal-actions">
                <button class="btn-secondary" id="weekly-goal-cancel">取消</button>
                <button class="btn-primary" id="weekly-goal-save">保存</button>
            </div>
        </div>`;
    modal.classList.add('visible');
    const input = modal.querySelector('#weekly-goal-input');
    setTimeout(() => input.focus(), 50);
    // preset buttons
    modal.querySelectorAll('.weekly-goal-presets button').forEach(btn => {
        btn.classList.toggle('selected', parseInt(btn.dataset.min, 10) === current);
        btn.onclick = () => {
            input.value = btn.dataset.min;
            modal.querySelectorAll('.weekly-goal-presets button').forEach(b => b.classList.remove('selected'));
            btn.classList.add('selected');
        };
    });
    modal.querySelector('.modal-close').onclick = modal.querySelector('#weekly-goal-cancel').onclick = () => modal.classList.remove('visible');
    modal.querySelector('#weekly-goal-save').onclick = () => {
        const v = parseInt(input.value, 10);
        if (!Number.isFinite(v) || v < 30 || v > 1200) {
            input.focus();
            return;
        }
        setWeeklyGoalMinutes(v);
        modal.classList.remove('visible');
    };
    modal.onclick = (e) => { if (e.target === modal) modal.classList.remove('visible'); };
}

// ---- 章节分享按钮 ----
function shareChapter(anchor) {
    const article = document.getElementById(anchor);
    if (!article) return;
    const url = `${SITE_URL}#${anchor}`;
    const title = article.querySelector('.chapter-title')?.textContent.trim() || anchor;
    const bookSlug = article.dataset.book || '';
    const bookTitle = (BOOK_META[bookSlug] && BOOK_META[bookSlug].title) || bookSlug;
    const fullText = `${bookTitle} · ${title}\n${url}`;
    const btn = document.querySelector(`.chapter-share-btn[data-share-anchor="${anchor}"]`);

    function markCopied() {
        if (!btn) return;
        const orig = btn.innerHTML;
        btn.classList.add('copied');
        btn.innerHTML = '<svg class="icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-2px"><polyline points="20 6 9 17 4 12"/></svg>已复制';
        setTimeout(() => { btn.classList.remove('copied'); btn.innerHTML = orig; }, 2000);
    }

    // 优先用 navigator.share（手机原生分享）
    if (navigator.share) {
        navigator.share({ title: `${bookTitle} · ${title}`, text: title, url }).then(markCopied).catch(() => copyFallback());
    } else {
        copyFallback();
    }
    function copyFallback() {
        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(fullText).then(markCopied).catch(() => legacyCopy(fullText, markCopied));
        } else {
            legacyCopy(fullText, markCopied);
        }
    }
    function legacyCopy(text, cb) {
        const ta = document.createElement('textarea');
        ta.value = text;
        ta.style.position = 'fixed';
        ta.style.opacity = '0';
        document.body.appendChild(ta);
        ta.select();
        try { document.execCommand('copy'); cb(); } catch (e) {}
        document.body.removeChild(ta);
    }
}

// 绑定分享按钮（事件委托，章节动态渲染也适用）
document.addEventListener('click', (e) => {
    const btn = e.target.closest('.chapter-share-btn');
    if (btn) {
        e.preventDefault();
        const anchor = btn.dataset.shareAnchor;
        if (anchor) shareChapter(anchor);
    }
    const editBtn = e.target.closest('#weekly-goal-edit');
    if (editBtn) {
        e.preventDefault();
        openWeeklyGoalEditor();
    }
});

// TTS 朗读按钮的可见性 / audioUrl 在 build 时已确定（扫 assets/audio/），
// 这里不需要再跑 HEAD 探测。点击时直接从 data-audio-url 取地址即可。

let ttsCurrentAudio = null;
let ttsCurrentBtn = null;
function toggleTts(btn) {
    const url = btn.dataset.audioUrl;
    const player = document.querySelector(`.chapter-tts-player[data-tts-player="${btn.dataset.ttsAnchor}"]`);
    if (!player) return;

    if (ttsCurrentAudio && !ttsCurrentAudio.paused) {
        ttsCurrentAudio.pause();
        if (ttsCurrentBtn) {
            ttsCurrentBtn.classList.remove('playing');
            ttsCurrentBtn.querySelector('.tts-label').textContent = '朗读';
            ttsCurrentBtn.innerHTML = ttsCurrentBtn.innerHTML.replace('volume-x', 'volume');
        }
        ttsCurrentAudio = null;
        ttsCurrentBtn = null;
        return;
    }

    // 新建或复用 audio
    if (!player.querySelector('audio')) {
        player.innerHTML = `<audio controls preload="none" src="${url}"></audio>`;
    }
    const audio = player.querySelector('audio');

    // 关闭其他正在播放的
    if (ttsCurrentAudio && ttsCurrentAudio !== audio) {
        ttsCurrentAudio.pause();
        ttsCurrentAudio.currentTime = 0;
        if (ttsCurrentBtn) {
            ttsCurrentBtn.classList.remove('playing');
            ttsCurrentBtn.querySelector('.tts-label').textContent = '朗读';
        }
    }

    audio.play();
    ttsCurrentAudio = audio;
    ttsCurrentBtn = btn;
    btn.classList.add('playing');
    btn.querySelector('.tts-label').textContent = '暂停';
    player.classList.add('open');
    // MediaSession 锁屏控制: 设置 metadata + 动作 handler
    setupMediaSession(btn, audio);

    audio.onended = () => {
        btn.classList.remove('playing');
        btn.querySelector('.tts-label').textContent = '朗读';
        player.classList.remove('open');
        ttsCurrentAudio = null;
        ttsCurrentBtn = null;
    };
    audio.onerror = () => {
        btn.classList.remove('playing');
        btn.querySelector('.tts-label').textContent = '朗读';
        ttsCurrentAudio = null;
        ttsCurrentBtn = null;
    };
}

document.addEventListener('click', (e) => {
    const ttsBtn = e.target.closest('.chapter-tts-btn');
    if (ttsBtn) {
        e.preventDefault();
        toggleTts(ttsBtn);
    }
});

// MediaSession 锁屏 / 系统通知控制: chapter title + book + 上一章 / 下一章 / 播放暂停
function setupMediaSession(btn, audio) {
    if (!('mediaSession' in navigator)) return;
    const chapterId = btn.dataset.ttsAnchor;
    const article = document.getElementById(chapterId);
    const chapterTitle = (article && article.querySelector('.chapter-title')?.textContent) || chapterId;
    const bookSlug = (typeof CHAPTER_BOOK_MAP !== 'undefined') ? CHAPTER_BOOK_MAP[chapterId] : '';
    const bookTitle = (BOOKS_META[bookSlug] && BOOKS_META[bookSlug].title) || '知识花园';
    // 找相邻章节 (供 nexttrack / previoustrack)
    const all = (typeof CHAPTERS !== 'undefined') ? CHAPTERS : [];
    const idx = all.indexOf(chapterId);
    const prevId = (idx > 0) ? all[idx - 1] : null;
    const nextId = (idx >= 0 && idx + 1 < all.length) ? all[idx + 1] : null;
    // metadata
    try {
        navigator.mediaSession.metadata = new MediaMetadata({
            title: chapterTitle,
            artist: bookTitle,
            album: '知识花园',
        });
    } catch (e) { /* 旧浏览器 / 不支持 metadata, 跳过 */ }
    // 动作 handler
    navigator.mediaSession.setActionHandler('play', () => audio.play());
    navigator.mediaSession.setActionHandler('pause', () => audio.pause());
    if (prevId) {
        const prevBtn = document.querySelector(`.chapter-tts-btn[data-tts-anchor="${prevId}"]`);
        if (prevBtn && prevBtn.dataset.audioUrl) {
            navigator.mediaSession.setActionHandler('previoustrack', () => {
                audio.pause();
                toggleTts(prevBtn);
            });
        }
    }
    if (nextId) {
        const nextBtn = document.querySelector(`.chapter-tts-btn[data-tts-anchor="${nextId}"]`);
        if (nextBtn && nextBtn.dataset.audioUrl) {
            navigator.mediaSession.setActionHandler('nexttrack', () => {
                audio.pause();
                toggleTts(nextBtn);
            });
        }
    }
    // 同步状态
    audio.addEventListener('play', () => navigator.mediaSession.playbackState = 'playing');
    audio.addEventListener('pause', () => navigator.mediaSession.playbackState = 'paused');
    audio.addEventListener('ended', () => navigator.mediaSession.playbackState = 'none');
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

function refreshBookProgressUI() {
    // 按 book 分组统计已完成章节数
    const byBook = {};
    document.querySelectorAll('.chapter').forEach(article => {
        const b = article.dataset.book;
        if (!byBook[b]) byBook[b] = { done: 0, total: 0 };
        byBook[b].total += 1;
        if (progress.completed[article.id]) byBook[b].done += 1;
    });
    document.querySelectorAll('.chap-progress-pct').forEach(el => {
        const b = el.dataset.bookProgress;
        const s = byBook[b];
        if (s && s.total > 0) {
            const pct = Math.round(s.done / s.total * 100);
            el.textContent = '\u6574\u672c ' + pct + '% (\u5df2\u8bfb ' + s.done + '/' + s.total + ')';
        }
    });
    // 同步更新 sidebar 上的 book-level 进度
    document.querySelectorAll('.book-group').forEach(g => {
        const b = g.dataset.book;
        const s = byBook[b];
        const bar = g.querySelector('.book-progress-bar-fill');
        const label = g.querySelector('.book-progress-label');
        if (s && bar && label) {
            const pct = Math.round(s.done / s.total * 100);
            bar.style.width = pct + '%';
            label.textContent = s.done + ' / ' + s.total;
        }
    });
}

// ============================================================
// Homepage TOC：渲染 overview section 的进度标记 + 继续阅读卡
// ============================================================
const CHECK_SVG = '<svg class="icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>';
const DOT_SVG = '<svg class="icon" width="8" height="8" viewBox="0 0 24 24" fill="currentColor"><circle cx="12" cy="12" r="6"/></svg>';

// 继续阅读 carousel: 1 个 primary (lastRead) + 2-3 个 "next" (同系列下一章 / RELATED / 7 天书签)
function renderResumeCarousel() {
    const wrap = document.getElementById('resume-carousel');
    const track = document.getElementById('resume-carousel-track');
    if (!wrap || !track) return;
    const prog = JSON.parse(localStorage.getItem('progress') || '{}');
    const cards = [];
    // 1) Primary: lastRead
    const last = prog.lastRead;
    if (last && last.chapterId) {
        const article = document.getElementById(last.chapterId);
        if (article) {
            const title = article.querySelector('.chapter-title')?.textContent || last.chapterId;
            const book = CHAPTER_BOOK_MAP[last.chapterId] || '';
            const bookTitle = (BOOKS_META[book] && BOOKS_META[book].title) || book;
            const ago = formatRelativeTime(last.timestamp);
            // 进度: 从 progress.readPct[chapterId] 取
            const progAll = JSON.parse(localStorage.getItem('progress') || '{}');
            const readPctMap = (progAll && progAll.readPct) || {};
            const pct = Math.min(99, readPctMap[last.chapterId] || 0);
            cards.push({
                chapterId: last.chapterId,
                title: title,
                book: book,
                bookTitle: bookTitle,
                eyebrow: '继续阅读',
                meta: '上次 ' + ago,
                pct: pct,
                primary: true
            });
            // 2) 同系列下一章 (同书 + 索引 + 1)
            const allInBook = (CHAPTERS_BY_BOOK && CHAPTERS_BY_BOOK[book]) || [];
            const idx = allInBook.indexOf(last.chapterId);
            if (idx >= 0 && idx + 1 < allInBook.length) {
                const nextId = allInBook[idx + 1];
                const nArticle = document.getElementById(nextId);
                if (nArticle) {
                    const nTitle = nArticle.querySelector('.chapter-title')?.textContent || nextId;
                    cards.push({
                        chapterId: nextId,
                        title: nTitle,
                        book: book,
                        bookTitle: bookTitle,
                        eyebrow: '同系列下一章',
                        meta: '',
                        pct: 0,
                        primary: false
                    });
                }
            }
        }
    }
    // 3) 主题 RELATED (复用 dense index) — 找 primary 章节的 top-1 related
    if (cards.length > 0 && cards.length < 4 && _kbDenseIndex && _kbDenseIndex.chapters) {
        const primaryId = cards[0].chapterId;
        const chIdx = _kbDenseIndex.chapters.findIndex(c => c.id === primaryId);
        if (chIdx >= 0) {
            const emb = kbDecodeEmbedding(_kbDenseIndex.chapters[chIdx].embedding);
            const cands = _kbDenseIndex.chapters
                .map((c, i) => ({ id: c.id, bookSlug: c.bookSlug, bookTitle: c.bookTitle, chapterTitle: c.chapterTitle, score: cosineSim(emb, kbDecodeEmbedding(c.embedding)) }))
                .filter(c => c.id !== primaryId && !cards.some(cc => cc.chapterId === c.id))
                .sort((a, b) => b.score - a.score)
                .slice(0, 4 - cards.length);
            cands.forEach(c => {
                const article = document.getElementById(c.id);
                if (!article) return;
                const cTitle = article.querySelector('.chapter-title')?.textContent || c.chapterTitle;
                const cBook = CHAPTER_BOOK_MAP[c.id] || c.bookSlug;
                const cBookTitle = (BOOKS_META[cBook] && BOOKS_META[cBook].title) || c.bookTitle;
                cards.push({
                    chapterId: c.id,
                    title: cTitle,
                    book: cBook,
                    bookTitle: cBookTitle,
                    eyebrow: '主题相关',
                    meta: '',
                    pct: 0,
                    primary: false
                });
            });
        }
    }
    if (cards.length === 0) {
        wrap.style.display = 'none';
        return;
    }
    // 渲染
    const arrowSvg = '<svg class="icon resume-arrow" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="7" y1="17" x2="17" y2="7"/><polyline points="7 7 17 7 17 17"/></svg>';
    track.innerHTML = cards.map(c => {
        const cls = c.primary ? 'resume-card primary' : 'resume-card';
        return '<a class="' + cls + '" href="#' + c.chapterId + '">' +
            (c.primary ? arrowSvg : '') +
            '<div class="resume-card-head"><span class="dot"></span><span>' + c.eyebrow + '</span></div>' +
            '<div class="resume-card-book">' + c.bookTitle + '</div>' +
            '<div class="resume-card-title">' + c.title + '</div>' +
            (c.pct > 0 ? '<div class="resume-card-progress"><div class="resume-card-progress-fill" style="width:' + c.pct + '%"></div></div>' : '') +
            '<div class="resume-card-meta">' + (c.meta || '<span>未开始</span>') + (c.pct > 0 ? '<span>' + c.pct + '%</span>' : '') + '</div>' +
            '</a>';
    }).join('');
    wrap.style.display = '';
}

function renderOverview() {
    // 1. 章节 marker (✓ / ◐ / ○)
    document.querySelectorAll('.ov-ch-marker').forEach(el => {
        const id = el.dataset.chapter;
        const isCompleted = !!progress.completed[id];
        const pct = progress.readPct[id] || 0;
        el.classList.remove('is-done', 'is-progress');
        if (isCompleted) {
            el.classList.add('is-done');
            el.innerHTML = CHECK_SVG;
        } else if (pct >= 10) {
            el.classList.add('is-progress');
            el.innerHTML = DOT_SVG;
        } else {
            el.innerHTML = '';
        }
    });

    // 2. 每个 series 的进度条 + 文字
    document.querySelectorAll('.overview-card').forEach(card => {
        const bookSlug = card.dataset.book;
        const chapters = card.querySelectorAll('.ov-ch-marker');
        let done = 0;
        chapters.forEach(m => {
            const id = m.dataset.chapter;
            if (progress.completed[id]) done++;
        });
        const total = chapters.length;
        const pct = total > 0 ? Math.round(done / total * 100) : 0;
        const fill = card.querySelector('[data-book-fill="' + bookSlug + '"]');
        const label = card.querySelector('[data-book-label="' + bookSlug + '"]');
        if (fill) fill.style.width = pct + '%';
        if (label) label.textContent = done + ' / ' + total;
    });

    // 3. 顶部总览 "已读 %"
    const overallPctEl = document.getElementById('overview-read-pct');
    if (overallPctEl) {
        const total = document.querySelectorAll('.ov-ch-marker').length;
        const done = Object.keys(progress.completed).length;
        const pct = total > 0 ? Math.round(done / total * 100) : 0;
        overallPctEl.textContent = pct;
    }

    // 4. 个人数据看板
    const setText = (id, n) => { const el = document.getElementById(id); if (el) el.textContent = n; };
    const completedCount = Object.keys(progress.completed).length;
    setText('d-read-count', completedCount);
    const inProgress = Object.values(progress.readPct || {}).filter(p => p > 0 && p < 100).length;
    setText('d-reading-count', inProgress);
    const totalSeconds = Object.values(progress.timeSpent || {}).reduce((a, b) => a + b, 0);
    setText('d-time-spent', Math.round(totalSeconds / 60));
    const notesCount = Object.values(notes).reduce((acc, arr) => acc + (Array.isArray(arr) ? arr.length : 0), 0);
    setText('d-notes-count', notesCount);
    const bookmarksCount = Object.values(bookmarks).reduce((acc, arr) => acc + (Array.isArray(arr) ? arr.length : 0), 0);
    setText('d-bookmarks-count', bookmarksCount);
    // 连续阅读天数（基于 dailyTime）
    const daily = progress.dailyTime || {};
    const dates = Object.keys(daily).sort();
    let streak = 0;
    if (dates.length) {
        const oneDay = 86400000;
        const today = new Date();
        today.setHours(0, 0, 0, 0);
        for (let i = 0; i < 365; i++) {
            const d = new Date(today.getTime() - i * oneDay);
            const k = d.toISOString().slice(0, 10);
            if (daily[k] && daily[k] > 0) streak++;
            else if (i > 0) break;
        }
    }
    setText('d-streak-days', streak);
    const streakEl = document.getElementById('dashboard-streak');
    if (streakEl) {
        if (streak >= 1) {
            const msg = streak >= 7 ? '太稳了！保持这个节奏。' : streak >= 3 ? '正在养成习惯。' : '继续，节奏起来了。';
            streakEl.innerHTML = '<span class="flame">●</span> 已连续 ' + streak + ' 天阅读 · ' + msg;
        } else {
            streakEl.textContent = '开始你的第一次阅读，建立连续记录。';
        }
    }
    // GitHub-style 16 周阅读热度图
    renderStreakHeatmap(daily);
    // 里程碑 / 成就
    renderAchievements();

    // 6. 周阅读目标进度（基于本周 dailyTime 总和）
    refreshWeeklyGoal(daily);

    // 7. 今日复习队列（基于笔记 + 间隔重复状态）
    refreshReviewQueue();

    // 6. 周阅读目标进度（基于本周 dailyTime 总和）
    refreshWeeklyGoal(daily);

    // 5. 每周回顾（基于 dailyTime + completed 时间戳）— 支持 本周/本月/今年 三档
    renderRecap();

    // 4. 继续阅读 carousel (1 个 primary + 2-3 个 pick up next)
    renderResumeCarousel();

    // 5. 学习路径 (基于 reading history / RELATED / 7 天书签 / 7 天笔记 / priority)
    renderLearningPath();
}

// ============================================================
// 全局当前 recap tab，刷新 overview 时保留
// （renderRecap + 点击事件定义在 renderOverview 外部，避免内部 let TDZ）
// ============================================================
let _recapRange = 'week';
function renderRecap() {
    const weeklyGrid = document.getElementById('weekly-grid');
    const summaryEl = document.getElementById('recap-summary');
    if (!weeklyGrid) return;

    const oneDay = 86400000;
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const range = _recapRange;
    const rangeMs = range === 'week' ? 7 * oneDay : range === 'month' ? 30 * oneDay : 365 * oneDay;
    const rangeLabel = range === 'week' ? '本周' : range === 'month' ? '本月' : '今年';
    // 重新读 localStorage（独立函数不依赖外层局部变量）
    const prog = JSON.parse(localStorage.getItem('progress') || '{}');
    // 笔记是 array of {chapterId, bookSlug, text, timestamp}，不是按 chapterId 分组的 map
    const notesArr = Array.isArray(notes) ? notes : JSON.parse(localStorage.getItem('notes') || '[]');
    const daily = prog.daily || {};

    // 区间内阅读秒数（按 daily）
    let rangeSec = 0;
    const daysToScan = Math.min(rangeMs / oneDay, 366);
    for (let i = 0; i < daysToScan; i++) {
        const d = new Date(today.getTime() - i * oneDay);
        const k = d.toISOString().slice(0, 10);
        rangeSec += (daily[k] || 0);
    }
    // 区间内已读章节
    let rangeCount = 0;
    for (const [cid, ts] of Object.entries(prog.completed || {})) {
        if (!ts || typeof ts !== 'number') continue;
        const dt = new Date(ts);
        const diff = today.getTime() - new Date(dt.getFullYear(), dt.getMonth(), dt.getDate()).getTime();
        if (diff >= 0 && diff < rangeMs) rangeCount++;
    }
    // 区间内新增笔记
    let rangeNotes = 0;
    for (const n of notesArr) {
        if (!n || typeof n.timestamp !== 'number') continue;
        const dt = new Date(n.timestamp);
        const diff = today.getTime() - new Date(dt.getFullYear(), dt.getMonth(), dt.getDate()).getTime();
        if (diff >= 0 && diff < rangeMs) rangeNotes++;
    }
    // 区间内涉及的不同书数
    const rangeBooks = new Set();
    for (const [cid, ts] of Object.entries(prog.completed || {})) {
        if (!ts || typeof ts !== 'number') continue;
        const dt = new Date(ts);
        const diff = today.getTime() - new Date(dt.getFullYear(), dt.getMonth(), dt.getDate()).getTime();
        if (diff >= 0 && diff < rangeMs) {
            const m = cid.match(/^([^_]+)__/);
            if (m) rangeBooks.add(m[1]);
        }
    }

    const cells = [
        { num: rangeCount, lbl: '已读章节' },
        { num: Math.round(rangeSec / 60), lbl: '阅读分钟' },
        { num: rangeNotes, lbl: '新增笔记' },
        { num: rangeBooks.size, lbl: '涉及系列' },
    ];
    const hasAny = cells.some(c => c.num > 0);
    if (hasAny) {
        weeklyGrid.innerHTML = cells.map(c =>
            '<div class="weekly-cell"><div class="weekly-num">' + c.num + '</div><div class="weekly-lbl">' + c.lbl + '</div></div>'
        ).join('');
    } else {
        const emptyMsg = range === 'week' ? '本周还没有阅读记录 — 去读一章开始累计。'
            : range === 'month' ? '本月还没有阅读记录。'
            : '今年还没有阅读记录。';
        weeklyGrid.innerHTML = '<div class="weekly-empty">' + emptyMsg + '</div>';
    }
    // 顶上一行简短 summary
    if (summaryEl) {
        const totalChapters = document.querySelectorAll('.chapter[data-book]').length;
        const pct = totalChapters ? Math.round(Object.keys(prog.completed || {}).length / totalChapters * 100) : 0;
        summaryEl.innerHTML = rangeLabel + '读了 <strong>' + rangeCount + '</strong> 章 · '
            + Math.round(rangeSec / 60) + ' 分钟 · 涉及 <strong>' + rangeBooks.size + '</strong> 个系列 · '
            + '累计 ' + pct + '% 进度';
    }
}

// 切换本周/本月/今年
document.addEventListener('click', (e) => {
    const tab = e.target.closest('.recap-tab');
    if (tab) {
        e.preventDefault();
        const range = tab.dataset.range;
        if (range && range !== _recapRange) {
            _recapRange = range;
            document.querySelectorAll('.recap-tab').forEach(t => t.classList.toggle('active', t === tab));
            renderRecap();
        }
    }
});

// 复制 weekly recap 为 Markdown (发邮件 / 笔记用)
function buildRecapMarkdown() {
    const rangeLabel = _recapRange === 'week' ? '本周' : _recapRange === 'month' ? '本月' : '今年';
    const summaryEl = document.getElementById('recap-summary');
    const summaryText = summaryEl ? summaryEl.innerText.trim() : '';
    const rangeDays = _recapRange === 'week' ? 7 : _recapRange === 'month' ? 30 : 365;
    const lines = [`# 知识花园 · ${rangeLabel}阅读摘要`, ''];
    if (summaryText) lines.push(summaryText, '');
    lines.push(`> 自动生成于 ${new Date().toISOString().slice(0, 10)}`);
    return lines.join('\\n');
}
document.addEventListener('click', async (e) => {
    const btn = e.target.closest('#recap-export');
    if (!btn) return;
    e.preventDefault();
    const md = buildRecapMarkdown();
    try {
        await navigator.clipboard.writeText(md);
        btn.classList.add('copied');
        const orig = btn.textContent;
        btn.textContent = '已复制';
        setTimeout(() => { btn.classList.remove('copied'); btn.textContent = orig; }, 1500);
    } catch (err) {
        // 回退: 用临时 textarea
        const ta = document.createElement('textarea');
        ta.value = md;
        document.body.appendChild(ta);
        ta.select();
        try { document.execCommand('copy'); btn.textContent = '已复制'; } catch (e2) { btn.textContent = '复制失败'; }
        document.body.removeChild(ta);
        setTimeout(() => { btn.textContent = '复制'; }, 1500);
    }
});

// 学习路径：基于 reading history / RELATED / 7 天书签 / 7 天笔记 / priority
// - 老用户：5 章个性化（in-progress / 同系列下一章 / 主题 RELATED / 7 天书签 / 7 天笔记）
// - 新用户（无 history）：5 个 series 按 priority 取首章
function renderLearningPath() {
    const container = document.getElementById('learning-path');
    if (!container) return;

    const completed = Object.keys(progress.completed || {});
    const readPct = progress.readPct || {};
    const bookmarks = Object.keys(progress.bookmarks || {});

    // 构建 chapter 索引 (DOM 一次性扫)
    const allChapters = {};
    document.querySelectorAll('.chapter[data-book]').forEach(el => {
        allChapters[el.id] = {
            id: el.id,
            bookSlug: el.dataset.book,
            chapSlug: el.dataset.chap,
            title: el.querySelector('.chapter-title')?.textContent.trim() || el.id,
        };
    });
    const chaptersByBook = {};
    Object.values(allChapters).forEach(c => {
        if (!chaptersByBook[c.bookSlug]) chaptersByBook[c.bookSlug] = [];
        chaptersByBook[c.bookSlug].push(c);
    });
    Object.values(chaptersByBook).forEach(arr => arr.sort((a, b) => a.chapSlug.localeCompare(b.chapSlug)));

    const hasHistory = completed.length > 0 || bookmarks.length > 0 || notes.length > 0;

    // 主题 RELATED（与 renderPersonalRecs 旧版同源）
    const RELATED = {
        'rag': ['multi-agent', 'llm-prompt', 'context-engineering'],
        'multi-agent': ['crewai', 'harness-engineering', 'claude-code'],
        'crewai': ['multi-agent', 'harness-engineering', 'agent-skills'],
        'llm-prompt': ['context-engineering', 'rag', 'vibe-coding'],
        'context-engineering': ['memory-architecture', 'rag', 'llm-prompt'],
        'harness-engineering': ['multi-agent', 'claude-code', 'a2a-multi-agent'],
        'claude-code': ['vibe-coding', 'harness-engineering', 'agent-skills', 'cn-codex'],
        'vibe-coding': ['claude-code', 'llm-prompt', 'a2a-multi-agent', 'cn-codex'],
        'agent-skills': ['claude-code', 'harness-engineering', 'a2a-multi-agent'],
        'a2a-multi-agent': ['memory-architecture', 'harness-engineering', 'vibe-coding'],
        'memory-architecture': ['context-engineering', 'harness-engineering', 'a2a-multi-agent'],
        'embodied-agent': ['llm-prompt', 'multi-agent', 'vibe-coding'],
        'ai-content-economy': ['vibe-coding', 'claude-code', 'indie-ai-product'],
        'agent-cost': ['harness-engineering', 'claude-code', 'multi-agent'],
        'indie-ai-product': ['vibe-coding', 'ai-content-economy', 'claude-code'],
        'codex-cases': ['vibe-coding', 'claude-code', 'harness-engineering', 'a2a-multi-agent', 'cn-codex'],
        'cn-codex': ['codex-cases', 'vibe-coding', 'claude-code', 'a2a-multi-agent'],
    };

    let top, headerTitle, headerDesc;

    if (hasHistory) {
        // === 老用户：5 策略打分 ===
        const recs = [];

        // 1) 继续读 (10 分)
        Object.entries(readPct).forEach(([cid, pct]) => {
            if (pct >= 10 && pct <= 90 && !completed.includes(cid)) {
                const c = allChapters[cid];
                if (c) recs.push({ ...c, score: 10, reason: '上次读到 ' + pct + '%，还没看完' });
            }
        });

        // 2) 同系列下一章 (8 分)
        completed.forEach(cid => {
            const c = allChapters[cid];
            if (!c) return;
            const arr = chaptersByBook[c.bookSlug];
            if (!arr) return;
            const idx = arr.findIndex(x => x.id === cid);
            if (idx >= 0 && idx + 1 < arr.length) {
                const next = arr[idx + 1];
                if (!completed.includes(next.id)) {
                    const bookTitle = (BOOK_META[c.bookSlug] || {}).title || c.bookSlug;
                    if (!recs.find(r => r.id === next.id)) {
                        recs.push({ ...next, score: 8, reason: '续《' + bookTitle + '》第 ' + (idx + 2) + ' 章' });
                    }
                }
            }
        });

        // 3) 主题 RELATED 跨书桥接 (5 分)
        const readBooks = new Set(Object.values(allChapters).filter(c => completed.includes(c.id)).map(c => c.bookSlug));
        const seenTarget = new Set(recs.map(r => r.id));
        readBooks.forEach(book => {
            const related = RELATED[book] || [];
            related.forEach(rb => {
                if (readBooks.has(rb)) return;
                const arr = chaptersByBook[rb] || [];
                const target = arr.find(c => !completed.includes(c.id) && !seenTarget.has(c.id));
                if (target) {
                    const bookTitle = (BOOK_META[book] || {}).title || book;
                    recs.push({ ...target, score: 5, reason: '读《' + bookTitle + '》之后通常会看这条线' });
                    seenTarget.add(target.id);
                }
            });
        });

        // 4) 7 天内书签 (3 分)
        const sevenDaysAgo = Date.now() - 7 * 86400000;
        bookmarks.forEach(bid => {
            const bm = progress.bookmarks[bid];
            if (!bm || bm.timestamp < sevenDaysAgo) return;
            const c = allChapters[bid];
            if (c && !completed.includes(c.id)) {
                const reason = formatRelativeTime(bm.timestamp) + ' 加的书签，还没读完';
                if (!recs.find(r => r.id === c.id)) recs.push({ ...c, score: 3, reason });
            }
        });

        // 5) 7 天内有笔记的章节 (2 分) — 笔记代表用户深度关注
        const recentNoteChapters = new Set();
        for (const n of notes) {
            if (n && typeof n.timestamp === 'number' && n.timestamp >= sevenDaysAgo && n.chapterId) {
                recentNoteChapters.add(n.chapterId);
            }
        }
        recentNoteChapters.forEach(cid => {
            const c = allChapters[cid];
            if (c && !completed.includes(cid)) {
                const reason = '7 天内在这章加了笔记，再翻一遍可能有新发现';
                if (!recs.find(r => r.id === c.id)) recs.push({ ...c, score: 2, reason });
            }
        });

        // 排序 + 去重 + top 5
        recs.sort((a, b) => b.score - a.score);
        const seen = new Set();
        top = [];
        for (const r of recs) {
            if (seen.has(r.id)) continue;
            seen.add(r.id);
            top.push(r);
            if (top.length >= 5) break;
        }
        headerTitle = '你的学习路径';
        headerDesc = '基于阅读历史 + 主题关联 + 7 天书签 + 7 天笔记，共 ' + top.length + ' 章。';
    } else {
        // === 新用户：按 BOOKS_META priority 取前 5 个 series 的首章 ===
        const booksArr = Object.entries(BOOKS_META)
            .map(([slug, m]) => ({ slug, ...m }))
            .sort((a, b) => a.priority - b.priority)
            .slice(0, 5);
        top = booksArr.map(b => ({
            id: b.firstChapter.anchor,
            bookSlug: b.slug,
            title: b.firstChapter.title,
            reason: b.desc ? (b.desc.length > 50 ? b.desc.slice(0, 50) + '…' : b.desc) : '从这里开始入门',
        }));
        headerTitle = '新人路线 · 5 章入门';
        headerDesc = '不知道从哪开始？按 priority 排序的 5 个系列首章，1 周内建立 AI 应用开发心智模型。';
    }

    if (top.length === 0) {
        container.style.display = 'none';
        return;
    }
    container.style.display = '';

    // 渲染为有序列表 (步骤感)
    container.innerHTML =
        '<h2 class="section-h2">' + headerTitle + '</h2>' +
        '<p class="section-desc">' + headerDesc + '</p>' +
        '<ol class="rec-path-list">' +
        top.map((r, i) => {
            const bm = (typeof BOOK_META !== 'undefined' && BOOK_META[r.bookSlug]) || {};
            const booksMetaRow = BOOKS_META[r.bookSlug] || {};
            const bookTitle = bm.title || booksMetaRow.title || r.bookSlug;
            const color = booksMetaRow.color || '#b08968';
            const icon = booksMetaRow.icon || 'book';
            return (
                '<li class="rec-path-item">' +
                '<span class="rec-step">' + String(i + 1).padStart(2, '0') + '</span>' +
                '<a class="rec-link" href="#' + r.id + '">' +
                '<span class="rec-icon" style="color:' + color + '">' + svg_icon(icon, 18) + '</span>' +
                '<span class="rec-title">' + r.title + '</span>' +
                '<span class="rec-book">' + bookTitle + '</span>' +
                '</a>' +
                '<span class="rec-why">' + r.reason + '</span>' +
                '</li>'
            );
        }).join('') +
        '</ol>';
}

// ============================================================
// 知识问答：TF-IDF 向量 + cosine 相似度
// - 索引 assets/knowledge_index.json 由 build_reader.py 预生成
// - 首次使用按需加载（~1.7 MB），之后浏览器缓存
// - 搜索 = tokenize(query) → query vector → dot(q, d)/(||q||*||d||) → top 5
// ============================================================
let _kbIndex = null;
let _kbIndexLoading = null;

async function loadKnowledgeIndex() {
    if (_kbIndex) return _kbIndex;
    if (_kbIndexLoading) return _kbIndexLoading;
    _kbIndexLoading = fetch('assets/knowledge_index.json').then(r => r.json());
    _kbIndex = await _kbIndexLoading;
    return _kbIndex;
}

function kbTokenize(text) {
    const terms = [];
    // ASCII words (lowercased)
    const asciiMatches = text.match(/[A-Za-z0-9]+/g);
    if (asciiMatches) for (const w of asciiMatches) terms.push(w.toLowerCase());
    // CJK 1-gram + 2-gram
    const cjk = text.replace(/[A-Za-z0-9\s]+/g, ' ');
    for (let i = 0; i < cjk.length; i++) {
        const c = cjk[i];
        if (c >= '\u4e00' && c <= '\u9fff') terms.push(c);
    }
    for (let i = 0; i < cjk.length - 1; i++) {
        const c1 = cjk[i], c2 = cjk[i + 1];
        if (c1 >= '\u4e00' && c1 <= '\u9fff' && c2 >= '\u4e00' && c2 <= '\u9fff') {
            terms.push(c1 + c2);
        }
    }
    return terms;
}

function kbSearch(query, topK) {
    if (topK == null) topK = 5;
    const idx = _kbIndex;
    if (!idx) return [];
    const terms = kbTokenize(query);
    if (!terms.length) return [];
    // query TF
    const qTF = {};
    for (const t of terms) qTF[t] = (qTF[t] || 0) + 1;
    // query vector (TF-IDF weighted)
    const qVec = {};
    let qSq = 0;
    for (const t in qTF) {
        const idf = idx.idf[t];
        if (!idf) continue;
        const w = idf * qTF[t];
        qVec[t] = w;
        qSq += w * w;
    }
    const qNorm = Math.sqrt(qSq) || 1;
    // score each chunk
    const scored = [];
    for (let i = 0; i < idx.chunks.length; i++) {
        const c = idx.chunks[i];
        const cVec = c.vec;
        let dot = 0;
        for (const t in qVec) {
            if (cVec[t]) dot += qVec[t] * cVec[t];
        }
        if (dot <= 0) continue;
        const sim = dot / (qNorm * c.norm);
        scored.push({ idx: i, score: sim });
    }
    scored.sort((a, b) => b.score - a.score);
    return scored.slice(0, topK);
}

function kbHighlight(text, query) {
    if (!query) return text;
    // 高亮 query 里的 CJK 子串 + ASCII word (escape regex meta)
    const parts = [];
    const cjk = query.match(/[\u4e00-\u9fff]+/g) || [];
    const ascii = query.match(/[A-Za-z0-9]+/g) || [];
    const terms = [...new Set([...cjk, ...ascii.map(w => w.toLowerCase())])].filter(t => t.length >= 1);
    if (!terms.length) return text;
    // 按长度倒序，避免短词覆盖长词（如 "R" 覆盖 "RAG"）
    terms.sort((a, b) => b.length - a.length);
    const esc = (s) => {
        let out = '';
        for (let i = 0; i < s.length; i++) {
            const c = s[i];
            if (c === '.' || c === '*' || c === '+' || c === '?' || c === '^' || c === '$' || c === '{' || c === '}' || c === '(' || c === ')' || c === '|' || c === '[' || c === ']' || c === String.fromCharCode(92)) {
                out += String.fromCharCode(92) + c;
            } else {
                out += c;
            }
        }
        return out;
    };
    const re = new RegExp('(' + terms.map(esc).join('|') + ')', 'gi');
    return text.replace(re, '<mark>$1</mark>');
}

// 围绕 query term 截取 snippet: 找到首个匹配位置,前后各 ±window 字符
// - 比固定 chunk[0:200] 更精准, 用户直接看到 query 命中上下文
function kbSnippet(text, query, winBefore, winAfter) {
    if (winBefore == null) winBefore = 60;
    if (winAfter == null) winAfter = 140;
    if (!text) return '';
    if (!query) return text.slice(0, winBefore + winAfter) + (text.length > winBefore + winAfter ? '…' : '');
    const lower = text.toLowerCase();
    const cjk = query.match(/[\u4e00-\u9fff]+/g) || [];
    const ascii = query.match(/[a-z0-9]+/g) || [];
    const terms = [...cjk, ...ascii.map(w => w.toLowerCase())].filter(t => t.length >= 1);
    if (!terms.length) return text.slice(0, winBefore + winAfter) + (text.length > winBefore + winAfter ? '…' : '');
    // 找首个 query term 出现位置 (CJK 单字可能太短, 优先 2-gram)
    let firstIdx = -1;
    const sortedTerms = terms.sort((a, b) => b.length - a.length);
    for (const t of sortedTerms) {
        const idx = lower.indexOf(t.toLowerCase());
        if (idx >= 0 && (firstIdx < 0 || idx < firstIdx)) firstIdx = idx;
    }
    if (firstIdx < 0) {
        // 没匹配, 用 chunk 前 200 字
        return text.slice(0, 200) + (text.length > 200 ? '…' : '');
    }
    const start = Math.max(0, firstIdx - winBefore);
    const end = Math.min(text.length, firstIdx + winAfter);
    let snippet = text.slice(start, end);
    if (start > 0) snippet = '…' + snippet;
    if (end < text.length) snippet = snippet + '…';
    return snippet;
}

// ============================================================
// 同义词扩展（精简版，只放 1 个最近同义词，避免 query 被稀释）
// - 优先 CJK ↔ CJK，English ↔ English，不跨语言扩展（太泛）
// - 严格控制条目：只加能解决明显语义鸿沟的（rag ↔ 检索增强生成）
// - 不引入模型，纯字符串替换
// ============================================================
const KB_SYNONYMS = {
    // RAG — 中文"检索增强生成"经常和 RAG 互替
    'rag': '检索增强生成',
    '检索增强生成': 'rag',
    // CoT
    'cot': '思维链',
    '思维链': 'cot',
    // Fine-tuning
    '微调': 'fine-tuning',
    'fine-tuning': '微调',
    // Hallucination
    '幻觉': 'hallucination',
    'hallucination': '幻觉',
    // Knowledge cutoff
    '知识截止': 'knowledge cutoff',
    // Tool
    '工具调用': 'function calling',
    'function calling': '工具调用',
    // Codex / Claude Code / Vibe Coding
    'claude code': 'claude-code',
    'vibe coding': '氛围编程',
    '氛围编程': 'vibe coding',
    // Memory
    '长期记忆': 'long-term memory',
    // MCP / A2A
    'mcp': 'model context protocol',
    'a2a': 'agent-to-agent',
    // 通用 IT 术语 (双向，避免 query 单边卡死)
    // 钱 → cost，调试 → debug，性能 → perf，等等
    '省钱': '成本 费用 开销 cost',
    '成本': 'cost 费用 省钱 开销',
    '费用': 'cost 成本 省钱',
    '性能': 'performance 性能优化 perf',
    '调试': 'debug debugging 排错',
    '排错': 'debug 调试',
    '测试': 'test testing',
    '部署': 'deploy deployment',
    '监控': 'monitor monitoring observability',
    '安全': 'security 安全防护',
    '并发': 'concurrency parallel 并行',
    '并行': 'parallel 并发',
    '缓存': 'cache caching 缓存策略',
    '日志': 'log logging 日志系统',
    '优化': 'optimize optimization',
    '升级': 'upgrade update',
    '回滚': 'rollback revert',
'压测': 'stress test 压力测试',
    '限流': 'rate limit throttling',
    '熔断': 'circuit breaker 熔断器',
    // 注意：不加 "agent" ↔ "智能体" 等基础术语的扩展
    // 因为 agent 在 cn-codex 系列里大量出现,扩展会污染结果
    // 'agent': '', // 占位（不扩展，避免污染）
};

function kbExpandSynonyms(query) {
    const lower = query.toLowerCase();
    let expanded = query;
    const escChars = new Set(['.', '*', '+', '?', '^', '$', '{', '}', '(', ')', '|', '[', ']', String.fromCharCode(92)]);
    for (const [key, syns] of Object.entries(KB_SYNONYMS)) {
        const k = key.toLowerCase();
        // Per-char escape 避免 char class 里 \\ 嵌套问题
        let escK = '';
        for (let i = 0; i < k.length; i++) {
            const c = k[i];
            escK += escChars.has(c) ? (String.fromCharCode(92) + c) : c;
        }
        const re = new RegExp('(^|[^a-z0-9\u4e00-\u9fff])' + escK + '(?=$|[^a-z0-9\u4e00-\u9fff])', 'i');
        if (re.test(lower)) {
            expanded += ' ' + syns;
        }
    }
    return expanded;
}

// 标题/章节加权：query term 出现在 chapterTitle OR bookTitle → 该 chunk ×boost
// - chapterTitle 完全命中 1 个 term：×5.0（强信号）
// - chapterTitle 命中 2+ terms：×8.0（极强信号，等于"这就是标题"）
// - 仅 bookTitle 命中：×2.0（弱信号，整个系列相关）
// - 都不命中：×1.0
// 上下文加权：query term 出现在 chapterTitle / bookTitle / bookDescription → chunk ×boost
// - chapterTitle 命中 2+ terms：×8.0 （"上下文窗口与 token 基础" 完美匹配）
// - chapterTitle 命中 1 term：×5.0
// - bookTitle 命中：×2.0 （整个系列相关）
// - bookDesc 命中（query 在系列描述里出现）：×1.5 （弱信号,避免抢主导）
// - 都不命中：×1.0
function kbTitleBoost(chunkIdx, query) {
    const idx = _kbIndex;
    if (!idx) return 1;
    const c = idx.chunks[chunkIdx];
    if (!c) return 1;
    const qLower = query.toLowerCase();
    const cjk = qLower.match(/[\u4e00-\u9fff]+/g) || [];
    const ascii = qLower.match(/[a-z0-9]+/g) || [];
    const qTerms = [...cjk, ...ascii].filter(t => t.length >= 2);
    if (!qTerms.length) return 1;
    const titleLower = (c.chapterTitle || '').toLowerCase();
    const bookLower = (c.bookTitle || '').toLowerCase();
    // bookDesc 从 BOOKS_META 拿
    const bookMeta = (typeof BOOKS_META !== 'undefined' && BOOKS_META[c.bookSlug]) || {};
    const descLower = (bookMeta.desc || '').toLowerCase();
    let chapterHit = 0, bookHit = 0, descHit = 0;
    for (const t of qTerms) {
        if (titleLower.includes(t)) chapterHit++;
        if (bookLower.includes(t)) bookHit++;
        if (descLower.includes(t)) descHit++;
    }
    if (chapterHit >= 2) return 8.0;
    if (chapterHit >= 1) return 5.0;
    if (bookHit >= 1) return 2.0;
    if (descHit >= 2) return 1.8;
    if (descHit >= 1) return 1.5;
    return 1;
}

// ============================================================
// Dense embedding 搜索（可选，需用户启用 AI 语义搜索）
// - 浏览器侧 lazy 加载 @xenova/transformers
// - 模型 Xenova/bge-small-zh-v1.5 (24MB int8 量化)，首次下载后续缓存
// - 跟 TF-IDF 索引 chunk ID 对齐
// ============================================================
let _kbDenseIndex = null;
let _kbDenseIndexLoading = null;
let _kbPipe = null;
let _kbPipeLoading = null;

async function loadKbDenseIndex() {
    if (_kbDenseIndex) return _kbDenseIndex;
    if (_kbDenseIndexLoading) return _kbDenseIndexLoading;
    _kbDenseIndexLoading = fetch('assets/knowledge_dense.json').then(r => r.json());
    _kbDenseIndex = await _kbDenseIndexLoading;
    return _kbDenseIndex;
}

async function loadKbPipe(onProgress) {
    if (_kbPipe) return _kbPipe;
    if (_kbPipeLoading) return _kbPipeLoading;
    // 1) 加载 transformers.js (本地 ESM)
    if (!window.transformers) {
        if (onProgress) onProgress('加载 transformers.js...');
        const url = new URL('assets/transformers.js', document.baseURI).href;
        const mod = await import(url);
        window.transformers = mod;
    }
    // 2) 加载模型（首次会下载 ~24MB int8 量化 ONNX）
    if (onProgress) onProgress('加载 AI 模型（首次约 24 MB）...');
    const { pipeline, env } = window.transformers;
    env.allowLocalModels = false;
    env.useBrowserCache = true;
    _kbPipeLoading = pipeline('feature-extraction', 'Xenova/bge-small-zh-v1.5', { quantized: true });
    _kbPipe = await _kbPipeLoading;
    return _kbPipe;
}

// 把 base64 编码的 512-dim float32 → Float32Array
function kbDecodeEmbedding(b64) {
    const bytes = Uint8Array.from(atob(b64), c => c.charCodeAt(0));
    return new Float32Array(bytes.buffer);
}

// cosine 相似度 (L2 normalized embeddings = dot product)
function cosineSim(a, b) {
    let dot = 0;
    for (let i = 0; i < a.length; i++) dot += a[i] * b[i];
    return dot;
}

async function kbEmbedQuery(query) {
    const pipe = await loadKbPipe();
    // BGE 中文模型推荐 query 加 "为这个句子生成表示以用于检索相关文章：" prefix
    const prefixed = '为这个句子生成表示以用于检索相关文章：' + query;
    const out = await pipe(prefixed, { pooling: 'mean', normalize: true });
    return new Float32Array(out.data);
}

function kbDenseScore(queryEmb, topN) {
    if (topN == null) topN = 50;
    const idx = _kbDenseIndex;
    if (!idx) return new Map();
    const chunks = idx.chunks;  // [id1, b641, id2, b642, ...]
    const scores = new Map();
    for (let i = 0; i < chunks.length; i += 2) {
        const id = chunks[i];
        const b64 = chunks[i + 1];
        const emb = kbDecodeEmbedding(b64);
        let dot = 0;
        for (let j = 0; j < 512; j++) dot += queryEmb[j] * emb[j];
        scores.set(id, dot);
    }
    // 返回 top-N (用 id 作 key,方便跟 TF-IDF id 合并)
    const sorted = Array.from(scores.entries()).sort((a, b) => b[1] - a[1]).slice(0, topN);
    return new Map(sorted);
}

// 章节去重 + 多样化：topK 个结果里,同一章节最多 2 个 chunk
// - 策略：先按 score 排序,然后贪心选,每章节计数,超过 2 个就跳过
function kbChapterDiverse(scored, topK) {
    const chapterCount = new Map();
    const out = [];
    for (const item of scored) {
        const ch = item.chapterId;
        const cnt = chapterCount.get(ch) || 0;
        if (cnt >= 2) continue;  // 每章节最多 2 个
        out.push(item);
        chapterCount.set(ch, cnt + 1);
        if (out.length >= topK) break;
    }
    // 如果去重后不够 topK,从剩余里继续选（不限每章节数）
    if (out.length < topK) {
        for (const item of scored) {
            if (out.includes(item)) continue;
            out.push(item);
            if (out.length >= topK) break;
        }
    }
    return out;
}

// 混合搜索：dense + TF-IDF + 标题加权 + 同义词扩展 + 章节去重
async function kbHybridSearch(query, useDense, topK) {
    if (topK == null) topK = 5;
    await loadKnowledgeIndex();
    const expandedQuery = kbExpandSynonyms(query);
    // 1) TF-IDF (用扩展 query 算) — 取更多候选(100)方便后续去重
    const tfidfHits = kbSearch(expandedQuery, 100);
    // 标题加权 + 章节首段加权 (chunk 0 通常是章节概述/引言, 概念查询更相关)
    const tfidfMap = new Map();
    for (const h of tfidfHits) {
        const c = _kbIndex.chunks[h.idx];
        let boost = kbTitleBoost(h.idx, query);
        // chunk id 格式 'book__chap__i', i==0 表示章节首段
        if (c.id.endsWith('__0')) boost *= 1.3;
        tfidfMap.set(c.id, { score: h.score * boost, chapterId: c.chapterId });
    }
    // 2) Dense (如果启用)
    let denseMap = null;
    if (useDense) {
        await loadKbDenseIndex();
        const queryEmb = await kbEmbedQuery(query);
        denseMap = kbDenseScore(queryEmb, 100);
    }
    // 3) Merge：每个 chunk id 一个综合分
    const merged = new Map();
    for (const [id, s] of tfidfMap) merged.set(id, { tfidf: s.score, dense: 0, chapterId: s.chapterId });
    if (denseMap) {
        for (const [id, score] of denseMap) {
            const existing = merged.get(id);
            const c = _kbIndex.chunks.find(c => c.id === id);
            const chapterId = existing ? existing.chapterId : (c ? c.chapterId : null);
            if (!existing) merged.set(id, { tfidf: 0, dense: score, chapterId });
            else existing.dense = score;
        }
    }
    // 综合分：dense*0.7 + tfidf*0.3
    const final = [];
    for (const [id, s] of merged) {
        const score = s.dense * 0.7 + s.tfidf * 0.3;
        if (score > 0) final.push({ id, score, chapterId: s.chapterId });
    }
    final.sort((a, b) => b.score - a.score);
    return kbChapterDiverse(final, topK);
}

async function kbRunSearch() {
    const input = document.getElementById('kb-input');
    const results = document.getElementById('kb-results');
    const query = (input.value || '').trim();
    if (!query) {
        results.innerHTML = '<div class="kb-empty">先在上面输入问题吧。</div>';
        return;
    }
    saveKbQuery(query);
    const aiToggle = document.getElementById('kb-ai-toggle');
    const useDense = aiToggle && aiToggle.checked;
    results.innerHTML = '<div class="kb-loading">加载索引中（首次约 1.7 MB）…</div>';
    try {
        let hits;
        if (useDense) {
            if (!_kbPipe) results.innerHTML = '<div class="kb-loading">加载 AI 模型中（首次约 24 MB）…</div>';
            // 混合 + 章节去重
            hits = await kbHybridSearch(query, true, 5);
        } else {
            await loadKnowledgeIndex();
            const expanded = kbExpandSynonyms(query);
            // 用扩展 query 搜 + 标题加权 + 章节去重
            const tfidfHits = kbSearch(expanded, 100);
            const idToChunk = new Map(_kbIndex.chunks.map(c => [c.id, c]));
            const scored = tfidfHits.map(h => {
                const c = _kbIndex.chunks[h.idx];
                let boost = kbTitleBoost(h.idx, query);
                // chunk 0 (章节首段) ×1.3 额外加权
                if (c.id.endsWith('__0')) boost *= 1.3;
                return { id: c.id, score: h.score * boost, chapterId: c.chapterId };
            }).sort((a, b) => b.score - a.score);
            hits = kbChapterDiverse(scored, 5);
        }
        if (!hits.length) {
            results.innerHTML = '<div class="kb-empty">没找到相关段落。试试更短或不同的关键词，或启用 AI 语义搜索（需下载 24 MB 模型）。</div>';
            return;
        }
        const idx = _kbIndex;
        // 用 id 反查 TF-IDF 拿 text/title/bookSlug
        const idToChunk = new Map(idx.chunks.map((c, i) => [c.id, { chunk: c, idx: i }]));
        const topScore = hits[0].score || 1;
        results.innerHTML = hits.map((h, i) => {
            const meta = idToChunk.get(h.id);
            if (!meta) return '';
            const c = meta.chunk;
            const bm = BOOK_META[c.bookSlug] || BOOKS_META[c.bookSlug] || {};
            const color = bm.color || '#b08968';
            const rel = (h.score / topScore * 100).toFixed(0);
            const tag = useDense
                ? (i === 0 ? '★ AI 最相关' : '相关度 ' + rel + '%')
                : (i === 0 ? '★ 最相关' : '相关度 ' + rel + '%');
            return (
                '<a class="kb-result" href="#' + c.chapterId + '" data-chapter="' + c.chapterId + '" data-query="' + escapeAttr(query) + '">' +
                '<div class="kb-result-meta">' +
                '<span class="kb-result-book" style="color:' + color + '">' + c.bookTitle + '</span>' +
                '<span class="kb-result-chapter">' + c.chapterTitle + '</span>' +
                '<span class="kb-result-score">' + tag + '</span>' +
                '</div>' +
                '<div class="kb-result-text">' + kbHighlight(kbSnippet(c.text, query), query) + '</div>' +
                '</a>'
            );
        }).join('');
    } catch (e) {
        results.innerHTML = '<div class="kb-empty">搜索失败：' + e.message + '</div>';
    }
}

function kbOpen() {
    const modal = document.getElementById('kb-modal');
    if (!modal) return;
    modal.classList.add('visible');
    // 预加载索引（不阻塞打开）
    if (!_kbIndex && !_kbIndexLoading) loadKnowledgeIndex();
    renderKbHistory();
    setTimeout(() => document.getElementById('kb-input')?.focus(), 50);
}
function kbClose() {
    const modal = document.getElementById('kb-modal');
    if (modal) modal.classList.remove('visible');
}

// Q&A 搜索历史 (localStorage 最近 8 条)
function getKbHistory() {
    try { return JSON.parse(localStorage.getItem('kg_kb_history') || '[]'); } catch (e) { return []; }
}
function saveKbQuery(query) {
    if (!query || query.length < 2) return;
    let h = getKbHistory().filter(q => q !== query);
    h.unshift(query);
    if (h.length > 8) h = h.slice(0, 8);
    try { localStorage.setItem('kg_kb_history', JSON.stringify(h)); } catch (e) {}
}
function renderKbHistory() {
    const results = document.getElementById('kb-results');
    if (!results) return;
    const h = getKbHistory();
    if (!h.length) {
        results.innerHTML = '<div class="kb-empty kb-hint">键入问题后回车。默认走 TF-IDF + 同义词扩展 + 标题加权,勾选 AI 语义搜索可加载 BGE 中文模型做 dense embedding 混合检索。</div>';
        return;
    }
    const html = h.map((q, i) => '<div class="kb-history-row" data-query="' + escapeAttr(q) + '">' +
        '<span class="kb-history-q">' + q + '</span>' +
        '<span class="kb-history-x" data-remove="' + escapeAttr(q) + '">×</span>' +
        '</div>').join('');
    results.innerHTML = '<div class="kb-history-label">最近搜索</div>' + html;
}
// 委托: 点击历史行 → 回填 + 搜索; 点 × → 删除
document.addEventListener('click', (e) => {
    const x = e.target.closest('.kb-history-x');
    if (x) {
        e.preventDefault(); e.stopPropagation();
        const q = x.dataset.remove;
        let h = getKbHistory().filter(item => item !== q);
        try { localStorage.setItem('kg_kb_history', JSON.stringify(h)); } catch (e) {}
        renderKbHistory();
        return;
    }
    const row = e.target.closest('.kb-history-row');
    if (row) {
        e.preventDefault();
        document.getElementById('kb-input').value = row.dataset.query;
        kbRunSearch();
    }
});

// 事件绑定
const kbLauncher = document.getElementById('kb-launcher');
if (kbLauncher) kbLauncher.addEventListener('click', kbOpen);
const kbCloseBtn = document.querySelector('.kb-close');
if (kbCloseBtn) kbCloseBtn.addEventListener('click', kbClose);
const kbSearchBtn = document.getElementById('kb-search-btn');
if (kbSearchBtn) kbSearchBtn.addEventListener('click', kbRunSearch);
const kbInput = document.getElementById('kb-input');
if (kbInput) kbInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') { e.preventDefault(); kbRunSearch(); }
    if (e.key === 'Escape') { e.preventDefault(); kbClose(); }
});
// 点击 backdrop 关闭
const kbModalEl = document.getElementById('kb-modal');
if (kbModalEl) kbModalEl.addEventListener('click', (e) => {
    if (e.target === kbModalEl) kbClose();
});

// 搜索建议 (input 时下拉 top-3 匹配章节标题)
let kbSugTimer = null;
let kbSugItems = [];
function kbRenderSuggestions() {
    const sugEl = document.getElementById('kb-suggestions');
    if (!sugEl) return;
    if (kbSugItems.length === 0) { sugEl.style.display = 'none'; return; }
    sugEl.innerHTML = kbSugItems.map((it, i) =>
        '<div class="kb-sug-row" data-i="' + i + '">' +
        '<span class="kb-sug-book">' + escapeAttr(it.bookTitle) + '</span>' +
        '<span class="kb-sug-title">' + escapeAttr(it.chapterTitle) + '</span>' +
        '</div>'
    ).join('');
    sugEl.style.display = '';
    sugEl.querySelectorAll('.kb-sug-row').forEach(row => {
        row.addEventListener('click', () => {
            const it = kbSugItems[parseInt(row.dataset.i)];
            document.getElementById('kb-input').value = it.chapterTitle;
            sugEl.style.display = 'none';
            kbRunSearch();
        });
    });
}
async function kbSuggest(query) {
    if (!query || query.length < 2) { kbSugItems = []; kbRenderSuggestions(); return; }
    // 优先用轻量 title 索引 (不查 chunk)
    const titles = (typeof CHAPTER_TITLES_MAP !== 'undefined') ? CHAPTER_TITLES_MAP : {};
    const bookMap = (typeof CHAPTER_BOOK_MAP !== 'undefined') ? CHAPTER_BOOK_MAP : {};
    const q = query.toLowerCase();
    const hits = [];
    for (const [cid, title] of Object.entries(titles)) {
        const t = title.toLowerCase();
        let score = 0;
        if (t === q) score = 100;
        else if (t.includes(q)) score = 50 - (t.length - q.length);
        else {
            // 单字符匹配
            let i = 0, j = 0, contig = 0, maxContig = 0;
            while (i < q.length && j < t.length) {
                if (q[i] === t[j]) { i++; contig++; if (contig > maxContig) maxContig = contig; }
                else contig = 0;
                j++;
            }
            if (i === q.length) score = 10 + maxContig;
        }
        if (score > 0) hits.push({ cid, title, score });
    }
    hits.sort((a, b) => b.score - a.score);
    kbSugItems = hits.slice(0, 5).map(h => {
        const bookSlug = bookMap[h.cid] || '';
        const bookTitle = (BOOKS_META[bookSlug] && BOOKS_META[bookSlug].title) || bookSlug;
        return { chapterId: h.cid, chapterTitle: h.title, bookTitle };
    });
    kbRenderSuggestions();
}
if (kbInput) kbInput.addEventListener('input', () => {
    clearTimeout(kbSugTimer);
    const q = kbInput.value.trim();
    if (q.length < 2) { kbSugItems = []; kbRenderSuggestions(); return; }
    kbSugTimer = setTimeout(() => kbSuggest(q), 150);
});
// 输入框聚焦时如果已有 query, 重新显示建议
if (kbInput) kbInput.addEventListener('focus', () => {
    if (kbInput.value.trim().length >= 2) kbSuggest(kbInput.value.trim());
});

// Q&A 结果点击: 关 modal → 跳章节 → 找 query term → scroll + 黄色闪 2 秒
function escapeAttr(s) {
    return String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}
function kbJumpToMatch(chapterId, query) {
    kbClose();
    const article = document.getElementById(chapterId);
    if (!article) return;
    // Lazy load body first (Q&A jump 进入未加载章节)
    const body = article.querySelector('.chapter-body[data-load-book]');
    if (body) {
        const bookSlug = body.dataset.loadBook;
        lazyLoadChapter(bookSlug, chapterId).then(() => doScroll());
        return;
    }
    doScroll();
    function doScroll() {
        // 找 query term 首次出现位置
        const cjk = (query || '').match(/[\u4e00-\u9fff]+/g) || [];
        const ascii = (query || '').match(/[A-Za-z0-9]+/g) || [];
        const terms = [...cjk, ...ascii].filter(t => t.length >= 2);
        if (!terms.length) return;
        // 在 article 文本节点里找首个匹配 term
        const walker = document.createTreeWalker(article, NodeFilter.SHOW_TEXT, null);
        let firstNode = null, firstIdx = -1;
        while (walker.nextNode()) {
            const node = walker.currentNode;
            const lower = node.nodeValue.toLowerCase();
            for (const t of terms.sort((a, b) => b.length - a.length)) {
                const idx = lower.indexOf(t.toLowerCase());
                if (idx >= 0 && (firstIdx < 0 || idx < firstIdx)) {
                    firstNode = node;
                    firstIdx = idx;
                    break;
                }
            }
            if (firstNode) break;
        }
        if (!firstNode) return;
        // 包一层 <mark class="kb-jump-flash">  闪 2s 后移除
        const range = document.createRange();
        range.setStart(firstNode, firstIdx);
        // 取到 term 末尾
        const matchedTerm = terms.sort((a, b) => b.length - a.length).find(t => firstNode.nodeValue.substring(firstIdx, firstIdx + t.length).toLowerCase() === t.toLowerCase());
        range.setEnd(firstNode, firstIdx + (matchedTerm ? matchedTerm.length : 2));
        const mark = document.createElement('mark');
        mark.className = 'kb-jump-flash';
        try { range.surroundContents(mark); } catch (e) { /* 跨节点 fallback: 滚动 + 用 selection */ }
        // 滚动到 mark
        mark.scrollIntoView({ behavior: 'smooth', block: 'center' });
        setTimeout(() => {
            // 拆开 mark 恢复原文本
            const parent = mark.parentNode;
            while (mark.firstChild) parent.insertBefore(mark.firstChild, mark);
            parent.removeChild(mark);
        }, 2500);
    }
    if (window.location.hash === '#' + chapterId) {
        doScroll();
    } else {
        // 切到目标章节
        window.location.hash = chapterId;
        setTimeout(doScroll, 100);
    }
}

// 委托点击: 任何 .kb-result 触发 jump
document.addEventListener('click', (e) => {
    const a = e.target.closest('.kb-result');
    if (!a) return;
    const chapterId = a.dataset.chapter;
    const query = a.dataset.query;
    if (chapterId && query) {
        e.preventDefault();
        kbJumpToMatch(chapterId, query);
    }
});

// 全局快捷键 Ctrl+/
document.addEventListener('keydown', (e) => {
    if (e.ctrlKey && e.key === '/') {
        e.preventDefault();
        const modal = document.getElementById('kb-modal');
        if (modal && modal.classList.contains('visible')) kbClose();
        else kbOpen();
    }
});

// ============================================================
// 读完 CTA: 滚到章节末尾 → 底部弹出 "继续读下一章" sticky bar
// - 找当前 active chapter, 距离底部 < 300px → 显示
// - 离开 (scroll up) → 隐藏
// ============================================================
(function() {
    let cta = document.createElement('div');
    cta.className = 'next-chapter-cta';
    cta.innerHTML = '<span class="next-cta-label">继续读下一章</span><span class="next-cta-title"></span><span class="next-cta-arrow">→</span>';
    cta.style.display = 'none';
    document.body.appendChild(cta);
    let currentActive = null;
    function update() {
        const chapters = document.querySelectorAll('article.chapter');
        const center = window.scrollY + window.innerHeight * 0.7;
        let active = null;
        for (const art of chapters) {
            const top = art.offsetTop;
            const bot = top + art.offsetHeight;
            if (center >= top && center < bot) { active = art; break; }
        }
        if (!active) { cta.style.display = 'none'; return; }
        // 距离章节底部 < 300px 才显示
        const distToEnd = (active.offsetTop + active.offsetHeight) - (window.scrollY + window.innerHeight);
        if (distToEnd > 300) { cta.style.display = 'none'; return; }
        // 找下一章
        const nextLink = active.querySelector('.chap-nav-next');
        if (!nextLink) { cta.style.display = 'none'; return; }
        const title = nextLink.querySelector('.chap-nav-title')?.textContent || '下一章';
        if (active === currentActive) return;  // 同一章不更新
        currentActive = active;
        cta.querySelector('.next-cta-title').textContent = title;
        cta.style.display = 'flex';
        cta.onclick = (e) => {
            e.preventDefault();
            nextLink.click();
            window.scrollTo({ top: 0, behavior: 'smooth' });
        };
    }
    window.addEventListener('scroll', update, { passive: true });
    setTimeout(update, 200);
})();

// overview-mode 切换：只看首页 TOC
function showOverview() {
    document.body.classList.add('overview-mode');
    window.scrollTo({ top: 0, behavior: 'instant' });
    if (window.location.hash) history.replaceState(null, '', window.location.pathname);
}

function hideOverview() {
    document.body.classList.remove('overview-mode');
}

// 初始模式：URL 有 hash 跳到章节，否则显示 overview
function initOverviewMode() {
    const hash = window.location.hash;
    if (!hash || hash === '#') {
        showOverview();
    } else {
        hideOverview();
    }
}

// 监听 hash 变化
window.addEventListener('hashchange', () => {
    if (window.location.hash) {
        hideOverview();
        // 确保目标章节内容已加载 (深链 / 书签直跳)
        const id = window.location.hash.replace('#', '');
        const article = document.getElementById(id);
        if (article) {
            const body = article.querySelector('.chapter-body[data-load-book]');
            if (body) lazyLoadChapter(body.dataset.loadBook, id);
        }
    } else {
        showOverview();
    }
    updateOgMeta();
});

// 动态 OG meta: 章节切换时同步 og:title / og:description / og:image / og:url
// 这样用户复制分享链接或某些爬虫现场抓取时拿到对应书的 OG 卡
function updateOgMeta() {
    const hash = window.location.hash.replace('#', '');
    if (!hash) {
        // overview 模式: 用全站 OG
        const ogTitle = `个人知识库 · ${CHAPTERS.length / 10} 个系列 · 100 章`;
        setMeta('og-title', ogTitle);
        setMeta('og-desc', 'Multi-Agent / LLM Prompt / CrewAI / RAG / Harness / Cost / Indie / Context / Skills / Claude Code');
        setMeta('og-image', `${SITE_URL}assets/og.png`);
        setMeta('tw-title', ogTitle);
        setMeta('tw-desc', 'Multi-Agent / LLM Prompt / CrewAI / RAG / Harness / Cost / Indie / Context / Skills / Claude Code');
        setMeta('tw-image', `${SITE_URL}assets/og.png`);
        setMeta('og-url', SITE_URL);
        return;
    }
    const book = CHAPTER_BOOK_MAP[hash];
    const chapTitle = CHAPTER_TITLES_MAP[hash];
    if (!book || !chapTitle) return;
    const bookMeta = BOOK_META[book] || { title: book };
    const fullTitle = `${chapTitle} · ${bookMeta.title} · 个人知识库`;
    const pageUrl = `${SITE_URL}books_pages/${book}/${hash.split('__')[1]}.html`;
    setMeta('og-title', fullTitle);
    setMeta('og-desc', chapTitle);
setMeta('og-image', `${SITE_URL}assets/og-${book}.png`);
        setMeta('tw-title', fullTitle);
        setMeta('tw-desc', chapTitle);
        setMeta('tw-image', `${SITE_URL}assets/og-${book}.png`);
    setMeta('og-url', pageUrl);
}
function setMeta(id, val) {
    const el = document.getElementById(id);
    if (el) el.setAttribute('content', val);
}
// 初始化 BOOK_META (title 映射) — 从 sidebar 里的 data-book 反推
const BOOK_META = (() => {
    const out = {};
    document.querySelectorAll('[data-book]').forEach(el => {
        const slug = el.dataset.book;
        if (out[slug]) return;
        // 优先取 overview-card 的 .overview-card-title, fallback 到 book-title-text
        const card = el.closest('.overview-card');
        const titleEl = card ? card.querySelector('.overview-card-title') : el.querySelector('.book-title-text');
        if (titleEl) out[slug] = { title: titleEl.textContent.trim() };
    });
    return out;
})();
const CHAPTER_BOOK_MAP = __CHAPTER_BOOK_MAP__;
const CHAPTER_TITLES_MAP = __CHAPTER_TITLES_MAP__;
const SITE_URL = '__SITE_URL__';
// 初始化一次 (处理用户直接带 hash 进入的情况)
updateOgMeta();

// sidebar 的 h1 点 = 回首页
const sidebarH1 = document.querySelector('.sidebar h1');
if (sidebarH1) {
    sidebarH1.style.cursor = 'pointer';
    sidebarH1.title = '回到首页';
    sidebarH1.addEventListener('click', showOverview);
}

// ============================================================
// 首次访问引导
// - localStorage kg_welcomed 标记是否已引导
// - 选 3+ 标签 → 标签对应 series 优先级 → 取首章 → 推 5 章
// ============================================================
const WELCOME_TAG_TO_BOOKS = {
    'rag': ['rag'],
    'agent': ['multi-agent', 'crewai', 'a2a-multi-agent'],
    'claude-code': ['claude-code'],
    'codex': ['codex-cases'],
    'vibe-coding': ['vibe-coding'],
    'harness': ['harness-engineering', 'agent-skills'],
    'memory': ['memory-architecture', 'context-engineering'],
    'llm-prompt': ['llm-prompt', 'context-engineering'],
    'cn-codex': ['cn-codex'],
    'indie': ['indie-ai-product'],
    'content': ['ai-content-economy'],
    'embodied': ['embodied-agent'],
};

function showWelcomeModal() {
    if (localStorage.getItem('kg_welcomed')) return;
    const modal = document.getElementById('welcome-modal');
    if (!modal) return;
    modal.style.display = 'flex';
    const selected = new Set();
    const countEl = document.getElementById('welcome-count');
    const goBtn = document.getElementById('welcome-go');
    document.querySelectorAll('.welcome-tag').forEach(btn => {
        btn.addEventListener('click', () => {
            const tag = btn.dataset.tag;
            if (selected.has(tag)) {
                selected.delete(tag);
                btn.classList.remove('selected');
            } else {
                selected.add(tag);
                btn.classList.add('selected');
            }
            countEl.textContent = selected.size;
            goBtn.disabled = selected.size < 3;
        });
    });
    goBtn.addEventListener('click', () => {
        modal.style.display = 'none';
        showWelcomeResults([...selected]);
    });
    document.getElementById('welcome-skip').addEventListener('click', () => {
        modal.style.display = 'none';
        localStorage.setItem('kg_welcomed', '1');
    });
    document.getElementById('welcome-close').addEventListener('click', () => {
        document.getElementById('welcome-results').style.display = 'none';
        localStorage.setItem('kg_welcomed', '1');
    });
}

function showWelcomeResults(tags) {
    const container = document.getElementById('welcome-results');
    const list = document.getElementById('welcome-results-list');
    // 收集 tag → 对应 books → 排序去重 → 取首章
    const seenBooks = new Set();
    const candidates = [];
    for (const tag of tags) {
        for (const slug of (WELCOME_TAG_TO_BOOKS[tag] || [])) {
            if (seenBooks.has(slug)) continue;
            seenBooks.add(slug);
            const meta = BOOKS_META[slug];
            if (meta && meta.firstChapter) {
                candidates.push({ slug, ...meta });
            }
        }
    }
    candidates.sort((a, b) => (a.priority || 999) - (b.priority || 999));
    const picks = candidates.slice(0, 5);
    list.innerHTML = picks.map((c, i) => (
        '<a class="welcome-result-item" href="#' + c.firstChapter.anchor + '">' +
        '<span class="welcome-result-step">' + (i + 1) + '</span>' +
        '<div class="welcome-result-body">' +
        '<div class="welcome-result-title">' + c.firstChapter.title + '</div>' +
        '<div class="welcome-result-book">' + c.title + '</div>' +
        '</div></a>'
    )).join('');
    container.style.display = 'flex';
    // 点击结果也关闭 modal
    list.querySelectorAll('.welcome-result-item').forEach(a => {
        a.addEventListener('click', () => {
            container.style.display = 'none';
            localStorage.setItem('kg_welcomed', '1');
        });
    });
}

renderOverview();
// 首次访问才弹引导 (老用户直接跳过)
showWelcomeModal();
initOverviewMode();

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
                            showCompletionCelebration(chapterId);
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
        // 实时刷新周目标进度条
        if (typeof refreshWeeklyGoal === 'function') {
            refreshWeeklyGoal(progress.dailyTime);
        }
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
    renderOverview();
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
    // overview 模式下不弹 — 继续阅读卡已经显示在 overview 里
    if (document.body.classList.contains('overview-mode')) return;
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

// Anki 闪卡导出（CSV / tab-separated）
document.getElementById('export-anki').addEventListener('click', () => {
    if (!Array.isArray(notes) || notes.length === 0) {
        showAnkiHelp('还没有高亮或笔记，先在正文里选中文字添加吧。');
        return;
    }
    const csv = buildAnkiCsv(notes);
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `knowledge-garden-anki-${new Date().toISOString().slice(0, 10)}.txt`;
    a.click();
    URL.revokeObjectURL(url);
    showAnkiHelp(`导出了 ${notes.length} 张卡片。Anki 里 File → Import 选这个 .txt 文件即可。`, true);
});

// buildAnkiCsv — Front: book/chapter, Back: highlight + 用户笔记 + URL，Tags: kg + 章节 slug
function buildAnkiCsv(notesArr) {
    const lines = ['Front\tBack\tTags'];
    const seen = new Set();
    for (const note of notesArr) {
        if (!note.chapterId) continue;
        const meta = getChapterMeta(note.chapterId);
        const bookSlug = note.bookSlug || meta.book || '';
        const bookTitle = (BOOK_META[bookSlug] && BOOK_META[bookSlug].title) || bookSlug;
        const chapterTitle = meta.title || note.chapterId;
        // 高亮 text 优先取 note.text（保存的原文），note 类型用 quote
        const content = (note.text || note.quote || '').trim();
        if (!content) continue;
        // 去重：同章节同内容
        const dedupKey = `${note.chapterId}::${content}`;
        if (seen.has(dedupKey)) continue;
        seen.add(dedupKey);
        // Front: book / chapter - 让用户主动回忆
        const front = `${bookTitle}\n${chapterTitle}`;
        // Back: 高亮内容 + 用户笔记 + URL
        const url = `${SITE_URL}#${note.chapterId}`;
        const userText = (note.type === 'note' && note.text && note.quote && note.text.trim() !== note.quote.trim())
            ? note.text : '';
        const back = userText
            ? `${content}\n\n—— 我的笔记 ——\n${userText}\n\n来源：${url}`
            : `${content}\n\n来源：${url}`;
        const tags = ['kg', bookSlug, note.chapterId.split('__')[1] || ''].filter(Boolean).join(' ');
        lines.push([front, back, tags].map(csvEscape).join('\t'));
    }
    return lines.join('\\n');
}

// 转义 Anki CSV 字段：去掉换行（替换为空格）、tab 转空格
function csvEscape(s) {
    return String(s)
        .replace(/\\r?\\n/g, ' ')   // 多行折叠成单行（Anki 闪卡一般单行更易复习）
        .replace(/\\t/g, ' ')
        .replace(/  +/g, ' ')    // 合并多余空格
        .trim();
}

// Anki 导入帮助弹窗
function showAnkiHelp(msg, success = false) {
    let modal = document.getElementById('anki-help-modal');
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'anki-help-modal';
        modal.className = 'modal-overlay';
        modal.innerHTML = `
            <div class="modal-content anki-help">
                <button class="modal-close">×</button>
                <h3 id="anki-help-title">Anki 导入指南</h3>
                <p id="anki-help-msg" class="anki-msg"></p>
                <ol class="anki-steps">
                    <li>打开 <strong>Anki</strong>（没有的话去 <a href="https://apps.ankiweb.net/" target="_blank">apps.ankiweb.net</a> 免费下载）</li>
                    <li>顶部菜单 <strong>File → Import</strong></li>
                    <li>选刚才下载的 <code>knowledge-garden-anki-YYYY-MM-DD.txt</code></li>
                    <li>Import Options 里：
                        <ul>
                            <li>Notetype: <strong>Basic</strong>（或 Basic+Reverse）</li>
                            <li>Field separator: <strong>Tab</strong>（默认）</li>
                            <li>"Allow HTML in fields": ✓ 勾上</li>
                        </ul>
                    </li>
                    <li>选个 Deck（建议新建 "Knowledge Garden"）</li>
                    <li>点 <strong>Import</strong> 即可</li>
                </ol>
                <p class="anki-tip">
                    卡片设计：<strong>Front</strong> 显示「书名 / 章节」，想不起来时点翻面看 <strong>Back</strong>（高亮内容 + 你的笔记 + 来源链接）。<br>
                    这是一种"主动回忆"练习，比光读一遍记得牢 5 倍。
                </p>
                <button class="btn-primary" id="anki-help-ok">知道了</button>
            </div>`;
        document.body.appendChild(modal);
        modal.querySelector('.modal-close').onclick = () => modal.classList.remove('visible');
        modal.querySelector('#anki-help-ok').onclick = () => modal.classList.remove('visible');
        modal.onclick = (e) => { if (e.target === modal) modal.classList.remove('visible'); };
    }
    document.getElementById('anki-help-msg').textContent = msg;
    document.getElementById('anki-help-msg').className = `anki-msg ${success ? 'anki-msg-success' : 'anki-msg-warn'}`;
    modal.classList.add('visible');
}

// ---- 笔记图谱：把高亮 + 笔记画成 force-directed 图 ----
function openNotesGraph() {
    if (!Array.isArray(notes) || notes.length === 0) {
        showAnkiHelp('还没有高亮或笔记，先在正文里选中文字添加吧。');
        return;
    }
    let modal = document.getElementById('notes-graph-modal');
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'notes-graph-modal';
        modal.className = 'modal-overlay notes-graph-overlay';
        modal.innerHTML = `
            <div class="notes-graph-container">
                <div class="notes-graph-header">
                    <h3>笔记图谱</h3>
                    <div class="notes-graph-stats" id="notes-graph-stats"></div>
                    <button class="modal-close graph-close">×</button>
                </div>
                <div class="notes-graph-help" id="notes-graph-help">
                    每个圆是一个章节（大小 = 笔记数）。线越粗 = 两个章节间的笔记越多。颜色 = 系列主题色。
                    <span class="notes-graph-tip">拖动节点 · 滚轮缩放 · 双击进入章节</span>
                </div>
                <canvas id="notes-graph-canvas"></canvas>
                <div class="notes-graph-tooltip" id="notes-graph-tooltip"></div>
            </div>`;
        document.body.appendChild(modal);
        modal.querySelector('.graph-close').onclick = () => modal.classList.remove('visible');
    }
    modal.classList.add('visible');
    renderNotesGraph(modal);
}

// 构建 + 渲染笔记图谱
function renderNotesGraph(modal) {
    const canvas = modal.querySelector('#notes-graph-canvas');
    const ctx = canvas.getContext('2d');
    const tooltip = modal.querySelector('#notes-graph-tooltip');
    const stats = modal.querySelector('#notes-graph-stats');

    // 自适应高 DPR
    const dpr = window.devicePixelRatio || 1;
    const rect = modal.getBoundingClientRect();
    const W = rect.width - 0;
    const H = rect.height - 100; // 减去 header
    canvas.style.width = W + 'px';
    canvas.style.height = H + 'px';
    canvas.width = W * dpr;
    canvas.height = H * dpr;
    ctx.scale(dpr, dpr);

    // 按章节聚合笔记
    const chapterNodes = new Map(); // chapterId -> { id, count, book, title, color, x, y, vx, vy }
    const chapterLinks = new Map(); // "a|b" -> { a, b, weight }

    notes.forEach(n => {
        if (!n.chapterId) return;
        if (!chapterNodes.has(n.chapterId)) {
            const article = document.getElementById(n.chapterId);
            const bookSlug = (article && article.dataset.book) || n.bookSlug || '';
            const title = (article && article.querySelector('.chapter-title')?.textContent.trim()) || n.chapterId;
            const book = BOOK_META[bookSlug] || {};
            chapterNodes.set(n.chapterId, {
                id: n.chapterId,
                book: bookSlug,
                title,
                color: book.color || '#b08968',
                count: 0,
                notes: [],
                x: W / 2 + (Math.random() - 0.5) * W * 0.6,
                y: H / 2 + (Math.random() - 0.5) * H * 0.6,
                vx: 0, vy: 0,
            });
        }
        chapterNodes.get(n.chapterId).count++;
        chapterNodes.get(n.chapterId).notes.push(n);
    });

    // 按书聚合，同书内的章节聚成一簇
    const booksArr = {};
    chapterNodes.forEach(n => {
        if (!booksArr[n.book]) booksArr[n.book] = [];
        booksArr[n.book].push(n);
    });
    const bookCenters = {};
    const bookKeys = Object.keys(booksArr);
    bookKeys.forEach((book, i) => {
        const angle = (i / bookKeys.length) * Math.PI * 2;
        bookCenters[book] = {
            x: W / 2 + Math.cos(angle) * Math.min(W, H) * 0.32,
            y: H / 2 + Math.sin(angle) * Math.min(W, H) * 0.32,
        };
    });
    chapterNodes.forEach(n => {
        const bc = bookCenters[n.book];
        n.x = bc.x + (Math.random() - 0.5) * 100;
        n.y = bc.y + (Math.random() - 0.5) * 100;
    });

    // 章节之间基于"共享笔记时段"或"同书"连边
    // 简化：同书的章节连 + 跨书共享关键字连
    const nodesArr = Array.from(chapterNodes.values());
    const nodesByBook = booksArr;
    // 同书内的章节串成链
    Object.values(nodesByBook).forEach(arr => {
        arr.sort((a, b) => a.title.localeCompare(b.title));
        for (let i = 0; i < arr.length - 1; i++) {
            const key = arr[i].id < arr[i + 1].id ? `${arr[i].id}|${arr[i + 1].id}` : `${arr[i + 1].id}|${arr[i].id}`;
            chapterLinks.set(key, { a: arr[i].id, b: arr[i + 1].id, weight: 1, intraBook: true });
        }
    });
    // 跨书：基于笔记文本的关键词重叠 (top 2 关键词)
    const chapterKeywords = new Map();
    nodesArr.forEach(n => {
        const text = n.notes.map(x => (x.text || x.quote || '')).join(' ').toLowerCase();
        // 提取中文 2-gram + 英文词
        const grams = new Set();
        for (let i = 0; i < text.length - 1; i++) {
            const c = text[i], n2 = text[i + 1];
            if (/[\u4e00-\u9fa5]/.test(c) && /[\u4e00-\u9fa5]/.test(n2)) {
                grams.add(c + n2);
            } else if (/[a-z]/i.test(c)) {
                let j = i;
                while (j < text.length && /[a-z0-9]/i.test(text[j])) j++;
                grams.add(text.slice(i, j).toLowerCase());
                i = j - 1;
            }
        }
        chapterKeywords.set(n.id, grams);
    });
    for (let i = 0; i < nodesArr.length; i++) {
        for (let j = i + 1; j < nodesArr.length; j++) {
            if (nodesArr[i].book === nodesArr[j].book) continue;
            const a = chapterKeywords.get(nodesArr[i].id);
            const b = chapterKeywords.get(nodesArr[j].id);
            let overlap = 0;
            a.forEach(g => { if (b.has(g)) overlap++; });
            if (overlap >= 2) {
                const key = nodesArr[i].id < nodesArr[j].id ? `${nodesArr[i].id}|${nodesArr[j].id}` : `${nodesArr[j].id}|${nodesArr[i].id}`;
                chapterLinks.set(key, { a: nodesArr[i].id, b: nodesArr[j].id, weight: Math.min(overlap, 5), intraBook: false });
            }
        }
    }

    stats.textContent = `${nodesArr.length} 个章节 · ${notes.length} 条笔记 · ${chapterLinks.size} 条关联`;

    // 力导向模拟 (Fruchterman-Reingold 简化版)
    const area = W * H;
    const k = Math.sqrt(area / nodesArr.length) * 0.8; // 理想距离
    let temperature = W / 10;
    const coolingRate = 0.97;
    let iter = 0;
    const maxIter = 400;

    function step() {
        // 排斥力
        nodesArr.forEach(v => { v.vx = 0; v.vy = 0; });
        for (let i = 0; i < nodesArr.length; i++) {
            for (let j = i + 1; j < nodesArr.length; j++) {
                const a = nodesArr[i], b = nodesArr[j];
                let dx = a.x - b.x, dy = a.y - b.y;
                let dist = Math.sqrt(dx * dx + dy * dy) || 1;
                const force = (k * k) / dist;
                const fx = (dx / dist) * force;
                const fy = (dy / dist) * force;
                a.vx += fx; a.vy += fy;
                b.vx -= fx; b.vy -= fy;
            }
        }
        // 吸引 (link)
        chapterLinks.forEach(link => {
            const a = chapterNodes.get(link.a), b = chapterNodes.get(link.b);
            if (!a || !b) return;
            let dx = a.x - b.x, dy = a.y - b.y;
            let dist = Math.sqrt(dx * dx + dy * dy) || 1;
            const force = (dist * dist) / k * 0.05 * link.weight;
            const fx = (dx / dist) * force;
            const fy = (dy / dist) * force;
            a.vx -= fx; a.vy -= fy;
            b.vx += fx; b.vy += fy;
        });
        // 同书中心吸引
        nodesArr.forEach(n => {
            const bc = bookCenters[n.book];
            if (!bc) return;
            const dx = bc.x - n.x, dy = bc.y - n.y;
            n.vx += dx * 0.003;
            n.vy += dy * 0.003;
        });
        // 应用速度 + 温度
        nodesArr.forEach(v => {
            const disp = Math.sqrt(v.vx * v.vx + v.vy * v.vy) || 1;
            const limit = Math.min(disp, temperature);
            v.x += (v.vx / disp) * limit;
            v.y += (v.vy / disp) * limit;
            // 边界
            v.x = Math.max(40, Math.min(W - 40, v.x));
            v.y = Math.max(40, Math.min(H - 40, v.y));
        });
        temperature *= coolingRate;
        iter++;
    }

    function render() {
        ctx.clearRect(0, 0, W, H);
        // 背景网格
        ctx.strokeStyle = 'rgba(176, 137, 104, 0.06)';
        ctx.lineWidth = 1;
        for (let x = 0; x < W; x += 60) {
            ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, H); ctx.stroke();
        }
        for (let y = 0; y < H; y += 60) {
            ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke();
        }
        // 边
        chapterLinks.forEach(link => {
            const a = chapterNodes.get(link.a), b = chapterNodes.get(link.b);
            if (!a || !b) return;
            ctx.strokeStyle = link.intraBook ? a.color : 'rgba(176, 137, 104, 0.35)';
            ctx.globalAlpha = link.intraBook ? 0.45 : 0.25 + link.weight * 0.08;
            ctx.lineWidth = link.intraBook ? 1.5 : 1 + link.weight * 0.5;
            ctx.beginPath();
            ctx.moveTo(a.x, a.y);
            ctx.lineTo(b.x, b.y);
            ctx.stroke();
        });
        ctx.globalAlpha = 1;
        // 节点
        nodesArr.forEach(n => {
            const r = 14 + Math.sqrt(n.count) * 6;
            // 外环
            ctx.fillStyle = n.color + '20';
            ctx.beginPath();
            ctx.arc(n.x, n.y, r + 4, 0, Math.PI * 2);
            ctx.fill();
            // 主体
            ctx.fillStyle = n.color;
            ctx.beginPath();
            ctx.arc(n.x, n.y, r, 0, Math.PI * 2);
            ctx.fill();
            // 边框
            ctx.strokeStyle = '#fff';
            ctx.lineWidth = 2;
            ctx.stroke();
            // 文字 (book title + chapter #)
            const label = (BOOK_META[n.book] || {}).title || n.book;
            ctx.fillStyle = '#2a2a2e';
            ctx.font = '11px -apple-system, "PingFang SC", sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText(label.slice(0, 8), n.x, n.y - r - 6);
            // 笔记数
            ctx.fillStyle = '#fff';
            ctx.font = 'bold 11px -apple-system';
            ctx.fillText(String(n.count), n.x, n.y + 4);
        });
    }

    function loop() {
        if (iter < maxIter && temperature > 0.5) {
            step();
            render();
            requestAnimationFrame(loop);
        } else {
            render();
        }
    }
    loop();

    // 交互：拖动节点 + 双击跳转
    let dragging = null;
    let dragOff = { x: 0, y: 0 };
    let hoverNode = null;

    function findNode(x, y) {
        for (let i = nodesArr.length - 1; i >= 0; i--) {
            const n = nodesArr[i];
            const r = 14 + Math.sqrt(n.count) * 6;
            const dx = x - n.x, dy = y - n.y;
            if (dx * dx + dy * dy <= r * r) return n;
        }
        return null;
    }

    function getMousePos(e) {
        const r = canvas.getBoundingClientRect();
        return {
            x: (e.clientX - r.left) * (W / r.width),
            y: (e.clientY - r.top) * (H / r.height),
        };
    }

    canvas.onmousedown = (e) => {
        const { x, y } = getMousePos(e);
        const n = findNode(x, y);
        if (n) {
            dragging = n;
            dragOff.x = x - n.x;
            dragOff.y = y - n.y;
        }
    };
    canvas.onmousemove = (e) => {
        const { x, y } = getMousePos(e);
        if (dragging) {
            dragging.x = x - dragOff.x;
            dragging.y = y - dragOff.y;
            temperature = 0; // 停止模拟
            render();
        } else {
            const n = findNode(x, y);
            hoverNode = n;
            canvas.style.cursor = n ? 'pointer' : 'default';
            if (n) {
                const title = (BOOK_META[n.book] || {}).title || n.book;
                tooltip.innerHTML = '<div class="ngt-book">' + title + '</div><div class="ngt-title">' + n.title + '</div><div class="ngt-meta">' + n.count + ' 条笔记</div>';
                tooltip.style.left = e.clientX + 12 + 'px';
                tooltip.style.top = e.clientY + 12 + 'px';
                tooltip.classList.add('visible');
            } else {
                tooltip.classList.remove('visible');
            }
        }
    };
    canvas.onmouseup = () => { dragging = null; };
    canvas.onmouseleave = () => { dragging = null; tooltip.classList.remove('visible'); };
    canvas.ondblclick = (e) => {
        const { x, y } = getMousePos(e);
        const n = findNode(x, y);
        if (n) {
            window.location.hash = n.id;
            modal.classList.remove('visible');
        }
    };
    // 触屏支持
    canvas.ontouchstart = (e) => {
        const t = e.touches[0];
        const { x, y } = getMousePos(t);
        const n = findNode(x, y);
        if (n) { dragging = n; dragOff.x = x - n.x; dragOff.y = y - n.y; }
    };
    canvas.ontouchmove = (e) => {
        e.preventDefault();
        const t = e.touches[0];
        const { x, y } = getMousePos(t);
        if (dragging) { dragging.x = x - dragOff.x; dragging.y = y - dragOff.y; temperature = 0; render(); }
    };
    canvas.ontouchend = () => { dragging = null; };
    // 滚轮缩放（重置缩放比例用，不画大）
    let scale = 1;
    canvas.onwheel = (e) => {
        e.preventDefault();
        scale *= e.deltaY < 0 ? 1.1 : 0.9;
        scale = Math.max(0.5, Math.min(2, scale));
        ctx.setTransform(dpr * scale, 0, 0, dpr * scale, 0, 0);
        render();
    };
}

document.getElementById('show-notes-graph').addEventListener('click', openNotesGraph);

// ---- Spaced Repetition 复习（FSRS-lite） ----
// 卡片状态存储在 localStorage['reviewCards']，按 cardId 索引
// 每张卡片状态: { due (ms), interval (days), ease (1.3-2.5), reps, lapses, lastReview, isNew }
// 算法简化版 SM-2：Again 重置 1天 + ease-0.2; Hard interval*1.2; Good interval*ease; Easy interval*ease*1.3
function getReviewStore() {
    try { return JSON.parse(localStorage.getItem('reviewCards') || '{}'); }
    catch (e) { return {}; }
}
function saveReviewStore(store) { localStorage.setItem('reviewCards', JSON.stringify(store)); }

function cardKeyFromNote(note) {
    // 用 chapterId + text 的 hash 做唯一 ID
    const txt = (note.text || note.quote || '').trim().slice(0, 200);
    return (note.chapterId || '') + '::' + txt;
}

function buildCardFromNote(note) {
    const article = note.chapterId && document.getElementById(note.chapterId);
    const bookSlug = (article && article.dataset.book) || note.bookSlug || '';
    const bookTitle = (BOOK_META[bookSlug] && BOOK_META[bookSlug].title) || bookSlug;
    const chapterTitle = (article && article.querySelector('.chapter-title')?.textContent.trim()) || note.chapterId || '';
    const content = (note.text || note.quote || '').trim();
    return {
        front: `${bookTitle}\n${chapterTitle}`,
        back: content,
        source: { chapterId: note.chapterId, book: bookTitle, chap: chapterTitle },
        isNote: note.type === 'note',
    };
}

function refreshReviewQueue() {
    const container = document.getElementById('review-queue');
    if (!container) return;
    if (!Array.isArray(notes) || notes.length === 0) {
        container.style.display = 'none';
        return;
    }
    const store = getReviewStore();
    const now = Date.now();
    const todayKey = localDateKey(new Date());
    // 对每个 note 检查 card 状态，统计今天到期的数量
    const dueKeys = [];
    notes.forEach(n => {
        const key = cardKeyFromNote(n);
        if (!key) return;
        const card = store[key];
        if (!card) {
            // 新卡片 — 没复习过，立即入队
            dueKeys.push({ key, n, due: true, isNew: true });
        } else if (card.due && card.due <= now + 86400000) {
            // 已到期或在 24h 内到期
            dueKeys.push({ key, n, due: true, isNew: false });
        } else if (card.lastReview && localDateKey(new Date(card.lastReview)) === todayKey) {
            // 今天已经复习过，不重复
        }
    });
    const newCount = dueKeys.filter(d => d.isNew).length;
    const dueCount = dueKeys.filter(d => !d.isNew).length;
    if (dueKeys.length === 0) {
        // 找出最早的 due
        let earliest = null;
        Object.values(store).forEach(c => {
            if (!earliest || c.due < earliest) earliest = c.due;
        });
        const nextLabel = earliest ? new Date(earliest).toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' }) : '';
        container.innerHTML = `
            <div class="review-queue-icon">${svg_icon('brain', 14)}</div>
            <div class="review-queue-body">
                <div class="review-queue-title">今日复习完成</div>
                <div class="review-queue-desc">${nextLabel ? '下次复习 ' + nextLabel : '继续读章节自动加入复习'}</div>
            </div>
            <button class="review-queue-btn" disabled style="opacity:.5;cursor:default">已完成</button>`;
        container.style.display = '';
        return;
    }
    container.innerHTML = `
        <div class="review-queue-icon">${svg_icon('brain', 14)}</div>
        <div class="review-queue-body">
            <div class="review-queue-title">${dueKeys.length} 张卡片待复习</div>
            <div class="review-queue-desc">${newCount ? newCount + ' 张新 · ' : ''}${dueCount ? dueCount + ' 张到期' : ''}</div>
        </div>
        <button class="review-queue-btn" id="start-review-now">开始复习</button>`;
    container.style.display = '';
    const btn = document.getElementById('start-review-now');
    if (btn) btn.onclick = () => startReviewSession(dueKeys);
}

// 开始复习 session
let reviewSession = null;
function startReviewSession(dueList) {
    if (!dueList || dueList.length === 0) {
        refreshReviewQueue();
        return;
    }
    let modal = document.getElementById('review-modal');
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'review-modal';
        modal.className = 'modal-overlay review-overlay';
        modal.innerHTML = `
            <div class="review-container">
                <div class="review-header">
                    <div class="review-progress-bar"><div class="review-progress-fill" id="review-progress-fill"></div></div>
                    <div class="review-progress-text" id="review-progress-text">0 / 0</div>
                    <button class="modal-close graph-close" id="review-close-btn">×</button>
                </div>
                <div class="review-card-area" id="review-card-area"></div>
            </div>`;
        document.body.appendChild(modal);
        document.getElementById('review-close-btn').onclick = () => {
            modal.classList.remove('visible');
            refreshReviewQueue();
        };
        modal.onclick = (e) => { if (e.target === modal) { modal.classList.remove('visible'); refreshReviewQueue(); } };
    }
    reviewSession = {
        modal,
        queue: dueList.slice(),
        total: dueList.length,
        done: 0,
        again: 0,
        hard: 0,
        good: 0,
        easy: 0,
        results: [],
    };
    modal.classList.add('visible');
    showNextReviewCard();
}

function showNextReviewCard() {
    const s = reviewSession;
    if (!s || s.queue.length === 0) {
        showReviewSummary();
        return;
    }
    const item = s.queue.shift();
    const card = buildCardFromNote(item.n);
    const store = getReviewStore();
    const cardState = store[item.key] || { isNew: true };
    const area = s.modal.querySelector('#review-card-area');
    const fill = s.modal.querySelector('#review-progress-fill');
    const text = s.modal.querySelector('#review-progress-text');
    const reviewedCount = s.done;
    const totalCount = s.total;
    fill.style.width = (reviewedCount / totalCount * 100) + '%';
    text.textContent = reviewedCount + ' / ' + totalCount;

    area.innerHTML = `
        <div class="review-card">
            <div class="review-card-hint">${cardState.isNew ? '新卡片' : '复习'}</div>
            <div class="review-card-front">${escapeHtml(card.front)}</div>
            <div class="review-card-source">${card.isNote ? '📝 笔记' : '高亮'}</div>
            <button class="review-show-btn" id="review-show">显示答案</button>
        </div>`;
    area.querySelector('#review-show').onclick = () => showReviewBack(item, card, cardState);
}

function showReviewBack(item, card, cardState) {
    const s = reviewSession;
    const area = s.modal.querySelector('#review-card-area');
    const preview = (card.back || '').slice(0, 200);
    area.innerHTML = `
        <div class="review-card">
            <div class="review-card-hint">答案</div>
            <div class="review-card-back">${escapeHtml(preview)}${card.back.length > 200 ? '…' : ''}</div>
            <div class="review-card-source">来源：${card.source.book} · ${card.source.chap}${card.source.chapterId ? ' (<a href="#' + card.source.chapterId + '">打开章节</a>)' : ''}</div>
            <div class="review-card-divider"></div>
            <div class="review-card-hint" style="margin-top:0">回忆得怎么样？</div>
            <div class="review-card-actions">
                <button class="review-grade-btn again" data-grade="0">
                    <span class="gg-label">忘了</span>
                    <span class="gg-interval" id="gg-int-0">1 天</span>
                </button>
                <button class="review-grade-btn hard" data-grade="1">
                    <span class="gg-label">勉强</span>
                    <span class="gg-interval" id="gg-int-1">—</span>
                </button>
                <button class="review-grade-btn good" data-grade="2">
                    <span class="gg-label">记得</span>
                    <span class="gg-interval" id="gg-int-2">—</span>
                </button>
                <button class="review-grade-btn easy" data-grade="3">
                    <span class="gg-label">秒答</span>
                    <span class="gg-interval" id="gg-int-3">—</span>
                </button>
            </div>
        </div>`;
    // 预测各选项的 interval 并显示
    const next = predictNextIntervals(cardState);
    area.querySelector('#gg-int-0').textContent = formatInterval(next[0]);
    area.querySelector('#gg-int-1').textContent = formatInterval(next[1]);
    area.querySelector('#gg-int-2').textContent = formatInterval(next[2]);
    area.querySelector('#gg-int-3').textContent = formatInterval(next[3]);
    area.querySelectorAll('.review-grade-btn').forEach(btn => {
        btn.onclick = () => {
            const grade = parseInt(btn.dataset.grade, 10);
            gradeReview(item.key, cardState, grade);
            const labels = ['again', 'hard', 'good', 'easy'];
            s[labels[grade]]++;
            s.done++;
            showNextReviewCard();
        };
    });
}

// 算法：基于当前状态预测 4 个 grade 后的新 interval
function predictNextIntervals(state) {
    const now = Date.now();
    let interval, ease, reps, lapses;
    if (state.isNew) {
        interval = 0; ease = 2.5; reps = 0; lapses = 0;
    } else {
        interval = state.interval || 0; ease = state.ease || 2.5; reps = state.reps || 0; lapses = state.lapses || 0;
    }
    const out = [];
    // Again
    out.push(1);
    // Hard
    out.push(Math.max(1, Math.round(interval * 1.2)));
    // Good
    out.push(Math.max(1, Math.round((interval + 1) * ease)));
    // Easy
    out.push(Math.max(2, Math.round((interval + 1) * ease * 1.3)));
    return out;
}

function formatInterval(days) {
    if (days < 1) return '<1 天';
    if (days === 1) return '1 天';
    if (days < 30) return days + ' 天';
    if (days < 365) return Math.round(days / 30) + ' 月';
    return Math.round(days / 365 * 10) / 10 + ' 年';
}

function gradeReview(key, oldState, grade) {
    const store = getReviewStore();
    const now = Date.now();
    const DAY = 86400000;
    let interval, ease, reps, lapses;
    if (oldState.isNew) {
        interval = 0; ease = 2.5; reps = 0; lapses = 0;
    } else {
        interval = oldState.interval || 0; ease = oldState.ease || 2.5; reps = oldState.reps || 0; lapses = oldState.lapses || 0;
    }
    let nextInterval, nextEase, nextReps, nextLapses;
    if (grade === 0) {
        // Again
        nextInterval = 1;
        nextEase = Math.max(1.3, ease - 0.2);
        nextReps = 0;
        nextLapses = lapses + 1;
    } else if (grade === 1) {
        // Hard
        nextInterval = Math.max(1, Math.round(interval * 1.2));
        nextEase = Math.max(1.3, ease - 0.05);
        nextReps = reps + 1;
        nextLapses = lapses;
    } else if (grade === 2) {
        // Good
        nextInterval = Math.max(1, Math.round((interval + 1) * ease));
        nextEase = ease;
        nextReps = reps + 1;
        nextLapses = lapses;
    } else {
        // Easy
        nextInterval = Math.max(2, Math.round((interval + 1) * ease * 1.3));
        nextEase = ease + 0.05;
        nextReps = reps + 1;
        nextLapses = lapses;
    }
    store[key] = {
        due: now + nextInterval * DAY,
        interval: nextInterval,
        ease: nextEase,
        reps: nextReps,
        lapses: nextLapses,
        lastReview: now,
        isNew: false,
    };
    saveReviewStore(store);
}

function showReviewSummary() {
    const s = reviewSession;
    const area = s.modal.querySelector('#review-card-area');
    const fill = s.modal.querySelector('#review-progress-fill');
    const text = s.modal.querySelector('#review-progress-text');
    fill.style.width = '100%';
    text.textContent = s.done + ' / ' + s.total;
    const accuracy = Math.round((s.good + s.easy) / Math.max(1, s.done) * 100);
    let nextDue = null;
    const store = getReviewStore();
    Object.values(store).forEach(c => { if (!nextDue || c.due < nextDue) nextDue = c.due; });
    const nextLabel = nextDue ? new Date(nextDue).toLocaleDateString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : '—';
    area.innerHTML = `
        <div class="review-summary">
            <h3>今日复习完成</h3>
            <div class="score-num">${accuracy}%</div>
            <div class="stats-row">
                <div class="stat-cell"><div class="n">${s.again}</div><div class="l">忘了</div></div>
                <div class="stat-cell"><div class="n">${s.hard}</div><div class="l">勉强</div></div>
                <div class="stat-cell"><div class="n">${s.good}</div><div class="l">记得</div></div>
                <div class="stat-cell"><div class="n">${s.easy}</div><div class="l">秒答</div></div>
            </div>
            <div class="review-next-due">下次复习：${nextLabel}</div>
            <button class="btn-primary" id="review-finish-btn" style="margin-top:16px">完成</button>
        </div>`;
    area.querySelector('#review-finish-btn').onclick = () => {
        s.modal.classList.remove('visible');
        reviewSession = null;
        refreshReviewQueue();
        renderOverview();
    };
}

function escapeHtml(s) {
    return String(s)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
}

document.getElementById('start-review').addEventListener('click', () => {
    if (!Array.isArray(notes) || notes.length === 0) {
        showAnkiHelp('还没有高亮或笔记，先在正文里选中文字添加吧。');
        return;
    }
    // 计算所有 due（不只是今天到期的）
    const store = getReviewStore();
    const now = Date.now();
    const dueList = [];
    notes.forEach(n => {
        const key = cardKeyFromNote(n);
        if (!key) return;
        const card = store[key];
        if (!card) {
            dueList.push({ key, n, isNew: true });
        } else if (card.due <= now) {
            dueList.push({ key, n, isNew: false });
        }
    });
    if (dueList.length === 0) {
        // 没有到期，但可能有"今天刚复习完的"
        showAnkiHelp('当前没有到期卡片。继续读章节自动加入复习队列。');
        return;
    }
    // 按到期时间排序（新卡最后，让用户先巩固旧卡）
    dueList.sort((a, b) => {
        const sa = store[a.key];
        const sb = store[b.key];
        if (!sa && !sb) return 0;
        if (!sa) return -1; // 新卡在前
        if (!sb) return 1;
        return sa.due - sb.due;
    });
    startReviewSession(dueList.slice(0, 30)); // 每次最多复习 30 张
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

    // 状态 filter 预计算
    const completed = new Set(Object.keys(progress.completed || {}));
    const bookmarks = new Set(Object.keys(progress.bookmarks || {}));
    const notesChapters = new Set((Array.isArray(notes) ? notes : []).map(n => n && n.chapterId).filter(Boolean));
    function statusPass(id) {
        switch (activeFilter) {
            case '__status_read': return completed.has(id);
            case '__status_unread': return !completed.has(id) && !bookmarks.has(id);
            case '__status_with_notes': return notesChapters.has(id);
            case '__status_with_bookmarks': return bookmarks.has(id);
            default: return true;
        }
    }

    for (const item of searchIndex) {
        if (activeFilter.startsWith('__status_')) {
            if (!statusPass(item.id)) continue;
        } else if (activeFilter !== 'all' && item.book !== activeFilter) {
            continue;
        }
        if (item.lower.includes(q)) {
            // 算分数：标题命中 > 内容命中
            const titleIdx = item.title.toLowerCase().indexOf(q);
            let score = titleIdx >= 0 ? (100 - titleIdx) : 1;
            // 状态 filter 时给状态轻微加权
            if (activeFilter === '__status_with_bookmarks' && bookmarks.has(item.id)) score += 5;
            if (activeFilter === '__status_with_notes' && notesChapters.has(item.id)) score += 5;
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
    hideOverview();

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
function openCommandPalette() {
    commandPalette.classList.add('visible');
    setTimeout(() => { commandInput.focus(); commandInput.select(); }, 30);
}
document.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        openCommandPalette();
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

// 工具栏搜索按钮 → 打开命令面板
const searchTriggerBtn = document.getElementById('search-trigger-btn');
if (searchTriggerBtn) searchTriggerBtn.addEventListener('click', openCommandPalette);

// 系列对比表: + 按钮展开章节列表
document.addEventListener('click', (e) => {
    const btn = e.target.closest('.compare-expand');
    if (!btn) return;
    e.preventDefault();
    e.stopPropagation();
    const targetId = btn.dataset.target;
    const target = document.getElementById(targetId);
    if (!target) return;
    const open = !target.hidden;
    target.hidden = open;
    btn.classList.toggle('open', !open);
    btn.textContent = !open ? '×' : '+';
});

// 点击背景关闭
commandPalette.addEventListener('click', (e) => {
    if (e.target === commandPalette) {
        commandPalette.classList.remove('visible');
        commandInput.value = '';
    }
});
"""


def build_html():
    global JS
    books = discover_books()

    if not books:
        print("警告：没找到任何书。请在 books/ 目录下创建子目录。")
        return

    # 扫描 assets/audio/{book}/*.mp3 — 哪些章节已有 TTS 音频
    # 避免运行时 HEAD 检测 → 不再发 175 个探测请求 → 没有 404 噪声
    audio_dir = ROOT / "assets" / "audio"
    available_audio = {}  # anchor -> url
    if audio_dir.exists():
        for book_dir in audio_dir.iterdir():
            if not book_dir.is_dir():
                continue
            book = book_dir.name
            for mp3 in book_dir.glob("*.mp3"):
                chap = mp3.stem
                anchor = f"{book}__{chap}"
                available_audio[anchor] = f"assets/audio/{book}/{chap}.mp3"

    # 构建内容
    bookshelf_html_parts = []
    content_parts = []
    total_chars = 0
    total_chapters = 0
    chapter_anchors = []  # j/k 跳转用, 按文档顺序
    chapter_book_map = {}  # anchor -> book_slug (动态 OG meta 切换用)

    book_icons = {}  # slug -> svg (sidebar 小图标，16px)
    book_icons_big = {}  # slug -> svg (封面大图标，72px)
    book_levels = {}  # slug -> (level_int, level_name) 难度

    for book_idx, (book_slug, meta, chapters) in enumerate(books):
        icon_name = meta.get("icon", "book")
        book_icons[book_slug] = svg_icon(icon_name, size=16)
        book_icons_big[book_slug] = svg_icon(icon_name, size=72)
        book_color = meta.get("color", "#b08968")
        book_level = meta.get("level", 3)
        book_level_name = meta.get("level_name", "进阶")
        book_levels[book_slug] = (book_level, book_level_name)

        # 书架章节列表
        chapter_items = []
        book_chapters_html_parts = []
        book_chapter_bodies = []  # [{anchor, body_html}, ...] — 供 lazy load JSON 用

        # 预计算所有章节展示标题（用于底部 prev/next 导航）
        chap_titles = []
        for chap_slug, chap_path in chapters:
            md_text = chap_path.read_text(encoding="utf-8")
            chap_titles.append(chapter_display_title(md_text, chap_slug))

        for chap_idx, (chap_slug, chap_path) in enumerate(chapters, 1):
            md_text = chap_path.read_text(encoding="utf-8")
            content_html = md_to_html(md_text)
            chars = count_words(md_text)
            total_chars += chars
            minutes = max(1, chars // 400)

            # TL;DR：从首段提炼摘要（自动去 markdown 标记）
            import re as _re
            _plain = _re.sub(r"`([^`]+)`", r"\1", md_text)
            _plain = _re.sub(r"\*\*([^*]+)\*\*", r"\1", _plain)
            _plain = _re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", _plain)
            _first_para = ""
            _first_quote = ""
            for _line in _plain.split("\n\n"):
                _line = _line.strip()
                if not _line or _line.startswith("#"):
                    continue
                # 跳过代码块
                if "```" in _line or _line.startswith("    "):
                    continue
                if _line.startswith(">"):
                    if not _first_quote:
                        _first_quote = _re.sub(r"^>\s*", "", _line)
                    continue
                # 跳过 - 列表
                if _line.startswith(("-", "*", "1.", "2.", "3.", "4.", "5.", "6.", "7.", "8.", "9.")):
                    continue
                if not _first_para or len(_first_para) < 20:
                    _first_para = _line
                    if len(_first_para) > 20:
                        break
            # 截断到 ~140 字，加省略号
            tldr_html = ""
            # 优先用 blockquote（一般是作者写的导语），如果没有或太短，用首段
            if _first_quote and len(_first_quote) > 15:
                _tldr_source = _first_quote
            else:
                _tldr_source = _first_para
            if _tldr_source and len(_tldr_source) > 15:
                _tldr_text = _tldr_source[:140].rstrip("，。、；：")
                if len(_tldr_source) > 140:
                    _tldr_text += "…"
                tldr_html = (
                    f'<aside class="tldr-card">'
                    f'<div class="tldr-label">TL;DR</div>'
                    f'<p class="tldr-text">{_tldr_text}</p>'
                    f'</aside>'
                )

            # 提取章节内 TOC (H2/H3 标题)
            toc_items = extract_toc(content_html)
            toc_html = ""
            if len(toc_items) >= 3:  # 至少 3 个才显示
                toc_links = "".join(
                    f'<li class="toc-l{item["level"]}"><a href="#{item["id"]}" data-toc-id="{item["id"]}">{item["text"]}</a></li>'
                    for item in toc_items
                )
                toc_html = (
                    f'<aside class="chapter-toc" aria-label="本章目录">'
                    f'<div class="toc-title">本章目录</div>'
                    f'<ul class="toc-list">{toc_links}</ul>'
                    f'</aside>'
                )

            # 用目录名（去掉数字前缀）作为展示标题
            display_title = chap_titles[chap_idx - 1]

            # 章节锚点：bookSlug__chapterSlug
            anchor = f"{book_slug}__{chap_slug}"

            chapter_items.append(
                f'<li><a href="#{anchor}">'
                f'<span class="ch-num">{chap_idx:02d}</span>'
                f'<span>{display_title}</span>'
                f'<span class="ch-read-pct" data-chapter="{anchor}"></span>'
                f'</a></li>'
            )

            # 上一章 / 下一章信息
            prev_link = ''
            next_link = ''
            if chap_idx > 1:
                prev_slug = chapters[chap_idx - 2][0]
                prev_anchor = f"{book_slug}__{prev_slug}"
                prev_title = chap_titles[chap_idx - 2]
                prev_link = (
                    f'<a class="chap-nav-link chap-nav-prev" href="#{prev_anchor}">'
                    f'<span class="chap-nav-label">\u4e0a\u4e00\u7ae0</span>'
                    f'<span class="chap-nav-num">{chap_idx - 1:02d} / {len(chapters):02d}</span>'
                    f'<span class="chap-nav-title">{prev_title}</span>'
                    f'</a>'
                )
            if chap_idx < len(chapters):
                next_slug = chapters[chap_idx][0]
                next_anchor = f"{book_slug}__{next_slug}"
                next_title = chap_titles[chap_idx]
                next_link = (
                    f'<a class="chap-nav-link chap-nav-next" href="#{next_anchor}">'
                    f'<span class="chap-nav-label">\u4e0b\u4e00\u7ae0</span>'
                    f'<span class="chap-nav-num">{chap_idx + 1:02d} / {len(chapters):02d}</span>'
                    f'<span class="chap-nav-title">{next_title}</span>'
                    f'<span class="chap-nav-arrow">\u2192</span>'
                    f'</a>'
                )
            else:
                # 最后一章 → 回到目录
                next_link = (
                    f'<a class="chap-nav-link chap-nav-next chap-nav-overview" href="#{meta.get("order", [""])[0] and f"{book_slug}__{chapters[0][0]}" or ""}" '
                    f'onclick="event.preventDefault();window.scrollTo({{top:0,behavior:\'smooth\'}});if(typeof showOverview===\'function\')showOverview();return false;">'
                    f'<span class="chap-nav-label">\u672c\u4e66\u8bfb\u5b8c\uff0c\u56de\u5230\u76ee\u5f55</span>'
                    f'<span class="chap-nav-num">\u2605 \u2605 \u2605</span>'
                    f'<span class="chap-nav-title">{meta.get("title", book_slug)}</span>'
                    f'<span class="chap-nav-arrow">\u2191</span>'
                    f'</a>'
                )

            chap_nav_html = (
                f'<nav class="chap-nav" aria-label="\u7ae0\u8282\u5bfc\u822a">'
                f'{prev_link}'
                f'{next_link}'
                f'</nav>'
            ) if prev_link or next_link else ''

            # 章节顶部 progress 条
            chap_progress_html = (
                f'<div class="chap-progress">'
                f'<div class="chap-progress-bar"><div class="chap-progress-fill" style="width:{(chap_idx/len(chapters))*100:.1f}%"></div></div>'
                f'<div class="chap-progress-info">'
                f'<span class="chap-progress-pos">第 <b>{chap_idx}</b> / {len(chapters)} 章</span>'
                f'<span class="chap-progress-sep">\u00b7</span>'
                f'<span class="chap-progress-pct" data-book-progress="{book_slug}">\u6574\u672c 0%</span>'
                f'</div>'
                f'</div>'
            )

            # ch01 系列导览：列出本系列所有章节（仅 ch01 显示）
            series_intro_html = ''
            if chap_idx == 1:
                toc_items = ''.join(
                    f'<li><a href="#{book_slug}__{cs}"><span class="series-toc-num">{i:02d}</span><span class="series-toc-title">{chap_titles[i-1]}</span></a></li>'
                    for i, (cs, _) in enumerate(chapters, 1)
                )
                series_intro_html = (
                    f'<aside class="series-intro">'
                    f'<div class="series-intro-head">'
                    f'<span class="series-intro-label">\u7cfb\u5217\u5bfc\u89c8</span>'
                    f'<span class="series-intro-count">{len(chapters)} \u7ae0</span>'
                    f'<button class="series-intro-toggle" aria-expanded="true" aria-controls="series-toc-{book_slug}">\u6536\u8d77</button>'
                    f'</div>'
                    f'<p class="series-intro-desc">{meta.get("description", "")}</p>'
                    f'<ol class="series-toc" id="series-toc-{book_slug}">{toc_items}</ol>'
                    f'</aside>'
                )

            level_dots = "●" * book_level + "○" * (5 - book_level)
            level_badge = (
                f'<span class="level-badge" data-level="{book_level}" title="难度 {book_level}/5">'
                f'<span class="level-dots">{level_dots}</span>'
                f'<span class="level-name">{book_level_name}</span>'
                f'</span>'
            )
            # build-time 决定是否渲染 TTS 按钮 + 播放器（避免运行时 175 个 HEAD 探测 → 165 个 404）
            has_audio = anchor in available_audio
            tts_btn_html = (
                f'<button class="chapter-tts-btn" data-tts-anchor="{anchor}" data-audio-url="{available_audio[anchor]}" title="朗读本章（Edge TTS）">{svg_icon("volume", size=14)} <span class="tts-label">朗读</span></button>'
                if has_audio else ''
            )
            tts_player_html = (
                f'<div class="chapter-tts-player" data-tts-player="{anchor}"></div>'
                if has_audio else ''
            )
            book_chapters_html_parts.append(
                f'<article id="{anchor}" class="chapter" data-book="{book_slug}" data-chap="{chap_slug}">'
                f'<nav class="breadcrumb" aria-label="位置导航">'
                f'<a href="#overview">首页</a>'
                f'<span class="bc-sep">›</span>'
                f'<a href="#book-{book_slug}">{meta.get("title", book_slug)}</a>'
                f'<span class="bc-sep">›</span>'
                f'<span class="bc-current">第 {chap_idx} 章</span>'
                f'</nav>'
                f'<div class="chapter-ribbon" style="--book-color: {book_color}">'
                f'<div class="ribbon-icon">{book_icons_big.get(book_slug, "")}</div>'
                f'<div class="ribbon-meta">'
                f'<div class="ribbon-book">{meta.get("title", book_slug)}</div>'
                f'<div class="ribbon-num">CHAPTER {chap_idx:02d} / {len(chapters):02d}</div>'
                f'</div>'
                f'</div>'
                f'<h1 class="chapter-title">{display_title}</h1>'
                f'{chap_progress_html}'
                f'<div class="chapter-meta-row">'
                f'<div class="chapter-meta">约 {minutes} 分钟 · {chars} 字 · {level_badge}</div>'
                f'<div class="chapter-actions">'
                f'{tts_btn_html}'
                f'<button class="chapter-share-btn" data-share-anchor="{anchor}" title="分享本章链接">{svg_icon("share", size=14)} 分享</button>'
                f'</div>'
                f'</div>'
                f'{tts_player_html}'
                f'{series_intro_html}'
                f'<div class="chapter-body" data-load-book="{book_slug}" data-load-chapter="{anchor}">'
                f'<div class="chapter-loading">加载章节内容…</div>'
                f'</div>'
                f'<div class="chapter-end">本章完</div>'
                f'{chap_nav_html}'
                f'<div class="related-chapters" id="related-chapters-{anchor}" data-chapter="{anchor}"></div>'
                f'<button class="completion-toggle" data-chapter="{anchor}">'
                f'<svg class="icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-2px;margin-right:4px"><rect x="3" y="3" width="18" height="18" rx="2"/></svg>'
                f'标记为已读</button>'
                f'</article>'
            )

            total_chapters += 1
            chapter_anchors.append(anchor)
            chapter_book_map[anchor] = book_slug
            # 收集章节 body HTML — 供 lazy load JSON 用
            body_inner = (
                f'<div class="chapter-content">'
                f'{tldr_html}'
                f'{content_html}'
                f'</div>'
                f'{toc_html}'
            )
            book_chapter_bodies.append({"anchor": anchor, "body": body_inner})

        # 书的章节数
        chap_count = len(chapters)

        # 书架 HTML
        bookshelf_html_parts.append(
            f'<div class="book-group" data-book="{book_slug}">'
            f'<div class="book-header">'
            f'<span class="book-icon">{book_icons[book_slug]}</span>'
            f'<span class="book-title-text">{meta["title"]}</span>'
            f'<span class="book-chapters-count">{chap_count} 章</span>'
            f'<span class="book-chevron" aria-hidden="true">{svg_icon("chevron-down", size=14)}</span>'
            f'</div>'
            f'<div class="book-progress-bar"><div class="book-progress-bar-fill" style="width:0%"></div></div>'
            f'<div class="book-progress-label">0 / {chap_count}</div>'
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

        # 包一层 <section id="book-{slug}"> 让 breadcrumb 锚点生效
        content_parts.append(f'<section id="book-{book_slug}" class="book-section">' + book_cover + "".join(book_chapters_html_parts) + '</section>')

        # 写 per-book JSON 供 lazy load
        if book_chapter_bodies:
            import json as __json
            books_dir = ROOT / "assets" / "books"
            books_dir.mkdir(parents=True, exist_ok=True)
            with open(books_dir / f"{book_slug}.json", "w", encoding="utf-8") as bf:
                __json.dump({"chapters": book_chapter_bodies}, bf, ensure_ascii=False)

    total_minutes = max(1, total_chars // 400)

    # 生成首页 TOC (overview section)
    overview_html = build_overview_html(books, total_chapters, total_chars, total_minutes)

    # j/k 跳转的章节列表 (JSON array, 按文档顺序)
    import json as _json
    chapter_anchors_json = _json.dumps(chapter_anchors, ensure_ascii=False)
    # 交叉引用：book -> { 1..10 -> {anchor, title} }
    chapter_refs = {}
    for _slug, _meta, _chapters in books:
        chapter_refs[_slug] = []
        for _i, (_cslug, _cpath) in enumerate(_chapters, 1):
            _ct = chapter_display_title(_cpath.read_text(encoding="utf-8"), _cslug)
            chapter_refs[_slug].append({
                "num": _i,
                "anchor": f"{_slug}__{_cslug}",
                "title": _ct,
            })
    chapter_refs_json = _json.dumps(chapter_refs, ensure_ascii=False)
    chapter_book_map_json = _json.dumps(chapter_book_map, ensure_ascii=False)
    chapter_titles_map = {}
    for _slug, _meta, _chs in books:
        for _cs, _cp in _chs:
            _anchor = f"{_slug}__{_cs}"
            _md = _cp.read_text(encoding="utf-8")
            chapter_titles_map[_anchor] = chapter_display_title(_md, _cs)
    chapter_titles_map_json = _json.dumps(chapter_titles_map, ensure_ascii=False)
    # CHAPTERS_BY_BOOK — 供"同系列下一章"用 (按书分组, 保持原顺序)
    chapters_by_book = {}
    for _slug, _meta, _chs in books:
        chapters_by_book[_slug] = [f"{_slug}__{_cs}" for _cs, _cp in _chs]
    chapters_by_book_init = "Object.assign(CHAPTERS_BY_BOOK, " + _json.dumps(chapters_by_book, ensure_ascii=False) + ")"
    # 学习路径 fallback 用：每本书的 priority + 首章 anchor/title
    books_meta = {}
    for _slug, _meta, _chs in books:
        if not _chs:
            continue
        _first_cs, _first_cp = _chs[0]
        books_meta[_slug] = {
            "title": _meta.get("title", _slug),
            "priority": _meta.get("priority", 999),
            "color": _meta.get("color", "#b08968"),
            "icon": _meta.get("icon", "book"),
            "desc": _meta.get("description", ""),
            "firstChapter": {
                "anchor": f"{_slug}__{_first_cs}",
                "title": chapter_display_title(_first_cp.read_text(encoding="utf-8"), _first_cs),
            },
        }
    books_meta_json = _json.dumps(books_meta, ensure_ascii=False)
    # JS 不是 f-string, 用占位符后替换
    JS = JS.replace("__CHAPTERS_JSON__", chapter_anchors_json)
    JS = JS.replace("__CHAPTERS_BY_BOOK_INIT__", chapters_by_book_init)
    JS = JS.replace("__CHAPTER_REFS__", chapter_refs_json)
    JS = JS.replace("__CHAPTER_BOOK_MAP__", chapter_book_map_json)
    JS = JS.replace("__CHAPTER_TITLES_MAP__", chapter_titles_map_json)
    JS = JS.replace("__SITE_URL__", SITE_URL)
    JS = JS.replace("__ICONS_JSON__", _json.dumps(ICONS, ensure_ascii=False))
    JS = JS.replace("__BOOKS_META__", books_meta_json)

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>个人知识库 · 多书阅读</title>

    <link rel="manifest" href='data:application/json,{{"name":"个人知识库","short_name":"KB","start_url":"./","display":"standalone","background_color":"%23faf9f5","theme_color":"%23b08968","icons":[{{"src":"{PWA_ICON_DATA_URI}","sizes":"any","type":"image/svg+xml","purpose":"any"}}]}}'>
    <link rel="icon" type="image/svg+xml" href='{PWA_ICON_DATA_URI}'>
    <link rel="apple-touch-icon" href='{PWA_ICON_DATA_URI}'>
    <link rel="sitemap" type="application/xml" href="sitemap.xml">
    <link rel="alternate" type="application/rss+xml" title="个人知识库" href="rss.xml">
    <meta name="theme-color" content="#faf9f5">

    <!-- Open Graph / Twitter Card -->
    <meta property="og:type" content="website">
    <meta property="og:url" content="{SITE_URL}">
    <meta property="og:title" content="个人知识库 · {len(books)} 个系列 · {total_chapters} 章" id="og-title">
    <meta property="og:description" content="Multi-Agent / LLM Prompt / CrewAI / RAG / Harness Engineering / Cost / Indie / Context / Skills / Claude Code" id="og-desc">
    <meta property="og:image" content="{SITE_URL}assets/og.png" id="og-image">
    <meta property="og:image:width" content="1200">
    <meta property="og:image:height" content="630">
    <meta property="og:locale" content="zh_CN">
    <meta property="og:site_name" content="个人知识库">
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="个人知识库 · {len(books)} 个系列 · {total_chapters} 章" id="tw-title">
    <meta name="twitter:description" content="Multi-Agent / LLM Prompt / CrewAI / RAG / Harness / Cost / Indie / Context / Skills / Claude Code" id="tw-desc">
    <meta name="twitter:image" content="{SITE_URL}assets/og.png" id="tw-image">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="default">
    <meta name="apple-mobile-web-app-title" content="知识库">

    <style>{CSS}</style>
</head>
<body class="sidebar-collapsed">
    <div class="progress"></div>
    <a class="skip-link" href="#main-content">跳到正文</a>
    <button class="focus-exit" id="focus-exit" title="退出专注模式 (F)" aria-label="退出专注模式">{svg_icon('close', size=18)}</button>

    <button class="sidebar-toggle" id="sidebar-toggle" title="目录 (S)" aria-label="切换侧边栏" aria-expanded="false">{svg_icon('menu')} 书架</button>

    <aside class="sidebar" role="navigation" aria-label="章节导航">
        <h1>个人知识库</h1>
        <div class="subtitle">{len(books)} 个系列 · {total_chapters} 章 · 约 {total_minutes} 分钟</div>
        <div class="bookshelf">
            {''.join(bookshelf_html_parts)}
        </div>
        <div class="sidebar-bookmarks" id="sidebar-bookmarks"></div>
        <button class="kb-launcher" id="kb-launcher" title="知识问答 (Ctrl+/)" aria-label="知识问答">
            {svg_icon('search', 14)} 知识问答
        </button>
    </aside>

    <!-- 知识问答 modal -->
    <div class="kb-modal" id="kb-modal" role="dialog" aria-label="知识问答" aria-modal="true">
        <div class="kb-modal-inner">
            <div class="kb-modal-header">
                <h3>知识问答</h3>
                <p class="kb-modal-desc">在 {len(books)} 系列 / {total_chapters} 章里问任何问题，从最相关的段落找答案。</p>
                <button class="modal-close kb-close" aria-label="关闭">×</button>
            </div>
            <div class="kb-input-row">
                <input type="text" class="kb-input" id="kb-input" placeholder="例如：什么是 RAG？怎么估算 token 成本？" autocomplete="off">
                <button class="kb-search-btn" id="kb-search-btn">{svg_icon('search', 14)} 搜</button>
            </div>
            <div class="kb-options">
                <label class="kb-toggle">
                    <input type="checkbox" id="kb-ai-toggle">
                    <span>启用 AI 语义搜索</span>
                    <span class="kb-toggle-hint">(首次 ~24 MB BGE 中文模型)</span>
                </label>
            </div>
            <div class="kb-suggestions" id="kb-suggestions" style="display:none"></div>
            <div class="kb-results" id="kb-results">
                <div class="kb-empty kb-hint">键入问题后回车。默认走 TF-IDF + 同义词扩展 + 标题加权，勾选 AI 语义搜索可加载 BGE 中文模型做 dense embedding 混合检索。</div>
            </div>
        </div>
    </div>

    <div class="toolbar" role="toolbar" aria-label="工具栏">
        <button id="more-btn" title="工具" aria-label="工具菜单">{svg_icon('menu')}</button>
        <div class="toolbar-menu" id="toolbar-menu">
            <div class="toolbar-grid">
                <div class="t-row">
                    <div class="t-group">
                        <span class="t-lbl">字号</span>
                        <div class="t-btns">
                            <button class="opt-btn font-btn" data-size="small" title="小字号 (-)">A−</button>
                            <button class="opt-btn font-btn" data-size="medium" title="中字号">A</button>
                            <button class="opt-btn font-btn" data-size="large" title="大字号 (+)">A+</button>
                        </div>
                    </div>
                    <div class="t-group">
                        <span class="t-lbl">宽度</span>
                        <div class="t-btns">
                            <button class="opt-btn width-btn" data-width="narrow" title="窄">窄</button>
                            <button class="opt-btn width-btn" data-width="medium" title="中">中</button>
                            <button class="opt-btn width-btn" data-width="wide" title="宽">宽</button>
                        </div>
                    </div>
                </div>
                <div class="t-row">
                    <div class="t-group">
                        <span class="t-lbl">字体</span>
                        <div class="t-btns">
                            <button class="opt-btn fam-btn" data-fam="serif" title="衬线">衬</button>
                            <button class="opt-btn fam-btn" data-fam="sans" title="无衬线">黑</button>
                            <button class="opt-btn fam-btn" data-fam="mono" title="等宽">等</button>
                        </div>
                    </div>
                    <div class="t-group">
                        <span class="t-lbl">主题</span>
                        <div class="t-btns">
                            <button class="opt-btn theme-btn" data-theme="light" title="亮">亮</button>
                            <button class="opt-btn theme-btn" data-theme="dark" title="暗">暗</button>
                            <button class="opt-btn theme-btn" data-theme="sepia" title="羊皮纸">纸</button>
                            <button class="opt-btn theme-btn" data-theme="green" title="护眼绿">绿</button>
                        </div>
                    </div>
                </div>
            </div>
            <div class="toolbar-divider"></div>
            <div class="toolbar-actions">
                <button id="search-trigger-btn">{svg_icon('search')}<span>搜索</span><kbd>⌘K</kbd></button>
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
        <input type="text" class="notes-search" id="notes-search" placeholder="搜索笔记 (Cmd+Shift+F)" autocomplete="off">
        <div class="notes-filter" id="notes-filter">
            <button class="nf-chip active" data-tag="all">全部</button>
            <button class="nf-chip" data-tag="重要">重要</button>
            <button class="nf-chip" data-tag="todo">todo</button>
            <button class="nf-chip" data-tag="问题">问题</button>
            <button class="nf-chip" data-tag="想法">想法</button>
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
                <button id="export-anki" title="把高亮 + 笔记导出为 Anki 闪卡 (CSV)">{svg_icon('layers')} 导出 Anki 闪卡</button>
                <button id="show-notes-graph" title="把高亮 + 笔记画成知识图谱">{svg_icon('network')} 笔记图谱</button>
                <button id="start-review" title="基于间隔重复算法复习高亮 / 笔记">{svg_icon('brain')} 今日复习</button>
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
                <div class="help-row"><span>上一章 / 下一章</span><span><kbd>K</kbd> / <kbd>J</kbd></span></div>
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

    <!-- 首次访问引导 -->
    <div class="welcome-modal" id="welcome-modal" role="dialog" aria-label="欢迎" aria-modal="true" style="display:none">
        <div class="welcome-inner">
            <div class="welcome-hero">
                <h2>欢迎来到个人知识库</h2>
                <p class="welcome-desc">{len(books)} 个系列 · {total_chapters} 章 · 约 {total_minutes} 分钟。选 3 个你感兴趣的方向,我会推荐 5 章让你开始。</p>
            </div>
            <div class="welcome-tags" id="welcome-tags">
                <button class="welcome-tag" data-tag="rag">RAG / 检索增强</button>
                <button class="welcome-tag" data-tag="agent">Agent / 多智能体</button>
                <button class="welcome-tag" data-tag="claude-code">Claude Code 实战</button>
                <button class="welcome-tag" data-tag="codex">Codex / 编程工具</button>
                <button class="welcome-tag" data-tag="vibe-coding">Vibe Coding</button>
                <button class="welcome-tag" data-tag="harness">Harness 工程</button>
                <button class="welcome-tag" data-tag="memory">记忆 / 上下文</button>
                <button class="welcome-tag" data-tag="llm-prompt">Prompt / LLM</button>
                <button class="welcome-tag" data-tag="cn-codex">国产 AI 工具</button>
                <button class="welcome-tag" data-tag="indie">独立开发者</button>
                <button class="welcome-tag" data-tag="content">AI 内容创作</button>
                <button class="welcome-tag" data-tag="embodied">具身智能 / 机器人</button>
            </div>
            <p class="welcome-hint" id="welcome-hint">选 3 个标签 (已选 <span id="welcome-count">0</span>/3)</p>
            <div class="welcome-actions">
                <button class="welcome-skip" id="welcome-skip">跳过,我自己逛逛</button>
                <button class="welcome-go" id="welcome-go" disabled>推荐 5 章 →</button>
            </div>
        </div>
    </div>
    <div class="welcome-results" id="welcome-results" style="display:none">
        <div class="welcome-results-inner">
            <h3>为你挑了这 5 章</h3>
            <div class="welcome-results-list" id="welcome-results-list"></div>
            <button class="welcome-close" id="welcome-close">开始阅读</button>
        </div>
    </div>

    <!-- 命令面板（搜索） -->
    <div class="command-palette">
        <div class="command-modal">
            <input type="text" class="command-input" placeholder="搜索章节标题或内容...">
            <div class="command-filters" id="command-filters">
                <button class="command-chip active" data-filter="all">全部</button>
                <button class="command-chip command-chip-status" data-filter="__status_unread">未读</button>
                <button class="command-chip command-chip-status" data-filter="__status_with_notes">有笔记</button>
                <button class="command-chip command-chip-status" data-filter="__status_with_bookmarks">有书签</button>
                <button class="command-chip command-chip-status" data-filter="__status_read">已读完</button>
                {''.join(f'<button class="command-chip" data-filter="{slug}">{title}</button>' for slug, title, _ in books)}
            </div>
            <div class="command-hint">
                <span>↑↓ 选择 · Enter 跳转 · Esc 关闭</span>
                <span>Ctrl+K</span>
            </div>
            <div class="command-results"></div>
        </div>
    </div>

    <main class="content" id="main-content" role="main">
        {overview_html}
        {''.join(content_parts)}
    </main>

    <!-- 开发者彩蛋面板：连按 5 次 ? 开启 -->
    <aside id="dev-panel" class="dev-panel" role="dialog" aria-label="\u5f00\u53d1\u8005\u70ed\u529b\u56fe" aria-modal="false">
        <div class="dev-panel-head">
            <div class="dev-panel-title">
                <span class="dev-panel-eyebrow">DEV MODE</span>
                <span id="dev-stats">\u52a0\u8f7d\u4e2d...</span>
            </div>
            <button class="dev-panel-close" aria-label="\u5173\u95ed">\u00d7</button>
        </div>
        <div id="dev-heatmap" class="dev-heatmap"></div>
        <div class="dev-panel-legend">
            <span><span class="dev-legend-cell done"></span>\u5df2\u8bfb</span>
            <span><span class="dev-legend-cell progress"></span>\u8fdb\u884c\u4e2d</span>
            <span><span class="dev-legend-cell unread"></span>\u672a\u8bfb</span>
            <span class="dev-panel-hint">\u6309 ESC \u6216 5\u00d7? \u5173\u95ed</span>
        </div>
    </aside>

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

    # 生成 sitemap.xml (SEO)
    build_sitemap(books)
    # 生成 rss.xml (订阅)
    build_rss(books)
    # 生成 robots.txt
    build_robots()
    # 生成 sw.js (PWA Service Worker, 同源文件, 不再用 blob URL)
    build_sw()
    # 生成 per-chapter 静态页 (100 个, 每章专属 OG + 跳转 index.html#anchor)
    build_per_chapter_pages(books)
    # 生成 knowledge index (RAG 知识问答用 — TF-IDF 向量 + 章节 chunk)
    build_knowledge_index(books)
    # 生成 dense embedding index (sentence-transformers BGE 中文,浏览器 transformers.js)
    # 首次会下载约 400MB 模型,之后缓存;可关 SKIP_DENSE=1 跳过
    if not os.environ.get("SKIP_DENSE"):
        try:
            build_dense_index(books)
        except Exception as e:
            print(f"WARN: dense index build failed: {e}")
            print("  (继续构建,知识问答仍可用 TF-IDF 模式)")


if __name__ == "__main__":
    build_html()