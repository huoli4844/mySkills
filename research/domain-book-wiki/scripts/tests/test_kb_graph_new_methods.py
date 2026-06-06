"""kb_graph 知识图谱引擎 — 7个新增方法的单元测试

覆盖：check_graph_quality, check_l1_connectivity, check_similar_names,
      degree_centrality, check_bridge_gaps, check_path_integrity, suggest_build_order
"""

import pytest
from kb_graph import KGraph

pytestmark = pytest.mark.integration


@pytest.fixture
def kg(tmp_path):
    """创建临时 KGraph 实例（自动清理）"""
    g = KGraph(str(tmp_path))
    g.build()
    return g


def _seed_db(kg):
    """填入种子数据"""
    with kg._conn() as c:
        c.executescript("""
            INSERT INTO nodes (id, type, name, book_id, chapter_num, confidence)
            VALUES
                ('bk/concept/c1', 'concept', '概念A', 'bk', '1', 0.95),
                ('bk/concept/c2', 'concept', '概念B', 'bk', '1', 0.95),
                ('bk/ke/ke1', 'knowledge-element', 'KE1', 'bk', '1', 0.85),
                ('bk/ke/ke2', 'knowledge-element', 'KE2', 'bk', '2', 0.85),
                ('bk/kp/kp1', 'knowledge', 'KP1', 'bk', '1', 0.85),
                ('bk/sp/sp1', 'skill', 'SP1', 'bk', '1', 0.75),
                ('bk/scene/sc1', 'scenario', '场景1', 'bk', '1', 0.65),
                ('bk/concept/c_orphan', 'concept', '空心概念', 'bk', '2', 0.95);
            INSERT INTO edges (source_id, target_id, rel_type)
            VALUES
                ('bk/concept/c1', 'bk/concept/c2', 'RELATED_TO'),
                ('bk/concept/c1', 'bk/ke/ke1', 'PART_OF'),
                ('bk/ke/ke1', 'bk/kp/kp1', 'RELATED_TO'),
                ('bk/kp/kp1', 'bk/sp/sp1', 'EVOLVED_FROM'),
                ('bk/sp/sp1', 'bk/scene/sc1', 'APPLIES_TO'),
                ('bk/concept/c2', 'bk/ke/ke2', 'PART_OF');
        """)


class TestCheckGraphQuality:
    def test_empty_graph(self, kg):
        q = kg.check_graph_quality()
        assert "summary" in q
        assert "issues" in q
        assert q["summary"]["total"] == 0

    def test_detects_hollow_concepts(self, kg):
        _seed_db(kg)
        q = kg.check_graph_quality()
        hollow = [i for i in q["issues"] if i["category"] == "空心概念"]
        assert len(hollow) > 0
        assert any("空心概念" in h["message"] for h in hollow)

    def test_returns_top_nodes(self, kg):
        _seed_db(kg)
        q = kg.check_graph_quality()
        assert "top_nodes" in q


class TestCheckL1Connectivity:
    def test_empty_graph(self, kg):
        conn = kg.check_l1_connectivity()
        assert "overall_passed" in conn
        assert "checks" in conn

    def test_seeded_connectivity(self, kg):
        _seed_db(kg)
        conn = kg.check_l1_connectivity()
        assert isinstance(conn["overall_passed"], bool)
        assert len(conn["checks"]) > 0


class TestCheckSimilarNames:
    def test_empty(self, kg):
        result = kg.check_similar_names()
        # returns dict like {'pairs': [], 'total': 0}
        assert isinstance(result, dict)
        assert "pairs" in result
        assert result["total"] == 0

    def test_no_false_positive(self, kg):
        _seed_db(kg)
        result = kg.check_similar_names()
        for pair in result.get("pairs", []):
            assert pair.get("name1") != pair.get("name2")


class TestDegreeCentrality:
    def test_empty(self, kg):
        cent = kg.degree_centrality()
        assert isinstance(cent, dict)
        assert "nodes" in cent
        assert cent["total"] == 0

    def test_seeded(self, kg):
        _seed_db(kg)
        cent = kg.degree_centrality()
        assert cent["total"] > 0


class TestCheckBridgeGaps:
    def test_empty(self, kg):
        gaps = kg.check_bridge_gaps()
        assert isinstance(gaps, dict)

    def test_seeded(self, kg):
        _seed_db(kg)
        gaps = kg.check_bridge_gaps()
        assert "gaps" in gaps


class TestCheckPathIntegrity:
    def test_empty(self, kg):
        paths = kg.check_path_integrity()
        assert isinstance(paths, dict)

    def test_seeded(self, kg):
        _seed_db(kg)
        paths = kg.check_path_integrity()
        assert "broken_count" in paths
        assert isinstance(paths["broken_count"], int)


class TestSuggestBuildOrder:
    def test_empty(self, kg):
        order = kg.suggest_build_order()
        assert isinstance(order, dict | list)

    def test_seeded(self, kg):
        _seed_db(kg)
        order = kg.suggest_build_order()
        if isinstance(order, dict) and "phases" in order:
            assert len(order["phases"]) > 0
