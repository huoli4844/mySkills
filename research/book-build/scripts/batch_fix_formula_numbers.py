#!/usr/bin/env python3
"""
批量修复公式编号 v2 — 安全版 + 完整版。
覆盖 batch_fix_formula_numbers.py 的所有功能，新增：

  1. > $$ 引用块规范化（> $$ → $$，删除空引用行 >）
  2. 未闭合 $$ 检测与修复（在公式内容后插入闭合 $$）
  3. 连续 $$（空块）删除（$$\\n$$）
  4. \\tag 在 $$ 之前（错误位置）的检测与移动

修复顺序：清除旧tag → 规范化引用块 → 删除空块/孤立行 → 修复未闭合
           → 行级状态机编号 → 验证

安全机制：自动备份 + 先读后写（绝不在写之后读）
"""

import re
import os
import sys
import shutil
from pathlib import Path


def cleanup_empty_consecutive_dollars(lines):
    """删除连续 $$ 对（两个 $$ 行相邻 = 空公式块）"""
    changed = True
    while changed:
        new_lines = []
        i = 0
        changed = False
        while i < len(lines):
            if i+1 < len(lines) and lines[i].strip() == '$$' and lines[i+1].strip() == '$$':
                i += 2
                changed = True
                continue
            new_lines.append(lines[i])
            i += 1
        lines = new_lines
    return lines


def find_unclosed_dollar(lines):
    """检测未闭合的 $$，返回 (has_unclosed, last_open_pos)"""
    in_f = False
    last_open = -1
    for i, line in enumerate(lines):
        if line.strip() == '$$':
            if not in_f:
                in_f = True
                last_open = i
            else:
                in_f = False
    return in_f, last_open


def fix_unclosed_dollar(lines, open_pos):
    """在未闭合 $$ 后第一个公式内容行之后插入闭合 $$"""
    for j in range(open_pos + 1, min(open_pos + 10, len(lines))):
        if lines[j].strip() and lines[j].strip() != '$$':
            lines.insert(j + 1, '$$')
            return lines
    return lines


