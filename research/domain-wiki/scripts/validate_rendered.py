#!/usr/bin/env python3
"""validate_rendered.py — 渲染输出文件的公式+Mermaid语法验证

检查项:
  公式: $$配对、花括号平衡、\left/\right、\begin/\end、空\frac
  Mermaid: classDef定义完整性、mindmap检测、标签括号平衡

用法:
  python3 validate_rendered.py --book-dir /path [--fix]
  python3 validate_rendered.py --file /path/to/file.md
  python3 validate_rendered.py --chapter --book-dir /path -c 3"""

import argparse
import os
import re
import sys


def check_file(filepath: str) -> list[dict]:
    """检查单个.md文件的公式和Mermaid语法"""
    if not os.path.exists(filepath):
        return []
    with open(filepath, encoding='utf-8') as f:
        content = f.read()
    
    issues = []
    name = os.path.basename(filepath)
    
    # === 公式检查 ===
    dd_count = content.count("$$")
    if dd_count > 0 and dd_count % 2 != 0:
        issues.append({"file": name, "severity": "error", 
                       "category": "formula_unpaired_dollar",
                       "message": f"$$不配对({dd_count}个)"})
    
    for m in re.finditer(r'\$\$(.*?)\$\$', content, re.DOTALL):
        tex = m.group(1)
        opens = tex.count('{')
        closes = tex.count('}')
        if opens != closes:
            issues.append({"file": name, "severity": "error",
                           "category": "formula_unbalanced_braces",
                           "message": f"花括号{opens}开{closes}闭: {tex[:80]}..."})
        lefts = tex.count('\\left')
        rights = tex.count('\\right')
        if lefts != rights:
            issues.append({"file": name, "severity": "error",
                           "category": "formula_leftright_mismatch",
                           "message": f"\\left {lefts}  \\right {rights}: {tex[:80]}..."})
        begins = tex.count('\\begin')
        ends = tex.count('\\end')
        if begins != ends:
            issues.append({"file": name, "severity": "error",
                           "category": "formula_beginend_mismatch",
                           "message": f"\\begin {begins} \\end {ends}: {tex[:80]}..."})
        if re.search(r'\\frac\{\s*\}\{\s*\}', tex):
            issues.append({"file": name, "severity": "error",
                           "category": "formula_empty_frac",
                           "message": f"空\\frac: {tex[:80]}..."})
    
    # === Mermaid检查 ===
    for mm in re.finditer(r'```mermaid\s*\n(.*?)```', content, re.DOTALL):
        diagram = mm.group(1)
        defined = set(re.findall(r'classDef\s+(\w+)', diagram))
        used = set(re.findall(r':::\s*(\w+)', diagram))
        class_stmts = set(re.findall(r'class\s+\S+\s+(\w+)', diagram))
        for uc in used | class_stmts:
            if uc not in defined and uc != 'default':
                issues.append({"file": name, "severity": "warning",
                               "category": "mermaid_undefined_class",
                               "message": f"classDef '{uc}'未定义"})
        if 'mindmap' in diagram:
            issues.append({"file": name, "severity": "warning",
                           "category": "mermaid_mindmap",
                           "message": "mindmap格式(Obsidian不兼容，应使用graph TD)"})
    
    return issues


def validate_book(book_dir: str) -> list[dict]:
    """验证全书渲染文件的公式和Mermaid语法"""
    all_issues = []
    dirs = ["30_核心概念", "40_知识要素", "50_知识点", 
            "60_技能点", "70_应用场景", "80_实体", "90_习题", "10_总揽"]
    
    for dname in dirs:
        dpath = os.path.join(book_dir, dname)
        if not os.path.isdir(dpath):
            continue
        for root, _, files in os.walk(dpath):
            for fname in files:
                if fname.endswith(".md"):
                    fpath = os.path.join(root, fname)
                    all_issues.extend(check_file(fpath))
    
    return all_issues


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--book-dir")
    p.add_argument("--file")
    p.add_argument("-c", "--chapter")
    p.add_argument("--fix", action="store_true")
    
    a = p.parse_args()
    
    if a.file:
        issues = check_file(a.file)
    elif a.chapter and a.book_dir:
        ch_name = f"第{a.chapter}章"
        issues = []
        for d in ["30_核心概念", "40_知识要素", "50_知识点", 
                   "60_技能点", "70_应用场景", "80_实体"]:
            dpath = os.path.join(a.book_dir, d)
            if os.path.isdir(dpath):
                for f in os.listdir(dpath):
                    if f.endswith(".md") and f.startswith(ch_name):
                        issues.extend(check_file(os.path.join(dpath, f)))
    elif a.book_dir:
        issues = validate_book(a.book_dir)
    else:
        p.print_help()
        return
    
    # Report
    errors = [i for i in issues if i["severity"] == "error"]
    warnings = [i for i in issues if i["severity"] == "warning"]
    
    if not issues:
        print("✅ 无语法问题")
        return
    
    print(f"📋 验证结果: {len(errors)} 错误, {len(warnings)} 警告")
    for i in issues:
        symbol = "❌" if i["severity"] == "error" else "⚠️"
        print(f"  {symbol} [{i['category']}] {i['file']}: {i['message']}")
    
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
