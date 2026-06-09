#!/usr/bin/env python3
"""validate_mermaid.py — 批量验证知识库中所有概念文件的Mermaid图语法

扫描30_核心概念/目录下所有.md文件，提取core_concept_map的mermaid代码块，
检查常见语法问题：未引用的括号/逗号、单行图、无效首行。

用法:
  python3 scripts/validate_mermaid.py --book-dir /path/to/book_dir

输出: 每个有问题的文件列出具体行号和问题类型
成功退出码=0(全部通过)，非0=有至少一个问题
"""
import argparse
import glob
import os
import re
import sys


def validate_book(book_dir: str, fix: bool = False) -> int:
    concepts_dir = os.path.join(book_dir, '30_核心概念')
    if not os.path.isdir(concepts_dir):
        print(f"❌ 目录不存在: {concepts_dir}")
        return 1

    total = 0
    issues = 0
    for fpath in sorted(glob.glob(os.path.join(concepts_dir, '*.md'))):
        name = os.path.basename(fpath)
        with open(fpath) as f:
            content = f.read()

        total += 1

        # Extract mermaid block after "### 4. 核心概念图谱"
        m = re.search(r'### 4\. 核心概念图谱\n(.*?)(?=### 图谱解析)', content, re.DOTALL)
        if not m:
            print(f"❌ {name}: 找不到「核心概念图谱」节")
            issues += 1
            continue

        section = m.group(1).strip()
        m2 = re.search(r'```mermaid\n(.*?)\n```', section, re.DOTALL)
        if not m2:
            print(f"❌ {name}: 核心概念图谱节无mermaid代码块")
            issues += 1
            continue

        block = m2.group(1).strip()

        file_issues = []
        lines = block.split('\n')

        # 1. 首行必须是 graph / sequenceDiagram
        first = lines[0] if lines else ''
        if first.startswith('%%{init:') and len(lines) > 1:
            first = lines[1]
        if first.startswith('flowchart '):
            file_issues.append(f"  ⚠️ 使用 flowchart（建议改用 graph TD，Obsidian 不兼容）")
        elif not (first.startswith('graph ') or first.startswith('sequenceDiagram')):
            file_issues.append(f"  首行不是graph/flowchart: {first[:40]}")

        # 2. 各行检查
        for i, line in enumerate(lines, 1):
            if '[' in line and ']' in line:
                label = line[line.index('[') + 1:line.index(']')]
                # 检查括号/逗号未引用
                has_special = ('(' in label or ',' in label or '[' in label)
                is_quoted = label.startswith('"') or label.startswith("'")
                if has_special and not is_quoted:
                    file_issues.append(f"  L{i}: 特殊字符未用引号: {label[:40]}")

            # 检查单行
            if i == 1 and line.startswith('graph '):
                # graph声明行后的剩余部分
                after = line.split(' ', 2)
                if len(after) >= 3 and len(lines) == 1:
                    file_issues.append(f"  单行图: {len(after[2])}个字符在同一行")

        if file_issues:
            print(f"❌ {name}:")
            for fi in file_issues:
                print(fi)
            issues += 1

    print(f"\n📊 总计: {total} 个文件, {issues} 个有问题, {total - issues} 个通过")
    return 1 if issues > 0 else 0


def main():
    p = argparse.ArgumentParser(description='验证知识库概念文件的Mermaid图语法')
    p.add_argument('--book-dir', required=True, help='书籍知识库根目录')
    args = p.parse_args()
    sys.exit(validate_book(args.book_dir))


if __name__ == '__main__':
    main()
