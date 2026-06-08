"""content_check_rules.py — 入口文件，从 rules/ 子目录导入各检查模块

从 comprehensive_content_check.py 拆分。
v42.0: 新增字段字数阈值、wikilink 有效性、跨概念污染检测（从 comprehensive_content_check.py 迁入）。
v45.1: 拆分为 rules/ 子目录 — bloom / wikilink / formula / size / diagram。
"""

import os
import re
from collections import defaultdict

from dag_constants import DIR
from log_utils import get_logger

# ── 从子模块导入 ──
from rules.bloom import check_content_depth, extract_section, has_placeholder, section_has_real_content
from rules.formula import check_formula_quality, KNOWN_LATEX_CMDS
from rules.diagram import (
    _resolve_image_path, check_image_references, check_image_required,
    check_mermaid_quality, check_self_generated_diagrams,
)
from rules.wikilink import _find_md_file, check_wikilink_validity, auto_fix_wikilinks, get_all_md_filenames
from rules.size import (
    check_field_word_counts, check_knowledge_density, check_wu_field_count, _detect_node_type,
)

log = get_logger(__name__)

# ── 重新导出所有公共接口（保持向后兼容） ──
__all__ = [
    # bloom
    "check_content_depth", "extract_section", "has_placeholder", "section_has_real_content",
    # formula
    "check_formula_quality", "KNOWN_LATEX_CMDS",
    # diagram
    "_resolve_image_path", "check_image_references", "check_image_required",
    "check_mermaid_quality", "check_self_generated_diagrams",
    # wikilink
    "_find_md_file", "check_wikilink_validity", "auto_fix_wikilinks", "get_all_md_filenames",
    # size
    "check_field_word_counts", "check_knowledge_density", "check_wu_field_count",
    "_detect_node_type",
    # main
    "check_file_full", "check_concepts", "check_ke", "check_kp", "check_sp",
    "check_scenes", "check_entities", "check_exercises", "check_solutions",
    "check_cross_concept_pollution", "run_depth_checks",
]


# ── 综合文件检查 ──

def check_file_full(fpath, node_type, wiki_root):
    """对单个文件执行全部检查，返回 FAIL 列表和 WARN 列表"""
    fails, warns = [], []
    name = os.path.basename(fpath).replace(".md", "")
    file_label = f"{node_type}/{name}"

    try:
        with open(fpath) as f:
            content = f.read()
    except Exception as e:
        return [(f"文件无法读取: {e}")], []

    parts = content.split("---", 2)
    body = parts[2].strip() if len(parts) >= 3 else ""

    if has_placeholder(body):
        fails.append(f"[{file_label}] body 中含占位符")

    non_mermaid = re.sub(r"```.*?```", "", body, flags=re.DOTALL)
    double_bs = re.findall(r"\\\\([a-zA-Z]{2,})", non_mermaid)
    if double_bs:
        fails.append(f"[{file_label}] LaTeX双反斜杠: {' '.join(double_bs[:5])}（应为单\\）")

    d_fail, d_warn = check_content_depth(body, node_type, name)
    if d_fail:
        fails.append(f"[{file_label}] 内容深度: {d_fail}")
    if d_warn:
        warns.append(f"[{file_label}] 内容深度: {d_warn}")

    f_fails, f_warns = check_formula_quality(body, file_label)
    fails.extend(f_fails)
    warns.extend(f_warns)

    m_fails, m_warns = check_mermaid_quality(body, file_label)
    fails.extend(m_fails)
    warns.extend(m_warns)

    i_fails, i_warns = check_image_references(body, fpath, file_label, wiki_root)
    fails.extend(i_fails)
    warns.extend(i_warns)

    s_fails, s_warns = check_self_generated_diagrams(body, file_label, node_type)
    fails.extend(s_fails)
    warns.extend(s_warns)

    r_fails, r_warns = check_image_required(body, file_label, node_type)
    fails.extend(r_fails)
    warns.extend(r_warns)

    # 概念特殊检查
    if node_type == "concept":
        formula_match = re.search(r"### \d+\.?\s*公式引用\s*\n(.*?)(?=\n### |\Z)", body, re.DOTALL)
        if formula_match:
            formula_sec = formula_match.group(1).strip()
            if formula_sec not in ("无", "") and not re.search(r"\$\$", formula_sec):
                fails.append(f"[{file_label}] formula_references 不含$$公式（文本化引用）")
        figure_match = re.search(r"### \d+\.?\s*图引用\s*\n(.*?)(?=\n### |\Z)", body, re.DOTALL)
        if figure_match:
            figure_sec = figure_match.group(1).strip()
            tables_in_fig = re.findall(r"表\d+[-–]-\d+", figure_sec)
            if tables_in_fig:
                fails.append(f"[{file_label}] figure_references 含表引用: {' '.join(tables_in_fig)}")

    # 置信度合规
    fm_match = re.search(r"^---\n(.*?)\n---", content, re.DOTALL)
    if fm_match:
        fm_text = fm_match.group(1)
        conf_match = re.search(r"confidence:\s*(\S+)", fm_text)
        if conf_match:
            try:
                conf = float(conf_match.group(1))
                if node_type == "concept" and conf < 0.90:
                    warns.append(f"[{file_label}] 概念置信度 {conf} 低于0.95")
            except ValueError:
                pass

    return fails, warns


