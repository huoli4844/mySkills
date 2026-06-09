#!/usr/bin/env python3
"""split_book_to_chapters.py — 书籍预处理：创建目录结构 + 复制图片 + 按章节拆分

整个工作流（Prepare → Split → Pipeline）：
  1. prepare: 创建 book_dir 的标准目录结构 + 复制图片
  2. split:   从整书 md 按章节拆分为 20_正文/ 独立文件
  3. 然后走 domain-wiki 标准 pipeline

用法:
  # 完整准备流程（创建目录 + 复制图片 + 拆分章节）
  python3 split_book_to_chapters.py prepare \
    --raw-dir <raw/书籍名/> \
    -w <book_dir>

  # 仅拆分章节（假设目录和图片已准备好）
  python3 split_book_to_chapters.py split <whole_book.md> -w <book_dir>

设计说明:
  自动检测章节标题: # 或 ## 开头 + 第N章 模式。
  自动消除 TOC 重复：如果同一章节号出现两次（TOC + 正文），只保留正文版本。
  标准化文件名为: 第N章 章节名.md（匹配 discover_chapters() 的 re 模式）。
"""

import argparse
import os
import re
import shutil
import sys
from collections import OrderedDict


# ── 标准书籍目录结构 ──
BOOK_DIRS = [
    "10_总揽",
    "20_正文",
    "20_正文/images",
    "30_核心概念",
    "40_知识要素",
    "50_知识点",
    "60_技能点",
    "70_应用场景",
    "80_实体",
    "90_习题",
    "90_习题/解答",
]

# ── 章节标题检测模式 ──
CHAPTER_PATTERN = re.compile(r"^(?:#{1,2})\s*(第\s*\d+\s*章\s*.*?)(?:\s*)$")
CHAPTER_NUM_PATTERN = re.compile(r"第\s*(\d+)\s*章")
# 无#前缀的章节标题（如 "第6章 电缆及连接器的设计 ..."）
CHAPTER_BARE_PATTERN = re.compile(r"^(第\s*\d+\s*章\s*.*?)(?:\s*)$")


# =============================================================
# Phase 1: 创建目录 + 复制图片
# =============================================================

def prepare_book(
    book_dir: str,
    raw_dir: str | None = None,
) -> dict:
    """创建书籍标准目录结构，并可选复制图片。

    Args:
        book_dir: 书籍根目录
        raw_dir:  raw 目录下的原始文件目录（含 images/）

    Returns:
        {"dirs_created": int, "images_copied": int}
    """
    created = 0
    for d in BOOK_DIRS:
        path = os.path.join(book_dir, d)
        os.makedirs(path, exist_ok=True)
        created += 1
        print(f"  ✓ {d}/")

    # 复制图片
    copied = 0
    if raw_dir:
        src_images = os.path.join(raw_dir, "images")
        dst_images = os.path.join(book_dir, "20_正文", "images")
        if os.path.isdir(src_images):
            for fname in os.listdir(src_images):
                src = os.path.join(src_images, fname)
                dst = os.path.join(dst_images, fname)
                if os.path.isfile(src) and not os.path.exists(dst):
                    shutil.copy2(src, dst)
                    copied += 1
            total = len(os.listdir(dst_images))
            print(f"  ✓ 图片复制: {copied} 新复制, 共 {total} 个文件")
        else:
            print(f"  ⚠ 未找到图片目录: {src_images}")

    return {"dirs_created": created, "images_copied": copied}


# =============================================================
# Phase 2: 按章节拆分
# =============================================================

