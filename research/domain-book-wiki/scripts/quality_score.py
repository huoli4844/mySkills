#!/usr/bin/env python3.12
"""quality_score.py — 生成每章可比较的质量评分 JSON。

从 content check 结果 + 节点统计 + YAML 预校验结果中提取指标，
输出 .dag/第N章/quality_score.json 和 .dag/quality_summary.json（全书汇总）。

用法:
  python3.12 quality_score.py --book-dir /path/to/book -c 1
  python3.12 quality_score.py --book-dir /path/to/book --all      # 全书
  python3.12 quality_score.py --book-dir /path/to/book --compare  # 对比各章
"""

import argparse
import glob
import json
import os
import re
import sys
import time
from datetime import datetime
from typing import Any

from log_utils import get_logger

log = get_logger(__name__)

# ── Module-level cache for book-level index coverage (computed once per book) ──
_coverage_cache: dict[str, dict[str, Any]] = {}


def _compute_index_coverage_penalty(book_dir: str) -> dict[str, Any]:
    """计算 L2/L3/L4 索引覆盖率并返回扣分信息。

    从 book_overview.md 中统计引用的节点数，与 L1 总节点数对比计算覆盖率。
    覆盖率 < 80% 时扣分（最多扣 5 分）。

    Returns:
        dict with keys: l2_penalty, l2_coverage_pct, l2_indexed_nodes,
                        l2_total_nodes, l2_overview_file,
                        l3_penalty, l4_penalty (if applicable)
    """
    if book_dir in _coverage_cache:
        return _coverage_cache[book_dir]

    from dag_state import WorkspacePaths
    wp = WorkspacePaths(book_dir)

    result: dict[str, Any] = {
        "l2_penalty": 0.0,
        "l2_coverage_pct": 100.0,
        "l2_indexed_nodes": 0,
        "l2_total_nodes": 0,
        "l2_overview_file": "",
        "l3_penalty": 0.0,
        "l4_penalty": 0.0,
    }

    # ── L1 总节点数 ──
    node_dirs: list[tuple[str, str]] = [
        ("concepts", "30_核心概念"),
        ("kes", "40_知识要素"),
        ("kps", "50_知识点"),
        ("sps", "60_技能点"),
        ("scenes", "70_应用场景"),
        ("entities", "80_实体"),
    ]
    total_l1_nodes = 0
    for key, dir_name in node_dirs:
        d = os.path.join(book_dir, dir_name)
        if os.path.isdir(d):
            total_l1_nodes += len([f for f in os.listdir(d) if f.endswith(".md")])

    if total_l1_nodes == 0:
        result["l2_total_nodes"] = 0
        _coverage_cache[book_dir] = result
        return result

    result["l2_total_nodes"] = total_l1_nodes

    # ── L2 索引覆盖率：读取 book_overview.md ──
    l2_dir = wp.l2_dir
    book_name = os.path.basename(book_dir)
    overview_pattern = os.path.join(l2_dir, f"book_overview_{book_name}_*.md")
    overview_files = sorted(glob.glob(overview_pattern))

    if overview_files:
        overview_path = overview_files[0]
        result["l2_overview_file"] = overview_path
        try:
            with open(overview_path, encoding="utf-8") as fh:
                content = fh.read()
            indexed_nodes = _extract_nodes_from_overview(content)
            result["l2_indexed_nodes"] = len(indexed_nodes)
            if total_l1_nodes > 0:
                coverage = round(len(indexed_nodes) / total_l1_nodes * 100, 1)
                result["l2_coverage_pct"] = coverage
                if coverage < 80:
                    # 线性扣分：0% 覆盖 → 扣 5 分，80% → 扣 0 分
                    penalty = round(5 * (1 - coverage / 80), 1)
                    result["l2_penalty"] = max(0, min(5, penalty))
        except Exception as e:
            log.warning(f"L2 索引覆盖率检查失败: {e}")

    # ── L3 索引覆盖率：读取 domain_overview.md（如果存在）──
    l3_dir = wp.l3_dir
    if os.path.isdir(l3_dir):
        domain_pattern = os.path.join(l3_dir, "domain_overview_*.md")
        domain_files = sorted(glob.glob(domain_pattern))
        if domain_files:
            try:
                with open(domain_files[0], encoding="utf-8") as fh:
                    l3_content = fh.read()
                l3_indexed = _extract_nodes_from_overview(l3_content)
                # L3 覆盖率：检查 domain_overview 中引用了多少本 domain 下的书
                # 这里对比 L3 索引中引用的节点数与 domain 下所有书的 L1 节点之和
                domain_dir = wp.domain_dir
                domain_total_nodes = 0
                for entry in os.listdir(domain_dir):
                    book_path = os.path.join(domain_dir, entry)
                    if not os.path.isdir(book_path):
                        continue
                    for key, dir_name in node_dirs:
                        d = os.path.join(book_path, dir_name)
                        if os.path.isdir(d):
                            domain_total_nodes += len([f for f in os.listdir(d) if f.endswith(".md")])
                if domain_total_nodes > 0:
                    l3_coverage = round(len(l3_indexed) / domain_total_nodes * 100, 1)
                    if l3_coverage < 80:
                        l3_penalty = round(5 * (1 - l3_coverage / 80), 1)
                        result["l3_penalty"] = max(0, min(5, l3_penalty))
            except Exception as e:
                log.warning(f"L3 索引覆盖率检查失败: {e}")

    # ── L4 索引覆盖率：读取 kb_overview.md（如果存在）──
    l4_dir = wp.l4_dir
    if os.path.isdir(l4_dir):
        kb_pattern = os.path.join(l4_dir, "kb_overview_*.md")
        kb_files = sorted(glob.glob(kb_pattern))
        if kb_files:
            try:
                with open(kb_files[0], encoding="utf-8") as fh:
                    l4_content = fh.read()
                l4_indexed = _extract_nodes_from_overview(l4_content)
                # L4 覆盖率：统计 KB 根下所有 domain 的所有 book 的 L1 节点
                kb_total_nodes = 0
                kb_root = wp.kb_root
                for domain_entry in os.listdir(kb_root):
                    domain_path = os.path.join(kb_root, domain_entry)
                    if not os.path.isdir(domain_path):
                        continue
                    for book_entry in os.listdir(domain_path):
                        book_path = os.path.join(domain_path, book_entry)
                        if not os.path.isdir(book_path):
                            continue
                        for key, dir_name in node_dirs:
                            d = os.path.join(book_path, dir_name)
                            if os.path.isdir(d):
                                kb_total_nodes += len([f for f in os.listdir(d) if f.endswith(".md")])
                if kb_total_nodes > 0:
                    l4_coverage = round(len(l4_indexed) / kb_total_nodes * 100, 1)
                    if l4_coverage < 80:
                        l4_penalty = round(5 * (1 - l4_coverage / 80), 1)
                        result["l4_penalty"] = max(0, min(5, l4_penalty))
            except Exception as e:
                log.warning(f"L4 索引覆盖率检查失败: {e}")

    _coverage_cache[book_dir] = result
    return result


