"""dag_pipeline_done.py — Pipeline 阶段完成与推进 (next/done)

从 dag_pipeline.py 拆分，通过 re-export 保持兼容。
"""

import glob
import json
import os
import re
from types import SimpleNamespace

from dag_constants import (
    DAG_DEPENDS,
    DAG_ITEM_HINTS,
    DAG_ORDER,
    DIR,
    NODE_CONFIG,
    PipelineArgs,
)
from dag_index import _build_level_indices, check_stray_files, fix_broken_links
from dag_quality import check_level_quality
from dag_state import (
    PipelineLock,
    _book_name,
    _load_state,
    _phase_count,
    _phase_dir,
    _phase_latest_mtime,
    _save_state,
    _state_path,
    _wr,
    extract_exercises_from_text,
    get_wiki_root,
    verify_exercise_solution_mapping,
)
from log_utils import get_logger
from phase_validator import validate_phase_output
from script_runner import run_script

log = get_logger(__name__)

SKILL_DIR = os.path.dirname(os.path.abspath(__file__))

    # 获取已有文件名列表
    # 只添加不存在的 item
    # 构建 skeleton 并只塞入新 items
# ===== 原始单阶段操作 =====
    # ── v35.3: 自动检测工作区布局（嵌套/平铺）并保存到 .dag/config.yaml ──
    # ── v33.1: Phase 0 — 自动运行 schema.py 预检 YAML 数据 ──
            # 不自动更新状态——多章共用目录时文件数无法区分章节归属
            # 用户必须通过 pipeline done 显式标记完成
