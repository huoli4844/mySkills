"""pipeline_auto_fix.py — 骨架解答自动修复函数

从 pipeline_auto.py 提取，v45.1。
"""

import os
import re


def _fix_solution_skeleton(sol_dir, book_id, book_name, ch):
    """自动修复骨架解答中的破 Mermaid 和断 wikilink。返回修复数。"""
    fixed = 0
    for sf in sorted(os.listdir(sol_dir)):
        if not sf.endswith(".md"):
            continue
        sf_path = os.path.join(sol_dir, sf)
        with open(sf_path, encoding="utf-8") as f:
            scontent = f.read()
        original = scontent
        # 修复1：删除空Mermaid块（```mermaid\n无\n```）
        new_content = re.sub(r"```mermaid\n[^\n]*\n无\n```", "无", scontent)
        # 修复2：Mermaid 块内 → 替换为 >（避免与箭头语法冲突）
        new_content = re.sub(
            r"(```mermaid\n.*?)→(.*?```)", lambda m: m.group(1) + ">" + m.group(2), new_content, flags=re.DOTALL
        )
        # 修复3：修复断wikilink — 用相对路径（布局无关，v45.1）
        new_content = new_content.replace(
            "[[01_领域/01_资料库/无/10_总揽/book_overview_无_无|《无》第无章]]",
            f"[[../../10_总揽/book_overview_{book_id}_0|《{book_name}》第{ch}章]]",
        )
        # 从解答文件名推导对应习题名
        ex_base = sf.replace(".md", "")
        ex_file_name = ex_base.replace("-解答_", "_") if "-解答_" in ex_base else ex_base.replace("-解答", "")
        new_content = new_content.replace("[[90_习题/无|无]]", f"[[90_习题/{ex_file_name}|{ex_file_name}]]")
        if new_content != original:
            with open(sf_path, "w", encoding="utf-8") as f:
                f.write(new_content)
            fixed += 1
    return fixed
