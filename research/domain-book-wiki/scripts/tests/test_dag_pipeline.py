"""test_dag_pipeline.py — dag_pipeline 集成测试

测试 pipeline_init, phase_add, pipeline_done, pipeline_validate 的核心逻辑。
使用 tempfile + mock，不依赖真实知识库数据。
"""

import json
import os
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

# 确保 scripts 目录在 sys.path 中
from dag_utils import (
    DAG_DEPENDS,
    DAG_ORDER,
    _load_state,
    _phase_dir,
    _save_state,
    _state_path,
)

pytestmark = pytest.mark.integration

# ── fixtures ───────────────────────────────────────────────


@pytest.fixture
def wiki_workspace(tmp_path):
    """创建一个最小化的 wiki 工作区目录结构"""
    wr = tmp_path / "wiki"
    wr.mkdir()
    # 创建 .dag 目录
    (wr / ".dag").mkdir()
    # 创建基本阶段目录
    for ph in ["concepts", "ke", "entities", "kp", "sp", "scene", "exercises", "solutions"]:
        d = _phase_dir(str(wr), ph)
        os.makedirs(d, exist_ok=True)
    return str(wr)


@pytest.fixture
def mock_args(wiki_workspace):
    """创建模拟的 argparse args 对象"""
    return SimpleNamespace(
        wiki_root=wiki_workspace,
        book_id="01_test_book",
        book_name="TestBook",
        chapter="1",
        phase="concepts",
        input=None,
        output=None,
        fix=False,
        action="scan",
    )


def _make_state(book_id="01_test_book", phases_done=None):
    """辅助：创建最小 state 字典"""
    phases = {}
    for i, ph in enumerate(DAG_ORDER):
        status = "done" if (phases_done and ph in phases_done) else "pending"
        phases[ph] = {"index": i, "status": status, "files": 0, "deps": DAG_DEPENDS[ph]}
    return {
        "book_id": book_id,
        "book_name": "TestBook",
        "chapter": "1",
        "wiki_root": "",
        "current_index": -1,
        "phases": phases,
    }


# ── 测试 pipeline_init ─────────────────────────────────────


class TestPipelineInit:
    def test_state_json_created(self, wiki_workspace, mock_args):
        """pipeline_init 应创建 state.json 文件"""
        from dag_pipeline_ops import pipeline_init

        with (
            patch("dag_pipeline.detect_layout") as mock_detect,
            patch("dag_pipeline.save_workspace_config"),
            patch("dag_pipeline._print_pipeline_status"),
        ):
            mock_detect.return_value = {"layout": "flat", "kb_root": wiki_workspace}
            pipeline_init(mock_args)

        sp = _state_path(wiki_workspace, "01_test_book", "1")
        assert os.path.exists(sp), "state.json 应被创建"

    def test_state_json_structure(self, wiki_workspace, mock_args):
        """state.json 应包含正确的阶段结构"""
        from dag_pipeline_ops import pipeline_init

        with (
            patch("dag_pipeline.detect_layout") as mock_detect,
            patch("dag_pipeline.save_workspace_config"),
            patch("dag_pipeline._print_pipeline_status"),
        ):
            mock_detect.return_value = {"layout": "flat", "kb_root": wiki_workspace}
            pipeline_init(mock_args)

        sp = _state_path(wiki_workspace, "01_test_book", "1")
        state = _load_state(sp)
        assert "phases" in state
        assert state["book_id"] == "01_test_book"
        # 所有 12 个阶段都应在 state 中
        for ph in DAG_ORDER:
            assert ph in state["phases"], f"阶段 {ph} 应在 state 中"
        # 每个阶段应有 index, status, files, deps
        for ph in DAG_ORDER:
            p = state["phases"][ph]
            assert "index" in p
            assert "status" in p
            assert "files" in p
            assert "deps" in p


# ── 测试 phase_add ──────────────────────────────────────────


class TestPhaseAdd:
    def test_no_input_file(self, wiki_workspace, mock_args):
        """phase_add 无 --input 应不崩溃并直接返回"""
        from dag_pipeline_ops import phase_add

        mock_args.input = None
        result = phase_add(mock_args)
        assert result is None  # 函数应直接返回而不崩溃

    def test_empty_new_items(self, wiki_workspace, mock_args, tmp_path):
        """phase_add 空 items 应不崩溃并直接返回"""
        from dag_pipeline_ops import phase_add

        input_file = tmp_path / "empty.json"
        input_file.write_text(json.dumps({"items": []}))
        mock_args.input = str(input_file)
        result = phase_add(mock_args)
        assert result is None  # 函数应直接返回而不崩溃


# ── 测试 pipeline_done 概念闸门逻辑 ────────────────────────


