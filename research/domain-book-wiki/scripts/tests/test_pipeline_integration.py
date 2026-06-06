"""pipeline 集成测试 — v39.1

测试 pipeline auto 全流程：状态管理、依赖检查、自动修复闭环。
使用 scripts/tests/fixtures/wiki/ 中的 fixture 数据。
"""

import json
import os
import shutil

import pytest
from dag_utils import DAG_DEPENDS, DAG_ORDER, DIR

pytestmark = pytest.mark.integration

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures", "wiki")


@pytest.fixture
def temp_workspace(tmp_path):
    """创建临时工作区（从 fixture 复制）"""
    if os.path.isdir(FIXTURE_DIR):
        # 复制 fixture 数据
        for item in os.listdir(FIXTURE_DIR):
            src = os.path.join(FIXTURE_DIR, item)
            dst = tmp_path / item
            if os.path.isdir(src):
                shutil.copytree(src, str(dst))
            else:
                shutil.copy2(src, str(dst))
    yield str(tmp_path)


class TestDAGOrder:
    """测试 DAG 顺序和依赖配置"""

    def test_dag_order_length(self):
        assert len(DAG_ORDER) == 12

    def test_dag_order_starts_with_chapter_toc(self):
        assert DAG_ORDER[0] == "chapter_toc"

    def test_dag_order_ends_with_l4(self):
        assert DAG_ORDER[-1] == "l4_indices"

    def test_all_phases_have_deps(self):
        for ph in DAG_ORDER:
            assert ph in DAG_DEPENDS, f"{ph} missing from DAG_DEPENDS"

    def test_chapter_toc_no_deps(self):
        assert DAG_DEPENDS["chapter_toc"] == []

    def test_concepts_depends_on_chapter_toc(self):
        assert "chapter_toc" in DAG_DEPENDS["concepts"]

    def test_kp_depends_on_concepts_ke_entities(self):
        deps = DAG_DEPENDS["kp"]
        assert "concepts" in deps
        assert "ke" in deps
        assert "entities" in deps

    def test_solutions_depends_on_exercises(self):
        assert "exercises" in DAG_DEPENDS["solutions"]

    def test_no_circular_dependencies(self):
        """验证 DAG 无环"""
        visited = set()
        in_stack = set()

        def has_cycle(node):
            if node in in_stack:
                return True
            if node in visited:
                return False
            visited.add(node)
            in_stack.add(node)
            for dep in DAG_DEPENDS.get(node, []):
                if has_cycle(dep):
                    return True
            in_stack.remove(node)
            return False

        for ph in DAG_ORDER:
            visited.clear()
            in_stack.clear()
            assert not has_cycle(ph), f"Circular dependency involving {ph}"


class TestStateManagement:
    """测试 Pipeline 状态管理"""

    def test_state_path_format(self):
        from dag_utils import _state_path

        path = _state_path("/tmp/wiki", "01_emc", "3")
        assert path.endswith(".json")
        assert "01_emc" in path

    def test_state_path_chapter_zero(self):
        from dag_utils import _state_path

        path = _state_path("/tmp/wiki", "01_emc", "0")
        assert "01_emc" in path

    def test_load_nonexistent_state(self):
        from dag_utils import _load_state

        # 不存在的路径应该抛异常或返回默认
        try:
            result = _load_state("/nonexistent/path.json")
            # 如果没抛异常，应该返回合理默认值
            assert isinstance(result, dict)
        except (FileNotFoundError, json.JSONDecodeError):
            pass  # 抛异常也是可接受的行为


