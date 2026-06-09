#!/usr/bin/env python3
"""
verify_chapter.py — 教材质量核验脚本

对已生成的章节 .md 文件运行综合核验清单（13项 + 章级模式检查）。

用法：
  python3 scripts/verify_chapter.py output/第1章-绪论.md
  python3 scripts/verify_chapter.py output/第1章-绪论.md --verbose  # 详细模式
  python3 scripts/verify_chapter.py output/*.md                      # 批量检查
"""
import argparse, re, sys
from pathlib import Path


def check_chapter(filepath: str, verbose: bool = False) -> dict:
    """对一章运行完整核验，返回 {name, passed, details, score}"""
    try:
        text = Path(filepath).read_text(encoding='utf-8', errors='ignore')
    except FileNotFoundError:
        return {"name": filepath, "passed": 0, "total": 13, "details": [("FILE_NOT_FOUND", False, "")], "score": 0.0}

    total_chars = len(text)
    results = []

    # 0a 内容提要
    r = ('0a 内容提要', '## 内容提要' in text, '')
    results.append(r)

    # 0b 学习目标（数目标个数）
    has_obj = '通过本章学习，读者应达成以下学习目标' in text
    after_obj = text.split('通过本章学习')[1].split('---')[0] if '通过本章学习' in text else ''
    obj_items = len(re.findall(r'^\d+\. ', after_obj, re.MULTILINE))
    ok_obj = has_obj and obj_items >= 5
    results.append(('0b 学习目标', ok_obj, f'{obj_items}条'))

    # 1 权威定义
    multi_std = 'GB/T' in text and 'IEC' in text and 'IEEE' in text and 'GJB' in text
    results.append(('1 权威定义', multi_std, ''))

    # 2 直观引入（第一段不是公式）
    after_1_1 = text.split('## 1.1')[1].strip() if '## 1.1' in text else ''
    not_formula = not after_1_1.startswith('$$')
    results.append(('2 直观引入', not_formula, ''))

    # 3 有编号的公式
    formula_count = len(re.findall(r'\\tag\{', text))
    results.append(('3 公式编号', formula_count >= 3, f'{formula_count}个'))

    # 4 "式中"变量解释
    results.append(('4 "式中"', '式中，' in text, ''))

    # 5 含数字实例
    example_count = len(re.findall(r'例 \d+-\d+', text))
    results.append(('5 数字实例', example_count >= 1, f'{example_count}个'))

    # 6a 本章总结 — 数"本章总结"到"习题"之间的数字编号行
    summary_items = 0
    if '## 本章总结' in text:
        sum_section = text.split('## 本章总结')[1]
        if '## 习题' in sum_section:
            sum_section = sum_section.split('## 习题')[0]
        elif '---' in sum_section:
            sum_section = sum_section.split('---')[0]
        summary_items = len(re.findall(r'^\d+\. ', sum_section, re.MULTILINE))
    results.append(('6a 本章总结', summary_items >= 4, f'{summary_items}条'))

    # 6b 三层次习题
    has_basic = '基础题' in text
    has_adv = '进阶题' in text
    has_think = '思考题' in text
    ex_section = ''
    if '## 习题' in text:
        ex_section = text.split('## 习题')[1]
        for sep in ['## 参考文献', '## 深入阅读', '---']:
            if sep in ex_section:
                ex_section = ex_section.split(sep)[0]
    ex_count = len(re.findall(r'\d+-\d+', ex_section))
    results.append(('6b 三层次习题', has_basic and has_adv and has_think, f'{ex_count}题'))

    # 6c 参考文献
    has_ref = '## 参考文献' in text
    ref_section = ''
    if '## 参考文献' in text:
        ref_section = text.split('## 参考文献')[1]
        if '## 深入阅读' in ref_section:
            ref_section = ref_section.split('## 深入阅读')[0]
    ref_count = len(re.findall(r'^\d+\. ', ref_section, re.MULTILINE))
    results.append(('6c 参考文献', has_ref and ref_count >= 3, f'{ref_count}条'))

    # Mermaid有图必有文字说明
    mermaid_count = text.count('```mermaid')
    fig_captions = bool(re.search(r'\*图 \d+-\d+', text))
    results.append(('Mermaid说明', fig_captions or mermaid_count == 0, f'{mermaid_count}个图'))

    # LaTeX语法（花括号平衡）
    bad_braces = 0
    for m in re.finditer(r'\$\$(.+?)\$\$', text, re.DOTALL):
        f = m.group(1)
        if f.count('{') != f.count('}'):
            bad_braces += 1
    results.append(('LaTeX合法', bad_braces == 0, f'{bad_braces}个不平衡'))

    # 无KB模板泄漏
    no_leak = not any(kw in text for kw in ['精准释义', '本质特征', '前置知识'])
    results.append(('无KB泄漏', no_leak, ''))

    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    score = passed / total

    if verbose:
        print(f"\n{'='*55}")
        print(f"  \U0001f4cb 核验: {Path(filepath).name}")
        print(f"{'='*55}")
        for name, ok, detail in results:
            d = f' — {detail}' if detail else ''
            print(f'  {"✅" if ok else "❌"} {name}{d}')
        print(f"\n  \U0001f4ca {passed}/{total} ({score*100:.0f}%)")

    return {
        "name": Path(filepath).name,
        "path": filepath,
        "passed": passed,
        "total": total,
        "score": score,
        "chars": total_chars,
        "details": results,
    }


def main():
    parser = argparse.ArgumentParser(description='章节质量核验')
    parser.add_argument('files', nargs='+', help='.md 文件路径')
    parser.add_argument('--verbose', '-v', action='store_true', help='详细模式')
    args = parser.parse_args()

    all_results = []
    for f in args.files:
        r = check_chapter(f, verbose=args.verbose)
        all_results.append(r)

    if len(all_results) > 1:
        print(f"\n{'='*55}")
        print(f"  \U0001f4ca 批量摘要")
        print(f"{'='*55}")
        for r in all_results:
            emoji = '✅' if r['score'] >= 0.85 else ('⚠️' if r['score'] >= 0.6 else '❌')
            print(f"  {emoji} {r['name']:40s} {r['passed']:2d}/{r['total']} ({r['score']*100:.0f}%)  {r['chars']:>7,} chars")


if __name__ == '__main__':
    main()
