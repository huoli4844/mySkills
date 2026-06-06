"""pipeline_insights.py — 知识图谱洞察 (v46.0 新增)

借鉴 LLM Wiki 的 Graph Insights 机制：
  1. 孤立节点检测 — degree <= 1 的节点
  2. 稀疏社区发现 — Louvain 社区检测 + cohesion 评分
  3. 桥接节点识别 — 连接 3+ 社区的枢纽节点
  4. 跨章连通性报告

依赖: networkx (python3.12 -m pip install networkx)

用法:
  python3 pipeline_insights.py report -w BOOK_DIR --book-id XX
  python3 pipeline_insights.py gaps -w BOOK_DIR --book-id XX       # 仅知识缺口
  python3 pipeline_insights.py communities -w BOOK_DIR --book-id XX # 仅社区分析
"""

import os
import sys
from collections import defaultdict
from typing import Any

from dag_constants import DIR
from log_utils import get_logger

log = get_logger(__name__)

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)


# ── 类型常量 ──────────────────────────────────────────────

NODE_TYPES = {
    "concept": "核心概念",
    "knowledge-element": "知识要素",
    "entity": "实体",
    "knowledge-point": "知识点",
    "skill-point": "技能点",
    "scenario": "应用场景",
    "exercise": "习题",
    "solution": "解答",
}

TYPE_ICONS = {
    "concept": "📘",
    "knowledge-element": "📐",
    "entity": "📦",
    "knowledge-point": "🎯",
    "skill-point": "🔧",
    "scenario": "🏗",
    "exercise": "📝",
    "solution": "✅",
}

# 认知层级权重 (Bloom: 知道→理解→应用→分析→评价→创造)
COGNITIVE_ORDER = {
    "knowledge-element": 0,  # 知道
    "entity": 0,
    "concept": 1,  # 理解
    "knowledge-point": 2,  # 应用
    "skill-point": 3,  # 分析
    "scenario": 4,  # 评价→创造
}


def _load_graph(wr: str, book_id: str) -> dict[str, Any] | None:
    """从 kb_graph 加载图谱数据。返回 {nodes, edges} 或 None。"""
    try:
        from kb_graph import KGraph

        kg = KGraph(wr)
        kg_data = kg.query_all()
        if not kg_data:
            log.warning("图谱数据为空")
            return None

        nodes = kg_data.get("nodes", [])
        edges = kg_data.get("edges", [])
        return {"nodes": nodes, "edges": edges}
    except Exception as e:
        log.error(f"加载图谱失败: {e}")
        return None


def _build_networkx(nodes: list[dict], edges: list[dict]):
    """构建 networkx 图"""
    import networkx as nx

    G = nx.Graph()
    for n in nodes:
        nid = n.get("id", "")
        G.add_node(
            nid,
            name=n.get("name", nid),
            type=n.get("type", "unknown"),
            chapter=n.get("chapter", ""),
        )
    for e in edges:
        G.add_edge(
            e.get("source", ""),
            e.get("target", ""),
            weight=e.get("weight", 1.0),
        )
    return G


def detect_isolated_nodes(
    G, book_id: str
) -> list[dict]:
    """检测孤立节点 (degree <= 1)。

    Returns:
        [{"id": ..., "name": ..., "type": ..., "degree": ..., "chapter": ...}, ...]
    """
    isolated = []
    for nid, degree in G.degree():
        if degree <= 1:
            attrs = G.nodes[nid]
            isolated.append(
                {
                    "id": nid,
                    "name": attrs.get("name", nid),
                    "type": attrs.get("type", "unknown"),
                    "degree": degree,
                    "chapter": attrs.get("chapter", ""),
                }
            )
    # 按 degree 排序（0 度最严重）
    isolated.sort(key=lambda x: x["degree"])
    return isolated


