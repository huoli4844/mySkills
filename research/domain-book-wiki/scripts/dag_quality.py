"""dag_quality.py — 知识图谱质量检查 (re-export 兼容层)

v41.0: 图检查函数拆分到 quality_graph_checks.py。
本文件保留编排函数 + re-export 入口。
"""

import json
import os
import re
from typing import Any

from dag_constants import (
    DAG_ORDER,
    DIR,
    LEVEL_QUALITY_CHECKS,
    PipelineArgs,
)

# dag_utils 公共导入
# v39.1: 打破循环依赖——从 dag_utils 导入而非 pipeline_auto
from dag_index import check_stray_files, fix_broken_links
from dag_state import (
    _load_state,
    _phase_dir,
    _state_path,
    _wr,
    get_wiki_root,
    scan_broken_links,
    verify_exercise_solution_mapping,
)

# v39.1: 显式导入（原靠运行时延迟导入碰巧能跑）
from phase_validator import validate_phase_output
from script_runner import run_concept_verify, run_mermaid_check

SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_ASSEMBLER = os.path.join(SKILL_DIR, "template_assembler.py")
INDEX_ASSEMBLER = os.path.join(SKILL_DIR, "index_assembler.py")
GEN_INDEX = os.path.join(SKILL_DIR, "generate_index_data.py")

from log_utils import get_logger  # noqa: E402

# ── 从 quality_graph_checks re-export ──
from quality_graph_checks import (  # noqa: E402
    _check_book_centrality,
    _check_book_chain,
    _check_book_similar,
    _check_cross_book_alignment,
    _check_cross_book_refs,
    _check_cross_domain_bridges,
    _check_domain_chain,
    _check_full_graph,
    _check_full_library_blindspots,
    _check_full_library_health,
    _check_graph_quality,
    _check_graph_wikilinks,
    _check_knowledge_islands,
    _check_l2_coverage,
)

log = get_logger(__name__)


def pipeline_check(args: PipelineArgs) -> None:
    wr = _wr(args)
    ch = args.chapter or "0"
    sp = _state_path(wr, args.book_id, ch)
    if not os.path.exists(sp):
        log.error("未初始化")
        return
    s = _load_state(sp)
    log.info("=== Pipeline 最终验证 ===")
    for ph in DAG_ORDER:
        p = s.get("phases", {}).get(ph, {})
        st = p.get("status", "pending")
        fc = p.get("files", 0)
        log.info(f"{'✅' if st=='done' else '⏳' if st=='in_progress' else '❌'} {ph}: {st} ({fc} 文件)")
    # 每阶段输出校验
    log.info("--- 阶段输出校验 ---")
    total_issues = 0
    for ph in ["concepts", "ke", "kp", "sp", "scene", "entities", "exercises", "solutions"]:
        result = validate_phase_output(wr, ph, ch)
        if result["passed"]:
            log.success(f"{ph}: 通过")
        else:
            log.error(f"{ph}: {len(result['issues'])} 项问题")
            for issue in result["issues"][:5]:
                log.info(f"{issue}")
            total_issues += len(result["issues"])
    # 概念根源质量闸门：验证定义出处
    from tac_quality import run_type_quality_checks

    concept_dir = _phase_dir(wr, "concepts")
    source_issues = 0
    if os.path.isdir(concept_dir):
        for fname in sorted(os.listdir(concept_dir)):
            if not fname.endswith(".md"):
                continue
            fpath = os.path.join(concept_dir, fname)
            with open(fpath) as fh:
                fc = fh.read()
            tm = re.search(r"^---\n(.*?)\n---", fc, re.DOTALL)
            if tm:
                typ = ""
                for line in tm.group(1).split("\n"):
                    if line.startswith("type:"):
                        typ = line.split(":", 1)[1].strip()
                        break
                if typ == "concept":
                    qc = run_type_quality_checks(fpath, "concept_template.md")
                    if not qc["passed"]:
                        for issue in qc["critical"]:
                            if "出处" in issue or "检索" in issue or "标记词" in issue:
                                log.error(f"[concept] {fname}: {issue[:80]}")
                                source_issues += 1
    if source_issues == 0:
        log.success("[concept] 定义出处验证全部通过")
    else:
        log.error(f"[concept] 定义出处验证: {source_issues} 项问题（定义未在正文中出现）")
    fix_broken_links(args)
    check_stray_files(args)
    # 验证习题-解答 1:1 对应关系
    wr = _wr(args)
    missing = verify_exercise_solution_mapping(wr)
    if missing:
        log.warning(f"习题-解答对应关系: {len(missing)} 道习题缺少解答")
        for m in missing[:5]:
            log.info(f"缺少: {m}")
        if len(missing) > 5:
            log.info(f"... 还有 {len(missing)-5} 道")
    else:
        log.success("习题-解答 1:1 对应关系验证通过")


