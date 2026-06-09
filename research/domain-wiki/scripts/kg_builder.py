#!/usr/bin/env python3
"""kg_builder.py — 知识图谱引擎

从已渲染的 .md 文件构建 SQLite 知识图谱。
- nodes: 从 frontmatter 提取（name, type, chapter_num, confidence, bloom_level, difficulty）
- edges: 从 wikilinks 解析（source→target 关系）
- FTS5 全文搜索

只读不写，不修改任何 .md 文件。

用法:
  from kg_builder import KGraph
  kg = KGraph("/path/to/wiki")
  kg.build()              # 全量重建
  kg.query("传导耦合")     # 查询节点+关联
"""

from __future__ import annotations

import os
import re
import sqlite3
import sys
from datetime import datetime
from collections import defaultdict


# ── SQLite Schema ──────────────────────────────────────────

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS nodes (
    id          TEXT PRIMARY KEY,
    type        TEXT NOT NULL,
    name        TEXT NOT NULL,
    book_id     TEXT DEFAULT '',
    chapter_num TEXT DEFAULT '',
    confidence  REAL DEFAULT 0.0,
    source_chapter TEXT DEFAULT '',
    summary     TEXT DEFAULT '',
    dir         TEXT DEFAULT '',
    mtime       REAL DEFAULT 0,
    file_path   TEXT DEFAULT '',
    bloom_level TEXT DEFAULT '',
    difficulty  TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS edges (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id   TEXT NOT NULL,
    target_id   TEXT NOT NULL,
    rel_type    TEXT NOT NULL DEFAULT 'RELATED_TO',
    section     TEXT DEFAULT '',
    weight      REAL NOT NULL DEFAULT 1.0,
    FOREIGN KEY (source_id) REFERENCES nodes(id),
    FOREIGN KEY (target_id) REFERENCES nodes(id)
);
CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(source_id);
CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(target_id);

CREATE VIRTUAL TABLE IF NOT EXISTS nodes_fts USING fts5(
    name, type, summary, frontmatter_text
);

CREATE TABLE IF NOT EXISTS _build_meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

# ── 类型目录映射 ──────────────────────────────────────────

TYPE_DIRS = {
    "concept": "30_核心概念",
    "knowledge-element": "40_知识要素",
    "knowledge": "50_知识点",
    "skill": "60_技能点",
    "scenario": "70_应用场景",
    "entity": "80_实体",
    "exercise": "90_习题",
    "solution": "90_习题/解答",
}


class KGraph:
    """知识图谱引擎"""

    def __init__(self, wiki_root: str, book_dir: str | None | list[str] = None,
                 db_name: str = "knowledge_graph.db"):
        self.wiki_root = os.path.abspath(wiki_root)
        if book_dir is None:
            self.book_dirs = [self.wiki_root]
        elif isinstance(book_dir, str):
            self.book_dirs = [os.path.abspath(book_dir)]
        else:
            self.book_dirs = [os.path.abspath(d) for d in book_dir]
        self.db_path = os.path.join(self.wiki_root, ".dag", db_name)

    # ── 内部连接管理 ──────────────────────────────────────

    def _conn(self):
        """获取数据库连接（上下文管理器）"""
        class _Ctx:
            def __init__(self, path):
                self.path = path
            def __enter__(self_):
                self_._c = sqlite3.connect(self_.path)
                self_._c.row_factory = sqlite3.Row
                self_._c.execute("PRAGMA journal_mode=WAL")
                self_._c.execute("PRAGMA synchronous=OFF")
                return self_._c
            def __exit__(self_, *args):
                self_._c.commit()
                self_._c.close()
        return _Ctx(self.db_path)

    def _init_db(self):
        """初始化数据库表"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        with self._conn() as c:
            c.executescript(SCHEMA_SQL)

    # ── 辅助 ──────────────────────────────────────────────

    @staticmethod
    def _parse_frontmatter(content: str) -> dict:
        """解析 YAML frontmatter"""
        m = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
        if not m:
            return {}
        fm = {}
        for line in m.group(1).split("\n"):
            if ":" in line:
                k, v = line.split(":", 1)
                k = k.strip()
                v = v.strip().strip('"').strip("'")
                if k:
                    fm[k] = v
        return fm

    @staticmethod
    def _extract_wikilinks(content: str) -> list[str]:
        """从 .md 内容中提取 wikilink 目标"""
        targets = set()
        for m in re.finditer(r"\[\[([^\]|]+)", content):
            t = m.group(1).strip()
            if "#" in t:
                t = t.split("#")[0]
            # 去掉 ../ 前缀
            while t.startswith("../"):
                t = t[3:]
            if t:
                targets.add(t)
        return sorted(targets)

    @staticmethod
    def _is_type_dir(dir_name: str) -> bool:
        """判断目录是否为类型目录"""
        return any(dir_name.endswith(d) for d in TYPE_DIRS.values())

    @classmethod
    def _type_for_dir(cls, dir_name: str) -> str:
        """从目录名推导节点类型"""
        for t, d in TYPE_DIRS.items():
            if dir_name.endswith(d):
                return t
        return "unknown"

    @staticmethod
    def _mtime(path: str) -> float:
        try:
            return os.path.getmtime(path)
        except OSError:
            return 0.0

    def _scan_all_md_files(self) -> list[dict]:
        """扫描所有类型目录下的 .md 文件"""
        files = []
        for node_type, rel_dir in TYPE_DIRS.items():
            for bd in self.book_dirs:
                scan_dir = os.path.join(bd, rel_dir)
                if not os.path.isdir(scan_dir):
                    continue
                for fn in sorted(os.listdir(scan_dir)):
                    if not fn.endswith(".md"):
                        continue
                    path = os.path.join(scan_dir, fn)
                    files.append({
                        "path": path,
                        "fname": fn[:-3],
                        "type": node_type,
                        "dir": scan_dir,
                    })
        return files

    # ── 构建 ──────────────────────────────────────────────

    def build(self) -> dict:
        """全量重建知识图谱"""
        self._init_db()

        nodes = []
        edges = []
        name_to_id = defaultdict(set)  # name → [node_id, ...]

        md_files = self._scan_all_md_files()
        for entry in md_files:
            try:
                with open(entry["path"], encoding="utf-8") as f:
                    content = f.read()
            except Exception as e:
                print(f"  ⚠️  读取失败: {entry['path']}: {e}")
                continue

            fm = self._parse_frontmatter(content)
            name = fm.get("name", entry["fname"])
            if isinstance(name, list):
                name = name[0] if name else entry["fname"]

            # 相对路径 = 类型目录下的文件名
            dir_name = os.path.basename(entry["dir"])
            node_id = f"{dir_name}/{entry['fname']}"

            chapter_num = fm.get("chapter_num", fm.get("source_chapter", ""))
            try:
                confidence = float(fm.get("confidence", 0) or 0)
            except (ValueError, TypeError):
                confidence = 0.0
            summary = fm.get("summary", "")[:500]

            nodes.append({
                "id": node_id,
                "type": entry["type"],
                "name": name,
                "book_id": fm.get("book_id", ""),
                "chapter_num": str(chapter_num) if chapter_num else "",
                "confidence": confidence,
                "source_chapter": fm.get("source_chapter", ""),
                "summary": summary,
                "dir": dir_name,
                "mtime": self._mtime(entry["path"]),
                "file_path": entry["path"],
                "bloom_level": fm.get("bloom_level", ""),
                "difficulty": fm.get("difficulty", ""),
            })
            name_to_id[name].add(node_id)
            name_to_id[entry["fname"]].add(node_id)

        # 第二次扫描：解析 wikilinks 构造边
        for entry in md_files:
            try:
                with open(entry["path"], encoding="utf-8") as f:
                    content = f.read()
            except Exception as e:
                print(f"  [kg_builder] 读取文件失败 {entry.get('path', '?')}: {e}")
                continue

            dir_name = os.path.basename(entry["dir"])
            source_id = f"{dir_name}/{entry['fname']}"
            wikilinks = self._extract_wikilinks(content)

            for target in wikilinks:
                # 尝试匹配 target
                target_ids = name_to_id.get(target, set())

                # 如果 target 包含 / 前缀，尝试作为完整 ID
                if not target_ids and "/" in target:
                    # 可能像 "30_核心概念/xxx" 格式
                    target_ids = {target}

                # 前向匹配：从文件路径匹配
                if not target_ids:
                    for entry2 in md_files:
                        dir2 = os.path.basename(entry2["dir"])
                        if f"{dir2}/{entry2['fname']}" == target or entry2["fname"] == target:
                            target_ids.add(f"{dir2}/{entry2['fname']}")
                            break

                # 名称模糊匹配
                if not target_ids:
                    nid_set = name_to_id.get(target)
                    if nid_set:
                        target_ids = nid_set

                for target_id in target_ids:
                    if source_id != target_id:
                        edges.append({
                            "source": source_id,
                            "target": target_id,
                            "rel_type": "RELATED_TO",
                            "section": "",
                            "weight": 1.0,
                        })

        # 写库
        with self._conn() as c:
            c.execute("DELETE FROM nodes")
            c.execute("DELETE FROM edges")
            c.execute("DELETE FROM nodes_fts")

            for n in nodes:
                c.execute(
                    """INSERT INTO nodes
                       (id, type, name, book_id, chapter_num, confidence,
                        source_chapter, summary, dir, mtime, file_path,
                        bloom_level, difficulty)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (n["id"], n["type"], n["name"], n["book_id"], n["chapter_num"],
                     n["confidence"], n["source_chapter"], n["summary"],
                     n["dir"], n["mtime"], n["file_path"],
                     n["bloom_level"], n["difficulty"]),
                )

            for e in edges:
                c.execute(
                    """INSERT INTO edges (source_id, target_id, rel_type, section, weight)
                       VALUES (?,?,?,?,?)""",
                    (e["source"], e["target"], e["rel_type"], e["section"], e["weight"]),
                )

            # FTS5
            for i, n in enumerate(nodes):
                fm_text = f"type:{n['type']} name:{n['name']} chapter:{n['chapter_num']}"
                c.execute(
                    "INSERT INTO nodes_fts (rowid, name, type, summary, frontmatter_text) VALUES (?,?,?,?,?)",
                    (i + 1, n["name"], n["type"], n["summary"][:200], fm_text),
                )

            c.execute(
                "INSERT OR REPLACE INTO _build_meta (key, value) VALUES (?, ?)",
                ("last_build", datetime.now().isoformat()),
            )

        stats = self._stats()
        print(f"  📊 KG构建: nodes={stats['nodes']} ({stats['types']}种类型), "
              f"edges={stats['edges']}, db={os.path.getsize(self.db_path)} bytes")
        return stats

    def quick_build(self) -> dict:
        """增量检查：若有数据库且文件未修改则跳过"""
        if os.path.exists(self.db_path):
            with self._conn() as c:
                row = c.execute("SELECT value FROM _build_meta WHERE key='last_build'").fetchone()
            if row:
                # 检查是否有新文件
                new_files = [f for f in self._scan_all_md_files()
                             if self._mtime(f["path"]) > 0]
                # 简单策略：总是重建（以确保最新）
                pass
        return self.build()

    # ── 查询 ──────────────────────────────────────────────

    def query(self, name: str) -> dict:
        """按节点名查询"""
        with self._conn() as c:
            rows = c.execute("SELECT * FROM nodes WHERE name=? LIMIT 1", (name,)).fetchall()
            if not rows:
                rows = c.execute("SELECT * FROM nodes WHERE id=? LIMIT 1", (name,)).fetchall()
            if not rows:
                rows = c.execute("SELECT * FROM nodes WHERE name LIKE ? LIMIT 10",
                                 (f"%{name}%",)).fetchall()
            if not rows:
                return {"error": f"未找到节点: {name}"}

            results = []
            for row in rows:
                node = {
                    "id": row["id"], "type": row["type"], "name": row["name"],
                    "chapter_num": row["chapter_num"], "confidence": row["confidence"],
                }
                out_edges = c.execute(
                    "SELECT target_id, rel_type FROM edges WHERE source_id=?",
                    (row["id"],),
                ).fetchall()
                in_edges = c.execute(
                    "SELECT source_id, rel_type FROM edges WHERE target_id=?",
                    (row["id"],),
                ).fetchall()
                results.append({
                    "node": node,
                    "edges_out": [{"target": e[0], "rel_type": e[1]} for e in out_edges],
                    "edges_in": [{"source": e[0], "rel_type": e[1]} for e in in_edges],
                })
            return {"results": results, "total": len(results)}

    def search(self, text: str, limit: int = 20) -> dict:
        """搜索节点"""
        with self._conn() as c:
            rows = c.execute(
                "SELECT id, type, name, confidence, chapter_num FROM nodes "
                "WHERE name LIKE ? OR summary LIKE ? LIMIT ?",
                (f"%{text}%", f"%{text}%", limit),
            ).fetchall()
            return {
                "query": text,
                "results": [dict(r) for r in rows],
                "total": len(rows),
            }

    def trace(self, name: str, max_levels: int = 5, max_nodes: int = 50) -> dict:
        """追踪影响链（BFS）"""
        with self._conn() as c:
            root = c.execute(
                "SELECT id, name, type FROM nodes WHERE name=? OR id=? LIMIT 1",
                (name, name),
            ).fetchone()
            if not root:
                return {"error": f"未找到节点: {name}"}

            levels = []
            visited = {root["id"]}
            queue = [(root["id"], 0)]
            type_rank = {"concept": 0, "knowledge-element": 1, "knowledge": 2,
                         "skill": 3, "scenario": 4, "entity": 1, "exercise": 5, "solution": 5}

            while queue and len(visited) < max_nodes:
                current, depth = queue.pop(0)
                if depth > max_levels:
                    continue

                neighbors = []
                for tid, in c.execute(
                    "SELECT target_id FROM edges WHERE source_id=?", (current,)
                ).fetchall():
                    if tid not in visited:
                        neighbors.append(tid)
                        visited.add(tid)
                        queue.append((tid, depth + 1))
                for sid, in c.execute(
                    "SELECT source_id FROM edges WHERE target_id=?", (current,)
                ).fetchall():
                    if sid not in visited:
                        neighbors.append(sid)
                        visited.add(sid)
                        queue.append((sid, depth + 1))

                if neighbors:
                    level_nodes = []
                    for nid in neighbors[:10]:
                        r = c.execute("SELECT id, name, type FROM nodes WHERE id=?", (nid,)).fetchone()
                        if r:
                            level_nodes.append({"id": r["id"], "name": r["name"], "type": r["type"]})
                    levels.append({"level": depth, "nodes": level_nodes})

            return {"root": root["name"], "root_id": root["id"], "levels": levels}

    # ── 统计 ──────────────────────────────────────────────

    def _stats(self) -> dict:
        """获取基本统计"""
        with self._conn() as c:
            nodes = c.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
            edges = c.execute("SELECT COUNT(*) FROM edges").fetchone()[0]
            types = c.execute("SELECT type, COUNT(*) FROM nodes GROUP BY type ORDER BY COUNT(*) DESC").fetchall()
            avg_edges = round(edges / max(nodes, 1), 1)
            return {
                "nodes": nodes,
                "edges": edges,
                "avg_edges": avg_edges,
                "types": ", ".join(f"{t}:{c}" for t, c in types),
                "type_counts": {t: c for t, c in types},
            }

    def get_type_stats(self) -> list:
        """按类型统计（每个类型的节点数、平均出度、平均入度）"""
        with self._conn() as c:
            return c.execute(
                """SELECT n.type, COUNT(*),
                          ROUND(AVG((SELECT COUNT(*) FROM edges WHERE source_id=n.id)), 1),
                          ROUND(AVG((SELECT COUNT(*) FROM edges WHERE target_id=n.id)), 1)
                   FROM nodes n
                   WHERE n.type NOT IN ('index','exercise','solution')
                   GROUP BY n.type ORDER BY COUNT(*) DESC""",
            ).fetchall()

    def get_chapter_distribution(self) -> list:
        """按章节+类型分布"""
        with self._conn() as c:
            return c.execute(
                """SELECT n.chapter_num, n.type, COUNT(*)
                   FROM nodes n
                   WHERE n.type NOT IN ('index','exercise','solution')
                     AND n.chapter_num != ''
                   GROUP BY n.chapter_num, n.type ORDER BY n.chapter_num""",
            ).fetchall()

    def get_top_nodes(self, limit: int = 10) -> list:
        """按度中心性排名的 top 节点"""
        with self._conn() as c:
            return c.execute(
                """SELECT n.id, n.name, n.type,
                          (SELECT COUNT(*) FROM edges WHERE target_id=n.id) AS in_degree,
                          (SELECT COUNT(*) FROM edges WHERE source_id=n.id) AS out_degree
                   FROM nodes n
                   WHERE n.type NOT IN ('index','exercise','solution')
                   ORDER BY (in_degree + out_degree) DESC
                   LIMIT ?""",
                (limit,),
            ).fetchall()

    def get_edge_count(self, node_id: str) -> int:
        """节点边数"""
        with self._conn() as c:
            r = c.execute(
                "SELECT COUNT(*) FROM edges WHERE source_id=? OR target_id=?",
                (node_id, node_id),
            ).fetchone()
            return r[0] if r else 0

    def check_graph_quality(self) -> dict:
        """图质量检查"""
        issues = []
        with self._conn() as c:
            # 空心概念（无外链的概念）
            hollow = c.execute(
                """SELECT n.id, n.name FROM nodes n
                   WHERE n.type='concept'
                   AND NOT EXISTS (SELECT 1 FROM edges e WHERE e.source_id=n.id)""",
            ).fetchall()
            for h in hollow:
                issues.append({
                    "category": "空心概念",
                    "message": f"概念「{h['name']}」没有出链",
                    "severity": "critical",
                    "fix_hint": f"在 {h['name']} 中添加相关知识要素wikilink",
                })

            # 孤儿KE（无入链的 KE）
            orphan_ke = c.execute(
                """SELECT n.id, n.name FROM nodes n
                   WHERE n.type='knowledge-element'
                   AND NOT EXISTS (SELECT 1 FROM edges e WHERE e.target_id=n.id)""",
            ).fetchall()
            for o in orphan_ke:
                issues.append({
                    "category": "孤儿KE",
                    "message": f"知识要素「{o['name']}」无入链",
                    "severity": "warning",
                    "fix_hint": f"确保有概念或KP引用了 {o['name']}",
                })

            # 孤立节点（0 关联）
            isolated = c.execute(
                """SELECT n.id, n.name, n.type FROM nodes n
                   WHERE n.type NOT IN ('exercise','solution','index')
                   AND NOT EXISTS (SELECT 1 FROM edges e WHERE e.source_id=n.id OR e.target_id=n.id)""",
            ).fetchall()
            for iso in isolated:
                issues.append({
                    "category": "孤立节点",
                    "message": f"「{iso['name']}」({iso['type']})无任何边",
                    "severity": "warning",
                    "fix_hint": "添加 wikilink 将其关联到其他节点",
                })

            # 过载概念（入度 > 20）
            overloaded = c.execute(
                """SELECT n.id, n.name, COUNT(*) AS cnt FROM nodes n
                   JOIN edges e ON e.target_id=n.id
                   WHERE n.type='concept'
                   GROUP BY n.id HAVING cnt > 20
                   ORDER BY cnt DESC""",
            ).fetchall()
            for ov in overloaded:
                issues.append({
                    "category": "过载节点",
                    "message": f"概念「{ov['name']}」入度 {ov['cnt']} > 20",
                    "severity": "info",
                    "fix_hint": "考虑将大概念拆分为子概念",
                })

        type_counts = self._stats()["type_counts"]
        all_non_idx = sum(c for t, c in type_counts.items()
                          if t not in ("exercise", "solution", "index"))
        summary = {
            "critical": len([i for i in issues if i["severity"] == "critical"]),
            "warning": len([i for i in issues if i["severity"] == "warning"]),
            "info": len([i for i in issues if i["severity"] == "info"]),
            "total_issues": len(issues),
            "non_index_nodes": all_non_idx,
        }
        return {"summary": summary, "issues": issues}

    def get_raw_nodes(self, book_id: str = "") -> dict:
        """获取所有节点原始数据（用于索引构建）"""
        like = f"{book_id}/%" if book_id else "%"
        nodes = {}
        with self._conn() as c:
            rows = c.execute(
                "SELECT id, type, name, chapter_num, confidence, bloom_level, difficulty FROM nodes WHERE id LIKE ?",
                (like,),
            ).fetchall()
            for r in rows:
                node_id = r["id"]
                edge_count = self.get_edge_count(node_id)
                nodes[node_id] = {
                    "id": node_id,
                    "type": r["type"],
                    "name": r["name"],
                    "chapter_num": r["chapter_num"],
                    "confidence": r["confidence"],
                    "bloom_level": r["bloom_level"],
                    "difficulty": r["difficulty"],
                    "edge_count": edge_count,
                }
        return nodes

    def get_edges(self, book_id: str = "") -> list:
        """获取所有边（用于索引中的 Mermaid 构建）"""
        like = f"{book_id}/%" if book_id else "%"
        with self._conn() as c:
            return c.execute(
                """SELECT e.source_id, e.target_id, e.rel_type
                   FROM edges e
                   JOIN nodes ns ON e.source_id=ns.id
                   JOIN nodes nt ON e.target_id=nt.id
                   WHERE ns.id LIKE ? AND nt.id LIKE ?""",
                (like, like),
            ).fetchall()