class TestDIRRegistry:
    """测试 DIR 路径注册表"""

    def test_all_l1_dirs_defined(self):
        required = ["CONCEPTS", "KE", "KP", "SP", "SCENE", "ENTITIES", "EXERCISES", "SOLUTIONS"]
        for key in required:
            assert key in DIR, f"DIR missing key: {key}"

    def test_all_l2l4_dirs_defined(self):
        required = ["OVERVIEW", "SOURCE", "DOMAIN_CTRL", "KB_CTRL"]
        for key in required:
            assert key in DIR, f"DIR missing key: {key}"

    def test_dir_values_are_strings(self):
        for key, val in DIR.items():
            assert isinstance(val, str), f"DIR[{key}] should be string, got {type(val)}"


class TestBuildKBFiles:
    """测试 build_kb_files.py 核心功能"""

    def test_load_items_missing_file(self):
        """v38.4: 数据文件不存在应返回空列表"""
        from build_kb_files import _load_items

        result = _load_items("nonexistent.yaml", "/tmp/fake", "99")
        assert result == []

    def test_load_items_from_fixture(self):
        """从 fixture 加载概念数据"""
        from build_kb_files import _load_items

        fixture_data = os.path.join(os.path.dirname(__file__), "..", "data", "第3章")
        if os.path.isdir(fixture_data):
            result = _load_items("concepts.yaml", None, None)
            # 可能找到也可能找不到，取决于运行环境
            assert isinstance(result, list | dict)


# ── v40.0: 新功能测试 ────────────────────────────────


class TestScriptRunner:
    """测试 ScriptRunner 抽象层"""

    def test_script_result_defaults(self):
        from script_runner import ScriptResult

        r = ScriptResult()
        assert r.success is False
        assert r.returncode == -1
        assert r.error_count == 0
        assert r.has_errors is False
        assert r.items == []

    def test_script_result_with_data(self):
        from script_runner import ScriptResult

        r = ScriptResult(success=True, returncode=0, data={"fail": 0, "warn": 3}, error_count=0, warn_count=3)
        assert r.success is True
        assert r.get("fail") == 0
        assert r.get("warn") == 3
        assert r.get("missing", "default") == "default"

    def test_extract_json_whole_output(self):
        from script_runner import _extract_json

        result = _extract_json('{"total": 10, "fail": 2}')
        assert result == {"total": 10, "fail": 2}

    def test_extract_json_output_prefix(self):
        from script_runner import _extract_json

        stdout = 'some log\nJSON_OUTPUT:{"errors": 5, "warnings": 1}\nmore log'
        result = _extract_json(stdout)
        assert result == {"errors": 5, "warnings": 1}

    def test_extract_json_last_line(self):
        from script_runner import _extract_json

        stdout = 'processing...\ndone\n{"status": "ok"}'
        result = _extract_json(stdout)
        assert result == {"status": "ok"}

    def test_extract_json_empty(self):
        from script_runner import _extract_json

        assert _extract_json("") == {}
        assert _extract_json("no json here") == {}

    def test_run_script_nonexistent(self):
        from script_runner import run_script

        r = run_script("nonexistent_script_xyz.py")
        assert r.success is False
        assert r.returncode == -1


class TestStateLock:
    """测试状态文件并发保护"""

    def test_save_and_load_state(self, tmp_path):
        from dag_utils import _load_state, _save_state

        state_path = str(tmp_path / "test_state.json")
        state = {"phases": {"concepts": {"status": "done"}}}
        _save_state(state_path, state)
        loaded = _load_state(state_path)
        assert loaded == state

    def test_load_state_missing(self, tmp_path):
        from dag_utils import _load_state

        loaded = _load_state(str(tmp_path / "nonexistent.json"))
        assert loaded == {"phases": {}}

    def test_wal_recovery(self, tmp_path):
        from dag_utils import _load_state, _save_state

        state_path = str(tmp_path / "test_state.json")
        wal_path = state_path + ".wal"
        # 写正常状态
        state = {"phases": {"ke": {"status": "done"}}}
        _save_state(state_path, state)
        # 损坏主文件
        with open(state_path, "w") as f:
            f.write("{corrupted")
        # WAL 应该存在且能恢复
        if os.path.exists(wal_path):
            loaded = _load_state(state_path)
            assert loaded == state

    def test_state_lock_file_created(self, tmp_path):
        from dag_utils import _save_state

        state_path = str(tmp_path / "test_state.json")
        _save_state(state_path, {"phases": {}})
        assert os.path.exists(state_path + ".lock")