def check_level_quality(args: PipelineArgs, level: str) -> dict[str, Any]:
    """对指定层级运行质量审核，返回 {passed, critical, warnings, detail}

    参数：
        args: 已解析的 argparse 对象
        level: "L1", "L2", "L3", 或 "L4"
    """

    wr = _wr(args)
    ch = args.chapter or "0"
    sp = _state_path(wr, args.book_id, ch)

    config = LEVEL_QUALITY_CHECKS.get(level)
    if not config:
        return {"passed": False, "critical": [f"未知层级: {level}"], "warnings": [], "detail": {}}

    state_exists = os.path.exists(sp)
    s = _load_state(sp) if state_exists else {}
    phases = s.get("phases", {})

    # Dispatch to level-specific handler
    level_handlers = {
        "L1": _check_l1_quality,
        "L2": _check_l2_quality,
        "L3": _check_l3_quality,
        "L4": _check_l4_quality,
    }
    handler = level_handlers.get(level, _check_l1_quality)

    critical, warnings, detail = handler(args, phases, wr, ch, sp, config)

    passed = len(critical) == 0
    return {
        "passed": passed,
        "level": level,
        "label": config["label"],
        "critical": critical,
        "warnings": warnings,
        "detail": detail,
    }


def _run_check(
    severity: str, check_id: str, description: str, result: str, msg: str, detail: dict, critical: list, warnings: list
) -> None:
    """统一的检查结果收集"""
    detail[check_id] = {"result": result, "msg": msg}
    if result == "fail":
        if severity == "critical":
            critical.append(msg)
        else:
            warnings.append(msg)