def detect_bridge_nodes(
    G, communities: list[set], book_id: str
) -> list[dict]:
    """检测桥接节点 — 连接 3+ 社区的枢纽。

    Returns:
        [{"id": ..., "name": ..., "type": ..., "communities": N, ...}, ...]
    """
    if len(communities) < 3:
        return []

    # 构建节点→社区映射
    node_to_comm = {}
    for i, comm in enumerate(communities):
        for nid in comm:
            node_to_comm.setdefault(nid, set()).add(i)

    bridges = []
    for nid in G.nodes():
        neighbor_comms = set()
        for neighbor in G.neighbors(nid):
            if neighbor in node_to_comm:
                neighbor_comms.update(node_to_comm[neighbor])
        # 自身社区不算
        own_comms = node_to_comm.get(nid, set())
        external = neighbor_comms - own_comms
        if len(external) >= 3:
            attrs = G.nodes[nid]
            bridges.append(
                {
                    "id": nid,
                    "name": attrs.get("name", nid),
                    "type": attrs.get("type", "unknown"),
                    "communities": len(external),
                    "degree": G.degree(nid),
                }
            )
    bridges.sort(key=lambda x: -x["communities"])
    return bridges


def detect_sparse_communities(
    G, communities: list[set]
) -> list[dict]:
    """检测稀疏社区 (cohesion < 0.15)。

    Returns:
        [{"id": i, "size": N, "cohesion": score, "members": [...]}, ...]
    """
    sparse = []
    for i, comm in enumerate(communities):
        if len(comm) < 3:
            continue
        # cohesion = 内部边数 / 可能最大边数
        subgraph = G.subgraph(comm)
        n_nodes = subgraph.number_of_nodes()
        possible_edges = n_nodes * (n_nodes - 1) / 2
        actual_edges = subgraph.number_of_edges()
        cohesion = actual_edges / possible_edges if possible_edges > 0 else 0

        members_info = []
        for nid in comm:
            attrs = G.nodes[nid]
            members_info.append(
                {
                    "id": nid,
                    "name": attrs.get("name", nid),
                    "type": attrs.get("type", "unknown"),
                }
            )

        comm_info = {
            "id": i,
            "size": len(comm),
            "cohesion": round(cohesion, 3),
            "members": members_info,
        }
        if cohesion < 0.15:
            sparse.append(comm_info)

    sparse.sort(key=lambda x: x["cohesion"])
    return sparse


def run_louvain(G) -> list[set]:
    """运行 Louvain 社区检测"""
    from networkx.algorithms.community import louvain_communities

    return louvain_communities(G, seed=42)


def cross_chapter_connectivity(
    G, nodes: list[dict]
) -> dict[str, Any]:
    """分析跨章连通性。

    Returns:
        {"chapter_pairs": [(ch1, ch2, count), ...], "isolated_chapters": [...]}
    """
    # 提取章节标签
    chapter_labels = {}
    for n in nodes:
        nid = n.get("id", "")
        # 从 node ID 中提取章节号 (例如 "xxx/第1章 电磁兼容概述/...")
        import re

        ch_match = re.search(r"第(\d+)章", nid)
        if ch_match:
            chapter_labels[nid] = f"第{ch_match.group(1)}章"

    # 统计跨章边
    ch_pairs = defaultdict(int)
    for n1, n2 in G.edges():
        ch1 = chapter_labels.get(n1)
        ch2 = chapter_labels.get(n2)
        if ch1 and ch2 and ch1 != ch2:
            pair = tuple(sorted([ch1, ch2]))
            ch_pairs[pair] += 1

    # 排序
    sorted_pairs = sorted(ch_pairs.items(), key=lambda x: -x[1])

    return {
        "cross_chapter_edges": sorted_pairs,
        "total_cross_chapter": len(sorted_pairs),
        "total_cross_chapter_edges": sum(c for _, c in sorted_pairs),
    }


def _keyword_overlap_ratio(text_a: str, text_b: str) -> float:
    """计算两个文本的关键词重叠率（Jaccard 相似度）。

    使用 2-gram 字符级 n-gram 进行快速近似语义相似度计算，
    不依赖 sklearn 等重量级库。

    Returns:
        0.0 ~ 1.0 之间的相似度
    """
    import re

    def _tokens(s: str) -> set[str]:
        """提取有意义的中文关键词（2-3 字 n-gram）"""
        # 去除非中文字符和标点
        cleaned = re.sub(r"[^\u4e00-\u9fff]", "", s)
        ngrams = set()
        for n in (2, 3):
            for i in range(len(cleaned) - n + 1):
                ngrams.add(cleaned[i : i + n])
        return ngrams

    ta = _tokens(text_a)
    tb = _tokens(text_b)
    if not ta or not tb:
        return 0.0
    intersection = ta & tb
    union = ta | tb
    return len(intersection) / len(union) if union else 0.0


