"""
Book cover generator for knowledge-garden
Renders 900x500 WeChat-style covers with gradient bg + big title + icon
"""
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "covers"
OUT.mkdir(parents=True, exist_ok=True)

# 字体路径（用 Noto SC，跨平台稳）
FONT_SERIF = r"C:\Windows\Fonts\NotoSerifSC-VF.ttf"   # 思源宋体替代 — title
FONT_SANS  = r"C:\Windows\Fonts\NotoSansSC-VF.ttf"    # 思源黑体替代 — subtitle/meta
FONT_YAHEI = r"C:\Windows\Fonts\msyh.ttc"             # fallback

# 10 个 book 的元数据 (跟 _meta.json 同步)
BOOKS = [
    {
        "slug": "multi-agent",
        "title": "Multi-Agent 实战",
        "subtitle": "10 章学透多 Agent 系统架构",
        "chapters": 10,
        "chars": 8758,
        "color": (91, 140, 133),       # #5b8c85
        "icon": "M4 12h16M4 6h16M4 18h7",  # agent nodes
    },
    {
        "slug": "llm-prompt",
        "title": "LLM Prompt 实战",
        "subtitle": "10 章掌握 prompt 工程方法论",
        "chapters": 10,
        "chars": 11944,
        "color": (176, 137, 104),      # #b08968
        "icon": "M9 5l7 7-7 7",         # arrow
    },
    {
        "slug": "crewai",
        "title": "CrewAI 入门到实战",
        "subtitle": "10 章搭起多 Agent 协作框架",
        "chapters": 10,
        "chars": 12371,
        "color": (108, 99, 255),       # #6c63ff
        "icon": "M16 11a3 3 0 1 0-6 0 3 3 0 0 0 6 0zM8 11a3 3 0 1 0-6 0 3 3 0 0 0 6 0z",  # 2 dots
    },
    {
        "slug": "rag",
        "title": "RAG 实战",
        "subtitle": "10 章从 0 搭建检索增强生成系统",
        "chapters": 10,
        "chars": 7102,
        "color": (13, 148, 136),       # #0d9488
        "icon": "M9 12h6M9 16h6M9 8h6",  # lines
    },
    {
        "slug": "harness-engineering",
        "title": "Harness Engineering",
        "subtitle": "10 章搭起 Agent 评测与 harness",
        "chapters": 10,
        "chars": 14725,
        "color": (194, 65, 12),        # #c2410c
        "icon": "M3 6h18M3 12h18M3 18h12",  # layers
    },
    {
        "slug": "agent-cost",
        "title": "Agent 成本工程",
        "subtitle": "10 章压住 AI Agent 的烧钱速度",
        "chapters": 10,
        "chars": 9083,
        "color": (79, 70, 229),        # #4f46e5
        "icon": "M12 2v20M5 9l7-7 7 7",  # funnel-like
    },
    {
        "slug": "indie-ai-product",
        "title": "Indie + AI",
        "subtitle": "10 章做 AI 时代的产品方法论",
        "chapters": 10,
        "chars": 18120,
        "color": (217, 119, 6),        # #d97706
        "icon": "M4.5 16.5l-2 2M19.5 5.5l2-2M12 15l-3-3",  # rocket
    },
    {
        "slug": "context-engineering",
        "title": "Context Engineering 实战",
        "subtitle": "10 章从 prompt 跨进上下文工程",
        "chapters": 10,
        "chars": 15084,
        "color": (124, 58, 237),       # #7c3aed
        "icon": "M4 6h16M4 12h12M4 18h8",  # context lines
    },
    {
        "slug": "agent-skills",
        "title": "Agent Skills 实战",
        "subtitle": "10 章学会写 Claude Agent Skills",
        "chapters": 10,
        "chars": 12770,
        "color": (236, 72, 153),       # #ec4899
        "icon": "M12 2l2.5 6.5L21 9l-5 4.5L17.5 21 12 17l-5.5 4L8 13.5 3 9l6.5-.5L12 2z",  # star
    },
    {
        "slug": "claude-code",
        "title": "Claude Code 实战",
        "subtitle": "10 章上手 Claude Code 工作流",
        "chapters": 10,
        "chars": 11506,
        "color": (5, 150, 105),        # #059669
        "icon": "M4 17l6-6-6-6M12 19h8",  # terminal chevron
    },
]

W, H = 900, 500


def hex_to_rgb(h):
    h = h.lstrip('#')
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


def rgb_to_hex(rgb):
    return '#%02x%02x%02x' % rgb


def mix(c1, c2, t):
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


