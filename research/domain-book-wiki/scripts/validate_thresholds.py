#!/usr/bin/env python3
"""validate_thresholds.py — 内容深度阈值有效性回测

对已生成的知识库做一次"阈值 vs 实际"的回测分析：
- 统计每类节点的实际字数分布 (min/p25/median/p75/max)
- 对比 defaults.yaml 中的 min_body_chars 阈值
- 报告偏差（阈值过低 / Agent 执行不到位）
- 输出 JSON 格式反馈报告

用法：
    python3 validate_thresholds.py <wiki_root> [--output report.json]

v42.0: 新增
"""

import argparse
import json
import os
import re
import statistics
import sys
from typing import Any

import yaml
from dag_constants import PipelineError

# 节点类型 → 目录名映射 (与 BUILDER_CONFIG 一致)
_NODE_TYPE_DIRS: dict[str, str] = {
    "concept": "30_核心概念",
    "knowledge-element": "30_知识要素",
    "knowledge": "40_知识点",
    "skill": "50_技能点",
    "scenario": "60_应用场景",
    "entity": "70_实体",
    "exercise": "90_习题",
    "solution": "90_习题/解答",
}


def _strip_frontmatter(content: str) -> str:
    """移除 YAML frontmatter（--- ... ---）"""
    m = re.match(r"^---\s*\n.*?\n---\s*\n", content, re.DOTALL)
    return content[m.end():] if m else content


def _strip_wu_sections(content: str) -> str:
    """移除 {{wu}} ... {{/wu}} 区块"""
    return re.sub(r"\{\{wu\}\}.*?\{\{/wu\}\}", "", content, flags=re.DOTALL)


def _count_body_chars(content: str) -> int:
    """计算正文字符数（排除 frontmatter 和 wu 区块）"""
    body = _strip_frontmatter(content)
    body = _strip_wu_sections(body)
    # 移除空行和纯空白行
    lines = [line for line in body.split("\n") if line.strip()]
    return sum(len(line.strip()) for line in lines)


def _count_nonempty_sections(content: str) -> int:
    """计算非空的 ### 子节数量"""
    body = _strip_frontmatter(content)
    sections = re.split(r"^### ", body, flags=re.MULTILINE)
    # 第一个元素是 ### 之前的内容（通常是 ## 标题等），跳过
    count = 0
    for sec in sections[1:]:
        # 检查子节是否有非空内容
        lines = [line for line in sec.split("\n") if line.strip() and not line.startswith("#")]
        if lines:
            count += 1
    return count


def _load_thresholds(skill_dir: str) -> dict[str, Any]:
    """从 defaults.yaml 加载阈值配置"""
    config_path = os.path.join(skill_dir, "configs", "defaults.yaml")
    if not os.path.exists(config_path):
        print(f"❌ 找不到配置文件: {config_path}", file=sys.stderr)
        raise PipelineError(f"找不到配置文件: {config_path}")
    with open(config_path, encoding="utf-8") as f:
        config = yaml.safe_load(f)
    return dict(config.get("content_depth_thresholds", {}))


def _compute_percentile(data: list[int], p: float) -> int:
    """计算百分位数"""
    if not data:
        return 0
    sorted_data = sorted(data)
    k = (len(sorted_data) - 1) * p
    f = int(k)
    c = f + 1 if f + 1 < len(sorted_data) else f
    d = k - f
    return int(sorted_data[f] + d * (sorted_data[c] - sorted_data[f]))


