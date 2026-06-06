"""quality_graph_checks.py — 知识图谱质量检查函数集合

从 dag_quality.py 拆分。包含所有图驱动的质量检查：
L1 图谱、L2 wikilinks/覆盖率、L3 跨书分析、L4 全库分析。
"""

import os
import re

from dag_constants import DIR, PipelineArgs
from dag_state import get_wiki_root


def _check_graph_quality(check_id: str, wr: str) -> tuple:
    """L1 图谱质量检查（v35.0: 空心概念/孤儿KE/过载/相似名/连通性/路径/孤立节点）"""
    try:
        from kb_graph import KGraph

        wiki_root = get_wiki_root(wr)
        kg = KGraph(wiki_root)
        if not os.path.exists(kg.db_path):
            return "pass", "图谱未构建，跳过"
        kg.build()

        if check_id == "graph_connectivity":
            conn = kg.check_l1_connectivity()
            if not conn["overall_passed"]:
                fail_d = "; ".join(", ".join(c["issues"][:1]) for c in conn["checks"] if not c["passed"])
                return "fail", f"图连通性: {fail_d}"
            return "pass", "图连通性正常"

        elif check_id == "graph_path_integrity":
            paths = kg.check_path_integrity()
            if paths["broken_count"] > 0:
                return "fail", f"路径断裂: {paths['broken_count']} 处"
            return "pass", "路径完整性正常"

        elif check_id == "graph_hollow_concepts":
            quality = kg.check_graph_quality()
            hollow = [i for i in quality["issues"] if i["category"] == "空心概念"]
            if hollow:
                names = [i["message"].split("「")[1].split("」")[0] for i in hollow]
                return "fail", f"空心概念: {', '.join(names)}"
            return "pass", "无空心概念"

        elif check_id == "graph_orphan_nodes":
            quality = kg.check_graph_quality()
            orphans = [i for i in quality["issues"] if i["category"] == "孤立节点"]
            if orphans:
                names = [i["message"].split("「")[1].split("」")[0] for i in orphans]
                return "fail", f"孤立节点: {', '.join(names)}"
            return "pass", "无孤立节点"

        elif check_id == "graph_orphan_ke":
            quality = kg.check_graph_quality()
            orphan_kes = [i for i in quality["issues"] if i["category"] == "孤儿KE"]
            if orphan_kes:
                names = [i["message"].split("「")[1].split("」")[0] for i in orphan_kes]
                return "fail", f"孤儿KE（无KP引用）: {', '.join(names)}"
            return "pass", "KE均有KP引用"

        elif check_id == "graph_overloaded":
            quality = kg.check_graph_quality()
            overloaded = [i for i in quality["issues"] if i["category"] == "过载节点"]
            if overloaded:
                names = [i["message"].split("「")[1].split("」")[0] for i in overloaded[:3]]
                return "fail", f"过载节点（入度≥10）: {', '.join(names)}"
            return "pass", "无过载节点"

        elif check_id == "graph_similar_names":
            similar = kg.check_similar_names(threshold=0.85)
            if similar.get("total", 0) > 0:
                pairs = [f"{p['name1']}≈{p['name2']}" for p in similar.get("pairs", [])[:3]]
                return "fail", f"{similar['total']} 组相似节点名: {', '.join(pairs)}"
            return "pass", "无相似节点名"
    except ImportError:
        return "skip", "kb_graph.py 不可用，跳过图谱检查"
    except Exception as e:
        return "fail", f"图谱检查异常（{check_id}）: {e}"
    return "pass", ""


def _check_graph_wikilinks(wr: str, level: str) -> tuple:
    """检查 L2 索引 wikilink 在图谱中可追溯"""
    try:
        from kb_graph import KGraph

        wiki_root = get_wiki_root(wr)
        kg = KGraph(wiki_root)
        if not os.path.exists(kg.db_path):
            return "pass", "图谱未构建，跳过"
        kg.build()
        overview_dir = os.path.join(wr, DIR["OVERVIEW"])
        if not os.path.isdir(overview_dir):
            return "pass", "L2 目录不存在，跳过"
        missing = []
        for fname in os.listdir(overview_dir):
            if not fname.endswith(".md"):
                continue
            with open(os.path.join(overview_dir, fname)) as fh:
                fc = fh.read()
            for m in re.finditer(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]", fc):
                target = m.group(1).split("/")[-1]
                with kg._conn() as c2:
                    cnt = c2.execute("SELECT COUNT(*) FROM nodes WHERE id LIKE ?", (f"%{target}",)).fetchone()[0]
                    if cnt == 0:
                        missing.append(target)
        if missing:
            return "fail", f"L2 索引中 {len(missing)} 个节点图谱未收录: {', '.join(missing[:5])}"
        return "pass", "L2 索引节点全在图谱中可追溯"
    except ImportError:
        return "skip", "kb_graph.py 不可用"
    except Exception as e:
        return "fail", f"L2 wikilink 图谱检查异常: {e}"


