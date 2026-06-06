"""config.py + template_assembler.py 单元测试 — v38.0"""

import os

import pytest

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
