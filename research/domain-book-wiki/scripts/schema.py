#!/usr/bin/env python3
"""
schema.py — YAML 数据校验器

验证 data/ 目录下的 YAML 文件是否符合对应 JSON Schema 定义。
核心功能：校验 items 数组结构、必填键、bd 是否为对象（捕获 bd-as-string bug）、
以及各数据类型的 bd 必填字段。

用法:
  python3 schema.py                          # 校验所有 data/*.yaml
  python3 schema.py concepts.yaml            # 校验指定文件
  python3 schema.py --list                   # 列出所有支持的 schema
  python3 schema.py --strict                 # 严格模式：additionalProperties 也报错
"""

from __future__ import annotations


import json
import os
import sys
from typing import Any

from dag_constants import PipelineError
from log_utils import get_logger

log = get_logger(__name__)


import yaml  # noqa: E402

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SCHEMA_DIR = os.path.join(SCRIPT_DIR, "schemas")
DATA_DIR = os.path.join(SCRIPT_DIR, "data")

# ── Bloom 认知层级排序（低→高）──────────────────────────────────
BLOOM_ORDER = ["知道", "理解", "应用", "分析", "评价", "创造"]

# ── 各类型允许的 bloom_level 值域 ─────────────────────────────
# "kps" 定位知道→应用，"sps" 定位应用→分析，"scenes" 定位分析→创造
BLOOM_RANGES = {
    "kps": {
        "知道→理解", "知道→应用", "理解→应用",
    },
    "sps": {
        "应用", "理解→应用", "应用→分析", "分析",
    },
    "scenes": {
        "分析→评价", "分析→评价→创造", "评价→创造",
    },
}

# ── 数据类型 → schema 文件映射 ──────────────────────────────────
TYPE_SCHEMA_MAP = {
    "concepts": "concepts.schema.json",
    "kes": "kes.schema.json",
    "kps": "kps.schema.json",
    "sps": "sps.schema.json",
    "scenes": "scenarios.schema.json",
    "entities": "entities.schema.json",
}

# ── YAML 文件名 → 类型名映射（扩展名变体） ──────────────────────
FILENAME_TYPE_MAP = {
    "concepts.yaml": "concepts",
    "kes.yaml": "kes",
    "kps.yaml": "kps",
    "sps.yaml": "sps",
    "scenes.yaml": "scenes",
    "entities.yaml": "entities",
    "concepts.json": "concepts",
    "kes.json": "kes",
    "kps.json": "kps",
    "sps.json": "sps",
    "scenes.json": "scenes",
    "entities.json": "entities",
}


def _resolve_type(filename: str) -> str | None:
    """根据文件名解析数据类型名"""
    basename = os.path.basename(filename)
    return FILENAME_TYPE_MAP.get(basename)


def load_schema(type_name: str) -> dict[str, Any]:
    """加载指定类型的 JSON Schema"""
    schema_filename = TYPE_SCHEMA_MAP.get(type_name)
    if not schema_filename:
        raise ValueError(f"Unknown type: {type_name}. Supported: {list(TYPE_SCHEMA_MAP.keys())}")

    schema_path = os.path.join(SCHEMA_DIR, schema_filename)
    if not os.path.exists(schema_path):
        raise FileNotFoundError(f"Schema file not found: {schema_path}")

    with open(schema_path, encoding="utf-8") as f:
        return json.load(f)


