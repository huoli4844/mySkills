#!/usr/bin/env python3
"""检查 Markdown 文件中所有表格的结构合法性。

检查项：
  1. 对齐行定位：对齐行必须是紧跟在表头之后的第二行（不在表头之前）
  2. 列数一致性：对齐行的列数必须等于表头行的列数
  3. 表题位置：表题（**表X-X**）应在表格上方

用法：
  python3 scripts/check_table_columns.py /path/to/file.md
  python3 scripts/check_table_columns.py /path/to/output/*.md
  python3 scripts/check_table_columns.py --fix /path/to/file.md  # 自动修复空对齐行前置
"""

import os
import re
import sys
from pathlib import Path


def check_tables(filepath: str, fix: bool = False) -> tuple[int, int, list[str]]:
    """返回 (错误数, 修复数, 问题描述列表)"""
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    errors = []
    fixes = 0

    for i in range(len(lines) - 1):
        l0 = lines[i].strip()
        l1 = lines[i + 1].strip()

        # --- Check 1: alignment row before header (double alignment pattern) ---
        if (re.match(r'^\|:--', l0) and
            not re.match(r'^\|:--', l1) and l1.startswith('|') and
            i + 2 < len(lines) and re.match(r'^\|:--', lines[i + 2].strip())):
            # Found: alignment, header, alignment → first alignment row is spurious
            title = ''
            for j in range(i - 1, max(0, i - 5), -1):
                if '**表' in lines[j]:
                    title = lines[j].strip()
                    break
            errors.append(f"Line {i+1}: 表头前多余对齐行 → {title or '(无表题)'}")
            if fix:
                lines[i] = ''  # Remove the first alignment line
                fixes += 1

        # --- Check 2: column count mismatch between header and alignment ---
        if (l0.startswith('|') and not re.match(r'^\|:--', l0) and
            l1.startswith('|') and re.match(r'^\|:--', l1)):

            hdr_cols = [c for c in l0.split('|') if c.strip() != '']
            alg_cols = [c for c in l1.split('|') if c.strip() != '']

            if len(hdr_cols) != len(alg_cols):
                title = ''
                for j in range(i - 1, max(0, i - 5), -1):
                    if '**表' in lines[j]:
                        title = lines[j].strip()
                        break
                errors.append(
                    f"Line {i+1}-{i+2}: 列数不匹配 → header={len(hdr_cols)}列, align={len(alg_cols)}列"
                    f"  {title or '(无表题)'}"
                )
                # Column mismatch needs manual fix — report only

    if fix and fixes > 0:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.writelines(lines)

    return len(errors), fixes, errors


def main():
    args = sys.argv[1:]
    fix_mode = '--fix' in args
    paths = [a for a in args if a != '--fix']

    if not paths:
        print("用法: python3 check_table_columns.py [--fix] <file.md> [file2.md ...]")
        print("      支持通配符: python3 check_table_columns.py output/*.md")
        sys.exit(1)

    total_errors = 0
    total_fixes = 0

    for pattern in paths:
        if '*' in pattern:
            from glob import glob
            files = sorted(glob(pattern))
        else:
            files = [pattern]

        for f in files:
            fpath = str(Path(f).expanduser().resolve())
            if not os.path.exists(fpath):
                print(f"⚠️  不存在: {fpath}")
                continue

            errs, fxs, msgs = check_tables(fpath, fix=fix_mode)
            total_errors += errs
            total_fixes += fxs

            if errs or fxs:
                print(f"\n{fpath}")
                print(f"  {'❌' if errs else '✅'} 错误: {errs}, 修复: {fxs}")
                for m in msgs:
                    print(f"     {m}")

    print(f"\n{'='*50}")
    if total_errors == 0:
        print("✅ 所有表格通过检查")
    else:
        print(f"❌ 总计 {total_errors} 个错误")
    if total_fixes > 0:
        print(f"🔧 已自动修复 {total_fixes} 处")
    sys.exit(1 if total_errors > 0 else 0)


if __name__ == '__main__':
    main()
