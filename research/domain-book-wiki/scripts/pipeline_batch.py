"""pipeline_batch.py — 批量章编排器

v46.0: 集成 SHA256 增量缓存，自动跳过未变化章节。
v45.2: 新增。支持一次性处理整本书的所有章节。
  1. 自动发现所有章节源文件
  2. 逐章执行 pipeline auto
  3. 全章完成后生成 L2/L3/L4 索引
  4. 支持断点续传（--from-chapter）
  5. 支持自动重试（--retry N）
  6. v46.0: SHA256 增量缓存 — 自动跳过未修改章节

用法:
  python3 dag_controller.py pipeline batch -w BOOK_DIR --book-id XX [--retry 3] [--from-chapter 2] [--no-cache]
"""

import os
import time

from dag_constants import DAG_ORDER, DIR
from dag_state import _load_state, _state_path
from log_utils import get_logger

log = get_logger(__name__)

SKILL_DIR = os.path.dirname(os.path.abspath(__file__))

# v46.0: 增量缓存开关
_cache_module = None


def _get_cache():
    global _cache_module
    if _cache_module is None:
        try:
            from chapter_cache import (
                check_chapter,
                is_pipeline_complete,
                save_chapter_hash,
                yaml_files_exist,
            )

            _cache_module = {
                "check": check_chapter,
                "complete": is_pipeline_complete,
                "save": save_chapter_hash,
                "yaml_ok": yaml_files_exist,
            }
        except ImportError:
            _cache_module = False
    return _cache_module


def discover_chapters(wr: str) -> list[tuple[str, str]]:
    """从 20_正文/ 自动发现所有章节。

    返回 [(章节号, 源文件路径), ...] 按章节号排序。
    例如: [("1", "20_正文/第1章 电磁兼容概述.md"), ...]
    """
    import re

    src_dir = os.path.join(wr, DIR["SOURCE"])
    if not os.path.isdir(src_dir):
        return []

    chapters = []
    for fname in sorted(os.listdir(src_dir)):
        m = re.match(r"第(\d+)章\s.*\.md$", fname)
        if m:
            chapters.append((m.group(1), os.path.join(src_dir, fname)))
    return chapters


def run_batch_pipeline(
    wr: str,
    book_id: str,
    retry: int = 0,
    from_chapter: str | None = None,
    l1_only: bool = False,
    no_cache: bool = False,
) -> dict:
    """批量执行所有章节的 pipeline。

    Args:
        wr: 书目录路径
        book_id: 书 ID (如 01_xxx)
        retry: 质量闸门失败后的最大重试次数
        from_chapter: 从指定章开始（断点续传）
        l1_only: 只执行 L1 阶段，跳过索引
        no_cache: 禁用增量缓存（强制重建所有章）

    Returns:
        {"success": bool, "chapters": {ch: status, ...}, "total_time": float, "skipped_by_cache": int}
    """
    chapters = discover_chapters(wr)
    if not chapters:
        log.error("未在 20_正文/ 中发现任何章节文件")
        return {"success": False, "chapters": {}, "total_time": 0}

    started = from_chapter is None
    results = {}
    all_success = True
    skipped_by_cache = 0
    t0 = time.time()

    # v46.0: 缓存模块
    cache = _get_cache() if not no_cache else False

    log.info("=" * 70)
    log.info(f"  批量 Pipeline: {book_id} ({len(chapters)} 章)")
    log.info(f"  自动重试: {retry} 次 | 从第{from_chapter or 1}章开始 | {'仅L1' if l1_only else '全量'}")
    log.info(f"  增量缓存: {'启用' if cache else '禁用'}")
    log.info("=" * 70)

    for ch_num, src_path in chapters:
        if not started:
            if ch_num == from_chapter:
                started = True
            else:
                log.info(f"[第{ch_num}章] 跳过（从第{from_chapter}章开始）")
                results[ch_num] = "skipped"
                continue

        log.info(f"\n{'─' * 60}")
        log.info(f"  📖 第{ch_num}章: {os.path.basename(src_path)}")
        log.info(f"{'─' * 60}")

        sp = _state_path(wr, book_id, ch_num)

        # 检查是否已完成
        if os.path.exists(sp):
            s = _load_state(sp)
            all_done = all(
                s.get("phases", {}).get(ph, {}).get("status") == "done"
                for ph in DAG_ORDER
                if ph not in ("l3_indices", "l4_indices")
            )
            if all_done:
                log.success(f"[第{ch_num}章] 已完成，跳过")
                results[ch_num] = "done"
                continue

        # v46.0: SHA256 增量缓存检查
        if cache:
            chk = cache["check"](wr, book_id, ch_num)
            if chk["status"] == "unchanged":
                log.success(f"[第{ch_num}章] 源文件未变化 + YAML 完整 → 跳过")
                skipped_by_cache += 1
                results[ch_num] = "cached"
                continue
            elif chk["status"] == "changed":
                log.info(f"[第{ch_num}章] 源文件已变化 (旧: {chk.get('saved_hash', 'N/A')}, 新: {chk['current_hash']}) → 重新处理")
            elif chk["status"] == "missing_yaml":
                log.info(f"[第{ch_num}章] YAML 数据缺失 → 需要生成")
            elif chk["status"] == "incomplete":
                log.info(f"[第{ch_num}章] pipeline 未完成 → 继续执行")

        # 初始化 + 执行 pipeline auto
        success = _execute_chapter_pipeline(wr, book_id, ch_num, retry, l1_only)
        results[ch_num] = "success" if success else "failed"
        if not success:
            all_success = False
            if retry == 0:
                log.error(f"[第{ch_num}章] 失败（重试已用尽），继续下一章")
            else:
                log.error(f"[第{ch_num}章] 失败，继续下一章")

    elapsed = time.time() - t0

    # 汇总报告
    log.info("\n" + "=" * 70)
    log.info(f"  批量 Pipeline 完成 ({elapsed:.0f}s)")
    log.info("=" * 70)
    for ch_num, status in results.items():
        if status in ("success", "done"):
            icon = "✅"
        elif status == "cached":
            icon = "💾"
        elif status == "skipped":
            icon = "⏭️"
        else:
            icon = "❌"
        log.info(f"  {icon} 第{ch_num}章: {status}")

    if skipped_by_cache > 0:
        log.info(f"\n💾 增量缓存节省: {skipped_by_cache} 章跳过，无需重新处理")

    if all_success:
        log.success("\n🎉 全部章节构建成功！")
    else:
        failed_chs = [ch for ch, s in results.items() if s == "failed"]
        log.warning(f"\n⚠️ {len(failed_chs)} 章失败: {failed_chs}")

    return {
        "success": all_success,
        "chapters": results,
        "total_time": elapsed,
        "skipped_by_cache": skipped_by_cache,
    }