def _concept_name_similarity(name_a: str, name_b: str) -> float:
    """计算两个概念名称的相似度。

    使用编辑距离 + Jaccard 加权，对中文概念名称做模糊匹配。

    Returns:
        0.0 ~ 1.0
    """
    # 完全相同
    if name_a == name_b:
        return 1.0

    # 简单关键词重叠
    set_a = set(name_a)
    set_b = set(name_b)
    if not set_a or not set_b:
        return 0.0
    jaccard = len(set_a & set_b) / len(set_a | set_b)

    # 包含关系加分
    if name_a in name_b or name_b in name_a:
        jaccard = max(jaccard, 0.8)

    return jaccard


def _parse_md_sections(content: str) -> dict[str, str]:
    """解析 .md 文件，提取关键字段。

    Returns:
        {
            "name": str,
            "chapter_num": str,
            "book_id": str,
            "type": str,
            "bloom_level": str,
            "definition_sentence": str,
            "classification": str,
            "solved_problem": str,
            "file_path": str,
        }
    """
    import re

    result: dict[str, str] = {}

    # FM 解析
    fm_match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    fm_text = fm_match.group(1) if fm_match else ""

    for field in ["name", "chapter_num", "book_id", "type"]:
        m = re.search(rf"^{field}:\s*(.+)$", fm_text, re.MULTILINE)
        if m:
            result[field] = m.group(1).strip()

    # bloom_level 可能在 FM 或正文中
    bloom_fm = re.search(r"^bloom_level:\s*(.+)$", fm_text, re.MULTILINE)
    if bloom_fm:
        result["bloom_level"] = bloom_fm.group(1).strip()

    # 从学习目标中推断 Bloom 层级
    if "bloom_level" not in result:
        bloom_body = re.search(
            r"记忆层|理解层|应用层|分析层|评价层|创造层",
            content,
        )
        if bloom_body:
            levels = set()
            for level in ["记忆层", "理解层", "应用层", "分析层", "评价层", "创造层"]:
                if level in content:
                    levels.add(level)
            result["bloom_level"] = ", ".join(sorted(levels)) if levels else ""

    # 术语定义
    def_sec = re.search(
        r"###\s*\d+\.?\s*术语定义\s*\n+(.+?)(?:\n###|\n##|\Z)",
        content, re.DOTALL,
    )
    if def_sec:
        result["definition_sentence"] = def_sec.group(1).strip()

    # 分类
    class_sec = re.search(
        r"###\s*\d+\.?\s*分类与学科归属.*?\n-\s*\*\*分类\*\*[：:]\s*(.+?)(?:\n|$)",
        content, re.DOTALL,
    )
    if class_sec:
        result["classification"] = class_sec.group(1).strip()

    # 解决的问题
    solved_sec = re.search(
        r"###\s*\d+\.?\s*解决的问题\s*\n+(.+?)(?:\n###|\n##|\Z)",
        content, re.DOTALL,
    )
    if solved_sec:
        result["solved_problem"] = solved_sec.group(1).strip()

    return result


