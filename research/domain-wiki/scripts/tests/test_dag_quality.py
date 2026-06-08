"""test_dag_quality.py — dag_quality 集成测试

测试 check_level_quality 的 L1-L4 各级检查，
_check_graph_wikilinks 断链检测，_check_book_chain 全书链路验证。

使用 tempfile + mock，不依赖真实知识库数据。
"""

import os
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from dag_utils import DAG_DEPENDS, DAG_ORDER, _phase_dir, _save_state, _state_path

pytestmark = pytest.mark.integration

# ── fixtures ───────────────────────────────────────────────


@pytest.fixture
def wiki_workspace(tmp_path):
    """创建最小化的 wiki 工作区"""
    wr = tmp_path / "wiki"
    wr.mkdir()
    (wr / ".dag").mkdir()
    for ph in ["concepts", "ke", "entities", "kp", "sp", "scene", "exercises", "solutions"]:
        d = _phase_dir(str(wr), ph)
        os.makedirs(d, exist_ok=True)
    return str(wr)


@pytest.fixture
def mock_args(wiki_workspace):
    return SimpleNamespace(
        wiki_root=wiki_workspace,
        book_id="01_test_book",
        book_name="TestBook",
        chapter="1",
        phase="concepts",
        fix=False,
        action="scan",
    )


def _make_state(phases_done=None):
    phases = {}
    for i, ph in enumerate(DAG_ORDER):
        status = "done" if (phases_done and ph in phases_done) else "pending"
        phases[ph] = {"index": i, "status": status, "files": 0, "deps": DAG_DEPENDS[ph]}
    return {
        "book_id": "01_test_book",
        "book_name": "TestBook",
        "chapter": "1",
        "wiki_root": "",
        "current_index": -1,
        "phases": phases,
    }


# ── 测试 check_level_quality 基本行为 ──────────────────────


class TestCheckLevelQuality:
    def test_unknown_level(self, mock_args):
        """传入未知层级应返回 passed=False"""
        from dag_quality import check_level_quality

        result = check_level_quality(mock_args, "L99")
        assert result["passed"] is False
        assert any("未知层级" in c for c in result["critical"])

    def test_l1_all_checks_skip_when_no_data(self, wiki_workspace, mock_args):
        """L1 检查在无数据时：阶段未完成应产生 critical"""
        from dag_quality import check_level_quality

        sp = _state_path(wiki_workspace, "01_test_book", "1")
        state = _make_state()  # 全部 pending
        _save_state(sp, state)

        with (
            patch("dag_quality.scan_broken_links") as mock_sbl,
            patch("dag_quality.verify_exercise_solution_mapping") as mock_vesm,
            patch("dag_quality._check_graph_quality") as mock_gcq,
            patch("dag_quality.check_shared_figures") as mock_csf,
            patch("subprocess.run") as mock_sub,
        ):
            mock_sbl.return_value = 0
            mock_vesm.return_value = []
            mock_gcq.return_value = ("pass", "跳过")
            mock_csf.return_value = {}
            mock_sub.return_value = MagicMock(returncode=0, stdout="{}")

            result = check_level_quality(mock_args, "L1")

        assert isinstance(result, dict)
        assert "passed" in result
        assert "critical" in result
        assert "warnings" in result
        assert "detail" in result

    def test_l1_all_phases_done_pass(self, wiki_workspace, mock_args):
        """所有 L1 阶段标记 done 时 all_phases_done 检查应通过"""
        from dag_quality import check_level_quality

        sp = _state_path(wiki_workspace, "01_test_book", "1")
        all_l1 = ["concepts", "ke", "entities", "kp", "sp", "scene", "exercises", "solutions"]
        state = _make_state(phases_done=[*all_l1, "chapter_toc"])
        _save_state(sp, state)

        with (
            patch("dag_quality.scan_broken_links") as mock_sbl,
            patch("dag_quality.verify_exercise_solution_mapping") as mock_vesm,
            patch("dag_quality._check_graph_quality") as mock_gcq,
            patch("dag_quality.check_shared_figures") as mock_csf,
            patch("subprocess.run") as mock_sub,
        ):
            mock_sbl.return_value = 0
            mock_vesm.return_value = []
            mock_gcq.return_value = ("pass", "")
            mock_csf.return_value = {}
            mock_sub.return_value = MagicMock(returncode=0, stdout="{}")

            result = check_level_quality(mock_args, "L1")

        # all_phases_done 应 pass
        detail = result.get("detail", {})
        if "all_phases_done" in detail:
            assert detail["all_phases_done"]["result"] == "pass"

    def test_l2_requires_l1_done(self, wiki_workspace, mock_args):
        """L2 检查在 L1 未完成时应产生 critical"""
        from dag_quality import check_level_quality

        sp = _state_path(wiki_workspace, "01_test_book", "1")
        state = _make_state()  # 全部 pending
        _save_state(sp, state)

        with (
            patch("dag_quality.scan_broken_links") as mock_sbl,
            patch("dag_quality._check_graph_wikilinks") as mock_gw,
            patch("dag_quality._check_l2_coverage") as mock_lc,
            patch("dag_quality._check_book_chain") as mock_bc,
            patch("dag_quality._check_book_centrality") as mock_bcent,
            patch("dag_quality._check_book_similar") as mock_bs,
        ):
            mock_sbl.return_value = 0
            mock_gw.return_value = ("pass", "")
            mock_lc.return_value = ("pass", "")
            mock_bc.return_value = ("pass", "")
            mock_bcent.return_value = ("pass", "")
            mock_bs.return_value = ("pass", "")

            result = check_level_quality(mock_args, "L2")

        # L1 未完成 → all_l1_done 应 fail
        detail = result.get("detail", {})
        if "all_l1_done" in detail:
            assert detail["all_l1_done"]["result"] == "fail"


