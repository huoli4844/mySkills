"""config.py + template_assembler.py 单元测试 — v38.0"""

import os

import pytest

# v50.7: 从 test_config_extended.py 合并的测试依赖
from config import (
    _FALLBACK_CONTENT_DEPTH,
    _FALLBACK_SECTION_COUNTS,
    SkillConfig,
    _deep_merge,
    _load_yaml,
    get_config,
    load_config,
    reload_config,
)

pytestmark = pytest.mark.smoke


class TestConfig:
    """测试 config.py 配置加载"""

    def test_get_config_returns_dataclass(self):
        from config import SkillConfig, get_config

        cfg = get_config()
        assert isinstance(cfg, SkillConfig)

    def test_config_has_thresholds(self):
        from config import get_config

        cfg = get_config()
        assert isinstance(cfg.content_depth_thresholds, dict)
        assert len(cfg.content_depth_thresholds) > 0

    def test_config_has_section_counts(self):
        from config import get_config

        cfg = get_config()
        assert isinstance(cfg.section_counts, dict)

    def test_config_has_confidence_levels(self):
        from config import get_config

        cfg = get_config()
        assert isinstance(cfg.confidence_levels, dict)

    def test_config_singleton(self):
        from config import get_config

        cfg1 = get_config()
        cfg2 = get_config()
        assert cfg1 is cfg2  # 单例

    def test_load_config_fallback(self):
        """不存在 YAML 文件时应使用兜底值"""
        from config import load_config

        cfg = load_config("nonexistent_book_xyz")
        assert cfg is not None
        assert len(cfg.content_depth_thresholds) > 0


class TestTemplateAssemblerCore:
    """测试 template_assembler.py 核心函数"""

    def test_verify_definition_empty(self):
        from template_assembler import verify_definition

        assert verify_definition("", "test_concept") is False

    def test_verify_definition_no_marker(self):
        from template_assembler import verify_definition

        assert verify_definition("random text without any marker words at all", "test") is False

    def test_verify_definition_with_marker(self):
        from template_assembler import verify_definition

        result = verify_definition("概念A是指设备在特定环境中正常工作", "概念A")
        assert result is True

    def test_validate_frontmatter_missing_fields(self):
        from template_assembler import validate_frontmatter

        errors = validate_frontmatter({}, "concept_template.md", "test.md")
        assert len(errors) > 0  # 缺少必填字段

    def test_validate_frontmatter_valid(self):
        from template_assembler import validate_frontmatter

        fm = {"name": "test", "type": "concept", "confidence": 0.95}
        errors = validate_frontmatter(fm, "concept_template.md", "test.md")
        assert len(errors) == 0

    def test_validate_frontmatter_bad_confidence(self):
        from template_assembler import validate_frontmatter

        fm = {"name": "test", "type": "concept", "confidence": "0.50"}
        errors = validate_frontmatter(fm, "concept_template.md", "test.md")
        assert any("confidence" in e for e in errors)

    def test_check_placeholders_clean(self):
        from template_assembler import check_placeholders

        assert check_placeholders("clean text", "test.md") == 0

    def test_check_placeholders_dirty(self):
        from template_assembler import check_placeholders

        count = check_placeholders("has {{name}} and {{type}}", "test.md")
        assert count >= 2

    def test_fill_template_basic(self):
        from template_assembler import fill_template

        result = fill_template("Hello {{name}}, welcome to {{place}}", {"name": "World", "place": "Earth"})
        assert "World" in result
        assert "Earth" in result

    def test_fill_template_strips_jinja(self):
        from template_assembler import fill_template

        result = fill_template("{% if x %}content{% endif %}", {"x": "true"})
        assert "{%" not in result
        assert "content" in result

    def test_confidence_levels_registered(self):
        from template_assembler import CONFIDENCE_LEVELS

        assert "concept_template.md" in CONFIDENCE_LEVELS
        assert 0.95 in CONFIDENCE_LEVELS["concept_template.md"]

    def test_required_frontmatter_registered(self):
        from template_assembler import REQUIRED_FRONTMATTER

        for key in REQUIRED_FRONTMATTER:
            assert "name" in REQUIRED_FRONTMATTER[key]
            assert "type" in REQUIRED_FRONTMATTER[key]

    def test_type_quality_checks_structure(self):
        from template_assembler import TYPE_QUALITY_CHECKS

        for _template_name, checks in TYPE_QUALITY_CHECKS.items():
            for severity, check_id, description in checks:
                assert severity in ("critical", "warning")
                assert isinstance(check_id, str)
                assert len(description) > 0


