#!/usr/bin/env python3
"""
renumber_cross_file.py — 跨文件编号重排脚本。

在同一章有多个文件（如正文+案例+实验）时，确保公式/图/例/表编号
在所有文件中连续分配，无重叠无跳跃。

用法:
    python3 scripts/renumber_cross_file.py output/ --chapter 8
    # 扫描 output/ 下所有包含 "第8章" 或 "案例8-" 的文件
    # 统一分配编号：正文从 8-1 到 8-100，案例从 8-101 到 8-200

    python3 scripts/renumber_cross_file.py file1.md file2.md --chapter 8
    # 指定文件列表

    python3 scripts/renumber_cross_file.py output/ --dry-run
    # 预览模式：只报告编号冲突不修改
"""

import re
import sys
import os
import glob
import argparse
from collections import Counter


def collect_files(base_path, chapter_num):
    """收集指定章号的所有相关文件。"""
    files = []
    patterns = [
        os.path.join(base_path, f"第{chapter_num}章*.md"),
        os.path.join(base_path, f"案例{chapter_num}-*.md"),
        os.path.join(base_path, f"实验{chapter_num}_*.md"),
        os.path.join(base_path, f"案例{chapter_num}_*.md"),
        os.path.join(base_path, "output", f"第{chapter_num}章*.md"),
    ]
    for pat in patterns:
        files.extend(glob.glob(pat))
    # 去重并按文件名排序
    return sorted(set(files))


def _find_all_tags(text, pattern):
    """找到所有模式匹配及其位置。"""
    matches = []
    for m in re.finditer(pattern, text):
        matches.append({
            "full": m.group(),
            "num_str": m.group(1),
            "ch": m.group(1).split("-")[0],
            "num": int(m.group(1).split("-")[1]),
            "pos": m.start(),
        })
    return matches


def analyze(files, chapter_num):
    """分析并报告当前编号状态。"""
    ch = str(chapter_num)
    formula_all = []
    fig_all = []
    example_all = []
    table_all = []

    for f in files:
        content = open(f, "r", encoding="utf-8").read()
        formula_all.extend([
            (f, m["num_str"], m["num"])
            for m in _find_all_tags(content, r"tag\{(\d+-\d+)\}")
        ])
        fig_all.extend([
            (f, m.group())
            for m in re.finditer(r"\*图(\d+-\d+)", content)
        ])
        example_all.extend([
            (f, m.group())
            for m in re.finditer(r"\*\*例(\d+-\d+)", content)
        ])
        table_all.extend([
            (f, m.group())
            for m in re.finditer(r"\*\*表(\d+-\d+)", content)
        ])

    # 检查重复
    formula_nums = [n[1] for n in formula_all]
    fig_nums = [n[1] for n in fig_all]
    example_nums = [n[1] for n in example_all]
    table_nums = [n[1] for n in table_all]

    dup_formula = {k: v for k, v in Counter(formula_nums).items() if v > 1}
    dup_fig = {k: v for k, v in Counter(fig_nums).items() if v > 1}
    dup_example = {k: v for k, v in Counter(example_nums).items() if v > 1}
    dup_table = {k: v for k, v in Counter(table_nums).items() if v > 1}

    print(f"📊 跨文件编号分析 (第{ch}章, {len(files)} 文件)")
    print(f"  公式: {len(formula_all)} 个, 重复: {'❌ ' + str(dup_formula) if dup_formula else '✅ 无'}")
    print(f"  图注: {len(fig_all)} 个, 重复: {'❌ ' + str(dup_fig) if dup_fig else '✅ 无'}")
    print(f"  例题: {len(example_all)} 个, 重复: {'❌ ' + str(dup_example) if dup_example else '✅ 无'}")
    print(f"  表注: {len(table_all)} 个, 重复: {'❌ ' + str(dup_table) if dup_table else '✅ 无'}")

    return {
        "formula": formula_all,
        "fig": fig_all,
        "example": example_all,
        "table": table_all,
        "dup_formula": dup_formula,
        "dup_fig": dup_fig,
        "dup_example": dup_example,
        "dup_table": dup_table,
        "files": files,
    }


def fix_cross_file(files, chapter_num, offset=0, dry_run=False):
    """统一重排跨文件编号。"""
    ch = str(chapter_num)

    for f in files:
        content = open(f, "r", encoding="utf-8").read()
        original = content

        # 公式 tags: 替换所有 tag{ch-XX} 为 tag{ch-NNN}
        tags = _find_all_tags(content, r"\\{0,2}tag\{" + ch + r"-(\d+)\}")
        if not tags:
            continue

        counter = offset + 1
        for t in tags:
            content = content[: t["pos"]] + f"\\tag{{{ch}-{counter}}}" + content[t["pos"] + len(t["full"]):]
            counter += 1
            offset += 1

        if dry_run:
            print(f"  [DRY RUN] {os.path.basename(f)}: {len(tags)} 个公式 → ch{ch} 偏移后")
            continue

        if content != original:
            open(f, "w", encoding="utf-8").write(content)
            print(f"  ✅ {os.path.basename(f)}: {len(tags)} 个公式重排")

    return offset


def main():
    parser = argparse.ArgumentParser(description="跨文件编号重排")
    parser.add_argument("path", help="文件或目录路径")
    parser.add_argument("--chapter", "-c", type=int, required=True, help="章号")
    parser.add_argument("--offset", type=int, default=0, help="起始偏移（默认0=文件内重排）")
    parser.add_argument("--dry-run", "-n", action="store_true", help="预览模式")
    parser.add_argument("--fix", action="store_true", help="执行修复")
    args = parser.parse_args()

    if os.path.isdir(args.path):
        files = collect_files(args.path, args.chapter)
    else:
        files = sorted(glob.glob(args.path) or [args.path])

    if not files:
        print(f"❌ 未找到文件: {args.path}")
        sys.exit(1)

    print(f"📂 {len(files)} 个文件")

    if args.dry_run or not args.fix:
        analyze(files, args.chapter)
        if not args.fix:
            print("\n💡 使用 --fix 执行修复，使用 --dry-run 仅预览")
            return

    fix_cross_file(files, args.chapter, offset=args.offset, dry_run=args.dry_run)

    if not args.dry_run:
        print("\n✅ 完成。运行验证:")
        print(f"  python3 -c \"import re; c=open(...).read(); tags=re.findall(r'tag\\{{\\d+-\\d+\\}}',c); print(f'OK: {{len(tags)}}')\"")


if __name__ == "__main__":
    main()
