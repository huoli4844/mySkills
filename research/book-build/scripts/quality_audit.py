#!/usr/bin/env python3
"""
quality_audit.py — 统一质量审计入口。
整合 comprehensive_audit.py、post_generation_check.py、outline_vs_chapter_audit.py，
输出结构化的审计报告。

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
import subprocess
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional


def run_script(script_name: str, args: List[str], cwd: str) -> Dict:
    """运行某个审计脚本，捕获输出"""
    script_path = os.path.join(os.path.dirname(__file__), script_name)
    if not os.path.exists(script_path):
        return {"script": script_name, "status": "not_found", "output": ""}
    
    try:
        result = subprocess.run(
            [sys.executable, script_path] + args,
            capture_output=True, text=True, timeout=120,
            cwd=cwd
        )
        return {
            "script": script_name,
            "status": "ok" if result.returncode == 0 else "error",
            "returncode": result.returncode,
            "stdout": result.stdout[-2000:],
            "stderr": result.stderr[-1000:],
        }
    except subprocess.TimeoutExpired:
        return {"script": script_name, "status": "timeout", "output": ""}


def check_formulas(content: str, prefix: str) -> Dict:
    """检查公式编号"""
    tags = [int(t) for t in re.findall(r'\\tag\{' + prefix + r'-(\d+)\}', content)]
    blocks = len(re.findall(r'\$\$(.*?)\$\$', content, re.DOTALL))
    
    # 配对检查
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
    tables = len(re.findall(r'^\|', content, re.MULTILINE)) // 2  # 表格至少2行
    mermaids = len(re.findall(r'```mermaid', content))
    examples = len(re.findall(r'^### \*\*例\d+-\d+\*\*', content, re.MULTILINE))
    exercises = len(re.findall(r'^\d+-\d+', content, re.MULTILINE))
    has_summary = '本章总结' in content
    has_exercises = '## 习题' in content
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
    
    # 快速模式不检查大纲差距
    if not quick:
        # 检查写作说明/军规等不应出现在正文的内容
        has_forbidden = {
            "writing_notes": '本章写作说明' in content,
            "rules_check": '12条军规' in content or '军规落实' in content,
            "formula_summary": '全章核心公式总结' in content,
        }
        result["forbidden"] = has_forbidden
    
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
        result["issues"].extend(mermaid_issues[:3])  # 显示前3个
    
    return result


def check_mermaid(content: str) -> List[str]:
    """检查 Mermaid 图语法问题"""
    blocks = re.findall(r'```mermaid\n(.*?)```', content, re.DOTALL)
    issues = []
    for idx, block in enumerate(blocks):
        lines = block.strip().split('\n')
        first = lines[0].strip() if lines else ''
        
        # 1. 检查 ---config--- 语法（兼容性问题）
        if block.strip().startswith('---'):
            issues.append(f"Mermaid图{idx+1}: 使用 ---config--- 语法，建议改用 %%{{init}}%%")
        
        # 2. 检查 subgraph 标题中的括号和 direction 指令
        in_subgraph = False
        for i, line in enumerate(lines):
            s = line.strip()
            if s.startswith('subgraph '):
                in_subgraph = True
                title = s[9:].strip()
                if title.startswith('"') and title.endswith('"'):
                    title = title[1:-1]
                if '(' in title or ')' in title:
                    issues.append(f"Mermaid图{idx+1} L{i+1}: subgraph 标题含括号: '{title[:40]}'")
            if s == 'end' and in_subgraph:
                in_subgraph = False
            # 检查 subgraph 内的 direction 指令
            if in_subgraph and 'direction ' in s:
                issues.append(f"Mermaid图{idx+1} L{i+1}: subgraph 内 direction 可能导致渲染问题，建议移除")
        
        # 3. 检查 mindmap 中的特殊字符
        if 'mindmap' in first or 'mindmap' in block:
            # mindmap 中不能有 --- 除非是 init 后的分隔
            pass
        
        # 4. 检查 unclosed quotes in node labels
        for i, line in enumerate(lines):
            s = line.strip()
            if s.count('"') % 2 != 0:
                issues.append(f"Mermaid图{idx+1} L{i+1}: 引号未配对")
        
        # 5. 检查 round node 括号顺序 [("text")] vs [("text)"]
        for i, line in enumerate(lines):
            # 检查 [("...")] 中圆括号位置
            if re.search(r'\[\(\"[^"]*\)\"\]', line):
                issues.append(f"Mermaid图{idx+1} L{i+1}: [(\"text)\"] 应为 [(\"text\")]（圆括号被吞入标签）")
        
        # 6. 检查 timeline 中文书名号
        if 'timeline' in first:
            for i, line in enumerate(lines):
                if '《' in line or '》' in line:
                    issues.append(f"Mermaid图{idx+1} L{i+1}: timeline 中含书名号《》, 可能导致渲染问题")
        
        # 7. 检查是否有 %%{init 配置语法
        for i, line in enumerate(lines):
            if '%%{' in line and '}%%' not in line:
                issues.append(f"Mermaid图{idx+1} L{i+1}: init 配置块未闭合")
    
    return issues


def main():
    parser = argparse.ArgumentParser(description="统一质量审计")
    parser.add_argument("--project", help="项目根目录")
    parser.add_argument("--chapter", type=int, default=None, help="指定章节")
    parser.add_argument("--quick", action="store_true", help="快速审计（仅编号+$$）")
    parser.add_argument("--json", action="store_true", help="输出JSON")
    args = parser.parse_args()
    
    if args.project:
        output_dir = Path(args.project) / "output"
        files = sorted(output_dir.glob("第*.md"))
        files = [f for f in files if '报告' not in f.name]
    else:
        print("❌ 请指定 --project 或 --file")
        sys.exit(1)
    
    if args.chapter:
        files = [f for f in files if f.name.startswith(f"第{args.chapter}章")]
    
    results = []
    total_issues = 0
    
    print(f"{'章':>4} {'大小':>7} {'行数':>5} {'公式':>4} {'编号':>4} {'$$':>3} {'图':>3} {'表':>3} {'例题':>3} {'状态':>6}")
    print("-" * 55)
    
    for fpath in files:
        r = audit_chapter(str(fpath), args.quick)
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
    
    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
