#!/usr/bin/env python3
"""preprocess_toc.py — 从章节 .md 自适应提取容器结构，输出 chapter_toc.json

v36.5: 自适应容器策略
  - 自动探测每章的容器层级（不硬编码 ###）
  - 超大无子标题节段自动按段落密度分割
  - 输出 containers[] 替代原 leaf_nodes（向后兼容保留 leaf_nodes）

用法:
  python3 preprocess_toc.py 20_正文/第2章.md -o .dag/第2章/chapter_toc.json
  python3 preprocess_toc.py 20_正文/第2章.md -o .dag/第2章/chapter_toc.json --max-span 200

输出 (v36.5):
  {
    "chapter": "2",
    "file": "20_正文/第2章 电磁原理.md",
    "total_lines": 968,
    "container_level": 3,              // 本章自适应容器层级
    "container_reason": "### 级12个标题，平均86行/容器",
    "level_stats": {"2": {"count": 4, "avg_lines": 242}, ...},
    "headings_tree": [...],           // 完整标题树
    "containers": [                   // 自适应容器列表（核心输出）
      {"id": "c2_01", "level": 3, "text": "2.1.1 麦克斯韦方程",
       "line": 28, "line_end": 116, "span_lines": 88,
       "has_children": true, "child_count": 3,
       "support_count": 12, "status": "candidate"},
      {"id": "c2_02", "level": 2, "text": "2.2 简单预测",
       "line": 120, "line_end": 280, "span_lines": 160,
       "has_children": false, "auto_split": true,
       "split_into": [
         {"sub_id": "c2_02a", "line": 120, "line_end": 195, "split_reason": "空行分割"},
         {"sub_id": "c2_02b", "line": 196, "line_end": 280, "split_reason": "空行分割"}
       ], "status": "oversized_split"}
    ],
    "leaf_nodes": [...],              // 向后兼容
    "summary": {
      "total_containers": 15,
      "from_headings": 12,
      "from_oversized_split": 3
    }
  }

算法：
  第一层：扫描 # 号 → 建树 → 统计各层级标题数/平均行数
  第二层：自适应选择容器层级（标题数≥3 且 平均行数 30-300 的最深层）
  第三层：超大节段（>max_span 行且无子标题）按空行/加粗/编号自动分割
  工具只定位，AI 判断哪个容器是核心概念。
"""

import argparse
import json
import os
import re
import sys
from collections import OrderedDict

from dag_constants import PipelineError
from log_utils import get_logger

log = get_logger(__name__)



def parse_headings(filepath):
    """扫描 .md 文件，返回所有标题的列表（含行号、层级、行范围）。"""
    with open(filepath, encoding="utf-8") as f:
        lines = f.readlines()

    total_lines = len(lines)

    # ── 跳过 frontmatter（---...---） ──
    body_start = 0
    if lines and lines[0].startswith("---"):
        for i in range(1, min(len(lines), 100)):
            if lines[i].strip() == "---":
                body_start = i + 1
                break

    # ── 提取所有标题行 ──
    headings = []  # list of OrderedDict
    for i in range(body_start, total_lines):
        line = lines[i]
        m = re.match(r"^(#{1,6})\s+(.+?)(?:\s*\{#.*\})?\s*$", line)
        if m:
            level = len(m.group(1))
            text = m.group(2).strip()
            headings.append(
                OrderedDict(
                    [
                        ("level", level),
                        ("text", text),
                        ("line", i + 1),  # 1-indexed
                        ("line_end", None),  # 待计算
                    ]
                )
            )

    if not headings:
        return {"total_lines": total_lines, "headings": [], "concept_candidates": []}

    # ── 用栈计算 line_end ──
    # 栈里存 (index_in_headings, level)
    stack = []
    for idx, h in enumerate(headings):
        # 弹出同级或更高级的标题（更高级=更少的#）
        while stack and stack[-1][1] >= h["level"]:
            prev_idx, _prev_level = stack.pop()
            headings[prev_idx]["line_end"] = h["line"] - 1
        stack.append((idx, h["level"]))

    # 关闭栈中剩余的
    last_line = total_lines
    while stack:
        prev_idx, _ = stack.pop()
        headings[prev_idx]["line_end"] = last_line

    # ── 构建层级树 ──
    def build_tree(headings_list, parent_level=0, start_idx=0):
        """递归构建树结构。每个节点包含 headings 的字段 + children 列表。"""
        result = []
        i = start_idx
        while i < len(headings_list):
            h = headings_list[i]
            if h["level"] <= parent_level:
                break
            node = OrderedDict(h)
            # 从 i+1 开始找子节点（level 大于当前 level 的）
            children, next_i = build_tree(headings_list, h["level"], i + 1)
            node["children"] = children if children else []
            result.append(node)
            i = next_i if next_i > i else i + 1
        return result, i

    tree, _ = build_tree(headings)

    # ── 提取所有叶节点（无子标题的标题），含层级，供 AI 判断哪些是概念 ──
    def collect_leaf_nodes(nodes, result=None):
        if result is None:
            result = []
        for n in nodes:
            if not n.get("children"):
                result.append(
                    {
                        "level": n["level"],
                        "text": n["text"],
                        "line": n["line"],
                        "line_end": n["line_end"],
                    }
                )
            else:
                collect_leaf_nodes(n["children"], result)
        return result

    leaf_nodes = collect_leaf_nodes(tree)

    return {
        "total_lines": total_lines,
        "headings_tree": tree,
        "leaf_nodes": leaf_nodes,
    }