def scan_node_type(
    wiki_root: str, node_type: str, dir_name: str, thresholds: dict[str, Any]
) -> dict[str, Any]:
    """扫描某一类节点的所有 .md 文件，返回统计结果"""
    node_dir = os.path.join(wiki_root, dir_name)
    if not os.path.isdir(node_dir):
        return {"node_type": node_type, "status": "skipped", "reason": "目录不存在"}

    files: list[dict[str, Any]] = []
    body_chars_list: list[int] = []
    sections_list: list[int] = []

    for fname in sorted(os.listdir(node_dir)):
        if not fname.endswith(".md"):
            continue
        fpath = os.path.join(node_dir, fname)
        try:
            with open(fpath, encoding="utf-8") as f:
                content = f.read()
        except (OSError, UnicodeDecodeError):
            continue

        bc = _count_body_chars(content)
        ns = _count_nonempty_sections(content)
        body_chars_list.append(bc)
        sections_list.append(ns)
        files.append({"file": fname, "body_chars": bc, "nonempty_sections": ns})

    if not files:
        return {"node_type": node_type, "status": "skipped", "reason": "无 .md 文件"}

    # 统计
    min_chars = min(body_chars_list)
    max_chars = max(body_chars_list)
    median_chars = int(statistics.median(body_chars_list))
    p25_chars = _compute_percentile(body_chars_list, 0.25)
    p75_chars = _compute_percentile(body_chars_list, 0.75)
    mean_chars = int(statistics.mean(body_chars_list))

    # 阈值对比
    threshold = thresholds.get(node_type, {})
    min_body_chars_threshold = threshold.get("min_body_chars", 0)
    min_nonempty_secs_threshold = threshold.get("min_nonempty_secs", 0)

    below_threshold = sum(1 for bc in body_chars_list if bc < min_body_chars_threshold)
    below_pct = round(below_threshold / len(files) * 100, 1) if files else 0

    # 阈值有效性判断
    if min_body_chars_threshold > 0 and p75_chars < min_body_chars_threshold:
        verdict = "⚠️ 阈值可能过高（P75 低于阈值）"
    elif min_body_chars_threshold > 0 and below_pct > 50:
        verdict = "⚠️ 超半数低于阈值（Agent 执行不到位或阈值过高）"
    elif min_body_chars_threshold > 0 and below_pct < 10 and median_chars > min_body_chars_threshold * 2:
        verdict = "💡 阈值可能过低（中位数远超阈值，考虑提升）"
    else:
        verdict = "✅ 阈值合理"

    return {
        "node_type": node_type,
        "status": "ok",
        "file_count": len(files),
        "body_chars": {
            "min": min_chars,
            "p25": p25_chars,
            "median": median_chars,
            "mean": mean_chars,
            "p75": p75_chars,
            "max": max_chars,
        },
        "nonempty_sections": {
            "min": min(sections_list),
            "median": int(statistics.median(sections_list)),
            "max": max(sections_list),
        },
        "threshold": {
            "min_body_chars": min_body_chars_threshold,
            "min_nonempty_secs": min_nonempty_secs_threshold,
        },
        "below_threshold_count": below_threshold,
        "below_threshold_pct": below_pct,
        "verdict": verdict,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="内容深度阈值有效性回测")
    parser.add_argument("wiki_root", help="wiki 根目录路径")
    parser.add_argument("--output", "-o", help="输出 JSON 报告路径")
    args = parser.parse_args()

    wiki_root = os.path.abspath(args.wiki_root)
    if not os.path.isdir(wiki_root):
        print(f"❌ 目录不存在: {wiki_root}", file=sys.stderr)
        raise PipelineError(f"目录不存在: {wiki_root}")

    # 自动定位 skill_dir（脚本所在目录的上级）
    skill_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    thresholds = _load_thresholds(skill_dir)

    results: list[dict[str, Any]] = []
    for node_type, dir_name in _NODE_TYPE_DIRS.items():
        result = scan_node_type(wiki_root, node_type, dir_name, thresholds)
        results.append(result)

    # 汇总
    report: dict[str, Any] = {
        "wiki_root": wiki_root,
        "thresholds_source": os.path.join(skill_dir, "configs", "defaults.yaml"),
        "node_types": results,
    }

    # 输出
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"📊 报告已写入: {args.output}")

    # 打印摘要
    print(f"\n{'='*70}")
    print("📊 内容深度阈值回测报告")
    print(f"   wiki_root: {wiki_root}")
    print(f"{'='*70}\n")

    for r in results:
        nt = r["node_type"]
        if r["status"] == "skipped":
            print(f"  {nt:25s} ⏭️  跳过: {r.get('reason', '')}")
            continue

        bc = r["body_chars"]
        th = r["threshold"]
        print(f"  {nt:25s} ({r['file_count']:3d} 文件)")
        print(f"    字数分布: min={bc['min']:5d}  p25={bc['p25']:5d}  "
              f"med={bc['median']:5d}  p75={bc['p75']:5d}  max={bc['max']:5d}")
        print(f"    阈值:     min_body_chars={th['min_body_chars']}")
        print(f"    低于阈值: {r['below_threshold_count']}/{r['file_count']} "
              f"({r['below_threshold_pct']}%)")
        print(f"    判定:     {r['verdict']}")
        print()


if __name__ == "__main__":
    try:
        main()
    except PipelineError as e:
        print(f"❌ {e}", file=sys.stderr)
        raise
