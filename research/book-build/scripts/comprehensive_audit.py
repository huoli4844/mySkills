#!/usr/bin/env python3
"""
综合质量审计脚本 — 检查军规符合性（不检查大纲差距）

用法：
  python3 comprehensive_audit.py --output /path/to/output --start-ch 1 --end-ch 14

检查项：
1. 第二人称"你"（习题前的正文中不得出现）
2. Step标记（应为"第一步/第二步"等学术表述）
3. 小结条目数（必须恰好6条）
4. 占位符（[待补充]/[TODO]等）
5. 参考文献格式
6. $$配对
7. 公式标签章号前缀

输出JSON格式报告，便于后续自动化处理。
"""
import re
import os
import json
import argparse


def check_second_person(content, ch_num):
    """检查正文中是否使用第二人称'你'（习题前）"""
    if '## 习题' in content:
        before_exam = content.split('## 习题')[0]
        for line in before_exam.split('\n'):
            if '你' in line:
                return True, line.strip()[:100]
    return False, None


def check_step_markers(content, ch_num):
    """检查是否存在Step标记"""
    match = re.search(r'Step\s+\d', content)
    if match:
        return True, match.group(0)
    return False, None


def check_summary_count(content, ch_num):
    """检查小结条目数（必须恰好6条）"""
    if '## 本章总结' not in content:
        return True, "缺少本章小结"
    
    summary_match = re.search(r'## 本章总结(.*?)## 习题', content, re.DOTALL)
    if not summary_match:
        return True, "小结格式异常"
    
    summary_text = summary_match.group(1)
    
    # 检查数字编号：1. xxx / ① xxx
    numbered = re.findall(r'^[\d①②③④⑤⑥⑦⑧⑨⑩]+\.?\s+', summary_text, re.MULTILINE)
    
    # 检查表格形式：| ① | 设计方法 | ...
    table_rows = re.findall(r'^\|\s*[①②③④⑤⑥⑦⑧⑨⑩\d]+\s*\|', summary_text, re.MULTILINE)
    
    if numbered:
        count = len(numbered)
    elif table_rows:
        count = len(table_rows)
    else:
        count = 0
    
    if count != 6:
        return True, f"小结条目数{count}，应为6条"
    
    return False, None


def check_placeholders(content, ch_num):
    """检查占位符"""
    placeholders = ['[待补充]', '[TODO]', '[请填写]', '[补充]', '[占位]']
    for ph in placeholders:
        if ph in content:
            return True, ph
    return False, None


def check_footnotes_format(content, ch_num):
    """检查参考文献格式"""
    if '## 参考文献' not in content:
        return True, "缺少参考文献章节"
    
    ref_section = content.split('## 参考文献')[1].split('##')[0] if '## 深入阅读' in content else content.split('## 参考文献')[1]
    refs = re.findall(r'\[\s*[MS]\s*\]', ref_section)
    if not refs:
        return True, "参考文献缺少[M]或[S]标识"
    
    return False, None


def check_dollar_pairing(content, ch_num):
    """检查$$配对"""
    dollar_count = content.count('$$')
    if dollar_count % 2 != 0:
        return True, f"奇数个$$（{dollar_count}个）"
    return False, None


def check_tag_chapter_prefix(content, ch_num):
    """检查公式标签章号前缀"""
    tags = re.findall(r'\\tag\{(\d+)-(\d+)\}', content)
    wrong = []
    for major, minor in tags:
        if major != str(ch_num):
            wrong.append(f"\\tag{{{major}-{minor}}}")
    
    if wrong:
        return True, f"公式标签章号错误: {', '.join(wrong[:3])}"
    
    return False, None


def audit_chapter(ch_num, output_dir):
    """审计单个章节"""
    # 找章节文件
    chapter_file = None
    for fn in os.listdir(output_dir):
        if fn.startswith(f"第{ch_num}章") and fn.endswith(".md"):
            chapter_file = fn
            break
    
    if not chapter_file:
        return {
            'chapter': ch_num,
            'file': None,
            'status': 'missing',
            'issues': []
        }
    
    with open(os.path.join(output_dir, chapter_file), 'r', encoding='utf-8') as f:
        content = f.read()
    
    issues = []
    
    checks = [
        check_second_person,
        check_step_markers,
        check_summary_count,
        check_placeholders,
        check_footnotes_format,
        check_dollar_pairing,
        check_tag_chapter_prefix,
    ]
    
    for check_fn in checks:
        has_issue, detail = check_fn(content, ch_num)
        if has_issue:
            issues.append({
                'check': check_fn.__name__,
                'detail': detail
            })
    
    return {
        'chapter': ch_num,
        'file': chapter_file,
        'status': 'failed' if issues else 'passed',
        'issues': issues,
        'size_kb': round(len(content) / 1024, 1)
    }


def main():
    parser = argparse.ArgumentParser(description='综合质量审计')
    parser.add_argument('--output', required=True, help='输出目录')
    parser.add_argument('--start-ch', type=int, default=1, help='起始章节')
    parser.add_argument('--end-ch', type=int, default=14, help='结束章节')
    args = parser.parse_args()
    
    results = []
    
    for ch_num in range(args.start_ch, args.end_ch + 1):
        result = audit_chapter(ch_num, args.output)
        results.append(result)
        status = '❌' if result['status'] == 'failed' else '✅'
        file_info = f"({result['file']}, {result['size_kb']}KB)" if result['file'] else "(未找到)"
        issue_count = len(result['issues'])
        print(f"{status} 第{ch_num}章 {file_info} {issue_count}个问题")
        for issue in result['issues']:
            print(f"   - {issue['check']}: {issue['detail']}")
    
    # 输出JSON报告
    report_path = os.path.join(args.output, 'comprehensive_audit_report.json')
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print(f"\n报告已保存: {report_path}")
    
    # 汇总统计
    passed = sum(1 for r in results if r['status'] == 'passed')
    failed = sum(1 for r in results if r['status'] == 'failed')
    missing = sum(1 for r in results if r['status'] == 'missing')
    print(f"\n汇总: {passed}章通过, {failed}章有问题, {missing}章未找到")


if __name__ == '__main__':
    main()