def _check_l2_coverage(wr: str, args: PipelineArgs) -> tuple:
    """检查 L2 索引覆盖 ≥80% 的 L1 节点"""
    try:
        from kb_graph import KGraph

        wiki_root = get_wiki_root(wr)
        kg = KGraph(wiki_root)
        if not os.path.exists(kg.db_path):
            return "pass", "图谱未构建，跳过"
        kg.build()
        with kg._conn() as c:
            total = c.execute(
                "SELECT COUNT(*) FROM nodes WHERE id LIKE ? AND type NOT IN ('index','exercise','solution')",
                (f"{args.book_id}/%",),
            ).fetchone()[0]
        overview_dir = os.path.join(wr, DIR["OVERVIEW"])
        indexed = set()
        if os.path.isdir(overview_dir):
            for fname in os.listdir(overview_dir):
                if not fname.endswith(".md"):
                    continue
                with open(os.path.join(overview_dir, fname)) as fh:
                    fc = fh.read()
                for m in re.finditer(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]", fc):
                    indexed.add(m.group(1).split("/")[-1])
        if total > 0:
            coverage = round(len(indexed) / total * 100, 1)
            if coverage >= 80:
                return "pass", f"L2 覆盖率 {coverage}% ({len(indexed)}/{total})"
            return "fail", f"L2 覆盖率仅 {coverage}% ({len(indexed)}/{total})，需 ≥80%"
        return "pass", "无 L1 节点，跳过"
    except ImportError:
        return "skip", "kb_graph.py 不可用"
    except Exception as e:
        return "fail", f"L2 覆盖率检查异常: {e}"


def _check_cross_book_refs(wr: str) -> tuple:
    """领域内跨书引用检查"""
    try:
        from kb_graph import KGraph

        wiki_root = get_wiki_root(wr)
        kg = KGraph(wiki_root)
        if not os.path.exists(kg.db_path):
            return "pass", "图谱未构建，跳过"
        kg.build()
        with kg._conn() as c:
            books = set()
            for (nid,) in c.execute("SELECT DISTINCT id FROM nodes WHERE id LIKE ?", ("%/%",)).fetchall():
                parts = nid.split("/")
                if len(parts) >= 2:
                    books.add(parts[0])
            if len(books) <= 1:
                return "pass", "仅单书，无需跨书引用检查"
            cross = 0
            for src, tgt in c.execute("SELECT source_id, target_id FROM edges").fetchall():
                sb = src.split("/")[0] if "/" in src else ""
                tb = tgt.split("/")[0] if "/" in tgt else ""
                if sb and tb and sb != tb:
                    cross += 1
            return "pass", f"跨书引用 {cross} 条"
    except ImportError:
        return "skip", "kb_graph.py 不可用"
    except Exception as e:
        return "fail", f"跨书引用检查异常: {e}"


def _check_full_graph(wr: str) -> tuple:
    """全库图谱完整性检查"""
    try:
        from kb_graph import KGraph

        wiki_root = get_wiki_root(wr)
        kg = KGraph(wiki_root)
        if not os.path.exists(kg.db_path):
            return "pass", "图谱未构建，跳过"
        kg.build()
        quality = kg.check_graph_quality()
        hollow = [i for i in quality["issues"] if i["category"] == "空心概念"]
        if hollow:
            names = [i["message"].split("「")[1].split("」")[0] for i in hollow[:5]]
            return "fail", f"全库存在空心概念: {', '.join(names)}"
        return "pass", "全库图谱完整，无空心概念"
    except ImportError:
        return "skip", "kb_graph.py 不可用"
    except Exception as e:
        return "fail", f"全库图谱检查异常: {e}"


