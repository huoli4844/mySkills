"""dag_controller 基础测试"""


import pytest
from dag_utils import DAG_DEPENDS, DAG_ORDER, DIR, LEVEL_QUALITY_CHECKS

pytestmark = pytest.mark.unit


class TestDagUtils:
    def test_dir_has_18_keys(self):
        assert len(DIR) == 18  # v51.5: added DOMAIN_DIR, LIBRARY_DIR
        for key in [
            "CONCEPTS",
            "KE",
            "KP",
            "SP",
            "SCENE",
            "ENTITIES",
            "EXERCISES",
            "SOLUTIONS",
            "OVERVIEW",
            "SOURCE",
            "DOMAIN_CTRL",
            "KB_CTRL",
            "FIELD",
            "LIBRARY",
            "TOC",
            "DATA",
        ]:
            assert key in DIR, f"Missing DIR key: {key}"

    def test_dag_order_12_phases(self):
        assert len(DAG_ORDER) == 12  # v36.1: added chapter_toc
        assert DAG_ORDER[0] == "chapter_toc"
        assert DAG_ORDER == [
            "chapter_toc",
            "concepts",
            "ke",
            "entities",
            "kp",
            "sp",
            "scene",
            "exercises",
            "solutions",
            "l2_indices",
            "l3_indices",
            "l4_indices",
        ]

    def test_dag_depends_acyclic(self):
        """验证 DAG 依赖无循环"""
        visited = set()

        def dfs(phase, path):
            if phase in path:
                pytest.fail(f"Cycle detected: {path}")
            if phase in visited:
                return
            visited.add(phase)
            for dep in DAG_DEPENDS.get(phase, []):
                dfs(dep, [*path, phase])

        for phase in DAG_ORDER:
            dfs(phase, [])

    def test_level_quality_checks_structural(self):
        """验证所有层级都有检查项，L1 有 graph 检查"""
        for level in ["L1", "L2", "L3", "L4"]:
            assert level in LEVEL_QUALITY_CHECKS, f"Missing level: {level}"
            checks = LEVEL_QUALITY_CHECKS[level]["checks"]
            assert len(checks) >= 4, f"{level} has only {len(checks)} checks"

    def test_l1_has_graph_checks(self):
        """L1 必须有 4 项图检查"""
        l1 = LEVEL_QUALITY_CHECKS["L1"]["checks"]
        graph_ids = [c[1] for c in l1 if c[1].startswith("graph_")]
        assert len(graph_ids) >= 4, f"L1 has {len(graph_ids)} graph checks: {graph_ids}"

    def test_l2_has_graph_checks(self):
        l2 = LEVEL_QUALITY_CHECKS["L2"]["checks"]
        assert any("graph_l2" in c[1] for c in l2), "L2 missing graph checks"

    def test_l3_has_graph_checks(self):
        l3 = LEVEL_QUALITY_CHECKS["L3"]["checks"]
        assert any("graph_l3" in c[1] for c in l3), "L3 missing graph checks"

    def test_l4_has_graph_checks(self):
        l4 = LEVEL_QUALITY_CHECKS["L4"]["checks"]
        assert any("graph_l4" in c[1] for c in l4), "L4 missing graph checks"
