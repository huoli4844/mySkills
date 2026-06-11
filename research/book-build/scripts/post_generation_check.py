"""post_generation_check.py — CLI entry point for post-generation quality checks.
Check logic lives in scripts/post_gen_check/ package.
Usage:
  python3 scripts/post_generation_check.py output/第N章.md [--fix] [--verbose]
"""
import re, sys, os
from pathlib import Path
from post_gen_check import (
    check_formulas, check_formula_format, _fix_missing_tag,
    _fix_duplicate_tags, _fix_numbering_gap, _fix_formula_format,
    extract_chapter_number, fix_chapter_prefix,
    check_mermaid, _fix_mermaid_issues, check_mermaid_has_caption,
    check_wikilinks, check_tag_placement, check_spelling, check_derivation_depth,
)

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

    # ── 1.5 公式格式规范检查（新增）──
    print(f"\n  📐 公式格式规范检查")
    format_issues = check_formula_format(text, verbose)
    if format_issues:
        for line, severity, desc, fixable, _ in format_issues:
            prefix = '❌' if severity == 'ERROR' else '⚠️'
            print(f"    {prefix} [{severity}] L{line} {desc}")
            total_issues += 1
        if auto_fix:
            text_before = text
            text = _fix_formula_format(text)
            if text != text_before:
                print(f"    ✅ 已自动修复格式问题")
    else:
        print(f"    ✅ 公式格式规范（tag在$$前一行，无空$$块）")

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

    # ── 2.5 Mermaid有图必有说明检查（新增）──
    print(f"\n  📝 Mermaid图注检查")
    caption_issues = check_mermaid_has_caption(text, verbose)
    if caption_issues:
        for line, severity, desc, _, _ in caption_issues:
            prefix = '⚠️'
            print(f"    {prefix} [{severity}] {desc}")
            total_issues += 1
    else:
        print(f"    ✅ 所有Mermaid图后都有图注")

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

    # ── 3.5 \tag{}放置检查 ──
    print(f"\n  🏷️  \\tag{{}}放置检查")
    tag_place_issues = check_tag_placement(text)
    if tag_place_issues:
        for line, severity, desc, _, _ in tag_place_issues:
            prefix = '❌' if severity == 'ERROR' else '⚠️'
            print(f"    {prefix} [{severity}] {desc}")
            total_issues += 1
    else:
        print(f"    ✅ 所有\\tag{{}}在$$块内部")

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

    # ── 5. 推导深度启发式检查（新增）──
    print(f"\n  🔬 推导深度检查")
    depth_issues = check_derivation_depth(text, verbose)
    if depth_issues:
        for line, severity, desc, _, _ in depth_issues:
            prefix = '⚠️'
            print(f"    {prefix} [{severity}] {desc}")
            total_issues += 1
    else:
        print(f"    ✅ 公式前含推导词比例正常")

    # 统计
    # Use non-greedy match with DOTALL to properly count formula blocks
    formula_blocks = re.findall(r'\$\$(.+?)\$\$', text, re.DOTALL)
    formula_count = len(formula_blocks)
    tag_count = len(re.findall(r'\\\\tag\{', text))
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
        tags = re.findall(r'\\\\tag\{(?:' + str(chapter_n) + r'-)?(\d+)\}', fixed_text)
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
    parser.add_argument('files', nargs='+', help='.md 文件路径（支持 glob，如 output/*.md）')
    parser.add_argument('--fix', action='store_true', help='自动修复可修复的问题')
    parser.add_argument('--verbose', '-v', action='store_true', help='详细输出')
    parser.add_argument('--dir', '-d', action='store_true', help='目录模式：扫描目录下所有 .md 文件')
    args = parser.parse_args()

    # --dir 模式：将 files[0] 视为目录，列出所有 .md
    if args.dir:
        target_dir = args.files[0] if args.files else '.'
        if os.path.isdir(target_dir):
            md_files = sorted(
                os.path.join(target_dir, f)
                for f in os.listdir(target_dir)
                if f.endswith('.md') and not f.endswith('.bak.md')
            )
            print(f"📂 目录模式: {target_dir} → {len(md_files)} 个 .md 文件")
            args.files = md_files

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
