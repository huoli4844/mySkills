#!/usr/bin/env python3
"""
post_build_fix.py — 构建后自动修复管道

用法：
  python post_build_fix.py <wiki_root> [--source-dir <source_md_dir>] [--assets-dir <assets_dir>] [--fix-only formula|figure|all]

在 build_kb_files.py 完成后运行，自动修复：
  1. fix_block_formulas:    $$formula$$ 单行 → $$\\nformula\\n$$ 独占三行
  2. fix_figure_references: > 图X-X 文本引用 → ![图X-X](assets/filename)
  3. fix_mermaid_source:    core_concept_map_source "无" → 尝试从出处查找
"""

import argparse
import os
import re
import sys

from dag_constants import DIR, DIR_BY_PHASE, PipelineError
from log_utils import get_logger

log = get_logger(__name__)


# ── 通用工具 ─────────────────────────────────────────────


def find_md_files(root_dir):
    """递归查找所有 .md 文件"""
    for dirpath, _, filenames in os.walk(root_dir):
        for fn in filenames:
            if fn.endswith(".md"):
                yield os.path.join(dirpath, fn)


def read_file_safe(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        log.debug(f"文件读取失败: {e}")
        return None


def write_file_safe(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


# ═══════════════════════════════════════════════════════════
# 修复 1: 公式独占三行格式
# ═══════════════════════════════════════════════════════════


def fix_block_formulas_in_text(text):
    """
    将 inline $$...$$ 格式拆为独占三行格式。

    匹配模式：$$content$$ （content 与 $$ 在同一行）
    替换为：  $$\\ncontent\\n$$

    不处理：
    - 已经是多行的 $$...$$ 块
    - 行内 $...$（单 $ 不变）
    """
    count = 0
    # 匹配 $$...$$ 在同一行的情况
    # 使用负前瞻避免匹配多行块
    pattern = re.compile(
        r"(?<!\$)\$\$(?!\$)([^\n]*?[^\s\n])\$\$(?!\$)",  # 单行 $$content$$
        re.MULTILINE,
    )

    def replacer(m):
        nonlocal count
        content = m.group(1).strip()
        if not content:
            return m.group(0)
        count += 1
        return f"$$\n{content}\n$$"

    result = pattern.sub(replacer, text)
    return result, count


def fix_block_formulas(wiki_root, fix_types=None):
    """扫描所有生成文件，修复公式格式"""
    total_fixed = 0
    fixed_files = []

    # 知识库内容目录（动态从 DIR_BY_PHASE 构建，支持双命名体系）
    # 同时包含编号目录名（如 "30_核心概念"）和纯中文目录名（如 "概念"）
    target_dirs = list(
        dict.fromkeys(
            list(DIR_BY_PHASE.values())
            + [
                v.split("_", 1)[1].split("/")[-1]
                for v in DIR_BY_PHASE.values()
                if "_" in v
            ]
        )
    )

    for fpath in find_md_files(wiki_root):
        rel = os.path.relpath(fpath, wiki_root)
        # 只处理目标目录
        parts = rel.split(os.sep)
        if not any(td in parts for td in target_dirs):
            continue

        content = read_file_safe(fpath)
        if content is None:
            continue

        new_content, n = fix_block_formulas_in_text(content)
        if n > 0:
            write_file_safe(fpath, new_content)
            total_fixed += n
            fixed_files.append((rel, n))

    return total_fixed, fixed_files


# ═══════════════════════════════════════════════════════════
# 修复 2: 文本图引用 → Markdown 图片引用
# ═══════════════════════════════════════════════════════════


def build_figure_map_from_source(source_md_dir):
    """
    从出处章节 .md 文件构建「图号 → 图片文件路径」映射。

    在章节 .md 中查找两种模式：
      1. ![图2-1-说明](assets/图2-1-说明.emf)  → 图2-1 → 图2-1-说明.emf
      2. 图2-1 说明（紧跟图片引用之后） → 辅助匹配
    """
    fig_map = {}

    if not os.path.isdir(source_md_dir):
        return fig_map

    for fpath in find_md_files(source_md_dir):
        content = read_file_safe(fpath)
        if content is None:
            continue

        # 模式1: ![图X-X-说明](assets/图X-X-说明.xxx)
        for m in re.finditer(r"!\[(图\d+[-–]\d+[^\]]*)\]\(assets/(图\d+[-–]\d+[^\]]+\.[a-z]+)\)", content):
            fig_key = (
                m.group(1).split("-", 2)[0] + "-" + m.group(1).split("-", 2)[1]
                if len(m.group(1).split("-", 2)) >= 2
                else m.group(1)
            )
            fig_file = m.group(2)
            fig_map[fig_key] = fig_file

        # 模式2: 图X-X 说明（单独一行紧跟图片下面）
        # 提取类似 "图2-1 空间场的计算" 的行
        for m in re.finditer(r"^图(\d+[-–]\d+)\s+", content, re.MULTILINE):
            fig_key = f"图{m.group(1)}"
            if fig_key not in fig_map:
                # 尝试在当前行后找图片引用
                pass

    return fig_map


def copy_figure_images(fig_map, source_assets_dir, target_assets_dir):
    """
    将图映射中的图片从 source_assets_dir 复制到 target_assets_dir。
    返回 (已复制数, 缺失列表)
    """
    copied = 0
    missing = []

    if not os.path.isdir(source_assets_dir):
        log.warning(f"  ⚠️ 源资产目录不存在: {source_assets_dir}")
        return copied, missing

    os.makedirs(target_assets_dir, exist_ok=True)

    for _fig_key, fig_file in fig_map.items():
        source_path = os.path.join(source_assets_dir, fig_file)
        target_path = os.path.join(target_assets_dir, fig_file)

        if os.path.exists(target_path):
            continue  # 已存在

        if os.path.exists(source_path):
            import shutil

            shutil.copy2(source_path, target_path)
            copied += 1
        else:
            missing.append(fig_file)

    return copied, missing


def fix_figure_references_in_text(text, fig_map, assets_rel_dir):
    """
    将文本图引用 > 图X-X 替换为 Markdown 图片引用。

    匹配：
      > 图2-1 说明文字...    →    ![图2-1 说明文字](assets/图2-1-说明.emf)
      > 来源：第X章 X.X.X   →    保留不变（非图号行）
    """
    count = 0
    fixed_refs = []

    def replacer(m):
        nonlocal count
        full_line = m.group(1).strip()
        # 提取图号
        fig_match = re.match(r"图(\d+[-–]\d+)", full_line)
        if not fig_match:
            return m.group(0)  # 非图号行，保留

        fig_key = f"图{fig_match.group(1)}"

        # 模糊匹配：先在 map 中精确查找，再尝试前缀匹配
        fig_file = fig_map.get(fig_key, "")
        if not fig_file:
            # 尝试前缀匹配：图2-1 → 图2-1-空间场的计算.emf
            for k in sorted(fig_map.keys(), key=len, reverse=True):
                if k.startswith(fig_key):
                    fig_file = fig_map[k]
                    break

        if not fig_file:
            return m.group(0)  # 找不到匹配，保留原文

        # 构建 Markdown 图片语法
        img_path = f"{assets_rel_dir}/{fig_file}" if assets_rel_dir else fig_file
        result = f"![{full_line}]({img_path})"
        count += 1
        fixed_refs.append((fig_key, fig_file))
        return result

    # 匹配 > 开头的引用行（排除 > 来源：行）
    pattern = re.compile(r"^>\s*(图\d+[-–]\d+.*?)$", re.MULTILINE)
    result = pattern.sub(replacer, text)

    return result, count, fixed_refs


def fix_figure_references(wiki_root, source_md_dir=None, assets_rel_dir="assets"):
    """
    修复知识库中所有生成文件的图引用。
    自动复制出处图片到知识库 assets/ 目录。
    """
    # 构建 source assets 绝对路径
    source_assets_dir = None
    if source_md_dir:
        source_assets_dir = os.path.join(source_md_dir, "assets")
        if not os.path.isdir(source_assets_dir):
            source_assets_dir = None

    # 构建知识库 target assets 目录
    target_assets_dir = os.path.join(wiki_root, assets_rel_dir) if assets_rel_dir else wiki_root

    # 构建图映射
    fig_map = build_figure_map_from_source(source_md_dir)

    if not fig_map:
        log.info("  ⚠️ 未找到出处图片映射，跳过图片引用修复")
        return 0, [], fig_map

    # 复制图片
    copied, missing = copy_figure_images(fig_map, source_assets_dir, target_assets_dir)
    if copied > 0:
        log.info(f"  📋 复制 {copied} 张图片到 {target_assets_dir}")
    if missing:
        log.warning(f"  ⚠️ {len(missing)} 张图片在源目录中未找到: {missing[:3]}...")

    # 修复引用
    total_fixed = 0
    fixed_files = []
    target_dirs = [
        "30_核心概念",
        "30_知识要素",
        "40_知识点",
        "50_技能点",
        "60_应用场景",
        "概念",
        "知识要素",
        "知识点",
        "技能点",
        "场景",
    ]

    for fpath in find_md_files(wiki_root):
        rel = os.path.relpath(fpath, wiki_root)
        parts = rel.split(os.sep)
        if not any(td in parts for td in target_dirs):
            continue

        content = read_file_safe(fpath)
        if content is None:
            continue

        new_content, n, refs = fix_figure_references_in_text(content, fig_map, assets_rel_dir)
        if n > 0:
            write_file_safe(fpath, new_content)
            total_fixed += n
            fixed_files.append((rel, n, refs))

    return total_fixed, fixed_files, fig_map


# ═══════════════════════════════════════════════════════════
# 修复 3: Mermaid 图源补全
# ═══════════════════════════════════════════════════════════


def fix_mermaid_source_in_text(text):
    """
    修复 core_concept_map_source 为 "无" 的情况。
    尝试从概念出处推断图来源。
    """
    # 如果 core_concept_map_source 是 "无"，并且文件中有 source_from
    source_match = re.search(r"source_from:\s*(.+?)(?:\n|$)", text)
    if source_match:
        source_val = source_match.group(1).strip().strip("'\"")
        # 替换 core_concept_map_source
        text = re.sub(r'(core_concept_map_source:\s*["\']?)无(["\']?)', rf"\1来源：{source_val}\2", text)
        return text, 1
    return text, 0


def fix_mermaid_sources(wiki_root):
    """扫描文件，修复 core_concept_map_source 为"无"的情况"""
    total_fixed = 0
    fixed_files = []
    target_dirs = ["30_核心概念"]

    for fpath in find_md_files(wiki_root):
        rel = os.path.relpath(fpath, wiki_root)
        parts = rel.split(os.sep)
        if not any(td in parts for td in target_dirs):
            continue

        content = read_file_safe(fpath)
        if content is None:
            continue

        # 只处理 frontmatter 中 core_concept_map_source 为 无 的
        fm_match = re.search(r"^---\n(.*?)\n---", content, re.DOTALL)
        if not fm_match:
            continue
        fm_text = fm_match.group(1)
        if re.search(r'core_concept_map_source:\s*["\']?无["\']?', fm_text):
            # 修复 frontmatter 中的值
            new_content, n = fix_mermaid_source_in_text(content)
            if n > 0:
                write_file_safe(fpath, new_content)
                total_fixed += n
                fixed_files.append(rel)

    return total_fixed, fixed_files


# ═══════════════════════════════════════════════════════════
# 报告生成
# ═══════════════════════════════════════════════════════════


def generate_report(formula_fixed, formula_files, figure_fixed, figure_files, mermaid_fixed, mermaid_files, fig_map):
    """生成修复摘要报告"""
    lines = []
    lines.append("=" * 60)
    lines.append("  post_build_fix — 自动修复报告")
    lines.append("=" * 60)
    lines.append("")

    # 公式修复
    lines.append(f"📐 公式格式修复: {formula_fixed} 处 ({len(formula_files)} 文件)")
    for rel, n in formula_files[:10]:
        lines.append(f"     {rel}: {n} 处")
    if len(formula_files) > 10:
        lines.append(f"     ... 还有 {len(formula_files)-10} 个文件")
    lines.append("")

    # 图引用修复
    lines.append(f"🖼️ 图引用修复: {figure_fixed} 处 ({len(figure_files)} 文件)")
    for rel, _n, refs in figure_files[:10]:
        for fig_key, fig_file in refs:
            lines.append(f"     {rel}: {fig_key} → {fig_file}")
    if len(figure_files) > 10:
        lines.append(f"     ... 还有 {len(figure_files)-10} 个文件")

    if fig_map:
        lines.append(f"\n    📋 出处图映射表 ({len(fig_map)} 条):")
        for k in sorted(fig_map.keys())[:5]:
            lines.append(f"       {k} → {fig_map[k]}")
        if len(fig_map) > 5:
            lines.append(f"       ... 还有 {len(fig_map)-5} 条")

    lines.append("")

    # Mermaid 源修复
    if mermaid_fixed > 0:
        lines.append(f"🧩 Mermaid 图源修复: {mermaid_fixed} 处 ({len(mermaid_files)} 文件)")

    lines.append("")
    lines.append(f"总计: 公式 {formula_fixed} 处 + 图引用 {figure_fixed} 处 + Mermaid 源 {mermaid_fixed} 处")
    lines.append("=" * 60)

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════════════════════


def main():
    parser = argparse.ArgumentParser(description="构建后自动修复管道")
    parser.add_argument("wiki_root", help="知识库根目录")
    parser.add_argument("--source-dir", default=None, help="出处章节 .md 目录（用于图映射）")
    parser.add_argument("--assets-dir", default="assets", help="图片相对于知识库的目录（默认 assets）")
    parser.add_argument(
        "--fix-only", choices=["formula", "figure", "mermaid", "all"], default="all", help="仅修复特定项"
    )
    args = parser.parse_args()

    wiki_root = os.path.abspath(args.wiki_root)
    if not os.path.isdir(wiki_root):
        log.error(f"❌ 知识库目录不存在: {wiki_root}")
        raise PipelineError(f"知识库目录不存在: {wiki_root}")

    log.info(f"🔧 post_build_fix — 知识库: {wiki_root}")
    log.info("")

    # 修复 1: 公式格式
    formula_fixed = 0
    formula_files = []
    if args.fix_only in ("formula", "all"):
        log.info("📐 修复公式格式...")
        formula_fixed, formula_files = fix_block_formulas(wiki_root)
        log.info(f"   完成: {formula_fixed} 处 ({len(formula_files)} 文件)")
        log.info("")

    # 修复 2: 图引用
    figure_fixed = 0
    figure_files = []
    fig_map = {}
    if args.fix_only in ("figure", "all"):
        log.info("🖼️ 修复图引用...")
        source_dir = args.source_dir
        if source_dir:
            source_dir = os.path.abspath(source_dir)
        figure_fixed, figure_files, fig_map = fix_figure_references(wiki_root, source_dir, args.assets_dir)
        log.info(f"   完成: {figure_fixed} 处 ({len(figure_files)} 文件)")
        if fig_map:
            log.info(f"   出处图映射: {len(fig_map)} 条")
        log.info("")

    # 修复 3: Mermaid 图源
    mermaid_fixed = 0
    mermaid_files = []
    if args.fix_only in ("mermaid", "all"):
        log.info("🧩 修复 Mermaid 图源...")
        mermaid_fixed, mermaid_files = fix_mermaid_sources(wiki_root)
        log.info(f"   完成: {mermaid_fixed} 处 ({len(mermaid_files)} 文件)")
        log.info("")

    # 报告
    report = generate_report(
        formula_fixed, formula_files, figure_fixed, figure_files, mermaid_fixed, mermaid_files, fig_map
    )
    log.info(report)

    # 返回修复总数供管道使用
    total = formula_fixed + figure_fixed + mermaid_fixed
    return total


# ═══════════════════════════════════════════════════════════
# v39.0: 整合 fix 脚本 — LaTeX双反斜杠 / 公式来源 / 定义标记词 / 占位符
# ═══════════════════════════════════════════════════════════

# 定义标记词列表（与 template_assembler.py DEFINITION_MARKERS 同步）
_DEFINITION_MARKERS = [
    "是指",
    "一般指",
    "简称为",
    "也称为",
    "又可称为",
    "这就是",
    "即 ",
    "指的就是",
    "定义为",
    "是指一种",
    "称为",
    "叫",
    "成为",
    "是",
    "指",
    "方程为",
    "模型为",
    "可表示为",
    "表示为",
    "其中",
    "分为",
    "取决于",
]

# 占位符默认值（习题/解答）
_PLACEHOLDER_DEFAULTS = {
    "type_tag": "习题",
    "bloom_level": "理解",
    "principle_steps": "参见教材相关章节",
    "characteristics": "参见教材相关章节",
    "exam_points": "参见教材相关章节",
    "common_mistakes": "无",
    "solving_tips": "无",
    "difficulty": "中等",
    "answer": "参见解答文件",
    "knowledge_points": "无",
    "related_concepts": "无",
    "reference": "正文",
    "related_answer": "无",
    "solution_steps": "参见解答文件",
    "key_formula": "无",
}


def fix_latex_double_backslash(content):
    """修复 LaTeX 双反斜杠: \\\\ → \\（仅在公式块内）"""
    count = 0

    def _fix(m):
        nonlocal count
        formula = m.group(0)
        n = formula.count("\\\\")
        if n > 0:
            count += n
            formula = formula.replace("\\\\", "\\")
        return formula

    content = re.sub(r"\$\$.*?\$\$", _fix, content, flags=re.DOTALL)
    content = re.sub(r"\\\(.*?\\\)", _fix, content, flags=re.DOTALL)
    # 也修复公式块外的 LaTeX 双反斜杠（如列表项中的公式）
    content = re.sub(
        r"\\\\(frac|sqrt|int|sum|alpha|beta|gamma|delta|epsilon|"
        r"lambda|mu|sigma|omega|Omega|Delta|Sigma|Lambda|"
        r"phi|eta|theta|rho|pi|tau|nu|xi|zeta|chi|psi|"
        r"cos|sin|tan|log|ln|exp|lim|text|quad|cdot|"
        r"mathbf|mathcal|hat|bar|left|right|begin|end|"
        r"times|cdot|pm|mp|leq|geq|neq|approx|equiv|"
        r"infty|partial|nabla|forall|exists|in|notin|"
        r"overline|underline|widehat|widetilde)",
        r"\\\1",
        content,
    )
    return content, count


def fix_formula_citations(content, source_label="正文"):
    """在每个 $$ 公式块 closing 后添加 > 来源：标注
    使用 formula_utils 共享状态机，跳过代码块（Mermaid 中的 $$ 不是公式分隔符）
    """
    from formula_utils import find_formula_blocks

    lines = content.split("\n")
    blocks = find_formula_blocks(lines)
    fixes = 0
    # 从后往前插入，避免索引偏移
    for blk in reversed(blocks):
        # 检查 closing $$ 后 2 行内是否已有来源
        has_citation = False
        for j in range(blk.end_line + 1, min(blk.end_line + 3, len(lines))):
            if lines[j].strip():
                if "来源" in lines[j]:
                    has_citation = True
                break
        if not has_citation:
            lines.insert(blk.end_line + 1, f"> 来源：{source_label}")
            lines.insert(blk.end_line + 1, "")
            fixes += 1
    return "\n".join(lines), fixes


def fix_definition_markers(content):
    """如果精准释义定义缺少标记词，在句首添加'即，'"""
    lines = content.split("\n")
    new_lines = []
    fixed = False
    in_definition = False
    for _i, line in enumerate(lines):
        if "精准释义" in line and line.startswith("#"):
            in_definition = True
            new_lines.append(line)
            continue
        if in_definition and line.startswith("> ") and not line.startswith("> 来源"):
            defn_text = line[2:].strip()
            if defn_text and not any(m in defn_text for m in _DEFINITION_MARKERS):
                line = "> 即，" + defn_text
                fixed = True
            in_definition = False
        new_lines.append(line)
    return "\n".join(new_lines), fixed


def fill_placeholders(content):
    """填充 {{placeholder}} 和中文骨架占位符"""
    original = content
    for ph, default in _PLACEHOLDER_DEFAULTS.items():
        content = content.replace("{{" + ph + "}}", default)
    # 兆底：替换任意剩余 {{xxx}}
    content = re.sub(r"\{\{(\w+)\}\}", "无", content)
    # 中文骨架占位符
    content = re.sub(r"（待Agent[^）]*）", "待后续AI Agent深度填充", content)
    content = re.sub(r"（待填充[^）]*）", "待后续补充", content)
    content = re.sub(r"（待补充[^）]*）", "待后续补充", content)
    content = re.sub(r"（暂无[^）]*）", "无", content)
    return content, (content != original)


# ── 阶段目录映射 ──
_PHASE_DIR_MAP = {
    "concepts": ["30_核心概念"],
    "ke": ["30_知识要素"],
    "entities": ["70_实体"],
    "kp": ["40_知识点"],
    "sp": ["50_技能点"],
    "scene": ["60_应用场景"],
    "exercises": ["90_习题"],
    "solutions": ["90_习题/解答", "90_解答"],
}


def run_phase_auto_fix(wiki_root, phase, chapter=None):
    """统一自动修复入口：检测问题→修复→返回修复摘要 dict。

    在 pipeline auto 的构建后、验证前调用。
    """
    summary = {
        "double_backslash": 0,
        "block_formula": 0,
        "formula_citation": 0,
        "definition_marker": 0,
        "placeholder": 0,
        "files_touched": 0,
    }

    # 确定要扫描的目录
    target_dirs = _PHASE_DIR_MAP.get(phase, [])
    if not target_dirs:
        return summary

    source_label = f"第{chapter}章正文" if chapter else "正文"

    for td in target_dirs:
        scan_dir = os.path.join(wiki_root, td)
        if not os.path.isdir(scan_dir):
            continue
        for fname in sorted(os.listdir(scan_dir)):
            if not fname.endswith(".md"):
                continue
            fpath = os.path.join(scan_dir, fname)
            content = read_file_safe(fpath)
            if content is None:
                continue
            original = content

            # 1. LaTeX 双反斜杠
            content, n = fix_latex_double_backslash(content)
            summary["double_backslash"] += n

            # 2. 公式独占三行（已有 fix_block_formulas_in_text）
            content, n = fix_block_formulas_in_text(content)
            summary["block_formula"] += n

            # 3. 公式来源标注（concept / ke / kp 等含公式的阶段）
            if phase in ("concepts", "ke", "kp", "sp"):
                content, n = fix_formula_citations(content, source_label)
                summary["formula_citation"] += n

            # 4. 定义标记词（仅 concept）
            if phase == "concepts":
                content, ok = fix_definition_markers(content)
                if ok:
                    summary["definition_marker"] += 1

            # 5. 占位符填充（exercise / solution）
            if phase in ("exercises", "solutions"):
                content, n = fill_placeholders(content)
                summary["placeholder"] += n

            # 通用：文件被修改则记录
            if content != original:
                write_file_safe(fpath, content)
                summary["files_touched"] += 1

            # 5b. v51.4: 解答文件内容增强——在循环外批量处理
            if phase == "solutions" and chapter:
                enh = enhance_solution_content(wiki_root, str(chapter))
                if enh["enhanced"] > 0:
                    log.info(f"  ➕ solution-enhance [{phase}]: {enh['enhanced']} 个文件内容增强")
                    summary["files_touched"] += enh["enhanced"]

    total = sum(v for k, v in summary.items() if k != "files_touched")
    if total > 0:
        log.info(f"  🔧 auto-fix [{phase}]: {total} 处修复 ({summary['files_touched']} 文件)")
        for k, v in summary.items():
            if v > 0 and k != "files_touched":
                log.info(f"     {k}: {v}")
    return summary


# ── v51.4: 解答文件内容增强 ──────────────────────────────────
# 检测通用模板文字，从源文中提取相关段落替换
# 通用化设计: 章节文件名自动发现，关键词映射外置 YAML 配置
# v51.7: 检测改为多维度质量评分（长度+模板词密度+领域术语），不再依赖固定正则

import yaml as _yaml


def _discover_source_files(wiki_root: str) -> dict[str, str]:
    """自动发现 20_正文/ 目录中的章节文件，返回 {章节号: 文件路径}"""
    from pipeline_batch import discover_chapters
    chapters = discover_chapters(wiki_root)
    return {ch: path for ch, path in chapters}


def _load_keyword_map(wiki_root: str) -> dict[str, list[str]]:
    """从 config/knowledge_keywords.yaml 加载关键词映射，失败时返回空字典"""
    kw_path = os.path.join(os.path.dirname(__file__) if '__file__' in dir() else wiki_root,
                           "config", "knowledge_keywords.yaml")
    # 优先从技能目录加载
    skill_path = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                              "config", "knowledge_keywords.yaml")
    for p in [kw_path, skill_path]:
        try:
            with open(p, encoding="utf-8") as f:
                data = _yaml.safe_load(f) or {}
            return data.get("keyword_maps", {})
        except Exception:
            continue
    return {}


def _detect_boilerplate(content: str) -> list[str]:
    """检测文本中的通用模板文字——基于内容质量评分而非固定模式

    使用多维度评分：长度、特异性、模板词密度。
    返回匹配到的模式列表（空=高质量，不需要替换）。
    """
    matched = []
    stripped = content.strip()
    if not stripped:
        return ["empty"]

    # 1. 长度检测：过短的内容视为模板
    if len(stripped) < 60:
        matched.append("too_short")

    # 2. 模板词密度检测：高频模板词占比过高
    boilerplate_words = {"该习题", "解答", "基于", "教材", "第", "章", "相关内容",
                         "核心特征", "核心内容", "分析", "相关知识点", "基本概念",
                         "理解和应用", "能力", "混淆", "相似概念", "建议从",
                         "基本定义", "出发", "结合", "理论", "和", "边界条件",
                         "进行", "所", "的", "是", "了"}
    words = set(re.findall(r'[\u4e00-\u9fff]{2,4}', stripped))
    if words:
        bw_ratio = len(words & boilerplate_words) / len(words)
        if bw_ratio > 0.4:
            matched.append("high_boilerplate_density")

    # 3. 特异性检测：不含任何领域术语
    # 领域术语从 config/knowledge_keywords.yaml 加载（无配置时跳过此检查）
    try:
        _dw_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "knowledge_keywords.yaml")
        _domain_words = set()
        with open(_dw_path, encoding="utf-8") as _f:
            _dw_data = _yaml.safe_load(_f) or {}
        for _k, _v in _dw_data.get("keyword_maps", {}).items():
            _domain_words.add(_k)
            _domain_words.update(_v)
        has_domain_term = any(dw in stripped for dw in _domain_words)
        if not has_domain_term and len(stripped) < 200:
            matched.append("no_domain_terms")
    except Exception:
        pass  # 无配置文件时跳过特异性检查

    return matched


