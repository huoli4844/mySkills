"""config.py 扩展单元测试 — _deep_merge, _load_yaml, load_config 优先级"""


import pytest
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

pytestmark = pytest.mark.unit


# ── _deep_merge ──────────────────────────────────────────


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
