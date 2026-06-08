#!/usr/bin/env python3
"""
schema_loader.py — 模板字段名唯一权威源 (v52.4)

从 assets/templates/*.md 自动提取 {{xxx}} 字段名作为单点事实源。
替代 dag_constants.REQUIRED_BD_FIELDS、phase_validator 等4处分散的字段列表。

用法:
    python3 schema_loader.py list                    # 列出所有类型及字段数
    python3 schema_loader.py extract concept         # 输出概念字段列表
    python3 schema_loader.py extract concept --yaml  # 输出 YAML 骨架
    python3 schema_loader.py verify concept field1 field2  # 验证字段名是否合法
    python3 schema_loader.py validate <yaml_path>    # 验证 YAML bd 字段 vs 模板
"""

import json
import os
import re
import sys

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # skill root (parent of scripts/)
ASSETS_DIR = os.path.join(SKILL_DIR, "assets", "templates")

# ── 类型名 → 模板文件名映射 ──────────────────────────────────
# 这是全系统唯一需要维护的映射表。
# 新增模板类型时，只需在此注册一行。
TYPE_TO_TEMPLATE = {
    "concept":      "concept_template.md",
    "ke":           "ke_template.md",
    "entity":       "entity_template.md",
    "kp":           "knowledge_template.md",
    "sp":           "skill_template.md",
    "scene":        "scenario_template.md",
    "exercise":     "exercise_template.md",
    "solution":     "eval_template.md",
}


# ── 自称不是 bd 字段的自动填充字段 ────────────────────────
# 这些 {{xxx}} 出现在模板正文中，但由 build_kb_files.py 从 fm 自动填充，
# 不需要在 YAML bd 中定义。
_AUTO_FILL_FIELDS: set[str] = {
    "name", "source_chapter", "source_from", "type_tag",
    "type", "confidence", "confidence_note", "chapter_num",
    "bloom_level", "entity_type", "aliases", "tags",
    "book_id", "book_name", "exercise_link", "exercise_name",
    "bloom_progression_analysis",
}


def _extract_placeholders(content: str) -> list[str]:
    """从模板内容中提取所有 {{xxx}} 占位符，返回有序去重列表。
    自动剔除 frontmatter 字段和自动填充字段。"""
    # 剔除 frontmatter 中的占位符（如 {{type}}, {{name}}, {{book_id}} 等）
    # frontmatter 以 --- 开始和结束
    fm_match = re.search(r"^---\n(.*?)\n---", content, re.DOTALL)
    body = content
    if fm_match:
        body = content[fm_match.end():]

    # 提取所有 {{xxx}}
    found = re.findall(r"\{\{([^}]+)\}\}", body)
    # 去重但保持顺序
    seen: set[str] = set()
    ordered: list[str] = []
    for f in found:
        name = f.strip()
        if name not in seen and name not in _AUTO_FILL_FIELDS:
            seen.add(name)
            ordered.append(name)
    return ordered


def get_template_path(type_name: str) -> str | None:
    """获取类型对应的模板文件路径。"""
    tmpl = TYPE_TO_TEMPLATE.get(type_name)
    if not tmpl:
        return None
    path = os.path.join(ASSETS_DIR, tmpl)
    if os.path.exists(path):
        return path
    return None


def get_placeholder_fields(type_name: str) -> list[str]:
    """获取指定类型模板中的所有 {{xxx}} 字段名。"""
    path = get_template_path(type_name)
    if not path:
        return []
    with open(path, encoding="utf-8") as f:
        content = f.read()
    return _extract_placeholders(content)


def list_all_types() -> dict[str, int]:
    """返回 {类型名: 字段数, ...}"""
    result: dict[str, int] = {}
    for tname in TYPE_TO_TEMPLATE:
        fields = get_placeholder_fields(tname)
        result[tname] = len(fields)
    return result


def verify_fields(type_name: str, candidate_fields: list[str]) -> dict:
    """验证候选字段名是否都存在于模板中。返回 {valid, missing, extra, all_fields}"""
    canonical = set(get_placeholder_fields(type_name))
    candidates = set(candidate_fields)
    missing = canonical - candidates      # 模板有但YAML没有
    extra = candidates - canonical        # YAML有但模板没有
    return {
        "valid": len(missing) == 0 and len(extra) == 0,
        "missing": sorted(missing),
        "extra": sorted(extra),
        "all_fields": sorted(canonical),
        "match_rate": f"{len(canonical - missing)}/{len(canonical)}" if canonical else "0/0",
    }


def generate_yaml_skeleton(type_name: str) -> str:
    """生成 YAML 骨架字符串（含占位字段）。"""
    fields = get_placeholder_fields(type_name)
    lines = [f"# {type_name} YAML 骨架 (schema_loader v52.4)"]
    lines.append(f"# 模板字段 ({len(fields)} 个):")
    lines.append("")
    lines.append("- name: 示例名称")
    lines.append("  file: 示例名称")
    lines.append("  fm:")
    lines.append("    source_chapter: 'N'")
    lines.append("    source_from: N.N.N")
    lines.append("    confidence: 0.85")
    lines.append("    confidence_note: 说明")
    lines.append("  bd:")
    for f in fields:
        if f.endswith("_diagram") or f.endswith("_analysis") or f.startswith("core_"):
            lines.append(f"    {f}: 无")
        else:
            lines.append(f"    {f}: ''")
    return "\n".join(lines)


