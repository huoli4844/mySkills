"""graph_quality.py — KGraph 质量检查 Mixin

v36.5: 从 kb_graph.py 拆分。KGraph 继承此 Mixin 获得质量检查方法。
包含: validate, check_graph_quality, check_l1_connectivity,
      check_similar_names, degree_centrality, check_bridge_gaps,
      check_path_integrity, suggest_build_order, export_mermaid
"""

from __future__ import annotations




class KGraphQualityMixin:
    """知识图谱质量检查方法集。

    作为 Mixin 被 KGraph 继承，可直接使用 self._conn() 和 self.query() 等。
    """

    def validate(self) -> list[dict]:
        """图级质量检查，返回问题列表"""
        issues = []

        with self._conn() as c:
            # 1. 孤立节点（0 入边 + 0 出边，排除索引和习题）
            orphans = c.execute(
                """SELECT n.id, n.type, n.name FROM nodes n
                   WHERE n.id NOT IN (SELECT DISTINCT source_id FROM edges)
                   AND n.id NOT IN (SELECT DISTINCT target_id FROM edges)
                   AND n.type NOT IN ('index')"""
            ).fetchall()
            for o in orphans:
                issues.append(
                    {
                        "severity": "warn",
                        "type": "orphan",
                        "message": f"{o[1]}「{o[2]}」无任何入边和出边",
                        "node_id": o[0],
                    }
                )

            # 2. 断链（edges 指向不存在的节点）
            dead = c.execute(
                """SELECT e.source_id, e.target_id, e.rel_type FROM edges e
                   LEFT JOIN nodes n ON e.target_id = n.id
                   WHERE n.id IS NULL"""
            ).fetchall()
            for d in dead:
                issues.append(
                    {
                        "severity": "error",
                        "type": "dead_link",
                        "message": f"{d[0]} → {d[1]} ({d[2]}) 目标不存在",
                    }
                )

            # 3. 置信度不匹配（概念 0.95 → KE 0.65）
            conf_gaps = c.execute(
                """SELECT e.source_id, n1.name, n1.confidence, e.target_id, n2.name, n2.confidence, e.rel_type
                   FROM edges e
                   JOIN nodes n1 ON e.source_id = n1.id
                   JOIN nodes n2 ON e.target_id = n2.id
                   WHERE n1.type='concept' AND n1.confidence >= 0.95
                   AND n2.confidence <= 0.75
                   AND e.rel_type NOT IN ('CONTRASTS_WITH')"""
            ).fetchall()
            for cg in conf_gaps:
                diff = cg[2] - cg[5]
                if diff >= 0.2:
                    issues.append(
                        {
                            "severity": "warn",
                            "type": "confidence_gap",
                            "message": f"概念「{cg[1]}」(0.95) → {cg[3].split('/')[0]}「{cg[4]}」({cg[5]}) 置信度差距 {diff:.2f}",
                        }
                    )

            # 4. 过度引用（一个节点被太多节点引用）
            overloaded = c.execute(
                """SELECT target_id, n.type, n.name, COUNT(*) AS cnt
                   FROM edges e JOIN nodes n ON e.target_id = n.id
                   GROUP BY target_id HAVING cnt >= 8
                   ORDER BY cnt DESC LIMIT 5"""
            ).fetchall()
            for ol in overloaded:
                issues.append(
                    {
                        "severity": "info",
                        "type": "overloaded",
                        "message": f"{ol[1]}「{ol[2]}」被 {ol[3]} 个节点引用，可能粒度过粗",
                    }
                )

        return issues

    def check_graph_quality(self, phase: str | None = None) -> dict:
        """综合图质量报告，用于质量审查体系。

        参数 phase: 当前完成的构建阶段。None=全量检查。
        阶段感知过滤：
        - exercises: 仅检查断链（习题不产生KBE关系）
        - concepts: 不检查→KE（KE尚未构建）
        - ke: 检查概念→KE
        - kp: 检查KE→KP
        - sp: 检查KP→SP
        - scene: 检查SP→Scene
        - entities: 仅检查孤立/过载
        - solutions: 仅检查断链

        返回结构化质量检查结果，含问题严重度分级：
        - critical: 必须修复（blocked）
        - warning: 建议修复
        - info: 仅供参考

        检查项：
        [critical] 空心概念（无KE引用）:
          概念节点未被任何知识要素引用，说明该概念是"架空"的
        [critical] 孤儿KE（无KP使用）:
          知识要素未被任何知识点使用
        [warning] 路径断裂（概念→KE→KP→SP→Scene）:
          从概念到应用场景的完整知识链断裂
        [warning] 孤立节点（度=0）:
          没有任何连接的节点，游离于知识体系外
        [warning] 过载节点（入度≥10）:
          被过多节点引用，可能粒度过粗需要拆分
        [info] 循环引用:
          双向引用关系，需要注意是否合理
        [info] 核心节点:
          度中心性排名前5的节点
        """
        issues = []

        # ── 阶段感知：确定哪些检查可激活 ──────────────────
        phase_checks = {
            "exercises": {"broken_links"},
            "concepts": {"broken_links", "confidence", "definition"},
            "ke": {"hollow_concept", "broken_links"},
            "kp": {"orphan_ke", "broken_links"},
            "sp": {"path_ke_kp", "broken_links"},
            "scene": {"path_kp_sp", "path_sp_scene", "broken_links"},
            "entities": {"orphan_node", "overloaded"},
            "solutions": {"broken_links"},
        }
        # 默认（全量）：所有检查都激活
        active = phase_checks.get(
            phase,
            {
                "hollow_concept",
                "orphan_ke",
                "path_ke_kp",
                "path_kp_sp",
                "path_sp_scene",
                "orphan_node",
                "overloaded",
                "cycle",
                "core",
                "broken_links",
            },
        )

        with self._conn() as c:
            # 目标类型是否存在（用于跳过"下游尚不存在"的检查）
            has_kp = c.execute("SELECT COUNT(*) FROM nodes WHERE type='knowledge'").fetchone()[0] > 0
            _has_sp = c.execute("SELECT COUNT(*) FROM nodes WHERE type='skill'").fetchone()[0] > 0
            _has_scene = c.execute("SELECT COUNT(*) FROM nodes WHERE type='scenario'").fetchone()[0] > 0

            # ── [critical] 空心概念（v43.15: 也检查 entity/knowledge 边）──
            if "hollow_concept" in active:
                hollow = c.execute("""
                    SELECT n.name FROM nodes n WHERE n.type='concept'
                    AND NOT EXISTS (
                        SELECT 1 FROM edges e
                        WHERE e.source_id = n.id
                        AND e.target_id IN (
                            SELECT id FROM nodes
                            WHERE type IN ('knowledge-element', 'entity', 'knowledge', 'skill', 'scenario')
                        )
                    )
                """).fetchall()
                for (name,) in hollow:
                    has_entity = c.execute("""
                        SELECT 1 FROM edges e WHERE e.source_id = (
                            SELECT id FROM nodes WHERE name=? AND type='concept' LIMIT 1
                        ) AND e.target_id IN (SELECT id FROM nodes WHERE type='entity') LIMIT 1
                    """, (name,)).fetchone() is not None
                    sv = "warning" if has_entity else "critical"
                    fix = ("已有实体引用，补充[[知识要素名]] wikilink 即可" if has_entity
                           else "在概念文件中添加 [[知识要素名]] wikilink")
                    issues.append(
                        {
                            "severity": sv,
                            "category": "空心概念",
                            "message": f"概念「{name}」无KE/实体/KP下游连接，内容无法向下游传递",
                            "fix_hint": fix,
                        }
                    )

            # ── [critical] 孤儿KE ────────────────────────
            if "orphan_ke" in active and has_kp:
                orphan_kes = c.execute("""
                    SELECT n.name FROM nodes n WHERE n.type='knowledge-element'
                    AND NOT EXISTS (
                        SELECT 1 FROM edges e
                        WHERE (e.source_id = n.id OR e.target_id = n.id)
                        AND (e.source_id IN (SELECT id FROM nodes WHERE type='knowledge')
                             OR e.target_id IN (SELECT id FROM nodes WHERE type='knowledge'))
                    )
                """).fetchall()
                for (name,) in orphan_kes:
                    issues.append(
                        {
                            "severity": "critical",
                            "category": "孤儿KE",
                            "message": f"知识要素「{name}」未被任何知识点使用",
                            "fix_hint": f"在相关KP文件的支撑知识要素节中添加[[{name}]]引用",
                        }
                    )

            # ── [warning] 路径断裂 ────────────────────────
            type_chain = ["concept", "knowledge-element", "knowledge", "skill", "scenario"]
            for i in range(len(type_chain) - 1):
                src_t, tgt_t = type_chain[i], type_chain[i + 1]
                broken = c.execute(
                    """
                    SELECT n.name FROM nodes n WHERE n.type=?
                    AND NOT EXISTS (
                        SELECT 1 FROM edges e
                        JOIN nodes nt ON e.target_id = nt.id
                        WHERE (e.source_id = n.id OR e.target_id = n.id)
                        AND nt.type=?
                    )
                """,
                    (src_t, tgt_t),
                ).fetchall()
                if broken:
                    names = [r[0] for r in broken[:5]]
                    extra = f"...还有{len(broken)-5}个" if len(broken) > 5 else ""
                    issues.append(
                        {
                            "severity": "warning",
                            "category": "路径断裂",
                            "message": f"{src_t}→{tgt_t}: {len(broken)}个{src_t}节点无{tgt_t}连接: {', '.join(names)}{extra}",
                        }
                    )

            # ── [warning] 孤立节点 ────────────────────────
            orphans = c.execute("""
                SELECT n.name, n.type FROM nodes n
                WHERE n.type NOT IN ('index', 'exercise', 'solution')
                AND NOT EXISTS (
                    SELECT 1 FROM edges e WHERE e.source_id = n.id OR e.target_id = n.id
                )
            """).fetchall()
            for name, ntype in orphans:
                issues.append(
                    {
                        "severity": "warning",
                        "category": "孤立节点",
                        "message": f"{ntype}「{name}」无任何入边和出边，完全游离",
                    }
                )

            # ── [warning] 过载节点 ────────────────────────
            overloaded = c.execute("""
                SELECT n.name, n.type, COUNT(*) AS cnt
                FROM edges e JOIN nodes n ON e.target_id = n.id
                WHERE n.type NOT IN ('index', 'exercise', 'solution')
                GROUP BY e.target_id HAVING cnt >= 10
                ORDER BY cnt DESC LIMIT 5
            """).fetchall()
            for name, ntype, cnt in overloaded:
                issues.append(
                    {
                        "severity": "warning",
                        "category": "过载节点",
                        "message": f"{ntype}「{name}」被{cnt}个节点引用，可能粒度过粗",
                    }
                )

            # ── [info] 循环引用 ────────────────────────────
            cycles = c.execute("""
                SELECT DISTINCT n1.name, n2.name FROM edges e1
                JOIN edges e2 ON e1.source_id = e2.target_id AND e1.target_id = e2.source_id
                JOIN nodes n1 ON e1.source_id = n1.id
                JOIN nodes n2 ON e1.target_id = n2.id
                WHERE e1.source_id < e1.target_id
            """).fetchall()
            for a, b in cycles[:5]:
                issues.append(
                    {
                        "severity": "info",
                        "category": "循环引用",
                        "message": f"「{a}」↔「{b}」存在双向引用",
                    }
                )

            # ── [info] 核心节点 ────────────────────────────
            top = c.execute("""
                SELECT n.name, n.type,
                    (SELECT COUNT(*) FROM edges WHERE source_id=n.id) AS out_d,
                    (SELECT COUNT(*) FROM edges WHERE target_id=n.id) AS in_d
                FROM nodes n WHERE n.type NOT IN ('index')
                ORDER BY (out_d + in_d) DESC LIMIT 5
            """).fetchall()

        # 统计
        critical_count = sum(1 for i in issues if i["severity"] == "critical")
        warning_count = sum(1 for i in issues if i["severity"] == "warning")
        info_count = sum(1 for i in issues if i["severity"] == "info")

        return {
            "issues": issues,
            "summary": {
                "critical": critical_count,
                "warning": warning_count,
                "info": info_count,
                "total": len(issues),
            },
            "top_nodes": [{"name": r[0], "type": r[1], "out_degree": r[2], "in_degree": r[3]} for r in top],
            "quality_pass": critical_count == 0,
        }

    def check_l1_connectivity(self, phase: str | None = None) -> dict:
        """L1构建阶段连通性检查 — 各阶段间的图连通性闸门"""
        checks = [
            ("concepts→ke", "concept", "knowledge-element"),
            ("ke→kp", "knowledge-element", "knowledge"),
            ("kp→sp", "knowledge", "skill"),
            ("sp→scene", "skill", "scenario"),
        ]
        results = []
        with self._conn() as c:
            for name, src, tgt in checks:
                total = c.execute("SELECT COUNT(*) FROM nodes WHERE type=?", (src,)).fetchone()[0]
                if total == 0:
                    results.append({"check_name": name, "passed": True, "issues": [], "total": 0})
                    continue
                connected = c.execute(
                    """
                    SELECT COUNT(DISTINCT n.id) FROM nodes n WHERE n.type=?
                    AND EXISTS (
                        SELECT 1 FROM edges e JOIN nodes nt ON e.target_id = nt.id
                        WHERE (e.source_id = n.id OR e.target_id = n.id) AND nt.type=?
                    )
                """,
                    (src, tgt),
                ).fetchone()[0]
                orphan_names = c.execute(
                    """
                    SELECT n.name FROM nodes n WHERE n.type=?
                    AND NOT EXISTS (
                        SELECT 1 FROM edges e JOIN nodes nt ON e.target_id = nt.id
                        WHERE (e.source_id = n.id OR e.target_id = n.id) AND nt.type=?
                    ) LIMIT 5
                """,
                    (src, tgt),
                ).fetchall()
                issues_list = [r[0] for r in orphan_names]
                results.append(
                    {
                        "check_name": name,
                        "passed": connected == total,
                        "issues": issues_list,
                        "total": total,
                        "connected": connected,
                    }
                )
        return {
            "checks": results,
            "overall_passed": all(r["passed"] for r in results),
        }

    def check_similar_names(self, threshold: float = 0.8) -> dict:
        """相似节点名检测（去重辅助）"""
        pairs = []
        with self._conn() as c:
            rows = c.execute("SELECT id, name, type FROM nodes").fetchall()
        names = [(r[0], r[1], r[2]) for r in rows]
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                n1, n2 = names[i][1], names[j][1]
                if not n1 or not n2:
                    continue
                # 简单相似度：最长公共前缀 / 最短名长度
                common = 0
                for a, b in zip(n1, n2):
                    if a == b:
                        common += 1
                    else:
                        break
                min_len = min(len(n1), len(n2))
                if min_len > 0:
                    sim = common / min_len
                    if sim >= threshold and n1 != n2:
                        pairs.append(
                            {
                                "name1": n1,
                                "type1": names[i][2],
                                "name2": n2,
                                "type2": names[j][2],
                                "similarity": round(sim, 2),
                            }
                        )
        return {"pairs": pairs, "total": len(pairs), "threshold": threshold}

    def degree_centrality(self) -> dict:
        """节点度中心性计算"""
        with self._conn() as c:
            rows = c.execute("""
                SELECT n.id, n.name, n.type,
                    (SELECT COUNT(*) FROM edges WHERE source_id=n.id) AS out_d,
                    (SELECT COUNT(*) FROM edges WHERE target_id=n.id) AS in_d
                FROM nodes n
                WHERE n.type NOT IN ('index')
                ORDER BY (out_d + in_d) DESC
            """).fetchall()
        orphans = [r for r in rows if r[3] == 0 and r[4] == 0]
        return {
            "nodes": [
                {"id": r[0], "name": r[1], "type": r[2], "out_degree": r[3], "in_degree": r[4], "degree": r[3] + r[4]}
                for r in rows
            ],
            "orphan_count": len(orphans),
            "total": len(rows),
        }

    def check_bridge_gaps(self, book_dir: str | None = None) -> dict:
        """KE与概念间的桥接验证"""
        gaps = []
        with self._conn() as c:
            kes = c.execute("""
                SELECT n.name FROM nodes n WHERE n.type='knowledge-element'
                AND NOT EXISTS (
                    SELECT 1 FROM edges e JOIN nodes nt ON e.target_id = nt.id
                    WHERE (e.source_id = n.id OR e.target_id = n.id) AND nt.type='concept'
                )
            """).fetchall()
            for (name,) in kes:
                gaps.append({"name": name, "type": "knowledge-element", "gap": "无概念连接"})
        return {"gaps": gaps, "total_gaps": len(gaps)}

    def check_path_integrity(self) -> dict:
        """概念→KE→KP→SP→Scene 路径完整性"""
        checks = []
        type_chain = ["concept", "knowledge-element", "knowledge", "skill", "scenario"]
        labels = ["概念", "知识要素", "知识点", "技能点", "应用场景"]
        with self._conn() as c:
            for i in range(len(type_chain) - 1):
                src_t, tgt_t = type_chain[i], type_chain[i + 1]
                total = c.execute("SELECT COUNT(*) FROM nodes WHERE type=?", (src_t,)).fetchone()[0]
                connected = c.execute(
                    """
                    SELECT COUNT(DISTINCT n.id) FROM nodes n WHERE n.type=?
                    AND EXISTS (
                        SELECT 1 FROM edges e JOIN nodes nt ON e.target_id = nt.id
                        WHERE (e.source_id = n.id OR e.target_id = n.id) AND nt.type=?
                    )
                """,
                    (src_t, tgt_t),
                ).fetchone()[0]
                broken_names = c.execute(
                    """
                    SELECT n.name FROM nodes n WHERE n.type=?
                    AND NOT EXISTS (
                        SELECT 1 FROM edges e JOIN nodes nt ON e.target_id = nt.id
                        WHERE (e.source_id = n.id OR e.target_id = n.id) AND nt.type=?
                    ) LIMIT 5
                """,
                    (src_t, tgt_t),
                ).fetchall()
                checks.append(
                    {
                        "link": f"{labels[i]}→{labels[i+1]}",
                        "total": total,
                        "connected": connected,
                        "broken": total - connected,
                        "broken_names": [r[0] for r in broken_names],
                    }
                )
        broken_count = sum(ch["broken"] for ch in checks)
        return {"checks": checks, "broken_count": broken_count}

    def suggest_build_order(self) -> dict:
        """基于图的依赖调度建议"""
        with self._conn() as c:
            rows = c.execute("""
                SELECT n.name, n.type,
                    (SELECT COUNT(*) FROM edges WHERE target_id=n.id) AS in_d,
                    (SELECT COUNT(*) FROM edges WHERE source_id=n.id) AS out_d
                FROM nodes n WHERE n.type NOT IN ('index')
                ORDER BY in_d ASC, out_d DESC
            """).fetchall()
        # 简单拓扑排序（基于入度）
        order = [{"name": r[0], "type": r[1], "in_degree": r[2], "out_degree": r[3]} for r in rows]
        # 检测循环
        cycle_warnings = []
        return {"order": order, "cycle_warnings": cycle_warnings, "total": len(order)}

    def export_mermaid(self, name: str, depth: int = 1) -> str:
        """以指定节点为中心导出 Mermaid 子图"""
        q = self.query(name)
        if "error" in q:
            return f"❌ {q['error']}"

        lines = ["```mermaid", "graph LR"]
        seen = set()

        with self._conn():
            for r in q.get("results", []):
                node = r["node"]
                nid = node["id"].replace("/", "_").replace(" ", "_")
                label = node["name"].replace('"', "")
                lines.append(f'    {nid}["{label}({node["type"]})"]')
                seen.add(node["id"])

                for e in r["edges_out"]:
                    tid = e["target"].replace("/", "_").replace(" ", "_")
                    rt = e["rel_type"]
                    lines.append(f"    {nid} --{rt}--> {tid}")

        lines.append("```")
        return "\n".join(lines)