def _check_book_chain(wr: str) -> tuple:
    """全书知识链完整性：概念→KE→KP→SP→Scene 路径"""
    try:
        from kb_graph import KGraph

        wiki_root = get_wiki_root(wr)
        kg = KGraph(wiki_root)
        if not os.path.exists(kg.db_path):
            return "pass", "图谱未构建，跳过"
        kg.build()
        paths = kg.check_path_integrity()
        if paths["broken_count"] > 0:
            return "fail", f"全书路径断裂: {paths['broken_count']} 处"
        return "pass", "全书知识链完整"
    except ImportError:
        return "skip", "kb_graph.py 不可用"
    except Exception as e:
        return "fail", f"全书链检查异常: {e}"


def _check_book_centrality(wr: str, args: PipelineArgs) -> tuple:
    """全书核心概念识别：度中心性 top5"""
    try:
        from kb_graph import KGraph

        wiki_root = get_wiki_root(wr)
        kg = KGraph(wiki_root)
        if not os.path.exists(kg.db_path):
            return "pass", "图谱未构建，跳过"
        kg.build()
        centrality = kg.degree_centrality()
        top5 = centrality.get("top5", [])
        orphans = centrality.get("orphan_count", 0)
        if top5:
            names = [n["name"] for n in top5[:3]]
            msg = f"核心节点: {', '.join(names)}"
            if orphans > 0:
                msg += f"；孤立节点: {orphans}"
            return "pass", msg
        return "pass", "无度中心性数据"
    except ImportError:
        return "skip", "kb_graph.py 不可用"
    except Exception as e:
        return "fail", f"中心性检查异常: {e}"


def _check_book_similar(wr: str) -> tuple:
    """跨章概念一致性：同名概念在不同章的定义"""
    try:
        from kb_graph import KGraph

        wiki_root = get_wiki_root(wr)
        kg = KGraph(wiki_root)
        if not os.path.exists(kg.db_path):
            return "pass", "图谱未构建，跳过"
        kg.build()
        similar = kg.check_similar_names(threshold=0.9)
        if similar.get("total", 0) > 0:
            pairs = [f"{p['name1']}≈{p['name2']}" for p in similar.get("pairs", [])[:3]]
            return "fail", f"全书 {similar['total']} 组相似概念: {', '.join(pairs)}"
        return "pass", "全书无相似/重复概念"
    except ImportError:
        return "skip", "kb_graph.py 不可用"
    except Exception as e:
        return "fail", f"相似概念检查异常: {e}"


def _check_cross_book_alignment(wr):
    """跨书概念对齐：领域内同名概念跨书定义一致性"""
    try:
        from kb_graph import KGraph

        wiki_root = get_wiki_root(wr)
        kg = KGraph(wiki_root)
        if not os.path.exists(kg.db_path):
            return "pass", "图谱未构建，跳过"
        kg.build()
        with kg._conn() as c:
            books = set()
            for (nid,) in c.execute("SELECT DISTINCT id FROM nodes WHERE id LIKE ?", ("%/%",)).fetchall():
                parts = nid.split("/")
                if len(parts) >= 2:
                    books.add(parts[0])
            if len(books) <= 1:
                return "pass", "仅单书，无需跨书对齐"
        similar = kg.check_similar_names(threshold=0.88)
        cross_book_pairs = 0
        if similar.get("pairs"):
            for p in similar["pairs"]:
                if "/" in p.get("name1", "") and "/" in p.get("name2", ""):
                    b1 = p["name1"].split("/")[0]
                    b2 = p["name2"].split("/")[0]
                    if b1 != b2:
                        cross_book_pairs += 1
        if cross_book_pairs > 0:
            return "pass", f"发现 {cross_book_pairs} 对跨书相似概念（领域内 {len(books)} 本书）"
        return "pass", f"领域内无跨书概念冲突（{len(books)} 本书）"
    except ImportError:
        return "skip", "kb_graph.py 不可用"
    except Exception as e:
        return "fail", f"跨书对齐异常: {e}"


def _check_knowledge_islands(wr):
    """知识孤岛检测：高重叠概念但跨书引用少"""
    try:
        from kb_graph import KGraph

        wiki_root = get_wiki_root(wr)
        kg = KGraph(wiki_root)
        if not os.path.exists(kg.db_path):
            return "pass", "图谱未构建，跳过"
        kg.build()
        with kg._conn() as c:
            books = set()
            for (nid,) in c.execute("SELECT DISTINCT id FROM nodes WHERE id LIKE ?", ("%/%",)).fetchall():
                parts = nid.split("/")
                if len(parts) >= 2:
                    books.add(parts[0])
            if len(books) <= 1:
                return "pass", "仅单书，无需孤岛检测"
            cross = 0
            for src, tgt in c.execute("SELECT source_id, target_id FROM edges").fetchall():
                sb = src.split("/")[0] if "/" in src else ""
                tb = tgt.split("/")[0] if "/" in tgt else ""
                if sb and tb and sb != tb:
                    cross += 1
            total_edges = c.execute("SELECT COUNT(*) FROM edges").fetchone()[0]
            if total_edges > 0 and cross < total_edges * 0.05:
                return "fail", f"跨书边仅 {cross}/{total_edges}（<5%）→ 可能存在知识孤岛"
            return "pass", f"跨书边 {cross}/{total_edges}，连接良好"
    except ImportError:
        return "skip", "kb_graph.py 不可用"
    except Exception as e:
        return "fail", f"孤岛检测异常: {e}"


