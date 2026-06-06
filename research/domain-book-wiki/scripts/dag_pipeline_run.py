"""dag_pipeline_run.py — Pipeline 验证与自动编排 (validate/auto)

从 dag_pipeline.py 拆分，通过 re-export 保持兼容。
"""

import glob
import json
import os
import re
import time as _time_mod
from typing import Any

from dag_constants import (
    DAG_DEPENDS,
    DAG_ITEM_HINTS,
    DAG_ORDER,
    DIR,
    PipelineArgs,
    PipelineError,
)
from dag_index import _build_level_indices, check_stray_files, fix_broken_links
from dag_quality import check_level_quality
from dag_state import (
    _load_state,
    _log_check_result,
    _phase_count,
    _phase_dir,
    _phase_latest_mtime,
    _save_state,
    _state_path,
    _wr,
    get_wiki_root,
    scan_broken_links,
    verify_exercise_solution_mapping,
)
from log_utils import get_logger
from phase_validator import validate_phase_output
from pipeline_auto import (
    _auto_build_kb_phase,
    _auto_build_solutions,
    _auto_detect_and_build_exercises,
    _run_comprehensive_check_on_phase,
)
from pipeline_insights import check_cross_chapter_consistency
from script_runner import (
    run_concept_verify,
    run_content_check,
    run_dir_registry_check,
    run_mermaid_check,
    run_script,
)

log = get_logger(__name__)

SKILL_DIR = os.path.dirname(os.path.abspath(__file__))


def _is_last_chapter(wr: str, ch: str) -> bool:
    """v43.13: 检查当前章节是否为最后一章。
    通过检测 20_正文/ 中是否存在编号更大的章节源文件来判断。
    返回 True 表示当前章是最后一章，应生成 L2/L3/L4 索引。
    """
    content_dir = os.path.join(wr, DIR.get("CONTENT", "20_正文"))
    if not os.path.isdir(content_dir):
        return True  # 找不到内容目录，保守生成
    current_ch = int(ch)
    for fname in os.listdir(content_dir):
        m = re.match(r"第(\d+)章\s", fname)
        if m:
            next_ch = int(m.group(1))
            if next_ch > current_ch:
                return False  # 存在更大的章节 → 不是最后一章
    return True  # 没有更大的章节 → 是最后一章

    # 获取已有文件名列表
    # 只添加不存在的 item
    # 构建 skeleton 并只塞入新 items
# ===== 原始单阶段操作 =====
    # ── v35.3: 自动检测工作区布局（嵌套/平铺）并保存到 .dag/config.yaml ──
    # ── v33.1: Phase 0 — 自动运行 schema.py 预检 YAML 数据 ──
            # 不自动更新状态——多章共用目录时文件数无法区分章节归属
            # 用户必须通过 pipeline done 显式标记完成
    # P0-3: 获取并发锁（进程退出时自动释放）
    # 🔍 Auto-validate: 每次 pipeline next 自动运行全量验证，确保当前已完成阶段输出无问题
        # ⚠️ 强制要求完整章节文件名：第1章 概述.md（拒绝短名 第1章.md）
            # 过滤：排除仅"第X章.md"的短名，只保留含完整标题的文件
    # 逐章L1内容生成：当章节>0时，用 build_kb_files.py 生成该章的概念/KE/KP/SP/Scene
            # F2 fix: 构建后走验证流程，不直接标 done
        # F2 fix: 索引构建后也走验证