def _check_l1_quality(args: PipelineArgs, phases: dict, wr: str, ch: str, sp: str, config: dict) -> None:
    """L1 层级质量检查：概念/KE/KP/SP/Scene"""
    critical = []
    warnings = []
    detail = {}

    for severity, check_id, description in config["checks"]:
        result = "fail"
        msg = description

        if check_id == "all_phases_done":
            l1 = ["concepts", "ke", "entities", "kp", "sp", "scene", "exercises", "solutions"]
            done = all(phases.get(p, {}).get("status") == "done" for p in l1)
            all_exist = all(os.path.isdir(_phase_dir(wr, p)) for p in l1)
            result = "pass" if (done or all_exist) else "fail"
            if not done and all_exist:
                msg = "L1 文件齐全但状态未全部标记 done"

        elif check_id == "exercise_solution_1to1":
            missing = verify_exercise_solution_mapping(wr)
            result = "pass" if len(missing) == 0 else "fail"
            if missing:
                msg = f"{len(missing)} 道习题缺少解答"

        elif check_id == "no_broken_links":
            broken = scan_broken_links(wr, args.book_id, ch)
            result = "pass" if broken == 0 else "fail"
            if broken:
                msg = f"发现 {broken} 个断链"

        elif check_id == "no_shared_figures":
            shared = check_shared_figures(wr, args.book_id)
            result = "pass" if len(shared) == 0 else "fail"
            if shared:
                details = "; ".join(f"{fig}被{len(cs)}个概念共享" for fig, cs in shared.items())
                msg = f"共享图: {details}"

        elif check_id == "no_placeholder":
            ph_count = 0
            for p in DAG_ORDER:
                d = _phase_dir(wr, p)
                if not os.path.isdir(d):
                    continue
                for fn in os.listdir(d):
                    if not fn.endswith(".md"):
                        continue
                    with open(os.path.join(d, fn)) as fh:
                        c = fh.read()
                    ph_count += len(re.findall(r"\{\{[^}]+\}\}", c))
            result = "pass" if ph_count == 0 else "fail"
            if ph_count:
                msg = f"发现 {ph_count} 个 {{placeholder}} 残留"

        elif check_id == "concept_definitions_valid":
            concept_dir = os.path.join(wr, DIR["CONCEPTS"])
            verify_script = os.path.join(os.path.dirname(__file__), "verify_concepts.py")
            if os.path.exists(verify_script) and os.path.isdir(concept_dir):
                cv = run_concept_verify(concept_dir, json_mode=True)
                issues = cv.error_count + cv.warn_count
                result = "pass" if issues == 0 else "fail"
                if issues:
                    msg = f"概念定义发现 {issues} 项问题"
            else:
                result = "pass"

        elif check_id == "mermaid_no_errors":
            mermaid_script = os.path.join(os.path.dirname(__file__), "validate_mermaid_syntax.py")
            if os.path.exists(mermaid_script):
                mr = run_mermaid_check(wr, json_mode=True)
                err_count = mr.error_count
                result = "pass" if err_count == 0 else "fail"
                if err_count:
                    msg = f"Mermaid 有 {err_count} 个错误"
            else:
                result = "pass"

        elif check_id in (
            "graph_connectivity",
            "graph_path_integrity",
            "graph_hollow_concepts",
            "graph_orphan_nodes",
            "graph_orphan_ke",
            "graph_overloaded",
            "graph_similar_names",
        ):
            result, msg = _check_graph_quality(check_id, wr)

        else:
            result = "skip"

        _run_check(severity, check_id, description, result, msg, detail, critical, warnings)

    return critical, warnings, detail


def _check_l2_quality(args: PipelineArgs, phases: dict, wr: str, ch: str, sp: str, config: dict) -> None:
    """L2 层级质量检查：单书总揽"""
    critical = []
    warnings = []
    detail = {}

    for severity, check_id, description in config["checks"]:
        result = "fail"
        msg = description

        if check_id == "all_l1_done":
            l1 = ["concepts", "ke", "entities", "kp", "sp", "scene", "exercises", "solutions"]
            done = all(phases.get(p, {}).get("status") == "done" for p in l1)
            result = "pass" if done else "fail"

        elif check_id == "l2_indices_exist":
            overview_dir = os.path.join(wr, DIR["OVERVIEW"])
            expected = ["book_overview"]  # v43.15: 融合为单文件
            existing = set(os.listdir(overview_dir)) if os.path.isdir(overview_dir) else set()
            missing = [p for p in expected if not any(f.startswith(p) and f.endswith(".md") for f in existing)]
            result = "pass" if not missing else "fail"
            msg = f"缺少 L2 索引文件: {', '.join(missing)}" if missing else "L2 索引文件齐全"

        elif check_id == "l2_content_not_empty":
            # v44.2: 检查 L2 overview 文件是否有实质性内容，非空壳
            overview_dir = os.path.join(wr, DIR["OVERVIEW"])
            empty_patt = re.compile(r"知识链连通率.*?0%|连通率.*?0%|（待补充）|暂无数据")
            empty_files = []
            if os.path.isdir(overview_dir):
                for fname in os.listdir(overview_dir):
                    if fname.startswith("book_overview") and fname.endswith(".md"):
                        fpath = os.path.join(overview_dir, fname)
                        with open(fpath) as fh:
                            content = fh.read()
                        if empty_patt.search(content) or len(content.strip()) < 200:
                            empty_files.append(fname)
            result = "pass" if not empty_files else "warning"
            msg = f"L2 overview 空内容文件: {', '.join(empty_files)}" if empty_files else "L2 overview 内容正常"

        elif check_id == "l2_indices_done":
            result = "pass" if phases.get("l2_indices", {}).get("status") in ("done", "synced") else "fail"

        elif check_id == "no_broken_links":
            broken = scan_broken_links(wr, args.book_id, ch)
            result = "pass" if broken == 0 else "fail"
            if broken:
                msg = f"发现 {broken} 个断链"

        elif check_id == "graph_l2_connectivity":
            result, msg = _check_graph_wikilinks(wr, "L2")

        elif check_id == "graph_l2_coverage":
            result, msg = _check_l2_coverage(wr, args)

        # ── v35.0: L2 深度图分析 ──
        elif check_id == "graph_book_chain":
            result, msg = _check_book_chain(wr)
        elif check_id == "graph_book_centrality":
            result, msg = _check_book_centrality(wr, args)
        elif check_id == "graph_book_similar":
            result, msg = _check_book_similar(wr)

        else:
            result = "skip"

        _run_check(severity, check_id, description, result, msg, detail, critical, warnings)

    return critical, warnings, detail


