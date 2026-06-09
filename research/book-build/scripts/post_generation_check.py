#!/usr/bin/env python3
"""
post_generation_check.py — 章节生成后自动质量检查 + 修复

在每章生成完成后自动运行：
  python3 scripts/post_generation_check.py output/第5章-搭接技术.md

检查项：
  1. 公式LaTeX语法（花括号平衡、\left/\right对称、无空\frac）
  2. 公式全编号（每个$$块必须有\tag，编号连续无重复无跳跃）
  3. Mermaid语法校验（7项：类型/关键字/引号/subgraph/emoji/init/classDef）
  4. Wikilink检查（教材禁止[[...]]交叉引用）
  5. 常见拼写错误检查
  6. 自动修复：缺编号→补编号、编号跳跃→重新编号、重复→去重、
     Mermaid非法关键字移除

用法：
  python3 scripts/post_generation_check.py output/第N章.md              # 检查+报告
  python3 scripts/post_generation_check.py output/第N章.md --fix       # 检查+自动修复
  python3 scripts/post_generation_check.py output/第N章.md --verbose   # 详细输出
  python3 scripts/post_generation_check.py output/*.md --fix           # 批量修复
"""

import re, sys, os
from pathlib import Path


def extract_chapter_number(text: str) -> int:
    """从文件中提取章号"""
    m = re.search(r'第\s*(\d+)\s*章', text)
    return int(m.group(1)) if m else 0


def fix_chapter_prefix(n: int) -> str:
    """返回章号前缀如 '5-'"""
    return f'{n}-'


def check_formulas(text: str, chapter_n: int, verbose: bool = False) -> list:
    """
    检查所有公式块，返回问题列表。
    每个问题: (行号, 严重级别, 描述, 可自动修复, 修复方法)
    """
    issues = []
    lines = text.split('\n')
    tag_prefix = f'{chapter_n}-'

    # Step 1: 定位所有 $$ 公式块
    in_formula = False
    formula_blocks = []  # [(start_line, end_line, content_lines)]
    start = 0
    current = []
    for i, line in enumerate(lines):
        if line.strip() == '$$':
            if in_formula:
                formula_blocks.append((start, i, current))
                current = []
                in_formula = False
            else:
                start = i
                in_formula = True
        elif in_formula:
            current.append((i, line))

    # Step 2: 检查每个公式块
    for start_line, end_line, content in formula_blocks:
        content_text = '\n'.join([l for _, l in content])
        block_lines = [l for _, l in content]
        full_text = '\n'.join(block_lines)

        # 2a. 花括号平衡
        braces = 0
        for ch in full_text:
            if ch == '{': braces += 1
            if ch == '}': braces -= 1
        if braces != 0:
            issues.append((start_line + 1, 'ERROR', f'花括号不平衡(差{braces}个"}}")', True,
                          lambda t, s=start_line, e=end_line: t))

        # 2b. \left/\right 匹配
        lefts = full_text.count('\\left')
        rights = full_text.count('\\right')
        if lefts != rights:
            issues.append((start_line + 1, 'ERROR', f'\\left({lefts})与\\right({rights})不匹配', True,
                          lambda t, s=start_line, e=end_line: t))

        # 2c. 空\frac
        if re.search(r'\\frac\s*\{\s*\}\s*\{[^}]*\}', full_text) or \
           re.search(r'\\frac\s*\{[^}]*\}\s*\{\s*\}', full_text):
            issues.append((start_line + 1, 'WARN', '存在空\\frac', True,
                          lambda t, s=start_line, e=end_line: t))

        # 2d. \begin/\end不匹配
        if full_text.count('\\begin') != full_text.count('\\end'):
            issues.append((start_line + 1, 'ERROR', '\\begin/\\end不匹配', True,
                          lambda t, s=start_line, e=end_line: t))

        # 2e. 检查\tag是否存在
        has_tag = '\\tag{' in full_text
        if not has_tag:
            issues.append((start_line + 1, 'ERROR', f'缺\\tag编号', True,
                          lambda t, s=start_line: _fix_missing_tag(t, s, chapter_n)))

    # Step 3: 提取所有\tag编号，检查连续性和重复
    tags = re.findall(r'\\tag\{' + tag_prefix + r'(\d+)\}', text)
    if tags:
        nums = [int(x) for x in tags]
        nums_sorted = sorted(nums)

        # 重复检查
        seen = set()
        dups = set()
        for n in nums:
            if n in seen:
                dups.add(n)
            seen.add(n)
        for d in sorted(dups):
            issues.append((0, 'ERROR', f'公式编号重复: {tag_prefix}{d}', True,
                          lambda t: _fix_duplicate_tags(t, chapter_n)))

        # 跳跃检查
        expected = list(range(min(nums_sorted), max(nums_sorted) + 1))
        missing = sorted(set(expected) - set(nums_sorted))
        if missing:
            issues.append((0, 'WARN', f'公式编号缺失: {", ".join(tag_prefix + str(m) for m in missing)}', True,
                          lambda t: _fix_numbering_gap(t, chapter_n)))

        # 编号超过+1检查（大跳跃）
        for i in range(1, len(nums_sorted)):
            if nums_sorted[i] - nums_sorted[i - 1] > 1:
                issues.append((0, 'INFO', f'编号跳跃: {tag_prefix}{nums_sorted[i-1]}→{tag_prefix}{nums_sorted[i]}', True,
                              lambda t: _fix_numbering_gap(t, chapter_n)))

    return issues