# v39.1: verify_exercise_solution_mapping 已移至 dag_utils.py（打破循环依赖）
# v38.0: validate_phase_output 已拆分到 phase_validator.py（通过顶部 import 导入）
# ===== 4. 12阶段DAG编排 =====
            # v35.2: exercises 为 0 时先尝试自动检测，避免遗漏习题
    # P5 fix: 先设为 in_progress，验证通过后才设为 done（避免竞态条件）
    # Task 7: 增量构建 — 如果阶段已是 done 且文件未变更，跳过重复验证
    # Auto-validation: 每个 L1 阶段完成后自动校验输出
    # 概念根源质量闸门：三步骤验证 + 文件级校验
        # 运行 verify_concepts_from_source.py 做最终验证
            # 构建临时 JSON 用于验证
                # 解析输出获取统计
            # 设置 blocked 状态
    # ── v33.1: KE 溯源验证（ke 阶段完成时）──
                # 收集 KE 数据用于验证
                    # 提取 KE 的 source 或 definition
    # 图连通性质量闸门：每个 L1 阶段完成后验证图连通性
    # v22.0 增强：
    # - pipeline_done: 仅报告不阻断（跨阶段引用需等上游构建完才产生）
    # - check_level_quality L1: 做真正的阻断闸门（所有阶段完成后检查）
                # v40.0: 增量构建图谱（跳过未变更文件，提升性能）
                # 综合图质量检查（传入当前阶段，过滤掉尚不存在的检查）
                    # pipeline_done 阶段：只报告不阻断
                    # 阻断由 check_level_quality L1 级别闸门承担
                # 连通性检查（不阻断，仅报告）
    # 验证习题-解答 1:1 对应关系
            # 设置 blocked 状态
    # 层级质量闸门：检查当前阶段所属层级是否全部完成
                # 如果有 critical 问题，设置 blocked 阻止继续
    # 所有验证通过，提升为 done
    # Task 7: 记录验证时的最新 mtime
    # 全部12个阶段完成 → 庆祝