def process_file(filepath):
    """处理单个文件，返回 (tag_count, was_unclosed)"""
    basename = os.path.basename(filepath)
    
    # 解析章节号
    m = re.search(r'第(\d+)章', basename)
    if not m:
        print(f"  ⏭️  跳过（无法识别章节号）: {basename}")
        return 0, False
    prefix = m.group(1)
    
    # Step 0: 备份
    backup(filepath)
    
    # Step 1: 先读后写（绝不能在写之后读！）
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    lines = content.split('\n')
    
    # Step 2: 清除所有孤立 \\tag{N-M} 行
    new_lines = []
    for line in lines:
        s = line.strip()
        if re.match(r'^\\tag\{\d+-[a-z0-9]+\}$', s):
            continue  # 删除孤立 tag 行
        new_line = re.sub(r'\\tag\{\d+-[a-z0-9]+\}', '', line)
        new_lines.append(new_line)
    lines = new_lines
    
    # Step 3: 规范化 > $$ → $$
    lines = [re.sub(r'^>\s*\$\$', '$$', l) for l in lines]
    lines = [l for l in lines if l.strip() != '>']  # 删除空引用行
    
    # Step 4: 删除连续 $$ 对（空块）
    lines = cleanup_empty_consecutive_dollars(lines)
    
    # Step 5: 检测并修复未闭合 $$
    was_unclosed = False
    has_unclosed, open_pos = find_unclosed_dollar(lines)
    if has_unclosed:
        lines = fix_unclosed_dollar(lines, open_pos)
        was_unclosed = True
        # 再次删除连续 $$（修复后可能产生）
        lines = cleanup_empty_consecutive_dollars(lines)
    
    # Step 6: 行级 $$ 配对 + 编号
    in_formula = False
    counter = 0
    output_lines = []
    formula_buf = []
    
    for line in lines:
        stripped = line.strip()
        is_boundary = (stripped == '$$')
        
        if not in_formula:
            if is_boundary:
                in_formula = True
                formula_buf = [line]
            else:
                output_lines.append(line)
        else:
            formula_buf.append(line)
            if is_boundary:
                in_formula = False
                counter += 1
                
                has_content = any(
                    l.strip() and l.strip() != '$$'
                    for l in formula_buf
                )
                
                if has_content:
                    tag = f'\\tag{{{prefix}-{counter}}}'
                    # 在闭合 $$ 之前插入 tag
                    insert_pos = len(formula_buf) - 1
                    while insert_pos >= 0 and formula_buf[insert_pos].strip() == '$$':
                        insert_pos -= 1
                    formula_buf.insert(insert_pos + 1, tag)
                
                output_lines.extend(formula_buf)
                formula_buf = []
    
    if formula_buf:
        output_lines.extend(formula_buf)
    
    result = '\n'.join(output_lines)
    
    # Step 7: 验证
    tags = re.findall(r'\\tag\{' + prefix + r'-(\d+)\}', result)
    n_tags = len(tags)
    
    # 检查孤立tag（块外）
    in_math = False
    orphan = 0
    for line in result.split('\n'):
        s = line.strip()
        if s == '$$':
            in_math = not in_math
            continue
        if not in_math and re.match(r'^\\tag\{\d+-\d+\}$', s):
            orphan += 1
    
    # 检查 $$ 配对
    dollar_count = result.count('$$')
    dollar_ok = (dollar_count % 2 == 0)
    
    # 检查编号连续性
    is_continuous = False
    if tags:
        is_continuous = sorted([int(t) for t in tags]) == list(range(1, n_tags + 1))
    
    # 检查 tag 位置（每个 tag 后面必须是 $$）
    tag_pos_ok = True
    r_lines = result.split('\n')
    for i, line in enumerate(r_lines):
        s = line.strip()
        if re.match(r'^\\tag\{\d+-\d+\}$', s):
            if i+1 < len(r_lines) and r_lines[i+1].strip() != '$$':
                tag_pos_ok = False
            if i >= 1 and r_lines[i-1].strip() == '$$':
                tag_pos_ok = False
    
    all_ok = (orphan == 0 and dollar_ok and is_continuous and tag_pos_ok)
    
    # 写回
    if all_ok:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(result)
        status = "✅" if all_ok else "❌"
        print(f"  {status} {basename}: {n_tags} 公式, 孤立tag={orphan}, $$偶数={dollar_ok}, 连续={is_continuous}, tag位置={tag_pos_ok}")
    if not all_ok:
        status = "❌"
        total_blocks = len(re.findall(r'\$\$(.*?)\$\$', result, re.DOTALL))
        print(f"  {status} {basename}: {n_tags}/{total_blocks} 编号, 孤立={orphan}, $$={dollar_ok}, 连续={is_continuous}, tag={tag_pos_ok}")
    
    return n_tags, was_unclosed


def backup(path):
    """创建备份文件"""
    bak_path = path + '.bak'
    if not os.path.exists(bak_path):
        shutil.copy2(path, bak_path)


def main():
    import argparse
    parser = argparse.ArgumentParser(
        description='批量修复公式编号 v2 — 完整版（含 >$$ 规范化 + 未闭合 $$ 修复）'
    )
    parser.add_argument(
        'paths', nargs='+',
        help='要修复的文件路径（支持通配符）'
    )
    parser.add_argument(
        '--backup-dir',
        default=None,
        help='备份目录（默认：源文件同目录下 .bak）'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='详细输出'
    )
    args = parser.parse_args()
    
    # 收集所有文件
    files = []
    for p in args.paths:
        if '*' in p or '?' in p:
            import glob
            files.extend(glob.glob(p))
        else:
            files.append(p)
    
    files = sorted(set(files))
    
    if not files:
        print("没有找到匹配的文件")
        sys.exit(1)
    
    print(f"修复 {len(files)} 个文件...")
    
    total = 0
    fixed_unclosed = 0
    
    for fpath in files:
        n, unclosed = process_file(fpath)
        total += n
        if unclosed:
            fixed_unclosed += 1
    
    print(f"\n总计: {total} 个公式")
    if fixed_unclosed:
        print(f"修复未闭合 $$: {fixed_unclosed} 个文件")
    print("完成。")


if __name__ == '__main__':
    main()