def check_cross_chapter_consistency(wr: str, book_id: str | None = None) -> dict:
    """v47.0: 跨章一致性校验。

    扫描领域内所有概念/KE/实体文件的 definition_sentence、Bloom 层级、
    分类归属等字段，检测跨章同名/近名概念定义不一致。

    Args:
        wr: 书目录（自动推导到领域层）
        book_id: 可选，限制仅在指定书籍内扫描

    Returns:
        {
            "total_concepts": int,
            "same_name_conflicts": [...],
            "similar_name_conflicts": [...],
            "summary": {...},
        }
    """
    import json
    import os
    import re
    from collections import defaultdict
    from pathlib import Path

    # 推导领域目录
    wp = WorkspacePaths(wr) if "WorkspacePaths" in dir() else None
    if wp is None:
        from dag_state import WorkspacePaths as _WP

        wp = _WP(wr)
    domain_dir = wp.domain_dir

    # 收集所有概念/KE/实体文件
    all_concepts: list[dict] = []
    book_dirs = []
    if book_id:
        # 单书模式
        book_dirs = [wr]
    else:
        # 领域模式：扫描所有书籍目录
        for entry in sorted(os.listdir(domain_dir)):
            entry_path = os.path.join(domain_dir, entry)
            if os.path.isdir(entry_path) and not entry.startswith(".") and entry != DIR.get("DOMAIN_CTRL", "领域总控"):
                book_dirs.append(entry_path)

    concept_dirs = [
        DIR.get("CONCEPTS", "30_核心概念"),
        DIR.get("KE", "40_知识要素"),
        DIR.get("ENTITIES", "80_实体"),
    ]

    for book_dir in book_dirs:
        for cd in concept_dirs:
            full_dir = os.path.join(book_dir, cd)
            if not os.path.isdir(full_dir):
                continue
            for fp in sorted(Path(full_dir).glob("*.md")):
                try:
                    content = fp.read_text(encoding="utf-8")
                except Exception as e:
                    log.debug(f"读取概念文件失败: {e}")
                    continue
                parsed = _parse_md_sections(content)
                parsed["file_path"] = str(fp)
                parsed["book_dir"] = book_dir
                all_concepts.append(parsed)

    if not all_concepts:
        return {
            "total_concepts": 0,
            "same_name_conflicts": [],
            "similar_name_conflicts": [],
            "summary": {"message": "未找到概念文件"},
        }

    # ── 1. 同名概念跨章一致性检查 ──
    name_groups: dict[str, list[dict]] = defaultdict(list)
    for c in all_concepts:
        name = c.get("name", "").strip()
        if name:
            name_groups[name].append(c)

    same_name_conflicts = []
    for name, items in name_groups.items():
        if len(items) < 2:
            continue
        # 比较所有配对
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                a, b = items[i], items[j]
                conflicts = []

                # 比较 definition_sentence
                def_a = a.get("definition_sentence", "")
                def_b = b.get("definition_sentence", "")
                if def_a and def_b and def_a != def_b:
                    sim = _keyword_overlap_ratio(def_a, def_b)
                    if sim < 0.5:
                        conflicts.append({
                            "type": "definition_mismatch",
                            "similarity": round(sim, 3),
                            "detail_a": def_a[:200],
                            "detail_b": def_b[:200],
                        })
                    elif sim < 0.8:
                        conflicts.append({
                            "type": "definition_divergence",
                            "similarity": round(sim, 3),
                            "detail_a": def_a[:200],
                            "detail_b": def_b[:200],
                        })

                # 比较 Bloom 层级
                bloom_a = a.get("bloom_level", "")
                bloom_b = b.get("bloom_level", "")
                if bloom_a and bloom_b and bloom_a != bloom_b:
                    conflicts.append({
                        "type": "bloom_mismatch",
                        "value_a": bloom_a,
                        "value_b": bloom_b,
                    })

                # 比较分类
                class_a = a.get("classification", "")
                class_b = b.get("classification", "")
                if class_a and class_b and class_a != class_b:
                    conflicts.append({
                        "type": "classification_mismatch",
                        "value_a": class_a,
                        "value_b": class_b,
                    })

                if conflicts:
                    same_name_conflicts.append({
                        "concept_name": name,
                        "file_a": a["file_path"],
                        "file_b": b["file_path"],
                        "chapter_a": a.get("chapter_num", ""),
                        "chapter_b": b.get("chapter_num", ""),
                        "conflicts": conflicts,
                    })

    # ── 2. 近名概念跨章一致性检查 ──
    # 构建所有概念名列表，进行 O(n²) 配对检查
    unique_names = list(name_groups.keys())
    similar_name_conflicts = []
    similarity_threshold = 0.6

    # 先对已识别的同名组不加额外检查
    for i in range(len(unique_names)):
        for j in range(i + 1, len(unique_names)):
            name_a, name_b = unique_names[i], unique_names[j]
            sim = _concept_name_similarity(name_a, name_b)
            if similarity_threshold <= sim < 1.0:
                items_a = name_groups[name_a]
                items_b = name_groups[name_b]
                # 取每组的第一个代表进行比较
                rep_a, rep_b = items_a[0], items_b[0]

                conflicts = []

                def_a = rep_a.get("definition_sentence", "")
                def_b = rep_b.get("definition_sentence", "")
                if def_a and def_b:
                    def_sim = _keyword_overlap_ratio(def_a, def_b)
                    if def_sim < 0.3:
                        conflicts.append({
                            "type": "potential_duplicate_low_def_sim",
                            "name_similarity": round(sim, 3),
                            "definition_similarity": round(def_sim, 3),
                            "note": "名称相似但定义差异大，可能为不同概念",
                        })
                    elif def_sim >= 0.7:
                        conflicts.append({
                            "type": "potential_merge_candidate",
                            "name_similarity": round(sim, 3),
                            "definition_similarity": round(def_sim, 3),
                            "note": "名称相似且定义高度重叠，建议检查是否需要合并",
                        })

                # 比较分类
                class_a = rep_a.get("classification", "")
                class_b = rep_b.get("classification", "")
                if class_a and class_b and class_a != class_b:
                    conflicts.append({
                        "type": "similar_name_different_classification",
                        "value_a": class_a,
                        "value_b": class_b,
                    })

                if conflicts:
                    similar_name_conflicts.append({
                        "name_a": name_a,
                        "name_b": name_b,
                        "name_similarity": round(sim, 3),
                        "file_a": rep_a["file_path"],
                        "file_b": rep_b["file_path"],
                        "chapter_a": rep_a.get("chapter_num", ""),
                        "chapter_b": rep_b.get("chapter_num", ""),
                        "conflicts": conflicts,
                    })

    # ── 汇总 ──
    total_conflicts = len(same_name_conflicts) + len(similar_name_conflicts)
    severity_breakdown = {
        "definition_mismatch": sum(
            1 for x in same_name_conflicts
            for c in x["conflicts"] if c["type"] == "definition_mismatch"
        ),
        "definition_divergence": sum(
            1 for x in same_name_conflicts
            for c in x["conflicts"] if c["type"] == "definition_divergence"
        ),
        "bloom_mismatch": sum(
            1 for x in same_name_conflicts
            for c in x["conflicts"] if c["type"] == "bloom_mismatch"
        ),
        "classification_mismatch": sum(
            1 for x in same_name_conflicts
            for c in x["conflicts"] if c["type"] == "classification_mismatch"
        ),
        "potential_merge_candidate": sum(
            1 for x in similar_name_conflicts
            for c in x["conflicts"] if c["type"] == "potential_merge_candidate"
        ),
        "potential_duplicate_low_def_sim": sum(
            1 for x in similar_name_conflicts
            for c in x["conflicts"] if c["type"] == "potential_duplicate_low_def_sim"
        ),
    }

    result = {
        "total_concepts": len(all_concepts),
        "unique_names": len(name_groups),
        "same_name_conflicts": same_name_conflicts,
        "similar_name_conflicts": similar_name_conflicts,
        "summary": {
            "total_conflicts": total_conflicts,
            "same_name_conflict_count": len(same_name_conflicts),
            "similar_name_conflict_count": len(similar_name_conflicts),
            "severity_breakdown": severity_breakdown,
        },
    }

    # 输出到文件
    dag_dir = os.path.join(wr, ".dag")
    os.makedirs(dag_dir, exist_ok=True)
    output_path = os.path.join(dag_dir, "cross_chapter_consistency.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    log.info(f"📋 跨章一致性报告已生成: {output_path}")
    log.info(f"   扫描概念: {len(all_concepts)} 个 (唯一名: {len(name_groups)})")
    log.info(f"   同名冲突: {len(same_name_conflicts)} 组")
    log.info(f"   近名冲突: {len(similar_name_conflicts)} 组")

    return result


def generate_insights_report(wr: str, book_id: str) -> str:
    """生成完整的洞察报告 (Markdown 格式)。

    Returns:
        Markdown 字符串
    """
    data = _load_graph(wr, book_id)
    if not data:
        return "⚠️ 无法加载图谱数据，请先运行 `pipeline batch` 构建知识库。"

    nodes = data["nodes"]
    edges = data["edges"]
    G = _build_networkx(nodes, edges)

    if G.number_of_nodes() == 0:
        return "⚠️ 图谱为空，请先构建知识库。"

    lines = []
    lines.append("# 知识图谱洞察报告\n")
    lines.append(f"> 分析时间: 自动生成 | 节点: {G.number_of_nodes()} | 边: {G.number_of_edges()}\n")

    # ── 1. 全局指标 ──
    lines.append("## 1. 全局指标\n")
    lines.append(f"- 总节点: {G.number_of_nodes()}")
    lines.append(f"- 总连接: {G.number_of_edges()}")
    if G.number_of_nodes() > 0:
        lines.append(f"- 平均度: {2 * G.number_of_edges() / G.number_of_nodes():.1f}")

    # 各类型统计
    type_counts = defaultdict(int)
    for n in nodes:
        type_counts[n.get("type", "unknown")] += 1
    lines.append("\n### 节点类型分布\n")
    for t, count in sorted(type_counts.items()):
        icon = TYPE_ICONS.get(t, "❓")
        label = NODE_TYPES.get(t, t)
        lines.append(f"- {icon} {label}: {count}")

    # ── 2. 知识缺口 ──
    lines.append("\n## 2. 知识缺口\n")
    isolated = detect_isolated_nodes(G, book_id)
    if isolated:
        lines.append(f"### ⚠️ 孤立节点 ({len(isolated)})\n")
        lines.append("以下节点缺乏与其他知识的连接：\n")
        for item in isolated[:15]:
            icon = TYPE_ICONS.get(item["type"], "❓")
            label = NODE_TYPES.get(item["type"], item["type"])
            deg_label = "完全孤立" if item["degree"] == 0 else "仅1条连接"
            lines.append(
                f"- {icon} **{item['name']}** ({label}) — {deg_label}"
            )
            if item.get("chapter"):
                lines.append(f"  章节: {item['chapter']}")
        if len(isolated) > 15:
            lines.append(f"\n...还有 {len(isolated) - 15} 个孤立节点")
    else:
        lines.append("✅ 无孤立节点\n")

    # ── 3. 社区分析 ──
    lines.append("\n## 3. 社区分析 (Louvain)\n")
    try:
        communities = run_louvain(G)
        lines.append(f"发现 **{len(communities)}** 个知识社区\n")

        # 稀疏社区
        sparse = detect_sparse_communities(G, communities)
        if sparse:
            lines.append("### ⚠️ 稀疏社区 (cohesion < 0.15)\n")
            for comm in sparse:
                top_members = comm["members"][:5]
                top_labels = ", ".join(
                    m["name"] for m in top_members
                )
                lines.append(
                    f"- 社区#{comm['id']}: {comm['size']}节点, "
                    f"cohesion={comm['cohesion']}, "
                    f"主要: {top_labels}"
                )
            lines.append("")

        # 桥接节点
        bridges = detect_bridge_nodes(G, communities, book_id)
        if bridges:
            lines.append("### 🔗 桥接节点 (连接 3+ 社区)\n")
            for b in bridges[:10]:
                icon = TYPE_ICONS.get(b["type"], "❓")
                label = NODE_TYPES.get(b["type"], b["type"])
                lines.append(
                    f"- {icon} **{b['name']}** ({label}) — "
                    f"连接 {b['communities']} 个社区, degree={b['degree']}"
                )
            lines.append("")
    except Exception as e:
        lines.append(f"⚠️ 社区检测失败: {e}\n")

    # ── 4. 跨章连通性 ──
    lines.append("\n## 4. 跨章连通性\n")
    conn = cross_chapter_connectivity(G, nodes)
    if conn["cross_chapter_edges"]:
        lines.append("章节间的知识连接强度：\n")
        for (ch1, ch2), count in conn["cross_chapter_edges"][:15]:
            lines.append(f"- {ch1} ↔ {ch2}: {count} 条连接")
        lines.append(f"\n总计 {conn['total_cross_chapter']} 对跨章连接, "
                     f"{conn['total_cross_chapter_edges']} 条边")
    else:
        lines.append("⚠️ 未发现跨章连接 — 各章知识缺乏交叉引用")

    # ── 5. 行动建议 ──
    lines.append("\n## 5. 行动建议\n")
    suggestions = []
    if isolated:
        suggestions.append(
            f"- **补充交叉引用**: {len(isolated)} 个孤立节点需要建立 "
            "[[wikilink]] 连接到相关概念/知识点"
        )
    if sparse:
        suggestions.append(
            f"- **加强社区内部连接**: {len(sparse)} 个稀疏社区 "
            "需要在 `## 相关概念` / `## 相关实体` 节补充连接"
        )
    if conn.get("total_cross_chapter_edges", 0) < 5:
        suggestions.append(
            "- **增加跨章引用**: 章节间知识连接偏少，建议在概念文件中添加 "
            "指向其他章节的 `## 相关章节` 节"
        )
    if not suggestions:
        suggestions.append("- ✅ 未发现明显问题，知识网络健康")

    lines.extend(suggestions)

    return "\n".join(lines)


def main():
    import argparse

    p = argparse.ArgumentParser(description="pipeline_insights — 知识图谱洞察")
    sp = p.add_subparsers(dest="cmd")

    # report
    rp = sp.add_parser("report", help="生成完整洞察报告")
    rp.add_argument("-w", "--wiki-root", required=True)
    rp.add_argument("--book-id", required=True)
    rp.add_argument("-o", "--output", help="输出文件路径 (默认 stdout)")

    # gaps
    gp = sp.add_parser("gaps", help="仅输出知识缺口")
    gp.add_argument("-w", "--wiki-root", required=True)
    gp.add_argument("--book-id", required=True)

    # communities
    cp = sp.add_parser("communities", help="仅输出社区分析")
    cp.add_argument("-w", "--wiki-root", required=True)
    cp.add_argument("--book-id", required=True)

    # consistency (v47.0: 跨章一致性校验)
    cs = sp.add_parser("consistency", help="跨章一致性校验")
    cs.add_argument("-w", "--wiki-root", required=True)
    cs.add_argument("--book-id", default=None, help="可选：限制在指定书籍")
    cs.add_argument("-o", "--output", help="输出 JSON 文件路径（默认 .dag/cross_chapter_consistency.json）")

    args = p.parse_args()

    if args.cmd == "report":
        report = generate_insights_report(args.wiki_root, args.book_id)
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(report)
            log.info(f"报告已保存到 {args.output}")
        else:
            print(report)

    elif args.cmd == "gaps":
        data = _load_graph(args.wiki_root, args.book_id)
        if not data:
            print("⚠️ 无法加载图谱数据")
            return
        G = _build_networkx(data["nodes"], data["edges"])
        isolated = detect_isolated_nodes(G, args.book_id)
        print(f"孤立节点: {len(isolated)}")
        for item in isolated[:20]:
            print(f"  [{item['type']}] {item['name']} (degree={item['degree']})")

    elif args.cmd == "communities":
        data = _load_graph(args.wiki_root, args.book_id)
        if not data:
            print("⚠️ 无法加载图谱数据")
            return
        G = _build_networkx(data["nodes"], data["edges"])
        try:
            communities = run_louvain(G)
            print(f"发现 {len(communities)} 个社区:")
            for i, comm in enumerate(communities):
                members = [
                    G.nodes[nid].get("name", nid) for nid in comm
                ]
                print(f"  社区#{i}: {len(comm)}节点 — {', '.join(members[:5])}")
            sparse = detect_sparse_communities(G, communities)
            if sparse:
                print(f"\n稀疏社区: {len(sparse)}")
                for s in sparse:
                    print(f"  社区#{s['id']}: cohesion={s['cohesion']}")
        except Exception as e:
            print(f"⚠️ 社区检测失败: {e}")

    elif args.cmd == "consistency":
        # v47.0: 跨章一致性校验
        import json

        result = check_cross_chapter_consistency(args.wiki_root, args.book_id)
        output = args.output
        if not output:
            output = os.path.join(args.wiki_root, ".dag", "cross_chapter_consistency.json")
        else:
            os.makedirs(os.path.dirname(os.path.abspath(output)), exist_ok=True)

        summary = result.get("summary", {})
        print(f"\n📋 跨章一致性校验完成")
        print(f"   扫描概念: {result.get('total_concepts', 0)} 个")
        print(f"   同名冲突: {summary.get('same_name_conflict_count', 0)} 组")
        print(f"   近名冲突: {summary.get('similar_name_conflict_count', 0)} 组")
        if summary.get("severity_breakdown"):
            print(f"   问题分类:")
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
                    print(f"      {labels.get(k, k)}: {v} 项")
        print(f"   报告: {output}")


if __name__ == "__main__":
    main()