# ============================================================
# v36.5: 自适应容器层级探测
# ============================================================


def _collect_level_stats(nodes, stats=None):
    """递归统计每个层级的标题数、总行数、最大行数。

    Returns: {level: {"count": int, "total_lines": int, "max_lines": int}}
    """
    if stats is None:
        stats = {}
    for n in nodes:
        span = (n["line_end"] - n["line"] + 1) if n["line_end"] else 1
        lv = n["level"]
        if lv not in stats:
            stats[lv] = {"count": 0, "total_lines": 0, "max_lines": 0}
        stats[lv]["count"] += 1
        stats[lv]["total_lines"] += span
        stats[lv]["max_lines"] = max(stats[lv]["max_lines"], span)
        _collect_level_stats(n.get("children", []), stats)
    return stats


def detect_container_level(headings_tree, total_lines, min_count=3, min_avg=30, max_avg=300):
    """自适应探测本章的容器层级。

    策略（从深到浅搜索）：
      1. 标题数 ≥ min_count 且 平均行数在 [min_avg, max_avg] 区间 → 选为容器层
      2. 兜底：取标题数最多的层级

    Returns: (container_level: int, reason: str, level_stats: dict)
    """
    stats = _collect_level_stats(headings_tree)
    if not stats:
        return 3, "无标题数据，默认 ###", stats

    # 计算平均值
    for lv in stats:
        stats[lv]["avg_lines"] = round(stats[lv]["total_lines"] / stats[lv]["count"], 1)

    # 从深到浅找符合条件的层级
    container_level = None
    for lv in sorted(stats.keys(), reverse=True):
        s = stats[lv]
        if s["count"] >= min_count and min_avg <= s["avg_lines"] <= max_avg:
            container_level = lv
            break

    # 兜底
    if container_level is None:
        container_level = max(stats, key=lambda lv: stats[lv]["count"])

    s = stats[container_level]
    hashes = "#" * container_level
    reason = f"{hashes} 级{s['count']}个标题，平均{s['avg_lines']}行/容器"

    return container_level, reason, stats


# ============================================================
# v36.5: 超大节段自动分割
# ============================================================


def _find_split_points(lines, start, end, max_chunk=150):
    """在超大无子标题节段中寻找分割点。

    分割点优先级：
      1. 连续空行（≥2 个空行）
      2. 加粗标题行（**xxx** 开头）
      3. 数字编号行（1. 2. 或 （1）（2））
      4. 定义标记词行（含"是指"/"称为"/"即"/"定义为"）

    Returns: [(sub_start, sub_end, reason), ...]
    """
    chunks = []
    chunk_start = start

    for i in range(start + 1, end):
        line = lines[i].strip()
        span = i - chunk_start

        if span < max_chunk:
            continue

        # 检测分割点
        split_reason = None

        # 优先级 1：连续空行
        if not line and i > 0 and not lines[i - 1].strip():
            split_reason = "空行分割"
        # 优先级 2：加粗标题行
        elif re.match(r"^\*\*[^*]+\*\*\s*$", line):
            split_reason = "加粗标题分割"
        # 优先级 3：数字编号行
        elif re.match(r"^(\d+[.、：:]|（\d+）)", line):
            split_reason = "编号段落分割"
        # 优先级 4：定义标记词
        elif any(kw in line for kw in ["是指", "称为", "即", "定义为", "所谓"]):
            split_reason = "定义标记词分割"
        # 超过 1.5 倍阈值强制切
        elif span >= int(max_chunk * 1.5):
            # 向前找最近的空行
            for j in range(i - 1, chunk_start, -1):
                if not lines[j].strip():
                    chunk_start = j + 1
                    break
            else:
                split_reason = "超长强制分割"

        if split_reason and (i - chunk_start) >= 20:  # 最小片段 20 行
            chunks.append((chunk_start, i - 1, split_reason))
            chunk_start = i

    # 收尾
    if chunk_start < end:
        chunks.append((chunk_start, end, "尾部" if chunks else "未分割"))

    return chunks


