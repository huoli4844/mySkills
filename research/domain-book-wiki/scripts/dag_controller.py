"""dag_controller.py — 知识库构建编排控制器（CLI 入口）

三层架构（v35.7 拆分）：
  dag_controller.py  ← CLI 入口 + main()
  dag_pipeline.py    ← pipeline 编排操作
  dag_quality.py     ← 知识图谱质量检查
  dag_index.py       ← 索引生成 + 文件完整性检查
  dag_utils.py       ← 常量、配置和工具函数

DAG 顺序（四级分层）：
  L1: concepts → ke → entities → kp → sp → scene → exercises → solutions
  L2: l2_indices（单书总揽）
  L3: l3_indices（领域总控）
  L4: l4_indices（知识库总控）
"""

import argparse
import json
import os
import sys

# 公共导入
from dag_constants import DIR, NODE_CONFIG, PipelineError
from dag_index import assemble, auto_detect_exercises, build_skeleton, check_stray_files, fix_broken_links, verify

# 子模块导入
from dag_pipeline_ops import phase_add, pipeline_init, pipeline_status
from dag_pipeline_run import pipeline_auto, pipeline_validate
from dag_pipeline_done import pipeline_done, pipeline_next
from dag_quality import pipeline_check
from dag_state import _wr
from log_utils import get_logger
from pipeline_batch import run_batch_pipeline, generate_phase2_tasks
from pipeline_extras import pipeline_fill_solutions, pipeline_fix, pipeline_review, pipeline_rollback

log = get_logger(__name__)

SKILL_DIR = os.path.dirname(os.path.abspath(__file__))