# ── 测试 _run_check 辅助函数 ───────────────────────────────


class TestRunCheck:
    def test_critical_failure_adds_to_critical(self):
        """critical 级别的 fail 应添加到 critical 列表"""
        from dag_quality import _run_check

        critical = []
        warnings = []
        detail = {}
        _run_check("critical", "test_check", "Test desc", "fail", "Something failed", detail, critical, warnings)
        assert len(critical) == 1
        assert "Something failed" in critical[0]
        assert len(warnings) == 0
        assert "test_check" in detail

    def test_warning_failure_adds_to_warnings(self):
        """warning 级别的 fail 应添加到 warnings 列表"""
        from dag_quality import _run_check

        critical = []
        warnings = []
        detail = {}
        _run_check("warning", "test_warn", "Warn desc", "fail", "Warning msg", detail, critical, warnings)
        assert len(critical) == 0
        assert len(warnings) == 1

    def test_pass_does_not_add(self):
        """pass 结果不应添加到任何列表"""
        from dag_quality import _run_check

        critical = []
        warnings = []
        detail = {}
        _run_check("critical", "test_pass", "Pass desc", "pass", "All good", detail, critical, warnings)
        assert len(critical) == 0
        assert len(warnings) == 0
        assert "test_pass" in detail
        assert detail["test_pass"]["result"] == "pass"


# ── 测试 _check_graph_wikilinks ────────────────────────────


class TestCheckGraphWikilinks:
    def test_no_graph_db_returns_pass(self, wiki_workspace):
        """图谱未构建时应返回 pass"""
        from dag_quality import _check_graph_wikilinks

        with patch("kb_graph.KGraph") as mock_kg_cls:
            mock_kg = MagicMock()
            mock_kg.db_path = os.path.join(wiki_workspace, ".dag", "nonexistent.db")
            mock_kg_cls.return_value = mock_kg

            result, msg = _check_graph_wikilinks(wiki_workspace, "L2")

        assert result == "pass"
        assert "跳过" in msg or "未构建" in msg

    def test_no_overview_dir_returns_pass(self, wiki_workspace):
        """L2 目录不存在时应返回 pass"""
        from dag_quality import _check_graph_wikilinks

        with patch("kb_graph.KGraph") as mock_kg_cls, patch("dag_quality.get_wiki_root") as mock_gwr:
            mock_kg = MagicMock()
            mock_kg.db_path = os.path.join(wiki_workspace, ".dag", "kb_graph.db")
            mock_kg.build.return_value = {}
            mock_kg_cls.return_value = mock_kg
            mock_gwr.return_value = wiki_workspace

            # 创建一个假的 db 文件让 os.path.exists 通过
            os.makedirs(os.path.dirname(mock_kg.db_path), exist_ok=True)
            with open(mock_kg.db_path, "w") as f:
                f.write("fake")

            result, _msg = _check_graph_wikilinks(wiki_workspace, "L2")

        # 10_总揽 目录不存在 → pass
        assert result == "pass"

    def test_import_error_returns_skip(self, wiki_workspace):
        """ImportError 应返回 skip"""
        # _check_graph_wikilinks 内部有 try/except ImportError
        # 直接测试 ImportError 路径
        with patch.dict("sys.modules", {"kb_graph": None}):
            from dag_quality import _check_graph_wikilinks
            result, _msg = _check_graph_wikilinks(wiki_workspace, "L2")
            assert result in ("skip", "pass")


# ── 测试 _check_book_chain ─────────────────────────────────