def _extract_nodes_from_overview(content: str) -> set[str]:
    """从 overview 文件内容中提取引用的节点名集合。

    从三个来源提取：
    1. Frontmatter 中的 node_stats 字段
    2. Mermaid 图中的节点定义（`NodeName["..."]` 或 `NodeName("...")` 形式）
    3. Wikilink 列表中的引用（`[[path|name]]` 或 `[[name]]` 形式）
    """
    nodes: set[str] = set()

    # ── 1. Frontmatter node_stats ──
    fm_match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if fm_match:
        fm_text = fm_match.group(1)
        # 尝试解析 node_stats 中的数值
        for line in fm_text.split("\n"):
            if "node_stats" in line.lower():
                # node_stats 可能是 YAML 嵌套结构，这里简单提取数字引用
                nums = re.findall(r"\d+", line)
                # 不作为节点名，跳过

    # ── 2. Mermaid 图中的节点 ──
    # 匹配 Mermaid 代码块
    mermaid_blocks = re.findall(r"```mermaid\n(.*?)```", content, re.DOTALL)
    for block in mermaid_blocks:
        # 匹配节点定义: NodeName["Label"] 或 NodeName("Label")
        node_defs = re.findall(r'(\w[^\[\](){}\s"]*)\s*[\[\(]"([^"]+)"[\]\)]', block)
        for node_id, node_label in node_defs:
            # 过滤掉明显的非节点标识符（如 Start, Basic, Apply 等学习轨道标签）
            if node_id in ("Start", "Basic", "Apply", "Deep", "Skill", "Create", "graph", "TB", "LR", "RL", "BT"):
                continue
            if node_label and len(node_label) >= 2:
                nodes.add(node_label)

    # ── 3. Wikilink 引用 ──
    # 匹配 [[path|name]] 或 [[name]]，提取显示名称
    wikilinks = re.findall(r"\[\[(?:[^\]|]*\/)?([^\]|#]+)(?:\|[^\]]+)?\]\]", content)
    for link in wikilinks:
        name = link.strip()
        if name and len(name) >= 2:
            nodes.add(name)

    return nodes