def _execute_chapter_pipeline(
    wr: str, book_id: str, ch_num: str, max_retry: int, l1_only: bool
) -> bool:
    """执行单章的 pipeline init + auto，带自动重试。

    返回 True 表示成功。
    """
    sp = _state_path(wr, book_id, ch_num)

    # Step 0: 确保已初始化
    if not os.path.exists(sp):
        log.info(f"[第{ch_num}章] 初始化 pipeline...")
        from types import SimpleNamespace

        from dag_pipeline_ops import pipeline_init

        init_args = SimpleNamespace(
            wiki_root=wr,
            book_id=book_id,
            chapter=ch_num,
            book_name=None,
        )
        try:
            pipeline_init(init_args)
        except Exception as e:
            log.error(f"[第{ch_num}章] 初始化失败: {e}")
            return False

        if not os.path.exists(sp):
            log.error(f"[第{ch_num}章] 初始化后状态文件未生成")
            return False

    # Step 1: 执行 pipeline auto（带重试）
    for attempt in range(max_retry + 1):
        if attempt > 0:
            log.info(f"[第{ch_num}章] 重试 {attempt}/{max_retry}...")

        from types import SimpleNamespace

        from dag_pipeline_run import pipeline_auto

        auto_args = SimpleNamespace(
            wiki_root=wr,
            book_id=book_id,
            chapter=ch_num,
            from_phase=None,
            l1_only=l1_only,
            dry_run=False,
        )

        try:
            pipeline_auto(auto_args)
        except Exception as e:
            log.error(f"[第{ch_num}章] pipeline auto 异常: {e}")
            if attempt >= max_retry:
                return False
            continue

        # 检查结果
        if not os.path.exists(sp):
            log.error(f"[第{ch_num}章] 状态文件丢失")
            return False

        s = _load_state(sp)

        # 收集失败阶段
        failed_phases = []
        for ph in DAG_ORDER:
            st = s.get("phases", {}).get(ph, {}).get("status", "pending")
            if st == "blocked":
                failed_phases.append(ph)

        if not failed_phases:
            # 检查是否全部 done
            incomplete = [
                ph
                for ph in DAG_ORDER
                if s.get("phases", {}).get(ph, {}).get("status") not in ("done", "pending")
                and (not l1_only or ph in _L1_PHASES)
            ]
            if incomplete:
                log.warning(f"[第{ch_num}章] 部分阶段未完成: {incomplete}")
            log.success(f"[第{ch_num}章] 完成")

            # v46.0: pipeline 成功后保存源文件 hash
            cache = _get_cache()
            if cache:
                try:
                    cache["save"](wr, ch_num)
                except Exception as e:
                    log.debug(f"缓存保存失败: {e}")
                    pass

            return True

        # 有阻塞阶段
        if attempt >= max_retry:
            log.error(f"[第{ch_num}章] 质量闸门失败: {failed_phases}（已用尽 {max_retry} 次重试）")
            return False

        log.warning(f"[第{ch_num}章] 质量闸门阻塞: {failed_phases}")

        # 自动修复尝试
        remaining = _auto_fix_blocked_phases(wr, book_id, ch_num, failed_phases)

        # 重试用尽时 → 生成结构化错误报告供 Agent 驱动修复
        if attempt >= max_retry:
            if remaining:
                report_path = collect_fix_report(wr, book_id, ch_num, remaining)
                log.info(f"[第{ch_num}章] 错误报告已生成: {report_path}")
                log.info(f"[第{ch_num}章] 运行 pipeline fix -w {wr} --book-id {book_id} -c {ch_num} 触发 Agent 修复")

    return False