def _fix_missing_tag(text: str, line_idx: int, chapter_n: int) -> str:
    """给指定的公式块补上下一个可用编号。\tag必须放在$$...$$内部。"""
    lines = text.split('\n')
    tag_prefix = f'{chapter_n}-'

    # 找到当前最大的编号
    existing = re.findall(r'\\tag\{' + tag_prefix + r'(\d+)\}', text)
    next_num = max([int(x) for x in existing]) + 1 if existing else 1

    # 找到该公式块的闭合 $$
    for i in range(line_idx, len(lines)):
        if lines[i].strip() == '$$':
            # 在闭合 $$ 之前插入 \tag（保证在$$...$$内部）
            lines.insert(i, f'\\tag{{{tag_prefix}{next_num}}}')
            break

    return '\n'.join(lines)


def _fix_duplicate_tags(text: str, chapter_n: int) -> str:
    """修复重复编号：重新从1开始连续编号"""
    tag_prefix = f'{chapter_n}-'
    lines = text.split('\n')
    new_lines = []
    tag_counter = 1
    for line in lines:
        if re.match(r'^\\tag\{' + tag_prefix + r'\d+\}$', line.strip()):
            new_lines.append(f'\\tag{{{tag_prefix}{tag_counter}}}')
            tag_counter += 1
        else:
            new_lines.append(line)
    return '\n'.join(new_lines)


def _fix_numbering_gap(text: str, chapter_n: int) -> str:
    """修复编号跳跃：重新从1开始连续编号"""
    return _fix_duplicate_tags(text, chapter_n)


# ── 合法Mermaid图表类型（首行关键字） ──
VALID_MERMAID_TYPES = {
    'flowchart', 'graph', 'sequenceDiagram', 'classDiagram',
    'stateDiagram-v2', 'erDiagram', 'gantt', 'pie', 'mindmap',
    'timeline', 'journey', 'xychart-beta', 'quadrantChart',
    'sankey-beta', 'gitgraph', 'requirementDiagram', 'block-beta',
}