def compute_chapter_score(book_dir: str, chapter: str) -> dict[str, Any]:
    """计算单章质量分"""
    from dag_state import WorkspacePaths
    wp = WorkspacePaths(book_dir)
    ch_label = f"第{chapter}章"

    score = {
        "chapter": chapter,
        "timestamp": datetime.now().isoformat(),
        "metrics": {},
        "errors": 0,
        "warnings": 0,
        "score": 0.0,
    }

    # ── 1. YAML 预校验指标 ──
    try:
        from yaml_pre_validate import validate_chapter_dir
        data_dir = wp.data_dir(chapter)
        if os.path.isdir(data_dir):
            pre_results = validate_chapter_dir(data_dir)
            score["metrics"]["yaml_items"] = sum(r.get("items_count", 0) for r in pre_results)
            score["metrics"]["yaml_errors"] = sum(r.get("errors_count", 0) for r in pre_results)
            score["metrics"]["yaml_warnings"] = sum(r.get("warnings", 0) for r in pre_results)
            score["errors"] += score["metrics"]["yaml_errors"]
            score["warnings"] += score["metrics"]["yaml_warnings"]
    except Exception as e:
        log.warning(f"YAML预校验失败: {e}")
        pass

    # ── 2. 节点数量统计 ──
    node_dirs: list[tuple[str, str]] = [
        ("concepts", "30_核心概念"),
        ("kes", "40_知识要素"),
        ("kps", "50_知识点"),
        ("sps", "60_技能点"),
        ("scenes", "70_应用场景"),
        ("entities", "80_实体"),
    ]
    node_counts = {}
    total_size_bytes = 0
    for key, dir_name in node_dirs:
        d = os.path.join(book_dir, dir_name)
        if os.path.isdir(d):
            md_files = [f for f in os.listdir(d) if f.endswith(".md")]
            node_counts[key] = len(md_files)
            for f in md_files:
                try:
                    total_size_bytes += os.path.getsize(os.path.join(d, f))
                except OSError:
                    pass
        else:
            node_counts[key] = 0
    score["metrics"]["node_counts"] = node_counts
    score["metrics"]["total_nodes"] = sum(node_counts.values())
    score["metrics"]["total_size_kb"] = round(total_size_bytes / 1024, 1)

    # ── 3. wikilink 连通性 ──
    try:
        import re
        wikilink_count = 0
        broken_count = 0
        # Build index of all md files in the book (including L2/L4 index dirs)
        # v50.0: 扩展扫描范围，包含 10_总揽 + 90_习题 等其他 MD 目录
        all_scan_dirs = [
            "30_核心概念", "40_知识要素", "50_知识点",
            "60_技能点", "70_应用场景", "80_实体",
            "10_总揽", "90_习题",
        ]
        all_files: set[str] = set()
        for dir_name in all_scan_dirs:
            d = os.path.join(book_dir, dir_name)
            if not os.path.isdir(d):
                continue
            for f in os.listdir(d):
                if f.endswith(".md"):
                    all_files.add(f.replace(".md", ""))
            # 递归: 90_习题/解答/ 子目录
            for root, _, files in os.walk(d):
                if root == d:
                    continue  # skip top-level, already scanned
                for f in files:
                    if f.endswith(".md"):
                        all_files.add(f.replace(".md", ""))

        for key, dir_name in node_dirs:
            d = os.path.join(book_dir, dir_name)
            if not os.path.isdir(d):
                continue
            for f in os.listdir(d):
                if not f.endswith(".md"):
                    continue
                with open(os.path.join(d, f), encoding="utf-8") as fh:
                    content = fh.read()
                links = re.findall(r'\[\[([^\]|#]+)', content)
                for link in links:
                    wikilink_count += 1
                    target = link.strip().split("/")[-1]  # Handle [[30_核心概念/name]]
                    if not target:
                        continue
                    if target not in all_files:
                        broken_count += 1
        score["metrics"]["wikilink_total"] = wikilink_count
        score["metrics"]["wikilink_broken"] = broken_count
        score["errors"] += broken_count
    except Exception as e:
        log.warning(f"Wikilink分析失败: {e}")
        pass

    # ── 3.5 L2/L3/L4 索引覆盖率检查（book-level，通过 cache 仅计算一次）──
    try:
        cov = _compute_index_coverage_penalty(book_dir)
        score["metrics"]["l2_coverage_pct"] = cov["l2_coverage_pct"]
        score["metrics"]["l2_indexed_nodes"] = cov["l2_indexed_nodes"]
        score["metrics"]["l2_total_nodes"] = cov["l2_total_nodes"]
        score["metrics"]["l2_overview_file"] = cov["l2_overview_file"]
        score["metrics"]["l2_penalty"] = cov["l2_penalty"]
        score["metrics"]["l3_penalty"] = cov["l3_penalty"]
        score["metrics"]["l4_penalty"] = cov["l4_penalty"]
        coverage_penalty = cov["l2_penalty"] + cov["l3_penalty"] + cov["l4_penalty"]
    except Exception as e:
        log.warning(f"索引覆盖率检查失败: {e}")
        coverage_penalty = 0.0

    # ── 4. 计算总分（0-100）──
    # 权重: YAML质量 40%, 节点完整性 40%, wikilink连通性 20%
    # v50.0: 降低 wikilink 权重(30→20) + 修正惩罚乘数(10→3)避免负分
    yaml_score = 40.0
    if score["metrics"].get("yaml_items", 0) > 0:
        yaml_err_rate = score["metrics"].get("yaml_errors", 0) / max(score["metrics"].get("yaml_items", 1), 1)
        yaml_score = max(0, 40 * (1 - yaml_err_rate * 5))

    node_score = min(40, score["metrics"].get("total_nodes", 0) * 2)

    link_score = 20.0
    if score["metrics"].get("wikilink_total", 0) > 0:
        link_rate = score["metrics"].get("wikilink_broken", 0) / max(score["metrics"].get("wikilink_total", 1), 1)
        link_score = max(0, 20 * (1 - link_rate * 3))

    score["score"] = round(max(0, yaml_score + node_score + link_score - coverage_penalty), 1)

    return score