def draw_gradient(w, h, base):
    """对角线渐变：左上 = base * 0.85，右下 = base * 1.18"""
    img = Image.new("RGB", (w, h))
    px = img.load()
    c_dark = tuple(int(c * 0.78) for c in base)
    c_light = tuple(min(255, int(c * 1.22)) for c in base)
    for y in range(h):
        for x in range(w):
            t = (x / w * 0.6 + y / h * 0.4)
            px[x, y] = mix(c_dark, c_light, t)
    return img


def draw_icon_svg(svg_path, x, y, size, color):
    """简单的 SVG 路径绘制（用 cairosvg）"""
    try:
        import cairosvg
        png_data = cairosvg.svg2png(url=str(svg_path), output_width=size, output_height=size)
        from io import BytesIO
        icon = Image.open(BytesIO(png_data)).convert("RGBA")
        # tint
        r, g, b, a = icon.split()
        gray = Image.merge("RGB", (r, g, b))
        # 简单 tint：替换颜色
        out = Image.new("RGBA", icon.size, (255, 255, 255, 0))
        for i, px in enumerate(gray.getdata()):
            if px[0] < 250:  # 非白
                out.putpixel((i % icon.size[0], i // icon.size[0]), (*color, 255))
        # 太慢，改用纯 PIL 画
        return out
    except Exception as e:
        return None


def draw_simple_icon(draw, x, y, size, color, icon_kind):
    """直接用 Pillow 画简单 icon（避开 cairosvg 依赖）"""
    if icon_kind == "agent":
        # 3 个圆 + 连线
        cy = y + size // 2
        r = size // 6
        positions = [(x + size*0.15, cy), (x + size*0.5, cy - size*0.2), (x + size*0.85, cy)]
        for px, py in positions:
            draw.ellipse([px-r, py-r, px+r, py+r], outline=color, width=3)
        # 连线
        for i in range(len(positions) - 1):
            draw.line([positions[i], positions[i+1]], fill=color, width=2)
    elif icon_kind == "arrow":
        # >> 箭头
        ay = y + size // 2
        for i, offset in enumerate([0, size*0.18]):
            sx = x + size*0.25 + offset
            draw.line([(sx, ay - size*0.2), (x + size*0.75 + offset, ay)], fill=color, width=4)
            draw.line([(x + size*0.75 + offset, ay), (x + size*0.55 + offset, ay - size*0.2)], fill=color, width=4)
            draw.line([(x + size*0.75 + offset, ay), (x + size*0.55 + offset, ay + size*0.2)], fill=color, width=4)
    elif icon_kind == "team":
        # 3 个小人
        cx = x + size // 2
        h = size
        for i, dx in enumerate([-size*0.3, 0, size*0.3]):
            bx = cx + dx
            # 头
            draw.ellipse([bx - size*0.08, y + size*0.15, bx + size*0.08, y + size*0.31], outline=color, width=3)
            # 身体
            draw.line([(bx, y + size*0.32), (bx, y + size*0.65)], fill=color, width=3)
            # 手臂
            draw.line([(bx - size*0.15, y + size*0.45), (bx + size*0.15, y + size*0.45)], fill=color, width=3)
            # 腿
            draw.line([(bx, y + size*0.65), (bx - size*0.1, y + size*0.85)], fill=color, width=3)
            draw.line([(bx, y + size*0.65), (bx + size*0.1, y + size*0.85)], fill=color, width=3)
    elif icon_kind == "doc":
        # 一摞文档 + 放大镜
        # 3 个 doc
        for i, dy in enumerate([size*0.55, size*0.45, size*0.35]):
            draw.rectangle([x + size*0.2, y + dy, x + size*0.55, y + dy + size*0.1], outline=color, width=2)
        # 放大镜
        cx, cy = x + size*0.7, y + size*0.45
        rr = size * 0.18
        draw.ellipse([cx-rr, cy-rr, cx+rr, cy+rr], outline=color, width=3)
        draw.line([(cx + rr*0.7, cy + rr*0.7), (cx + rr*1.5, cy + rr*1.5)], fill=color, width=3)
    elif icon_kind == "stack":
        # 4 层堆叠卡片
        for i in range(4):
            off = i * 4
            draw.rectangle([x + size*0.2 + off, y + size*0.25 + off, x + size*0.8 + off, y + size*0.45 + off], outline=color, width=2)
    elif icon_kind == "funnel":
        # 漏斗 + 钱币
        fx, fy = x + size*0.2, y + size*0.2
        fw, fh = size*0.6, size*0.4
        # 漏斗外框
        draw.polygon([
            (fx, fy), (fx + fw, fy),
            (fx + fw*0.7, fy + fh*0.6), (fx + fw*0.3, fy + fh*0.6)
        ], outline=color, width=3)
        # 漏斗颈
        draw.rectangle([fx + fw*0.4, fy + fh*0.6, fx + fw*0.6, fy + fh*0.8], outline=color, width=2)
        # 钱币
        draw.ellipse([x + size*0.75, y + size*0.4, x + size*0.95, y + size*0.6], outline=color, width=2)
    elif icon_kind == "rocket":
        # 火箭 icon
        cx = x + size // 2
        cy = y + size // 2
        # 主体
        draw.polygon([
            (cx, y + size*0.15),
            (cx + size*0.15, y + size*0.5),
            (cx + size*0.15, y + size*0.75),
            (cx - size*0.15, y + size*0.75),
            (cx - size*0.15, y + size*0.5),
        ], outline=color, width=3)
        # 火
        draw.polygon([
            (cx - size*0.08, y + size*0.75), (cx + size*0.08, y + size*0.75),
            (cx, y + size*0.9)
        ], fill=color)
    elif icon_kind == "star":
        # 5 角星
        import math
        cx = x + size // 2
        cy = y + size // 2
        r_outer = size * 0.45
        r_inner = size * 0.2
        pts = []
        for i in range(10):
            angle = -math.pi / 2 + i * math.pi / 5
            r = r_outer if i % 2 == 0 else r_inner
            pts.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
        draw.polygon(pts, outline=color, width=3)


ICON_MAP = {
    "multi-agent": "agent",
    "llm-prompt": "arrow",
    "crewai": "team",
    "rag": "doc",
    "harness-engineering": "stack",
    "agent-cost": "funnel",
    "indie-ai-product": "rocket",
    "context-engineering": "stack",
    "agent-skills": "star",
    "claude-code": "arrow",
}


def render(book):
    color = book["color"]
    img = draw_gradient(W, H, color)
    draw = ImageDraw.Draw(img, "RGBA")

    # 1. 大数字（章节数）—— 浅色，大字
    try:
        font_big = ImageFont.truetype(FONT_SERIF, 160)
    except:
        font_big = ImageFont.truetype(FONT_YAHEI, 160)
    big_text = f"{book['chapters']:02d}"
    # 计算位置（左上）
    draw.text((40, -30), big_text, font=font_big, fill=(255, 255, 255, 60))

    # 2. 主标题 —— 大字
    try:
        font_title = ImageFont.truetype(FONT_SERIF, 64)
    except:
        font_title = ImageFont.truetype(FONT_YAHEI, 64)
    draw.text((40, 180), book["title"], font=font_title, fill=(255, 255, 255, 255))

    # 3. 副标题
    try:
        font_sub = ImageFont.truetype(FONT_SANS, 22)
    except:
        font_sub = ImageFont.truetype(FONT_YAHEI, 22)
    draw.text((40, 280), book["subtitle"], font=font_sub, fill=(255, 255, 255, 230))

    # 4. 几何 icon —— 右上
    icon_kind = ICON_MAP[book["slug"]]
    icon_size = 96
    draw_simple_icon(draw, W - icon_size - 40, 40, icon_size, (255, 255, 255, 220), icon_kind)

    # 5. 底部 meta
    try:
        font_meta = ImageFont.truetype(FONT_SANS, 14)
    except:
        font_meta = ImageFont.truetype(FONT_YAHEI, 14)
    meta_left = f"{book['chapters']} \u7ae0 \u00b7 {book['chars']:,} \u5b57"
    draw.text((40, H - 40), meta_left, font=font_meta, fill=(255, 255, 255, 200))
    # 右下 brand
    brand = "knowledge-garden"
    bbox = draw.textbbox((0, 0), brand, font=font_meta)
    bw = bbox[2] - bbox[0]
    draw.text((W - bw - 40, H - 40), brand, font=font_meta, fill=(255, 255, 255, 200))

    # 保存
    out_path = OUT / f"{book['slug']}.png"
    img.save(out_path, "PNG", optimize=True)
    print(f"saved: {out_path}  ({out_path.stat().st_size:,} bytes)")
    return out_path


if __name__ == "__main__":
    if len(sys.argv) > 1:
        # 只渲染指定 book
        for b in BOOKS:
            if b["slug"] == sys.argv[1]:
                render(b)
                break
    else:
        # 渲染全部
        for b in BOOKS:
            render(b)