def pipeline_validate(args: PipelineArgs) -> dict[str, Any]:
    """全量验证：运行所有检查项，一次报告所有问题。
    返回 {"passed": bool, "critical": [str]} 供 pipeline_next 阻断使用。
    Task 7: 增量构建——若所有阶段 mtime 未变且上次验证通过，直接返回缓存结果。"""
    wr = _wr(args)
    ch = args.chapter or "0"
    sp = _state_path(wr, args.book_id, ch)
    if not os.path.exists(sp):
        log.error("未初始化")
        return {"passed": True, "critical": []}
    s = _load_state(sp)

    # Task 7: 检查是否可以跳过重复验证
    force = getattr(args, "force", False)
    if not force:
        last_full_validate = s.get("last_full_validate_mtime", 0)
        # 计算所有阶段目录的最新 mtime
        max_mtime = 0.0
        for ph in DAG_ORDER:
            mt = _phase_latest_mtime(wr, ph)
            if mt > max_mtime:
                max_mtime = mt
        if max_mtime > 0 and max_mtime <= last_full_validate and s.get("last_full_validate_passed", False):
            log.info(f"[pipeline validate] 文件未变更，跳过重复验证 (mtime={max_mtime:.0f})")
            return {"passed": True, "critical": []}

    log.info("=" * 50)
    log.info("  Pipeline 全量验证 (13/13)")
    log.info("=" * 50)

    # P20 fix: 在检查过程中收集关键指标，末尾复用（避免重复扫描）
    _tracked = {"broken_links": -1, "placeholder_count": -1, "content_fail": 0}

    # 1. 阶段状态检查
    log.info("\n[01/13] 阶段完成状态")
    for ph in DAG_ORDER:
        p = s.get("phases", {}).get(ph, {})
        st = p.get("status", "pending")
        fc = p.get("files", 0)
        log.info(f"{'✅' if st=='done' else '⏳' if st=='in_progress' else '❌'} {ph}: {st} ({fc} 文件)")

    # 2. 输出内容校验（FrontMatter + 置信度 + 占位符 + type）
    log.info("\n[02/13] FrontMatter + 置信度 + 占位符")
    fm_issues = 0
    for ph in ["concepts", "ke", "kp", "sp", "scene", "entities", "exercises", "solutions"]:
        result = validate_phase_output(wr, ph, ch)
        if not result["passed"]:
            fm_issues += len(result["issues"])
            for issue in result["issues"][:3]:
                log.error(f"[{ph}] {issue}")
    if fm_issues == 0:
        log.success("全部通过")

    # 3. 断链扫描 + wikilink/孤立文件交叉验证
    log.info("\n[03/13] 断链扫描 + wikilink 交叉验证")
    has_fix = hasattr(args, "fix") and args.fix

    class FakeArgs:
        def __init__(self):
            self.wiki_root = args.wiki_root
            self.book_id = args.book_id
            self.fix = has_fix
            self.action = "fix" if has_fix else "scan"

    fix_broken_links(FakeArgs())
    _tracked["broken_links"] = scan_broken_links(wr, args.book_id, ch)
    # v33.1: 同时运行 verify_completeness.py 做交叉验证
    vc_script = os.path.join(os.path.dirname(__file__), "verify_completeness.py")
    if os.path.exists(vc_script):
        vc_result = run_script("verify_completeness.py", [wr, "--json"], json_mode=True, timeout=60)
        if vc_result.success:
            vc_broken = vc_result.data.get("broken_links", 0)
            if vc_broken > 0 and _tracked["broken_links"] < vc_broken:
                _tracked["broken_links"] = vc_broken
                log.warning(f"verify_completeness.py 发现额外 {vc_broken} 个断链")
            stray = vc_result.data.get("stray_files", [])
            if stray:
                log.info(f"verify_completeness.py 发现 {len(stray)} 个孤立文件")

    # 4. 习题-解答 1:1
    log.info("\n[04/13] 习题-解答对应关系")
    missing = verify_exercise_solution_mapping(wr)
    if missing:
        log.error(f"{len(missing)} 道习题缺少解答")
        for m in missing[:5]:
            log.info(f"缺少: {m}")
    else:
        log.success("1:1 对应关系通过")

    # 5. Mermaid 语法
    log.info("\n[05/13] Mermaid 语法")
    mermaid_script = os.path.join(os.path.dirname(__file__), "validate_mermaid_syntax.py")
    _tracked["mermaid_errors"] = 0
    if os.path.exists(mermaid_script):
        mr = run_mermaid_check(wr, json_mode=True)
        err_count = mr.error_count
        warn_count = mr.warn_count
        _tracked["mermaid_errors"] = err_count
        if err_count > 0:
            log.error(f"发现 {err_count} 个 Mermaid 语法问题（含 {warn_count} 个警告）")
        else:
            log.success("Mermaid 语法通过（或无可检查块）")
    else:
        log.warning("validate_mermaid_syntax.py 不存在，跳过")

    # 6. 概念定义检验
    log.info("\n[06/13] 概念定义验证")
    concept_dir = os.path.join(wr, DIR["CONCEPTS"])
    verify_script = os.path.join(os.path.dirname(__file__), "verify_concepts.py")
    _tracked["concept_verify_errors"] = 0
    if os.path.exists(verify_script) and os.path.isdir(concept_dir):
        source_dir = os.path.join(wr, DIR["SOURCE"])
        src_file = None
        if os.path.isdir(source_dir):
            md_files = sorted([f for f in os.listdir(source_dir) if f.endswith(".md")])
            if md_files:
                combined_content = ""
                for fname in md_files:
                    fpath = os.path.join(source_dir, fname)
                    with open(fpath, encoding="utf-8") as fh:
                        combined_content += f"\n\n/* === {fname} === */\n\n" + fh.read()
                import tempfile

                tmp_combined = os.path.join(tempfile.gettempdir(), f"_dag_combined_source_{os.path.basename(wr)}.md")
                with open(tmp_combined, "w", encoding="utf-8") as fh:
                    fh.write(combined_content)
                src_file = tmp_combined
        cv = run_concept_verify(concept_dir, source=src_file or "", json_mode=True)
        if cv.has_errors:
            _tracked["concept_verify_errors"] = cv.error_count
            log.error(f"概念定义验证未通过（{cv.error_count} 个错误）")
    else:
        log.warning("跳过（无概念目录或验证脚本）")

    # 7. stray 文件
    log.info("\n[07/13] 孤文件检查")
    check_stray_files(args)

    # 8. 层级质量审核
    log.info("\n[08/13] 层级级质量闸门")
    for lv in ["L1", "L2", "L3", "L4"]:
        qr = check_level_quality(args, lv)
        if qr["passed"]:
            log.success(f"{lv}: {qr['label']} 通过")
        else:
            log.error(f"{lv}: {qr['label']} — {len(qr['critical'])} 项关键问题")
            for issue in qr["critical"][:3]:
                log.error(f"{issue}")
            for issue in qr["warnings"][:2]:
                log.warning(f"{issue}")

    # 9. 目录注册表一致性
    log.info("\n[09/13] 目录注册表一致性")
    check_script = os.path.join(os.path.dirname(__file__), "check_dir_registry.py")
    if os.path.exists(check_script):
        rr = run_dir_registry_check(wr, json_mode=True)
        err_count = rr.error_count
        if err_count > 0:
            log.error(f"发现 {err_count} 个注册表问题")
        else:
            log.success("目录注册表一致")
    else:
        log.warning("check_dir_registry.py 不存在，跳过")

    # 10. 生成内容深度质量检查（P19 fix: 只运行一次，不双重运行）
    log.info("\n[10/13] 生成内容深度质量检查")
    content_check_script = os.path.join(os.path.dirname(__file__), "comprehensive_content_check.py")
    content_fail = 0
    content_warn = 0
    if os.path.exists(content_check_script):
        cc = run_content_check(wr, quiet=False, json_mode=True)
        content_fail = cc.error_count
        content_warn = cc.warn_count
        if content_fail > 0:
            log.error(f"发现 {content_fail} 个严重问题, {content_warn} 个警告")
            # 从 JSON items 中提取前5个 FAIL 详情
            fail_items = [item for item in cc.items if item.get("severity") == "FAIL"][:5]
            for item in fail_items:
                log.info(f"  ❌ {item.get('type', '?')}: {item.get('detail', '')}")
            if len([item for item in cc.items if item.get("severity") == "FAIL"]) >= 5:
                log.info("...(更多问题请运行 comprehensive_content_check.py 查看完整报告)")
        else:
            log.success("生成内容质量检查通过")
    else:
        log.warning("comprehensive_content_check.py 不存在，跳过")

    # 11. v47.0: 渲染级校验（Mermaid/LaTeX/wikilink 可达性）
    log.info("\n[11/13] 渲染级校验 (validate_render)")
    render_script = os.path.join(os.path.dirname(__file__), "validate_render.py")
    render_fail = 0
    render_warn = 0
    if os.path.exists(render_script):
        try:
            from validate_render import validate_all as _validate_render_all
            wiki_root_r = get_wiki_root(wr)
            vr = _validate_render_all(wiki_root_r, args.book_id)
            render_fail = sum(1 for i in vr.get("mermaid", []) + vr.get("latex", [])
                              if i.get("severity") == "error")
            render_warn = sum(1 for i in vr.get("mermaid", []) + vr.get("latex", []) + vr.get("wikilink", [])
                              if i.get("severity") == "warning")
            if render_fail > 0:
                log.error(f"渲染校验发现 {render_fail} 个错误, {render_warn} 个警告")
            elif render_warn > 0:
                log.warning(f"渲染校验通过但有 {render_warn} 个警告")
            else:
                log.success("渲染校验通过")
        except Exception as e:
            log.warning(f"validate_render 执行异常: {e}")
    else:
        log.warning("validate_render.py 不存在，跳过")
    _tracked["render_fail"] = render_fail
    _tracked["render_warn"] = render_warn

    # 12. v47.0: 跨章一致性检查
    log.info("\n[12/13] 跨章一致性检查")
    cross_chapter_conflicts = 0
    cross_chapter_similar = 0
    try:
        cc_result = check_cross_chapter_consistency(wr, args.book_id)
        cross_chapter_conflicts = cc_result.get("summary", {}).get("same_name_conflict_count", 0)
        cross_chapter_similar = cc_result.get("summary", {}).get("similar_name_conflict_count", 0)
        if cross_chapter_conflicts > 0 or cross_chapter_similar > 0:
            log.warning(f"发现 {cross_chapter_conflicts} 组同名冲突, {cross_chapter_similar} 组近名冲突")
            severity = cc_result.get("summary", {}).get("severity_breakdown", {})
            for k, v in severity.items():
                if v > 0:
                    labels = {
                        "definition_mismatch": "定义严重不一致",
                        "definition_divergence": "定义有分歧",
                        "bloom_mismatch": "Bloom层级不一致",
                        "classification_mismatch": "分类归属不一致",
                        "potential_merge_candidate": "可能需合并",
                        "potential_duplicate_low_def_sim": "近名但定义差异大",
                    }
                    log.info(f"  {labels.get(k, k)}: {v} 项")
        else:
            log.success("跨章一致性检查通过")
    except Exception as e:
        log.warning(f"跨章一致性检查异常: {e}")
    _tracked["cross_chapter_conflicts"] = cross_chapter_conflicts
    _tracked["cross_chapter_similar"] = cross_chapter_similar

    # 13. 知识图谱健康检查（合并原 [11]+[12]）— A6优化：一次构建+双重验证
    log.info("\n[13/13] 知识图谱健康检查")
    try:
        from kb_graph import KGraph

        wiki_root = get_wiki_root(wr)
        kg = KGraph(wiki_root)
        if os.path.exists(kg.db_path):
            # 1) 结构完整性
            issues = kg.validate()
            errors = [i for i in issues if i["severity"] == "error"]
            if errors:
                log.error(f"发现 {len(errors)} 个图结构问题:")
                for e in errors[:3]:
                    log.error(f"{e['message'][:80]}")
            else:
                log.success("图结构完整，无断链/孤立节点")
            # 2) 质量增强分析
            quality = kg.check_graph_quality()
            crit = [i for i in quality["issues"] if i["severity"] == "critical"]
            if crit:
                for ci in crit[:3]:
                    log.info(f"🔴 [{ci['category']}] {ci['message']}")
                    if ci.get("fix_hint"):
                        log.info(f"🔧 {ci['fix_hint']}")
            else:
                log.success("无空心概念等 critical 问题")
            s_sum = quality["summary"]
            log.info(f"ℹ️  汇总: 🔴{s_sum['critical']}/⚠️{s_sum['warning']}/ℹ️{s_sum['info']}")
        else:
            log.warning("图索引未构建，跳过（运行 graph build）")
    except ImportError:
        log.warning("kb_graph.py 不可用，跳过")
    except Exception as e:
        log.warning(f"图检查异常: {e}")

    log.info("\n" + "=" * 50)
    log.info("  全量验证完成")
    log.info("=" * 50)

    # ── v33.1: 写入结构化 JSON 日志 ──

    _bl = _tracked.get("broken_links", -1)
    _bl = _bl if _bl >= 0 else scan_broken_links(wr, args.book_id, ch)
    log_data = {
        "phase_status": {ph: s.get("phases", {}).get(ph, {}).get("status", "pending") for ph in DAG_ORDER},
        "broken_links": _bl,
        "content_fail": content_fail,
        "content_warn": content_warn,
        "mermaid_errors": _tracked.get("mermaid_errors", 0),
        "concept_verify_errors": _tracked.get("concept_verify_errors", 0),
        "placeholder_count": _tracked.get("placeholder_count", 0),
        "cross_chapter_conflicts": _tracked.get("cross_chapter_conflicts", 0),
        "cross_chapter_similar": _tracked.get("cross_chapter_similar", 0),
    }
    _log_check_result(wr, args.book_id, ch, "pipeline_validate", log_data)

    # ── 收集验证结果（供 pipeline_next 阻断使用）──
    # P20 fix: 复用前面检查过程中收集的指标，不重复扫描
    broken = _tracked.get("broken_links", -1)
    if broken < 0:
        broken = scan_broken_links(wr, args.book_id, ch)
    placeholder_count = _tracked.get("placeholder_count", -1)
    if placeholder_count < 0:
        placeholder_count = 0
        for p in DAG_ORDER:
            d = _phase_dir(wr, p)
            if not os.path.isdir(d):
                continue
            for f in os.listdir(d):
                if not f.endswith(".md"):
                    continue
                with open(os.path.join(d, f)) as fh:
                    c = fh.read()
                placeholder_count += len(re.findall(r"\{\{[^}]+\}\}", c))
    # v33.1: 收集全部检查结果
    critical_issues = []
    if broken > 0:
        critical_issues.append(f"发现 {broken} 个断链")
    if placeholder_count > 0:
        critical_issues.append(f"发现 {placeholder_count} 个 {{placeholder}} 残留")
    if content_fail > 0:
        critical_issues.append(f"内容深度检查发现 {content_fail} 个 FAIL")
    mermaid_errors = _tracked.get("mermaid_errors", 0)
    if mermaid_errors > 0:
        critical_issues.append(f"Mermaid 语法检查发现 {mermaid_errors} 个问题")
    concept_verify_errors = _tracked.get("concept_verify_errors", 0)
    if concept_verify_errors > 0:
        critical_issues.append("概念定义验证未通过（定义缺标记词/为空/不可检索）")
    render_fail = _tracked.get("render_fail", 0)
    if render_fail > 0:
        critical_issues.append(f"渲染校验发现 {render_fail} 个错误")
    cross_chapter_conflicts = _tracked.get("cross_chapter_conflicts", 0)
    if cross_chapter_conflicts > 0:
        critical_issues.append(f"跨章一致性检查发现 {cross_chapter_conflicts} 组同名概念冲突")
    # Task 7: 缓存验证结果到 state
    passed = len(critical_issues) == 0
    s["last_full_validate_passed"] = passed
    # 计算所有阶段目录的最新 mtime

    s["last_full_validate_mtime"] = _time_mod.time()
    _save_state(sp, s)
    return {"passed": passed, "critical": critical_issues}