def _check_l3_quality(args: PipelineArgs, phases: dict, wr: str, ch: str, sp: str, config: dict) -> None:
    """L3 层级质量检查：领域总控"""
    critical = []
    warnings = []
    detail = {}
    wiki_root = get_wiki_root(wr)

    for severity, check_id, description in config["checks"]:
        result = "fail"
        msg = description

        if check_id == "all_books_l2_done":
            # 检查领域内所有书的 L2 是否完成
            # nested 布局：领域目录是 wr 的父目录
            if DIR["FIELD"] == "" and DIR["LIBRARY"] == "":
                library_dir = os.path.dirname(wr)
            else:
                library_dir = os.path.join(wiki_root, DIR["FIELD"], DIR["LIBRARY"])
            if not os.path.isdir(library_dir):
                # 兼容：直接在 wiki_root 的同级查找
                library_dir = os.path.join(os.path.dirname(wr), os.path.basename(wr))
            books_done = 0
            books_total = 0
            books_pending = []
            if os.path.isdir(library_dir):
                for book_dir_name in sorted(os.listdir(library_dir)):
                    book_path = os.path.join(library_dir, book_dir_name)
                    if not os.path.isdir(book_path) or book_dir_name.startswith("."):
                        continue
                    # Only count as book if it has .dag/ subdirectory (real book)
                    if not os.path.isdir(os.path.join(book_path, ".dag")):
                        continue
                    books_total += 1
                    book_state = os.path.join(book_path, ".dag")
                    if os.path.isdir(book_state):
                        # Book L2 is "done" if ANY chapter has l2_indices done (v43.12: only last ch generates L2)
                        book_l2_done = False
                        found_chapter = False
                        for sf in os.listdir(book_state):
                            if sf.endswith(".json") and "_ch" in sf:
                                try:
                                    with open(os.path.join(book_state, sf)) as fh:
                                        bs = json.load(fh)
                                    l2_status = bs.get("phases", {}).get("l2_indices", {}).get("status", "pending")
                                    found_chapter = True
                                    if l2_status in ("done", "synced"):
                                        book_l2_done = True
                                except (json.JSONDecodeError, ValueError, OSError):
                                    pass
                        if found_chapter and book_l2_done:
                            books_done += 1
                        else:
                            books_pending.append(book_dir_name)
                    else:
                        books_pending.append(book_dir_name)
            if books_total == 0:
                result = "pass"
                msg = "领域内无其他书，跳过"
            elif books_done == books_total:
                result = "pass"
                msg = f"领域内 {books_total} 本书的 L2 全部完成"
            else:
                result = "fail"
                msg = f"领域内 {books_done}/{books_total} 本书 L2 完成，待完成: {', '.join(books_pending[:3])}"
        elif check_id == "l3_indices_exist":
            # nested 布局：领域总控在域目录下
            if DIR["FIELD"] == "":
                ctrl_dir = os.path.join(os.path.dirname(wr), DIR["DOMAIN_CTRL"])
            else:
                ctrl_dir = os.path.join(wiki_root, DIR["FIELD"], DIR["DOMAIN_CTRL"])
            expected = ["domain_overview"]  # v43.15: 融合为单文件
            existing = set(os.listdir(ctrl_dir)) if os.path.isdir(ctrl_dir) else set()
            missing = [p for p in expected if not any(f.startswith(p) and f.endswith(".md") for f in existing)]
            result = "pass" if not missing else "fail"
            msg = f"缺少 L3 索引文件: {', '.join(missing)}" if missing else "L3 索引文件齐全"
        elif check_id == "l3_indices_done":
            result = "pass" if phases.get("l3_indices", {}).get("status") in ("done", "synced") else "fail"
        elif check_id == "no_broken_links_l3":
            broken = scan_broken_links(wr, args.book_id, ch)
            result = "pass" if broken == 0 else "fail"
            if broken:
                msg = f"发现 {broken} 个断链"
        elif check_id == "graph_l3_cross_book":
            result, msg = _check_cross_book_refs(wr)
        # ── v35.0: L3 跨书深度图分析 ──
        elif check_id == "graph_cross_book_align":
            result, msg = _check_cross_book_alignment(wr)
        elif check_id == "graph_knowledge_islands":
            result, msg = _check_knowledge_islands(wr)
        elif check_id == "graph_domain_chain":
            result, msg = _check_domain_chain(wr)
        else:
            result = "skip"

        _run_check(severity, check_id, description, result, msg, detail, critical, warnings)

    return critical, warnings, detail