def compute_all_chapters(book_dir: str) -> list[dict]:
    """计算全书所有章的质量分"""
    dag_dir = os.path.join(book_dir, ".dag")
    if not os.path.isdir(dag_dir):
        return []
    chapters = sorted(
        d.replace("第", "").replace("章", "")
        for d in os.listdir(dag_dir)
        if d.startswith("第") and d.endswith("章") and os.path.isdir(os.path.join(dag_dir, d))
    )
    return [compute_chapter_score(book_dir, ch) for ch in chapters]


def save_score(book_dir: str, chapter: str, score: dict) -> str:
    """保存单章质量分到 .dag/第N章/quality_score.json"""
    dag_dir = os.path.join(book_dir, ".dag", f"第{chapter}章")
    os.makedirs(dag_dir, exist_ok=True)
    path = os.path.join(dag_dir, "quality_score.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(score, f, ensure_ascii=False, indent=2)
    return path


def save_summary(book_dir: str, scores: list[dict]) -> str:
    """保存全书质量汇总"""
    path = os.path.join(book_dir, ".dag", "quality_summary.json")
    # 提取第一份 score 中的覆盖率信息（book-level，所有章共享）
    cov_info: dict[str, Any] = {}
    if scores:
        cov_info = {
            "l2_coverage_pct": scores[0]["metrics"].get("l2_coverage_pct", 100.0),
            "l2_indexed_nodes": scores[0]["metrics"].get("l2_indexed_nodes", 0),
            "l2_total_nodes": scores[0]["metrics"].get("l2_total_nodes", 0),
            "l2_penalty": scores[0]["metrics"].get("l2_penalty", 0.0),
            "l3_penalty": scores[0]["metrics"].get("l3_penalty", 0.0),
            "l4_penalty": scores[0]["metrics"].get("l4_penalty", 0.0),
        }
    summary = {
        "timestamp": datetime.now().isoformat(),
        "chapters": len(scores),
        "average_score": round(sum(s["score"] for s in scores) / max(len(scores), 1), 1),
        "total_errors": sum(s["errors"] for s in scores),
        "total_warnings": sum(s["warnings"] for s in scores),
        "total_nodes": sum(s["metrics"].get("total_nodes", 0) for s in scores),
        "index_coverage": cov_info,
        "per_chapter": {s["chapter"]: s["score"] for s in scores},
        "details": scores,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    return path


def print_compare(scores: list[dict]):
    """打印章节质量对比表"""
    print(f"\n{'章节':<8} {'得分':>6} {'节点':>5} {'错误':>5} {'警告':>5} {'wikilink断链':>12}")
    print("-" * 45)
    for s in scores:
        ch = f"第{s['chapter']}章"
        score = s["score"]
        nodes = s["metrics"].get("total_nodes", 0)
        errs = s["errors"]
        warns = s["warnings"]
        broken = s["metrics"].get("wikilink_broken", 0)
        flag = "🔴" if score < 60 else "🟡" if score < 80 else "🟢"
        print(f"{ch:<8} {flag}{score:>5.1f} {nodes:>5} {errs:>5} {warns:>5} {broken:>12}")
    avg = round(sum(s["score"] for s in scores) / max(len(scores), 1), 1)
    print(f"\n全书均分: {avg}")

    # ── L2/L3/L4 索引覆盖率 ──
    if scores:
        l2_cov = scores[0]["metrics"].get("l2_coverage_pct")
        l2_idx = scores[0]["metrics"].get("l2_indexed_nodes", 0)
        l2_tot = scores[0]["metrics"].get("l2_total_nodes", 0)
        l2_pen = scores[0]["metrics"].get("l2_penalty", 0.0)
        l3_pen = scores[0]["metrics"].get("l3_penalty", 0.0)
        l4_pen = scores[0]["metrics"].get("l4_penalty", 0.0)
        if l2_cov is not None:
            cov_flag = "🔴" if l2_cov < 80 else "🟢"
            print(f"\n📊 L2 索引覆盖率: {cov_flag} {l2_cov}% ({l2_idx}/{l2_tot} nodes)  |  扣分: {l2_pen}")
            if l3_pen > 0:
                print(f"📊 L3 索引覆盖率扣分: {l3_pen}")
            if l4_pen > 0:
                print(f"📊 L4 索引覆盖率扣分: {l4_pen}")


def main():
    parser = argparse.ArgumentParser(description="生成章节质量评分 JSON")
    parser.add_argument("--book-dir", required=True, help="书目录路径")
    parser.add_argument("-c", "--chapter", help="单章编号")
    parser.add_argument("--all", action="store_true", help="计算全书")
    parser.add_argument("--compare", action="store_true", help="对比各章得分")
    args = parser.parse_args()

    if args.compare or args.all:
        scores = compute_all_chapters(args.book_dir)
        if args.all:
            for s in scores:
                path = save_score(args.book_dir, s["chapter"], s)
                print(f"第{s['chapter']}章: {s['score']}分 → {path}")
            summary_path = save_summary(args.book_dir, scores)
            print(f"汇总: {summary_path}")
        if args.compare:
            print_compare(scores)
    elif args.chapter:
        score = compute_chapter_score(args.book_dir, args.chapter)
        path = save_score(args.book_dir, args.chapter, score)
        print(f"第{args.chapter}章: {score['score']}分 → {path}")
        print(json.dumps(score, ensure_ascii=False, indent=2))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