def pipeline_auto(args: PipelineArgs) -> None:
    """自动执行全部 pipeline 阶段（从当前或指定阶段开始，顺序推进）

    v41.0: 支持 --dry-run 预览构建计划
    """
    wr = _wr(args)
    ch = args.chapter or "0"
    sp = _state_path(wr, args.book_id, ch)
    if not os.path.exists(sp):
        log.error("未初始化，请先运行 pipeline init")
        return

    s = _load_state(sp)
    start_phase = getattr(args, "from_phase", None)
    l1_only = getattr(args, "l1_only", False)
    dry_run = getattr(args, "dry_run", False)
    started = start_phase is None

    # L1 内容阶段 → build_kb_files.py 类型映射
    KB_TYPE_MAP = {
        "concepts": "concept",
        "ke": "ke",
        "entities": "entity",
        "kp": "kp",
        "sp": "sp",
        "scene": "scene",
    }
    L1_PHASES = ["concepts", "ke", "entities", "kp", "sp", "scene", "exercises", "solutions"]

    all_passed = True
    skipped_any = False

    for ph in DAG_ORDER:
        # --from 过滤：跳过起始阶段之前的阶段
        if not started:
            if ph == start_phase:
                started = True
            else:
                continue

        # --l1-only 过滤
        if l1_only and ph not in L1_PHASES:
            continue

        # 已完成则跳过
        if s["phases"].get(ph, {}).get("status") == "done":
            log.success(f"[{ph}] 已完成，跳过")
            continue

        # 依赖检查
        deps = DAG_DEPENDS.get(ph, [])
        deps_met = all(s["phases"].get(d, {}).get("status") == "done" for d in deps)
        if not deps_met:
            unmet = [d for d in deps if s["phases"].get(d, {}).get("status") != "done"]
            log.info(f"[{ph}] 依赖未满足: {unmet}，跳过")
            skipped_any = True
            continue

        log.info(f"\n{'='*60}\n🔄 [{ph}] {DAG_ITEM_HINTS.get(ph, '')}\n{'='*60}")

        # dry-run: 只报告计划，不执行
        if dry_run:
            log.info(f"[dry-run] 将执行: {ph} (依赖已满足)")
            continue

        success = False
        try:
            if ph == "chapter_toc":
                # v36.1: 自动提取章节 TOC
                src_dir = os.path.join(wr, DIR["SOURCE"])
                src_files = sorted(glob.glob(os.path.join(src_dir, f"第{ch}章*.md")))
                if not src_files:
                    log.error(f"未找到 20_正文/第{ch}章*.md，请先完成 Phase 1（file2md）")
                    s["phases"][ph]["status"] = "blocked"
                    _save_state(sp, s)
                    all_passed = False
                    continue
                src_path = src_files[0]
                ch_dir = os.path.join(wr, ".dag", f"第{ch}章")
                os.makedirs(ch_dir, exist_ok=True)
                toc_out = os.path.join(ch_dir, "chapter_toc.json")
                r = run_script("preprocess_toc.py", [src_path, "-o", toc_out], timeout=30)
                if r.success:
                    success = True
                    with open(toc_out) as _toc_f:
                        log.success(f"章节 TOC 已提取 ({len(_toc_f.read())} bytes)")
                    # 打印容器摘要（v36.5）
                    try:
                        with open(toc_out) as fh:
                            toc_data = json.load(fh)
                        containers = toc_data.get("containers", [])
                        summary = toc_data.get("summary", {})
                        cl = toc_data.get("container_level", "?")
                        cr = toc_data.get("container_reason", "")
                        log.info(f"容器层级: Lv{cl} — {cr}")
                        log.info(f"容器数: {summary.get('total_containers', len(containers))} 个")
                        for c in containers[:5]:
                            icon = "🔀" if c.get("auto_split") else "📦"
                            log.info(
                                f"{icon} L{c['line']}-L{c['line_end']} ({c['span_lines']}行) Lv{c['level']}: {c['text']}"
                            )
                        if len(containers) > 5:
                            log.info(f"... 共 {len(containers)} 个")
                    except Exception as e:
                        log.warning(f"章节 TOC 解析异常: {e}")
                else:
                    log.error(f"TOC 提取失败: {r.stderr[:200]}")
                    s["phases"][ph]["status"] = "blocked"
                    _save_state(sp, s)
                    all_passed = False
                    continue
            elif ph == "exercises":
                # 自动检测习题
                success = _auto_detect_and_build_exercises(wr, s, args, ch)
                if not success:
                    # v35.7: exercises 检测失败 → blocked，不可 done
                    # 检查是否是 Phase 1 未完成（.docx存在但 .md 缺失）
                    docx_glob = sorted(glob.glob(os.path.join(wr, f"第{ch}章*")))
                    docx_exists = any(f.endswith(".docx") for f in docx_glob)
                    source_md = os.path.join(wr, DIR["SOURCE"], f"第{ch}章")
                    md_exists = any(os.path.exists(f"{source_md}{ext}") for ext in ["", ".md"])
                    if docx_exists and not md_exists:
                        log.error(f"exercises 依赖 Phase 1（file2md 转换源文件），但 20_正文/ 中无第{ch}章 .md")
                        log.info(f'→ 请先运行: python3 file2md.py "第{ch}章*.docx" 然后复制到 20_正文/')
                    s["phases"][ph]["status"] = "blocked"
                    s["phases"][ph]["files"] = 0
                    _save_state(sp, s)
                    all_passed = False
                    continue
            elif ph in KB_TYPE_MAP:
                # L1 内容阶段：调用 build_kb_files.py
                success = _auto_build_kb_phase(wr, ph, KB_TYPE_MAP[ph], ch, s["book_id"], s.get("book_name", ""))
            elif ph == "solutions":
                # v35.7: 自动生成解答，失败则 blocked
                success = _auto_build_solutions(wr, s, args, ch)
                if not success:
                    # solutions 失败但 exercises 有文件 → blocked
                    ex_count = _phase_count(wr, "exercises")
                    if ex_count > 0:
                        log.error(f"solutions 生成失败（{ex_count}道习题缺少解答），标记为 blocked")
                        s["phases"][ph]["status"] = "blocked"
                        s["phases"][ph]["files"] = 0
                        _save_state(sp, s)
                        all_passed = False
                        continue
            elif ph in ("l2_indices", "l3_indices", "l4_indices"):
                # v43.13: 智能跳过——只在最后一章生成索引，非最后一章标记为 synced
                if not _is_last_chapter(wr, ch):
                    log.info(f"  ⏭️ [{ph}] 非最终章（第{ch}章），跳过索引生成（将在最后一章统一生成）")
                    s["phases"][ph]["status"] = "synced"
                    s["phases"][ph]["files"] = 0
                    _save_state(sp, s)
                    continue
                # v40.0: 索引阶段前自动构建知识图谱（L2+ 索引依赖图数据）
                if ph == "l2_indices":
                    try:
                        from kb_graph import KGraph

                        wiki_root = get_wiki_root(wr)
                        kg = KGraph(wiki_root)
                        if not os.path.exists(kg.db_path):
                            log.info("  📊 自动构建知识图谱（L2 索引依赖图数据）...")
                            kg.build()
                            log.success("知识图谱构建完成")
                    except Exception as e:
                        log.warning(f"知识图谱构建失败: {e}")
                idx_ok = _build_level_indices(wr, ph, args)
                success = idx_ok
            else:
                log.warning(f"[{ph}] 未知阶段类型，跳过")
                skipped_any = True
                continue

            if success:
                # v33.1: 每阶段构建后运行 comprehensive-content-check + validate_phase_output
                cc_passed, _cc_fail_count, _cc_fail_lines = _run_comprehensive_check_on_phase(wr, ph, ch)
                vresult = validate_phase_output(wr, ph, ch)
                if vresult["passed"] and cc_passed:
                    s["phases"][ph]["status"] = "done"
                    s["phases"][ph]["files"] = _phase_count(wr, ph)
                    _save_state(sp, s)
                    log.success(f"[{ph}] → done ({s['phases'][ph]['files']} 文件)，验证通过")
                else:
                    # v39.1: 自动重试一次（构建后修复可能已修复部分问题，重新验证）
                    log.warning(f"[{ph}] 验证未通过，自动重试...")
                    cc_passed2, cc_fail_count2, _cc_fail_lines2 = _run_comprehensive_check_on_phase(wr, ph, ch)
                    vresult2 = validate_phase_output(wr, ph, ch)
                    if vresult2["passed"] and cc_passed2:
                        s["phases"][ph]["status"] = "done"
                        s["phases"][ph]["files"] = _phase_count(wr, ph)
                        _save_state(sp, s)
                        log.success(f"[{ph}] → done ({s['phases'][ph]['files']} 文件)，重试验证通过")
                    else:
                        s["phases"][ph]["status"] = "blocked"
                        _save_state(sp, s)
                        all_issues = list(vresult2.get("issues", []))
                        if not cc_passed2:
                            all_issues.append(f"内容深度检查: {cc_fail_count2} 项 FAIL")
                        log.error(f"[{ph}] 构建完成但验证发现 {len(all_issues)} 项问题:")
                        for issue in all_issues[:5]:
                            log.error(f"{issue}")
                        all_passed = False
            else:
                # v35.7: 构建无输出 → blocked（而非静默 done）
                log.error(f"[{ph}] 构建未产生输出，标记为 blocked（需检查数据完整性）")
                s["phases"][ph]["status"] = "blocked"
                s["phases"][ph]["files"] = 0
                _save_state(sp, s)
                all_passed = False
        except PipelineError as e:
            log.error(f"[{ph}] pipeline 错误: {e}")
            s["phases"][ph]["status"] = "blocked"
            _save_state(sp, s)
            all_passed = False
        except Exception as e:
            log.error(f"[{ph}] 异常: {e}")
            s["phases"][ph]["status"] = "blocked"
            _save_state(sp, s)
            all_passed = False

    # 完成摘要
    log.info(f"\n{'='*60}")
    done_count = sum(1 for p in s["phases"].values() if p.get("status") == "done")
    total = len(s["phases"])
    log.info(f"自动执行完成: {done_count}/{total} 阶段 done")
    if skipped_any:
        log.warning("部分阶段因依赖未满足被跳过，可再次运行 pipeline auto 继续")
    log.info(f"{'='*60}")

    # dry-run 模式：只报告计划，不执行后处理
    if dry_run:
        log.info("\n[dry-run] 预览完成，未实际执行任何操作")
        return

    # 全部成功 → 自动修复断链 + 运行 pipeline validate
    if all_passed and not skipped_any:
        log.info("\n🎉 全部阶段完成，自动修复断链...\n")

        # Auto-fix broken links
        class FA:
            pass

        fa = FA()
        fa.wiki_root = args.wiki_root
        fa.book_id = args.book_id
        fa.fix = True
        fa.action = "fix"
        fix_broken_links(fa)
        log.info("\n  运行最终 pipeline validate...\n")
        pipeline_validate(args)
    elif skipped_any:
        log.info("\n💡 仍有未完成阶段，请再次运行 pipeline auto 或 pipeline next 继续")
    else:
        log.info("\n⚠️ 部分阶段验证未通过，请修复后运行 pipeline done <phase> 确认")


