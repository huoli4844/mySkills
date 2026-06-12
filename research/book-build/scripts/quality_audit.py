#!/usr/bin/env python3
"""
quality_audit.py — 统一质量审计入口。
审计检查函数在 quality_audit_checks.py 中管理。
用法：
  python3 scripts/quality_audit.py --project /path/to/教材
  python3 scripts/quality_audit.py --project /path/to/教材 --chapter 7
  python3 scripts/quality_audit.py --project /path/to/教材 --quick
"""

import os
import re
import sys
import json
import argparse
from pathlib import Path
from typing import List, Dict, Optional
from quality_audit_checks import (
    check_formulas, check_content_stats, check_second_person,
    check_step_markers, check_summary_count, check_placeholders,
    check_footnotes_format, check_dollar_pairing, check_tag_chapter_prefix,
    check_professor_quality, check_learning_objectives, check_mermaid,
    check_figure_captions, check_technical_depth, check_forbidden_content,
)

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
    # 中间推导步骤的辅助公式不需要编号（“辅助公式直接给出，不自创编号”）
    # 仅公式块>标签数但差值超过4个时才警告（1-2个中间步骤属正常推导）
    missing = f['formula_blocks'] - f['formula_tags']
    if f["formula_tags"] < f["formula_blocks"] and not f.get("has_derivation"):
        if missing > 4:
            issues.append(f"缺{missing}个编号")

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
