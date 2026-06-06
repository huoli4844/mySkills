"""
kb_graph_query.py — 知识图谱查询方法集

v50.7: 从 kb_graph.py 恢复独立模块（死代码清理时误删除，类被内联到使用点之后导致前向引用错误）。
"""

from log_utils import get_logger

log = get_logger(__name__)


class KGraphQueryMixin:
    """知识图谱查询方法集。

    作为 Mixin 被 KGraph 继承，可直接使用 self._conn()、self.query() 等。
    """

    # ── 查询 ──────────────────────────────────────────────

    def query(self, name: str) -> dict:
        """按节点名查询，返回节点信息 + 一级关联图"""
        with self._conn() as c:
            # 三段式退避：精确 name → 精确 id → 模糊 name
            rows = c.execute("SELECT * FROM nodes WHERE name=? LIMIT 1", (name,)).fetchall()
            if not rows:
                rows = c.execute("SELECT * FROM nodes WHERE id=? LIMIT 1", (name,)).fetchall()
            if not rows:
                rows = c.execute("SELECT * FROM nodes WHERE name LIKE ? LIMIT 10", (f"%{name}%",)).fetchall()
            if not rows:
                return {"error": f"未找到节点: {name}"}

            results = []
            for row in rows:
                node = {
                    "id": row[0],
                    "type": row[1],
                    "name": row[2],
                    "book_id": row[3],
                    "chapter_num": row[4],
                    "confidence": row[5],
                    "source_chapter": row[6],
                    "summary": row[7][:200],
                }
                out_edges = c.execute(
                    "SELECT target_id, rel_type, section FROM edges WHERE source_id=?", (row[0],)
                ).fetchall()
                in_edges = c.execute(
                    "SELECT source_id, rel_type, section FROM edges WHERE target_id=?", (row[0],)
                ).fetchall()
                results.append(
                    {
                        "node": node,
                        "edges_out": [{"target": e[0], "rel_type": e[1], "section": e[2]} for e in out_edges],
                        "edges_in": [{"source": e[0], "rel_type": e[1], "section": e[2]} for e in in_edges],
                    }
                )

            return {"results": results, "total": len(results)}

    # ── 搜索 ──────────────────────────────────────────────

    def search(self, text: str, limit: int = 20) -> dict:
        """搜索所有节点（优先 LIKE 全库搜索，FTS5 兜底不支持中文分词）"""
        with self._conn() as c:
            rows = c.execute(
                """SELECT id, type, name, confidence, source_chapter, summary
                   FROM nodes
                   WHERE name LIKE ? OR summary LIKE ?
                   LIMIT ?""",
                (f"%{text}%", f"%{text}%", limit),
            ).fetchall()

            results = []
            for row in rows:
                results.append(
                    {
                        "id": row[0],
                        "type": row[1],
                        "name": row[2],
                        "confidence": row[3],
                        "source_chapter": row[4],
                        "snippet": row[5][:200],
                    }
                )

            return {"query": text, "results": results, "total": len(results)}

    # ── 影响链追踪 ────────────────────────────────────────

    def trace(self, name: str) -> dict:
        """从指定节点向下游/上游双向追踪影响链"""
        node_result = self.query(name)
        if "error" in node_result:
            return node_result

        with self._conn() as c:
            root_node = c.execute(
                "SELECT id, name, type FROM nodes WHERE name=? OR id LIKE ? OR id=?", (name, f"%/{name}", name)
            ).fetchone()
            if not root_node:
                return {"root": name, "levels": [], "error": f"未找到节点: {name}"}
            root_id = root_node[0]
            root_type = root_node[2]

        levels = []
        visited = set()
        queue = [(root_id, 0, root_type, "out")]

        type_hierarchy = {
            "concept": 0,
            "knowledge-element": 1,
            "knowledge": 2,
            "entity": 2,
            "skill": 3,
            "scenario": 4,
            "exercise": 5,
            "solution": 5,
            "index": -1,
        }

        with self._conn() as c:
            while queue:
                current, level, ctype, _direction = queue.pop(0)
                if current in visited:
                    continue
                visited.add(current)

                targets = []
                # 出边追踪（source→target）
                out_edges = c.execute("SELECT target_id, rel_type FROM edges WHERE source_id=?", (current,)).fetchall()
                for tid, rt in out_edges:
                    tn = c.execute("SELECT id, name, type FROM nodes WHERE id=?", (tid,)).fetchone()
                    if tn and tn[0] not in visited and tn[2] != "index":
                        ch = type_hierarchy.get(tn[2], 99)
                        if ch >= type_hierarchy.get(ctype, 0):
                            targets.append(
                                {"id": tn[0], "name": tn[1], "type": tn[2], "rel_type": rt, "direction": "out"}
                            )
                            if len(visited) < 200:
                                queue.append((tid, level + 1, tn[2], "out"))

                # 入边追踪（target←source）
                in_edges = c.execute("SELECT source_id, rel_type FROM edges WHERE target_id=?", (current,)).fetchall()
                for sid, rt in in_edges:
                    sn = c.execute("SELECT id, name, type FROM nodes WHERE id=?", (sid,)).fetchone()
                    if sn and sn[0] not in visited and sn[2] != "index":
                        sh = type_hierarchy.get(sn[2], 99)
                        nh = type_hierarchy.get(ctype, 0)
                        if sh >= nh:
                            targets.append(
                                {"id": sn[0], "name": sn[1], "type": sn[2], "rel_type": rt, "direction": "in"}
                            )
                            if len(visited) < 200:
                                queue.append((sid, level + 1, sn[2], "in"))

                if targets:
                    levels.append({"level": level, "nodes": targets})

        return {"root": name, "root_id": root_id, "root_type": root_type, "levels": levels}

    # ── 修改影响分析 ──────────────────────────────────────

    def impact(self, name: str) -> dict:
        """修改前的完整影响分析"""
        node_result = self.query(name)
        if "error" in node_result:
            return node_result

        with self._conn() as c:
            out_direct = c.execute(
                """SELECT target_id, n.type, n.name, e.rel_type
                   FROM edges e JOIN nodes n ON e.target_id = n.id
                   WHERE e.source_id=? OR e.source_id LIKE ?""",
                (name, f"%/{name}"),
            ).fetchall()
            in_direct = c.execute(
                """SELECT source_id, n.type, n.name, e.rel_type
                   FROM edges e JOIN nodes n ON e.source_id = n.id
                   WHERE e.target_id=? OR e.target_id LIKE ?""",
                (name, f"%/{name}"),
            ).fetchall()

            indirect = c.execute(
                """SELECT DISTINCT n2.id, n2.type, n2.name
                   FROM edges e1 JOIN edges e2 ON e1.target_id = e2.source_id
                   JOIN nodes n2 ON e2.target_id = n2.id
                   WHERE (e1.source_id=? OR e1.source_id LIKE ?)
                   AND n2.id NOT LIKE ?""",
                (name, f"%/{name}", f"%{name}%"),
            ).fetchall()

            exercises = c.execute(
                """SELECT n.id, n.name FROM edges e JOIN nodes n ON e.target_id = n.id
                   WHERE (e.source_id=? OR e.source_id LIKE ?)
                   AND n.type IN ('exercise', 'solution')""",
                (name, f"%/{name}"),
            ).fetchall()

        return {
            "node": name,
            "direct_out": [{"id": r[0], "type": r[1], "name": r[2], "rel_type": r[3]} for r in out_direct],
            "direct_in": [{"id": r[0], "type": r[1], "name": r[2], "rel_type": r[3]} for r in in_direct],
            "indirect": [{"id": r[0], "type": r[1], "name": r[2]} for r in indirect],
            "exercises": [{"id": r[0], "name": r[1]} for r in exercises],
            "direct_count": len(out_direct) + len(in_direct),
            "indirect_count": len(indirect),
            "exercise_count": len(exercises),
        }