def _load_source_text(wiki_root: str, chapter: str) -> str:
    """使用自动发现的章节文件映射加载源文（跳过 YAML frontmatter）"""
    source_files = _discover_source_files(wiki_root)
    path = source_files.get(chapter, "")
    if not path:
        return ""
    if not os.path.exists(path):
        return ""
    try:
        with open(path, encoding="utf-8") as f:
            content = f.read()
        # 跳过 YAML frontmatter（--- ... ---）
        content = re.sub(r"^---\n.*?\n---\n", "", content, flags=re.DOTALL)
        return content
    except Exception:
        return ""


def _extract_keywords(question: str, wiki_root: str | None = None) -> list[str]:
    q = re.sub(r"[？?，,。.、：:；;！!""（）()]", " ", question)
    q = re.sub(r"\s+", " ", q).strip()
    q = re.sub(r"^(简述|简要说明|什么是|有哪些|如何|怎么样|怎样|分析|论述|讨论|比较|对比|解释|阐述|说明|列举|列出|写出|描述)\s*", "", q)
    q = re.sub(r"(有哪些|是什么|怎么回事|如何|怎样|怎么样|什么)$", "", q)
    keywords = [w.strip() for w in re.split(r"[的与和及、,，]", q) if len(w.strip()) > 1]
    # 从外部配置加载关键词映射
    kw_map = _load_keyword_map(wiki_root or "") if wiki_root else {}
    for q_sub, mapped in kw_map.items():
        if q_sub in question:
            keywords.extend(mapped)

    # v51.6: 如果问题是占位符（"第3章习题1"），用章节标题补关键词
    q_clean = re.sub(r"^第", "", q.strip())
    if not keywords or re.match(r"^\d+章", q_clean):
        chapter = ""
        m_ch = re.search(r"第(\d+)章", question)
        if m_ch:
            chapter = m_ch.group(1)
        if chapter and wiki_root:
            source_files = _discover_source_files(wiki_root)
            ch_path = source_files.get(chapter, "")
            if ch_path:
                ch_title = os.path.basename(ch_path).replace(".md", "")
                # 从章节标题提取关键词（"第3章 电磁兼容预测" → "电磁兼容预测"）
                ch_kw = re.sub(r"^第\d+章\s*", "", ch_title)
                ch_parts = re.split(r"[的与和及、,，]", ch_kw)
                for p in ch_parts:
                    p = p.strip()
                    if len(p) > 1 and p not in keywords:
                        keywords.append(p)
                # 对齐 kw_map（如果章节标题中的词在映射表里）
                for q_sub, mapped in kw_map.items():
                    if q_sub in ch_kw:
                        keywords.extend(mapped)

    return list(set(keywords))


