#!/usr/bin/env python3
"""yaml_gen.py — Agent YAML 生成辅助工具

从模板中提取字段、反查模板类型、验证 YAML 匹配、交互式生成，
帮助 Agent 根据模板生成正确的 YAML 数据。

四种模式（argparse 子命令）:
    extract     从模板提取 {{变量}}，输出 YAML 骨架
    match       给定字段名列表，自动匹配对应模板类型
    validate    快速验证 YAML 字段是否与模板匹配
    interactive 交互式逐字段填写，输出完整 YAML

用法:
    # 字段提取（输出为 YAML 骨架带注释）
    python3 yaml_gen.py extract concept
    python3 yaml_gen.py extract solution
    python3 yaml_gen.py extract all

    # 模板发现（字段→类型反查）
    python3 yaml_gen.py match "principle_steps,characteristics,exam_points"
    python3 yaml_gen.py match "skill_objectives,core_operation"

    # 验证模式
    python3 yaml_gen.py validate .dag/第1章/data/concepts.yaml

    # 交互式生成
    python3 yaml_gen.py interactive concept concepts_template.yaml
"""

from __future__ import annotations


import argparse
import os
import re
import sys

import yaml
from dag_constants import PipelineError

# ── 路径常量 ─────────────────────────────────────────────────

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES_DIR = os.path.join(SKILL_DIR, "assets", "templates")
REFERENCES_DIR = os.path.join(SKILL_DIR, "references")
FIELD_MAPPING_PATH = os.path.join(REFERENCES_DIR, "yaml-field-mapping.md")

# ── 类型→quality_key 映射 ───────────────────────────────────

QUALITY_KEY_MAP: dict[str, str] = {
    "concept": "concept",
    "ke": "concept/ke",
    "entity": "concept/entity",
    "knowledge": "knowledge",
    "skill": "skill",
    "scenario": "scenario",
    "exercise": "eval/exercise",
    "solution": "eval/solution",
}

# ── 类型→模板文件名映射 ─────────────────────────────────────

TEMPLATE_FILE_MAP: dict[str, str] = {
    "concept": "concept_template.md",
    "ke": "concept_template.md",
    "entity": "concept_template.md",
    "knowledge": "knowledge_template.md",
    "skill": "skill_template.md",
    "scenario": "scenario_template.md",
    "exercise": "eval_template.md",
    "solution": "eval_template.md",
}

# ── 所有支持的模板类型 ──────────────────────────────────────

ALL_TYPES = sorted(QUALITY_KEY_MAP.keys())

# ── FrontMatter 公共字段（所有类型通用）─────────────────────

COMMON_FRONTMATTER_FIELDS: list[str] = [
    "name",
    "book_id",
    "book_name",
    "chapter_num",
    "confidence",
    "confidence_note",
    "source_chapter",
    "source_from",
    "type",
    "type_tag",
    "aliases",
    "tags",
    "bloom_level",
]

# ── 类型→confidence 映射（用于 extract 容器输出） ─────────────

CONFIDENCE_EXTRACT_MAP: dict[str, float] = {
    "concept": 0.95,
    "ke": 0.85,
    "entity": 0.85,
    "knowledge": 0.85,
    "skill": 0.75,
    "scenario": 0.65,
    "exercise": 0.65,
    "solution": 0.85,
}

# ── 注释分隔符 ──────────────────────────────────────────────

SECTION_SEP = "# " + "─" * 60


# ═══════════════════════════════════════════════════════════════
# 模板解析
# ═══════════════════════════════════════════════════════════════

_VAR_RE = re.compile(r"\{\{(\w+)\}\}")


def extract_template_vars(template_path: str) -> list[str]:
    """从模板文件中提取所有 ``{{变量}}`` 名称，去重保序。

    Args:
        template_path: 模板文件绝对路径

    Returns:
        按首次出现顺序排列的变量名列表
    """
    if not os.path.exists(template_path):
        return []
    with open(template_path, encoding="utf-8") as f:
        content = f.read()
    seen: set[str] = set()
    result: list[str] = []
    for m in _VAR_RE.finditer(content):
        name = m.group(1)
        if name not in seen:
            seen.add(name)
            result.append(name)
    return result


# ═══════════════════════════════════════════════════════════════
# yaml-field-mapping.md 解析
# ═══════════════════════════════════════════════════════════════

