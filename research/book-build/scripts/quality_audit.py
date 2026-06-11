#!/usr/bin/env python3
"""
quality_audit.py — 统一质量审计入口。

所有审计函数在此单文件内，不再分散到独立脚本。
所有审计函数集中管理，不再分散到独立脚本。
但保持函数独立、可复用，不再互相调用。

用法：
  python3 scripts/quality_audit.py --project /path/to/教材              # 全量审计
  python3 scripts/quality_audit.py --project /path/to/教材 --chapter 7  # 单章
  python3 scripts/quality_audit.py --project /path/to/教材 --quick      # 快速（仅编号+$$）
"""

import os
import re
import sys
import json
import argparse
from pathlib import Path
from typing import List, Dict, Optional


def check_formulas(content: str, prefix: str) -> Dict:
    """检查公式编号"""
    tags = [int(t) for t in re.findall(r'\\tag\{' + prefix + r'-(\d+)\}', content)]
    blocks = len(re.findall(r'\$\$(.*?)\$\$', content, re.DOTALL))

    # 配对检查（行级状态机，处理 >$$ 格式）
    in_math = False
    for line in content.split('\n'):
        s = line.strip()
        if s == '$$' or s == '> $$':
            in_math = not in_math

    return {
        "formula_blocks": blocks,
        "formula_tags": len(tags),
        "tags_continuous": tags == list(range(1, len(tags)+1)) if tags else True,
        "dollars_paired": not in_math,
        "orphan_tags": 0,
    }


def check_content_stats(content: str) -> Dict:
    """检查内容统计"""
    tables = len(re.findall(r'^\|', content, re.MULTILINE)) // 2
    mermaids = len(re.findall(r'```mermaid', content))
    examples = len(re.findall(r'^### \*\*例\d+-\d+\*\*', content, re.MULTILINE))
    exercises = len(re.findall(r'^\d+-\d+', content, re.MULTILINE))
    has_summary = '本章总结' in content
    has_exercises = '## 习题' in content or '思考题' in content
    has_refs = '## 参考文献' in content

    return {
        "tables": max(0, tables),
        "mermaids": mermaids,
        "examples": examples,
        "exercises": exercises,
        "has_summary": has_summary,
        "has_exercises": has_exercises,
        "has_references": has_refs,
    }


# ============================================================
# 军规合规检查
# ============================================================

def check_second_person(content: str) -> List[str]:
    """检查正文中是否使用第二人称'你'（习题前）"""
    issues = []
    if '## 习题' in content:
        before_exam = content.split('## 习题')[0]
        for line in before_exam.split('\n'):
            if '你' in line:
                issues.append(f"正文含第二人称'你': {line.strip()[:80]}")
    return issues


def check_step_markers(content: str) -> List[str]:
    """检查是否存在Step标记（应为'第一步/第二步'等学术表述）"""
    issues = []
    match = re.search(r'Step\s+\d', content)
    if match:
        issues.append(f"存在Step标记: '{match.group(0)}'")
    return issues


def check_summary_count(content: str) -> List[str]:
    """检查小结条目数（必须恰好6条）"""
    issues = []
    if '## 本章总结' not in content:
        return issues  # 无小结不算军规违规

    summary_match = re.search(r'## 本章总结(.*?)## 习题', content, re.DOTALL)
    if not summary_match:
        return issues

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
        issues.append(f"小结条目数{count}，应为6条")
    return issues


def check_placeholders(content: str) -> List[str]:
    """检查占位符"""
    issues = []
    placeholders = ['[待补充]', '[TODO]', '[请填写]', '[补充]', '[占位]']
    for ph in placeholders:
        if ph in content:
            issues.append(f"存在占位符: {ph}")
    return issues


def check_footnotes_format(content: str) -> List[str]:
    """检查参考文献格式"""
    issues = []
    if '## 参考文献' not in content:
        issues.append("缺少参考文献章节")
        return issues

    ref_section = content.split('## 参考文献')[1].split('##')[0] if '## 深入阅读' in content else content.split('## 参考文献')[1]
    refs = re.findall(r'\[\s*[MS]\s*\]', ref_section)
    if not refs:
        issues.append("参考文献缺少[M]或[S]标识")
    return issues


def check_dollar_pairing(content: str) -> List[str]:
    """检查$$配对"""
    issues = []
    dollar_count = content.count('$$')
    if dollar_count % 2 != 0:
        issues.append(f"奇数个$$（{dollar_count}个），存在未闭合公式块")
    return issues