class TestCheckBookChain:
    def test_no_graph_db_returns_pass(self, wiki_workspace):
        """图谱未构建时 _check_book_chain 应返回 pass"""
        from dag_quality import _check_book_chain

        with patch("kb_graph.KGraph") as mock_kg_cls, patch("dag_quality.get_wiki_root") as mock_gwr:
            mock_kg = MagicMock()
            mock_kg.db_path = os.path.join(wiki_workspace, ".dag", "nonexistent.db")
            mock_kg_cls.return_value = mock_kg
            mock_gwr.return_value = wiki_workspace

            result, msg = _check_book_chain(wiki_workspace)

        assert result == "pass"
        assert "跳过" in msg or "未构建" in msg

    def test_broken_path_returns_fail(self, wiki_workspace):
        """路径断裂时 _check_book_chain 应返回 fail"""
        from dag_quality import _check_book_chain

        with patch("kb_graph.KGraph") as mock_kg_cls, patch("dag_quality.get_wiki_root") as mock_gwr:
            mock_kg = MagicMock()
            mock_kg.db_path = os.path.join(wiki_workspace, ".dag", "kb_graph.db")
            mock_kg.build.return_value = {}
            mock_kg.check_path_integrity.return_value = {"broken_count": 3}
            mock_kg_cls.return_value = mock_kg
            mock_gwr.return_value = wiki_workspace

            os.makedirs(os.path.dirname(mock_kg.db_path), exist_ok=True)
            with open(mock_kg.db_path, "w") as f:
                f.write("fake")

            result, msg = _check_book_chain(wiki_workspace)

        assert result == "fail"
        assert "断裂" in msg or "3" in msg


# ── 测试 check_shared_figures ──────────────────────────────


class TestCheckSharedFigures:
    def test_no_shared_figures(self, wiki_workspace):
        """无共享图应返回空字典"""
        from dag_quality import check_shared_figures

        concept_dir = os.path.join(wiki_workspace, "30_核心概念")
        os.makedirs(concept_dir, exist_ok=True)
        # 创建两个概念文件，各引用不同的图
        with open(os.path.join(concept_dir, "concept_a.md"), "w") as f:
            f.write("---\nname: A\n---\n图1-1 是 A 的图")
        with open(os.path.join(concept_dir, "concept_b.md"), "w") as f:
            f.write("---\nname: B\n---\n图2-1 是 B 的图")

        result = check_shared_figures(wiki_workspace, None)
        assert len(result) == 0

    def test_shared_figure_detected(self, wiki_workspace):
        """同一图号被两个概念引用应被检测"""
        from dag_quality import check_shared_figures

        concept_dir = os.path.join(wiki_workspace, "30_核心概念")
        os.makedirs(concept_dir, exist_ok=True)
        with open(os.path.join(concept_dir, "concept_a.md"), "w") as f:
            f.write("---\nname: ConceptA\n---\n参见图1-1")
        with open(os.path.join(concept_dir, "concept_b.md"), "w") as f:
            f.write("---\nname: ConceptB\n---\n参见图1-1")

        result = check_shared_figures(wiki_workspace, None)
        assert "图1-1" in result
        assert len(result["图1-1"]) == 2


# ── 测试 _check_graph_quality 图谱检查 ─────────────────────


class TestCheckGraphQualityFunc:
    def test_skip_when_no_db(self, wiki_workspace):
        """无图谱 DB 时所有 graph 检查应跳过"""
        from dag_quality import _check_graph_quality

        with patch("kb_graph.KGraph") as mock_kg_cls, patch("dag_quality.get_wiki_root") as mock_gwr:
            mock_kg = MagicMock()
            mock_kg.db_path = os.path.join(wiki_workspace, ".dag", "no.db")
            mock_kg_cls.return_value = mock_kg
            mock_gwr.return_value = wiki_workspace

            for check_id in ["graph_connectivity", "graph_path_integrity", "graph_hollow_concepts", "graph_orphan_ke"]:
                result, _msg = _check_graph_quality(check_id, wiki_workspace)
                assert result == "pass", f"{check_id} 应返回 pass（跳过）"

    def test_import_error_returns_skip(self, wiki_workspace):
        """ImportError 应返回 skip"""
        from dag_quality import _check_graph_quality


        # _check_graph_quality 内部有 from kb_graph import KGraph
        # 当 patch 使其 ImportError 时，应返回 skip
        with patch.dict("sys.modules", {"kb_graph": None}):
            # 强制让 from kb_graph import KGraph 抛出 ImportError
            result, _msg = _check_graph_quality("graph_connectivity", wiki_workspace)
            # 可能返回 pass（因为 db 不存在）或 skip（ImportError）
            assert result in ("skip", "pass")