def _count_support(lines, start, end):
    """统计容器内公式($$)、图(图X-X / ![]() )、表(表X-X / |---|)数量。"""
    count = 0
    for i in range(start, min(end + 1, len(lines))):
        line = lines[i]
        if "$$" in line:
            count += 1
        if re.search(r"图\d+[-–]\d+|!\[", line):
            count += 1
        if re.search(r"表\d+[-–]\d+|^\|[-\s|]+\|$", line):
            count += 1
    return count


def build_containers(headings_tree, lines, container_level, max_span=200):
    """构建自适应容器列表。

    对每个标题节点：
      - 如果 level == container_level → 作为一个容器
      - 如果 level < container_level 且无子标题且 span > max_span → 自动分割
      - 如果 level < container_level 且有子标题 → 跳过（子标题会处理）

    Returns: (containers: list, summary: dict)
    """
    containers = []
    counter = [0]

    def _make_id():
        counter[0] += 1
        return f"c{counter[0]:03d}"

    def _process(nodes):
        for n in nodes:
            span = n["line_end"] - n["line"] + 1
            children = n.get("children", [])
            has_children = len(children) > 0

            if n["level"] == container_level:
                # 容器层节点
                cid = _make_id()
                support = _count_support(lines, n["line"] - 1, n["line_end"] - 1)
                containers.append(
                    OrderedDict(
                        [
                            ("id", cid),
                            ("level", n["level"]),
                            ("text", n["text"]),
                            ("line", n["line"]),
                            ("line_end", n["line_end"]),
                            ("span_lines", span),
                            ("has_children", has_children),
                            ("child_count", len(children)),
                            ("support_count", support),
                            ("status", "candidate"),
                        ]
                    )
                )
            elif n["level"] < container_level and not has_children and span > max_span:
                # 超大无子标题节段 → 自动分割
                split_points = _find_split_points(lines, n["line"] - 1, n["line_end"] - 1, max_chunk=max_span)
                if len(split_points) > 1:
                    # 有多个子片段 → 标记为 oversized_split
                    sub_id_base = _make_id()
                    split_into = []
                    for idx, (s, e, reason) in enumerate(split_points):
                        sub_support = _count_support(lines, s, e)
                        sub_id = f"{sub_id_base}{chr(ord('a') + idx)}"
                        split_into.append(
                            OrderedDict(
                                [
                                    ("sub_id", sub_id),
                                    ("line", s + 1),  # 1-indexed
                                    ("line_end", e + 1),
                                    ("span_lines", e - s + 1),
                                    ("support_count", sub_support),
                                    ("split_reason", reason),
                                ]
                            )
                        )
                    containers.append(
                        OrderedDict(
                            [
                                ("id", sub_id_base),
                                ("level", n["level"]),
                                ("text", n["text"]),
                                ("line", n["line"]),
                                ("line_end", n["line_end"]),
                                ("span_lines", span),
                                ("has_children", False),
                                ("child_count", 0),
                                ("support_count", _count_support(lines, n["line"] - 1, n["line_end"] - 1)),
                                ("auto_split", True),
                                ("split_into", split_into),
                                ("status", "oversized_split"),
                            ]
                        )
                    )
                else:
                    # 分割失败（只有一个片段）→ 作为普通容器
                    cid = _make_id()
                    support = _count_support(lines, n["line"] - 1, n["line_end"] - 1)
                    containers.append(
                        OrderedDict(
                            [
                                ("id", cid),
                                ("level", n["level"]),
                                ("text", n["text"]),
                                ("line", n["line"]),
                                ("line_end", n["line_end"]),
                                ("span_lines", span),
                                ("has_children", False),
                                ("child_count", 0),
                                ("support_count", support),
                                ("status", "oversized_no_split"),
                            ]
                        )
                    )

            # 递归处理子节点
            if has_children:
                _process(children)

    _process(headings_tree)

    from_headings = sum(1 for c in containers if c["status"] == "candidate")
    from_split = sum(1 for c in containers if c.get("auto_split"))

    summary = OrderedDict(
        [
            ("total_containers", len(containers)),
            ("from_headings", from_headings),
            ("from_oversized_split", from_split),
        ]
    )

    return containers, summary


