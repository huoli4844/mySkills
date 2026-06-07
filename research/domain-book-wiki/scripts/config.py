"""config.py — 外置配置加载器

v38.0: 将硬编码在代码中的配置字典外置为 YAML，支持按书籍/领域覆盖。

配置优先级：
  1. configs/{book_id}_overrides.yaml  （书籍级覆盖，可选）
  2. configs/defaults.yaml             （全局默认值）
  3. 代码中的 _FALLBACK                （最终兜底）

用法：
    from config import get_config
    cfg = get_config()
    thresholds = cfg.content_depth_thresholds
    section_counts = cfg.section_counts
    confidence_levels = cfg.confidence_levels
"""

from __future__ import annotations


import os
from dataclasses import dataclass, field
from typing import Any

from log_utils import get_logger

log = get_logger(__name__)

# 尝试导入 yaml（可选依赖）
try:
    import yaml

    _HAS_YAML = True
except ImportError:
    _HAS_YAML = False

# ── 配置目录 ──────────────────────────────────────────────

_SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
_CONFIG_DIR = os.path.join(os.path.dirname(_SKILL_DIR), "configs")


# ── 兜底配置（当 YAML 文件不存在时使用）───────────────────

_FALLBACK_CONTENT_DEPTH = {
    "concept": {"min_nonempty_secs": 12, "min_body_chars": 1200, "max_wu_ratio": 0.2},
    "knowledge-element": {"min_nonempty_secs": 8, "min_body_chars": 1500, "max_wu_ratio": 0.2},
    "knowledge": {"min_nonempty_secs": 16, "min_body_chars": 1600, "max_wu_ratio": 0.2},
    "skill": {"min_nonempty_secs": 14, "min_body_chars": 1500, "max_wu_ratio": 0.2},
    "scenario": {"min_nonempty_secs": 14, "min_body_chars": 1800, "max_wu_ratio": 0.2},
    "exercise": {"min_nonempty_secs": 2, "min_body_chars": 200, "max_wu_ratio": 0.3},
    "solution": {"min_nonempty_secs": 8, "min_body_chars": 2000, "max_wu_ratio": 0.3},
    "entity": {"min_nonempty_secs": 3, "min_body_chars": 300, "max_wu_ratio": 0.2},
}

_FALLBACK_SECTION_COUNTS = {
    "concept": {"total_secs": 17},
    "knowledge-element": {"total_secs": 11},
    "knowledge": {"total_secs": 21},
    "skill": {"total_secs": 18},
    "scenario": {"total_secs": 17},
    "entity": {"total_secs": 5},
    "exercise": {"total_secs": 0},
    "solution": {"total_secs": 15},
}

_FALLBACK_CONFIDENCE_LEVELS = {
    "concept_template.md": [0.95],
    "ke_template.md": [0.85],        # v47.0: KE 专用模板
    "entity_template.md": [0.85],    # v47.0: 实体专用模板
    "knowledge_template.md": [0.85],
    "skill_template.md": [0.75],
    "scenario_template.md": [0.65],
    "eval/exercise": [0.65],
    "eval/solution": [0.65, 0.85],
}


# ── 配置数据类 ────────────────────────────────────────────


@dataclass
class SkillConfig:
    """技能配置容器"""

    content_depth_thresholds: dict[str, dict[str, Any]] = field(default_factory=dict)
    section_counts: dict[str, dict[str, int]] = field(default_factory=dict)
    confidence_levels: dict[str, set[float]] = field(default_factory=dict)

    def __post_init__(self):
        if not self.content_depth_thresholds:
            self.content_depth_thresholds = dict(_FALLBACK_CONTENT_DEPTH)
        if not self.section_counts:
            self.section_counts = dict(_FALLBACK_SECTION_COUNTS)
        if not self.confidence_levels:
            self.confidence_levels = {k: set(v) for k, v in _FALLBACK_CONFIDENCE_LEVELS.items()}


# ── YAML 加载 ────────────────────────────────────────────


def _load_yaml(filepath: str) -> dict[str, Any]:
    """加载 YAML 文件，失败时返回空字典"""
    if not _HAS_YAML:
        return {}
    if not os.path.exists(filepath):
        return {}
    try:
        with open(filepath, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return data if isinstance(data, dict) else {}
    except Exception as e:
        log.warning(f"  ⚠️  配置加载失败 {filepath}: {e}")
        return {}


def _deep_merge(base: dict, override: dict) -> dict:
    """深度合并两个字典，override 覆盖 base"""
    result = dict(base)
    for key, val in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(val, dict):
            result[key] = _deep_merge(result[key], val)
        else:
            result[key] = val
    return result


def load_config(book_id: str | None = None) -> SkillConfig:
    """加载配置。

    优先级：
    1. configs/{book_id}_overrides.yaml（如指定 book_id）
    2. configs/defaults.yaml
    3. 代码内兜底值

    Args:
        book_id: 可选的书籍 ID，用于加载书籍级覆盖

    Returns:
        SkillConfig 实例
    """
    # 加载全局默认
    defaults = _load_yaml(os.path.join(_CONFIG_DIR, "defaults.yaml"))

    # 加载书籍级覆盖
    overrides: dict[str, Any] = {}
    if book_id:
        overrides = _load_yaml(os.path.join(_CONFIG_DIR, f"{book_id}_overrides.yaml"))

    # 合并
    merged = _deep_merge(defaults, overrides)

    # 构建 SkillConfig
    cfg = SkillConfig()

    if "content_depth_thresholds" in merged:
        cfg.content_depth_thresholds = _deep_merge(_FALLBACK_CONTENT_DEPTH, merged["content_depth_thresholds"])

    if "section_counts" in merged:
        cfg.section_counts = _deep_merge(_FALLBACK_SECTION_COUNTS, merged["section_counts"])

    if "confidence_levels" in merged:
        raw_cl = merged["confidence_levels"]
        cfg.confidence_levels = {k: set(v) if isinstance(v, list) else {v} for k, v in raw_cl.items()}

    return cfg


# ── 全局单例 ──────────────────────────────────────────────

_default_config: SkillConfig | None = None


def get_config(book_id: str | None = None) -> SkillConfig:
    """获取配置（全局单例，book_id=None 时缓存复用）。

    Args:
        book_id: 可选的书籍 ID

    Returns:
        SkillConfig 实例
    """
    global _default_config
    if book_id is None:
        if _default_config is None:
            _default_config = load_config()
        return _default_config
    return load_config(book_id)


def reload_config() -> None:
    """强制重新加载配置（用于测试或配置热更新）"""
    global _default_config
    _default_config = None
