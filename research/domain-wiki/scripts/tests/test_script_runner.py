"""script_runner.py 单元测试 — ScriptResult, run_script, _extract_json, _resolve_script"""

import json
import os
import tempfile

import pytest
from script_runner import ScriptResult, _extract_json, _resolve_script, run_script

pytestmark = pytest.mark.unit

# ── ScriptResult 数据类 ────────────────────────────────────


class TestScriptResult:
    """ScriptResult 基础属性测试"""

    def test_default_values(self):
        r = ScriptResult()
        assert r.success is False
        assert r.returncode == -1
        assert r.data == {}
        assert r.stdout == ""
        assert r.stderr == ""
        assert r.error_count == 0
        assert r.warn_count == 0
        assert r.elapsed_ms == 0

    def test_success_result(self):
        r = ScriptResult(success=True, returncode=0, data={"items": [1, 2, 3]})
        assert r.success is True
        assert r.returncode == 0
        assert r.data["items"] == [1, 2, 3]

    def test_get_existing_key(self):
        r = ScriptResult(data={"name": "test", "count": 42})
        assert r.get("name") == "test"
        assert r.get("count") == 42

    def test_get_missing_key_default(self):
        r = ScriptResult(data={})
        assert r.get("missing") is None
        assert r.get("missing", "fallback") == "fallback"

    def test_has_errors_true(self):
        r = ScriptResult(error_count=3)
        assert r.has_errors is True

    def test_has_errors_false(self):
        r = ScriptResult(error_count=0)
        assert r.has_errors is False

    def test_items_property(self):
        r = ScriptResult(data={"items": [{"id": 1}, {"id": 2}]})
        assert len(r.items) == 2
        assert r.items[0]["id"] == 1

    def test_items_empty_when_missing(self):
        r = ScriptResult(data={})
        assert r.items == []

    def test_elapsed_ms_set(self):
        r = ScriptResult(elapsed_ms=1500)
        assert r.elapsed_ms == 1500


# ── _extract_json ────────────────────────────────────────


class TestExtractJson:
    """JSON 提取策略测试"""

    def test_whole_line_json(self):
        stdout = '{"errors": 0, "warnings": 2}\n'
        data = _extract_json(stdout)
        assert data["errors"] == 0
        assert data["warnings"] == 2

    def test_json_output_marker(self):
        stdout = "some log output\nJSON_OUTPUT:{\"fail\": 5, \"warn\": 1}\n"
        data = _extract_json(stdout)
        assert data["fail"] == 5
        assert data["warn"] == 1

    def test_last_line_json(self):
        stdout = "Starting...\nProcessing...\n{\"result\": \"ok\", \"count\": 10}\n"
        data = _extract_json(stdout)
        assert data["result"] == "ok"
        assert data["count"] == 10

    def test_no_json_returns_empty(self):
        stdout = "just plain text\nno json here\n"
        data = _extract_json(stdout)
        assert data == {}

    def test_invalid_json_returns_empty(self):
        stdout = "{invalid json content\n"
        data = _extract_json(stdout)
        assert data == {}

    def test_empty_stdout(self):
        data = _extract_json("")
        assert data == {}

    def test_nested_json(self):
        obj = {"items": [{"id": "a"}, {"id": "b"}], "total": 2}
        stdout = json.dumps(obj) + "\n"
        data = _extract_json(stdout)
        assert len(data["items"]) == 2
        assert data["total"] == 2


# ── _resolve_script ──────────────────────────────────────


class TestResolveScript:
    """脚本路径解析测试"""

    def test_absolute_path_unchanged(self):
        abs_path = os.path.abspath("/tmp/test_script.py")
        assert _resolve_script(abs_path) == abs_path

    def test_filename_only_searches_scripts_dir(self):
        result = _resolve_script("schema.py")
        assert result.endswith("scripts/schema.py")

    def test_relative_path_resolved(self):
        # 含路径分隔符的相对路径
        result = _resolve_script("subdir/script.py")
        assert os.path.isabs(result)


# ── run_script ──────────────────────────────────────────


class TestRunScript:
    """run_script 集成测试"""

    def test_nonexistent_script_returns_failure(self):
        r = run_script("nonexistent_script_xyz_12345.py")
        assert r.success is False
        assert r.returncode == -1
        assert "不存在" in r.stderr

    def test_run_python_hello(self):
        """创建一个临时脚本并运行"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, dir=tempfile.gettempdir()) as f:
            f.write('print("hello world")\n')
            f.flush()
            tmp_path = f.name
        try:
            r = run_script(tmp_path)
            assert r.success is True
            assert r.returncode == 0
            assert "hello world" in r.stdout
            assert r.elapsed_ms >= 0
        finally:
            os.unlink(tmp_path)

    def test_run_with_json_mode(self):
        """JSON 模式：脚本输出 JSON，run_script 应解析"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, dir=tempfile.gettempdir()) as f:
            f.write('import json, sys\n')
            f.write('if "--json" in sys.argv:\n')
            f.write('    print(json.dumps({"errors": 0, "warnings": 1, "items": []}))\n')
            f.write('else:\n')
            f.write('    print("no json")\n')
            f.flush()
            tmp_path = f.name
        try:
            r = run_script(tmp_path, json_mode=True)
            assert r.success is True
            assert r.data.get("errors") == 0
            assert r.data.get("warnings") == 1
        finally:
            os.unlink(tmp_path)

    def test_run_failing_script(self):
        """运行退出码非0的脚本"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, dir=tempfile.gettempdir()) as f:
            f.write('import sys\nsys.exit(1)\n')
            f.flush()
            tmp_path = f.name
        try:
            r = run_script(tmp_path)
            assert r.success is False
            assert r.returncode == 1
        finally:
            os.unlink(tmp_path)

    def test_run_with_timeout(self):
        """超时测试"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, dir=tempfile.gettempdir()) as f:
            f.write('import time\ntime.sleep(10)\n')
            f.flush()
            tmp_path = f.name
        try:
            r = run_script(tmp_path, timeout=1)
            assert r.success is False
            assert "超时" in r.stderr
        finally:
            os.unlink(tmp_path)

    def test_run_with_args(self):
        """传递参数给脚本"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, dir=tempfile.gettempdir()) as f:
            f.write('import sys\nprint(" ".join(sys.argv[1:]))\n')
            f.flush()
            tmp_path = f.name
        try:
            r = run_script(tmp_path, args=["hello", "world"])
            assert r.success is True
            assert "hello world" in r.stdout
        finally:
            os.unlink(tmp_path)

    def test_json_mode_with_errors_fails(self):
        """JSON 模式下 errors > 0 时 success 为 False"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, dir=tempfile.gettempdir()) as f:
            f.write('import json\nprint(json.dumps({"errors": 3}))\n')
            f.flush()
            tmp_path = f.name
        try:
            r = run_script(tmp_path, json_mode=True)
            assert r.success is False
            assert r.error_count == 3
        finally:
            os.unlink(tmp_path)