# ── 各类型检查函数 ──

def _fmt(items_with_severity, type_label):
    """将 (severity, msg) 元组列表转为 ('FAIL'|'WARN', type_label, msg) 格式"""
    return [(severity, type_label, msg) for severity, msg in items_with_severity]


def _scan_dir(dir_path, node_type, wiki_root):
    """扫描目录内所有 .md 文件，返回 ([(severity, msg)], [...])"""
    fails, warns = [], []
    if not os.path.isdir(dir_path):
        return fails, warns
    for fname in sorted(os.listdir(dir_path)):
        if not fname.endswith(".md"):
            continue
        short_types = {"concept", "knowledge", "skill", "scenario", "knowledge-element", "entity"}
        long_types = {"exercise", "solution"}
        if node_type in short_types and re.match(r"^第\d+章-", fname):
            fails.append(("FAIL", f"命名违规: {fname} 不应含章节前缀(第N章-)"))
        if node_type in long_types and "_" not in fname and "-" not in fname:
            fails.append(("FAIL", f"命名违规: {fname} 长名缺章节标记（应为第N章-习题X / 第N章-习题X-解答）"))
        fpath = os.path.join(dir_path, fname)
        ff, fw = check_file_full(fpath, node_type, wiki_root)
        fails.extend(("FAIL", m) for m in ff)
        warns.extend(("WARN", m) for m in fw)
    return fails, warns


def check_concepts(dir_path, wiki_root):
    f, w = _scan_dir(dir_path, "concept", wiki_root)
    return _fmt(f, "concept") + _fmt(w, "concept")

def check_ke(dir_path, wiki_root):
    f, w = _scan_dir(dir_path, "knowledge-element", wiki_root)
    return _fmt(f, "KE") + _fmt(w, "KE")

def check_kp(dir_path, wiki_root):
    f, w = _scan_dir(dir_path, "knowledge", wiki_root)
    return _fmt(f, "KP") + _fmt(w, "KP")

def check_sp(dir_path, wiki_root):
    f, w = _scan_dir(dir_path, "skill", wiki_root)
    return _fmt(f, "SP") + _fmt(w, "SP")

def check_scenes(dir_path, wiki_root):
    f, w = _scan_dir(dir_path, "scenario", wiki_root)
    return _fmt(f, "Scene") + _fmt(w, "Scene")

def check_entities(dir_path, wiki_root):
    f, w = _scan_dir(dir_path, "entity", wiki_root)
    return _fmt(f, "Entity") + _fmt(w, "Entity")

def check_exercises(dir_path, wiki_root):
    f, w = _scan_dir(dir_path, "exercise", wiki_root)
    return _fmt(f, "Exercise") + _fmt(w, "Exercise")

def check_solutions(dir_path, wiki_root):
    f, w = _scan_dir(dir_path, "solution", wiki_root)
    return _fmt(f, "Solution") + _fmt(w, "Solution")


