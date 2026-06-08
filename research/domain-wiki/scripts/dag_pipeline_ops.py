"""dag_pipeline_ops.py — Pipeline 基础操作 (init/status/add)

从 dag_pipeline.py 拆分，通过 re-export 保持兼容。
"""

import json
import os

from dag_constants import (
    DAG_DEPENDS,
    DAG_ORDER,
    NODE_CONFIG,
    PipelineArgs,
    PipelineError,
)
from dag_index import fix_broken_links
from dag_state import (
    WorkspacePaths,
    _book_name,
    _load_state,
    _phase_count,
    _save_state,
    _state_path,
    _wr,
    detect_layout,
    save_workspace_config,
)
from log_utils import get_logger
from pipeline_auto import _print_pipeline_status
from script_runner import run_script

log = get_logger(__name__)

def phase_add(args: PipelineArgs) -> None:
    """向已有 phase 增量添加 items，不覆盖已有文件"""
    cfg = NODE_CONFIG.get(args.phase)
    if not cfg:
        log.error(f"无效阶段: {args.phase}")
        return

    if not args.input or not os.path.exists(args.input):
        log.error("需要 --input 指定新 items 的 JSON 文件")
        return

    with open(args.input) as f:
        new_data = json.load(f)

    new_items = new_data.get("items", [])
    if not new_items:
        log.warning("新 items 为空")
        return

    wr = _wr(args)
    output_dir = os.path.join(wr, cfg["dir"])
    os.makedirs(output_dir, exist_ok=True)

    # 获取已有文件名列表
    existing_names = set()
    for f in os.listdir(output_dir):
        if f.endswith(".md"):
            existing_names.add(f)

    # 只添加不存在的 item
    to_add = []
    skipped = []
    for item in new_items:
        name = item.get("name", "")
        if cfg["filename_style"] == "name_only":
            fname = f"{name}.md"
        else:
            bn = _book_name(new_data.get("book_id", args.book_id))
            ch = new_data.get("chapter_num", args.chapter or "0")
            fname = f"{name}_{bn}_{ch}.md"

        if fname in existing_names:
            skipped.append(name)
        else:
            to_add.append(item)

    if not to_add:
        log.success(f"[{args.phase}] 全部 {len(new_items)} 个 items 已存在，无需更新")
        return

    # 构建 skeleton 并只塞入新 items
    skeleton = {
        "template": cfg["template"],
        "output_dir": output_dir,
        "book_id": new_data.get("book_id", args.book_id),
        "book_name": new_data.get("book_name", _book_name(args.book_id)),
        "chapter_num": new_data.get("chapter_num", args.chapter or "0"),
        "items": to_add,
    }

    os.makedirs(os.path.join(wr, ".dag"), exist_ok=True)
    tmp_json = os.path.join(wr, ".dag", f"tmp_add_{args.phase}.json")
    with open(tmp_json, "w") as f:
        json.dump(skeleton, f, ensure_ascii=False, indent=2)

    r = run_script("template_assembler.py", [tmp_json], timeout=120)
    if r.stdout:
        print(r.stdout, end="")
    if not r.success:
        raise PipelineError("phase_add", f"template_assembler 失败 ({r.returncode}): {r.stderr[:200]}")

    log.success(f"[{args.phase}] 增量添加 {len(to_add)} 个（跳过 {len(skipped)} 个已有）")
    if skipped:
        log.info(f"已存在: {', '.join(skipped[:5])}{'...' if len(skipped)>5 else ''}")