class TestPhaseValidator:
    """测试 phase_validator.py"""

    def test_validate_nonexistent_dir(self):
        from phase_validator import validate_phase_output

        result = validate_phase_output("/nonexistent/path", "concepts", "0")
        assert result["passed"] is True
        assert result["issues"] == []

    def test_validate_empty_dir(self, tmp_path):
        """空目录应通过验证"""
        from phase_validator import validate_phase_output

        concepts_dir = tmp_path / "30_核心概念"
        concepts_dir.mkdir()
        result = validate_phase_output(str(tmp_path), "concepts", "0")
        assert result["passed"] is True


class TestDagUtilsExpanded:
    """测试 dag_utils.py 展开后的函数"""

    def test_state_path(self, tmp_path):
        from dag_utils import _state_path

        result = _state_path(str(tmp_path), "book1", "3")
        assert result.endswith("book1_ch3.json")
        assert os.path.isdir(os.path.dirname(result))

    def test_book_name(self):
        from dag_utils import _book_name

        assert _book_name("01_测试书籍") == "测试书籍"
        assert _book_name("nounderscore") == "nounderscore"

    def test_extract_chapter_num(self):
        from dag_utils import extract_chapter_num

        assert extract_chapter_num("第3章 概述.md") == "3"
        assert extract_chapter_num("3.5") == "3.5"
        assert extract_chapter_num("random.md") == "1"

    def test_validate_md_file_nonexistent(self):
        from dag_utils import validate_md_file

        result = validate_md_file("/nonexistent/file.md")
        assert result["valid"] is False
        assert "不存在" in result["errors"]

    def test_extract_exercises(self):
        from dag_utils import extract_exercises_from_text

        text = """
习题
1. 什么是概念A？
2. 简述其核心要素。
"""
        result = extract_exercises_from_text(text, "test_book", "3")
        assert len(result) >= 1
        assert "第3章" in result[0]["name"]


# ── 从 test_config_extended.py 合并 ──


class TestDeepMerge:
    """深度合并函数测试"""

    def test_flat_merge(self):
        base = {"a": 1, "b": 2}
        override = {"b": 3, "c": 4}
        result = _deep_merge(base, override)
        assert result == {"a": 1, "b": 3, "c": 4}

    def test_nested_merge(self):
        base = {"x": {"a": 1, "b": 2}, "y": 10}
        override = {"x": {"b": 3, "c": 4}}
        result = _deep_merge(base, override)
        assert result == {"x": {"a": 1, "b": 3, "c": 4}, "y": 10}

    def test_override_dict_with_scalar(self):
        """override 用标量覆盖 base 的字典"""
        base = {"x": {"a": 1}}
        override = {"x": "replaced"}
        result = _deep_merge(base, override)
        assert result["x"] == "replaced"

    def test_empty_override(self):
        base = {"a": 1, "b": {"c": 2}}
        result = _deep_merge(base, {})
        assert result == base

    def test_empty_base(self):
        result = _deep_merge({}, {"a": 1})
        assert result == {"a": 1}

    def test_both_empty(self):
        assert _deep_merge({}, {}) == {}

    def test_does_not_mutate_base(self):
        base = {"a": 1}
        override = {"b": 2}
        _deep_merge(base, override)
        assert base == {"a": 1}  # 不应修改原对象

    def test_three_level_deep(self):
        base = {"l1": {"l2": {"l3": "base"}}}
        override = {"l1": {"l2": {"l3": "override"}}}
        result = _deep_merge(base, override)
        assert result["l1"]["l2"]["l3"] == "override"


# ── _load_yaml ──────────────────────────────────────────


