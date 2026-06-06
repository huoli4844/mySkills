"""schema.py 单元测试 — YAML 校验、schema 加载、错误格式化"""


import pytest
from schema import (
    FILENAME_TYPE_MAP,
    TYPE_SCHEMA_MAP,
    _resolve_type,
    format_errors,
    load_schema,
    load_yaml_file,
    validate_yaml,
)

pytestmark = pytest.mark.unit


# ── _resolve_type ────────────────────────────────────────


class TestResolveType:
    """文件名到类型名映射"""

    def test_concepts_yaml(self):
        assert _resolve_type("concepts.yaml") == "concepts"

    def test_kes_yaml(self):
        assert _resolve_type("kes.yaml") == "kes"

    def test_kps_yaml(self):
        assert _resolve_type("kps.yaml") == "kps"

    def test_sps_yaml(self):
        assert _resolve_type("sps.yaml") == "sps"

    def test_scenes_yaml(self):
        assert _resolve_type("scenes.yaml") == "scenes"

    def test_entities_yaml(self):
        assert _resolve_type("entities.yaml") == "entities"

    def test_json_variants(self):
        assert _resolve_type("concepts.json") == "concepts"
        assert _resolve_type("kes.json") == "kes"

    def test_unknown_filename(self):
        assert _resolve_type("unknown_data.yaml") is None

    def test_path_with_directory(self):
        assert _resolve_type("/some/path/concepts.yaml") == "concepts"


# ── load_schema ──────────────────────────────────────────


class TestLoadSchema:
    """Schema 加载测试"""

    def test_load_known_schema(self):
        """至少 concepts schema 应该存在"""
        try:
            schema = load_schema("concepts")
            assert isinstance(schema, dict)
            assert "items" in schema or "properties" in schema or "$schema" in schema
        except FileNotFoundError:
            pytest.skip("Schema files not present in test environment")

    def test_unknown_type_raises_value_error(self):
        with pytest.raises(ValueError, match="Unknown type"):
            load_schema("nonexistent_type_xyz")

    def test_all_mapped_types_loadable(self):
        """所有映射的类型都应该有对应 schema 文件"""
        for type_name in TYPE_SCHEMA_MAP:
            try:
                schema = load_schema(type_name)
                assert isinstance(schema, dict)
            except FileNotFoundError:
                pytest.skip(f"Schema for {type_name} not found")


# ── validate_yaml (通过临时文件测试) ────────────────────


