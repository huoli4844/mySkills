#!/usr/bin/env python3
"""
大纲-章节差距自动化分析工具。
对比写作大纲和已有章节正文，输出补充与完善分析报告。

用法：
  python3 outline_vs_chapter_audit.py --project /path/to/project --output /path/to/output

输出：
  output/补充与完善分析报告.md  — 详细分析报告
  output/补充执行清单.json      — 结构化执行清单
"""
import os
import re
import sys
import json
import argparse
from datetime import datetime

def parse_outline_sections(guide_content):
    """从写作大纲提取 ### 节标题，返回 (节号, 节名) 列表。"""
    sections = re.findall(r'^###\s+(\d+(?:\.\d+)*)\s+(.+)', guide_content, re.MULTILINE)
    return [(snum, sname.strip()) for snum, sname in sections]

def parse_section_targets(guide_content):
    """从大纲表格提取各节目标体量(如 38KB)。"""
    targets = {}
    in_table = False
    for line in guide_content.split('\n'):
        if '| 大纲节号 | 标题' in line:
            in_table = True
            continue
        if in_table:
            if '**总计**' in line or '**体量目标**' in line:
                in_table = False
                break
            parts = [p.strip() for p in line.split('|') if p.strip()]
            for i, p in enumerate(parts):
                snum_match = re.match(r'^(\d+\.\d+(?:\.\d+)*)', p)
                if snum_match and ('KB' in p or ('字节' in p)):
                    targets[snum_match.group(1)] = p
                elif snum_match:
                    # 节号和体量在不同列
                    target = parts[i+1] if i+1 < len(parts) else ''
                    if target and ('KB' in target or '字节' in target):
                        targets[snum_match.group(1)] = target
    return targets

def parse_blind_spots(guide_content):
    """从大纲提取共同盲区/可补充内容。"""
    blind_spots = []
    in_blind = False
    for line in guide_content.split('\n'):
        if '共同盲区' in line:
            in_blind = True
            continue
        if in_blind:
            stripped = line.strip()
            if re.match(r'^\d+\.', stripped):
                blind_spots.append(stripped)
            elif not stripped:
                continue
            else:
                in_blind = False
    return blind_spots

def parse_specific_reqs(guide_content):
    """从大纲提取每节写作指南中的具体要求。"""
    reqs = []
    current_section = ''
    for line in guide_content.split('\n'):
        section_match = re.match(r'^###\s+(\d+(?:\.\d+)*)\s+(.+)', line)
        if section_match:
            current_section = f"{section_match.group(1)} {section_match.group(2)}"
            continue
        if current_section and line.strip().startswith('**') and ('手法' in line or '引入' in line or '核心' in line):
            reqs.append(f"{current_section}: {line.strip()}")
    return reqs

def parse_unmet_rules(guide_content):
    """从大纲提取军规未落实项(- [ ]标记)。"""
    unmet = []
    in_rules = False
    for line in guide_content.split('\n'):
        if '12条军规' in line:
            in_rules = True
            continue
        if in_rules:
            if '- [ ]' in line:
                unmet.append(line.replace('- [ ]', '').strip())
            elif line.strip() and not line.strip().startswith('-'):
                in_rules = False
    return unmet

def analyze_chapter(chapter_content):
    """分析已有章节内容，返回统计字典。"""
    return {
        'formula_count': len(re.findall(r'\\tag\{', chapter_content)),
        'mermaid_count': len(re.findall(r'```mermaid', chapter_content)),
        'table_count': len(re.findall(r'^\|[-\s|:]+$', chapter_content, re.MULTILINE)),
        'example_count': len(re.findall(r'\*\*例\s+\d+-\d+\*\*', chapter_content)),
        'case_count': len(re.findall(r'\*\*案例\s+\d+-\d+\*\*', chapter_content)),
        'has_summary': '本章总结' in chapter_content or '小结' in chapter_content,
        'has_exercise': '## 习题' in chapter_content,
        'fig_count': len(re.findall(r'图\s+\d+-\d+', chapter_content)),
    }

