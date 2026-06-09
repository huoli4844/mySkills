#!/usr/bin/env python3
"""graph_analytics.py — 知识图谱分析函数集

提供从 kg_builder 数据生成索引模板所需各分析板块的函数：
- build_graph_section(): 构建所有分析板块（连通率、质量、Mermaid、学习路径等）
- get_enriched_nodes(): 拓扑增强字段（度中心性、上下游、in_scene 等）
"""

from __future__ import annotations

import itertools
import os
import sys
from collections import defaultdict


# ── Mermaid 安全命名 ──────────────────────────────────────

def _mermaid_safe(name: str) -> str:
    """将名称转为 Mermaid 安全标识符"""
    safe = ""
    for c in name:
        if c.isalnum() or "\u4e00" <= c <= "\u9fff" or "\u3400" <= c <= "\u4dbf" or c == "_":
            safe += c
        elif c in " \t-":
            safe += "_"
    return safe or "node"


# ── 拓扑增强 ──────────────────────────────────────────────

def get_enriched_nodes(kg) -> dict:
    """从 KGraph 获取每个节点的拓扑增强字段

    Returns:
        {node_id: {degree, out_degree, in_degree, downstream_count, upstream_count, in_scene}}
    """
    enriched = {}
    try:
        with kg._conn() as c:
            rows = c.execute(
                """SELECT n.id, n.type, n.name,
                          (SELECT COUNT(*) FROM edges WHERE source_id=n.id) AS out_d,
                          (SELECT COUNT(*) FROM edges WHERE target_id=n.id) AS in_d
                   FROM nodes n WHERE n.type NOT IN ('index')""",
            ).fetchall()
            for nid, ntype, _name, out_d, in_d in rows:
                downstream = c.execute(
                    """SELECT COUNT(DISTINCT e.target_id) FROM edges e
                       WHERE e.source_id=?""",
                    (nid,),
                ).fetchone()[0]
                upstream = c.execute(
                    """SELECT COUNT(DISTINCT e.source_id) FROM edges e
                       WHERE e.target_id=? AND e.source_id IN
                         (SELECT id FROM nodes WHERE type NOT IN ('exercise','solution','index'))""",
                    (nid,),
                ).fetchone()[0]
                in_scene = (
                    c.execute(
                        """SELECT COUNT(*) FROM edges e WHERE e.source_id=?
                           AND e.target_id IN (SELECT id FROM nodes WHERE type='scenario')""",
                        (nid,),
                    ).fetchone()[0]
                    > 0
                )
                enriched[nid] = {
                    "degree": out_d + in_d,
                    "out_degree": out_d,
                    "in_degree": in_d,
                    "downstream_count": downstream,
                    "upstream_count": upstream,
                    "in_scene": in_scene,
                }
    except Exception as e:
        print(f"  ⚠️ 拓扑增强失败: {e}")
    return enriched


# ── 构建索引模板用的 graph_section ────────────────────────

