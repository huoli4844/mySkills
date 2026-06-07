"""kb_graph_builder.py — KGraph 构建 Mixin

v39.2: 从 kb_graph.py 拆分。包含全量构建、增量构建、文件处理和边解析逻辑。
KGraph 通过 Mixin 继承获得这些方法。
v45.1-todo: 789行，建议拆分为:
  - kb_graph_builder.py（构建入口+增量，~300行）
  - kb_graph_edges.py（边解析+文件处理，~489行）
"""

from __future__ import annotations


import os
import re
from datetime import datetime

from log_utils import get_logger

log = get_logger(__name__)


class KGraphBuilderMixin:
    """知识图谱构建方法集。

    作为 Mixin 被 KGraph 继承，可直接使用 self._conn()、self._init_db()、
    self._parse_frontmatter()、self._book_dirs() 等核心方法。
    """

    # ── v46.0: 边权重批量更新 ───────────────────────────

    def _update_all_edge_weights(self) -> None:
        """v46.0: 根据节点类型和关系类型批量更新所有边权重。

        权重 = rel_type 基础权重 × type affinity
        """
        with self._conn() as c:
            # 构建 node_id → type 映射
            node_types: dict[str, str] = {}
            for row in c.execute("SELECT id, type FROM nodes"):
                node_types[row[0]] = row[1]

            # 批量更新
            updated = 0
            for row in c.execute("SELECT id, source_id, target_id, rel_type FROM edges"):
                edge_id, src, tgt, rel_type = row
                src_type = node_types.get(src)
                tgt_type = node_types.get(tgt)
                weight = self.compute_edge_weight(rel_type, src_type, tgt_type)
                c.execute(
                    "UPDATE edges SET weight = ? WHERE id = ?",
                    (weight, edge_id),
                )
                updated += 1

            log.info(f"[kb_graph] 权重计算完成: {updated} 条边")

    # ── 构建辅助 ──────────────────────────────────────────

    def _build_node_name_map(self, nodes: list[dict]) -> dict[str, str]:
        """构建 name→node_id 映射表（用于解析纯文本引用）"""
        name_to_id = {}
        for n in nodes:
            name = n.get("name", "")
            # 多个同名节点时优先保留第一个
            if name and name not in name_to_id:
                name_to_id[name] = n["id"]
        return name_to_id

    def _build_name_to_id_pre(self) -> dict[str, str]:
        """预扫描所有 .md 文件，从 frontmatter 构建 name→node_id 映射。

        在 _process_file 之前调用，为 COMPOSED_OF 和 TESTS 提供查找表。
        """
        name_to_id = {}
        for book_dir in self._book_dirs():
            type_dirs = self._type_dir_map(book_dir)
            for scan_dir, _node_type in sorted(type_dirs.items()):
                if not os.path.isdir(scan_dir):
                    continue
                for fname in sorted(os.listdir(scan_dir)):
                    if not fname.endswith(".md"):
                        continue
                    fpath = os.path.join(scan_dir, fname)
                    try:
                        with open(fpath, encoding="utf-8") as f:
                            content = f.read()
                    except Exception as e:
                        log.warning(f"图谱构建错误: {e}")
                        continue
                    fm = self._parse_frontmatter(content)
                    if not fm:
                        continue
                    name = fm.get("name", os.path.basename(fpath).replace(".md", ""))
                    if isinstance(name, list):
                        name = name[0] if name else ""
                    if not name:
                        continue
                    node_id = self._make_node_id(fpath, book_dir)
                    if name not in name_to_id:
                        name_to_id[name] = node_id
        return name_to_id

    def _full_target(self, target: str, book_dir: str) -> str:
        """补全短路径为完整节点 ID"""
        t = target
        if t.startswith("01_领域/01_资料库/"):
            t = t[len("01_领域/01_资料库/") :]
        elif t.startswith("01_资料库/"):
            t = t[len("01_资料库/") :]
        if book_dir and "/" in t and not t.startswith("01_"):
            bname = os.path.basename(book_dir)
            if bname.startswith("01_"):
                return f"{bname}/{t}"
        return t

    # ── 构建 ──────────────────────────────────────────────

    def build(self) -> dict:
        """全量重建知识图谱"""
        self._init_db()
        _now = datetime.now().isoformat()

        nodes = []
        edges = []

        # 预扫描：先收集所有 name→node_id 映射（COMPOSED_OF 和 TESTS 需要）
        name_to_id = self._build_name_to_id_pre()

        # 扫描所有书籍目录
        for book_dir in self._book_dirs():
            type_dirs = self._type_dir_map(book_dir)
            for scan_dir, node_type in sorted(type_dirs.items()):
                if not os.path.isdir(scan_dir):
                    continue
                for fname in sorted(os.listdir(scan_dir)):
                    if not fname.endswith(".md"):
                        continue
                    fpath = os.path.join(scan_dir, fname)
                    self._process_file(fpath, node_type, book_dir, nodes, edges, name_to_id)

        # 后处理：解析纯文本引用（非 wikilink 形式的关联）
        name_to_id = self._build_node_name_map(nodes)
        self._resolve_plaintext_edges(nodes, edges, name_to_id)

        # 写库
        with self._conn() as c:
            c.execute("DELETE FROM nodes")
            c.execute("DELETE FROM edges")
            c.execute("DELETE FROM nodes_fts")

            for n in nodes:
                c.execute(
                    """INSERT INTO nodes (id, type, name, book_id, chapter_num,
                       confidence, source_chapter, summary, dir, mtime, file_path,
                       bloom_level, difficulty)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        n["id"],
                        n["type"],
                        n["name"],
                        n["book_id"],
                        n["chapter_num"],
                        n["confidence"],
                        n["source_chapter"],
                        n["summary"],
                        n["dir"],
                        n["mtime"],
                        n["file_path"],
                        n["bloom_level"],
                        n["difficulty"],
                    ),
                )

            for e in edges:
                c.execute(
                    """INSERT INTO edges (source_id, target_id, rel_type, section, weight)
                       VALUES (?,?,?,?,?)""",
                    (e["source"], e["target"], e["rel_type"], e["section"], 1.0),
                )

            # FTS5 重建
            c.execute("DELETE FROM nodes_fts")
            for i, n in enumerate(nodes):
                fm_text = f"type:{n['type']} book:{n['book_id']} chapter:{n['chapter_num']}"
                c.execute(
                    "INSERT INTO nodes_fts (rowid, name, type, summary, frontmatter_text) " "VALUES (?,?,?,?,?)",
                    (i + 1, n["name"], n["type"], n["summary"], fm_text),
                )

        stats = self._stats()
        book_count = len(self._book_dirs())
        log.info(f"[kb_graph] nodes: {stats['nodes']} ({stats['types']})  "
            f"edges: {stats['edges']} ({stats['rel_types']})  "
            f"books: {book_count}  db: {self.db_path}")

        # v46.0: 计算所有边的权重
        self._update_all_edge_weights()
        stats["weighted"] = True

        return stats

    def build_incremental(self) -> dict:
        """v38.0: 增量构建 — 仅重建已变更的文件，大幅降低 I/O。

        策略：
        1. 对每个 .md 文件计算 content hash（SHA-256 前 16 字节）
        2. 与 _file_hashes 表比对，跳过未变更文件
        3. 仅删除+重建变更节点的 edges
        4. 新文件全量插入，已删除文件全量清除

        Returns:
            统计字典 {nodes, edges, changed, skipped, ...}
        """
        import hashlib

        self._init_db()
        now = datetime.now().isoformat()

        # ── 加载已知 hash ──
        known_hashes: dict[str, str] = {}
        with self._conn() as c:
            for row in c.execute("SELECT file_path, content_hash FROM _file_hashes"):
                known_hashes[row[0]] = row[1]

        # ── 扫描所有文件，计算 hash ──
        current_files: dict[str, str] = {}
        file_infos: list[tuple[str, str, str]] = []

        for book_dir in self._book_dirs():
            type_dirs = self._type_dir_map(book_dir)
            for scan_dir, node_type in sorted(type_dirs.items()):
                if not os.path.isdir(scan_dir):
                    continue
                for fname in sorted(os.listdir(scan_dir)):
                    if not fname.endswith(".md"):
                        continue
                    fpath = os.path.join(scan_dir, fname)
                    try:
                        with open(fpath, encoding="utf-8") as _f:
                            content = _f.read()
                        content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]
                    except OSError:
                        continue
                    current_files[fpath] = content_hash
                    file_infos.append((fpath, node_type, book_dir))

        # ── 分类：新增 / 变更 / 未变 / 已删除 ──
        changed_files = []
        skipped = 0
        for fpath, node_type, book_dir in file_infos:
            fhash = current_files[fpath]
            if fpath in known_hashes and known_hashes[fpath] == fhash:
                skipped += 1
            else:
                changed_files.append((fpath, node_type, book_dir))

        deleted_files = set(known_hashes.keys()) - set(current_files.keys())

        if not changed_files and not deleted_files:
            stats = self._stats()
            stats["changed"] = 0
            stats["skipped"] = skipped
            stats["deleted"] = 0
            log.info(f"[kb_graph] 增量构建: 全部 {skipped} 个文件未变更，跳过重建")
            return stats

        log.info(f"[kb_graph] 增量构建: {len(changed_files)} 变更, " f"{len(deleted_files)} 删除, {skipped} 未变")

        # ── 收集变更节点的 node_id（用于边清理）──
        changed_node_ids: list[str] = []
        for fpath, _, _ in changed_files:
            basename = os.path.splitext(os.path.basename(fpath))[0]
            changed_node_ids.append(basename)
        for fpath in deleted_files:
            basename = os.path.splitext(os.path.basename(fpath))[0]
            changed_node_ids.append(basename)

        # ── 处理变更文件 ──
        nodes = []
        edges = []
        name_to_id = self._build_name_to_id_pre()

        for fpath, node_type, book_dir in changed_files:
            self._process_file(fpath, node_type, book_dir, nodes, edges, name_to_id)

        # ── 写库（增量模式：仅替换变更节点）──
        with self._conn() as c:
            for fpath in deleted_files:
                basename = os.path.splitext(os.path.basename(fpath))[0]
                c.execute("DELETE FROM nodes WHERE id LIKE ?", (f"%{basename}",))

            for fpath, _, _ in changed_files:
                basename = os.path.splitext(os.path.basename(fpath))[0]
                c.execute("DELETE FROM nodes WHERE id LIKE ?", (f"%{basename}",))

            for nid_pattern in changed_node_ids:
                c.execute("DELETE FROM edges WHERE source_id LIKE ?", (f"%{nid_pattern}",))
                c.execute("DELETE FROM edges WHERE target_id LIKE ?", (f"%{nid_pattern}",))

            for n in nodes:
                c.execute(
                    """INSERT OR REPLACE INTO nodes
                       (id, type, name, book_id, chapter_num, confidence,
                        source_chapter, summary, dir, mtime, file_path,
                        bloom_level, difficulty)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        n["id"],
                        n["type"],
                        n["name"],
                        n["book_id"],
                        n["chapter_num"],
                        n["confidence"],
                        n["source_chapter"],
                        n["summary"],
                        n["dir"],
                        n["mtime"],
                        n["file_path"],
                        n["bloom_level"],
                        n["difficulty"],
                    ),
                )

            for e in edges:
                c.execute(
                    """INSERT INTO edges (source_id, target_id, rel_type, section, weight)
                       VALUES (?,?,?,?,?)""",
                    (e["source"], e["target"], e["rel_type"], e["section"], 1.0),
                )

            # 更新 _file_hashes 表
            for fpath in deleted_files:
                c.execute("DELETE FROM _file_hashes WHERE file_path = ?", (fpath,))
            for fpath, content_hash in current_files.items():
                if fpath in [f for f, _, _ in changed_files] or fpath not in known_hashes:
                    c.execute(
                        """INSERT OR REPLACE INTO _file_hashes
                           (file_path, content_hash, mtime, built_at)
                           VALUES (?,?,?,?)""",
                        (fpath, content_hash, os.path.getmtime(fpath) if os.path.exists(fpath) else 0, now),
                    )

            # 重建 FTS（增量：全量重建 FTS，成本低）
            c.execute("DELETE FROM nodes_fts")
            all_nodes = c.execute("SELECT id, name, type, summary FROM nodes").fetchall()
            for i, (nid, name, ntype, summary) in enumerate(all_nodes):
                c.execute(
                    "INSERT INTO nodes_fts (rowid, name, type, summary, frontmatter_text) " "VALUES (?,?,?,?,?)",
                    (i + 1, name, ntype, summary or "", f"type:{ntype} id:{nid}"),
                )

        stats = self._stats()
        stats["changed"] = len(changed_files)
        stats["skipped"] = skipped
        stats["deleted"] = len(deleted_files)
        book_count = len(self._book_dirs())
        log.info(f"[kb_graph] 增量构建完成: nodes={stats['nodes']} edges={stats['edges']} "
            f"changed={stats['changed']} skipped={stats['skipped']} "
            f"deleted={stats['deleted']} books={book_count}")

        # v46.0: 增量后也更新权重
        self._update_all_edge_weights()
        stats["weighted"] = True

        return stats

    # ── 纯文本边解析 ──────────────────────────────────────

    def _resolve_plaintext_edges(self, nodes: list[dict], edges: list[dict], name_to_id: dict[str, str]):
        """后处理：解析纯文本引用，建立非 wikilink 形式的边。

        处理：
        1. 习题 ↔ 解答（ANSWERS）：通过命名约定关联
        2. CONTRASTS_WITH / EVOLVED_FROM / LIMITED_BY / PART_OF：
           从表格、粗体文本、段落中提取概念名，匹配已知节点
        """
        # 收集每本书的目录信息
        book_info = {}
        for n in nodes:
            bid = n.get("book_id", "")
            if bid not in book_info:
                book_info[bid] = []
            book_info[bid].append(n)

        # ── 习题 ↔ 解答（ANSWERS）──
        exercise_nodes = [n for n in nodes if n["type"] == "exercise"]
        solution_nodes = [n for n in nodes if n["type"] == "solution"]

        exercise_name_to_id = {}
        for n in exercise_nodes:
            exercise_name_to_id[n["name"]] = n["id"]
        solution_by_exercise_name = {}
        for n in solution_nodes:
            sol_name = n["name"]
            if sol_name.endswith("-解答"):
                ex_name = sol_name[:-3]
                solution_by_exercise_name[ex_name] = n["id"]

        # exercise → solution
        for n in exercise_nodes:
            ex_id = n["id"]
            ex_name = n["name"]
            sol_id = solution_by_exercise_name.get(ex_name)
            if sol_id:
                dup = any(e["source"] == ex_id and e["target"] == sol_id and e["rel_type"] == "ANSWERS" for e in edges)
                if not dup:
                    edges.append(
                        {
                            "source": ex_id,
                            "target": sol_id,
                            "rel_type": "ANSWERS",
                            "section": "关联习题解答",
                        }
                    )

        # solution → exercise（从解答的 "关联习题" 节提取）
        for n in solution_nodes:
            sol_id = n["id"]
            fpath = n.get("file_path", "")
            if not fpath or not os.path.isfile(fpath):
                continue
            try:
                with open(fpath, encoding="utf-8") as f:
                    content = f.read()
            except Exception as e:
                log.warning(f"图谱构建错误: {e}")
                continue
            parts = content.split("---", 2)
            body = parts[2].strip() if len(parts) >= 3 else ""
            sections = self._split_sections(body)
            for sec in sections:
                if "关联习题" in sec["heading"] and "解答" not in sec["heading"]:
                    exercise_name_found = self._extract_exercise_name(sec["content"])
                    if exercise_name_found:
                        ex_id = exercise_name_to_id.get(exercise_name_found)
                        if ex_id:
                            dup = any(
                                e["source"] == sol_id and e["target"] == ex_id and e["rel_type"] == "ANSWERS"
                                for e in edges
                            )
                            if not dup:
                                edges.append(
                                    {
                                        "source": sol_id,
                                        "target": ex_id,
                                        "rel_type": "ANSWERS",
                                        "section": "关联习题",
                                    }
                                )

        # ── 非 wikilink 节中的概念名匹配 ──────────────────
        concept_like_types = {"concept", "knowledge", "knowledge-element", "skill", "entity", "scenario"}
        for n in nodes:
            if n["type"] not in concept_like_types:
                continue
            nid = n["id"]
            fpath = n.get("file_path", "")
            if not fpath or not os.path.isfile(fpath):
                continue
            try:
                with open(fpath, encoding="utf-8") as f:
                    content = f.read()
            except Exception as e:
                log.warning(f"图谱构建错误: {e}")
                continue
            parts = content.split("---", 2)
            body = parts[2].strip() if len(parts) >= 3 else ""
            sections = self._split_sections(body)
            for sec in sections:
                heading = sec["heading"]
                if self._should_skip(heading):
                    continue
                rel_type = self._infer_rel_type(heading)
                if rel_type == "RELATED_TO":
                    continue
                has_wikilinks = bool(self._extract_wikilinks(sec["content"]))
                if has_wikilinks:
                    continue
                ref_names = self._extract_names_from_plaintext(sec["content"], rel_type)
                for ref_name in ref_names:
                    target_id = name_to_id.get(ref_name)
                    if target_id and target_id != nid:
                        dup = any(
                            e["source"] == nid and e["target"] == target_id and e["rel_type"] == rel_type for e in edges
                        )
                        if not dup:
                            edges.append(
                                {
                                    "source": nid,
                                    "target": target_id,
                                    "rel_type": rel_type,
                                    "section": heading,
                                }
                            )
                # 全文扫描匹配（用于 EVOLVED_FROM, LIMITED_BY, PART_OF）
                if rel_type in ("EVOLVED_FROM", "LIMITED_BY", "PART_OF"):
                    sec_content = sec["content"]
                    sorted_names = sorted(name_to_id.keys(), key=len, reverse=True)
                    matched = set()
                    for nn in sorted_names:
                        if nn in sec_content and nn not in matched:
                            target_id = name_to_id[nn]
                            if target_id and target_id != nid:
                                dup = any(
                                    e["source"] == nid and e["target"] == target_id and e["rel_type"] == rel_type
                                    for e in edges
                                )
                                if not dup:
                                    edges.append(
                                        {
                                            "source": nid,
                                            "target": target_id,
                                            "rel_type": rel_type,
                                            "section": heading,
                                        }
                                    )
                                matched.add(nn)

    def _extract_names_from_plaintext(self, text: str, rel_type: str) -> list[str]:
        """从纯文本（表格、粗体列表、段落）中提取潜在的引用名。"""
        names = []
        seen = set()

        # **A vs B** 模式
        for m in re.finditer(r"\*\*([^*]+)\*\*\s*(?:与|vs|vs\.|和|跟)\s*\*\*([^*]+)\*\*", text):
            for g in [m.group(1).strip(), m.group(2).strip()]:
                if g and g not in seen:
                    names.append(g)
                    seen.add(g)
        # **A vs B** 在同一个粗体块内
        for m in re.finditer(r"\*\*([^*]+?)\s*(?:与|vs|vs\.|和|跟)\s*([^*]+?)\*\*", text):
            for g in [m.group(1).strip(), m.group(2).strip()]:
                if g and g not in seen and len(g) >= 2:
                    names.append(g)
                    seen.add(g)
        # 独立 **名称**
        for m in re.finditer(r"\*\*([^*]{2,30}?)\*\*", text):
            name = m.group(1).strip()
            if (
                name
                and name not in seen
                and not name.startswith("步骤")
                and len(name) >= 2
                and not re.match(r"^[0-9.、\s]+$", name)
            ):
                names.append(name)
                seen.add(name)

        # 表格第一列
        table_pattern = r"^\|([^|]+)\|"
        for line in text.split("\n"):
            line = line.strip()
            if line.startswith("|") and "---" not in line:
                m = re.match(table_pattern, line)
                if m:
                    cell = m.group(1).strip()
                    if cell and cell not in seen and len(cell) >= 2:
                        skip_words = {
                            "概念",
                            "说明",
                            "异同",
                            "对比项",
                            "对比维度",
                            "易混淆组",
                            "A",
                            "B",
                            "类型",
                            "传播环境",
                            "特点",
                            "示例",
                        }
                        if cell not in skip_words:
                            names.append(cell)
                            seen.add(cell)

        # 列表项 `- Name：`
        for m in re.finditer(r"^-\s+([^：:—\-]{2,40}?)[：:—\-]", text, re.MULTILINE):
            name = m.group(1).strip()
            if name and name not in seen and len(name) >= 2:
                names.append(name)
                seen.add(name)

        # "分为/包含/包括" 模式
        for m in re.finditer(
            r"(?:分为|包含|包括|涵盖|由|由……组成|由……构成)"
            r"(?:[^，。；]{0,20}?)"
            r"(?:[、，,]\s*(?:和|与|及)?\s*)?"
            r"([^，。；、]{2,20})"
            r"(?:[、，,]\s*(?:和|与|及)?\s*)"
            r"([^，。；]{2,20})",
            text,
        ):
            for g in [m.group(1).strip(), m.group(2).strip()]:
                if g and g not in seen and len(g) >= 2:
                    names.append(g)
                    seen.add(g)

        return names

    def _extract_exercise_name(self, text: str) -> str | None:
        """从纯文本中提取习题名（如 '第2章-习题5'）"""
        text = text.strip()
        m = re.search(r"(第\d+章-习题\d+)", text)
        if m:
            return m.group(1)
        m = re.search(r"(习题\d+)", text)
        if m:
            return m.group(1)
        return None

    # ── 文件处理 ──────────────────────────────────────────

    def _process_file(
        self, fpath: str, node_type: str, book_dir: str, nodes: list, edges: list, name_to_id: dict[str, str] | None = None
    ):
        """处理单个 .md 文件，提取节点和边"""
        try:
            with open(fpath, encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            log.warning(f"图谱构建错误: {e}")
            return

        fm = self._parse_frontmatter(content)
        if not fm:
            return
        name = fm.get("name", os.path.basename(fpath).replace(".md", ""))
        if isinstance(name, list):
            name = name[0] if name else ""

        parts = content.split("---", 2)
        body = parts[2].strip() if len(parts) >= 3 else ""

        summary = re.sub(r"#+\s*", "", body)[:200].strip()
        summary = re.sub(r"\s+", " ", summary)

        node_id = self._make_node_id(fpath, book_dir)
        mtime = os.path.getmtime(fpath)
        dir_name = os.path.basename(os.path.dirname(fpath))

        if "解答" in fpath:
            dir_name = "解答"

        node = {
            "id": node_id,
            "type": node_type,
            "name": name,
            "book_id": fm.get("book_id", ""),
            "chapter_num": str(fm.get("chapter_num", "")),
            "confidence": float(fm.get("confidence", 0)),
            "source_chapter": fm.get("source_chapter", ""),
            "summary": summary,
            "dir": dir_name,
            "mtime": mtime,
            "file_path": fpath,
            "bloom_level": str(fm.get("bloom_level", "") or ""),
            "difficulty": str(fm.get("difficulty", "") or ""),
        }
        nodes.append(node)

        sections = self._split_sections(body)
        for sec in sections:
            heading = sec["heading"]
            if self._should_skip(heading):
                continue
            rel_type = self._infer_rel_type(heading)
            wikilinks = self._extract_wikilinks(sec["content"])
            for target in wikilinks:
                if not target.strip():
                    continue
                full_target = target
                if full_target.startswith("01_领域/01_资料库/"):
                    full_target = full_target[len("01_领域/01_资料库/") :]
                elif full_target.startswith("01_资料库/"):
                    full_target = full_target[len("01_资料库/") :]
                if "/" not in full_target:
                    if name_to_id:
                        if full_target in name_to_id:
                            full_target = name_to_id[full_target]
                        else:
                            stripped = re.sub(r"^第\d+章-", "", full_target)
                            if stripped != full_target and stripped in name_to_id:
                                full_target = name_to_id[stripped]
                elif book_dir and not full_target.startswith("01_"):
                    bname = os.path.basename(book_dir)
                    if bname.startswith("01_"):
                        full_target = f"{bname}/{full_target}"
                edges.append(
                    {
                        "source": node_id,
                        "target": full_target,
                        "rel_type": rel_type,
                        "section": heading,
                    }
                )

        # 习题→解答
        if node_type == "exercise":
            for sec in sections:
                if "关联习题解答" in sec["heading"]:
                    for link in self._extract_wikilinks(sec["content"]):
                        edges.append(
                            {
                                "source": node_id,
                                "target": self._full_target(link, book_dir),
                                "rel_type": "ANSWERS",
                                "section": "关联习题解答",
                            }
                        )
            related_answer = fm.get("related_answer", "")
            if isinstance(related_answer, str) and related_answer.startswith("[["):
                target = related_answer[2:-2].split("|")[0]
                edges.append(
                    {
                        "source": node_id,
                        "target": self._full_target(target, book_dir),
                        "rel_type": "ANSWERS",
                        "section": "frontmatter.related_answer",
                    }
                )

        # 解答→习题
        if node_type == "solution":
            for sec in sections:
                if "关联习题" in sec["heading"] and "解答" not in sec["heading"]:
                    for link in self._extract_wikilinks(sec["content"]):
                        edges.append(
                            {
                                "source": node_id,
                                "target": self._full_target(link, book_dir),
                                "rel_type": "ANSWERS",
                                "section": "关联习题",
                            }
                        )

        # COMPOSED_OF：SP 实操步骤子技能
        if node_type == "skill" and name_to_id:
            for sec in sections:
                if "实操步骤" in sec["heading"]:
                    sec_text = sec["content"]
                    sub_steps = []
                    sub_steps += re.findall(r"^###\s+\d+[\.\、\s]+(.+?)$", sec_text, re.MULTILINE)
                    sub_steps += re.findall(r"\*\*\s*\d+[\.\、]\s*\*\*(.+?)$", sec_text, re.MULTILINE)
                    for m in re.finditer(r"^\d+[\.\、]\s+\*\*(.+?)\*\*", sec_text, re.MULTILINE):
                        sub_steps.append(m.group(1))
                    sub_steps += re.findall(r"^\d+[\.\、]\s+(?!\*\*)(.+?)$", sec_text, re.MULTILINE)
                    for m in re.finditer(r'\[\s*"\s*步骤\d+\s*[：:]\s*(.+?)\s*"\s*\]', sec_text):
                        sub_steps.append(m.group(1))
                    for m in re.finditer(r"\*\*步骤\d+\s+([^*]+?)\*\*", sec_text):
                        sub_steps.append(m.group(1))
                    for step_name in sub_steps:
                        step_name = step_name.strip().rstrip("。，；")
                        if not step_name or len(step_name) < 2:
                            continue
                        target_id = name_to_id.get(step_name)
                        if target_id and target_id != node_id:
                            dup = any(
                                e["source"] == node_id and e["target"] == target_id and e["rel_type"] == "COMPOSED_OF"
                                for e in edges
                            )
                            if not dup:
                                edges.append(
                                    {
                                        "source": node_id,
                                        "target": target_id,
                                        "rel_type": "COMPOSED_OF",
                                        "section": "实操步骤",
                                    }
                                )

        # TESTS：exercise 中的概念引用
        if node_type == "exercise" and name_to_id:
            sorted_names = sorted(name_to_id.keys(), key=len, reverse=True)
            matched = set()
            for nn in sorted_names:
                if nn in body and nn not in matched:
                    target_id = name_to_id[nn]
                    if target_id and target_id != node_id:
                        dup = any(
                            e["source"] == node_id and e["target"] == target_id and e["rel_type"] == "TESTS"
                            for e in edges
                        )
                        if not dup:
                            edges.append(
                                {
                                    "source": node_id,
                                    "target": target_id,
                                    "rel_type": "TESTS",
                                    "section": "body",
                                }
                            )
                        matched.add(nn)

        # EQUIVALENT_TO：frontmatter aliases
        aliases = fm.get("aliases", None)
        if isinstance(aliases, list) and aliases and name_to_id:
            for alias_name in aliases:
                if not isinstance(alias_name, str) or not alias_name.strip():
                    continue
                alias_name = alias_name.strip()
                alias_target = name_to_id.get(alias_name)
                if alias_target and alias_target != node_id:
                    for src, tgt in [(node_id, alias_target), (alias_target, node_id)]:
                        dup = any(
                            e["source"] == src and e["target"] == tgt and e["rel_type"] == "EQUIVALENT_TO"
                            for e in edges
                        )
                        if not dup:
                            edges.append(
                                {
                                    "source": src,
                                    "target": tgt,
                                    "rel_type": "EQUIVALENT_TO",
                                    "section": "frontmatter.aliases",
                                }
                            )

    # ── 统计 ──────────────────────────────────────────────

    def _stats(self) -> dict:
        with self._conn() as c:
            total_nodes = c.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
            total_edges = c.execute("SELECT COUNT(*) FROM edges").fetchone()[0]
            types_row = c.execute("SELECT type, COUNT(*) FROM nodes GROUP BY type ORDER BY COUNT(*) DESC").fetchall()
            rels_row = c.execute(
                "SELECT rel_type, COUNT(*) FROM edges GROUP BY rel_type ORDER BY COUNT(*) DESC"
            ).fetchall()
        return {
            "nodes": total_nodes,
            "edges": total_edges,
            "types": ", ".join(f"{t}({c})" for t, c in types_row),
            "rel_types": ", ".join(f"{t}({c})" for t, c in rels_row),
        }