def discover_chapter_ranges(filepath: str) -> list[tuple[int, int, str, str]]:
    """扫描文件，返回 [(start_line, end_line, heading_text, chapter_num), ...]

    Lines are 0-indexed. end_line is exclusive (the next chapter's start).
    如果同一章节号出现多次（TOC + 正文），只保留最后一次（正文版本）。
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    chapter_starts = []
    for i, line in enumerate(lines):
        m = CHAPTER_PATTERN.match(line)
        if not m:
            m = CHAPTER_BARE_PATTERN.match(line)
        if m:
            text = m.group(1).strip()
            chapter_starts.append((i, text))

    if not chapter_starts:
        return []

    # 按章节号分组，保留最后一个（正文版本）
    by_number: dict[str, tuple[int, str]] = OrderedDict()
    for start, text in chapter_starts:
        m = CHAPTER_NUM_PATTERN.search(text)
        if m:
            ch_num = m.group(1)
            by_number[ch_num] = (start, text)

    sorted_starts = sorted(by_number.items(), key=lambda x: int(x[1][0]))

    ranges = []
    items = list(sorted_starts)
    for j, (ch_num, (start, text)) in enumerate(items):
        if j + 1 < len(items):
            end = items[j + 1][1][0]
        else:
            end = len(lines)
        ranges.append((start, end, text, ch_num))

    return ranges


def normalize_filename(heading_text: str) -> str:
    """标准化文件名: 第N章 名称.md"""
    m = re.match(r'[#]*\s*第\s*(\d+)\s*章\s*(.*)', heading_text)
    if m:
        ch_num = m.group(1)
        ch_name = m.group(2).strip()
        ch_name = re.sub(r'\s*……\s*\d+\s*$', '', ch_name)
        ch_name = re.sub(r'\s+', ' ', ch_name)
        return f"第{ch_num}章 {ch_name}.md"
    safe = heading_text.lstrip('#').strip().replace('/', '／')
    return f"{safe}.md"


def split_book(
    book_path: str,
    output_dir: str,
    force: bool = False,
) -> list[dict]:
    """拆分整书为章节文件。"""
    os.makedirs(output_dir, exist_ok=True)

    if not os.path.isfile(book_path):
        print(f"[ERROR] 文件不存在: {book_path}")
        return []

    ranges = discover_chapter_ranges(book_path)
    if not ranges:
        print(f"[ERROR] 未检测到任何章节标题 ({book_path})")
        print("  支持的格式: # 第1章 xxx 或 ## 第N章 xxx")
        return []

    print(f"发现 {len(ranges)} 个章节（已消除 TOC 重复）:")

    results = []
    with open(book_path, 'r', encoding='utf-8') as f:
        all_lines = f.readlines()

    for start, end, heading_text, ch_num in ranges:
        chapter_lines = all_lines[start:end]
        fname = normalize_filename(heading_text)
        out_path = os.path.join(output_dir, fname)

        if os.path.exists(out_path) and not force:
            print(f"  ⚠ 跳过（文件已存在）: {fname}")
            results.append({"file": fname, "lines": len(chapter_lines), "ok": False})
            continue

        content = ''.join(chapter_lines).strip() + '\n'
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(content)

        print(f"  ✓ {fname} (行 {start+1}–{end}, {len(chapter_lines)} 行)")
        results.append({"file": fname, "lines": len(chapter_lines), "ok": True})

    return results


# =============================================================
# CLI
# =============================================================

def cmd_prepare(args):
    """执行 prepare 子命令"""
    book_dir = args.wiki_root
    if not book_dir:
        print("[ERROR] prepare 需指定 -w/--wiki-root")
        sys.exit(1)

    os.makedirs(book_dir, exist_ok=True)
    print(f"准备书籍目录: {book_dir}")
    result = prepare_book(book_dir, raw_dir=args.raw_dir)

    # 如果有 raw_dir 且指定了自动拆分
    if args.raw_dir and args.split:
        # 自动寻找书籍 md
        md_files = [f for f in os.listdir(args.raw_dir) if f.endswith('.md') and os.path.isfile(os.path.join(args.raw_dir, f))]
        if len(md_files) == 1:
            book_md = os.path.join(args.raw_dir, md_files[0])
            print(f"\n自动拆分章节: {book_md}")
            split_book(book_md, os.path.join(book_dir, "20_正文"), force=args.force)
        elif len(md_files) > 1:
            print(f"\n⚠ raw 目录下多个 .md 文件，请手动指定: python3 split_book_to_chapters.py split <file.md> -w <book_dir>")


def cmd_split(args):
    """执行 split 子命令"""
    output_dir = args.output_dir
    if not output_dir and args.wiki_root:
        output_dir = os.path.join(args.wiki_root, "20_正文")
    if not output_dir:
        print("[ERROR] 请指定 -o/--output-dir 或 -w/--wiki-root")
        sys.exit(1)

    results = split_book(args.book_path, output_dir, force=args.force)
    if not results:
        sys.exit(1)

    ok = sum(1 for r in results if r.get("ok"))
    skipped = sum(1 for r in results if not r.get("ok"))
    print(f"\n完成: {ok} 章节已写入, {skipped} 跳过")
    print(f"输出目录: {output_dir}/")


def main():
    p = argparse.ArgumentParser(description="书籍预处理工具：创建目录 + 复制图片 + 拆分章节")
    sp = p.add_subparsers(dest="cmd", required=True)

    # prepare 子命令
    prep = sp.add_parser("prepare", help="创建书籍标准目录结构 + 复制图片")
    prep.add_argument("-w", "--wiki-root", required=True, help="书籍根目录（目标目录）")
    prep.add_argument("--raw-dir", help="raw 源文件目录（含 images/）")
    prep.add_argument("--split", action="store_true", help="目录创建后自动拆分章节")
    prep.add_argument("--force", action="store_true", help="覆盖已有章节文件")

    # split 子命令
    spl = sp.add_parser("split", help="按章节拆分整书 Markdown")
    spl.add_argument("book_path", help="整书 Markdown 文件路径")
    spl.add_argument("-o", "--output-dir", help="输出目录（20_正文/），优先级高于 -w")
    spl.add_argument("-w", "--wiki-root", help="书籍根目录（自动追加 20_正文/）")
    spl.add_argument("--force", action="store_true", help="覆盖已有文件")

    args = p.parse_args()

    if args.cmd == "prepare":
        cmd_prepare(args)
    elif args.cmd == "split":
        cmd_split(args)


if __name__ == "__main__":
    main()