def pipeline_next(args: PipelineArgs) -> None:

    wr = _wr(args)
    ch = args.chapter or "0"
    # P0-3: 获取并发锁（进程退出时自动释放）
    lock = PipelineLock(wr)
    if not lock.acquire(timeout=5):
        log.error("无法获取 pipeline 锁 — 可能有另一个 pipeline 正在运行")
        return
    sp = _state_path(wr, args.book_id, ch)
    if not os.path.exists(sp):
        log.error("❌ 未初始化")
        return
    s = _load_state(sp)
    phases = s.get("phases", {})
    np = None
    for ph in DAG_ORDER:
        p = phases.get(ph, {})
        if p.get("status") == "pending":
            deps_met = all(phases.get(d, {}).get("status") == "done" for d in DAG_DEPENDS[ph])
            if deps_met:
                np = ph
                break
            else:
                log.warning(f"⏳ {ph} 依赖未满足: {[d for d in DAG_DEPENDS[ph] if phases.get(d,{}).get('status')!='done']}")
                return
    if not np:
        log.success("🎉 全部完成！")
        check_stray_files(args)
        return
    FA = SimpleNamespace(
        output=os.path.join(wr, ".dag", f"tmp_{np}_ch{ch}.json"),
        wiki_root=wr,
        book_id=s["book_id"],
        book_name=s.get("book_name", _book_name(s["book_id"])),
        chapter=ch,
        append=False,
    )
    os.makedirs(os.path.join(wr, ".dag"), exist_ok=True)
    log.info(f"\n{'='*60}\n🔄 [{np}] {DAG_ITEM_HINTS.get(np,'')}\n{'='*60}")

    # 🔍 Auto-validate: 每次 pipeline next 自动运行全量验证，确保当前已完成阶段输出无问题
    log.info("\n  🔍 自动运行 pipeline validate 验证当前阶段...")
    from dag_pipeline_run import pipeline_validate

    vr = pipeline_validate(args)
    if not vr.get("passed", True):
        critical = vr.get("critical", [])
        log.info("\n  ❌═══ 质量闸门阻断！═══❌")
        log.info(f"{len(critical)} 项关键问题未解决：(phase 已设为 blocked)")
        for c in critical[:5]:
            log.error(f"{c}")
        if len(critical) > 5:
            log.info(f"...还有 {len(critical)-5} 项")
        log.info("════════════════════════════")
        log.info("请修复上述问题后，运行 'pipeline next' 重新尝试")
        log.info(f"或运行 'pipeline done {np}' 强制跳过（不推荐）")
        s["phases"][np]["status"] = "blocked"
        _save_state(sp, s)
        return
    log.info("")

    if np == "exercises":
        # ⚠️ 强制要求完整章节文件名：第1章 概述.md（拒绝短名 第1章.md）
        ms = sorted(glob.glob(os.path.join(wr, DIR["SOURCE"], f"第{ch}章*")))
        if ms:
            # 过滤：排除仅"第X章.md"的短名，只保留含完整标题的文件
            full_names = [f for f in ms if os.path.basename(f) != f"第{ch}章.md"]
            if full_names:
                cf = full_names[0]
            else:
                log.error(f"20_正文/下仅发现短名文件，需使用完整文件名：第{ch}章 *.md")
                log.info(f"例如：第{ch}章 概述.md")
                cf = os.path.join(wr, DIR["SOURCE"], f"第{ch}章.md")  # 继续保持兼容但提示
        else:
            cf = os.path.join(wr, DIR["SOURCE"], f"第{ch}章.md")
        if os.path.exists(cf):
            with open(cf) as f:
                c = f.read()
            exs = extract_exercises_from_text(c, s["book_id"], ch)
            if exs:
                log.success(f"自动检测 {len(exs)} 道习题")
                os.makedirs(os.path.join(wr, NODE_CONFIG["exercises"]["dir"]), exist_ok=True)
                data = {
                    "template": "eval_template.md",
                    "quality_key": "eval/exercise",
                    "output_dir": os.path.join(wr, NODE_CONFIG["exercises"]["dir"]),
                    "book_id": s["book_id"],
                    "book_name": s.get("book_name", _book_name(s["book_id"])),
                    "chapter_num": ch,
                    "items": exs,
                }
                with open(FA.output, "w") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                log.info(f"运行: dag_controller.py phase exercises assemble {FA.output}")
                log.info("   然后: dag_controller.py pipeline done exercises")
                return
            else:
                log.warning("⚠️ 未检测到习题，可以跳过")
    # 逐章L1内容生成：当章节>0时，用 build_kb_files.py 生成该章的概念/KE/KP/SP/Scene
    if np in ("concepts", "ke", "kp", "sp", "scene") and ch and ch != "0":
        pm = {"concepts": "concept", "ke": "ke", "kp": "kp", "sp": "sp", "scene": "scene"}
        bf = os.path.abspath(os.path.join(os.path.dirname(__file__), "build_kb_files.py"))
        if os.path.exists(bf):
            log.info(f"使用 build_kb_files.py --type {pm[np]} --chapter {ch}")
            r = run_script(
                "build_kb_files.py",
                [
                    "--type",
                    pm[np],
                    "--chapter",
                    str(ch),
                    "--book-id",
                    s["book_id"],
                    "--book-name",
                    s.get("book_name", ""),
                    "--output-dir",
                    wr,
                    "--no-graph-check",
                ],
                timeout=300,
            )
            print(r.stdout[-500:] if r.stdout else "")
            if r.returncode != 0:
                log.warning(f"  ⚠️  build_kb_files.py 返回非零: {r.stderr[:300]}")
            # F2 fix: 构建后走验证流程，不直接标 done
            s["current_index"] = DAG_ORDER.index(np)
            vresult = validate_phase_output(wr, np, ch)
            if vresult["passed"]:
                s["phases"][np]["status"] = "done"
                _save_state(sp, s)
                log.success(f"[{np}] 已完成（第{ch}章），验证通过")
            else:
                s["phases"][np]["status"] = "blocked"
                _save_state(sp, s)
                log.error(f"[{np}] 构建完成但验证发现 {len(vresult['issues'])} 项问题:")
                for issue in vresult["issues"][:5]:
                    log.error(f"{issue}")
                log.info(f"修复后运行 'pipeline done {np}' 重新确认")
            return
        else:
            log.warning(f"  ⚠️  build_kb_files.py 不存在: {bf}")
    if np in ("l2_indices", "l3_indices", "l4_indices"):
        idx_ok = _build_level_indices(wr, np, args)
        s["current_index"] = DAG_ORDER.index(np)
        # F2 fix: 索引构建后也走验证
        vresult = validate_phase_output(wr, np, ch)
        if vresult["passed"] and idx_ok:
            s["phases"][np]["status"] = "done"
            _save_state(sp, s)
            log.success(f"[{np}] 构建完成，验证通过")
        else:
            s["phases"][np]["status"] = "done"
            _save_state(sp, s)
            warnings = len(vresult.get('issues', []))
            if not idx_ok:
                log.warning(f"[{np}] 索引构建存在错误，请检查日志")
            log.success(f"[{np}] 构建完成（{warnings} 项警告）")
        log.info("请运行 'pipeline next' 继续或 'pipeline status' 查看状态")
        return
    # Lazy import: 通过 facade 获取，使测试 mock dag_pipeline.build_skeleton 生效
    from dag_index import build_skeleton

    build_skeleton(np, FA)
    s["current_index"] = DAG_ORDER.index(np)
    phases[np]["status"] = "in_progress"
    _save_state(sp, s)




