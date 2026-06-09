#!/usr/bin/env python3
"""split_book_to_chapters.py — 书籍预处理：创建目录结构 + 复制图片 + 按章节拆分

整个工作流（Prepare → Split → Pipeline）:
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
  标准化文件名为: 第N章 名称.md（匹配 discover_chapters() 的 re 模式）。
  逐行扫描：不将整个文件读入内存，适合大文件处理。
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
# 检测是否为目录条目（带页码标记 ……N）
TOC_ENTRY_PATTERN = re.compile(r"第\s*\d+\s*章.*……\s*\d+\s*$")


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
# Phase 2: 按章节拆分（逐行扫描，不读入整个文件）
# =============================================================

def count_lines(filepath: str) -> int:
    """逐行统计文件总行数（不将文件读入内存）"""
    n = 0
    with open(filepath, 'rb') as f:
        for _ in f:
            n += 1
    return n


def discover_chapter_ranges(filepath: str) -> list[tuple[int, int, str, str]]:
    """扫描文件，返回 [(start_line, end_line, heading_text, chapter_num), ...]

    Lines are 0-indexed. end_line is exclusive (the next chapter's start).
    同一章节号出现多次时保留最后一次（正文版本优先于TOC版本）。
    单遍扫描：逐行读取，不将整个文件读入内存。
    """
    chapter_starts = []
    toc_start = None

    with open(filepath, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f):
            # 检测 ## 目录 标记
            if toc_start is None and re.match(r"^#{1,2}\s*目录\s*$", line.strip()):
                toc_start = i
            # 检测章节标题
            m = CHAPTER_PATTERN.match(line)
            if not m:
                m = CHAPTER_BARE_PATTERN.match(line)
            if m:
                text = m.group(1).strip()
                chapter_starts.append((i, text))

    if not chapter_starts:
        return []

    total_lines = count_lines(filepath)

    # 按章节号分组：优先保留内容版本（非TOC条目）
    by_number: dict[str, tuple[int, str]] = OrderedDict()
    for start, text in chapter_starts:
        m = CHAPTER_NUM_PATTERN.search(text)
        if m:
            ch_num = m.group(1)
            is_toc = bool(TOC_ENTRY_PATTERN.match(text))
            if ch_num in by_number:
                old_start, old_text = by_number[ch_num]
                old_is_toc = bool(TOC_ENTRY_PATTERN.match(old_text))
                if not is_toc and old_is_toc:  # 内容替换TOC
                    by_number[ch_num] = (start, text)
                elif is_toc and not old_is_toc:  # TOC不替换内容
                    pass
                else:  # 同类型保留最后
                    by_number[ch_num] = (start, text)
            else:
                by_number[ch_num] = (start, text)

    # 从TOC条目中收集章节完整标题，补全无标题的内容章节
    toc_titles = {}
    for start, text in chapter_starts:
        if TOC_ENTRY_PATTERN.match(text):
            m = CHAPTER_NUM_PATTERN.search(text)
            if m:
                cn = m.group(1)
                clean = re.sub(r'\s*……\s*\d+\s*$', '', text).strip()
                toc_titles[cn] = clean

    for ch_num in list(by_number.keys()):
        start, text = by_number[ch_num]
        has_name = bool(re.search(r'章\s+\S', text))
        if not has_name and ch_num in toc_titles:
            by_number[ch_num] = (start, toc_titles[ch_num])

    # 如果第一个内容章节不是第1章，从前言内容自动创建第1章
    first_content_line = None
    for start, text in chapter_starts:
        if not TOC_ENTRY_PATTERN.match(text) and CHAPTER_NUM_PATTERN.search(text):
            next_start = total_lines
            for s2, t2 in chapter_starts:
                if s2 > start:
                    next_start = s2
                    break
            span = next_start - start
            if span >= 100:
                first_content_line = start
                break

    if by_number:
        first_ch = min(by_number.keys(), key=lambda x: by_number[x][0])
        first_idx = int(first_ch)
        if first_idx > 1:
            first_start = by_number[first_ch][0]
            if toc_start is not None and (toc_start + 1) < first_start:
                ch1_title = toc_titles.get("1", "第1章 概述")
                by_number["1"] = (toc_start + 1, ch1_title)

    sorted_starts = sorted(by_number.items(), key=lambda x: int(x[1][0]))

    ranges = []
    items = list(sorted_starts)
    for j, (ch_num, (start, text)) in enumerate(items):
        if j + 1 < len(items):
            end = items[j + 1][1][0]
        else:
            end = total_lines
        ranges.append((start, end, text, ch_num))

    return ranges


def normalize_filename(heading_text: str) -> str:
    """标准化文件名: 第N章 名称.md（清理页码伪影）"""
    clean = re.sub(r'\s*……\s*\d*\s*$', '', heading_text)
    clean = re.sub(r'\s+\d+\s*$', '', clean)
    m = re.match(r'[#]*\s*第\s*(\d+)\s*章\s*(.*)', clean)
    if m:
        ch_num = m.group(1)
        ch_name = m.group(2).strip()
        ch_name = re.sub(r'\s*……\s*\d+\s*$', '', ch_name)
        ch_name = re.sub(r'\s+', ' ', ch_name)
        if ch_name:
            return f"第{ch_num}章 {ch_name}.md"
        else:
            return f"第{ch_num}章.md"
    safe = heading_text.lstrip('#').strip().replace('/', '／')
    return f"{safe}.md"


def split_book(
    book_path: str,
    output_dir: str,
    force: bool = False,
) -> list[dict]:
    """拆分整书为章节文件（逐章写入，不缓存全部内容到内存）"""
    os.makedirs(output_dir, exist_ok=True)

    if not os.path.isfile(book_path):
        print(f"[ERROR] 文件不存在: {book_path}")
        return []

    ranges = discover_chapter_ranges(book_path)
    if not ranges:
        print(f"[ERROR] 未检测到任何章节标题 ({book_path})")
        return []

    print(f"发现 {len(ranges)} 个章节（已消除 TOC 重复）:")

    results = []
    with open(book_path, 'r', encoding='utf-8') as f:
        all_lines = f.readlines()

    for start, end, heading_text, ch_num in ranges:
        chapter_lines = all_lines[start:end]
        fname = normalize_filename(heading_text)
        total_lines = len(chapter_lines)
        is_toc = bool(TOC_ENTRY_PATTERN.match(heading_text))

        # 跳过极小的TOC片段（<15行的纯目录子节列表）
        if total_lines < 15 and is_toc:
            print(f"  ⏭ 跳过（目录条目，仅 {total_lines} 行）: {fname}")
            results.append({"file": fname, "lines": total_lines, "ok": False})
            continue
        out_path = os.path.join(output_dir, fname)

        if os.path.exists(out_path) and not force:
            print(f"  ⚠ 跳过（文件已存在）: {fname}")
            results.append({"file": fname, "lines": total_lines, "ok": False})
            continue

        content = ''.join(chapter_lines).strip() + '\n'
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(content)

        print(f"  ✓ {fname} (行 {start+1}–{end}, {total_lines} 行)")
        results.append({"file": fname, "lines": total_lines, "ok": True})

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

    if args.raw_dir and args.split:
        md_files = [f for f in os.listdir(args.raw_dir) if f.endswith('.md') and os.path.isfile(os.path.join(args.raw_dir, f))]
        if len(md_files) == 1:
            book_md = os.path.join(args.raw_dir, md_files[0])
            print(f"\n自动拆分章节: {book_md}")
            split_book(book_md, os.path.join(book_dir, "20_正文"), force=args.force)
        elif len(md_files) > 1:
            print(f"\n⚠ raw 目录下多个 .md 文件，请手动指定")


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


def cmd_reconstruct(args):
    """从 content_list_v2.json 重建章节正文"""
    import json as _json, re as _re
    src_dir = os.path.join(args.wiki_root, "20_正文")
    if not os.path.isdir(src_dir):
        print(f"[ERROR] 20_正文 不存在: {src_dir}"); sys.exit(1)
    if not os.path.exists(args.v2_path):
        print(f"[ERROR] v2文件不存在: {args.v2_path}"); sys.exit(1)

    with open(args.v2_path, encoding='utf-8') as _f:
        _pages = _json.load(_f)

    def _ext(it):
        t, c = it.get("type",""), it.get("content",{})
        if t=="title" and isinstance(c,dict):
            pts=[tc.get("content","") for tc in c.get("title_content",[])]
            txt=" ".join(p for p in pts if p.strip())
            return f"{'#'*min(c.get('level',1),3)} {txt}","heading"
        if t=="paragraph" and isinstance(c,dict):
            pts=[pc.get("content","") for pc in c.get("paragraph_content",[]) if isinstance(pc,dict)]
            if pts: txt=" ".join(pts)
            if len(txt)>10: return txt,"body"
        return None,None

    pg_ch={}
    for pi,pg in enumerate(_pages):
        for it in pg:
            if it.get("type")=="page_header":
                for hc in it.get("content",{}).get("page_header_content",[]):
                    m=_re.search(r"第\s*(\d+)\s*章",hc.get("content",""))
                    if m: pg_ch[pi]=int(m.group(1))
    if not pg_ch: print("  ⚠ 未找到页眉章节信息"); return

    ch_pgs: dict[int,list[int]]={}
    for pi,ch in sorted(pg_ch.items()): ch_pgs.setdefault(ch,[]).append(pi)

    total=0; total_kb=0
    for ch in sorted(ch_pgs):
        pgs=ch_pgs[ch]; sp=min(pgs); ep=len(_pages)
        for c2 in sorted(ch_pgs):
            if c2>ch and ch_pgs[c2]: ep=ch_pgs[c2][0]; break
        lines=[]
        for pi in range(sp,ep):
            for it in _pages[pi]:
                txt,tt=_ext(it)
                if txt: lines.append(f"\n{txt}" if tt=="heading" else txt)
        body=_re.sub(r'^#+\s*$','',"\n\n".join(lines),flags=_re.MULTILINE).strip()
        if not body: continue

        fname=None
        for f in os.listdir(src_dir):
            if f.startswith(f"第{ch}章") and f.endswith(".md"): fname=f; break
        if not fname: fname=f"第{ch}章.md"
        fpath=os.path.join(src_dir,fname)
        old=os.path.getsize(fpath)//1024 if os.path.exists(fpath) else 0
        with open(fpath,"w",encoding='utf-8') as _f: _f.write(body+"\n")
        nw=os.path.getsize(fpath)//1024
        if nw>old*1.5: print(f"  ✅ 第{ch}章: {old}KB→{nw}KB")
        total+=1; total_kb+=nw
    print(f"\n完成: {total}章重建, 共{total_kb}KB")


def main():
    p = argparse.ArgumentParser(description="书籍预处理工具：创建目录 + 复制图片 + 拆分章节")
    sp = p.add_subparsers(dest="cmd", required=True)

    prep = sp.add_parser("prepare", help="创建书籍标准目录结构 + 复制图片")
    prep.add_argument("-w", "--wiki-root", required=True, help="书籍根目录（目标目录）")
    prep.add_argument("--raw-dir", help="raw 源文件目录（含 images/）")
    prep.add_argument("--split", action="store_true", help="目录创建后自动拆分章节")
    prep.add_argument("--force", action="store_true", help="覆盖已有章节文件")

    spl = sp.add_parser("split", help="按章节拆分整书 Markdown")
    spl.add_argument("book_path", help="整书 Markdown 文件路径")
    spl.add_argument("-o", "--output-dir", help="输出目录（20_正文/），优先级高于 -w")
    spl.add_argument("-w", "--wiki-root", help="书籍根目录（自动追加 20_正文/）")
    spl.add_argument("--force", action="store_true", help="覆盖已有文件")

    rec = sp.add_parser("reconstruct", help="从 content_list_v2.json 重建缺失章节正文")
    rec.add_argument("-w", "--wiki-root", required=True, help="书籍根目录")
    rec.add_argument("--v2-path", required=True, help="content_list_v2.json 路径")

    args = p.parse_args()

    if args.cmd == "prepare":
        cmd_prepare(args)
    elif args.cmd == "split":
        cmd_split(args)
    elif args.cmd == "reconstruct":
        cmd_reconstruct(args)


if __name__ == "__main__":
    main()