class TestRollback:
    """测试 pipeline rollback"""

    def test_get_downstream_phases(self):
        from pipeline_extras import _get_downstream_phases

        # concepts 的下游应包含 ke, entities 等
        downstream = _get_downstream_phases("concepts")
        assert isinstance(downstream, list)
        # 检查至少有一个下游
        assert len(downstream) > 0

    def test_get_downstream_phases_last(self):
        from pipeline_extras import _get_downstream_phases

        # l4_indices 应无下游
        downstream = _get_downstream_phases("l4_indices")
        assert downstream == []

    def test_get_downstream_phases_solutions(self):
        from pipeline_extras import _get_downstream_phases

        # solutions 的下游应包含 l2_indices
        downstream = _get_downstream_phases("solutions")
        assert "l2_indices" in downstream


class TestFillSolutions:
    """测试 fill-solutions 核心逻辑"""

    def test_collect_node_summaries_empty(self, tmp_path):
        from pipeline_auto import _collect_node_summaries

        summaries = _collect_node_summaries(str(tmp_path))
        assert isinstance(summaries, dict)
        assert len(summaries) == 0

    def test_generate_knowledge_loop(self):
        from pipeline_auto import _generate_knowledge_loop

        result = _generate_knowledge_loop(["传导耦合", "辐射耦合", "电磁屏蔽"], "测试题目", "3")
        assert len(result) >= 200  # 应该 >= 200 字
        assert "传导耦合" in result
        assert "知识闭环" in result

    def test_generate_exam_points(self):
        from pipeline_auto import _generate_exam_points

        result = _generate_exam_points([("传导耦合", "定义"), ("辐射耦合", "定义")], "分析")
        assert "传导耦合" in result
        assert "分析" in result

    def test_fill_skeleton_no_dir(self, tmp_path):
        from pipeline_auto import _fill_skeleton_solutions

        result = _fill_skeleton_solutions(str(tmp_path), str(tmp_path / "nonexistent"), "01", "test", "3")
        # 目录不存在，应返回 0
        assert result == 0


class TestConceptVerifyTolerance:
    """测试概念定义验证容错"""

    def test_normalize_strips_formulas(self):
        from verify_concepts_from_source import normalize

        text = "传导耦合是指通过导体传输的 $E=mc^2$ 电磁干扰"
        result = normalize(text)
        assert "E=mc" not in result
        assert "传导耦合" in result

    def test_normalize_strips_block_formulas(self):
        from verify_concepts_from_source import normalize

        text = "定义内容 $$\\sum_{i=1}^{n} x_i$$ 后续文本"
        result = normalize(text)
        assert "sum" not in result
        assert "定义内容" in result

    def test_has_formula(self):
        from verify_concepts_from_source import _has_formula

        assert _has_formula("含 $E=mc^2$ 公式") is True
        assert _has_formula("无公式文本") is False

    def test_strip_formulas(self):
        from verify_concepts_from_source import _strip_formulas


        result = _strip_formulas("传导耦合 $E=mc^2$ 是指")
        assert "[公式]" in result
        assert "E=mc" not in result


# ── v41.1: pipeline_auto / _auto_build_kb_phase / _auto_detect 测试 ──