# 3列格式: | `field` | `{{var}}` | 说明 |
# 4列格式: | `field` | `{{var}}` | ✅ | 说明 |
_TABLE_ROW_RE = re.compile(
    r"^\|\s*`(\w+)`\s*\|\s*`\{\{(\w+)\}\}`\s*\|"
    r"\s*(?:(✅)\s*\|)?\s*"
    r"(.+?)\s*\|"
)


def parse_field_mapping(md_path: str) -> dict[str, dict[str, str]]:
    """解析 yaml-field-mapping.md，按 section 返回字段信息。

    Returns:
        {section_name: {field_name: description}}
        每个字段的 description 可能包含必填标记前缀 "[required] "。
        同时维护一个全局的 field→required 和 field→description 映射。
    """
    if not os.path.exists(md_path):
        return {}

    sections: dict[str, dict[str, str]] = {}
    current_section: str | None = None

    with open(md_path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")

            # 判断 section header（## 或 ### 开头）
            sec_match = re.match(r"^(?:##|###)\s+(.+)$", line)
            if sec_match:
                current_section = sec_match.group(1).strip()
                if current_section not in sections:
                    sections[current_section] = {}
                continue

            # 非表格行跳过
            if not line.startswith("|"):
                continue

            row_match = _TABLE_ROW_RE.match(line)
            if not row_match:
                continue

            bd_key = row_match.group(1)
            required = row_match.group(3) == "✅"
            desc = row_match.group(4).strip()

            prefix = "[required] " if required else ""
            sections[current_section][bd_key] = prefix + desc

    return sections


def load_field_registry() -> tuple[
    dict[str, dict[str, str]],
    dict[str, bool],
    dict[str, str],
    dict[str, list[str]],
]:
    """加载完整的字段注册表。

    Returns:
        (sections, required_map, desc_map, type_fields_map)
        - sections: {section_name: {field: description}}
        - required_map: {field: bool}
        - desc_map: {field: description}
        - type_fields_map: {type_name: [field_names]}  # all types including ke/entity
    """
    raw = parse_field_mapping(FIELD_MAPPING_PATH)

    required_map: dict[str, bool] = {}
    desc_map: dict[str, str] = {}
    type_fields_map: dict[str, list[str]] = {}

    # 公共字段
    common_section = raw.get("FrontMatter 公共字段（所有类型通用）", {})
    for field, desc in common_section.items():
        desc_map[field] = desc
        required_map[field] = False

    # 类型→section 名称映射
    type_section_map = {
        "concept": "概念类 (concept_template.md, quality_key=concept)",
        "ke": "知识要素 (concept_template.md, quality_key=concept/ke)",
        "entity": "实体 (concept_template.md, quality_key=concept/entity)",
        "knowledge": "知识点 (knowledge_template.md, quality_key=knowledge)",
        "skill": "技能点 (skill_template.md, quality_key=skill)",
        "scenario": "应用场景 (scenario_template.md, quality_key=scenario)",
        "solution": "解答 (quality_key=eval/solution, confidence=0.85)",
        "exercise": "习题 (quality_key=eval/exercise, confidence=0.65)",
    }

    for type_name, section_name in type_section_map.items():
        # Try exact match first, then fuzzy
        section = raw.get(section_name, {})
        if not section:
            # Fuzzy match
            for key in raw:
                if type_name in key.lower() or section_name[:8] in key:
                    section = raw[key]
                    break

        fields = []
        for field, desc in section.items():
            fields.append(field)
            required = desc.startswith("[required] ")
            if required:
                required_map[field] = True
                desc_map[field] = desc[len("[required] ") :]
            else:
                if field not in required_map:
                    required_map[field] = False
                desc_map[field] = desc

        type_fields_map[type_name] = fields

    return raw, required_map, desc_map, type_fields_map


# ═══════════════════════════════════════════════════════════════
# 字段→类型 反向索引（用于 --match）
# ═══════════════════════════════════════════════════════════════

def build_reverse_index(
    type_fields_map: dict[str, list[str]],
) -> dict[str, list[str]]:
    """构建 field_name → [type_names] 反向索引。

    Args:
        type_fields_map: {type_name: [field_names]}

    Returns:
        {field_name: [type_names_containing_this_field]}
    """
    reverse: dict[str, list[str]] = {}
    for tname, fields in type_fields_map.items():
        for f in fields:
            reverse.setdefault(f, []).append(tname)
    # Also add common fields (available in all types)
    for f in COMMON_FRONTMATTER_FIELDS:
        if f not in reverse:
            reverse[f] = list(ALL_TYPES)
    return reverse


# ═══════════════════════════════════════════════════════════════
# 模式 1: 字段提取 (extract)
# ═══════════════════════════════════════════════════════════════

def cmd_extract(args: argparse.Namespace) -> None:
    """--extract-fields / extract 子命令：输出 YAML 骨架。"""
    required_map, desc_map, _type_fields_map = load_field_registry()[1:]

    types_to_extract: list[str]
    if args.type == "all":
        types_to_extract = ["concept", "ke", "entity", "knowledge", "skill", "scenario", "exercise", "solution"]
    else:
        types_to_extract = [args.type]

    for tname in types_to_extract:
        template_file = TEMPLATE_FILE_MAP.get(tname)
        if not template_file:
            print(f"# 未知类型: {tname}", file=sys.stderr)
            continue

        template_path = os.path.join(TEMPLATES_DIR, template_file)
        template_vars = extract_template_vars(template_path)

        # Build ordered field list: common frontmatter first, then type-specific
        all_fields: list[str] = []
        for f in COMMON_FRONTMATTER_FIELDS:
            if f in template_vars:
                all_fields.append(f)
        for f in template_vars:
            if f not in COMMON_FRONTMATTER_FIELDS and f not in all_fields:
                all_fields.append(f)

        quality_key = QUALITY_KEY_MAP.get(tname, tname)
        required_count = sum(1 for f in all_fields if required_map.get(f))
        confidence = CONFIDENCE_EXTRACT_MAP.get(tname, 0.85)

        print(f"# {_type_label(tname)} ({template_file}, quality_key={quality_key}) "
              f"— 共 {len(all_fields)} 个 bd 字段")
        if required_count:
            print(f"# ★ = 必填字段 ({required_count} 个)")
        print("# ── 容器结构 ──")
        if tname == "exercise":
            print("# [exercise 使用 exercise_template.md, 仅含题目，bd 中无解答内容]")
        print('- name: "节点名称"')
        print('  file: "节点名称"          # 不可含 .md 后缀')
        print('  fm:')
        print("    source_chapter: 'N'     # 章号")
        print('    source_from: "§N.X"     # 节号')
        print(f'    confidence: {confidence}        # {tname}={confidence}')
        print('    confidence_note: ""')
        print('  bd:')

        for field in all_fields:
            is_required = required_map.get(field, False)
            marker = " ★" if is_required else "  "
            desc = desc_map.get(field, field)
            if len(desc) > 60:
                desc = desc[:57] + "..."
            print(f'    {field}: ""{" " * max(1, 26 - len(field))}#{marker} {desc}')

        if tname != types_to_extract[-1]:
            print()


def _type_label(tname: str) -> str:
    """返回类型的中文标签。"""
    labels = {
        "concept": "概念类",
        "ke": "知识要素类",
        "entity": "实体类",
        "knowledge": "知识点类",
        "skill": "技能点类",
        "scenario": "应用场景类",
        "exercise": "习题类",
        "solution": "解答类",
    }
    return labels.get(tname, tname)


# ═══════════════════════════════════════════════════════════════
# 模式 2: 字段匹配 (match)
# ═══════════════════════════════════════════════════════════════

def cmd_match(args: argparse.Namespace) -> None:
    """match 子命令：给定字段列表，反查最佳匹配模板类型。"""
    _, _, _, type_fields_map = load_field_registry()
    reverse_index = build_reverse_index(type_fields_map)

    # Parse field list (comma-separated)
    field_list = [f.strip() for f in args.fields.split(",") if f.strip()]
    if not field_list:
        print("错误: 请提供至少一个字段名", file=sys.stderr)
        raise PipelineError("请提供至少一个字段名")

    # Score each type by how many fields match
    scores: dict[str, tuple[int, int, float]] = {}
    for tname in ALL_TYPES:
        type_fields = set(type_fields_map.get(tname, []))
        type_fields.update(COMMON_FRONTMATTER_FIELDS)
        matched = sum(1 for f in field_list if f in type_fields)
        total = len(type_fields)
        ratio = matched / len(field_list) if field_list else 0
        scores[tname] = (matched, total, ratio)

    # Sort by ratio descending, then matched count
    ranked = sorted(scores.items(), key=lambda x: (x[1][2], x[1][0]), reverse=True)

    # Output top matches
    for tname, (matched, _total, ratio) in ranked:
        if ratio > 0:
            template_file = TEMPLATE_FILE_MAP.get(tname, "?")
            quality_key = QUALITY_KEY_MAP.get(tname, tname)
            label = _type_label(tname)
            print(f"{label}: {tname} ({template_file}, quality_key={quality_key}) "
                  f"— 匹配 {matched}/{len(field_list)} 字段 ({ratio:.0%})")

    # Check for unknown fields
    known = set(reverse_index.keys())
    unknown = [f for f in field_list if f not in known]
    if unknown:
        print(f"\n⚠ 未识别的字段: {', '.join(unknown)}")


# ═══════════════════════════════════════════════════════════════
# 模式 3: 验证 (validate)
# ═══════════════════════════════════════════════════════════════

def cmd_validate(args: argparse.Namespace) -> None:
    """validate 子命令：快速验证 YAML 字段是否与模板匹配。"""
    yaml_path = args.yaml_file
    if not os.path.exists(yaml_path):
        print(f"错误: 文件不存在: {yaml_path}", file=sys.stderr)
        raise PipelineError(f"文件不存在: {yaml_path}")

    # Auto-detect type from filename
    detected_type = _detect_type_from_path(yaml_path)
    if not detected_type:
        print("错误: 无法从文件路径推断类型，请使用 --type 指定", file=sys.stderr)
        raise PipelineError("无法从文件路径推断类型，请使用 --type 指定")

    _, required_map, _, type_fields_map = load_field_registry()
    expected_fields = set(type_fields_map.get(detected_type, []))
    expected_fields.update(COMMON_FRONTMATTER_FIELDS)

    # Load YAML
    with open(yaml_path, encoding="utf-8") as f:
        try:
            data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            print(f"错误: YAML 解析失败: {e}", file=sys.stderr)
            raise PipelineError(f"YAML 解析失败: {e}") from e

    if not data or "items" not in data:
        print("错误: YAML 缺少 'items' 顶层键", file=sys.stderr)
        raise PipelineError("YAML 缺少 'items' 顶层键")

    items = data["items"]
    if not isinstance(items, list):
        print("错误: 'items' 必须是列表", file=sys.stderr)
        raise PipelineError("'items' 必须是列表")

    total_items = len(items)
    total_expected = len(expected_fields)

    # Validate each item
    total_valid = 0
    total_missing = 0
    total_invalid = 0

    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            total_invalid += 1
            continue

        item_fields = set(item.keys())
        valid = item_fields & expected_fields
        missing = expected_fields - item_fields
        invalid = item_fields - expected_fields

        total_valid += len(valid)
        total_missing += len(missing)
        total_invalid += len(invalid)

        if args.verbose:
            print(f"[{idx}] valid={len(valid)} missing={len(missing)} invalid={len(invalid)}")
            if missing:
                print(f"    缺失: {', '.join(sorted(missing)[:10])}")
            if invalid:
                print(f"    无效: {', '.join(sorted(invalid)[:10])}")

    # Summary
    max_possible = total_expected * total_items
    print(f"{total_items} 条记录, {total_expected} 期望字段/条")
    print(f"总计: {total_valid}/{max_possible} 字段有效, "
          f"{total_missing} 缺失, {total_invalid} 无效")

    # Required field check
    all_item_keys = set()
    for item in items:
        if isinstance(item, dict):
            all_item_keys.update(item.keys())
    truly_missing_required = [f for f in expected_fields if required_map.get(f) and f not in all_item_keys]
    if truly_missing_required:
        print(f"⚠ 必填字段缺失: {', '.join(truly_missing_required)}")


def _detect_type_from_path(path: str) -> str | None:
    """从文件路径推断模板类型。

    支持的模式:
        concepts.yaml → concept
        knowledge_elements.yaml → ke
        entities.yaml → entity
        knowledge.yaml → knowledge
        skills.yaml → skill
        scenarios.yaml → scenario
        exercises.yaml → exercise
        solutions.yaml → solution
    """
    basename = os.path.splitext(os.path.basename(path))[0].lower()
    mapping = {
        "concepts": "concept",
        "knowledge_elements": "ke",
        "entities": "entity",
        "knowledge": "knowledge",
        "skills": "skill",
        "scenarios": "scenario",
        "exercises": "exercise",
        "solutions": "solution",
    }
    for key, val in mapping.items():
        if key in basename:
            return val
    return None


# ═══════════════════════════════════════════════════════════════
# 模式 4: 交互式生成 (interactive)
# ═══════════════════════════════════════════════════════════════

def cmd_interactive(args: argparse.Namespace) -> None:
    """interactive 子命令：逐字段交互式填写，输出 YAML 文件。"""
    tname = args.type
    if tname not in QUALITY_KEY_MAP:
        print(f"错误: 未知类型 '{tname}'，支持: {', '.join(ALL_TYPES)}", file=sys.stderr)
        raise PipelineError(f"未知类型 '{tname}'，支持: {', '.join(ALL_TYPES)}")

    required_map, desc_map, _type_fields_map = load_field_registry()[1:]

    template_file = TEMPLATE_FILE_MAP.get(tname)
    template_path = os.path.join(TEMPLATES_DIR, template_file or "")
    template_vars = extract_template_vars(template_path)

    # Build ordered field list
    all_fields: list[str] = []
    for f in COMMON_FRONTMATTER_FIELDS:
        if f in template_vars:
            all_fields.append(f)
    for f in template_vars:
        if f not in COMMON_FRONTMATTER_FIELDS and f not in all_fields:
            all_fields.append(f)

    quality_key = QUALITY_KEY_MAP.get(tname, tname)
    label = _type_label(tname)

    print(f"\n{'='*60}")
    print(f"  交互式 YAML 生成 — {label} ({quality_key})")
    print(f"  共 {len(all_fields)} 个字段，回车跳过，输入 'q' 退出")
    print(f"{'='*60}\n")

    values: dict[str, str] = {}
    for i, field in enumerate(all_fields):
        is_required = required_map.get(field, False)
        desc = desc_map.get(field, "")
        req_mark = "★" if is_required else " "
        print(f"[{i+1}/{len(all_fields)}] [{req_mark}] {field}")
        if desc:
            print(f"      说明: {desc}")
        try:
            user_input = input("      输入: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\n已取消。")
            return

        if user_input.lower() == "q":
            print("已退出。已输入的字段将不会保存。")
            return
        if user_input:
            values[field] = user_input

    # Build output YAML
    output: dict = {
        "items": [values],
    }

    output_path = args.output
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        yaml.dump(output, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

    filled = len(values)
    total = len(all_fields)
    print(f"\n✓ 已保存到 {output_path} ({filled}/{total} 字段已填写)")


# ═══════════════════════════════════════════════════════════════
# CLI 入口
# ═══════════════════════════════════════════════════════════════

def build_parser() -> argparse.ArgumentParser:
    """构建 argparse 解析器，使用子命令模式。"""
    parser = argparse.ArgumentParser(
        prog="yaml_gen.py",
        description="Agent YAML 生成辅助工具 — 字段提取/类型匹配/验证/交互式生成",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python3 yaml_gen.py extract concept         # 输出概念类字段骨架
  python3 yaml_gen.py extract all             # 输出全部类型的骨架
  python3 yaml_gen.py match "skill_objectives,core_operation"  # 反查模板类型
  python3 yaml_gen.py validate data.yaml      # 验证字段匹配
  python3 yaml_gen.py interactive concept out.yaml  # 交互式填写
        """,
    )

    sub = parser.add_subparsers(dest="command", help="子命令")

    # ── extract ──
    p_extract = sub.add_parser("extract", help="从模板提取字段，输出 YAML 骨架")
    p_extract.add_argument(
        "type",
        choices=[*ALL_TYPES, "all"],
        help=f"模板类型 ({', '.join(ALL_TYPES)}) 或 'all'",
    )

    # ── match ──
    p_match = sub.add_parser("match", help="字段名列表反查模板类型")
    p_match.add_argument(
        "fields",
        help="逗号分隔的字段名列表，如 'principle_steps,characteristics,exam_points'",
    )

    # ── validate ──
    p_validate = sub.add_parser("validate", help="验证 YAML 字段与模板匹配")
    p_validate.add_argument("yaml_file", help="YAML 文件路径")
    p_validate.add_argument(
        "-v", "--verbose", action="store_true", help="显示每条的详细验证结果"
    )

    # ── interactive ──
    p_interactive = sub.add_parser("interactive", help="交互式逐字段填写")
    p_interactive.add_argument(
        "type", choices=ALL_TYPES, help=f"模板类型 ({', '.join(ALL_TYPES)})"
    )
    p_interactive.add_argument("output", help="输出的 YAML 文件路径")

    return parser


def main(argv: list[str] | None = None) -> None:
    """主入口。

    Args:
        argv: 命令行参数列表，None 表示使用 sys.argv[1:]
    """
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "extract":
        cmd_extract(args)
    elif args.command == "match":
        cmd_match(args)
    elif args.command == "validate":
        cmd_validate(args)
    elif args.command == "interactive":
        cmd_interactive(args)
    else:
        parser.print_help()
        raise PipelineError("请指定子命令")


if __name__ == "__main__":
    try:
        main()
    except PipelineError as e:
        print(f"错误: {e}", file=sys.stderr)
        raise