# ── lint: 确保模板目录存在 ──
if not os.path.isdir(ASSETS_DIR):
    print(f"⚠️ 模板目录不存在: {ASSETS_DIR}", file=sys.stderr)
    sys.exit(1)


# ── CLI ──
def main():
    if len(sys.argv) < 2:
        print("用法: python3 schema_loader.py <action> [args...]")
        print("  list                       — 列出所有类型及字段数")
        print("  extract <type> [--yaml]    — 提取字段列表或 YAML 骨架")
        print("  verify <type> <f1> [f2..]  — 验证字段名合法性")
        print("  validate <yaml_path>       — 验证 YAML bd 字段 vs 模板")
        return

    action = sys.argv[1]

    if action == "list":
        types = list_all_types()
        print(f"{'类型':<12} {'字段数':<6} {'模板文件'}")
        print("-" * 50)
        for tname in sorted(types):
            print(f"{tname:<12} {types[tname]:<6} {TYPE_TO_TEMPLATE.get(tname, '?')}")

    elif action == "extract":
        if len(sys.argv) < 3:
            print("请指定类型名称")
            return
        tname = sys.argv[2]
        if tname not in TYPE_TO_TEMPLATE:
            print(f"未知类型: {tname}。可用类型: {', '.join(TYPE_TO_TEMPLATE.keys())}")
            return
        if "--yaml" in sys.argv:
            print(generate_yaml_skeleton(tname))
        else:
            fields = get_placeholder_fields(tname)
            print(f"类型: {tname}  ({len(fields)} 个字段)")
            print()
            for f in fields:
                print(f"  {f}")

    elif action == "verify":
        if len(sys.argv) < 4:
            print("用法: schema_loader.py verify <type> <field1> [field2..]")
            return
        tname = sys.argv[2]
        candidates = sys.argv[3:]
        if tname not in TYPE_TO_TEMPLATE:
            print(f"未知类型: {tname}")
            return
        result = verify_fields(tname, candidates)
        if result["valid"]:
            print(f"✅ {tname}: 全部 {len(candidates)} 个字段名合法")
        else:
            if result["missing"]:
                print(f"⚠️ 缺少字段 ({len(result['missing'])}): {', '.join(result['missing'][:10])}")
            if result["extra"]:
                print(f"⚠️ 多余字段 ({len(result['extra'])}): {', '.join(result['extra'][:10])}")
            print(f"匹配率: {result['match_rate']}")

    elif action == "validate":
        if len(sys.argv) < 3:
            print("用法: schema_loader.py validate <yaml_path>")
            return
        yaml_path = sys.argv[2]
        if not os.path.exists(yaml_path):
            print(f"文件不存在: {yaml_path}")
            return
        try:
            import yaml as _yaml
        except ImportError:
            print("需要 pyyaml: pip install pyyaml")
            return
        with open(yaml_path, encoding="utf-8") as f:
            data = _yaml.safe_load(f)
        if not data or not isinstance(data, list):
            print(f"YAML 格式错误或为空: {yaml_path}")
            return
        # 自动推断类型 — 从 phase data file 名
        basename = os.path.basename(yaml_path).replace(".yaml", "")
        type_map = {
            "concepts": "concept", "kes": "ke", "entities": "entity",
            "kps": "kp", "sps": "sp", "scenes": "scene",
            "exercises": "exercise", "solutions": "solution",
        }
        tname = type_map.get(basename)
        if not tname:
            print(f"无法从文件名推断类型: {basename}")
            print(f"请用 'extract <type>' 手动检查")
            return
        canonical = set(get_placeholder_fields(tname))
        total_ok = 0
        total_items = 0
        for idx, item in enumerate(data):
            bd = item.get("bd", {})
            bd_fields = set(bd.keys()) if bd else set()
            missing = canonical - bd_fields
            extra = bd_fields - canonical
            total_items += 1
            if not missing and not extra:
                total_ok += 1
            else:
                name = item.get("name", f"[{idx}]")
                if missing:
                    print(f"  ⚠️ [{name}] 缺 {len(missing)} 字段: {', '.join(sorted(missing)[:5])}")
                if extra:
                    print(f"  ⚠️ [{name}] 多余 {len(extra)} 字段: {', '.join(sorted(extra)[:5])}")
        print(f"\n{'✅' if total_ok == total_items else '⚠️'} {yaml_path}: {total_ok}/{total_items} 条目字段完整")

    else:
        print(f"未知操作: {action}")
        print("可用操作: list, extract, verify, validate")


if __name__ == "__main__":
    main()