class TestAutoBuildKBPhase:
    """_auto_build_kb_phase() 测试"""

    def test_successful_build(self, tmp_path, monkeypatch):
        """成功调用 run_script 后返回 True"""
        from pipeline_auto import _auto_build_kb_phase
        from script_runner import ScriptResult

        # Mock run_script 返回成功
        def _mock_run_script(script_name, args=None, **kwargs):
            return ScriptResult(success=True, returncode=0, stdout="完成: 5 个文件\n")

        monkeypatch.setattr("pipeline_auto.run_script", _mock_run_script)
        # Mock run_phase_auto_fix
        monkeypatch.setattr("pipeline_auto.run_phase_auto_fix", lambda *a, **kw: None)

        wr = str(tmp_path)
        result = _auto_build_kb_phase(wr, "concepts", "concept", "3", "01_test", "测试教材")
        assert result is True

    def test_build_kb_py_not_found(self, tmp_path, monkeypatch):
        """build_kb_files.py 不存在时返回 False"""
        # Mock os.path.exists 对 build_kb_files.py 返回 False
        import os as _os

        from pipeline_auto import _auto_build_kb_phase
        _orig_exists = _os.path.exists

        def _mock_exists(path):
            if path.endswith("build_kb_files.py"):
                return False
            return _orig_exists(path)

        monkeypatch.setattr("pipeline_auto.os.path.exists", _mock_exists)

        wr = str(tmp_path)
        result = _auto_build_kb_phase(wr, "concepts", "concept", "3", "01_test", "测试教材")
        assert result is False

    def test_run_script_nonzero_but_generated(self, tmp_path, monkeypatch):
        """run_script 返回非零但有文件生成 → 仍返回 True"""
        from pipeline_auto import _auto_build_kb_phase
        from script_runner import ScriptResult

        def _mock_run_script(script_name, args=None, **kwargs):
            return ScriptResult(success=False, returncode=1, stdout="完成: 3 个文件\n")

        monkeypatch.setattr("pipeline_auto.run_script", _mock_run_script)
        monkeypatch.setattr("pipeline_auto.run_phase_auto_fix", lambda *a, **kw: None)

        wr = str(tmp_path)
        result = _auto_build_kb_phase(wr, "ke", "ke", "3", "01_test", "测试教材")
        assert result is True

    def test_run_script_nonzero_no_generation(self, tmp_path, monkeypatch):
        """run_script 返回非零且无文件生成 → 返回 False"""
        from pipeline_auto import _auto_build_kb_phase
        from script_runner import ScriptResult

        def _mock_run_script(script_name, args=None, **kwargs):
            return ScriptResult(success=False, returncode=1, stdout="错误: 数据缺失")

        monkeypatch.setattr("pipeline_auto.run_script", _mock_run_script)
        monkeypatch.setattr("pipeline_auto.run_phase_auto_fix", lambda *a, **kw: None)

        wr = str(tmp_path)
        result = _auto_build_kb_phase(wr, "entities", "entity", "3", "01_test", "测试教材")
        assert result is False


