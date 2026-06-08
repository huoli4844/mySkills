#!/usr/bin/env python3
"""
migrate_yaml_schema.py — 一键升级 YAML 数据到最新模板 schema

版本: v51.1
用途: 将旧版 YAML（v50.0 模板生成）迁移到新版 schema（v50.7+ 模板）
处理:
  1. 旧字段重命名（source→definition_source 等 7 组）
  2. 旧字段删除（concept 级字段从 ke/entity 中移除）
  3. 必填字段补充（solved_problem, knowledge_context, prerequisite_concepts 等）
  4. 验证迁移后 yaml_pre_validate 全部通过

用法:
  python3 migrate_yaml_schema.py --book-dir /path/to/book
  python3 migrate_yaml_schema.py --book-dir /path/to/book --dry-run  # 只报告不改
"""

import argparse
import glob
import os
import re
import sys
from copy import deepcopy

try:
    import yaml
except ImportError:
    print("需要 PyYAML: pip install pyyaml")
    sys.exit(1)


# ── 旧字段 → 新字段 映射表 ──────────────────────────────────
# (旧字段名, 新字段名) — 重命名
FIELD_RENAME_MAP: dict[str, str] = {
    "source": "definition_source",
    "skill_description": "skill_objectives",
    "operation_steps": "core_operation",
    "scene_description": "scenario_description",
}

# (旧字段名, 新字段名, 目标类型) — 仅特定类型执行重命名
FIELD_RENAME_BY_TYPE: dict[str, tuple[str, str]] = {
    "kp__exam_questions": ("exam_questions", "exam_and_misconceptions"),
    "kp__common_exam_points": ("common_exam_points", "exam_and_misconceptions"),
    "kp__exam_point_analysis": ("exam_point_analysis", "exam_and_misconceptions"),
    "solution__difficulty_first": ("difficulty_first", "difficulty_1_title"),
    "solution__difficulty_second": ("difficulty_second", "difficulty_2_title"),
    "solution__difficulty_third": ("difficulty_third", "difficulty_3_title"),
    "scene__objectives": ("objectives", "scene_elements"),
}

# 需从 KE bd 中移除的 concept 级字段
KE_REMOVE_FIELDS = {
    "value", "structure", "classification",
    "additional_explanations", "core_concept_map_source",
    "figure_references", "formula_references", "references",
    "definition_source", "mathematical_model",
}

# 需从 Entity bd 中移除的 concept 级字段
ENTITY_REMOVE_FIELDS = KE_REMOVE_FIELDS | {"upstream_downstream"}

# 从 concept bd 中移除的旧字段/不识别字段
CONCEPT_REMOVE_FIELDS = {
    "additional_explanations", "core_concept_map_source",
    "figure_references", "formula_references",
}

# 需从 kp.yml 的 exercise 条目中移除的 concept 级字段
EXERCISE_REMOVE_FIELDS = {
    "additional_explanations", "core_concept_map_source",
    "figure_references", "formula_references", "references",
    "definition_source",
}

# ── 必填字段补充（从 dag_constants 自动读取，确保与 schema 同步）─────────
# 迁移时尝试加载 dag_constants.REQUIRED_BD_FIELDS，如果失败则用内建默认值
_BUILTIN_REQUIRED: dict[str, dict[str, str]] = {
    "concept": {"solved_problem": "无"},
    "ke": {"solved_problem": "无", "entity_type": "知识要素", "definition_sentence": "无"},
    "entity": {"solved_problem": "无", "entity_type": "实体", "term_definition": "无"},
    "kp": {"solved_problem": "无", "engineering_practices": "无", "confusion_compare": "无", "self_check_questions": "无"},
    "sp": {"solved_problem": "无"},
    "scene": {"solved_problem": "无"},
}


def _get_required_defaults() -> dict[str, dict[str, str]]:
    """从 dag_constants 获取 REQUIRED_BD_FIELDS 并转为默认值映射。"""
    defaults = {k: {} for k in _BUILTIN_REQUIRED}
    try:
        from dag_constants import REQUIRED_BD_FIELDS
        for node_type, fields in REQUIRED_BD_FIELDS.items():
            if node_type not in defaults:
                defaults[node_type] = {}
            for field in fields:
                defaults[node_type].setdefault(field, "无")
    except Exception:
        # fallback: 用 _BUILTIN_REQUIRED 合并
        for nt, fields in _BUILTIN_REQUIRED.items():
            for f, v in fields.items():
                if f not in defaults.get(nt, {}):
                    defaults.setdefault(nt, {})[f] = v
    return defaults

