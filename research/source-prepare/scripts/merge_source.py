#!/usr/bin/env python3
"""
merge_source: 将 .docx 的正文 MD 与 .doc 的公式 LaTeX 融合，
生成完整的、公式可编辑的出处 MD 文件。

在 source-prepare 管线后使用：
  1. source-prepare .doc → _formulas/ (311 个 LaTeX 公式)
  2. source-prepare .docx → MD + assets/ (正文结构 + 图片)
  3. merge_source --md MD --formulas _formulas/latex/summary.json -o 融合后.md
"""
import argparse
import json
import re
import shutil
from pathlib import Path


def build_formula_map(summary_path: Path) -> list:
    """读取 formula-extract 的 summary.json，返回有序公式列表"""
    with open(summary_path) as f:
        data = json.load(f)
    formulas = sorted(data["formulas"], key=lambda x: int(x["name"].split("_")[1]))
    print(f"  📐 已加载 {len(formulas)} 个 LaTeX 公式")
    return formulas


def replace_wmf_with_latex(md_content: str, formulas: list) -> str:
    """
    将 MD 中的 ![](assets/image-xxx.wmf) 或 ![image](assets/image-xxx.png) 
    顺序替换为 $latex$ 公式。

    策略：
    - 独立成行（仅含图片引用 + 可选编号标签）→ $$ 块级
    - 与文本混排 → $ 行内
    """
    # 支持 .wmf（来自 .doc 融合）和 .png/.jpeg/.jpg（来自 .docx 图片公式）
    pattern = re.compile(r'!\[(?:image|)\]\(assets/image-\d+\.(?:wmf|png|jpe?g)\)')
    matches = pattern.findall(md_content)

    print(f"  🔍 发现 {len(matches)} 个 WMF 图片引用")
    print(f"  📐 可用公式 {len(formulas)} 个")

    lines = md_content.split('\n')
    formula_idx = 0
    new_lines = []
    skipped = []

    for line in lines:
        wmf_in_line = pattern.findall(line)
        if not wmf_in_line:
            new_lines.append(line)
            continue

        for wmf in wmf_in_line:
            if formula_idx >= len(formulas):
                skipped.append(wmf)
                line = line.replace(wmf, '', 1)
                continue

            latex = formulas[formula_idx]["latex"]
            formula_idx += 1

            wmf_count_in_line = len(wmf_in_line)
            if wmf_count_in_line == 1:
                # 单 WMF 行：判断是否独立
                rest = line.replace(wmf, '', 1).strip()
                label_match = re.match(r'^\([\d\w\-,]+\)\s*$', rest)
                if label_match or not rest:
                    # 独立公式 → 块级
                    replacement = f"$$ {latex} $$"
                    line = line.replace(wmf, replacement, 1)
                    line = re.sub(r'\s*\([\d\w\-,]+\)\s*$', '', line)
                else:
                    replacement = f"${latex}$"
                    line = line.replace(wmf, replacement, 1)
            else:
                # 多 WMF 行 → 行内
                replacement = f"${latex}$"
                line = line.replace(wmf, replacement, 1)

        new_lines.append(line)

    result = '\n'.join(new_lines)

    print(f"  ✅ 已替换 {formula_idx} 个公式")
    if skipped:
        print(f"  ⚠️  {len(skipped)} 个 WMF 无对应公式（跳过）")

    return result