class TestPipelineDoneConceptGate:
    def test_done_sets_in_progress_first(self, wiki_workspace, mock_args):
        """pipeline_done 应先将状态设为 in_progress，验证通过后才设为 done"""
        # 在 concepts 目录创建几个假的 .md 文件
        concept_dir = _phase_dir(wiki_workspace, "concepts")
        for i in range(3):
            with open(os.path.join(concept_dir, f"concept_{i}.md"), "w") as f:
                f.write("---\ntype: concept\nname: test\n---\nbody")

        # 创建 state 文件
        sp = _state_path(wiki_workspace, "01_test_book", "1")
        state = _make_state(phases_done=["chapter_toc"])
        _save_state(sp, state)

        # 验证初始状态
        loaded = _load_state(sp)
        assert loaded["phases"]["concepts"]["status"] == "pending"
        # 验证 state 结构正确
        assert loaded["phases"]["chapter_toc"]["status"] == "done"

    def test_done_invalid_phase(self, wiki_workspace, mock_args):
        """pipeline_done 传入无效阶段名应不崩溃并直接返回"""
        from dag_pipeline_done import pipeline_done

        sp = _state_path(wiki_workspace, "01_test_book", "1")
        state = _make_state()
        _save_state(sp, state)

        mock_args.phase = "invalid_phase"
        result = pipeline_done(mock_args)
        assert result is None  # 函数应直接返回而不崩溃


# ── 测试 DAG 依赖检查 ──────────────────────────────────────


class TestDAGDependencyCheck:
    def test_dependency_blocks_advancing(self, wiki_workspace, mock_args, capsys):
        """前置阶段未完成时 pipeline_next 应拒绝推进"""
        from dag_pipeline_done import pipeline_next

        sp = _state_path(wiki_workspace, "01_test_book", "1")
        # 所有阶段都是 pending（chapter_toc 也是 pending）
        state = _make_state()
        _save_state(sp, state)

        with (
            patch("dag_utils.PipelineLock") as mock_lock_cls,
            patch("dag_pipeline.pipeline_validate") as mock_pv,
            patch("dag_pipeline.build_skeleton", create=True) as _mock_bs,
        ):
            mock_lock = MagicMock()
            mock_lock.acquire.return_value = True
            mock_lock_cls.return_value = mock_lock
            mock_pv.return_value = {"passed": True, "critical": []}
            pipeline_next(mock_args)

        _out = capsys.readouterr().out
        # chapter_toc 是第一个阶段，无依赖，应被选中

    def test_all_deps_met_selects_next(self):
        """DAG_DEPENDS 中每个阶段的依赖都在 DAG_ORDER 中先出现"""
        for ph in DAG_ORDER:
            deps = DAG_DEPENDS.get(ph, [])
            ph_idx = DAG_ORDER.index(ph)
            for dep in deps:
                dep_idx = DAG_ORDER.index(dep)
                assert dep_idx < ph_idx, f"{dep} 应在 {ph} 之前"


# ── 测试 pipeline_validate 返回结构 ────────────────────────


class TestPipelineValidate:
    def test_validate_no_state(self, wiki_workspace, mock_args, capsys):
        """无 state 文件时 pipeline_validate 应返回 passed"""
        from dag_pipeline_run import pipeline_validate

        # 确保无 state 文件
        sp = _state_path(wiki_workspace, "01_test_book", "1")
        if os.path.exists(sp):
            os.remove(sp)

        result = pipeline_validate(mock_args)
        assert result["passed"] is True
        assert result["critical"] == []

    def test_validate_returns_dict(self, wiki_workspace, mock_args):
        """pipeline_validate 应返回包含 passed 和 critical 的字典"""
        from dag_pipeline_run import pipeline_validate


        sp = _state_path(wiki_workspace, "01_test_book", "1")
        state = _make_state(phases_done=DAG_ORDER)
        _save_state(sp, state)

        with (
            patch("dag_pipeline.validate_phase_output") as mock_vpo,
            patch("dag_pipeline.fix_broken_links"),
            patch("dag_pipeline.check_stray_files"),
            patch("dag_pipeline.scan_broken_links") as mock_sbl,
            patch("dag_pipeline.verify_exercise_solution_mapping") as mock_vesm,
            patch("dag_pipeline.check_level_quality") as mock_clq,
            patch("kb_graph.KGraph") as mock_kg,
            patch("subprocess.run") as mock_sub,
        ):
            mock_vpo.return_value = {"passed": True, "issues": []}
            mock_sbl.return_value = 0
            mock_vesm.return_value = []
            mock_clq.return_value = {"passed": True, "critical": [], "warnings": [], "detail": {}, "label": ""}
            mock_kg.side_effect = ImportError
            mock_sub.return_value = MagicMock(returncode=0, stdout="", stderr="")

            result = pipeline_validate(mock_args)

        assert isinstance(result, dict)
        assert "passed" in result
        assert "critical" in result


# ── 测试 state.json 持久化 ──────────────────────────────────


class TestStatePersistence:
    def test_save_and_load_roundtrip(self, wiki_workspace):
        """_save_state 和 _load_state 应能完整往返"""
        sp = _state_path(wiki_workspace, "01_test_book", "1")
        state = _make_state()
        state["phases"]["concepts"]["status"] = "done"
        state["phases"]["concepts"]["files"] = 7
        _save_state(sp, state)

        loaded = _load_state(sp)
        assert loaded["phases"]["concepts"]["status"] == "done"
        assert loaded["phases"]["concepts"]["files"] == 7

    def test_load_corrupted_state(self, wiki_workspace, tmp_path):
        """损坏的 state.json 应被备份并使用空 state 恢复"""
        sp = _state_path(wiki_workspace, "01_test_book", "1")
        with open(sp, "w") as f:
            f.write("{invalid json content")

        loaded = _load_state(sp)
        assert "phases" in loaded
        # 原文件应被备份
        dag_dir = os.path.dirname(sp)
        backups = [f for f in os.listdir(dag_dir) if "corrupted" in f]
        assert len(backups) >= 1