def check_tag_chapter_prefix(content: str, chapter: int) -> List[str]:
    """检查公式标签章号前缀"""
    issues = []
    tags = re.findall(r'\\tag\{(\d+)-(\d+)\}', content)
    wrong = []
    for major, minor in tags:
        if major != str(chapter):
            wrong.append(f"\\tag{{{major}-{minor}}}")
    if wrong:
        issues.append(f"公式标签章号错误: {', '.join(wrong[:5])}")
    return issues


# ============================================================
# 写作规范检查
# ============================================================

def check_professor_quality(content: str) -> List[str]:
    """检查教授级写作质量指标"""
    issues = []

    # 1. 设问引导（每节至少1个"为什么/如何"）
    sections = re.split(r'^## \d+\.', content, flags=re.MULTILINE)
    for i, sec in enumerate(sections[1:], 1):
        if '为什么' not in sec and '如何' not in sec:
            issues.append(f"§{i} 缺少设问引导句（为什么/如何）")

    # 2. 工程直觉提示词
    intuition_words = ['值得注意的是', '关键在于', '本质上', '工程启示']
    if not any(w in content for w in intuition_words):
        issues.append("全章缺少工程直觉提示词")

    # 3. 教学视角
    teaching_words = ['读者', '初学者', '在学习中', '建议读者', '值得思考']
    if sum(content.count(w) for w in teaching_words) < 3:
        issues.append("教学视角提示不足（建议≥3处）")

    return issues


def check_learning_objectives(content: str) -> List[str]:
    """检查学习目标是否被正文覆盖"""
    issues = []
    patterns = [
        r'通过本章学习，读者(?:应)?(?:达成以下学习目标|掌握以下内容|应掌握)(.*?)(?=\n\s*\n---|\n\s*\n##|\Z)',
        r'本章学习目标如下：(.*?)(?=\n\s*\n---|\n\s*\n##|\Z)',
    ]

    obj_section = None
    for p in patterns:
        obj_section = re.search(p, content, re.DOTALL)
        if obj_section:
            break

    if not obj_section:
        idx = content.find('## 内容提要')
        if idx >= 0:
            after = content[idx:idx+2000]
            numbered = re.findall(r'^\d+\.\s+\S', after, re.MULTILINE)
            if len(numbered) >= 3:
                return []
        return ["未找到学习目标"]

    obj_text = obj_section.group(1)
    objectives = re.findall(r'\d+\.\s*(.*?)(?=\n\s*\d+\.|\Z)', obj_text, re.DOTALL)
    if not objectives:
        objectives = [obj_text.strip()]

    for i, obj in enumerate(objectives):
        obj_clean = obj.strip()[:80]
        keywords = re.findall(r'[A-Za-z\u4e00-\u9fff\u0391-\u03c9]{2,}', obj)
        missing_kw = [kw for kw in keywords if len(kw) > 2 and kw not in content]
        if len(missing_kw) > len(keywords) * 0.5:
            issues.append(f"学习目标{i+1}: \"{obj_clean}\" 可能未被正文覆盖")

    return issues