class TestValidateYaml:
    """YAML 校验逻辑测试"""

    def _write_tmp_yaml(self, tmp_path, content: str, filename: str = "concepts.yaml") -> str:
        """创建临时 YAML 文件"""
        path = tmp_path / filename
        path.write_text(content, encoding="utf-8")
        return str(path)

    def test_unknown_filename_returns_error(self, tmp_path):
        """无法识别的文件名应返回错误"""
        path = self._write_tmp_yaml(tmp_path, "- name: test\n", "unknown_data.yaml")
        errors = validate_yaml(path)
        assert len(errors) >= 1
        assert "Cannot determine" in errors[0]["message"]

    def test_top_level_not_list(self, tmp_path):
        """顶层不是列表应报错"""
        path = self._write_tmp_yaml(tmp_path, "key: value\n", "concepts.yaml")
        errors = validate_yaml(path)
        assert any("Top-level must be a list" in e["message"] for e in errors)

    def test_item_not_dict(self, tmp_path):
        """列表元素不是对象应报错"""
        path = self._write_tmp_yaml(tmp_path, "- just a string\n- another string\n", "concepts.yaml")
        errors = validate_yaml(path)
        assert any("must be an object" in e["message"] for e in errors)

    def test_missing_required_keys(self, tmp_path):
        """缺少必填键应报错"""
        path = self._write_tmp_yaml(tmp_path, "- name: test\n  file: test.md\n", "concepts.yaml")
        errors = validate_yaml(path)
        missing_keys = [e["message"] for e in errors if "missing" in e["message"].lower()]
        # fm and bd should be missing
        assert any("fm" in m for m in missing_keys)
        assert any("bd" in m for m in missing_keys)

    def test_bd_as_string_bug_detected(self, tmp_path):
        """bd 是字符串而非对象时应报 bd-as-string bug"""
        yaml_content = (
            "- name: test\n"
            "  file: test.md\n"
            "  fm:\n"
            "    source_chapter: 1\n"
            "    confidence: 0.9\n"
            "    confidence_note: ok\n"
            "  bd: |\n"
            "    this is a string body\n"
        )
        path = self._write_tmp_yaml(tmp_path, yaml_content, "concepts.yaml")
        errors = validate_yaml(path)
        assert any("bd-as-string" in e["message"] or "must be an object" in e["message"] for e in errors)

    def test_valid_item_minimal(self, tmp_path):
        """一个结构完整的最小 item 应无严重错误"""
        yaml_content = (
            "- name: 测试概念\n"
            "  file: 01_concepts/test.md\n"
            "  fm:\n"
            "    source_chapter: 1\n"
            "    confidence: 0.9\n"
            "    confidence_note: high\n"
            "  bd:\n"
            "    term_english: Test\n"
            "    term_definition: A test concept\n"
        )
        path = self._write_tmp_yaml(tmp_path, yaml_content, "concepts.yaml")
        errors = validate_yaml(path)
        # 可能有一些 bd required field 缺失，但不应有类型错误
        type_errors = [e for e in errors if "must be an object" in e["message"]]
        assert len(type_errors) == 0

    def test_field_alias_normalization(self, tmp_path):
        """v41.0: 字段别名应被自动规范化"""
        yaml_content = (
            "- name: test\n"
            "  file: test.md\n"
            "  fm:\n"
            "    source_chapter: 1\n"
            "    confidence: 0.9\n"
            "    confidence_note: ok\n"
            "  bd:\n"
            "    concept_description: A definition\n"
            "    term_english: Test\n"
        )
        path = self._write_tmp_yaml(tmp_path, yaml_content, "concepts.yaml")
        errors = validate_yaml(path)
        # concept_description 应被映射为 term_definition，不应报 term_definition 缺失
        missing_td = [e for e in errors if "term_definition" in e["message"] and "missing" in e["message"].lower()]
        assert len(missing_td) == 0


# ── format_errors ────────────────────────────────────────


class TestFormatErrors:
    """错误格式化测试"""

    def test_no_errors_message(self):
        result = format_errors([])
        assert "no errors" in result.lower() or "✅" in result

    def test_with_errors(self):
        errors = [
            {"path": "$[0].bd", "message": "bd is wrong", "schema_path": "#/bd", "severity": "error"},
            {"path": "$[1].fm", "message": "fm warning", "schema_path": "", "severity": "warning"},
        ]
        result = format_errors(errors)
        assert "1 errors" in result
        assert "1 warnings" in result
        assert "bd is wrong" in result

    def test_format_preserves_paths(self):
        errors = [{"path": "$[3].name", "message": "missing", "schema_path": "", "severity": "error"}]
        result = format_errors(errors)
        assert "$[3].name" in result


# ── load_yaml_file ───────────────────────────────────────


class TestLoadYamlFile:
    """YAML 文件加载"""

    def test_load_valid_yaml(self, tmp_path):
        path = tmp_path / "test.yaml"
        path.write_text("- name: hello\n  value: 42\n")
        data = load_yaml_file(str(path))
        assert isinstance(data, list)
        assert data[0]["name"] == "hello"
        assert data[0]["value"] == 42

    def test_load_empty_yaml(self, tmp_path):
        path = tmp_path / "empty.yaml"
        path.write_text("")
        data = load_yaml_file(str(path))
        assert data is None  # yaml.safe_load returns None for empty


# ── 常量一致性 ──────────────────────────────────────────


class TestConstants:
    """内部常量一致性检查"""

    def test_all_filename_types_have_schema(self):
        """FILENAME_TYPE_MAP 中的所有类型都应在 TYPE_SCHEMA_MAP 中有 schema"""
        for fname, type_name in FILENAME_TYPE_MAP.items():
            assert type_name in TYPE_SCHEMA_MAP, f"{fname} -> {type_name} has no schema"

    def test_type_schema_map_values_are_strings(self):
        for _k, v in TYPE_SCHEMA_MAP.items():
            assert isinstance(v, str)
            assert v.endswith(".json")