# ════════════════════════════════════════════════════════════
# CLI
# ════════════════════════════════════════════════════════════

def main():
    import argparse
    p = argparse.ArgumentParser(description="KGraph — 知识图谱引擎")
    p.add_argument("wiki_root", help="知识库根目录")
    sp = p.add_subparsers(dest="cmd", required=True)

    sp.add_parser("build", help="全量重建")
    qp = sp.add_parser("query", help="查询节点")
    qp.add_argument("name", help="节点名")

    sp.add_parser("stats", help="统计信息")
    sp.add_parser("quality", help="质量检查")
    sp.add_parser("top", help="Top 10 节点")

    args = p.parse_args()
    kg = KGraph(args.wiki_root)

    if args.cmd == "build":
        stats = kg.build()
        print(f"  nodes={stats['nodes']}, edges={stats['edges']}")
    elif args.cmd == "query":
        result = kg.query(args.name)
        print(f"查询: {args.name}")
        for r in result.get("results", []):
            n = r["node"]
            print(f"  节点: {n['name']} ({n['type']}) — 置信度 {n['confidence']}")
            for e in r.get("edges_out", []):
                print(f"    → {e['target']} [{e['rel_type']}]")
            for e in r.get("edges_in", []):
                print(f"    ← {e['source']} [{e['rel_type']}]")
    elif args.cmd == "stats":
        s = kg._stats()
        print(f"Nodes: {s['nodes']}  Edges: {s['edges']}  Avg edges/node: {s['avg_edges']}")
        print(f"Types: {s['types']}")
    elif args.cmd == "quality":
        q = kg.check_graph_quality()
        s = q["summary"]
        print(f"图质量检查:")
        print(f"  🔴 Critical: {s['critical']}   ⚠️ Warning: {s['warning']}   ℹ️ Info: {s['info']}")
        for issue in q["issues"][:20]:
            print(f"  [{issue['severity']}] {issue['message']}")
        if len(q["issues"]) > 20:
            print(f"  ... 还有 {len(q['issues'])-20} 个")
    elif args.cmd == "top":
        top = kg.get_top_nodes()
        print(f"Top 10 核心节点:")
        for i, r in enumerate(top, 1):
            deg = r["in_degree"] + r["out_degree"]
            print(f"  {i}. {r['name']} ({r['type']}) — 入度{r['in_degree']}, 出度{r['out_degree']}, 总度{deg}")


if __name__ == "__main__":
    main()