class TestLoadYaml:
    """YAML 加载函数测试"""

    def test_nonexistent_file_returns_empty(self):
        result = _load_yaml("/nonexistent/path/config.yaml")
        assert result == {}

    def test_valid_yaml(self, tmp_path):
        path = tmp_path / "test.yaml"
        path.write_text("key: value\nnested:\n  a: 1\n")
        result = _load_yaml(str(path))
        assert result == {"key": "value", "nested": {"a": 1}}

    def test_non_dict_yaml_returns_empty(self, tmp_path):
        """YAML 返回非 dict 时应返回空字典"""
        path = tmp_path / "list.yaml"
        path.write_text("- item1\n- item2\n")
        result = _load_yaml(str(path))
        assert result == {}

    def test_invalid_yaml_returns_empty(self, tmp_path):
        """语法错误的 YAML 应返回空字典（不崩溃）"""
        path = tmp_path / "bad.yaml"
        path.write_text("key: [unclosed\n")
        result = _load_yaml(str(path))
        assert result == {}

    def test_empty_file_returns_empty(self, tmp_path):
        path = tmp_path / "empty.yaml"
        path.write_text("")
        result = _load_yaml(str(path))
        assert result == {}


# ── SkillConfig 数据类 ──────────────────────────────────


class TestSkillConfig:
    """SkillConfig 默认值测试"""

    def test_post_init_fills_defaults(self):
        cfg = SkillConfig()
        assert cfg.content_depth_thresholds == _FALLBACK_CONTENT_DEPTH
        assert cfg.section_counts == _FALLBACK_SECTION_COUNTS

    def test_explicit_values_not_overridden(self):
        custom = {"custom_type": {"min_chars": 100}}
        cfg = SkillConfig(content_depth_thresholds=custom)
        assert cfg.content_depth_thresholds == custom

    def test_confidence_levels_are_sets(self):
        cfg = SkillConfig()
        for key, val in cfg.confidence_levels.items():
            assert isinstance(val, set), f"{key} should be a set, got {type(val)}"


# ── load_config 优先级 ──────────────────────────────────


class TestLoadConfig:
    """load_config 优先级机制"""

    def test_load_without_book_id_uses_fallback(self):
        """无 book_id 时使用兜底值"""
        cfg = load_config()
        assert isinstance(cfg, SkillConfig)
        assert len(cfg.content_depth_thresholds) > 0

    def test_load_with_nonexistent_book_id(self):
        """不存在的 book_id 时使用兜底值（无覆盖文件）"""
        cfg = load_config("nonexistent_book_xyz_12345")
        assert isinstance(cfg, SkillConfig)
        assert cfg.content_depth_thresholds == _FALLBACK_CONTENT_DEPTH

    def test_reload_clears_cache(self):
        """reload_config 应清除全局缓存"""
        cfg1 = get_config()
        reload_config()
        cfg2 = get_config()
        # 重新加载后应该是新的对象（值相同但不是同一个实例）
        assert cfg1 is not cfg2
        assert cfg1.content_depth_thresholds == cfg2.content_depth_thresholds


# ── 兜底配置完整性 ──────────────────────────────────────


class TestFallbackCompleteness:
    """兜底配置数据完整性"""

    def test_content_depth_has_all_types(self):
        expected_types = {"concept", "knowledge-element", "knowledge", "skill", "scenario", "exercise", "solution", "entity"}
        assert expected_types.issubset(set(_FALLBACK_CONTENT_DEPTH.keys()))

    def test_section_counts_has_all_types(self):
        expected_types = {"concept", "knowledge-element", "knowledge", "skill", "scenario", "exercise", "solution"}
        assert expected_types.issubset(set(_FALLBACK_SECTION_COUNTS.keys()))

    def test_each_threshold_has_required_keys(self):
        for type_name, thresholds in _FALLBACK_CONTENT_DEPTH.items():
            assert "min_nonempty_secs" in thresholds, f"{type_name} missing min_nonempty_secs"
            assert "min_body_chars" in thresholds, f"{type_name} missing min_body_chars"
            assert "max_wu_ratio" in thresholds, f"{type_name} missing max_wu_ratio"

    def test_each_section_count_has_total_secs(self):
        for type_name, counts in _FALLBACK_SECTION_COUNTS.items():
            assert "total_secs" in counts, f"{type_name} missing total_secs"