def check_mermaid(text: str, verbose: bool = False) -> list:
    """检查Mermaid图语法——全面校验，修复之前只查闭合的漏洞"""
    issues = []
    lines = text.split('\n')
    in_mermaid = False
    mermaid_content = []
    mermaid_start_line = 0
    mermaid_idx = 0  # 图序号

    # 变量跟踪所有 mermaid 块的起止行号
    mermaid_blocks = []
    for i, line in enumerate(lines):
        if line.strip() == '```mermaid':
            in_mermaid = True
            mermaid_start_line = i
            mermaid_content = []
            mermaid_idx += 1
        elif in_mermaid and line.strip() == '```':
            in_mermaid = False
            mermaid_blocks.append((mermaid_idx, mermaid_start_line, i, mermaid_content))
        elif in_mermaid:
            mermaid_content.append((i, line))

    # 检查未闭合的
    if in_mermaid:
        issues.append((mermaid_start_line + 1, 'ERROR',
                       f'Mermaid图{mermaid_idx}缺闭合```', True,
                       lambda t: t))

    for idx, start_line, end_line, content in mermaid_blocks:
        block_lines = [l for _, l in content]
        if not block_lines or all(not l.strip() for l in block_lines):
            issues.append((start_line + 1, 'WARN',
                           f'Mermaid图{idx}内容为空', False, None))
            continue

        first_line = block_lines[0].strip()
        chart_type = first_line.split()[0] if first_line else ''

        # ── 检查1：图表类型是否合法 ──
        if chart_type not in VALID_MERMAID_TYPES:
            issues.append((start_line + 1, 'WARN',
                           f'Mermaid图{idx}: 未知图表类型"{chart_type}"'
                           f'（合法: {", ".join(sorted(VALID_MERMAID_TYPES)[:10])}...）',
                           False, None))

        # ── 检查2：xychart-beta 语法 ──
        if chart_type == 'xychart-beta':
            valid_kw = {'title', 'x-axis', 'y-axis', 'bar', 'line'}
            found_kw = set()
            invalid_kw = set()
            for bline in block_lines[1:]:  # 跳过首行（"xychart-beta"本身不是关键字）
                kw = bline.strip().split()[0] if bline.strip() else ''
                if kw and kw not in valid_kw:
                    invalid_kw.add(kw)
                elif kw in valid_kw:
                    found_kw.add(kw)
            for bad in invalid_kw:
                issues.append((start_line + 1, 'ERROR',
                               f'Mermaid图{idx} xychart-beta含非法关键字"{bad}"'
                               f'（仅支持: {", ".join(sorted(valid_kw))}）',
                               False, None))
            if 'y-axis' not in found_kw:
                issues.append((start_line + 1, 'WARN',
                               f'Mermaid图{idx} xychart-beta缺y-axis定义',
                               False, None))
            bar_or_line = found_kw & {'bar', 'line'}
            if not bar_or_line:
                issues.append((start_line + 1, 'WARN',
                               f'Mermaid图{idx} xychart-beta缺bar/line数据',
                               False, None))

        # ── 检查3：flowchart/graph 节点标签引号 ──
        if chart_type in ('flowchart', 'graph'):
            for bline in block_lines:
                stripped = bline.strip()
                # 检测节点标签 [] 内含逗号或括号但未用引号包裹
                for m in re.finditer(r'([A-Za-z0-9_]+)\[([^\\"]*?)\]', stripped):
                    label = m.group(2)
                    if (',' in label or '(' in label or ')' in label) and \
                       '"' not in label:
                        issues.append((start_line + 1, 'WARN',
                                       f'Mermaid图{idx} 节点"{m.group(1)}"标签含'
                                       f'逗号/括号但未用引号: [{label}] → '
                                       f'["{label}"]',
                                       False, None))

        # ── 检查4：subgraph 标题特殊字符（Obsidian词法崩溃根因） ──
        for bline in block_lines:
            stripped = bline.strip()
            # subgraph 标题含括号/破折号/逗号等特殊字符
            if stripped.startswith('subgraph '):
                title = stripped[len('subgraph '):].strip()
                if re.search(r'[（）()—–,，]', title):
                    issues.append((start_line + 1, 'ERROR',
                                   f'Mermaid图{idx} subgraph标题含特殊字符: '
                                   f'"{title[:50]}"'
                                   f' → Obsidian词法错误，请移除括号/破折号/逗号',
                                   False, None))

        # ── 检查5：emoji在节点标签中 ──
        emoji_pattern = re.compile(
            '[\U0001F300-\U0001F9FF'  # Misc symbols + emoticons
            '\u2600-\u27BF'           # Misc symbols + dingbats
            '\u2B05-\u2B55'           # Arrows + misc
            '\u2702-\u27B0'           # Dingbats
            '\u23E9-\u23FA'           # Transport symbols
            '\u25AA-\u25FE'           # Geometric shapes
            '\u00A9\u00AE\u2122'     # Copyright, registered, trademark
            ']')
        for bline in block_lines:
            emojis = emoji_pattern.findall(bline)
            if emojis:
                issues.append((start_line + 1, 'WARN',
                               f'Mermaid图{idx} 节点含emoji: {" ".join(set(emojis))}'
                               f' → 替换为纯文字（Obsidian渲染崩溃）',
                               False, None))

        # ── 检查6：%%{init} 格式 ──
        for bline in block_lines:
            stripped = bline.strip()
            if '%%{init' in stripped:
                if "'" in stripped:
                    issues.append((start_line + 1, 'WARN',
                                   f'Mermaid图{idx} %%{{init}}用了单引号'
                                   f' → 必须用双引号JSON',
                                   False, None))
                if not stripped.endswith('%%'):
                    issues.append((start_line + 1, 'WARN',
                                   f'Mermaid图{idx} %%{{init}}缺闭合%%',
                                   False, None))

        # ── 检查6：classDef 定义覆盖 ──
        classdefs = set()
        class_uses = set()
        for bline in block_lines:
            m = re.match(r'classDef\s+(\w+)', bline.strip())
            if m:
                classdefs.add(m.group(1))
            for cm in re.finditer(r'([A-Za-z0-9_]+)\s*:::\s*(\w+)', bline.strip()):
                class_uses.add(cm.group(2))
        undefined_classes = class_uses - classdefs
        if undefined_classes:
            issues.append((start_line + 1, 'ERROR',
                           f'Mermaid图{idx} 引用未定义的classDef: '
                           f'{", ".join(sorted(undefined_classes))}',
                           False, None))

    return issues