def build_report(results, output_dir):
    """生成Markdown详细报告。"""
    lines = []
    lines.append("# 章节内容补充与完善分析报告")
    lines.append(f"\n分析日期: {datetime.now().strftime('%Y-%m-%d')}")
    lines.append(f"共 {len(results)} 章，其中 {sum(1 for r in results if r.get('status')!='未撰写')} 章已撰写\n\n")

    for r in results:
        ch = r['chapter']
        lines.append(f"\n{'='*80}")
        lines.append(f"## 第{ch}章 补充与完善分析\n")

        if r.get('status') == '未撰写':
            lines.append("❌ **本章尚未撰写**，需根据写作大纲从零开始编写。\n")
            continue

        lines.append("### 一、当前内容统计")
        lines.append(f"- 文件大小: {r.get('file_size_kb', 0)} KB")
        lines.append(f"- 公式数: {r.get('formula_count', 0)}")
        lines.append(f"- Mermaid图: {r.get('mermaid_count', 0)}")
        lines.append(f"- 表格数: {r.get('table_count', 0)}")
        lines.append(f"- 例题数: {r.get('example_count', 0)}")
        lines.append(f"- 案例数: {r.get('case_count', 0)}")
        lines.append(f"- 图表引用: {r.get('fig_count', 0)}")
        lines.append(f"- 有章节小结: {'✅' if r.get('has_summary') else '❌'}")
        lines.append(f"- 有习题: {'✅' if r.get('has_exercise') else '❌'}")

        missing = {k: v for k, v in r.get('section_coverage', {}).items() if v == '未覆盖'}
        if missing:
            lines.append(f"\n### 二、未覆盖的章节")
            for snum in missing:
                lines.append(f"- `{snum}`")

        targets = r.get('section_targets', {})
        if targets:
            lines.append(f"\n### 三、各节目标体量与覆盖情况")
            for snum, target in targets.items():
                status = '✅' if r.get('section_coverage', {}).get(snum) == '已覆盖' else '❌'
                lines.append(f"- `{snum}`: {target} {status}")

        blind = r.get('blind_spots', [])
        if blind:
            lines.append(f"\n### 四、参考书盲区 / 可补充内容")
            for i, b in enumerate(blind, 1):
                lines.append(f"{i}. {b}")

        lines.append(f"\n### 五、综合建议")
        gaps = []
        if r.get('formula_count', 0) < 5: gaps.append("补充编号公式")
        if r.get('mermaid_count', 0) == 0: gaps.append("补充Mermaid可视化图")
        if r.get('example_count', 0) < 2: gaps.append("补充计算例题")
        if r.get('case_count', 0) < 2: gaps.append("补充真实工程案例")
        if not r.get('has_summary'): gaps.append("补充本章小结")
        if not r.get('has_exercise'): gaps.append("补充习题")
        if missing: gaps.append(f"覆盖{len(missing)}个缺失章节")
        if not gaps: gaps.append("整体完整，按写作指南细化")
        for g in gaps:
            lines.append(f"- {g}")
        lines.append("")

    report_path = os.path.join(output_dir, '补充与完善分析报告.md')
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    return report_path