def _check_l4_quality(args: PipelineArgs, phases: dict, wr: str, ch: str, sp: str, config: dict) -> None:
    """L4 层级质量检查：知识库总控"""
    critical = []
    warnings = []
    detail = {}
    wiki_root = get_wiki_root(wr)

    for severity, check_id, description in config["checks"]:
        result = "fail"
        msg = description

        if check_id == "all_domains_l3_done":
            # 检查知识库内所有领域的 L3 是否完成
            field_dir = os.path.join(wiki_root, DIR["FIELD"])
            domains_done = 0
            domains_total = 0
            domains_pending = []
            if os.path.isdir(field_dir):
                for domain_name in sorted(os.listdir(field_dir)):
                    domain_path = os.path.join(field_dir, domain_name)
                    if not os.path.isdir(domain_path):
                        continue
                    # 查找领域总控目录
                    ctrl_dir = os.path.join(domain_path, DIR["DOMAIN_CTRL"])
                    if not os.path.isdir(ctrl_dir):
                        continue
                    domains_total += 1
                    # 检查领域内是否有书完成了 l3_indices
                    # 简化：检查该领域总控目录下是否有索引文件
                    idx_files = [f for f in os.listdir(ctrl_dir) if f.endswith(".md")]
                    # v43.15: 索引融合为单文件，判定阈值改为 ≥1
                    if len(idx_files) >= 1:
                        domains_done += 1
                    else:
                        domains_pending.append(domain_name)
            if domains_total <= 1:
                result = "pass"
                msg = "仅单领域，跳过"
            elif domains_done == domains_total:
                result = "pass"
                msg = f"{domains_total} 个领域的 L3 全部完成"
            else:
                result = "fail"
                msg = f"{domains_done}/{domains_total} 个领域 L3 完成，待完成: {', '.join(domains_pending[:3])}"
        elif check_id == "l4_indices_exist":
            kb_dir = os.path.join(wiki_root, DIR["KB_CTRL"])
            expected = ["kb_overview"]  # v43.15: 融合为单文件
            existing = set(os.listdir(kb_dir)) if os.path.isdir(kb_dir) else set()
            missing = [p for p in expected if not any(f.startswith(p) and f.endswith(".md") for f in existing)]
            result = "pass" if not missing else "fail"
            msg = f"缺少 L4 索引文件: {', '.join(missing)}" if missing else "L4 索引文件齐全"
        elif check_id == "l4_indices_done":
            result = "pass" if phases.get("l4_indices", {}).get("status") in ("done", "synced") else "fail"
        elif check_id == "no_broken_links_l4":
            broken = scan_broken_links(wr, args.book_id, ch)
            result = "pass" if broken == 0 else "fail"
            if broken:
                msg = f"发现 {broken} 个断链"
        elif check_id == "graph_l4_complete":
            result, msg = _check_full_graph(wr)
        # ── v35.0: L4 全库深度图分析 ──
        elif check_id == "graph_full_health":
            result, msg = _check_full_library_health(wr)
        elif check_id == "graph_cross_domain":
            result, msg = _check_cross_domain_bridges(wr)
        elif check_id == "graph_full_blindspots":
            result, msg = _check_full_library_blindspots(wr)
        else:
            result = "skip"

        _run_check(severity, check_id, description, result, msg, detail, critical, warnings)

    return critical, warnings, detail