# ===== 原始单阶段操作 =====
def pipeline_init(args: PipelineArgs) -> None:
    """初始化 pipeline 状态文件"""
    wr = _wr(args)
    ch = args.chapter or "0"
    sp = _state_path(wr, args.book_id, ch)

    # ── v35.3: 自动检测工作区布局（嵌套/平铺）并保存到 .dag/config.yaml ──
    layout_config = detect_layout(wr)
    save_workspace_config(wr, layout_config)
    log.info(f"📂 工作区布局: {layout_config['layout']} (kb_root={layout_config['kb_root']})")

    # ── v43.1: 使用 WorkspacePaths 统一创建所有输出目录 ──
    wp = WorkspacePaths(wr)
    wp.ensure_all()
    log.info("📁 输出目录已就绪")

    # ── Phase 0: 检查 .dag/ 目录的 YAML ──
    schema_errors = 0
    yaml_dirs_to_check = []
    data_dir = WorkspacePaths(wr).data_dir(ch)
    if os.path.isdir(data_dir):
        yaml_dirs_to_check.append((".dag/", data_dir))

    for dir_label, data_dir in yaml_dirs_to_check:
        log.info(f"\\n🔍 Phase 0: 预检 YAML 数据 schema ({dir_label})...")
        yaml_files = sorted(f for f in os.listdir(data_dir) if f.endswith((".yaml", ".yml")))
        if not yaml_files:
            log.info("  (目录为空，跳过)")
            continue
        for yf in yaml_files:
            r = run_script("schema.py", [os.path.join(data_dir, yf)], timeout=30)
            if not r.success:
                schema_errors += 1
                log.error(f"{yf}: schema 校验失败")
                if r.stderr:
                    for line in r.stderr.strip().split("\\n")[:3]:
                        log.info(f"  {line}")
            else:
                log.success(f"  {yf}")
    if schema_errors > 0:
        log.info(f"\n❌ Phase 0 阻断: {schema_errors} 个 YAML 文件 schema 校验失败。")
        log.info("请修复后重新运行 pipeline init。")
        log.info("常见问题: bd 是字符串而不是字典（应为 YAML dict）")
        raise PipelineError("init", f"{schema_errors} 个 YAML 文件 schema 校验失败")

    # ── Phase 0.5: YAML 内容预校验（秒级快速检查）──
    if yaml_dirs_to_check:
        log.info("\n🔍 Phase 0.5: YAML 内容预校验 (yaml_pre_validate)...")
        try:
            from yaml_pre_validate import validate_chapter_dir
            pre_results = validate_chapter_dir(data_dir, wr=wr, ch=ch)
            pre_errors = sum(r.get("errors_count", 0) for r in pre_results)
            pre_warns = sum(r.get("warnings", 0) for r in pre_results)
            if pre_errors > 0:
                log.warning(f"  发现 {pre_errors} 个内容错误, {pre_warns} 个警告")
                for r in pre_results:
                    if r.get("errors_count", 0) > 0:
                        fname = os.path.basename(r["path"])
                        for e in r.get("errors", []):
                            if e.get("severity") == "error":
                                log.warning(f"    {fname}: {e.get('field','')} — {e['message'][:100]}")
                log.info("  ⚠️  内容错误不阻断构建，但建议修复后重新运行")
            else:
                log.success(f"  内容预校验通过 ({pre_warns} 警告)")
        except Exception as e:
            log.warning(f"  yaml_pre_validate 执行异常: {e}（不阻断流程）")

    if yaml_dirs_to_check:
        log.success("Phase 0 通过: 所有 YAML 文件格式正确\\n")

    state = {
        "book_id": args.book_id,
        "book_name": args.book_name or _book_name(args.book_id),
        "chapter": ch,
        "wiki_root": wr,
        "current_index": -1,
        "phases": {},
    }
    for i, ph in enumerate(DAG_ORDER):
        if ph in ("l2_indices", "l3_indices", "l4_indices"):
            c = _phase_count(wr, ph)
            status = "done" if c > 0 else "pending"
        else:
            c = 0
            status = "pending"
        state["phases"][ph] = {"index": i, "status": status, "files": c, "deps": DAG_DEPENDS[ph]}
    _save_state(sp, state)
    _print_pipeline_status(state)




def pipeline_status(args: PipelineArgs) -> None:
    """显示 pipeline 当前状态"""
    wr = _wr(args)
    ch = args.chapter or "0"
    sp = _state_path(wr, args.book_id, ch)
    if not os.path.exists(sp):
        log.error("未初始化")
        return
    s = _load_state(sp)
    for ph in DAG_ORDER:
        if ph in s.get("phases", {}):
            c = _phase_count(wr, ph)
            s["phases"][ph]["files"] = c
            # 不自动更新状态——多章共用目录时文件数无法区分章节归属
            # 用户必须通过 pipeline done 显式标记完成
    _save_state(sp, s)
    _print_pipeline_status(s)
    fix_broken_links(args)  # 顺便做断链检查