def main():
    p = argparse.ArgumentParser(description="DAG Controller v2.2")
    sp = p.add_subparsers(dest="cmd")

    # phase
    ph = sp.add_parser("phase")
    node_phase_choices = [k for k in NODE_CONFIG if k not in ("l2_indices", "l3_indices", "l4_indices")]
    ph.add_argument("phase", choices=node_phase_choices)
    ph.add_argument("action", choices=["skeleton", "assemble", "verify", "auto-detect", "verify-source"])
    ph.add_argument("input", nargs="?")
    ph.add_argument("-o", "--output", default=None, help="输出路径（默认 tempfile 下 skeleton.json）")
    ph.add_argument("-w", "--wiki-root")
    ph.add_argument("--book-id", default=None)
    ph.add_argument("--book-name")
    ph.add_argument("-c", "--chapter")
    ph.add_argument("--chapter-file")
    ph.add_argument("--append", action="store_true")

    # pipeline
    pl = sp.add_parser("pipeline")
    pl.add_argument(
        "action", choices=["init", "status", "next", "done", "check", "validate", "auto", "preflight", "fill-solutions", "rollback", "batch", "insights", "fix", "review", "consistency", "build-all", "phase2-tasks"]
    )
    pl.add_argument("phase", nargs="?")
    pl.add_argument("-w", "--wiki-root")
    pl.add_argument("--book-id", default=None)
    pl.add_argument("--book-name")
    pl.add_argument("-c", "--chapter")
    pl.add_argument("--from", dest="from_phase", help="从指定阶段开始（例如: --from concepts）")
    pl.add_argument("--l1-only", action="store_true", help="仅执行 L1 阶段（跳过 L2/L3/L4 索引）")
    pl.add_argument("--retry", type=int, default=0, help="质量闸门失败后自动重试次数（默认0，推荐3）")
    pl.add_argument("--from-chapter", dest="from_chapter", help="从指定章节开始（断点续传）")
    pl.add_argument("--no-cache", dest="no_cache", action="store_true", help="禁用增量缓存（强制重建所有章节）")
    pl.add_argument("--field", dest="field", help="仅检查/修复指定字段（如 solved_problem、entity_type）")
    pl.add_argument("--auto-fill", dest="auto_fill", action="store_true", help="自动填充模式（fix 命令可用，尝试推断并写入）")
    pl.add_argument("--source-dir", dest="source_dir", help="源文件目录（build-all 命令用）")

    # check (shortcut)
    ck = sp.add_parser("check")
    ck.add_argument("-w", "--wiki-root")
    ck.add_argument("--book-id", default=None)
    ck.add_argument("-c", "--chapter")

    # fix (断链自动修复)
    fx = sp.add_parser("fix")
    fx.add_argument("-w", "--wiki-root")
    fx.add_argument("--book-id", default=None)
    fx.add_argument("-c", "--chapter")
    fx.add_argument("--fix", action="store_true", help="修复模式（默认仅扫描）")

    # stray (子代理路径检查)
    sy = sp.add_parser("stray")
    sy.add_argument("-w", "--wiki-root")
    sy.add_argument("--book-id", default=None)
    sy.add_argument("-c", "--chapter")

    # add (增量更新)
    ad = sp.add_parser("add")
    add_phase_choices = [k for k in NODE_CONFIG if k not in ("l2_indices", "l3_indices", "l4_indices")]
    ad.add_argument("phase", choices=add_phase_choices)
    ad.add_argument("input", help="新 items 的 JSON 文件")
    ad.add_argument("-w", "--wiki-root")
    ad.add_argument("--book-id", default=None)
    ad.add_argument("--book-name")
    ad.add_argument("-c", "--chapter")

    # graph (知识图谱)
    gr = sp.add_parser("graph")
    gr.add_argument(
        "action",
        choices=[
            "build",
            "query",
            "search",
            "trace",
            "impact",
            "validate",
            "mermaid",
            "connectivity",
            "similar",
            "centrality",
            "bridge",
            "path",
            "build-order",
            "quality",
        ],
    )
    gr.add_argument("args", nargs="*", help="查询参数")
    gr.add_argument("-w", "--wiki-root")
    gr.add_argument("--incremental", action="store_true", help="增量构建（跳过未变更文件）")

    a = p.parse_args()

    if not a.cmd:
        p.print_help()
        return

    # 快捷命令
    if a.cmd == "check":
        from types import SimpleNamespace as _NS

        pipeline_check(
            _NS(
                wiki_root=getattr(a, "wiki_root", None),
                book_id=getattr(a, "book_id", None),
                chapter=getattr(a, "chapter", None),
                phase=None,
                book_name=None,
                fix=False,
                action="scan",
            )
        )
        return
    if a.cmd == "fix":
        from types import SimpleNamespace as _NS

        fix_broken_links(
            _NS(
                wiki_root=getattr(a, "wiki_root", None),
                book_id=getattr(a, "book_id", None),
                chapter=getattr(a, "chapter", None),
                phase=None,
                book_name=None,
                fix=a.fix,
                action="fix" if a.fix else "scan",
            )
        )
        return
    if a.cmd == "stray":
        from types import SimpleNamespace as _NS

        check_stray_files(
            _NS(
                wiki_root=getattr(a, "wiki_root", None),
                book_id=getattr(a, "book_id", None),
                chapter=getattr(a, "chapter", None),
            )
        )
        return

    # phase
    if a.cmd == "phase":
        if a.action == "skeleton":
            build_skeleton(a.phase, a)
        elif a.action == "assemble":
            if not a.input:
                raise PipelineError("cli", "需要 JSON")
            assemble(a.phase, a.input, a)
        elif a.action == "auto-detect":
            if a.phase == "exercises":
                auto_detect_exercises(a)
            else:
                log.error("❌ auto-detect 仅支持 exercises")
        elif a.action == "verify":
            cfg = NODE_CONFIG.get(a.phase)
            if cfg:
                verify(a.phase, os.path.join(_wr(a), cfg["dir"]), a)
        elif a.action == "verify-source":
            if a.phase != "concepts":
                raise PipelineError("verify-source", "仅支持 concepts 阶段")
            if not a.input:
                raise PipelineError("verify-source", "需要概念 JSON 文件路径")
            from script_runner import run_script

            wr = _wr(a)
            source_dir = os.path.join(wr, DIR["SOURCE"])
            output_path = a.output or a.input.replace(".json", "_verified.json")
            args = [a.input, "--source-dir", source_dir, "--output", output_path]
            if a.input == output_path:
                args.append("--in-place")
            log.info(f"输入: {a.input}")
            log.info(f"正文: {source_dir}")
            log.info(f"输出: {output_path}")
            result = run_script("verify_concepts_from_source.py", args)
            if result.stdout:
                print(result.stdout, end="")
            if result.success:
                log.success("全部概念定义均可从正文提取")
            else:
                log.warning("部分概念定义未在正文中找到，已自动删除")
                log.info(f"请检查输出文件: {output_path}")

    # pipeline
    elif a.cmd == "pipeline":
        if a.action == "init":
            pipeline_init(a)
        elif a.action == "status":
            pipeline_status(a)
        elif a.action == "next":
            pipeline_next(a)
        elif a.action == "done":
            if not a.phase:
                raise PipelineError("pipeline", "done 需要指定阶段")
            pipeline_done(a)
        elif a.action == "check":
            pipeline_check(a)
        elif a.action == "validate":
            pipeline_validate(a)
        elif a.action == "auto":
            pipeline_auto(a)
        elif a.action == "preflight":
            # v52.4: 预验证闸门 — 写入YAML后、pipeline auto前执行
            wr = os.path.abspath(a.wiki_root) if a.wiki_root else os.path.abspath(".")
            ch = str(getattr(a, "chapter", "0") or "0")
            import importlib.util
            sl_spec = importlib.util.spec_from_file_location(
                "schema_loader",
                os.path.join(SKILL_DIR, "schema_loader.py"),
            )
            if sl_spec and sl_spec.loader:
                sl = importlib.util.module_from_spec(sl_spec)
                sl_spec.loader.exec_module(sl)
                _run_preflight(wr, ch, sl)
            else:
                log.warning("schema_loader.py 不可用，跳过 preflight（降级到普通 auto）")
                pipeline_auto(a)
        elif a.action == "fill-solutions":
            pipeline_fill_solutions(a)
        elif a.action == "rollback":
            if not a.phase:
                raise PipelineError("pipeline", "rollback 需要指定阶段")
            pipeline_rollback(a)
        elif a.action == "fix":
            # v47.0: 增量修复命令
            pipeline_fix(a)
        elif a.action == "review":
            # v50.7: 内容深度 Agent 二次审核
            pipeline_review(a)
        elif a.action == "build-all":
            # v50.8: 一键全流程（Phase 0→1→1.5→Phase2任务生成→3+）
            from pipeline_batch import pipeline_build_all
            pipeline_build_all(a)
        elif a.action == "phase2-tasks":
            # v50.8: 仅为指定章生成 Phase 2 任务
            wr = os.path.abspath(a.wiki_root) if a.wiki_root else os.path.abspath(".")
            ch = str(getattr(a, "chapter", "0") or "0")
            generate_phase2_tasks(wr, getattr(a, "book_id", ""), ch)
        elif a.action == "batch":
            # v45.2: 批量章编排 | v46.0: 增量缓存
            wr = os.path.abspath(a.wiki_root) if a.wiki_root else os.path.abspath(".")
            result = run_batch_pipeline(
                wr=wr,
                book_id=a.book_id,
                retry=getattr(a, "retry", 0),
                from_chapter=getattr(a, "from_chapter", None),
                l1_only=getattr(a, "l1_only", False),
                no_cache=getattr(a, "no_cache", False),
            )
            if not result["success"]:
                raise PipelineError("batch", "批量构建失败，详情见上方日志")
        elif a.action == "insights":
            # v46.0: 知识图谱洞察
            wr = os.path.abspath(a.wiki_root) if a.wiki_root else os.path.abspath(".")
            from pipeline_insights import generate_insights_report
            report = generate_insights_report(wr, a.book_id)
            print(report)
        elif a.action == "consistency":
            # v47.0: 跨章一致性校验
            wr = os.path.abspath(a.wiki_root) if a.wiki_root else os.path.abspath(".")
            from pipeline_insights import check_cross_chapter_consistency
            result = check_cross_chapter_consistency(wr, getattr(a, "book_id", None))
            import json
            summary = result.get("summary", {})
            log.info(f"📋 跨章一致性校验完成")
            log.info(f"   扫描概念: {result.get('total_concepts', 0)} 个")
            log.info(f"   同名冲突: {summary.get('same_name_conflict_count', 0)} 组")
            log.info(f"   近名冲突: {summary.get('similar_name_conflict_count', 0)} 组")
            if summary.get("severity_breakdown"):
                for k, v in summary["severity_breakdown"].items():
                    if v > 0:
                        labels = {
                            "definition_mismatch": "定义严重不一致",
                            "definition_divergence": "定义有分歧",
                            "bloom_mismatch": "Bloom层级不一致",
                            "classification_mismatch": "分类归属不一致",
                            "potential_merge_candidate": "可能需合并",
                            "potential_duplicate_low_def_sim": "近名但定义差异大",
                        }
                        log.warning(f"   {labels.get(k, k)}: {v} 项")

    # add (增量更新)
    elif a.cmd == "add":
        phase_add(a)

    # graph (知识图谱)
    elif a.cmd == "graph":
        wr = os.path.abspath(a.wiki_root) if hasattr(a, "wiki_root") and a.wiki_root else os.path.abspath(".")
        arg_str = " ".join(a.args) if hasattr(a, "args") and a.args else ""
        try:
            from kb_graph import KGraph

            kg = KGraph(wr)
            if a.action == "build":
                if a.incremental:
                    kg.build_incremental()
                else:
                    kg.build()
            elif a.action == "validate":
                if not os.path.exists(kg.db_path):
                    raise PipelineError("graph", "图索引不存在，先运行 build")
                issues = kg.validate()
                if issues:
                    for i in issues:
                        icon = {"error": "❌", "warn": "⚠️", "info": "ℹ️"}
                        log.info(f"{icon.get(i['severity'],'?')} [{i['type']}] {i['message']}")
                else:
                    log.success("图结构完整")
            elif a.action == "query":
                if not arg_str:
                    raise PipelineError("graph", "需要节点名")
                log.info(json.dumps(kg.query(arg_str), ensure_ascii=False, indent=2, default=str))
            elif a.action == "search":
                if not arg_str:
                    raise PipelineError("graph", "需要搜索词")
                log.info(json.dumps(kg.search(arg_str), ensure_ascii=False, indent=2, default=str))
            elif a.action == "trace":
                if not arg_str:
                    raise PipelineError("graph", "需要节点名")
                log.info(json.dumps(kg.trace(arg_str), ensure_ascii=False, indent=2, default=str))
            elif a.action == "impact":
                if not arg_str:
                    raise PipelineError("graph", "需要节点名")
                log.info(json.dumps(kg.impact(arg_str), ensure_ascii=False, indent=2, default=str))
            elif a.action == "mermaid":
                if not arg_str:
                    raise PipelineError("graph", "需要节点名")
                log.info(kg.export_mermaid(arg_str))
            elif a.action == "connectivity":
                result = kg.check_l1_connectivity()
                log.info(json.dumps(result, ensure_ascii=False, indent=2, default=str))
                if result["overall_passed"]:
                    log.success("所有阶段间引用完整")
                else:
                    for chk in result["checks"]:
                        if not chk["passed"]:
                            log.warning(f"{chk['check_name']}: {', '.join(chk['issues'][:3])}")
            elif a.action == "similar":
                result = kg.check_similar_names()
                log.info(json.dumps(result, ensure_ascii=False, indent=2, default=str))
                if result["total"] > 0:
                    log.warning(f"发现 {result['total']} 对相似节点名")
            elif a.action == "centrality":
                result = kg.degree_centrality()
                log.info(json.dumps(result, ensure_ascii=False, indent=2, default=str))
                if result["orphan_count"] > 0:
                    log.warning(f"{result['orphan_count']} 个孤立节点")
            elif a.action == "bridge":
                result = kg.check_bridge_gaps()
                log.info(json.dumps(result, ensure_ascii=False, indent=2, default=str))
                if result["total_gaps"] > 0:
                    log.warning(f"{result['total_gaps']} 个桥接缺口")
            elif a.action == "path":
                result = kg.check_path_integrity()
                log.info(json.dumps(result, ensure_ascii=False, indent=2, default=str))
                if result["broken_count"] > 0:
                    log.warning(f"路径断裂: {result['broken_count']} 处")
            elif a.action == "build-order":
                result = kg.suggest_build_order()
                log.info(json.dumps(result, ensure_ascii=False, indent=2, default=str))
                if result["cycle_warnings"]:
                    for w in result["cycle_warnings"]:
                        log.warning(f"{w}")
            elif a.action == "quality":
                result = kg.check_graph_quality()
                log.info(json.dumps(result, ensure_ascii=False, indent=2, default=str))
                if result["quality_pass"]:
                    log.success("图质量通过：无 critical 级别问题")
                else:
                    crits = [i for i in result["issues"] if i["severity"] == "critical"]
                    log.info(f"🔴 图质量未通过: {len(crits)} 项 critical 问题")
                    for ci in crits[:3]:
                        log.error(f"[{ci['category']}] {ci['message']}")
                        if ci.get("fix_hint"):
                            log.info(f"🔧 {ci['fix_hint']}")
                s = result["summary"]
                log.info(f"汇总: 🔴 {s['critical']} / ⚠️ {s['warning']} / ℹ️ {s['info']}")
        except ImportError:
            raise PipelineError("graph", "需要 kb_graph.py（domain-book-wiki 技能）") from None


