#!/usr/bin/env python3
"""
fix_common_issues.py — 修复质量检查自动化无法修复的共性问题。

用法:
    python3 scripts/fix_common_issues.py ~/Desktop/电磁兼容教材/output/

修复项:
    1. Mermaid 节点 emoji → 纯文字替代
    2. Mermaid 图缺图注 → 自动补 *图N-X：描述*
    3. 推导深度不足 → 检查后告警（需手动处理）
"""

import re
import sys
import os
import glob

# ── emoji → 纯文字映射 ──
EMOJI_MAP = {
    "✅": "通过", "❌": "不通过", "⚠️": "注意",
    "➡️": "指向", "⬅️": "反向", "⬆️": "上升", "⬇️": "下降",
    "🔴": "红色", "🟠": "橙色", "🟡": "黄色", "🟢": "绿色",
    "🔵": "蓝色", "🟣": "紫色", "⚪": "白色", "⚫": "黑色",
    "⭐": "重要", "🌟": "重点", "✨": "亮点",
    "★": "重要", "☆": "参考",
    "📌": "要点", "🔍": "查找", "💡": "提示",
    "✔": "通过", "✘": "不通过", "✳": "注意",
    "⬜": "空", "🟫": "棕色",
}

def fix_mermaid_emoji(text: str) -> str:
    """Mermaid 块中的 emoji 替换为纯文字。"""
    lines = text.split("\n")
    in_mermaid = False
    fixed_count = 0

    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped == "```mermaid":
            in_mermaid = True
        elif in_mermaid and stripped == "```":
            in_mermaid = False
        elif in_mermaid:
            original = line
            for emoji, replacement in EMOJI_MAP.items():
                if emoji in line:
                    line = line.replace(emoji, replacement)
            if line != original:
                fixed_count += 1
                lines[i] = line

    return "\n".join(lines), fixed_count


def fix_mermaid_captions(text: str) -> str:
    """在 Mermaid 图块后面缺少 *图N-X：描述* 时补上。

    策略：找到 Mermaid 块的闭合 ```，检查其后是否已有 *图 开头
    的图注，如果没有则在闭合行之后插入一行 *图N-XX：描述*。
    图号从文件中提取。
    """
    lines = text.split("\n")
    in_mermaid = False
    chapter_num = None
    fixed_count = 0
    mermaid_count = 0

    # 提取章号
    m = re.search(r"第\s*(\d+)\s*章", text)
    if m:
        chapter_num = int(m.group(1))

    # 获取当前最大图号
    existing_figs = re.findall(r"\*图" + (str(chapter_num) if chapter_num else r"\d+") + r"-(\d+)", text)
    fig_counter = max([int(x) for x in existing_figs]) if existing_figs else 0

    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped == "```mermaid":
            in_mermaid = True
            mermaid_count += 1
        elif in_mermaid and stripped == "```":
            in_mermaid = False
            # 检查闭合后 5 行内是否有图注
            has_caption = False
            for j in range(i + 1, min(i + 6, len(lines))):
                if re.match(r"\*图\d+-\d+", lines[j].strip()):
                    has_caption = True
                    break
                if lines[j].strip().startswith("#") or lines[j].strip().startswith("```"):
                    break
            if not has_caption and chapter_num:
                fig_counter += 1
                placeholder = f"\n*图{chapter_num}-{fig_counter}：示意图*\n"
                # 在闭合行后插入，注意后面的换行
                lines[i] = line + placeholder
                fixed_count += 1

    return "\n".join(lines), fixed_count


def check_derivation_depth(filepath: str) -> list:
    """检查推导深度，返回需要手动修复的位置列表。"""
    text = open(filepath, "r", encoding="utf-8").read()
    lines = text.split("\n")
    issues = []
    in_formula = False
    formula_positions = []
    formula_start = 0

    for i, line in enumerate(lines):
        if line.strip() == "$$":
            if in_formula:
                context_start = max(0, formula_start - 5)
                context = "\n".join(lines[context_start:formula_start])
                formula_positions.append((formula_start, context))
                in_formula = False
            else:
                formula_start = i
                in_formula = True

    derivation_hints = ["推导", "原理", "根据", "代入", "由式", "可得",
                        "得", "代入式", "由", "整理得", "即",
                        "因此", "所以", "故", "则", "于是", "由此"]

    consecutive_bare = 0
    for f_line, context in formula_positions:
        has_hint = any(hint in context for hint in derivation_hints)
        if has_hint:
            consecutive_bare = 0
        else:
            consecutive_bare += 1
        if consecutive_bare >= 3 and consecutive_bare % 3 == 0:
            issues.append((f_line + 1, consecutive_bare))

    return issues


def fix_file(filepath: str, dry_run: bool = False) -> dict:
    """对单个文件运行全部修复。"""
    print(f"\n{'='*60}")
    print(f"  修复: {os.path.basename(filepath)}")
    print(f"{'='*60}")

    text = open(filepath, "r", encoding="utf-8").read()
    original = text
    report = {"emoji": 0, "captions": 0, "derivation_issues": 0}

    # 1. emoji 修复
    text, emoji_count = fix_mermaid_emoji(text)
    report["emoji"] = emoji_count
    if emoji_count > 0:
        print(f"  ✅ Mermaid emoji 替换: {emoji_count} 处")

    # 2. 图注修复
    text, cap_count = fix_mermaid_captions(text)
    report["captions"] = cap_count
    if cap_count > 0:
        print(f"  ✅ 补Mermaid图注: {cap_count} 处")

    # 3. 推导深度检查（仅报告）
    derivation_issues = check_derivation_depth(filepath)
    report["derivation_issues"] = len(derivation_issues)
    if derivation_issues:
        print(f"  ⚠️ 推导深度不足 ({len(derivation_issues)} 处公式链)：")
        for line_no, count in derivation_issues[:5]:
            print(f"    L{line_no}: 连续{count}个公式无推导词")
        if len(derivation_issues) > 5:
            print(f"    ... 还有 {len(derivation_issues) - 5} 处")

    # 写入
    if not dry_run and text != original:
        open(filepath, "w", encoding="utf-8").write(text)
    elif text == original:
        print("  无需修改")

    return report


def main():
    import argparse
    parser = argparse.ArgumentParser(description="修复章节共性问题")
    parser.add_argument("path", help="文件或目录路径")
    parser.add_argument("--dry-run", "-n", action="store_true", help="预览模式")
    args = parser.parse_args()

    if os.path.isdir(args.path):
        files = sorted(glob.glob(os.path.join(args.path, "第*.md")))
    else:
        files = [args.path]

    if not files:
        print("❌ 未找到 .md 文件")
        sys.exit(1)

    totals = {"emoji": 0, "captions": 0, "derivation_issues": 0}
    for f in files:
        r = fix_file(f, dry_run=args.dry_run)
        for k in totals:
            totals[k] += r[k]

    print(f"\n{'='*60}")
    print(f"  汇总 ({len(files)} 文件)")
    print(f"{'='*60}")
    print(f"  Mermaid emoji 替换: {totals['emoji']} 处")
    print(f"  补Mermaid图注:     {totals['captions']} 处")
    print(f"  推导深度不足:      {totals['derivation_issues']} 处（需手动处理）")
    print(f"\n💡 推导深度修复建议：")
    print(f"   在连续公式链中插入推导文字，例如：")
    print(f"   '由式(N-M)可得'、'根据XXX原理'、'代入条件得'、'整理后得'")


if __name__ == "__main__":
    main()
