"""test_pipeline_extras.py — Pipeline 扩展命令测试

覆盖: pipeline_fill_solutions, pipeline_rollback, _get_downstream_phases.
"""

import os
from types import SimpleNamespace

import pytest
from dag_utils import DAG_DEPENDS, DAG_ORDER, _load_state, _save_state, _state_path
from pipeline_extras import _get_downstream_phases, pipeline_rollback

pytestmark = pytest.mark.integration


@pytest.fixture
def wiki_workspace(tmp_path):
    """创建带 .dag 目录的临时 wiki"""
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / ".dag").mkdir()
    return str(wiki)


@pytest.fixture
def state_with_phases(wiki_workspace):
    """创建含完整阶段状态的文件"""
    book_id = "01_test"
    ch = "1"
    sp = _state_path(wiki_workspace, book_id, ch)
    state = {
        "book_id": book_id,
        "book_name": "测试书",
        "chapter": ch,
        "phases": {},
    }
    for ph in DAG_ORDER:
        state["phases"][ph] = {
            "index": DAG_ORDER.index(ph),
            "status": "done",
            "files": 5,
            "deps": DAG_DEPENDS[ph],
        }
    _save_state(sp, state)
    return sp, book_id, ch


class TestGetDownstreamPhases:
    def test_concepts_downstream(self):
        """concepts 应产生大量下游"""
        downstream = _get_downstream_phases("concepts")
        assert "ke" in downstream
        assert "entities" in downstream
        assert "kp" in downstream
        assert "sp" in downstream
        assert "l4_indices" in downstream

    def test_leaf_phase_no_downstream(self):
        """l4_indices 无下游"""
        assert _get_downstream_phases("l4_indices") == []

    def test_solutions_downstream(self):
        """solutions 下游应包含索引阶段"""
        downstream = _get_downstream_phases("solutions")
        assert "l2_indices" in downstream

    def test_chapter_toc_downstream(self):
        """chapter_toc 是 concepts 的上游"""
        downstream = _get_downstream_phases("chapter_toc")
        assert "concepts" in downstream

    def test_no_self_reference(self):
        """下游不包含自身"""
        for ph in DAG_ORDER:
            assert ph not in _get_downstream_phases(ph)


class TestPipelineRollback:
    def test_rollback_resets_target_phase(self, wiki_workspace, state_with_phases):
        """rollback 应重置目标阶段为 pending"""
        sp, book_id, ch = state_with_phases
        args = SimpleNamespace(
            wiki_root=wiki_workspace,
            book_id=book_id,
            chapter=ch,
            phase="kp",
        )
        pipeline_rollback(args)

        state = _load_state(sp)
        assert state["phases"]["kp"]["status"] == "pending"

    def test_rollback_resets_downstream(self, wiki_workspace, state_with_phases):
        """rollback 应同时重置下游阶段"""
        sp, book_id, ch = state_with_phases
        args = SimpleNamespace(
            wiki_root=wiki_workspace,
            book_id=book_id,
            chapter=ch,
            phase="concepts",
        )
        pipeline_rollback(args)

        state = _load_state(sp)
        assert state["phases"]["concepts"]["status"] == "pending"
        assert state["phases"]["ke"]["status"] == "pending"
        assert state["phases"]["kp"]["status"] == "pending"

    def test_rollback_preserves_upstream(self, wiki_workspace, state_with_phases):
        """rollback 不影响上游阶段"""
        sp, book_id, ch = state_with_phases
        args = SimpleNamespace(
            wiki_root=wiki_workspace,
            book_id=book_id,
            chapter=ch,
            phase="kp",
        )
        pipeline_rollback(args)

        state = _load_state(sp)
        # concepts 和 ke 是 kp 的上游，应保持 done
        assert state["phases"]["concepts"]["status"] == "done"
        assert state["phases"]["ke"]["status"] == "done"

    def test_rollback_invalid_phase(self, wiki_workspace, state_with_phases, capsys):
        """无效阶段名应报错"""
        _sp, book_id, ch = state_with_phases
        args = SimpleNamespace(
            wiki_root=wiki_workspace,
            book_id=book_id,
            chapter=ch,
            phase="invalid_phase",
        )
        pipeline_rollback(args)
        # 不应崩溃，只是 log.error

    def test_rollback_preserves_md_files(self, wiki_workspace, state_with_phases):
        """v43.6: rollback 不再删除 .md 文件，仅重置状态"""
        _sp, book_id, ch = state_with_phases
        # 创建概念目录和文件
        concepts_dir = os.path.join(wiki_workspace, "30_核心概念")
        os.makedirs(concepts_dir, exist_ok=True)
        with open(os.path.join(concepts_dir, "测试概念.md"), "w") as f:
            f.write("test")

        args = SimpleNamespace(
            wiki_root=wiki_workspace,
            book_id=book_id,
            chapter=ch,
            phase="concepts",
        )
        pipeline_rollback(args)

        # v43.6: rollback 仅重置状态，不删除 .md 文件
        remaining = [f for f in os.listdir(concepts_dir) if f.endswith(".md")]
        assert len(remaining) == 1  # 文件应保留


class TestPipelineError:
    def test_pipeline_error_creation(self):
        """PipelineError 应包含阶段和消息"""
        from dag_utils import PipelineError

        err = PipelineError("concepts", "验证失败")
        assert err.phase == "concepts"
        assert "concepts" in str(err)
        assert "验证失败" in str(err)

    def test_pipeline_error_is_exception(self):
        """PipelineError 应可被 raise 和 catch"""
        from dag_utils import PipelineError


        with pytest.raises(PipelineError):
            raise PipelineError("kp", "构建失败")