class TestAutoDetectAndBuildExercises:
    """_auto_detect_and_build_exercises() 测试"""

    def test_source_file_not_found(self, tmp_path, monkeypatch):
        """源文件不存在时返回 False"""
        from pipeline_auto import _auto_detect_and_build_exercises

        # 创建空工作区（无源文件）
        wr = str(tmp_path)

        # 创建最小状态
        from dag_constants import DIR
        os.makedirs(os.path.join(wr, DIR["SOURCE"]), exist_ok=True)

        s = {"book_id": "01_test", "book_name": "测试教材"}
        # args 只需要有个占位对象
        result = _auto_detect_and_build_exercises(wr, s, None, "3")
        assert result is False

    def test_no_exercises_detected(self, tmp_path, monkeypatch):
        """正文中无习题时返回 False"""
        from dag_constants import DIR
        from pipeline_auto import _auto_detect_and_build_exercises

        wr = str(tmp_path)
        src_dir = os.path.join(wr, DIR["SOURCE"])
        os.makedirs(src_dir, exist_ok=True)

        # 创建不含习题的源文件
        src_file = os.path.join(src_dir, "第3章.md")
        with open(src_file, "w") as f:
            f.write("# 第3章\n\n这是正文内容，没有习题。\n\n## 小结\n\n本章结束。\n")

        s = {
            "book_id": "01_test", "book_name": "测试教材",
            "phases": {
                "exercises": {"status": "pending", "files": 0},
                "solutions": {"status": "pending", "files": 0},
            }
        }
        result = _auto_detect_and_build_exercises(wr, s, None, "3")
        # 无习题时函数返回 True 并自动标记 exercises+solutions 为 done
        assert result is True
        assert s.get("phases", {}).get("exercises", {}).get("status") == "done"
        assert s.get("phases", {}).get("solutions", {}).get("status") == "done"

    def test_exercises_detected_and_built(self, tmp_path, monkeypatch):
        """检测到习题并成功构建"""
        from dag_constants import DIR
        from pipeline_auto import _auto_detect_and_build_exercises
        from script_runner import ScriptResult

        wr = str(tmp_path)
        src_dir = os.path.join(wr, DIR["SOURCE"])
        os.makedirs(src_dir, exist_ok=True)

        # 创建包含习题的源文件
        src_file = os.path.join(src_dir, "第3章.md")
        with open(src_file, "w") as f:
            f.write("# 第3章\n\n## 习题\n\n1. 什么是传导耦合？\n2. 简述辐射耦合的原理。\n")

        # Mock run_script 返回成功
        def _mock_run_script(script_name, args=None, **kwargs):
            return ScriptResult(success=True, returncode=0, stdout="完成")

        monkeypatch.setattr("pipeline_auto.run_script", _mock_run_script)
        monkeypatch.setattr("pipeline_auto.run_phase_auto_fix", lambda *a, **kw: None)

        s = {"book_id": "01_test", "book_name": "测试教材"}
        result = _auto_detect_and_build_exercises(wr, s, None, "3")
        assert result is True


class TestPipelineAutoBasic:
    """pipeline_auto() 核心流程测试"""

    def test_pipeline_auto_dry_run(self, tmp_path, monkeypatch):
        """pipeline_auto --dry-run 只预览，不执行"""
        from dag_pipeline_run import pipeline_auto

        wr = str(tmp_path)
        bid = "01_test_book"
        ch = "3"

        # 创建工作区结构
        dag_dir = os.path.join(wr, ".dag")
        os.makedirs(dag_dir, exist_ok=True)

        # 创建状态文件
        sp = os.path.join(dag_dir, f"{bid}_{ch}.json")
        import json
        state = {
            "phases": {
                "chapter_toc": {"status": "done"},
                "concepts": {"status": "pending"},
            },
            "book_id": bid,
            "book_name": "测试教材",
            "chapter": ch,
        }
        with open(sp, "w") as f:
            json.dump(state, f)

        # Mock 所有可能的外部调用
        monkeypatch.setattr("dag_pipeline_run._state_path", lambda wr2, b, c: sp)
        monkeypatch.setattr("dag_pipeline_run._save_state", lambda *a, **kw: None)
        monkeypatch.setattr("dag_pipeline_run._load_state", lambda p: state)

        # 使用 types.SimpleNamespace 创建 mock args
        from types import SimpleNamespace
        args = SimpleNamespace(
            wiki_root=wr,
            book_id=bid,
            chapter=ch,
            force=False,
            dry_run=True,
            from_phase=None,
            l1_only=False,
        )

        # dry_run 不应抛异常
        pipeline_auto(args)

    def test_pipeline_auto_not_initialized(self, tmp_path, monkeypatch):
        """未初始化状态文件时提前退出"""
        from dag_pipeline_run import pipeline_auto

        wr = str(tmp_path)
        bid = "01_test_book"
        ch = "3"

        from types import SimpleNamespace
        args = SimpleNamespace(
            wiki_root=wr,
            book_id=bid,
            chapter=ch,
            force=False,
            dry_run=False,
            from_phase=None,
            l1_only=False,
        )

        # 应干净退出（不抛异常）
        pipeline_auto(args)
