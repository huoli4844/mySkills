#!/usr/bin/env python3
"""
validate_chapter_data.py — 构建前验证第N章 YAML 数据
检查常见错误模式，可自动修复。

用法:
  python3 validate_chapter_data.py --chapter 3              # 只报告
  python3 validate_chapter_data.py --chapter 3 --fix        # 自动修复
"""

import os

from log_utils import get_logger

log = get_logger(__name__)


import yaml  # noqa: E402

SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SKILL_DIR, "data")

REQUIRED_CONCEPT_BD_FIELDS = [
    "term_english",
    "term_definition",
    "source",
    "definition_sentence",
    "definition_source",
    "core_concept_map",
    "core_concept_map_source",
    "core_concept_map_analysis",
    "additional_explanations",
    "formula_references",
    "figure_references",
    "structure",
    "mathematical_model",
    "tech_classification",
    "application_scenarios",
    "typical_systems",
    "related_concepts_relations",
    "confusion_compare",
    "evolution",
    "engineering_practices",
    "common_misconceptions",
    "references",
    "related_knowledge_elements",
    "self_check_questions",
]

REQUIRED_KE_BD_FIELDS = [
    "definition",
    "classification",
    "structure",
    "key_parameters",
    "features",
    "application_scenarios",
    "value",
    "upstream_downstream",
    "related_knowledge_elements",
    "references",
    "source",
    "domain",
]

CONFIDENCE_NOTES = {
    0.95: "精准释义逐字匹配出处原文",
    0.85: "基于正文内容归纳生成",
    0.75: "基于正文内容归纳生成",
    0.65: "基于正文内容归纳生成",
}


def validate_file(filename, chapter, fix=False):
    path = os.path.join(DATA_DIR, filename)
    if not os.path.exists(path):
        return [], f"文件不存在: {filename}"

    with open(path) as f:
        items = yaml.safe_load(f) or []

    ch_items = [it for it in items if str(it.get("fm", {}).get("source_chapter", "")) == chapter]
    if not ch_items:
        return [], f"第{chapter}章无条目"

    errors = []
    fixed = 0

    for item in ch_items:
        name = item.get("name", "?")
        bd = item.get("bd")
        fm = item.get("fm", {})

        # bd must be a dict
        if isinstance(bd, str):
            errors.append(f"[{name}] bd 是字符串( {len(bd)} 字符)而非字典")

        # missing confidence_note
        if not fm.get("confidence_note"):
            expected_note = CONFIDENCE_NOTES.get(fm.get("confidence"), "基于正文内容归纳生成")
            errors.append(f"[{name}] 缺失 confidence_note")
            if fix:
                item["fm"]["confidence_note"] = expected_note
                fixed += 1

        # source_chapter type
        sc = fm.get("source_chapter")
        if sc is not None and not isinstance(sc, str):
            errors.append(f"[{name}] source_chapter 是 {type(sc).__name__}({sc}) 而非字符串")
            if fix:
                item["fm"]["source_chapter"] = str(sc)
                fixed += 1

        # missing bd fields
        exp_fields = REQUIRED_CONCEPT_BD_FIELDS if filename == "concepts.yaml" else REQUIRED_KE_BD_FIELDS
        if exp_fields and isinstance(bd, dict):
            for field in exp_fields:
                if field not in bd:
                    errors.append(f"[{name}] bd 缺失字段: {field}")
                    if fix:
                        bd[field] = "无"
                        fixed += 1

        # empty definition_source
        def_src = ""
        if isinstance(bd, dict):
            def_src = bd.get("definition_source", "")
        if isinstance(def_src, str) and not def_src.strip():
            errors.append(f"[{name}] definition_source 为空")
            if fix:
                sf = fm.get("source_from", f"第{chapter}章")
                bd["definition_source"] = f"来源：{sf}"
                fixed += 1

    # Save fixes
    if fix and fixed > 0:
        # P0-1: 原子写入
        import tempfile as _tmp

        fd, tmpname = _tmp.mkstemp(dir=os.path.dirname(path), suffix=".yaml.tmp")
        try:
            with os.fdopen(fd, "w") as f:
                yaml.dump(items, f, allow_unicode=True, default_flow_style=False, sort_keys=False, indent=2, width=120)
            os.replace(tmpname, path)
        except OSError:
            if os.path.exists(tmpname):
                os.unlink(tmpname)
            raise

    report = f"{filename}: {len(errors)} 问题"
    if fix and fixed > 0:
        report += f"，已修复 {fixed} 个"
    elif not errors:
        report = f"{filename}: ✅ 第{chapter}章无问题"
    return errors, report


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--chapter", required=True)
    parser.add_argument("--fix", action="store_true")
    args = parser.parse_args()

    ch = args.chapter
    all_err = 0
    for fname in ["concepts.yaml", "kes.yaml", "kps.yaml", "sps.yaml", "scenes.yaml", "entities.yaml"]:
        errs, report = validate_file(fname, ch, fix=args.fix)
        for e in errs:
            log.error(f"  ❌ {e}")
        log.info(f"  {report}")
        all_err += len(errs)
    if all_err == 0:
        log.success(f"\n✅ 第{ch}章数据验证通过")
    else:
        log.warning(f"\n⚠️  共 {all_err} 个问题" + ("（部分已自动修复）" if args.fix else "，使用 --fix 自动修复"))


if __name__ == "__main__":
    main()