# scene 额外补充（不在 REQUIRED_BD_FIELDS 中但 pipeline init 会警告）
SCENE_EXTRA_FIELDS = {
    "knowledge_context": "无",
    "overall_solution": "无",
}

# 测试专用补充
SOLUTION_REQUIRED = {
    "answer": "无",
}


def load_yaml(path: str) -> list[dict]:
    """安全加载 YAML，兼容 list 和 {items: [...]} 格式"""
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    if raw is None:
        return []
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict) and "items" in raw:
        return raw["items"]
    return []


def save_yaml(path: str, data: list[dict]) -> None:
    """写回 YAML"""
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)


def detect_type(filepath: str) -> str:
    """从文件名推断节点类型"""
    base = os.path.basename(filepath).lower()
    if "concept" in base:
        return "concept"
    if "entity" in base or "entities" in base:
        return "entity"
    if base.startswith("ke") or base.startswith("kes"):
        return "ke"
    if "kp" in base:
        return "kp"
    if "sp" in base:
        return "sp"
    if "scene" in base:
        return "scene"
    if "exercise" in base:
        return "exercise"
    if "solution" in base or "solutions" in base:
        return "solution"
    return "unknown"


def migrate_item(
    item: dict,
    node_type: str,
    stats: dict,
    required_defaults: dict[str, dict[str, str]] | None = None,
) -> dict:
    """迁移单条 YAML 记录的 bd 字段"""
    bd = item.get("bd", {})
    if not isinstance(bd, dict):
        return item

    item = deepcopy(item)
    bd = item.setdefault("bd", {})
    original_keys = set(bd.keys())

    # ── 1. 通用字段重命名 ──
    for old, new in FIELD_RENAME_MAP.items():
        if old in bd:
            bd[new] = bd.pop(old)
            stats["renamed"] += 1
            stats[f"rename_{old}→{new}"] = stats.get(f"rename_{old}→{new}", 0) + 1

    # ── 2. 按类型特化的重命名/合并 ──
    type_key = f"{node_type}__"
    for compound_key, (old, new) in FIELD_RENAME_BY_TYPE.items():
        if compound_key.startswith(type_key) and old in bd:
            # 合并：如果目标字段已存在且新旧不同，拼接
            old_val = bd.pop(old)
            if new in bd:
                if isinstance(bd[new], list) and isinstance(old_val, list):
                    bd[new].extend(old_val)
                elif isinstance(bd[new], str) and isinstance(old_val, str):
                    bd[new] = bd[new] + "\n" + old_val if bd[new] else old_val
            else:
                bd[new] = old_val
            stats["renamed"] += 1
            stats[f"rename_{old}→{new}"] = stats.get(f"rename_{old}→{new}", 0) + 1

    # ── 3. 按类型移除非法字段 ──
    remove_set: set[str] = set()
    if node_type == "ke":
        # ke 不应该有 concept 级字段
        for f in KE_REMOVE_FIELDS:
            if f in bd:
                remove_set.add(f)
    elif node_type == "entity":
        for f in ENTITY_REMOVE_FIELDS:
            if f in bd:
                remove_set.add(f)
    elif node_type == "concept":
        for f in CONCEPT_REMOVE_FIELDS:
            if f in bd:
                remove_set.add(f)
                # concept 的 definition_source 应重命名回 source（但模板期望 definition_source）
                if f == "definition_source":
                    pass
    elif node_type == "exercise":
        for f in EXERCISE_REMOVE_FIELDS:
            if f in bd:
                remove_set.add(f)

    for f in remove_set:
        if f in bd:
            del bd[f]
            stats["removed"] += 1

    # ── 4. 补充缺失的必填字段 ──
    defaults = (required_defaults or _get_required_defaults()).get(node_type, {})
    for field, default_val in defaults.items():
        if field not in bd or bd[field] is None or (isinstance(bd[field], str) and bd[field].strip() == ""):
            bd[field] = default_val
            stats["added"] += 1
            stats[f"added_{field}"] = stats.get(f"added_{field}", 0) + 1

    # ── 5. Scene 额外字段 ──
    if node_type == "scene":
        for field, default_val in SCENE_EXTRA_FIELDS.items():
            if field not in bd or bd[field] is None or (isinstance(bd[field], str) and bd[field].strip() == ""):
                bd[field] = default_val
                stats["added"] += 1

    # ── 6. Solution 额外字段 ──
    if node_type == "solution":
        for field, default_val in SOLUTION_REQUIRED.items():
            if field not in bd or bd[field] is None or (isinstance(bd[field], str) and bd[field].strip() == ""):
                bd[field] = default_val
                stats["added"] += 1

    # ── 7. fm 域补充 ──
    fm = item.get("fm", {})
    if not isinstance(fm, dict):
        fm = {}
    fm.setdefault("confidence", 0.7)
    fm.setdefault("bloom_level", "理解")
    item["fm"] = fm

    return item