def _check_domain_chain(wr):
    """领域教学链覆盖：聚合各书路径完整性"""
    try:
        from kb_graph import KGraph

        wiki_root = get_wiki_root(wr)
        kg = KGraph(wiki_root)
        if not os.path.exists(kg.db_path):
            return "pass", "图谱未构建，跳过"
        kg.build()
        paths = kg.check_path_integrity()
        if paths["broken_count"] > 0:
            return "fail", f"领域内 {paths['broken_count']} 处路径断裂"
        return "pass", "领域知识链完整"
    except ImportError:
        return "skip", "kb_graph.py 不可用"
    except Exception as e:
        return "fail", f"领域链检查异常: {e}"


def _check_full_library_health(wr):
    """全库结构健康度：节点/边/孤立/过载汇总"""
    try:
        from kb_graph import KGraph

        wiki_root = get_wiki_root(wr)
        kg = KGraph(wiki_root)
        if not os.path.exists(kg.db_path):
            return "pass", "图谱未构建，跳过"
        kg.build()
        issues = kg.validate()
        quality = kg.check_graph_quality()
        errors = len([i for i in issues if i["severity"] == "error"])
        criticals = quality["summary"]["critical"]
        warnings = quality["summary"]["warning"]
        centrality = kg.degree_centrality()
        msg = f"节点{centrality['total']} 边(统计略)"
        if errors > 0 or criticals > 0:
            msg += f" ❌{errors}err {criticals}crit"
        if warnings > 0:
            msg += f" ⚠{warnings}warn"
        return "pass" if (errors + criticals) == 0 else "fail", msg
    except ImportError:
        return "skip", "kb_graph.py 不可用"
    except Exception as e:
        return "fail", f"全库健康检查异常: {e}"


def _check_cross_domain_bridges(wr):
    """跨领域桥接：不同领域间概念关联分析"""
    try:
        from kb_graph import KGraph

        wiki_root = get_wiki_root(wr)
        kg = KGraph(wiki_root)
        if not os.path.exists(kg.db_path):
            return "pass", "图谱未构建，跳过"
        kg.build()
        with kg._conn() as c:
            domains = set()
            for (nid,) in c.execute("SELECT DISTINCT id FROM nodes WHERE id LIKE '01_领域/%'").fetchall():
                parts = nid.split("/")
                if len(parts) >= 2:
                    domains.add(parts[1])
            if len(domains) <= 1:
                return "pass", "仅单领域，无需跨领域桥接"
            cross_domain = 0
            for src, tgt in c.execute("SELECT source_id, target_id FROM edges").fetchall():
                sd = src.split("/")[1] if "/" in src and len(src.split("/")) >= 2 else ""
                td = tgt.split("/")[1] if "/" in tgt and len(tgt.split("/")) >= 2 else ""
                if sd and td and sd != td:
                    cross_domain += 1
            return "pass", f"跨领域边 {cross_domain} 条（{len(domains)} 个领域）"
    except ImportError:
        return "skip", "kb_graph.py 不可用"
    except Exception as e:
        return "fail", f"跨领域检查异常: {e}"


def _check_full_library_blindspots(wr):
    """全库知识盲区：所有书中概念→Scene 无完整路径"""
    try:
        from kb_graph import KGraph

        wiki_root = get_wiki_root(wr)
        kg = KGraph(wiki_root)
        if not os.path.exists(kg.db_path):
            return "pass", "图谱未构建，跳过"
        kg.build()
        paths = kg.check_path_integrity()
        if paths["broken_count"] > 0:
            return "fail", f"全库 {paths['broken_count']} 处知识盲区（概念无 Scene 路径）"
        return "pass", "全库无知识盲区"
    except ImportError:
        return "skip", "kb_graph.py 不可用"
    except Exception as e:
        return "fail", f"盲区检查异常: {e}"
