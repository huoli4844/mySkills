"""graph_analytics.py — 知识图谱分析与数据获取 (v42.0 从 generate_index_data.py 拆分)

包含:
  - _get_enriched_nodes(): 拓扑增强字段查询
  - _build_graph_section(): 10大分析模块（连接性/知识链/图质量/排名/Mermaid/
    章节分布/学习路径/错题归因/Bloom路径/待修复项）
  - _get_kg_data(): KB Graph 数据读取
"""

import itertools
import os
import sys

from log_utils import get_logger

log = get_logger(__name__)

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)


def _get_enriched_nodes(kg, book_id, kg_data):
    """从 kb_graph 获取每个节点的拓扑增强字段：
    - degree: 度中心性数值
    - downstream_count: 下游类型节点数
    - upstream_count: 上游类型节点数
    - in_scene: 是否被Scene引用（知识链完整度）
    - quality_flag: 空心概念/孤儿KE 标记
    """
    if not kg_data:
        return None
    try:
        prefix = f"{book_id}/"
        enriched = {}
        with kg._conn() as c:
            # 所有非索引节点
            rows = c.execute(
                """
                SELECT n.id, n.type, n.name,
                    (SELECT COUNT(*) FROM edges WHERE source_id=n.id) AS out_d,
                    (SELECT COUNT(*) FROM edges WHERE target_id=n.id) AS in_d
                FROM nodes n WHERE n.id LIKE ? AND n.type NOT IN ('index')
            """,
                (prefix + "%",),
            ).fetchall()
            for nid, _ntype, _name, out_d, in_d in rows:
                # 下游计数：该节点作为source指向更具体的类型
                downstream = c.execute(
                    """
                    SELECT COUNT(DISTINCT e.target_id) FROM edges e
                    JOIN nodes nt ON e.target_id = nt.id
                    WHERE e.source_id=?
                """,
                    (nid,),
                ).fetchone()[0]
                # 上游计数：该节点作为target来自更抽象的类型
                upstream = c.execute(
                    """
                    SELECT COUNT(DISTINCT e.source_id) FROM edges e
                    JOIN nodes ns ON e.source_id = ns.id
                    WHERE e.target_id=?
                    AND ns.type NOT IN ('exercise','solution','index')
                """,
                    (nid,),
                ).fetchone()[0]
                # 是否在Scene中被引用
                in_scene = (
                    c.execute(
                        """
                    SELECT COUNT(*) FROM edges e
                    JOIN nodes nt ON e.target_id = nt.id
                    WHERE e.source_id=? AND nt.type='scenario'
                """,
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
        return enriched
    except Exception as e:
        log.warning(f"图谱分析错误: {e}")
        return None


def _build_graph_section(kg, book_id, kg_stats, like_pattern=None):
    """v35.0: 构建图驱动的结构化内容字典

    返回 dict: {
        chain_connectivity, node_connectivity, graph_quality,
        top_nodes, mindmap, chapter_distribution, learning_path
    }
    """
    if like_pattern is None:
        like_pattern = f"%/{book_id}/%"

    result = {
        "chain_connectivity": "（图谱未构建）",
        "node_connectivity": "",
        "graph_quality": "",
        "top_nodes": "",
        "mindmap": "",
        "chapter_distribution": "",
        "learning_path": "（待补充）",
        "error_attribution": "（暂无习题数据，无法归因分析）",
        "learning_path_v2": "（待补充）",
        "cross_book_conflicts": "（暂无跨书数据）",
        "knowledge_blindspots": "（待补充）",
        "todo_items": "（无待修复项）",
    }
    try:
        _enriched = _get_enriched_nodes(kg, book_id, kg_stats)
        quality = kg.check_graph_quality()

        # ── 1. 节点连接性统计 ──
        node_conn = ""
        with kg._conn() as c:
            type_stats = c.execute(
                """
                SELECT n.type, COUNT(*),
                       ROUND(AVG((SELECT COUNT(*) FROM edges WHERE source_id=n.id)), 1),
                       ROUND(AVG((SELECT COUNT(*) FROM edges WHERE target_id=n.id)), 1)
                FROM nodes n WHERE n.id LIKE ? AND n.type NOT IN ('index','exercise','solution')
                GROUP BY n.type ORDER BY COUNT(*) DESC
            """,
                (f"{like_pattern}%",),
            ).fetchall()
            if type_stats:
                node_conn = "| 节点类型 | 数量 | 平均出度 | 平均入度 |\n|:--------|:---:|:-------:|:-------:|\n"
                for t, cnt, avg_o, avg_i in type_stats:
                    node_conn += f"| {t} | {cnt} | {avg_o} | {avg_i} |\n"

        with kg._conn() as c:
            total = c.execute(
                "SELECT COUNT(*) FROM nodes WHERE id LIKE ? AND type NOT IN ('index','exercise','solution')",
                (f"{like_pattern}%",),
            ).fetchone()[0]
            connected = c.execute(
                """
                SELECT COUNT(DISTINCT n.id) FROM nodes n
                WHERE n.id LIKE ? AND n.type NOT IN ('index','exercise','solution')
                AND EXISTS (SELECT 1 FROM edges e WHERE e.source_id=n.id OR e.target_id=n.id)
            """,
                (f"{like_pattern}%",),
            ).fetchone()[0]
            if total > 0:
                conn_rate = round(connected / total * 100, 1)
                node_conn += f"\n> **连通率**: {connected}/{total} 节点 ({conn_rate}%) 有至少一条边连接\n"
        result["node_connectivity"] = node_conn

        # ── 2. 知识链连通率 ──
        chain_text = ""
        with kg._conn() as c:
            chain_types = ["concept", "knowledge-element", "knowledge", "skill", "scenario"]
            chain_text = "| 链路 | 总数 | 连通数 | 连通率 |\n|:----|:---:|:-----:|:-----:|\n"
            for src_t, tgt_t in itertools.pairwise(chain_types):
                src_cnt = c.execute(
                    "SELECT COUNT(*) FROM nodes WHERE type=? AND id LIKE ?", (src_t, f"{like_pattern}%")
                ).fetchone()[0]
                connected_cnt = c.execute(
                    """
                    SELECT COUNT(DISTINCT n.id) FROM nodes n
                    WHERE n.type=? AND n.id LIKE ?
                    AND EXISTS (SELECT 1 FROM edges e JOIN nodes nt ON e.target_id=nt.id
                                WHERE (e.source_id=n.id OR e.target_id=n.id) AND nt.type=?
                                UNION ALL
                                SELECT 1 FROM edges e JOIN nodes ns ON e.source_id=ns.id
                                WHERE (e.source_id=n.id OR e.target_id=n.id) AND ns.type=?)
                """,
                    (src_t, f"{like_pattern}%", tgt_t, tgt_t),
                ).fetchone()[0]
                rate = round(connected_cnt / src_cnt * 100, 1) if src_cnt else 0
                bar = "█" * int(rate / 10) + "░" * (10 - int(rate / 10)) if rate > 0 else "░" * 10
                chain_text += f"| {src_t}→{tgt_t} | {src_cnt} | {connected_cnt} | {bar} {rate}% |\n"
        result["chain_connectivity"] = chain_text

        # ── 3. 图质量摘要 ──
        s = quality["summary"]
        qual_text = "| 严重度 | 数量 | 含义 |\n|:------|:---:|:-----|\n"
        qual_text += f"| 🔴 Critical | {s['critical']} | 空心概念/孤儿KE，需立即修复 |\n"
        qual_text += f"| ⚠️ Warning | {s['warning']} | 路径断裂/孤立节点/过载节点 |\n"
        qual_text += f"| ℹ️ Info | {s['info']} | 循环引用/核心节点参考 |\n"
        hollow = [i for i in quality["issues"] if i["category"] == "空心概念"]
        if hollow:
            qual_text += "\n**空心概念（无KE引用）**：\n"
            max_show = 8  # v43.15: 截断长列表
            for h in hollow[:max_show]:
                name = h["message"].split("「")[1].split("」")[0]
                fix = h.get("fix_hint", "补充引用的知识要素").split("或")[0]
                qual_text += f"- {name} → {fix}\n"
            if len(hollow) > max_show:
                qual_text += f"  ... 还有 {len(hollow) - max_show} 个空心概念，\n"
                qual_text += "  建议：在核心概念文件中添加 [[知识要素名]] wikilink\n"
        orphan_kes = [i for i in quality["issues"] if i["category"] == "孤儿KE"]
        if orphan_kes:
            qual_text += "\n**孤儿KE（无KP使用）**：\n"
            max_show_ke = 10  # v43.15: 截断长列表
            for o in orphan_kes[:max_show_ke]:
                name = o["message"].split("「")[1].split("」")[0]
                qual_text += f"- {name}\n"
            if len(orphan_kes) > max_show_ke:
                qual_text += f"  ... 还有 {len(orphan_kes) - max_show_ke} 个孤儿KE，\n"
                qual_text += "  建议：知识点文件中用 [[KE名]] 引用这些知识要素\n"
        result["graph_quality"] = qual_text

        # ── 4. 核心知识节点排名 ──
        top = quality.get("top_nodes", [])
        if top:
            top_text = "| 排名 | 节点 | 类型 | 入度 | 出度 | 总度 |\n|:---:|:----|:----|:---:|:---:|:---:|\n"
            for i, t in enumerate(top[:10], 1):
                deg = t["in_degree"] + t["out_degree"]
                top_text += f"| {i} | {t['name']} | {t['type']} | {t['in_degree']} | {t['out_degree']} | {deg} |\n"
            result["top_nodes"] = top_text

        # ── 5. Mermaid 全景图（v43.15: 包含所有节点类型）──
        try:
            if total > 0:
                type_icons = {
                    "concept": "📘", "knowledge-element": "📐",
                    "knowledge": "🎯", "skill": "🔧",
                    "scenario": "🏗", "entity": "📦",
                }
                mermaid_lines = ["graph TB"]
                all_nodes = {}  # name → (safe_name, icon)

                def _mermaid_safe(name):
                    """将名称转为 Mermaid 安全标识符，替换所有非字母/数字/CJK字符"""
                    safe = ""
                    for c in name:
                        if c.isalnum() or '\u4e00' <= c <= '\u9fff' or '\u3400' <= c <= '\u4dbf' or c == '_':
                            safe += c
                        elif c in ' \t-':
                            safe += '_'
                    return safe or "node"

                with kg._conn() as c2:
                    # v43.15: 先查高连接度边（TOP 50），再只为有边节点画图
                    edge_rows = c2.execute(
                        """SELECT n1.name, n2.name FROM edges e
                        JOIN nodes n1 ON e.source_id=n1.id
                        JOIN nodes n2 ON e.target_id=n2.id
                        WHERE e.source_id LIKE ?
                        AND n1.type NOT IN ('index', 'solution', 'exercise')
                        AND n2.type NOT IN ('index', 'solution', 'exercise')
                        ORDER BY (SELECT COUNT(*) FROM edges e2
                                  WHERE e2.source_id=e.source_id OR e2.target_id=e.target_id) DESC
                        LIMIT 50""",
                        (f"{like_pattern}%",),
                    ).fetchall()

                    # 收集有边的节点名
                    connected_names = set()
                    for src, tgt in edge_rows:
                        connected_names.add(src)
                        connected_names.add(tgt)

                    # 只为有边的节点画图
                    for ntype, icon in type_icons.items():
                        rows = c2.execute(
                            "SELECT name FROM nodes WHERE type=? AND id LIKE ?",
                            (ntype, f"{like_pattern}%"),
                        ).fetchall()
                        for (name,) in rows:
                            if name not in connected_names:
                                continue
                            safe = _mermaid_safe(name)
                            label = name.replace('"', "'")
                            all_nodes[name] = (safe, icon)
                            mermaid_lines.append(f'    {safe}["{label}"]')
                    drawn_edges = set()
                    for src, tgt in edge_rows:
                        if src in all_nodes and tgt in all_nodes:
                            edge_key = (src, tgt)
                            if edge_key not in drawn_edges:
                                drawn_edges.add(edge_key)
                                ss = all_nodes[src][0]
                                ts = all_nodes[tgt][0]
                                mermaid_lines.append(f"    {ss} -.-> {ts}")

                result["mindmap"] = "\n".join(mermaid_lines)
        except Exception as e:
            log.debug(f"图谱分析暂跳过: {e}")

        # ── 6. 按章节分布 ──
        with kg._conn() as c:
            chapter_nodes = c.execute(
                """
                SELECT n.chapter_num, n.type, COUNT(*)
                FROM nodes n WHERE n.id LIKE ? AND n.type NOT IN ('index','exercise','solution')
                AND n.chapter_num != ''
                GROUP BY n.chapter_num, n.type ORDER BY n.chapter_num
            """,
                (f"{like_pattern}%",),
            ).fetchall()
            if chapter_nodes:
                by_ch = {}
                for ch, nt, cnt in chapter_nodes:
                    if ch not in by_ch:
                        by_ch[ch] = {}
                    by_ch[ch][nt] = cnt
                ch_text = "| 章节 | 概念 | KE | KP | SP | Scene |\n|:----|:---:|:--:|:--:|:--:|:----:|\n"
                for ch in sorted(by_ch.keys()):
                    d = by_ch[ch]
                    ch_text += f"| 第{ch}章 | {d.get('concept',0)} | {d.get('knowledge-element',0)} | {d.get('knowledge',0)} | {d.get('skill',0)} | {d.get('scenario',0)} |\n"
                result["chapter_distribution"] = ch_text

        # ── 7. 推荐学习路径 ──
        if top:
            paths = []
            for t_node in top[:3]:
                try:
                    trace_result = kg.trace(t_node["name"])
                    if trace_result.get("levels"):
                        path_nodes = []
                        for lvl in trace_result["levels"][:5]:
                            seen_type = set()
                            for n in lvl["nodes"]:
                                if n["type"] not in seen_type and len(path_nodes) < 8:
                                    path_nodes.append(f"[[{n['name']}]]")
                                    seen_type.add(n["type"])
                        if path_nodes:
                            paths.append(f"- 🚀 从「{t_node['name']}」出发: {' → '.join(path_nodes)}")
                except Exception as e:
                    log.debug(f"路径分析跳过: {e}")
            if paths:
                result["learning_path"] = "\n".join(paths)

        # ── 8. 错题归因分析（v35.5）──
        try:
            with kg._conn() as c:
                exercises = c.execute(
                    """
                    SELECT n.name, n.chapter_num FROM nodes n
                    WHERE n.type='exercise' AND n.id LIKE ?
                """,
                    (f"{like_pattern}%",),
                ).fetchall()
                if exercises:
                    attr_lines = []
                    for ex_name, ex_ch in exercises[:10]:
                        # 查找与习题关联的概念
                        related = c.execute(
                            """
                            SELECT n2.name, n2.type FROM edges e
                            JOIN nodes n1 ON e.source_id=n1.id
                            JOIN nodes n2 ON e.target_id=n2.id
                            WHERE n1.name=? AND n2.type IN ('concept','knowledge')
                            LIMIT 3
                        """,
                            (ex_name,),
                        ).fetchall()
                        if related:
                            concepts = [f"[[{r[0]}]]" for r in related if r[1] == "concept"]
                            kps = [f"[[{r[0]}]]" for r in related if r[1] == "knowledge"]
                            if concepts or kps:
                                attr_lines.append(
                                    f"- **{ex_name}**（第{ex_ch}章）↔ " f"{', '.join(concepts[:2] or kps[:2])}"
                                )
                    if attr_lines:
                        result["error_attribution"] = "\n".join(attr_lines)
                    else:
                        result["error_attribution"] = "（习题已生成但未与概念/知识点建立图谱连接）"
                else:
                    result["error_attribution"] = "（本书暂无习题）"
        except Exception as e:
            log.debug(f"图谱分析暂跳过: {e}")

        # ── 9. 学习路径v2：基于 Bloom 层级的动态学习路径算法（v36.0）──
        try:
            with kg._conn() as c:
                # 查询所有 KR 节点及其 Bloom 层级、难度
                kps = c.execute(
                    """
                    SELECT n.name, n.chapter_num, n.bloom_level, n.difficulty
                    FROM nodes n
                    WHERE n.type='knowledge' AND n.id LIKE ?
                    ORDER BY n.chapter_num
                """,
                    (f"{like_pattern}%",),
                ).fetchall()

                # 查询所有 SP 节点及其 Bloom 层级
                sps = c.execute(
                    """
                    SELECT n.name, n.chapter_num, n.bloom_level, n.difficulty
                    FROM nodes n
                    WHERE n.type='skill' AND n.id LIKE ?
                    ORDER BY n.chapter_num
                """,
                    (f"{like_pattern}%",),
                ).fetchall()

                # 查询前置依赖边（PREREQUISITE_OF）
                prereq_edges = c.execute(
                    """
                    SELECT e.source_id, e.target_id
                    FROM edges e
                    WHERE e.rel_type='PREREQUISITE_OF'
                    AND (e.source_id LIKE ? OR e.target_id LIKE ?)
                """,
                    (
                        f"{like_pattern}%",
                        f"{like_pattern}%",
                    ),
                ).fetchall()

                if kps:
                    # ── 9a. Bloom 层级序列表 ──
                    bloom_order = {"记忆": 0, "理解": 1, "应用": 2, "分析": 3, "评价": 4, "创造": 5}
                    bloom_emoji = {"记忆": "📖", "理解": "📝", "应用": "🔧", "分析": "🔍", "评价": "⭐", "创造": "💡"}

                    # 空值默认"理解"
                    def _bloom_score(bl):
                        return bloom_order.get(bl, 1)

                    # 按章节分组，记录 Bloom 层级
                    by_chapter = {}  # ch → [(kp_name, bloom_level, difficulty)]
                    for row in kps:
                        kp_name, ch, bl, diff = row[0], str(row[1]), (row[2] or ""), (row[3] or "")
                        if ch not in by_chapter:
                            by_chapter[ch] = []
                        by_chapter[ch].append((kp_name, bl, diff))

                    path_lines = []
                    path_lines.append("**动态学习路径（基于 Bloom 认知层级 + 前置依赖）**\n")
                    path_lines.append("")
                    path_lines.append("> 算法：按章内 Bloom 层级递进排序（记忆→理解→应用→分析→评价→创造），")
                    path_lines.append("> 跨章考虑 PREREQUISITE_OF 前置依赖关系，自动推荐学习轨道。\n")

                    # ── Bloom 分布统计（全章）──
                    bloom_total_counts = {"记忆": 0, "理解": 0, "应用": 0, "分析": 0, "评价": 0, "创造": 0}
                    for row in kps:
                        bl = row[2] or ""
                        if bl in bloom_total_counts:
                            bloom_total_counts[bl] += 1
                    # 过滤存在的层级
                    active_blooms = {k: v for k, v in bloom_total_counts.items() if v > 0}
                    if active_blooms:
                        dist_line = "| Bloom 层级 | 知识点数 | 占比 |\n|:-----------|:--------:|:---:|\n"
                        total_kps = sum(active_blooms.values())
                        for bl in ["记忆", "理解", "应用", "分析", "评价", "创造"]:
                            cnt = active_blooms.get(bl, 0)
                            if cnt > 0:
                                pct = round(cnt / total_kps * 100, 1)
                                bar = "█" * int(pct / 10) + "░" * (10 - int(pct / 10))
                                dist_line += f"| {bloom_emoji.get(bl, '')} {bl} | {cnt} | {bar} {pct}% |\n"
                        path_lines.append("### Bloom 层级分布\n")
                        path_lines.append(dist_line)
                        path_lines.append(f"> 💡 共有 {total_kps} 个知识点，覆盖 {len(active_blooms)} 个 Bloom 层级。")
                        path_lines.append("  若缺少低层级（记忆/理解），建议先阅读核心概念页补充基础。\n")

                    # ── 构建前置依赖图谱（name→[prerequisite_names]）──
                    name_to_prereqs = {}  # name → list of prerequisite names
                    prereq_name_pairs = []
                    for src_id, tgt_id in prereq_edges:
                        # 从 id 提取 name（id 格式: book_id/40_知识点/xxx）
                        src_name = src_id.rsplit("/", 1)[-1] if "/" in src_id else src_id
                        tgt_name = tgt_id.rsplit("/", 1)[-1] if "/" in tgt_id else tgt_id
                        prereq_name_pairs.append((src_name, tgt_name))
                        if src_name not in name_to_prereqs:
                            name_to_prereqs[src_name] = []
                        name_to_prereqs[src_name].append(tgt_name)

                    # ── 按章 Bloom 渐进路径（v43.15: Mermaid 思维导图）──
                    path_lines.append("### 按章推荐路径（Bloom 渐进思维导图）\n")
                    mindmap_lines = ["```mermaid", "mindmap", "  📚 全书知识体系"]
                    for ch in sorted(by_chapter.keys()):
                        items = by_chapter[ch]
                        ch_label = f"第{ch}章"
                        mindmap_lines.append(f"    {ch_label}")
                        sorted_items = sorted(items, key=lambda x: _bloom_score(x[1]) if len(x) >= 2 else 1)
                        for item in sorted_items:
                            kp_name = item[0] if len(item) >= 1 else "?"
                            mindmap_lines.append(f"      {kp_name}")
                    mindmap_lines.append("```")
                    path_lines.append("\n".join(mindmap_lines))
                    path_lines.append("\n> 思维导图展示各章知识点按 Bloom 层级递进的排列关系\n")

                    # ── 前置依赖链分析 ──
                    if prereq_name_pairs:
                        path_lines.append("### 跨章前置依赖链\n")
                        path_lines.append("> 以下知识点有明确的前置依赖（PREREQUISITE_OF）关系，")
                        path_lines.append("> 建议按依赖顺序学习（A ← B 表示「B 前置依赖 A」，应先学 A）：\n")
                        # 构建依赖图谱：A → [B, C] 表示 B 和 C 依赖于 A
                        dep_graph = {}
                        for src, tgt in prereq_name_pairs:
                            if tgt not in dep_graph:
                                dep_graph[tgt] = []
                            dep_graph[tgt].append(src)
                        # 按依赖数量排序展示
                        sorted_deps = sorted(dep_graph.items(), key=lambda x: len(x[1]), reverse=True)
                        for target_name, prereq_names in sorted_deps[:5]:
                            prereq_links = [f"[[{p}]]" for p in prereq_names[:3]]
                            path_lines.append(f"- **[[{target_name}]]** 依赖: {' + '.join(prereq_links)}")
                        if len(sorted_deps) > 5:
                            path_lines.append(f"  ... 还有 {len(sorted_deps) - 5} 条依赖关系")
                        path_lines.append("")

                    # ── 推荐学习轨道 ──
                    path_lines.append("### 推荐学习轨道\n")
                    path_lines.append("根据 Bloom 层级组合和目标，推荐以下学习轨道：\n")

                    # v43.15: 学习轨道 Mermaid 流程图
                    track_lines = ["```mermaid", "graph LR"]
                    track_lines.append('    Start[开始学习] --> Basic[基础夯实]')
                    track_lines.append('    Basic --> Apply[应用实践]')
                    track_lines.append('    Apply --> Deep[深度学习]')
                    if sps:
                        track_lines.append('    Apply --> Skill[技能练习]')
                    track_lines.append('    Deep --> Create[创造创新]')
                    track_lines.append("```")
                    path_lines.append("\n".join(track_lines))
                    path_lines.append("")

                    # 轨道1: 基础夯实（仅记忆+理解）
                    basic_kps = [f"[[{row[0]}]]" for row in kps if row[2] in ("记忆", "理解")]
                    if basic_kps:
                        path_lines.append("1. 📖 **基础夯实轨道**（记忆→理解）")
                        path_lines.append("   目标：掌握核心概念和基本原理")
                        path_lines.append(
                            f"   路径：{' → '.join(basic_kps[:5])}" + (" ..." if len(basic_kps) > 5 else "")
                        )
                        path_lines.append("")

                    # 轨道2: 应用实践（应用+分析）
                    apply_kps = [f"[[{row[0]}]]" for row in kps if row[2] in ("应用", "分析")]
                    if apply_kps:
                        path_lines.append("2. 🔧 **应用实践轨道**（理解→应用→分析）")
                        path_lines.append("   目标：将知识转化为实际分析和解决问题的能力")
                        path_lines.append(
                            f"   路径：{' → '.join(apply_kps[:5])}" + (" ..." if len(apply_kps) > 5 else "")
                        )
                        path_lines.append("")

                    # 轨道3: 深度学习（全层级）
                    advanced_kps = [f"[[{row[0]}]]" for row in kps if row[2] in ("评价", "创造")]
                    if advanced_kps:
                        path_lines.append("3. 💡 **深度学习轨道**（涵盖评价/创造层级）")
                        path_lines.append("   目标：能够评价和创造新的解决方案")
                        kp_list = (
                            basic_kps[:2] + apply_kps[:2] + advanced_kps[:2]
                            if basic_kps and apply_kps
                            else advanced_kps[:4]
                        )
                        path_lines.append(f"   路径：{' → '.join(kp_list)}")
                        path_lines.append("")

                    # 轨道4: 技能导向（KP→SP 映射）
                    if sps:
                        sp_bloom_counts = {}
                        for sp_name, _ch, bl, _ in sps:
                            bl = bl or ""
                            if bl not in sp_bloom_counts:
                                sp_bloom_counts[bl] = []
                            sp_bloom_counts[bl].append(sp_name)
                        path_lines.append("4. 🛠️ **技能导向轨道**（知识点→技能点）")
                        path_lines.append(f"   共有 {len(sps)} 个技能点，涵盖 {len(sp_bloom_counts)} 个 Bloom 层级。")
                        path_lines.append("   对照 [[技能点索引]] 选择与当前 KP 层级匹配的技能进行练习。")
                        path_lines.append("")

                    # 最终建议
                    path_lines.append("---")
                    path_lines.append(
                        f"> 📊 全书共 {len(kps)} 个知识点，{len(sps)} 个技能点，{len(prereq_edges)} 条前置依赖。"
                    )
                    path_lines.append("> 推荐学完每章知识点后，立即练习对应技能点以巩固学习效果。")

                    result["learning_path_v2"] = "\n".join(path_lines)

        except Exception as e:
            log.warning(f"学习路径生成失败: {e}")

            result["learning_path_v2"] = f"（学习路径算法异常: {e}）"

        # ── 10. 待修复项汇总（v35.5）──
        hollow = [i for i in quality["issues"] if i["category"] == "空心概念"]
        orphan = [i for i in quality["issues"] if i["category"] == "孤儿KE"]
        todo = []
        if hollow:
            names = [h["message"].split("「")[1].split("」")[0] for h in hollow[:5]]
            todo.append(f"- 🔴 空心概念（{len(hollow)}个）: {', '.join(names)} → 需补充KE引用")
        if orphan:
            names_o = [o["message"].split("「")[1].split("」")[0] for o in orphan[:5]]
            todo.append(f"- 🟡 孤儿KE（{len(orphan)}个）: {', '.join(names_o)} → 需关联到KP")
        if s["critical"] > 0 or s["warning"] > 0:
            if todo:
                result["todo_items"] = "\n".join(todo)
            else:
                result["todo_items"] = f"（{s['critical']}条严重问题，{s['warning']}条警告，详见图谱质量表）"

    except Exception as e:
        result["chain_connectivity"] = f"（图驱动内容生成异常: {e}）"
    return result


def _get_kg_data(wiki_root, book_id):
    """尝试从 kb_graph 读取增强数据，失败时返回 None"""
    try:
        from kb_graph import KGraph

        kg = KGraph(wiki_root)
        if not os.path.exists(kg.db_path):
            return None
        with kg._conn() as c:
            prefix = book_id
            # v43.13: 节点 ID 格式为 "领域/书籍/类型/名称"，需用 LIKE 匹配中间段
            rows = c.execute(
                """
                SELECT n.id, n.type, n.name, n.chapter_num, n.confidence,
                       (SELECT COUNT(*) FROM edges WHERE source_id = n.id) +
                       (SELECT COUNT(*) FROM edges WHERE target_id = n.id) AS edge_count
                FROM nodes n
                WHERE n.id LIKE '%/' || ? || '/%'
                AND n.type NOT IN ('index')
            """,
                (prefix,),
            ).fetchall()
            if not rows:
                return None
            result = {}
            for r in rows:
                result[r[0]] = {
                    "id": r[0],
                    "type": r[1],
                    "name": r[2],
                    "chapter_num": r[3] or "0",
                    "confidence": r[4],
                    "edge_count": r[5],
                }
            # 按章节分组的统计
            stats = {
                "total": len(result),
                "by_chapter": {},
                "confidence_dist": {},
                "orphans": sum(1 for v in result.values() if v["edge_count"] == 0),
                "avg_edges": round(sum(v["edge_count"] for v in result.values()) / max(len(result), 1), 1),
            }
            for v in result.values():
                ch = v["chapter_num"]
                stats["by_chapter"][ch] = stats["by_chapter"].get(ch, 0) + 1
                conf_key = str(v["confidence"])
                stats["confidence_dist"][conf_key] = stats["confidence_dist"].get(conf_key, 0) + 1
            return {"nodes": result, "stats": stats}
    except Exception as e:
        log.warning(f"图谱分析错误: {e}")
        return None