# ============================================================
# v52.4: Preflight — 写入 YAML 后的预验证闸门
# ============================================================
def _run_preflight(wr: str, ch: str, sl) -> None:
    """对第N章所有 YAML data 文件执行预验证。发现问题时不阻断，输出完整清单。"""
    import yaml as _yaml

    data_dir = os.path.join(wr, ".dag", f"第{ch}章", "data")
    if not os.path.isdir(data_dir):
        log.warning(f"❌ data 目录不存在: {data_dir}")
        log.warning("   请先写入 YAML 数据文件到该目录再运行 preflight")
        return

    phase_data_map = {
        "concepts.yaml": ("concept", "核心概念"),
        "kes.yaml": ("ke", "知识要素"),
        "entities.yaml": ("entity", "实体"),
        "kps.yaml": ("kp", "知识点"),
        "sps.yaml": ("sp", "技能点"),
        "scenes.yaml": ("scene", "应用场景"),
        "exercises.yaml": ("exercise", "习题"),
        "solutions.yaml": ("solution", "解答"),
    }

    total_issues = 0
    total_items = 0

    for fname, (type_name, cn_label) in sorted(phase_data_map.items()):
        fpath = os.path.join(data_dir, fname)
        issues: list[str] = []
        items_count = 0

        if not os.path.exists(fpath):
            issues.append("❌ 文件不存在")
        else:
            fsize = os.path.getsize(fpath)
            if fsize == 0:
                issues.append("❌ 空文件")
            else:
                with open(fpath, encoding="utf-8") as f:
                    try:
                        data = _yaml.safe_load(f)
                    except _yaml.YAMLError as e:
                        issues.append(f"❌ YAML 语法错误: {e}")
                        data = None

                if data is None:
                    issues.append("❌ 解析结果为 None")
                elif not isinstance(data, list):
                    issues.append(f"❌ 格式错误: 期望 YAML list，得到 {type(data).__name__}")
                else:
                    items_count = len(data)
                    canonical = sl.get_placeholder_fields(type_name)
                    canonical_set = set(canonical)
                    for idx, item in enumerate(data):
                        if not isinstance(item, dict):
                            continue
                        bd = item.get("bd", {})
                        if not isinstance(bd, dict):
                            issues.append(f"第{idx+1}项: bd 不是 dict")
                            continue
                        bd_fields = set(bd.keys())
                        missing = canonical_set - bd_fields
                        extra = bd_fields - canonical_set
                        name = item.get("name", f"[{idx}]")
                        if missing:
                            mlist = list(sorted(missing))
                            issues.append(f"⚠️ [{name}] 缺 {len(mlist)} 字段: {', '.join(mlist[:5])}")
                        if extra:
                            elist = list(sorted(extra))
                            issues.append(f"⚠️ [{name}] 多余 {len(elist)} 字段: {', '.join(elist[:5])}")
                        fm = item.get("fm", {})
                        conf = fm.get("confidence", 0)
                        if conf > 0.95 or conf < 0.5:
                            issues.append(f"⚠️ [{name}] confidence={conf} 超出合理范围 [0.5, 0.95]")

        total_items += items_count
        n_issues = len(issues)
        status = "✅" if n_issues == 0 else f"⚠️ {n_issues}项"
        log.info(f"  {status} {fname:<18} ({cn_label}, {items_count}项)")

        for iss in issues:
            log.info(f"      {iss}")

        total_issues += n_issues

    # 习题-解答配对检查
    log.info("")
    ex_path = os.path.join(data_dir, "exercises.yaml")
    sol_path = os.path.join(data_dir, "solutions.yaml")
    if os.path.exists(ex_path) and os.path.exists(sol_path):
        with open(ex_path) as f:
            ex_data = _yaml.safe_load(f) or []
        with open(sol_path) as f:
            sol_data = _yaml.safe_load(f) or []
        if len(ex_data) != len(sol_data):
            log.info(f"  ⚠️ 习题({len(ex_data)}) ≠ 解答({len(sol_data)}) 数量不匹配")
            total_issues += 1
        else:
            log.info(f"  ✅ 习题-解答配对: {len(ex_data)} = {len(sol_data)} ✓")

    # 总结
    log.info("")
    if total_issues == 0:
        log.info("🎉 Preflight 全部通过: %d 项数据，无问题", total_items)
    else:
        log.info("📋 Preflight 发现 %d 项问题（上述 ⚠️ 标记），请修复后运行 pipeline auto", total_issues)


if __name__ == "__main__":
    try:
        main()
    except PipelineError as e:
        log.error(str(e))
        sys.exit(1)