# v39.1: verify_exercise_solution_mapping 已移至 dag_utils.py（打破循环依赖）


# v38.0: validate_phase_output 已拆分到 phase_validator.py（通过顶部 import 导入）


# ===== 4. 12阶段DAG编排 =====


def pipeline_done(args: PipelineArgs) -> None:
    """标记指定阶段为 done，并运行自动验证

    v41.0: 支持 --dry-run 预览操作计划
    """
    wr = _wr(args)
    ch = args.chapter or "0"
    sp = _state_path(wr, args.book_id, ch)
    dry_run = getattr(args, "dry_run", False)
    if not os.path.exists(sp):
        log.error("未初始化")
        return
    s = _load_state(sp)
    ph = args.phase
    if ph not in DAG_ORDER:
        log.error("无效阶段")
        return

    # dry-run: 只报告计划
    if dry_run:
        status = s["phases"].get(ph, {}).get("status", "unknown")
        count = _phase_count(wr, ph)
        log.info(f"[dry-run] 将标记阶段 '{ph}' 为 done (当前状态: {status}, 文件数: {count})")
        return
    c = _phase_count(wr, ph)
    if c == 0 and ph not in ("l2_indices", "l3_indices", "l4_indices"):
        if ph == "exercises":
            # v35.2: exercises 为 0 时先尝试自动检测，避免遗漏习题
            src_dir = os.path.join(wr, DIR["SOURCE"])
            ms = sorted(glob.glob(os.path.join(src_dir, f"第{ch}章*"))) if ch != "0" else []
            if ms:
                full_names = [f for f in ms if os.path.basename(f) != f"第{ch}章.md"]
                cf = full_names[0] if full_names else ms[0]
                if os.path.exists(cf):
                    with open(cf) as f:
                        content = f.read()
                    exs = extract_exercises_from_text(content, s["book_id"], ch)
                    if exs:
                        import json as _json

                        ex_dir = os.path.join(wr, NODE_CONFIG["exercises"]["dir"])
                        os.makedirs(ex_dir, exist_ok=True)
                        data = {
                            "template": "eval_template.md",
                            "quality_key": "eval/exercise",
                            "output_dir": ex_dir,
                            "book_id": s["book_id"],
                            "book_name": s.get("book_name", _book_name(s["book_id"])),
                            "chapter_num": ch,
                            "items": exs,
                        }
                        tmp_json = os.path.join(wr, ".dag", f"tmp_auto_exercises_ch{ch}_done.json")
                        with open(tmp_json, "w") as fh:
                            _json.dump(data, fh, ensure_ascii=False, indent=2)
                        r = run_script("template_assembler.py", [tmp_json])
                        c = _phase_count(wr, ph)
                        log.success(f"自动检测到 {len(exs)} 道习题，已生成 {c} 个文件")
                    else:
                        log.warning(f"{ph} 为空（源文中未检测到习题），确认已完成？")
            else:
                log.warning(f"{ph} 为空，确认已完成？")
        else:
            log.warning(f"{ph} 为空，确认已完成？")
    # P5 fix: 先设为 in_progress，验证通过后才设为 done（避免竞态条件）
    # Task 7: 增量构建 — 如果阶段已是 done 且文件未变更，跳过重复验证
    force = getattr(args, "force", False)
    prev_status = s["phases"].get(ph, {}).get("status", "pending")
    prev_mtime = s["phases"].get(ph, {}).get("last_validated_mtime", 0)
    current_mtime = _phase_latest_mtime(wr, ph)
    if prev_status == "done" and not force and current_mtime > 0 and current_mtime <= prev_mtime:
        log.info(f"[{ph}] 文件未变更，跳过重复验证 (mtime={current_mtime:.0f})")
        return
    s["phases"][ph] = {"index": DAG_ORDER.index(ph), "status": "in_progress", "files": c, "deps": DAG_DEPENDS[ph]}
    _save_state(sp, s)
    log.info(f"🔄 [{ph}] 验证中 ({c} 文件)...")

    # Auto-validation: 每个 L1 阶段完成后自动校验输出
    l1_phases = {"concepts", "ke", "entities", "kp", "sp", "scene", "exercises", "solutions"}
    if ph in l1_phases:
        result = validate_phase_output(wr, ph, ch)
        if result["passed"]:
            log.success(f"{ph} 输出校验通过（{len(result['issues'])} 项问题）")
        else:
            log.warning(f"{ph} 输出校验发现 {len(result['issues'])} 项问题:")
            for issue in result["issues"]:
                log.error(f"{issue}")
            log.info("请在 'pipeline next' 前修复这些问题")

    # 概念根源质量闸门：三步骤验证 + 文件级校验
    if ph == "concepts":
        from tac_quality import run_type_quality_checks

        concept_dir = _phase_dir(wr, "concepts")
        concept_errors = []
        verified_count = 0
        total_concepts = 0
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
                        total_concepts += 1
                        qc = run_type_quality_checks(fpath, "concept_template.md")
                        if qc["passed"]:
                            verified_count += 1
                        else:
                            for issue in qc["critical"]:
                                concept_errors.append(f"{fname}: {issue}")

        # 运行 verify_concepts_from_source.py 做最终验证
        verify_script = os.path.join(os.path.dirname(__file__), "verify_concepts_from_source.py")
        source_dir = os.path.join(wr, DIR["SOURCE"])
        if os.path.exists(verify_script) and os.path.isdir(source_dir) and total_concepts > 0:
            import tempfile

            # 构建临时 JSON 用于验证
            concept_items = []
            for fname in sorted(os.listdir(concept_dir)):
                if not fname.endswith(".md"):
                    continue
                fpath = os.path.join(concept_dir, fname)
                with open(fpath) as fh:
                    fc = fh.read()
                tm = re.search(r"^---\n(.*?)\n---", fc, re.DOTALL)
                if not tm:
                    continue
                fm = {}
                for line in tm.group(1).split("\n"):
                    if ":" in line:
                        k, _, v = line.partition(":")
                        fm[k.strip()] = v.strip()
                if fm.get("type") != "concept":
                    continue
                body = fc.split("---", 2)[2] if fc.count("---") >= 2 else ""
                dm = re.search(r"^>\s*([^\n]+)", body, re.MULTILINE)
                definition = dm.group(1).strip() if dm else ""
                concept_items.append(
                    {
                        "name": fm.get("name", fname),
                        "definition": definition,
                        "source_chapter": fm.get("source_chapter", ""),
                        "source_from": fm.get("source_from", ""),
                    }
                )
            # v44.2: 仅验证当前章概念，避免跨章假阳性
            concept_items = [item for item in concept_items if str(item.get("source_chapter", "")) == str(ch)]
            if concept_items:
                tmp_json = os.path.join(tempfile.gettempdir(), f"_dag_concepts_verify_{ch}.json")
                import json as _json

                with open(tmp_json, "w") as fh:
                    _json.dump({"items": concept_items}, fh, ensure_ascii=False)
                r = run_script("verify_concepts_from_source.py", [tmp_json, "--source-dir", source_dir])
                # 解析输出获取统计（log 输出可能在 stdout 或 stderr）
                combined_output = r.stdout + r.stderr
                summary_match = re.search(r"保留: (\d+).*删除: (\d+)", combined_output, re.DOTALL)
                if summary_match:
                    _kept = int(summary_match.group(1))
                    removed = int(summary_match.group(2))
                    if removed > 0:
                        concept_errors.append(f"verify-source 验证失败：{removed} 个概念定义在正文中不可检索")
                elif not r.success:
                    concept_errors.append("verify-source 验证脚本执行失败")

        if concept_errors:
            log.info(f"\n  🔴 概念三步骤质量闸门未通过！{len(concept_errors)} 项问题:")
            for err in concept_errors[:10]:
                log.error(f"{err}")
            log.error(f"{total_concepts - verified_count}/{total_concepts} 个概念有问题")
            log.success(f"{verified_count}/{total_concepts} 个概念通过三步骤验证")
            log.info("🔧 修复方法：从 20_正文/ 中逐字提取定义文本，然后重新 assemble")
            # 设置 blocked 状态
            s["phases"][ph]["status"] = "blocked"
            _save_state(sp, s)
            log.info(f"\n  ⛔ [{ph}] 阶段状态设为 'blocked'（因概念质量闸门未通过）")
            log.info(f"修复后重新执行 pipeline done {ph} 确认")
            return
        else:
            log.success(f"概念三步骤验证通过：{verified_count}/{total_concepts} 个概念全部可追溯至正文")

    # ── v33.1: KE 溯源验证（ke 阶段完成时）──
    if ph == "ke":
        ke_dir = _phase_dir(wr, "ke")
        verify_source_script = os.path.join(os.path.dirname(__file__), "verify_concepts_from_source.py")
        source_dir = os.path.join(wr, DIR["SOURCE"])
        if os.path.exists(verify_source_script) and os.path.isdir(source_dir) and os.path.isdir(ke_dir):
            ke_count = len([f for f in os.listdir(ke_dir) if f.endswith(".md")])
            if ke_count > 0:
                # 收集 KE 数据用于验证
                ke_items = []
                for fname in sorted(os.listdir(ke_dir)):
                    if not fname.endswith(".md"):
                        continue
                    fpath = os.path.join(ke_dir, fname)
                    with open(fpath) as fh:
                        fc = fh.read()
                    tm = re.search(r"^---\n(.*?)\n---", fc, re.DOTALL)
                    if not tm:
                        continue
                    fm = {}
                    for line in tm.group(1).split("\n"):
                        if ":" in line:
                            k, _, v = line.partition(":")
                            fm[k.strip()] = v.strip()
                    if fm.get("type") != "knowledge-element":
                        continue
                    body = fc.split("---", 2)[2] if fc.count("---") >= 2 else ""
                    # 提取 KE 的 source 或 definition
                    source_match = re.search(r"(?:出处原文|source)[：:]\s*(.+?)(?:\n|$)", body)
                    def_match = re.search(r"##\s*定义.*?\n(.+?)(?:\n##|\n---|$)", body, re.DOTALL)
                    ke_text = ""
                    if source_match:
                        ke_text = source_match.group(1).strip()
                    elif def_match:
                        ke_text = def_match.group(1).strip()[:120]
                    ke_items.append(
                        {
                            "name": fm.get("name", fname),
                            "definition": ke_text,
                            "source_chapter": fm.get("source_chapter", ""),
                            "source_from": fm.get("source_from", ""),
                        }
                    )
                # v44.2: 仅验证当前章 KE，避免跨章假阳性
                ke_items = [item for item in ke_items if str(item.get("source_chapter", "")) == str(ch)]
                if ke_items:
                    import json as _json
                    import tempfile

                    tmp_json = os.path.join(tempfile.gettempdir(), f"_dag_ke_verify_{ch}.json")
                    with open(tmp_json, "w") as fh:
                        _json.dump({"items": ke_items}, fh, ensure_ascii=False)
                    r = run_script("verify_concepts_from_source.py", [tmp_json, "--source-dir", source_dir], timeout=120)
                    summary_match = re.search(r"保留: (\d+).*删除: (\d+)", r.stdout + r.stderr, re.DOTALL)
                    ke_removed = 0
                    if summary_match:
                        _ke_kept = int(summary_match.group(1))
                        ke_removed = int(summary_match.group(2))
                    elif r.returncode != 0:
                        ke_removed = 1  # 解析失败但脚本报错，保守标记
                    if ke_removed > 0:
                        log.info(f"\n  ⚠️  KE 溯源验证: {ke_removed} 个 KE 定义在正文中不可检索（不阻断，仅警告）")
                    else:
                        log.success(f"KE 溯源验证通过（{ke_count} 个 KE 全部可追溯至正文）")

    # 图连通性质量闸门：每个 L1 阶段完成后验证图连通性
    # v22.0 增强：
    # - pipeline_done: 仅报告不阻断（跨阶段引用需等上游构建完才产生）
    # - check_level_quality L1: 做真正的阻断闸门（所有阶段完成后检查）
    if ph in l1_phases:
        try:
            wiki_root = get_wiki_root(wr)
            from kb_graph import KGraph

            kg = KGraph(wiki_root)
            if os.path.exists(kg.db_path):
                # v40.0: 增量构建图谱（跳过未变更文件，提升性能）
                kg.build_incremental()
                # 综合图质量检查（传入当前阶段，过滤掉尚不存在的检查）
                quality = kg.check_graph_quality(phase=ph)
                critical_issues = [i for i in quality["issues"] if i["severity"] == "critical"]
                warning_issues = [i for i in quality["issues"] if i["severity"] == "warning"]

                if critical_issues:
                    # pipeline_done 阶段：只报告不阻断
                    # 阻断由 check_level_quality L1 级别闸门承担
                    log.info(f"\n  📊 [图质量] {len(critical_issues)} 项潜在问题（不阻断，L1层级闸门会最终把关）:")
                    for ci in critical_issues:
                        log.warning(f"[{ci['category']}] {ci['message']}")
                        if ci.get("fix_hint"):
                            log.info(f"{ci['fix_hint']}")
                elif warning_issues:
                    log.info(f"\n  📊 [图质量] {len(warning_issues)} 项 warning 问题:")
                    for wi in warning_issues[:5]:
                        log.warning(f"{wi['message']}")
                    if len(warning_issues) > 5:
                        log.info(f"...还有 {len(warning_issues) - 5} 项")
                else:
                    log.success("图质量检查通过")

                # 连通性检查（不阻断，仅报告）
                conn_result = kg.check_l1_connectivity(phase=ph)
                if not conn_result["overall_passed"]:
                    for chk in conn_result["checks"]:
                        if not chk["passed"]:
                            log.info(f"📊 {chk['check_name']}: {', '.join(chk['issues'][:2])}")
        except ImportError:
            pass
        except Exception as e:
            log.warning(f"图质量检查异常（不影响阶段完成，但建议排查）: {e}")

    # 验证习题-解答 1:1 对应关系
    if ph == "solutions":
        missing = verify_exercise_solution_mapping(wr)
        if missing:
            log.warning(f"发现 {len(missing)} 道习题缺少对应解答:")
            for m in missing:
                log.info(f"缺少: {m}")
            log.info("请生成解答后通过 'pipeline done solutions' 重新确认")
            # 设置 blocked 状态
            s["phases"][ph]["status"] = "blocked"
            _save_state(sp, s)
            log.info(f"\n  ⛔ [{ph}] 阶段状态设为 'blocked'（因习题-解答映射不完整）")
            log.info(f"请生成解答后重新执行 pipeline done {ph} 确认")
            return
        else:
            log.success("习题-解答 1:1 对应关系验证通过")
    # 层级质量闸门：检查当前阶段所属层级是否全部完成
    level_map = {
        "concepts": "L1",
        "ke": "L1",
        "entities": "L1",
        "kp": "L1",
        "sp": "L1",
        "scene": "L1",
        "exercises": "L1",
        "solutions": "L1",
        "l2_indices": "L2",
        "l3_indices": "L3",
        "l4_indices": "L4",
    }
    cur_level = level_map.get(ph)
    if cur_level:
        lv_phases = [p for p, lv in level_map.items() if lv == cur_level]
        level_done = all(s["phases"].get(p, {}).get("status") == "done" for p in lv_phases)
        if level_done:
            log.info(f"\n  📋 [{cur_level}] 层级质量审核中...")
            qr = check_level_quality(args, cur_level)
            if qr["passed"]:
                log.success(f"[{cur_level}] {qr['label']}: 全部通过（{len(qr['detail'])} 项检查）")
            else:
                log.warning(f"[{cur_level}] {qr['label']}: {len(qr['critical'])} 项关键问题未通过")
                for issue in qr["critical"]:
                    log.error(f"{issue}")
                for issue in qr["warnings"]:
                    log.warning(f"{issue}")
                log.info("建议通过 'pipeline validate' 查看完整报告并修复")
                # 如果有 critical 问题，设置 blocked 阻止继续
                if qr["critical"]:
                    s["phases"][ph]["status"] = "blocked"
                    _save_state(sp, s)
                    log.info(f"\n  ⛔ [{ph}] 阶段状态设为 'blocked'（层级质量闸门未通过）")
                    log.info(f"修复后重新执行 pipeline done {ph} 确认")
                    return

    # 所有验证通过，提升为 done
    s["phases"][ph]["status"] = "done"
    # Task 7: 记录验证时的最新 mtime
    s["phases"][ph]["last_validated_mtime"] = _phase_latest_mtime(wr, ph)
    _save_state(sp, s)
    log.info(f"\n  ✅ [{ph}] → done ({c} 文件)")

    # 全部12个阶段完成 → 庆祝
    if all(p.get("status") == "done" for p in s["phases"].values()):
        log.info("\n🎉 四级知识库全部构建完成！")
        log.info("  运行 'pipeline validate' 做最终全量验证")
        check_stray_files(args)
        fix_broken_links(args)