def check_mermaid(content: str) -> List[str]:
    """检查 Mermaid 图语法问题"""
    blocks = re.findall(r'```mermaid\n(.*?)```', content, re.DOTALL)
    issues = []
    for idx, block in enumerate(blocks):
        lines = block.strip().split('\n')
        first = lines[0].strip() if lines else ''

        # 1. ---config--- 语法
        if block.strip().startswith('---'):
            issues.append(f"Mermaid图{idx+1}: 使用 ---config--- 语法")

        # 2. subgraph 标题括号 + direction
        in_subgraph = False
        for i, line in enumerate(lines):
            s = line.strip()
            if s.startswith('subgraph '):
                in_subgraph = True
                title = s[9:].strip()
                if title.startswith('"') and title.endswith('"'):
                    title = title[1:-1]
                if '(' in title or ')' in title:
                    issues.append(f"Mermaid图{idx+1} L{i+1}: subgraph 标题含括号")
            if s == 'end' and in_subgraph:
                in_subgraph = False
            if in_subgraph and 'direction ' in s:
                issues.append(f"Mermaid图{idx+1} L{i+1}: subgraph 内 direction")

        # 3. 引号配对
        for i, line in enumerate(lines):
            if line.count('"') % 2 != 0:
                issues.append(f"Mermaid图{idx+1} L{i+1}: 引号未配对")

        # 4. 圆边节点
        for i, line in enumerate(lines):
            if re.search(r'\[\(""[^\"]*\)\"\]', line):
                issues.append(f"Mermaid图{idx+1} L{i+1}: 圆边节点括号位置错误")

        # 5. emoji 检测
        emoji_pattern = re.compile(
            r'[\U0001F300-\U0001FAFF\u2600-\u27BF\u2B50\uFE00-\uFE0F\u2702-\u27B0]'
        )
        for i, line in enumerate(lines):
            if emoji_pattern.search(line):
                issues.append(f"Mermaid图{idx+1} L{i+1}: 含 emoji")
            if '⭐' in line:
                issues.append(f"Mermaid图{idx+1} L{i+1}: 含星号 ⭐")

        # 6. 禁用语法
        if 'timeline' in block:
            issues.append(f"Mermaid图{idx+1}: 使用 timeline 语法")
        if 'mindmap' in block:
            issues.append(f"Mermaid图{idx+1}: 使用 mindmap 语法")
        if '%%{' in block:
            issues.append(f"Mermaid图{idx+1}: 使用 %%{{init}}%% 配置")
        if '<-->' in block:
            issues.append(f"Mermaid图{idx+1}: 使用 <--> 双向箭头")

    return issues


def check_figure_captions(content: str) -> List[str]:
    """检查图注位置（图注应在Mermaid下方，表题在表格上方）"""
    issues = []
    mermaid_blocks = re.findall(r'```mermaid\n(.*?)```', content, re.DOTALL)
    for idx, block in enumerate(mermaid_blocks):
        block_start = content.find(block)
        if block_start < 0:
            continue
        after = content[block_start + len(block) + 3:block_start + len(block) + 103]
        caption = re.search(r'\*图[\d\-]+[^*]+\*', after)
        if not caption:
            issues.append(f"Mermaid图{idx+1} 缺少图注（应在图下方加 *图X-Y 标题*）")
        elif after.find(caption.group()) > 50:
            issues.append(f"Mermaid图{idx+1} 图注距离图太远")
    return issues


def check_technical_depth(content: str, chapter: int) -> List[str]:
    """检查技术深度（第1章：电尺寸/窄宽带/术语体系/兼容电平图）"""
    issues = []
    if chapter == 1:
        depth_checks = {
            '电尺寸概念': ['电尺寸', 'λ/10', 'k = l/λ'],
            '窄带/宽带分类': ['窄带', '宽带', '百分比带宽'],
            '术语体系': ['术语', '核心术语'],
            '兼容电平图': ['兼容电平', '发射限值', '抗扰度限值'],
        }
        missing = []
        for name, kws in depth_checks.items():
            if not any(kw in content for kw in kws):
                missing.append(name)
        if missing:
            issues.append(f"缺技术深度内容: {', '.join(missing)}")
    return issues


def check_forbidden_content(content: str) -> Dict:
    """检查不应出现在正文的内容（军规检查/写作说明等）"""
    return {
        "writing_notes": '本章写作说明' in content,
        "rules_check": '12条军规' in content or '军规落实' in content,
        "formula_summary": '全章核心公式总结' in content,
    }


# ============================================================
# 审计入口
# ============================================================