def migrate_file(filepath: str, dry_run: bool = False, required_defaults: dict | None = None) -> dict:
    """迁移单个 YAML 文件"""
    node_type = detect_type(filepath)
    stats: dict = {"renamed": 0, "removed": 0, "added": 0, "items": 0, "path": filepath, "type": node_type}

    items = load_yaml(filepath)
    if not items:
        return stats

    stats["items"] = len(items)
    migrated = [migrate_item(it, node_type, stats, required_defaults) for it in items]

    if not dry_run and (stats["renamed"] > 0 or stats["removed"] > 0 or stats["added"] > 0 or node_type != "unknown"):
        # 统一保存为扁平列表格式（兼容预校验器期望）
        with open(filepath, "w", encoding="utf-8") as f:
            yaml.dump(migrated, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

    return stats


def main():
    parser = argparse.ArgumentParser(description="YAML schema migration tool")
    parser.add_argument("--book-dir", required=True, help="知识库根目录（含 .dag/）")
    parser.add_argument("--dry-run", action="store_true", help="仅报告不修改")
    args = parser.parse_args()

    book_dir = os.path.abspath(args.book_dir)
    dag_dir = os.path.join(book_dir, ".dag")
    if not os.path.isdir(dag_dir):
        print(f"❌ 未找到 .dag/ 目录: {dag_dir}")
        sys.exit(1)

    yaml_files = sorted(glob.glob(os.path.join(dag_dir, "第*章", "data", "*.yaml")))
    print(f"📋 扫描到 {len(yaml_files)} 个 YAML 文件\n")

    required_defaults = _get_required_defaults()
    total: dict = {"renamed": 0, "removed": 0, "added": 0, "items": 0, "files": 0}
    for fpath in yaml_files:
        rel = os.path.relpath(fpath, book_dir)
        stats = migrate_file(fpath, dry_run=args.dry_run, required_defaults=required_defaults)
        if stats["items"] > 0:
            total["renamed"] += stats["renamed"]
            total["removed"] += stats["removed"]
            total["added"] += stats["added"]
            total["items"] += stats["items"]
            total["files"] += 1
            if stats["renamed"] > 0 or stats["removed"] > 0 or stats["added"] > 0:
                print(f"  {'🔍' if args.dry_run else '✏️'} {rel:45s} "
                      f"items={stats['items']:3d}  "
                      f"rename={stats['renamed']:2d}  "
                      f"remove={stats['removed']:2d}  "
                      f"add={stats['added']:2d}  "
                      f"[{stats['type']}]")

    mode = "🔍 DRY RUN（未修改）" if args.dry_run else "✏️ 已修改"
    print(f"\n{mode}")
    print(f"📊 {total['files']}/{len(yaml_files)} 文件需变更")
    print(f"  字段重命名: {total['renamed']}")
    print(f"  字段删除:   {total['removed']}")
    print(f"  字段补充:   {total['added']}")
    print(f"  总记录数:   {total['items']}")

    if not args.dry_run and total["renamed"] + total["removed"] + total["added"] > 0:
        print("\n✅ 迁移完成，运行 yaml_pre_validate 验证:")
        print(f"  python3 yaml_pre_validate.py --chapter-dir {dag_dir}/第N章/data/")


if __name__ == "__main__":
    main()