def main():
    parser = argparse.ArgumentParser(description="提取章节 MD 的自适应容器结构")
    parser.add_argument("file", help="20_正文/第N章.md 路径")
    parser.add_argument("-o", "--output", required=True, help="输出 chapter_toc.json 路径")
    parser.add_argument("--max-span", type=int, default=200, help="超大节段分割阈值（行数，默认 200）")
    parser.add_argument("--legacy", action="store_true", help="仅输出旧格式 leaf_nodes（不生成 containers）")
    args = parser.parse_args()

    if not os.path.exists(args.file):
        log.error(f"❌ 文件不存在: {args.file}")
        raise PipelineError(f"文件不存在: {args.file}")

    parsed = parse_headings(args.file)
    tree = parsed["headings_tree"]
    total_lines = parsed["total_lines"]
    leaf_nodes = parsed["leaf_nodes"]

    # ── 读取文件行（用于 support_count 统计和超大节段分割）──
    with open(args.file, encoding="utf-8") as f:
        file_lines = f.readlines()

    # ── v36.5: 自适应容器探测 ──
    container_level, container_reason, level_stats = detect_container_level(tree, total_lines)

    # 构建 result
    result = OrderedDict(
        [
            ("chapter", _extract_chapter_from_path(args.file)),
            ("file", os.path.basename(args.file)),
            ("total_lines", total_lines),
        ]
    )

    if not args.legacy:
        # 自适应容器
        containers, summary = build_containers(tree, file_lines, container_level, args.max_span)

        result["container_level"] = container_level
        result["container_reason"] = container_reason
        result["level_stats"] = {
            str(lv): {
                "count": s["count"],
                "avg_lines": s["avg_lines"],
                "max_lines": s["max_lines"],
            }
            for lv, s in sorted(level_stats.items())
        }
        result["headings_tree"] = tree
        result["containers"] = containers
        result["leaf_nodes"] = leaf_nodes  # 向后兼容
        result["summary"] = summary
    else:
        # 旧格式
        result["headings_tree"] = tree
        result["leaf_nodes"] = leaf_nodes

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    # ── 打印报告 ──
    log.success(f"✅ {os.path.basename(args.file)} → {args.output}")
    log.info(f"   总行数: {total_lines}")
    log.info(f"   标题数: {len(tree)} (顶层)")

    if not args.legacy:
        hashes = "#" * container_level
        log.info(f"   容器层级: {hashes} (Lv{container_level}) — {container_reason}")
        log.info("   层级统计:")
        for lv, s in sorted(level_stats.items()):
            marker = " ← 容器层" if lv == container_level else ""
            log.info(f"     Lv{lv}: {s['count']}个标题, 平均{s['avg_lines']}行{marker}")
        log.info(f"   容器数: {summary['total_containers']} (标题{summary['from_headings']} + 分割{summary['from_oversized_split']})")

        # 打印前几个容器
        for c in containers[:5]:
            status_icon = "🔀" if c.get("auto_split") else "📦"
            log.info(f"     {status_icon} L{c['line']}-L{c['line_end']} ({c['span_lines']}行) Lv{c['level']}: {c['text']}")
            if c.get("auto_split"):
                for sub in c.get("split_into", []):
                    log.info(f"        └ {sub['sub_id']}: L{sub['line']}-L{sub['line_end']} ({sub['split_reason']})")
        if len(containers) > 5:
            log.info(f"     ... 共 {len(containers)} 个容器")
    else:
        cc = leaf_nodes
        log.info(f"   叶节点（概念候选）: {len(cc)}")
        for c in cc[:5]:
            log.info(f"     L{c['line']}-L{c['line_end']} (Lv{c['level']}): {c['text']}")
        if len(cc) > 5:
            log.info(f"     ... 共 {len(cc)} 个")
        by_level = {}
        for c in cc:
            lv = c["level"]
            by_level[lv] = by_level.get(lv, 0) + 1
        if len(by_level) > 1:
            log.info(f"   层级分布: {' | '.join(f'Lv{lv}:{cnt}' for lv, cnt in sorted(by_level.items()))}")


def _extract_chapter_from_path(filepath):
    """从文件路径提取章节号：第2章.md → '2'，第10章 xxx.md → '10'"""
    basename = os.path.basename(filepath)
    m = re.search(r"第(\d+)章", basename)
    return m.group(1) if m else "0"


if __name__ == "__main__":
    try:
        main()
    except PipelineError as e:
        log.error(str(e))
        raise