def audit_chapter(fpath: str, quick: bool = False) -> Dict:
    """审计单章"""
    with open(fpath, 'r', encoding='utf-8') as f:
        content = f.read()

    ch = re.search(r'第(\d+)章', os.path.basename(fpath))
    if not ch:
        return {"file": fpath, "error": "无法识别章节号"}
    prefix = ch.group(1)

    lines = content.count('\n') + 1
    size_kb = os.path.getsize(fpath) / 1024

    result = {
        "chapter": int(prefix),
        "file": os.path.basename(fpath),
        "size_kb": round(size_kb, 1),
        "lines": lines,
    }

    # 公式检查
    result["formulas"] = check_formulas(content, prefix)

    # 内容统计
    result["content"] = check_content_stats(content)

    # 军规合规检查（综合审计项）
    compliance = []
    compliance.extend(check_second_person(content))
    compliance.extend(check_step_markers(content))
    compliance.extend(check_summary_count(content))
    compliance.extend(check_placeholders(content))
    compliance.extend(check_footnotes_format(content))
    compliance.extend(check_dollar_pairing(content))
    compliance.extend(check_tag_chapter_prefix(content, int(prefix)))
    result["compliance"] = compliance

    # 快速模式不检查大纲差距和写作规范
    if not quick:
        # 禁止内容
        result["forbidden"] = check_forbidden_content(content)

    # 综合评分
    issues = []
    f = result["formulas"]
    if not f["dollars_paired"]:
        issues.append("$$ 未配对")
    if f["orphan_tags"] > 0:
        issues.append(f"{f['orphan_tags']}个孤立tag")
    if not f["tags_continuous"]:
        issues.append("编号不连续")
    if f["formula_tags"] < f["formula_blocks"]:
        issues.append(f"缺{f['formula_blocks']-f['formula_tags']}个编号")

    # 军规合规问题
    for c in compliance:
        issues.append(c)

    if not quick and result.get("forbidden"):
        for k, v in result["forbidden"].items():
            if v:
                issues.append(f"正文含{k}")

    result["issues"] = issues
    result["pass"] = len(issues) == 0

    # Mermaid 语法检查
    mermaid_issues = check_mermaid(content)
    result["mermaid_issues"] = mermaid_issues
    if mermaid_issues:
        result["pass"] = False
        result["issues"].extend(mermaid_issues[:3])

    # 学习目标覆盖检查
    obj_issues = check_learning_objectives(content)
    result["learning_objective_issues"] = obj_issues
    if obj_issues:
        result["pass"] = False
        result["issues"].extend(obj_issues[:3])

    # 图注位置检查
    fig_issues = check_figure_captions(content)
    result["figure_caption_issues"] = fig_issues
    if fig_issues:
        result["pass"] = False
        result["issues"].extend(fig_issues[:2])

    # 技术深度检查（第1章特有）
    td_issues = check_technical_depth(content, int(prefix))
    result["tech_depth_issues"] = td_issues
    if td_issues:
        result["pass"] = False
        result["issues"].extend(td_issues[:2])

    return result


def audit_project(project_path: str, chapter: Optional[int] = None,
                  quick: bool = False, output_json: bool = False) -> List[Dict]:
    """审计整个项目"""
    output_dir = Path(project_path) / "output"
    files = sorted(output_dir.glob("第*.md"))
    files = [f for f in files if '报告' not in f.name]

    if chapter:
        files = [f for f in files if f.name.startswith(f"第{chapter}章")]

    if not files:
        print(f"未找到章节文件: {output_dir}/第*.md")
        return []

    results = []
    total_issues = 0

    print(f"{'章':>4} {'大小':>7} {'行数':>5} {'公式':>4} {'编号':>4} {'$$':>3} {'图':>3} {'表':>3} {'例题':>3} {'状态':>6}")
    print("-" * 55)

    for fpath in files:
        r = audit_chapter(str(fpath), quick)
        results.append(r)

        f = r["formulas"]
        c = r["content"]
        status = "✅" if r["pass"] else f"❌ {r['issues'][0][:20]}"
        total_issues += len(r["issues"])

        print(f" 第{r['chapter']:>2}章 {r['size_kb']:>6.0f}KB {r['lines']:>5} "
              f"{f['formula_blocks']:>3}/{f['formula_tags']:>3} "
              f"{'✅' if f['dollars_paired'] else '❌'} "
              f"{'✅' if f['tags_continuous'] else '❌'} "
              f"{c['mermaids']:>2} {c['tables']:>2} {c['examples']:>2} "
              f"{status}")

    passed = sum(1 for r in results if r["pass"])
    print(f"\n--- 汇总 ---")
    print(f"审计: {len(results)} 章 | 通过: {passed} | 问题: {total_issues}")
    print(f"公式: {sum(r['formulas']['formula_tags'] for r in results)} 个")

    if output_json:
        print(json.dumps(results, ensure_ascii=False, indent=2))

    return results


def main():
    parser = argparse.ArgumentParser(description="统一质量审计")
    parser.add_argument("--project", help="项目根目录")
    parser.add_argument("--chapter", type=int, default=None, help="指定章节")
    parser.add_argument("--quick", action="store_true", help="快速审计（仅编号+$$）")
    parser.add_argument("--json", action="store_true", help="输出JSON")
    args = parser.parse_args()

    if not args.project:
        print("❌ 请指定 --project")
        sys.exit(1)

    audit_project(args.project, args.chapter, args.quick, args.json)


if __name__ == "__main__":
    main()