def main():
    parser = argparse.ArgumentParser(description='大纲-章节差距自动化分析')
    parser.add_argument('--project', default='/Users/huoli4844/Desktop/电磁兼容教材',
                        help='项目根目录')
    parser.add_argument('--output', default=None,
                        help='输出目录（默认为project/output）')
    args = parser.parse_args()

    output_dir = args.output or os.path.join(args.project, 'output')
    outline_dir = os.path.join(output_dir, '写作大纲')

    # 收集所有章节配置
    chapters = {}
    for ch_num in range(1, 20):
        guide_path = os.path.join(outline_dir, f'writing-guide-ch{ch_num}.md')
        if not os.path.exists(guide_path):
            continue

        with open(guide_path, 'r', encoding='utf-8') as f:
            guide_content = f.read()

        # 找对应章节文件
        chapter_file = None
        for fn in os.listdir(output_dir):
            if fn.startswith(f"第{ch_num}章") and fn.endswith(".md"):
                chapter_file = fn
                break

        chapters[ch_num] = {
            'guide_content': guide_content,
            'chapter_file': chapter_file,
            'guide_path': guide_path,
        }

    results = []
    print("=" * 100)
    print(f"章   |   大小KB   |  公式  | Mermaid |  表格  |  例题  |  案例  | 小结  | 习题  |  图表 ")
    print("=" * 100)

    for ch_num in sorted(chapters.keys()):
        cfg = chapters[ch_num]
        guide = cfg['guide_content']
        chapter_file = cfg['chapter_file']

        if chapter_file:
            chapter_path = os.path.join(output_dir, chapter_file)
            with open(chapter_path, 'r', encoding='utf-8') as f:
                chapter_content = f.read()
            file_size_kb = len(chapter_content.encode('utf-8')) / 1024
            stats = analyze_chapter(chapter_content)

            # 检查各节覆盖
            sections = parse_outline_sections(guide)
            targets = parse_section_targets(guide)
            section_coverage = {}
            for snum, _ in sections:
                section_coverage[snum] = '已覆盖' if snum in chapter_content else '未覆盖'

            result = {
                'chapter': ch_num,
                'chapter_file': chapter_file,
                'status': '已撰写',
                'file_size_kb': round(file_size_kb, 1),
                'section_coverage': section_coverage,
                'section_targets': targets,
                'blind_spots': parse_blind_spots(guide),
                'specific_reqs': parse_specific_reqs(guide)[:15],
                'unmet_rules': parse_unmet_rules(guide),
            }
            result.update(stats)
        else:
            result = {
                'chapter': ch_num,
                'status': '未撰写',
                'blind_spots': parse_blind_spots(guide),
                'specific_reqs': parse_specific_reqs(guide)[:15],
                'unmet_rules': parse_unmet_rules(guide),
            }

        results.append(result)

        if result['status'] == '未撰写':
            print(f"第{ch_num}章 |      N/A     |    0 |       0 |    0 |    0 |    0 |   ✗ |   ✗ |    0")
        else:
            has_s = '✓' if result['has_summary'] else '✗'
            has_e = '✓' if result['has_exercise'] else '✗'
            print(f"第{ch_num}章 | {str(result['file_size_kb']):>8} | {str(result['formula_count']):>4} | {str(result['mermaid_count']):>7} | {str(result['table_count']):>4} | {str(result['example_count']):>4} | {str(result['case_count']):>4} | {has_s:>3} | {has_e:>3} | {str(result['fig_count']):>4}")

    # 生成详细报告
    report_path = build_report(results, output_dir)

    # 写入JSON清单
    json_path = os.path.join(output_dir, '补充执行清单.json')
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n详细报告: {report_path}")
    print(f"执行清单: {json_path}")

    # 汇总统计
    total = len(results)
    written = sum(1 for r in results if r['status'] == '已撰写')
    missing_sections = sum(1 for r in results for a in r.get('actions', []) if a.get('type') == 'missing_section') if 'actions' in results[0] else \
        sum(len([k for k,v in r.get('section_coverage',{}).items() if v=='未覆盖']) for r in results if r['status']=='已撰写')
    missing_cases = sum(1 for r in results if r['status']=='已撰写' and r.get('case_count',0) < 2)
    missing_examples = sum(1 for r in results if r['status']=='已撰写' and r.get('example_count',0) < 2)
    missing_summaries = sum(1 for r in results if r['status']=='已撰写' and not r.get('has_summary'))
    print(f"\n{'='*60}")
    print(f"汇总: {total}章, {written}章已写, {total-written}章未写")
    print(f"  缺失小节: {missing_sections}")
    print(f"  案例不足: {missing_cases}章")
    print(f"  例题不足: {missing_examples}章")
    print(f"  缺小结: {missing_summaries}章")

if __name__ == '__main__':
    main()