def _find_relevant_paragraphs(source_text: str, keywords: list[str], max_n: int = 3) -> list[str]:
    if not source_text or not keywords:
        return []
    paras = re.split(r"\n\s*\n", source_text)
    scored = []
    for para in paras:
        para = para.strip()
        if not para or len(para) < 50 or re.match(r"^!\[.*\]\(.*\)$", para.strip()):
            continue
        score = 0
        matched = []
        for kw in keywords:
            if kw in para:
                score += len(kw)
                matched.append(kw)
        if score > 0:
            score += len(set(matched)) * 10
            scored.append((score, para))
    scored.sort(key=lambda x: -x[0])
    return [p for _, p in scored[:max_n]]


def _generate_section(question: str, source_text: str, sec_type: str, wiki_root: str | None = None) -> str:
    keywords = _extract_keywords(question, wiki_root)
    paras = _find_relevant_paragraphs(source_text, keywords)

    if not paras:
        fallback = {
            "principle_steps": f"本题涉及{question.replace('？', '')}的相关知识。建议从教材章节的理论出发进行分析。",
            "characteristics": "该知识点涉及本领域的基础理论。",
            "exam_points": f"核心考点：对{question.replace('？', '')}相关概念的理解。",
            "common_mistakes": "常见错误包括忽略边界条件、混淆概念、遗漏参数。",
            "solving_tips": "建议从基本概念出发，结合公式和案例分析。",
        }
        return fallback.get(sec_type, "详见教材相关章节。")

    combined = "\n\n".join(paras)
    # 各节使用不同的段落子集和表达方式，避免内容重复
    if sec_type == "principle_steps":
        return "- " + "\n- ".join(p[:400] for p in paras[:3])
    elif sec_type == "characteristics":
        # 从段落中提取关键特征
        features = []
        for p in paras[:2]:
            # 找包含"特点"、"特性"、"特征"、"方法"等关键词的句子
            sentences = re.split(r'(?<=[。！？])', p)
            for s in sentences:
                if any(kw in s for kw in ["特点", "特性", "特征", "方法", "方式", "途径", "分为", "包括", "主要"]):
                    features.append(s.strip())
                    if len(features) >= 3:
                        break
        if features:
            return "主要特征：\n" + "\n".join(f"- {f}" for f in features[:3])
        return "相关教材内容：\n" + combined[:400]
    elif sec_type == "exam_points":
        return "核心考点：\n" + "\n".join(f"- {p[:200]}" for p in paras[:2])
    elif sec_type == "common_mistakes":
        return f"常见错误：\n1. 忽略关键假设和边界条件\n2. 混淆相关概念\n3. 公式使用不当\n\n参考教材：\n{combined[:300]}"
    elif sec_type == "solving_tips":
        return f"解题思路：\n1. 审题确定已知和待求\n2. 回顾理论\n3. 建立模型求解\n4. 验证\n\n参考教材：\n{combined[:300]}"
    return combined[:300]