def fix_formulas(md_content: str) -> str:
    """
    清理 LaTeX 公式中的常见兼容性问题，确保在 Typora/KaTeX/GitHub 等
    标准渲染器中可显示。

    修复项:
    1. \\wideparen{n} → \\hat{n}（非标命令）
    2. \\frac{num}{} → num（空分母，MTEF 解析伪影）
    3. \\left\\uf048 / \\right\\uf049 → \\left( / \\right)（Unicode 损坏）
    4. $$ formula $$（单行块级）→ $$\\nformula\\n$$（Typora 兼容多行格式）
    """
    fixes = 0

    # Fix 1: \wideparen{n} → \hat{n}
    count = 0
    while '\\wideparen' in md_content:
        md_content = re.sub(r'\\wideparen\{([^}]*)\}', r'\\hat{\1}', md_content)
        count += 1
    if '\\wideparen' in md_content:
        md_content = md_content.replace('\\wideparen', '\\hat')
        count += 1
    fixes += count

    # Fix 2: \frac{num}{} → num（空分母）
    empty_frac = re.findall(r'\\frac\{([^}]*)\}\{\}', md_content)
    for num in set(empty_frac):
        md_content = md_content.replace(r'\frac{' + num + r'}{}', num)
        fixes += 1

    # Fix 3: 损坏的 \left / \right 分隔符
    for broken in ["\uF048", "\uF049"]:
        for cmd in ['left', 'right']:
            c = md_content.count(f"\\{cmd}{broken}")
            if c:
                md_content = md_content.replace(f"\\{cmd}{broken}", f"\\{cmd}(")
                fixes += c

    # Fix 4: 单行 $$ formula $$ → 多行 $$\\nformula\\n$$
    # 匹配 $$ ... $$ 在一行内的情况
    count_single = 0
    def _to_multiline(m):
        nonlocal count_single
        count_single += 1
        content = m.group(1).strip()
        return f"$$\n{content}\n$$"
    md_content = re.sub(r'^\$\$\s*(.+?)\s*\$\$$', _to_multiline, md_content, flags=re.MULTILINE)
    if count_single > 0:
        fixes += count_single
        print(f"  📐 已转换 {count_single} 个块级公式为 Typora 兼容格式")

    return md_content


def copy_non_wmf_assets(src_dir: Path, dst_dir: Path):
    """复制非 WMF 的 assets（保留实际插图/照片）"""
    if not src_dir.exists():
        print("  ℹ️  assets 目录不存在，跳过")
        return

    dst_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    for f in src_dir.iterdir():
        if f.is_file() and f.suffix.lower() not in ('.wmf',):
            shutil.copy2(f, dst_dir / f.name)
            count += 1
    print(f"  🖼️  已复制 {count} 个非公式图片（插图/照片）")


def main():
    parser = argparse.ArgumentParser(
        description="融合 .docx 正文 MD 与 .doc 公式 LaTeX → 完整出处 MD"
    )
    parser.add_argument("--md", required=True, help="file2md 输出的 MD 文件路径")
    parser.add_argument("--formulas", required=True,
                        help="formula-extract 的 latex/summary.json 路径")
    parser.add_argument("-o", "--output", required=True, help="输出 MD 路径")
    parser.add_argument("--assets", help="源 assets 目录（用于复制非公式图片）")
    parser.add_argument("--no-assets-copy", action="store_true",
                        help="不复制 assets")
    args = parser.parse_args()

    md_path = Path(args.md).resolve()
    formulas_path = Path(args.formulas).resolve()

    if not md_path.exists():
        print(f"❌ 文件不存在: {md_path}")
        return 1
    if not formulas_path.exists():
        print(f"❌ 文件不存在: {formulas_path}")
        return 1

    output_path = Path(args.output).resolve()
    output_dir = output_path.parent
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"📄 源 MD: {md_path.name}")
    print(f"📐 公式: {formulas_path.name}")
    print(f"📁 输出: {output_path}")

    # 1. 加载公式
    formulas = build_formula_map(formulas_path)

    # 2. 读取并替换
    md_content = md_path.read_text(encoding='utf-8')
    merged = replace_wmf_with_latex(md_content, formulas)

    # 3. 公式兼容性修复
    merged = fix_formulas(merged)

    # 4. 复制非公式图片
    if args.assets and not args.no_assets_copy:
        copy_non_wmf_assets(Path(args.assets).resolve(), output_dir / "assets")

    # 5. 写入
    output_path.write_text(merged, encoding='utf-8')
    lines = merged.count('\n') + 1
    print(f"\n✅ 融合完成！{output_path} ({lines} 行)")


if __name__ == "__main__":
    main()
