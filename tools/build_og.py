"""一次性脚本: 生成 OG image (1200x630), 提交到 assets/og.png.

设计: 暖米底 + 大字标题 + 装饰线 + 小副标题.
不依赖网络, 纯本地 Pillow + 系统字体.
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "og.png"
OUT.parent.mkdir(parents=True, exist_ok=True)

W, H = 1200, 630
BG = (250, 249, 245)         # 暖米 — 跟 --bg 同步
TEXT = (42, 42, 42)          # 跟 --text 同步
TEXT_FAINT = (138, 111, 71)  # 跟 --accent 同步
ACCENT = (176, 137, 104)     # 跟 --accent 一致


def find_font(candidates, size):
    for p in candidates:
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            continue
    return ImageFont.load_default()


# Windows 字体路径; 字体名匹配 site CSS
serif = find_font([
    r"C:\Windows\Fonts\NotoSerifSC-VF.ttf",
    r"C:\Windows\Fonts\STKAITI.TTF",
    r"C:\Windows\Fonts\simsun.ttc",
], 130)
sans = find_font([
    r"C:\Windows\Fonts\NotoSansSC-VF.ttf",
    r"C:\Windows\Fonts\msyh.ttc",
], 28)
sans_small = find_font([
    r"C:\Windows\Fonts\NotoSansSC-VF.ttf",
    r"C:\Windows\Fonts\msyh.ttc",
], 22)


def draw_centered(draw, text, font, y, fill, width=W):
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    x = (width - tw) // 2 - bbox[0]
    draw.text((x, y), text, font=font, fill=fill)


img = Image.new("RGB", (W, H), BG)
draw = ImageDraw.Draw(img)

# 顶部小英文 (eyebrow)
draw_centered(draw, "K N O W L E D G E   G A R D E N", sans_small, 100, TEXT_FAINT)

# 装饰线 (eyebrow 跟主标题之间)
draw.line([(W // 2 - 30, 165), (W // 2 + 30, 165)], fill=ACCENT, width=2)

# 主标题
draw_centered(draw, "个人知识库", serif, 215, TEXT)

# 副标题
draw_centered(draw, "5 个系列 · 50 章 · 约 137 分钟", sans, 405, TEXT_FAINT)

# 底部小标识
draw_centered(draw, "mishishi.github.io/knowledge-garden", sans_small, 540, TEXT_FAINT)

# 左下角 / 右下角 装饰小方块 (暗示 stack of books)
for i, color in enumerate([(91, 140, 133), (176, 137, 104), (108, 99, 255), (13, 148, 136), (194, 65, 12)]):
    x0 = 60 + i * 16
    draw.rectangle([(x0, H - 80), (x0 + 10, H - 40)], fill=color)

img.save(OUT, "PNG", optimize=True)
print(f"生成 {OUT} ({OUT.stat().st_size:,} bytes, {W}x{H})")