# ── 共享图检测（v36.0）──


def check_shared_figures(wiki_root, book_id):
    """扫描概念目录中所有 .md 文件，检测同一图号被多个概念引用。

    规则：图必须专门为解释当前概念而存在。
    同一图号出现在 2+ 概念中 => 共享图违规。
    返回 { 图号: [概念名1, 概念名2, ...] }
    """
    from collections import defaultdict

    concept_dirs = []
    # 扫描所有可能的 book 目录
    for base in [os.path.join(wiki_root, DIR["DOMAIN_DIR"], DIR["LIBRARY_DIR"]), os.path.join(wiki_root, DIR["LIBRARY_DIR"]), wiki_root]:
        if book_id:
            candidate = os.path.join(base, book_id, "30_核心概念")
        else:
            # 无 book_id 时扫描所有 30_核心概念 目录
            candidate = os.path.join(base, "30_核心概念") if os.path.exists(os.path.join(base, "30_核心概念")) else None
        if candidate and os.path.isdir(candidate):
            concept_dirs.append(candidate)

    if not concept_dirs:
        # 扁平布局：book_id 本身就是根
        for cand in [
            os.path.join(wiki_root, "30_核心概念"),
            os.path.join(wiki_root, book_id, "30_核心概念") if book_id else None,
        ]:
            if cand and os.path.isdir(cand):
                concept_dirs.append(cand)

    fig_to_concepts = defaultdict(list)

    for cd in concept_dirs:
        for fname in sorted(os.listdir(cd)):
            if not fname.endswith(".md"):
                continue
            fpath = os.path.join(cd, fname)
            try:
                with open(fpath, encoding="utf-8") as f:
                    content = f.read()
            except Exception as e:
                log.warning(f"文件读取失败 ({fname}): {e}")
                continue

            # 从 frontmatter 提取概念名称
            name_match = re.search(r"^---\n.*?\n---", content, re.DOTALL)
            if name_match:
                fm_text = name_match.group(0)
                n_match = re.search(r"name:\s*(.+)", fm_text)
                concept_name = n_match.group(1).strip().strip('"') if n_match else fname.replace(".md", "")
            else:
                concept_name = fname.replace(".md", "")

            # 提取正文中所有 图X-X 引用
            parts = content.split("---", 2)
            body = parts[2] if len(parts) >= 3 else ""
            for m in re.finditer(r"图(\d+[-–]\d+)", body):
                fig_key = f"图{m.group(1)}"
                fig_to_concepts[fig_key].append(concept_name)

    # 只返回被 2+ 个概念引用的图
    return {fig: cs for fig, cs in fig_to_concepts.items() if len(cs) >= 2}