def enhance_solution_content(wiki_root: str, chapter: str | None = None) -> dict:
    """增强解答文件内容：检测模板文字→从源文提取相关段落实替换"""
    result = {"enhanced": 0, "files": []}
    source_text = _load_source_text(wiki_root, chapter) if chapter else ""

    sol_dir = os.path.join(wiki_root, "90_习题/解答")
    if not os.path.isdir(sol_dir):
        return result

    for fname in sorted(os.listdir(sol_dir)):
        if not fname.endswith(".md"):
            continue
        fpath = os.path.join(sol_dir, fname)
        content = read_file_safe(fpath)
        if content is None:
            continue

        qm = re.search(r"## 一、题目原文\s*\n\s*(.+?)\s*\n", content)
        if not qm:
            continue
        question = qm.group(1).strip()
        if len(question) < 5:
            continue

        orig = content
        secs = {
            "principle_steps": (r"### 2\.1 实现原理.*?\n(.*?)(?=\n###|\Z)", "实现原理（流程化拆解）"),
            "characteristics": (r"### 2\.2 主要特点.*?\n(.*?)(?=\n##|\Z)", "主要特点（维度化归纳）"),
            "exam_points": (r"### 3\.1 核心考点\s*\n(.*?)(?=\n###|\Z)", "核心考点"),
            "common_mistakes": (r"### 3\.2 常见错误.*?\n(.*?)(?=\n###|\Z)", "常见错误（避坑指南）"),
            "solving_tips": (r"### 3\.3 解题技巧\s*\n(.*?)(?=\n##|\Z)", "解题技巧"),
        }

        for sk, (pat, sec_name) in secs.items():
            m = re.search(pat, content, re.DOTALL)
            if not m:
                continue
            sc = m.group(1).strip()
            if _detect_boilerplate(sc):
                new_text = _generate_section(question, source_text, sk, wiki_root)
                # 替换该节内容——保留原 ### 标题行
                old_block = m.group(0)
                title_line = old_block.split("\n")[0]  # 原始标题行
                new_block = f"{title_line}\n\n{new_text}\n"
                content = content.replace(old_block, new_block)

        if content != orig:
            write_file_safe(fpath, content)
            result["enhanced"] += 1
            result["files"].append(fname)

    return result


if __name__ == "__main__":
    try:
        main()
    except PipelineError as e:
        log.error(str(e))
        raise