def build_graph_section(kg) -> dict:
    """构建图驱动的结构化内容板块

    Returns:
        dict 包含各个板块的 markdown 字符串
    """

    result = {
        "chain_connectivity": "（图谱未构建）",
        "node_connectivity": "",
        "graph_quality": "",
        "top_nodes": "",
        "mindmap_content": "",
        "chapter_distribution": "",
        "learning_path": "（待补充）",
        "error_attribution": "（暂无习题数据，无法归因分析）",
        "learning_path_v2": "（待补充）",
        "todo_items": "（无待修复项）",
        "concept_index": "",
        "knowledge_index": "",
        "skill_index": "",
        "scenario_index": "",
    }

    try:
        quality = kg.check_graph_quality()
    except Exception as e:
        print(f"  ⚠️ 图质量检查失败: {e}")
        quality = {"summary": {"critical": 0, "warning": 0, "info": 0}, "issues": []}

    # ── 1. 节点连接性统计 ──
    try:
        type_stats = kg.get_type_stats()
        if type_stats:
            node_conn = "| 节点类型 | 数量 | 平均出度 | 平均入度 |\n|:--------|:---:|:-------:|:-------:|\n"
            for t, cnt, avg_o, avg_i in type_stats:
                node_conn += f"| {t} | {cnt} | {avg_o} | {avg_i} |\n"

            with kg._conn() as c:
                total = c.execute(
                    "SELECT COUNT(*) FROM nodes WHERE type NOT IN ('index','exercise','solution')",
                ).fetchone()[0]
                connected = c.execute(
                    """SELECT COUNT(DISTINCT n.id) FROM nodes n
                       WHERE n.type NOT IN ('index','exercise','solution')
                       AND EXISTS (SELECT 1 FROM edges e WHERE e.source_id=n.id OR e.target_id=n.id)""",
                ).fetchone()[0]
                if total > 0:
                    conn_rate = round(connected / total * 100, 1)
                    node_conn += f"\n> **连通率**: {connected}/{total} 节点 ({conn_rate}%) 有至少一条边连接\n"
            result["node_connectivity"] = node_conn
    except Exception as e:
        print(f"  ⚠️ 连接性统计失败: {e}")

    # ── 2. 知识链连通率 ──
    try:
        with kg._conn() as c:
            chain_types = ["concept", "knowledge-element", "knowledge", "skill", "scenario"]
            chain_text = "| 链路 | 总数 | 连通数 | 连通率 |\n|:----|:---:|:-----:|:-----:|\n"
            for src_t, tgt_t in itertools.pairwise(chain_types):
                src_cnt = c.execute(
                    "SELECT COUNT(*) FROM nodes WHERE type=?",
                    (src_t,),
                ).fetchone()[0]
                if src_cnt == 0:
                    continue
                connected_cnt = c.execute(
                    """SELECT COUNT(DISTINCT n.id) FROM nodes n
                       WHERE n.type=?
                       AND EXISTS (SELECT 1 FROM edges e
                                    JOIN nodes nt ON e.target_id=nt.id
                                    WHERE (e.source_id=n.id) AND nt.type=?)""",
                    (src_t, tgt_t),
                ).fetchone()[0]
                rate = round(connected_cnt / src_cnt * 100, 1)
                bar = "█" * int(rate / 10) + "░" * (10 - int(rate / 10))
                chain_text += f"| {src_t}→{tgt_t} | {src_cnt} | {connected_cnt} | {bar} {rate}% |\n"
            result["chain_connectivity"] = chain_text
    except Exception as e:
        print(f"  ⚠️ 知识链分析失败: {e}")

    # ── 3. 图质量摘要 ──
    try:
        s = quality["summary"]
        qual_text = "| 严重度 | 数量 | 含义 |\n|:------|:---:|:-----|\n"
        qual_text += f"| 🔴 Critical | {s['critical']} | 空心概念/孤儿KE，需立即修复 |\n"
        qual_text += f"| ⚠️ Warning | {s['warning']} | 路径断裂/孤立节点/过载节点 |\n"
        qual_text += f"| ℹ️ Info | {s['info']} | 循环引用/核心节点参考 |\n"

        hollow = [i for i in quality["issues"] if i["category"] == "空心概念"]
        if hollow:
            qual_text += "\n**空心概念（无KE引用）**：\n"
            for h in hollow[:8]:
                name = h["message"].split("「")[1].split("」")[0] if "「" in h["message"] else h["message"]
                fix = h.get("fix_hint", "补充引用的知识要素")
                qual_text += f"- {name} → {fix}\n"
            if len(hollow) > 8:
                qual_text += f"  ... 还有 {len(hollow)-8} 个空心概念\n"

        orphan_kes = [i for i in quality["issues"] if i["category"] == "孤儿KE"]
        if orphan_kes:
            qual_text += "\n**孤儿KE（无KP使用）**：\n"
            for o in orphan_kes[:10]:
                name = o["message"].split("「")[1].split("」")[0] if "「" in o["message"] else o["message"]
                qual_text += f"- {name}\n"
            if len(orphan_kes) > 10:
                qual_text += f"  ... 还有 {len(orphan_kes)-10} 个孤儿KE\n"

        result["graph_quality"] = qual_text
    except Exception as e:
        print(f"  ⚠️ 质量分析失败: {e}")

    # ── 4. 核心节点排名 ──
    try:
        top = kg.get_top_nodes(limit=10)
        if top:
            top_text = "| 排名 | 节点 | 类型 | 入度 | 出度 | 总度 |\n|:---:|:----|:----|:---:|:---:|:---:|\n"
            for i, r in enumerate(top, 1):
                deg = r["in_degree"] + r["out_degree"]
                top_text += f"| {i} | {r['name']} | {r['type']} | {r['in_degree']} | {r['out_degree']} | {deg} |\n"
            result["top_nodes"] = top_text
    except Exception as e:
        print(f"  ⚠️ Top节点分析失败: {e}")

    # ── 5. Mermaid 全景图 ──
    try:
        with kg._conn() as c:
            total_nodes = c.execute(
                "SELECT COUNT(*) FROM nodes WHERE type NOT IN ('index','exercise','solution')",
            ).fetchone()[0]

            if total_nodes > 0:
                type_icons = {
                    "concept": "📘", "knowledge-element": "📐",
                    "knowledge": "🎯", "skill": "🔧",
                    "scenario": "🏗", "entity": "📦",
                }
                mermaid_lines = ["graph TB"]

                # 获取高连接度边（TOP 50）
                edge_rows = c.execute(
                    """SELECT n1.name, n2.name FROM edges e
                       JOIN nodes n1 ON e.source_id=n1.id
                       JOIN nodes n2 ON e.target_id=n2.id
                       WHERE n1.type NOT IN ('index', 'solution', 'exercise')
                       AND n2.type NOT IN ('index', 'solution', 'exercise')
                       ORDER BY (SELECT COUNT(*) FROM edges e2
                                 WHERE e2.source_id=e.source_id OR e2.target_id=e.target_id) DESC
                       LIMIT 50""",
                ).fetchall()

                connected_names = set()
                for src, tgt in edge_rows:
                    connected_names.add(src)
                    connected_names.add(tgt)

                all_nodes = {}
                for ntype, icon in type_icons.items():
                    rows = c.execute(
                        "SELECT name FROM nodes WHERE type=?",
                        (ntype,),
                    ).fetchall()
                    for (name,) in rows:
                        if name and name in connected_names and name not in all_nodes:
                            safe = _mermaid_safe(name)
                            label = name.replace('"', "'")
                            all_nodes[name] = (safe, icon)
                            mermaid_lines.append(f'    {safe}["{label}"]')

                drawn = set()
                for src, tgt in edge_rows:
                    if src in all_nodes and tgt in all_nodes and src != tgt:
                        ek = (src, tgt)
                        if ek not in drawn:
                            drawn.add(ek)
                            ss = all_nodes[src][0]
                            ts = all_nodes[tgt][0]
                            mermaid_lines.append(f"    {ss} -.-> {ts}")

                result["mindmap_content"] = "\n".join(mermaid_lines)
    except Exception as e:
        print(f"  ⚠️ Mermaid生成失败: {e}")

    # ── 6. 章节分布 ──
    try:
        ch_nodes = kg.get_chapter_distribution()
        if ch_nodes:
            by_ch = {}
            for ch, nt, cnt in ch_nodes:
                if ch not in by_ch:
                    by_ch[ch] = {}
                by_ch[ch][nt] = cnt
            ch_text = "| 章节 | 概念 | KE | 实体 | KP | SP | Scene |\n|:----|:---:|:--:|:---:|:--:|:--:|:----:|\n"
            for ch in sorted(by_ch.keys()):
                d = by_ch[ch]
                ch_text += (f"| 第{ch}章 | {d.get('concept',0)} | {d.get('knowledge-element',0)} "
                           f"| {d.get('entity',0)} | {d.get('knowledge',0)} "
                           f"| {d.get('skill',0)} | {d.get('scenario',0)} |\n")
            result["chapter_distribution"] = ch_text
    except Exception as e:
        print(f"  ⚠️ 章节分布分析失败: {e}")

    # ── 7. 推荐学习路径 ──
    try:
        top5 = kg.get_top_nodes(limit=5)
        if top5:
            paths = []
            for r in top5[:3]:
                try:
                    trace_result = kg.trace(r["name"])
                    if trace_result.get("levels"):
                        path_nodes = []
                        for lvl in trace_result["levels"][:4]:
                            seen_type = set()
                            for n in lvl.get("nodes", [])[:3]:
                                if n["type"] not in seen_type and len(path_nodes) < 6:
                                    path_nodes.append(f"[[{n['name']}]]")
                                    seen_type.add(n["type"])
                        if path_nodes:
                            paths.append(f"- 🚀 从「{r['name']}」出发: {' → '.join(path_nodes)}")
                except Exception as e:  # 单条路径分析失败
                    pass
            if paths:
                result["learning_path"] = "\n".join(paths)
    except Exception as e:
        print(f"  ⚠️ 学习路径分析失败: {e}")

    # ── 8. 待修复项 ──
    s = quality["summary"]
    if s["total_issues"] > 0:
        todo_lines = []
        if s["critical"] > 0:
            todo_lines.append(f"- 🔴 修复 {s['critical']} 个严重问题（空心概念/孤儿KE）")
        if s["warning"] > 0:
            todo_lines.append(f"- ⚠️ 修复 {s['warning']} 个警告（孤立节点/路径断裂）")
        result["todo_items"] = "\n".join(todo_lines)

    return result