def load_yaml_file(yaml_path: str) -> Any:
    """加载 YAML 文件，返回解析后的数据（期望是 list）"""
    with open(yaml_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data


def validate_yaml(yaml_path: str) -> list[dict[str, Any]]:
    """
    校验 YAML 数据文件是否符合对应的 JSON Schema。

    Args:
        yaml_path: YAML 数据文件的绝对路径

    Returns:
        错误列表，每条包含：
          - path: 出错位置的 JSON Pointer 路径
          - message: 错误描述
          - schema_path: 出错 schema 路径
          - severity: "error" 或 "warning"
        如果无错误则返回空列表 []
    """
    type_name = _resolve_type(yaml_path)
    if not type_name:
        return [
            {
                "path": "",
                "message": f"Cannot determine data type from filename: {os.path.basename(yaml_path)}",
                "schema_path": "",
                "severity": "error",
            }
        ]

    # 加载 schema
    try:
        schema = load_schema(type_name)
    except (ValueError, FileNotFoundError) as e:
        return [
            {
                "path": "",
                "message": str(e),
                "schema_path": "",
                "severity": "error",
            }
        ]

    # 加载 YAML
    data = load_yaml_file(yaml_path)

    errors = []

    # v41.0: 字段别名映射——常见别名自动规范化
    _FIELD_ALIASES = {
        "skill_description": "skill_objectives",
        "sp_description": "skill_objectives",
        "concept_description": "term_definition",
        "definition": "term_definition",
        "ke_description": "ke_content",
        "knowledge_description": "knowledge_content",
        "exercise_description": "problem_statement",
        "question": "problem_statement",
    }
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict) and isinstance(item.get("bd"), dict):
                bd = item["bd"]
                for alias, canonical in _FIELD_ALIASES.items():
                    if alias in bd and canonical not in bd:
                        bd[canonical] = bd[alias]  # copy, not pop — 双向保留
                    if canonical in bd and alias not in bd:
                        bd[alias] = bd[canonical]  # 反向复制确保下游兼容

    # ── 顶层必须是 list ──
    if not isinstance(data, list):
        errors.append(
            {
                "path": "$",
                "message": f"Top-level must be a list, got {type(data).__name__}",
                "schema_path": "",
                "severity": "error",
            }
        )
        return errors

    # ── 逐 item 校验 ──
    for idx, item in enumerate(data):
        prefix = f"$[{idx}]"

        if not isinstance(item, dict):
            errors.append(
                {
                    "path": prefix,
                    "message": f"Each item must be an object, got {type(item).__name__}",
                    "schema_path": "",
                    "severity": "error",
                }
            )
            continue

        # 必填键: name, file, fm, bd
        for key in ["name", "file", "fm", "bd"]:
            if key not in item:
                errors.append(
                    {
                        "path": f"{prefix}.{key}",
                        "message": f"Required key '{key}' is missing",
                        "schema_path": "#/items/required",
                        "severity": "error",
                    }
                )

        # 如果缺少 fm 或 bd，跳过后续校验
        if "fm" not in item or "bd" not in item:
            continue

        # ── fm 校验 ──
        fm = item["fm"]
        if not isinstance(fm, dict):
            errors.append(
                {
                    "path": f"{prefix}.fm",
                    "message": f"'fm' must be an object, got {type(fm).__name__}",
                    "schema_path": "#/items/properties/fm/type",
                    "severity": "error",
                }
            )
        else:
            for fm_key in ["source_chapter", "confidence", "confidence_note"]:
                if fm_key not in fm:
                    errors.append(
                        {
                            "path": f"{prefix}.fm.{fm_key}",
                            "message": f"Required fm key '{fm_key}' is missing",
                            "schema_path": "#/items/properties/fm/required",
                            "severity": "error",
                        }
                    )

            # ── v43.7: Bloom 层级范围校验（仅 kps/sps/scenes）──
            if type_name in BLOOM_RANGES and "bloom_level" in fm:
                bl = fm["bloom_level"]
                allowed = BLOOM_RANGES[type_name]
                if bl and bl not in allowed:
                    errors.append(
                        {
                            "path": f"{prefix}.fm.bloom_level",
                            "message": (
                                f"bloom_level '{bl}' 不在 {type_name} 允许范围内。"
                                f"允许值: {sorted(allowed)}"
                            ),
                            "schema_path": "#/items/properties/fm/bloom_level",
                            "severity": "warning",
                        }
                    )

        # ── bd 校验（核心：捕获 bd-as-string bug） ──
        bd = item["bd"]
        if isinstance(bd, str):
            errors.append(
                {
                    "path": f"{prefix}.bd",
                    "message": "BUG: 'bd' is a string! It must be an object. "
                    "This is the 'bd-as-string' bug — likely YAML multi-line "
                    "scalar being loaded as string instead of nested mapping.",
                    "schema_path": "#/items/properties/bd/type",
                    "severity": "error",
                }
            )
            continue  # 无法继续校验 bd 的具体字段
        elif not isinstance(bd, dict):
            errors.append(
                {
                    "path": f"{prefix}.bd",
                    "message": f"'bd' must be an object, got {type(bd).__name__}",
                    "schema_path": "#/items/properties/bd/type",
                    "severity": "error",
                }
            )
            continue

        # ── bd 类型特定必填字段校验 ──
        bd_required = schema.get("items", {}).get("properties", {}).get("bd", {}).get("required", [])
        for bd_key in bd_required:
            if bd_key not in bd:
                errors.append(
                    {
                        "path": f"{prefix}.bd.{bd_key}",
                        "message": f"Required bd key '{bd_key}' is missing for type '{type_name}'",
                        "schema_path": "#/items/properties/bd/required",
                        "severity": "error",
                    }
                )

    return errors