# ── 跨概念污染检测 ──

_FIG_REF_PATTERN = re.compile(r"(?:图\s*\d+[-–—]\d+)")
_FORMULA_BLOCK_PATTERN = re.compile(r"\$\$(.*?)\$\$", re.DOTALL)


def _extract_fig_refs(body: str) -> set:
    """从 body 中提取所有图引用编号（如 图3-1）"""
    refs = set()
    cleaned = re.sub(r"```.*?```", "", body, flags=re.DOTALL)
    for m in _FIG_REF_PATTERN.finditer(cleaned):
        refs.add(m.group(0))
    return refs


def _extract_formula_signatures(body: str) -> set:
    """从 body 中提取公式块的内容签名（规范化后用于交叉比对）"""
    sigs = set()
    cleaned = re.sub(r"```.*?```", "", body, flags=re.DOTALL)
    for m in _FORMULA_BLOCK_PATTERN.finditer(cleaned):
        formula = m.group(1).strip()
        if not formula:
            continue
        norm = re.sub(r"\s+", "", formula)
        if len(norm) >= 10 and re.search(r"[\\a-zA-Z=+\-*/^_{}]", norm):
            sigs.add(norm[:120])
    return sigs


def check_cross_concept_pollution(wiki_root: str) -> list[tuple[str, str, str]]:
    """跨概念污染检测"""
    results = []
    concept_dir = os.path.join(wiki_root, DIR["CONCEPTS"])
    if not os.path.isdir(concept_dir):
        return results

    fig_to_concepts: dict = defaultdict(set)
    formula_to_concepts: dict = defaultdict(set)

    for fname in sorted(os.listdir(concept_dir)):
        if not fname.endswith(".md"):
            continue
        concept_name = fname.replace(".md", "")
        fpath = os.path.join(concept_dir, fname)
        try:
            with open(fpath, encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            log.debug(f"概念文件读取跳过 ({fpath}): {e}")
            continue

        parts = content.split("---", 2)
        body = parts[2] if len(parts) >= 3 else content
        for fig in _extract_fig_refs(body):
            fig_to_concepts[fig].add(concept_name)
        for sig in _extract_formula_signatures(body):
            formula_to_concepts[sig].add(concept_name)

    for fig, concepts in sorted(fig_to_concepts.items()):
        if len(concepts) >= 2:
            results.append(("WARN", "CrossConcept",
                f"图引用「{fig}」在 {len(concepts)} 个概念间共享: {', '.join(sorted(concepts))}"))

    for sig, concepts in sorted(formula_to_concepts.items()):
        if len(concepts) >= 2:
            display = sig[:60] + "..." if len(sig) > 60 else sig
            results.append(("WARN", "CrossConcept",
                f"公式块在 {len(concepts)} 个概念间共享: {', '.join(sorted(concepts))} — {display}"))

    return results


# ── 深度检查编排 ──

def run_depth_checks(wiki_root: str) -> list[tuple[str, str, str]]:
    """运行所有字段级深度检查（较重，通过 --depth-check 触发）"""
    results: list[tuple[str, str, str]] = []

    scan_dirs = [
        (DIR["CONCEPTS"], "concept"), (DIR["KE"], "knowledge-element"),
        (DIR["KP"], "knowledge"), (DIR["SP"], "skill"), (DIR["SCENE"], "scenario"),
        (DIR["SOLUTIONS"], "solution"), (DIR["EXERCISES"], "exercise"),
        (DIR["ENTITIES"], "entity"),
    ]

    for dir_name, _node_type in scan_dirs:
        dir_path = os.path.join(wiki_root, dir_name)
        if not os.path.isdir(dir_path):
            continue
        for fname in sorted(os.listdir(dir_path)):
            if not fname.endswith(".md"):
                continue
            fpath = os.path.join(dir_path, fname)
            results.extend(check_field_word_counts(fpath, wiki_root))
            results.extend(check_wu_field_count(fpath, wiki_root))
            results.extend(check_wikilink_validity(fpath, wiki_root))
            results.extend(check_knowledge_density(fpath, wiki_root))

    results.extend(check_cross_concept_pollution(wiki_root))
    return results