def check_wikilinks(text: str) -> list:
    """检查教材中是否含有[[wikilink]]（教材禁用），返回问题列表"""
    issues = []
    for m in re.finditer(r'\[\[([^\]]+)\]\]', text):
        line_num = text[:m.start()].count('\n') + 1
        issues.append((line_num, 'ERROR',
                       f'行{line_num}: 发现[[{m.group(1)}]] → 教材正文禁用wikilink'))
    return issues


def check_spelling(text: str, verbose: bool = False) -> list:
    """检查常见LaTeX拼写错误，返回问题列表"""
    issues = []
    # 这些是真正的拼写错误（不是命令子串）
    patterns = {
        r'\bomege\b': 'omega',
        r'\bthets\b': 'theta',
        r'\bepsilo\b': 'epsilon',
        r'\blamda\b': 'lambda',
        r'\bdelat\b': 'delta',
        r'\bsgima\b': 'sigma',
        r'\balfe\b': 'alpha',
        r'\bbete\b': 'beta',
        r'\bgama\b': 'gamma',
        r'\bpai\b': 'pi',
        r'\binfinty\b': 'infty',
        r'\bOmege\b': 'Omega',
    }
    for pattern, correct in patterns.items():
        for m in re.finditer(pattern, text):
            # 确保不是命令的一部分
            line_num = text[:m.start()].count('\n') + 1
            issues.append((line_num, 'WARN', f'疑似拼写错误: "{m.group()}"→"{correct}"', True,
                          lambda t, p=pattern, c=correct: t.replace(p, c)))

    return issues


