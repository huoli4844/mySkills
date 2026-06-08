"""
dag_utils.py — 兼容 shim

v42.0 拆分: dag_utils → dag_state (状态管理) + dag_constants (常量/异常)

本文件作为向后兼容层，从 dag_state 和 dag_constants re-export 所有符号，
使已有 import 语句无需修改。

迁移路线：新代码应直接导入 dag_state / dag_constants。
本 shim 在下一个大版本重构时删除。
"""

# ── 从 dag_constants 导入 ──────────────────────────────────
from dag_constants import (
    DAG_DEPENDS,
    DAG_ORDER,
    DIR,
    LEVEL_QUALITY_CHECKS,
    PipelineError,
)

# ── 从 dag_state 导入 ──────────────────────────────────────
from dag_state import (
    _book_name,
    _load_state,
    _phase_dir,
    _phase_latest_mtime,
    _save_state,
    _state_path,
    PipelineLock,
    extract_chapter_num,
    extract_exercises_from_text,
    validate_md_file,
    verify_exercise_solution_mapping,
)

__all__ = [
    "DAG_DEPENDS",
    "DAG_ORDER",
    "DIR",
    "LEVEL_QUALITY_CHECKS",
    "PipelineError",
    "PipelineLock",
    "_book_name",
    "_load_state",
    "_phase_dir",
    "_phase_latest_mtime",
    "_save_state",
    "_state_path",
    "extract_chapter_num",
    "extract_exercises_from_text",
    "validate_md_file",
    "verify_exercise_solution_mapping",
]
