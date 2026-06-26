#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Edge TTS 生成脚本
================
为每个章节生成 MP3 朗读音频（使用 Microsoft Edge 神经语音）

用法:
  python tools/build_tts.py                    # 生成所有缺失的音频
  python tools/build_tts.py --book cn-codex    # 只生成指定 book
  python tools/build_tts.py --force            # 强制重新生成（覆盖已存在）
  python tools/build_tts.py --voice zh-CN-XiaoxiaoNeural

依赖:
  pip install edge-tts

输出:
  assets/audio/{book}/{chapter}.mp3
"""
import argparse
import asyncio
import re
import sys
from pathlib import Path

import edge_tts

# 默认配置
DEFAULT_VOICE = "zh-CN-XiaoxiaoNeural"  # 温暖女声，新闻/小说
DEFAULT_RATE = "+0%"  # 语速
DEFAULT_VOLUME = "+0%"

# 清洗 Markdown / HTML → 纯文本
def clean_markdown(md: str) -> str:
    # 去除代码块
    md = re.sub(r'```[\s\S]*?```', '', md)
    # 去除行内代码
    md = re.sub(r'`[^`]+`', '', md)
    # 去除 HTML 标签
    md = re.sub(r'<[^>]+>', '', md)
    # 去除图片 / 链接保留文本
    md = re.sub(r'!\[([^\]]*)\]\([^)]+\)', r'\1', md)
    md = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', md)
    # 去除标题符号
    md = re.sub(r'^#+\s*', '', md, flags=re.MULTILINE)
    # 去除加粗 / 斜体
    md = re.sub(r'\*\*([^*]+)\*\*', r'\1', md)
    md = re.sub(r'\*([^*]+)\*', r'\1', md)
    # 去除引用 / 列表符号
    md = re.sub(r'^>\s*', '', md, flags=re.MULTILINE)
    md = re.sub(r'^\s*[-*+]\s+', '', md, flags=re.MULTILINE)
    md = re.sub(r'^\s*\d+\.\s+', '', md, flags=re.MULTILINE)
    # 去除水平线
    md = re.sub(r'^---+$', '', md, flags=re.MULTILINE)
    # 去除表格分隔符
    md = re.sub(r'^\|[-:|\s]+\|$', '', md, flags=re.MULTILINE)
    md = re.sub(r'\|', ' ', md)
    # 多余空行
    md = re.sub(r'\n{3,}', '\n\n', md)
    return md.strip()


def collect_chapters(books_dir: Path, target_book: str = None):
    """收集所有需要生成 TTS 的章节"""
    chapters = []
    for book_dir in sorted(books_dir.iterdir()):
        if not book_dir.is_dir():
            continue
        if target_book and book_dir.name != target_book:
            continue
        # 检查 _meta.json
        meta_path = book_dir / "_meta.json"
        if not meta_path.exists():
            continue
        for chap_dir in sorted(book_dir.iterdir()):
            if not chap_dir.is_dir():
                continue
            readme = chap_dir / "README.md"
            if not readme.exists():
                continue
            chapters.append((book_dir.name, chap_dir.name, readme))
    return chapters


async def generate_one(book: str, chap: str, md_path: Path, out_path: Path,
                       voice: str, rate: str, volume: str, force: bool):
    """生成单个章节的 MP3"""
    if out_path.exists() and not force:
        return f"skip  {book}/{chap}.mp3"

    text = md_path.read_text(encoding="utf-8")
    text = clean_markdown(text)
    if not text:
        return f"empty {book}/{chap}"

    # 限制单次合成长度（edge-tts 限制 ~10 分钟）
    MAX_CHARS = 5000
    if len(text) > MAX_CHARS * 2:
        # 分段：按段落切分后合并
        chunks = []
        current = ""
        for para in text.split("\n\n"):
            if len(current) + len(para) > MAX_CHARS and current:
                chunks.append(current.strip())
                current = para
            else:
                current += "\n\n" + para if current else para
        if current:
            chunks.append(current.strip())
        text = " ... ".join(chunks[:6])  # 最多 6 段

    out_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        communicate = edge_tts.Communicate(text, voice, rate=rate, volume=volume)
        await communicate.save(str(out_path))
        size_kb = out_path.stat().st_size // 1024
        return f"ok    {book}/{chap}.mp3 ({size_kb}KB, {len(text)}字)"
    except Exception as e:
        return f"FAIL  {book}/{chap}: {e}"


async def main():
    parser = argparse.ArgumentParser(description="Edge TTS 章节朗读生成")
    parser.add_argument("--book", help="只生成指定 book (slug)")
    parser.add_argument("--force", action="store_true", help="强制重新生成")
    parser.add_argument("--voice", default=DEFAULT_VOICE, help=f"语音（默认 {DEFAULT_VOICE}）")
    parser.add_argument("--rate", default=DEFAULT_RATE, help=f"语速（默认 {DEFAULT_RATE}）")
    parser.add_argument("--volume", default=DEFAULT_VOLUME, help=f"音量（默认 {DEFAULT_VOLUME}）")
    parser.add_argument("--concurrency", type=int, default=4, help="并发数（默认 4）")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    books_dir = repo_root / "books"
    audio_dir = repo_root / "assets" / "audio"

    chapters = collect_chapters(books_dir, args.book)
    if not chapters:
        print(f"未找到章节 (book={args.book})")
        return

    print(f"目标: {len(chapters)} 个章节")
    print(f"语音: {args.voice}  语速: {args.rate}  音量: {args.volume}")
    print(f"输出: {audio_dir.relative_to(repo_root)}")
    print("-" * 60)

    sem = asyncio.Semaphore(args.concurrency)

    async def task(book, chap, md_path):
        out = audio_dir / book / f"{chap}.mp3"
        async with sem:
            return await generate_one(book, chap, md_path, out,
                                      args.voice, args.rate, args.volume, args.force)

    tasks = [task(b, c, p) for b, c, p in chapters]
    results = await asyncio.gather(*tasks)

    ok = sum(1 for r in results if r.startswith("ok"))
    skip = sum(1 for r in results if r.startswith("skip"))
    fail = sum(1 for r in results if r.startswith("FAIL"))
    empty = sum(1 for r in results if r.startswith("empty"))

    for r in results:
        print(r)

    print("-" * 60)
    print(f"完成: 生成 {ok} · 跳过 {skip} · 失败 {fail} · 空 {empty}")
    if fail:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