def _fix_mermaid_issues(text: str) -> str:
    """修复Mermaid语法问题：移除xychart-beta中的非法关键字"""
    lines = text.split('\n')
    new_lines = []
    in_mermaid = False
    in_xychart = False

    # 已知的xychart-beta非法关键字列表
    INVALID_XYCHART_KW = {
        'bar-group-group', 'bar-group', 'group-bar',
        'test-chart', 'sample-chart', 'demo-chart',
    }

    for i, line in enumerate(lines):
        stripped = line.strip()

        if stripped == '```mermaid':
            in_mermaid = True
            in_xychart = False
            new_lines.append(line)
        elif in_mermaid and stripped == '```':
            in_mermaid = False
            in_xychart = False
            new_lines.append(line)
        elif in_mermaid:
            # 检测xychart-beta类型
            if stripped.startswith('xychart-beta'):
                in_xychart = True
                new_lines.append(line)
            elif in_xychart:
                kw = stripped.split()[0] if stripped else ''
                if kw in INVALID_XYCHART_KW:
                    # 跳过该行（移除非法关键字行）
                    continue
                else:
                    new_lines.append(line)
            else:
                new_lines.append(line)
        else:
            new_lines.append(line)

    return '\n'.join(new_lines)


def run_check(filepath: str, auto_fix: bool = False, verbose: bool = False) -> dict:
    """对单文件运行完整检查，返回结果字典"""

    print(f"\n{'='*60}")
    print(f"  📋 质量检查: {Path(filepath).name}")
    print(f"{'='*60}")

    text = Path(filepath).read_text(encoding='utf-8', errors='ignore')
    chapter_n = extract_chapter_number(text)
    total_issues = 0

    # ── 1. 公式检查 ──
    print(f"\n  📐 公式检查")
    formula_issues = check_formulas(text, chapter_n, verbose)
    if formula_issues:
        for line, severity, desc, _, _ in formula_issues:
            prefix = '❌' if severity == 'ERROR' else ('⚠️' if severity == 'WARN' else 'ℹ️')
            loc = f'L{line}' if line > 0 else ''
            print(f"    {prefix} [{severity}] {loc} {desc}")
            total_issues += 1
    else:
        print(f"    ✅ 所有公式语法正确，编号连续无问题")

    # ── 2. Mermaid检查 ──
    print(f"\n  🖼️  Mermaid图检查")
    mermaid_issues = check_mermaid(text, verbose)
    if mermaid_issues:
        for line, severity, desc, _, _ in mermaid_issues:
            prefix = '❌' if severity == 'ERROR' else '⚠️'
            print(f"    {prefix} [{severity}] {desc}")
            total_issues += 1
    else:
        print(f"    ✅ 所有Mermaid图语法校验通过（7项：类型/关键字/引号/subgraph/emoji/init/classDef）")

    # ── 3. Wikilink检查（教材禁用的[[...]]交叉引用）──
    print(f"\n  🔗  Wikilink检查")
    wikilink_issues = check_wikilinks(text)
    if wikilink_issues:
        for line, severity, desc in wikilink_issues:
            prefix = '❌' if severity == 'ERROR' else '⚠️'
            print(f"    {prefix} [{severity}] {desc}")
            total_issues += 1
    else:
        print(f"    ✅ 无[[wikilink]]残留")

    # ── 4. 拼写检查 ──
    print(f"\n  ✏️  拼写检查")
    spell_issues = check_spelling(text, verbose)
    if spell_issues:
        for line, severity, desc, _, _ in spell_issues:
            prefix = '⚠️' if severity == 'WARN' else 'ℹ️'
            loc = f'L{line}' if line > 0 else ''
            print(f"    {prefix} [{severity}] {loc} {desc}")
            total_issues += 1
    else:
        print(f"    ✅ 无常见拼写错误")

    # 统计
    # Use non-greedy match with DOTALL to properly count formula blocks
    formula_blocks = re.findall(r'\$\$(.+?)\$\$', text, re.DOTALL)
    formula_count = len(formula_blocks)
    tag_count = len(re.findall(r'\\tag\{', text))
    mermaid_count = text.count('```mermaid')
    example_count = len(re.findall(r'\*\*例\s*\d+-\d+\*\*', text))

    print(f"\n  📊 统计")
    print(f"    公式块: {formula_count} | 已编号: {tag_count} | Mermaid: {mermaid_count} | 例题: {example_count}")

    # ── 5. 自动修复 ──
    if auto_fix and total_issues > 0:
        print(f"\n  🔧 自动修复中...")
        fixed_text = text
        fix_count = 0

        # 5a. 修复公式编号问题（缺编号/重复/跳跃）
        from collections import Counter
        tags = re.findall(r'\\tag\{(?:' + str(chapter_n) + r'-)?(\d+)\}', fixed_text)
        if tags:
            nums = [int(x) for x in tags]
            if len(nums) != len(set(nums)):
                fixed_text = _fix_duplicate_tags(fixed_text, chapter_n)
                fix_count += 1
                print(f"    ✅ 修复重复编号 → 重新编号完成")

        # 5b. 补缺编号
        recheck = check_formulas(fixed_text, chapter_n, verbose=False)
        missing_tag_issues = [i for i in recheck if '缺\\tag编号' in i[2]]
        for issue in missing_tag_issues:
            line, _, desc, _, fix_fn = issue
            if fix_fn:
                fixed_text = fix_fn(fixed_text)
                fix_count += 1
                print(f"    ✅ L{line}: 补\\tag编号")

        # 5d. 修复Mermaid语法问题（非法关键字移除等）
        mermaid_fixed = _fix_mermaid_issues(fixed_text)
        if mermaid_fixed != fixed_text:
            fixed_text = mermaid_fixed
            fix_count += 1
            print(f"    ✅ 修复Mermaid非法关键字")

        # 5c. 修复跳跃（如果还有编号问题）
        recheck = check_formulas(fixed_text, chapter_n, verbose=False)
        gap_issues = [i for i in recheck if '编号跳跃' in i[2] or '编号缺失' in i[2] or '编号重复' in i[2]]
        gap_fixed = set()
        for issue in gap_issues:
            desc = issue[2]
            if desc not in gap_fixed:
                gap_fixed.add(desc)
                fix_fn = issue[4]
                if fix_fn:
                    fixed_text = fix_fn(fixed_text)
                    fix_count += 1
                    print(f"    ✅ 修复: {desc}")

        # 写入修复结果
        if fix_count > 0:
            Path(filepath).write_text(fixed_text, encoding='utf-8')
            print(f"\n  ✅ 已应用 {fix_count} 项修复到 {Path(filepath).name}")

    # 最终结论
    if total_issues == 0:
        print(f"\n  ✅ 全部检查通过！")
    else:
        if auto_fix:
            print(f"\n  ⚠️ 发现 {total_issues} 个问题，已尝试修复。建议重新运行检查确认。")
        else:
            print(f"\n  ⚠️ 发现 {total_issues} 个问题。使用 --fix 参数自动修复。")

    return {
        'file': filepath,
        'issues': total_issues,
        'formulas': formula_count,
        'tags': tag_count,
        'mermaids': mermaid_count,
        'examples': example_count,
    }


def main():
    import argparse
    parser = argparse.ArgumentParser(description='章节生成后自动质量检查')
    parser.add_argument('files', nargs='+', help='.md 文件路径')
    parser.add_argument('--fix', action='store_true', help='自动修复可修复的问题')
    parser.add_argument('--verbose', '-v', action='store_true', help='详细输出')
    args = parser.parse_args()

    all_results = []
    for f in args.files:
        if not os.path.exists(f):
            print(f"❌ 文件不存在: {f}")
            continue
        r = run_check(f, auto_fix=args.fix, verbose=args.verbose)
        all_results.append(r)

    if len(all_results) > 1:
        print(f"\n{'='*60}")
        print(f"  批量检查汇总")
        print(f"{'='*60}")
        for r in all_results:
            status = '✅' if r['issues'] == 0 else '⚠️'
            print(f"  {status} {Path(r['file']).name:40s} "
                  f"公式{r['formulas']:2d} 编号{r['tags']:2d} "
                  f"图{r['mermaids']} 例题{r['examples']} "
                  f"问题{r['issues']}")


if __name__ == '__main__':
    main()
