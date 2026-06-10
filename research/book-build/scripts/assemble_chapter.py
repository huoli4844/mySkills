#!/usr/bin/env python3
"""
assemble_chapter.py — 章节组装脚本。

将多节独立 .md 文件按大纲顺序组装为完整章文件，
并统一重排全部编号系统（公式/图/例/表）。

用法:
    python3 scripts/assemble_chapter.py output/前/ --out output/第8章-屏蔽技术.md --chapter 8
    python3 scripts/assemble_chapter.py output/前/ --out output/第8章-屏蔽技术.md --dry-run
"""

import re
import sys
import os
import glob
import argparse
import json
from pathlib import Path
from collections import Counter

# Try to load config; fallback to defaults
try:
    from book_config import Config
    cfg = Config()
    CHAPTER = cfg.textbook_name
except ImportError:
    cfg = None
    CHAPTER = None


def next_available_path(base_dir, chapter_num, title_hint=""):
    """根据输入目录中的文件列表推断输出路径。"""
    files = sorted(glob.glob(os.path.join(base_dir, "*.md")))
    if not files:
        slug = title_hint or f"第{chapter_num}章"
        return os.path.join(base_dir, f"第{chapter_num}章-{slug}.md")
    # 取第一个文件的目录
    return os.path.join(base_dir, f"第{chapter_num}章-组装.md")


def assemble(input_dir, chapter_num, output_path, dry_run=False, keep_sections=False):
    """将 input_dir 下的所有 .md 按文件名顺序组装。"""
    files = sorted(glob.glob(os.path.join(input_dir, "*.md")))
    if not files:
        print(f"❌ 输入目录无 .md 文件: {input_dir}")
        sys.exit(1)

    print(f"📦 组装 {len(files)} 个文件 → {output_path}")
    sections = []

    for f in files:
        content = open(f, "r", encoding="utf-8").read()
        # 剥离 YAML frontmatter
        content = re.sub(r"^---\n.*?\n---\n", "", content, flags=re.DOTALL)
        sections.append((os.path.basename(f), content))
        print(f"  + {os.path.basename(f)} ({len(content)} 字符)")

    # 拼接
    header = f"---\ntitle: 第{chapter_num}章\nassembled: true\nsource_files: {len(files)}\n---\n\n"
    body = "\n\n".join(c for _, c in sections)
    text = header + body

    if dry_run:
        print(f"\n[DRY RUN] 组装后总字符: {len(text)}")
        print(f"[DRY RUN] 文件数: {len(files)}")
        return True

    # 写入
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    open(output_path, "w", encoding="utf-8").write(text)

    print(f"\n✅ 已写入: {output_path} ({len(text)} 字符)")

    # 清理临时文件
    if not keep_sections:
        print(f"🧹 清理临时文件 ({len(files)} 个)...")
        for f in files:
            os.remove(f)
        print(f"✅ 已清理")

    # 提示下一步
    print(f"\n👉 下一步: python3 scripts/renumber.py \"{output_path}\"")
    print(f"👉 下一步: python3 scripts/post_generation_check.py \"{output_path}\" --fix --verbose")
    return True


def main():
    parser = argparse.ArgumentParser(description="章节组装脚本")
    parser.add_argument("input_dir", help="输入目录（含各节 .md 文件）")
    parser.add_argument("--out", "-o", help="输出文件路径")
    parser.add_argument("--chapter", "-c", type=int, required=True, help="章号")
    parser.add_argument("--dry-run", "-n", action="store_true", help="预览模式")
    parser.add_argument("--keep-sections", action="store_true", help="保留临时文件")
    args = parser.parse_args()

    output_path = args.out or next_available_path(args.input_dir, args.chapter)
    assemble(args.input_dir, args.chapter, output_path, args.dry_run, args.keep_sections)


if __name__ == "__main__":
    main()