_L1_PHASES = ["concepts", "ke", "entities", "kp", "sp", "scene", "exercises", "solutions"]


def _auto_fix_blocked_phases(wr: str, book_id: str, ch_num: str, blocked_phases: list[str]) -> list[dict]:
    """对阻塞阶段运行自动修复脚本。

    先尝试机械修复（公式格式、图引用、占位符），
    然后生成结构化错误报告供 Agent 驱动修复。

    Returns:
        修复后的错误报告列表（空 = 全部已修复）
    """
    errors = []

    # Step 1: 运行 content_check_rules 机械修复
    for ph in blocked_phases:
        if ph not in _L1_PHASES:
            continue
        log.info(f"[自动修复] 扫描 {ph} 格式问题...")
        try:
            from content_check_rules import check_file_full

            phase_dir = os.path.join(wr, {
                "concepts": "30_核心概念", "ke": "40_知识要素",
                "kp": "50_知识点", "sp": "60_技能点",
                "scene": "70_应用场景", "entities": "80_实体",
                "exercises": "90_习题", "solutions": "90_习题/解答",
            }.get(ph, ""))
            if not os.path.isdir(phase_dir):
                continue
            for fname in sorted(os.listdir(phase_dir)):
                if not fname.endswith(".md"):
                    continue
                fpath = os.path.join(phase_dir, fname)
                try:
                    result = check_file_full(fpath, ph.rstrip("s"), wr)
                    if result:
                        fails = sum(1 for r in result if r[0] == "FAIL")
                        if fails > 0:
                            errors.append({
                                "phase": ph,
                                "file": fname,
                                "fail_count": fails,
                                "details": [r for r in result if r[0] == "FAIL"][:5],
                            })
                except Exception as e:
                    log.warning(f"  content_check 异常 {fname}: {e}")
        except ImportError:
            log.warning("  content_check_rules 不可用，跳过")

    # Step 2: 运行 post_build_fix 机械修复
    for ph in blocked_phases:
        if ph in _L1_PHASES:
            log.info(f"[自动修复] 运行 post_build_fix on {ph}...")
            try:
                from post_build_fix import run_phase_auto_fix

                run_phase_auto_fix(wr, ph, ch_num)
            except Exception as e:
                log.warning(f"[自动修复] {ph} 修复异常: {e}")

    # Step 3: 提取 pipeline 状态中的阻塞原因
    from dag_state import _load_state, _state_path

    sp = _state_path(wr, book_id, ch_num)
    if os.path.exists(sp):
        s = _load_state(sp)
        for ph in blocked_phases:
            ph_state = s.get("phases", {}).get(ph, {})
            block_reason = ph_state.get("block_reason", "未知")
            log.warning(f"[第{ch_num}章] {ph} 阻塞原因: {block_reason}")
            # 合并到错误报告
            existing = [e for e in errors if e["phase"] == ph]
            if not existing:
                errors.append({
                    "phase": ph,
                    "file": "pipeline",
                    "fail_count": 1,
                    "block_reason": block_reason,
                    "details": [("BLOCKED", block_reason)],
                })

    return errors


def collect_fix_report(wr: str, book_id: str, ch_num: str, errors: list[dict]) -> str:
    """将结构化错误写入 JSON 报告文件，返回路径。

    Agent 可通过 delegate_task 读取此报告，分析后修复 YAML。
    """
    import json

    report_dir = os.path.join(wr, ".dag", f"第{ch_num}章")
    os.makedirs(report_dir, exist_ok=True)
    report_path = os.path.join(report_dir, "fix_report.json")

    report = {
        "book_id": book_id,
        "chapter": ch_num,
        "wiki_root": wr,
        "errors": errors,
        "error_count": len(errors),
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    log.info(f"[自动修复] 错误报告已保存: {report_path}")
    return report_path
