"""
OG image generator (1200x630).
默认生成全站 OG (assets/og.png); 接受 --book=<slug> 生成单本书的 OG (assets/og-<slug>.png).

设计: 暖米底 + 大字标题 + 装饰线 + 小副标题. 书本 OG 用书本主色块代替暖米底.
不依赖网络, 纯本地 Pillow + 系统字体.
"""
import argparse
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
ASSETS.mkdir(parents=True, exist_ok=True)

W, H = 1200, 630
BG = (250, 249, 245)         # 暖米 — 跟 --bg 同步
TEXT = (42, 42, 42)          # 跟 --text 同步
TEXT_FAINT = (138, 111, 71)  # 跟 --accent 同步
ACCENT = (176, 137, 104)     # 跟 --accent 一致

# 10 本书 — slug / 标题 / 主色 (跟 _meta.json 同步)
BOOKS = {
    "multi-agent":          ("Multi-Agent 实战",        (91, 140, 133)),
    "llm-prompt":           ("LLM Prompt 实战",         (176, 137, 104)),
    "crewai":               ("CrewAI 入门到实战",       (108, 99, 255)),
    "rag":                  ("RAG 实战",                (13, 148, 136)),
    "harness-engineering":  ("Harness Engineering",     (194, 65, 12)),
    "agent-cost":           ("Agent 成本工程",          (79, 70, 229)),
    "indie-ai-product":     ("Indie + AI",              (217, 119, 6)),
    "context-engineering":  ("Context Engineering 实战", (124, 58, 237)),
    "agent-skills":         ("Agent Skills 实战",       (236, 72, 153)),
    "claude-code":          ("Claude Code 实战",        (5, 150, 105)),
}


def find_font(candidates, size):
    for p in candidates:
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            continue
    return ImageFont.load_default()


# Windows 字体路径; 字体名匹配 site CSS
SERIF = find_font([
    r"C:\Windows\Fonts\NotoSerifSC-VF.ttf",
    r"C:\Windows\Fonts\STKAITI.TTF",
    r"C:\Windows\Fonts\simsun.ttc",
], 130)
SANS = find_font([
    r"C:\Windows\Fonts\NotoSansSC-VF.ttf",
    r"C:\Windows\Fonts\msyh.ttc",
], 28)
SANS_SMALL = find_font([
    r"C:\Windows\Fonts\NotoSansSC-VF.ttf",
    r"C:\Windows\Fonts\msyh.ttc",
], 22)


def draw_centered(draw, text, font, y, fill, width=W):
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    x = (width - tw) // 2 - bbox[0]
    draw.text((x, y), text, font=font, fill=fill)


def render_site_og(out_path: Path):
    """全站 OG — 暖米底."""
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    draw_centered(draw, "K N O W L E D G E   G A R D E N", SANS_SMALL, 100, TEXT_FAINT)
    draw.line([(W // 2 - 30, 165), (W // 2 + 30, 165)], fill=ACCENT, width=2)
    draw_centered(draw, "个人知识库", SERIF, 215, TEXT)
    draw_centered(draw, "10 个系列 · 100 章 · 约 303 分钟", SANS, 405, TEXT_FAINT)
    draw_centered(draw, "mishishi.github.io/knowledge-garden", SANS_SMALL, 540, TEXT_FAINT)

    # 底部 10 本书色块
    for i, (_slug, (_title, color)) in enumerate(BOOKS.items()):
        x0 = 60 + i * 16
        draw.rectangle([(x0, H - 80), (x0 + 10, H - 40)], fill=color)

    img.save(out_path, "PNG", optimize=True)
    print(f"生成 {out_path} ({out_path.stat().st_size:,} bytes, {W}x{H})")


def render_book_og(slug: str, out_path: Path):
    """单本书 OG — 书主色底 + 暖米大标题."""
    if slug not in BOOKS:
        raise SystemExit(f"未知 slug: {slug}. 可用: {', '.join(BOOKS.keys())}")
    title, color = BOOKS[slug]

    img = Image.new("RGB", (W, H), color)
    draw = ImageDraw.Draw(img)

    draw_centered(draw, "K N O W L E D G E   G A R D E N", SANS_SMALL, 100, (255, 255, 255))
    draw.line([(W // 2 - 30, 165), (W // 2 + 30, 165)], fill=(255, 255, 255), width=2)
    draw_centered(draw, title, SERIF, 230, (255, 255, 255))
    draw_centered(draw, "10 章 · 个人知识库", SANS, 430, (255, 255, 255))
    draw_centered(draw, "mishishi.github.io/knowledge-garden", SANS_SMALL, 540, (255, 255, 255))

    img.save(out_path, "PNG", optimize=True)
    print(f"生成 {out_path} ({out_path.stat().st_size:,} bytes, {W}x{H})")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--book", default=None, help="指定书 slug (e.g. multi-agent); 省略则生成全站 OG")
    args = ap.parse_args()

    if args.book:
        render_book_og(args.book, ASSETS / f"og-{args.book}.png")
    else:
        render_site_og(ASSETS / "og.png")