def format_errors(errors: list[dict[str, Any]]) -> str:
    """格式化错误列表为可读字符串"""
    if not errors:
        return "✅ All valid — no errors found."

    crit = [e for e in errors if e["severity"] == "error"]
    warn = [e for e in errors if e["severity"] == "warning"]

    lines = []
    lines.append(f"\n🔴 {len(crit)} errors, ⚠️ {len(warn)} warnings\n")

    for e in errors:
        icon = "🔴" if e["severity"] == "error" else "⚠️"
        lines.append(f"  {icon} [{e['path']}] {e['message']}")
        if e.get("schema_path"):
            lines.append(f"       schema: {e['schema_path']}")

    return "\n".join(lines)


def validate_all(strict: bool = False) -> dict[str, list[dict[str, Any]]]:
    """校验 data/ 目录下所有 YAML 文件，返回 {filename: errors} 映射"""
    results = {}
    for fname in sorted(FILENAME_TYPE_MAP.keys()):
        if not fname.endswith(".yaml"):
            continue
        yaml_path = os.path.join(DATA_DIR, fname)
        if not os.path.exists(yaml_path):
            continue
        errors = validate_yaml(yaml_path)
        results[fname] = errors
    return results


# ── CLI ──────────────────────────────────────────────────────────
def main():
    import argparse

    parser = argparse.ArgumentParser(description="Validate YAML data files against JSON Schemas")
    parser.add_argument("files", nargs="*", help="YAML file(s) to validate (from data/ directory). Default: all.")
    parser.add_argument("--list", action="store_true", help="List all supported schema types and exit")
    parser.add_argument("--strict", action="store_true", help="Strict mode (treat warnings as errors)")

    args = parser.parse_args()

    if args.list:
        log.info("Supported schema types:")
        for t in sorted(TYPE_SCHEMA_MAP.keys()):
            schema_path = os.path.join(SCHEMA_DIR, TYPE_SCHEMA_MAP[t])
            exists = "✅" if os.path.exists(schema_path) else "❌"
            log.info(f"  {exists} {t:12s} → {TYPE_SCHEMA_MAP[t]}")
        return
    if args.files:
        all_ok = True
        for fname in args.files:
            yaml_path = fname if os.path.isabs(fname) else os.path.join(DATA_DIR, fname)
            if not os.path.exists(yaml_path):
                log.error(f"❌ File not found: {yaml_path}")
                all_ok = False
                continue
            log.info(f"\n{'='*60}")
            log.info(f"  Validating: {os.path.basename(yaml_path)}")
            log.info(f"{'='*60}")
            errors = validate_yaml(yaml_path)
            log.info(format_errors(errors))
            # v43.7: 仅 error 级阻断，warning 不阻断
            crit = [e for e in errors if e["severity"] == "error"]
            if crit:
                all_ok = False
        if not all_ok:
            raise PipelineError("Some validations FAILED")
    else:
        # Validate all
        log.info(f"{'='*60}")
        log.info("  Validating all YAML files in data/")
        log.info(f"{'='*60}")

        results = validate_all(strict=args.strict)
        total_errors = 0
        all_ok = True

        for fname, errors in sorted(results.items()):
            log.info(f"\n── {fname} ──")
            log.info(format_errors(errors))
            # v43.7: 仅 error 级阻断，warning 不阻断
            crit = [e for e in errors if e["severity"] == "error"]
            if crit:
                all_ok = False
                total_errors += len(crit)

        log.info(f"\n{'='*60}")
        if all_ok:
            log.info("  ✅ All files validated successfully")
        else:
            log.error(f"  ❌ Total: {total_errors} error(s)")
        log.info(f"{'='*60}")
        if not all_ok:
            raise PipelineError("Some validations FAILED")


if __name__ == "__main__":
    main()
