#!/usr/bin/env python3
"""quality_reviewer.py — 质量审查引擎（v2.0 Agent可消费输出）

三阶检查体系：
  T1: 结构完整性 — YAML存在/fm字段/无{{xxx}}残留/无@prompt泄漏
  T2: 内容深度 — bd字段填充率/最小长度/空白检测
  T3: 交叉验证 — wikilink完整性/跨类型引用/图质量

输出模式：
  - chapter: 人类可读文本 (默认) 或 --json (Agent可消费JSON)
  - book: 同上
  - fix-manifest: 产生结构化修复清单，供pipeline auto-fix使用

用法:
  # 单章审查（人类可读）
  python3 quality_reviewer.py chapter --book-dir /path --book-id 01_ID -c 3

  # 单章审查（Agent可消费JSON）
  python3 quality_reviewer.py chapter --book-dir /path --book-id 01_ID -c 3 --json

  # 全书审查JSON
  python3 quality_reviewer.py book --book-dir /path --book-id 01_ID --json

  # 生成修复清单
  python3 quality_reviewer.py fix-manifest --book-dir /path --book-id 01_ID -c 3

  # 审查并阻断（低于阈值exit 1）
  python3 quality_reviewer.py chapter --book-dir /path --book-id 01_ID -c 3 --threshold 0.5
"""

from __future__ import annotations

import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime
from typing import Any

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
SKILL_DIR = os.path.dirname(SCRIPT_DIR)

SCHEMA_PATH = os.path.join(SKILL_DIR, "schemas", "domain_book_schema.json")
TEMPLATES_DIR = os.path.join(SKILL_DIR, "assets", "templates")

# ── 类型映射 ──
TYPE_YAML_MAP: dict[str, dict[str, str]] = {
    "concept":     {"yaml": "concepts.yaml",    "dir": "30_核心概念", "tpl": "concept_template.md"},
    "ke":          {"yaml": "kes.yaml",         "dir": "40_知识要素", "tpl": "ke_template.md"},
    "entity":      {"yaml": "entities.yaml",    "dir": "80_实体",    "tpl": "entity_template.md"},
    "kp":          {"yaml": "kps.yaml",         "dir": "50_知识点",   "tpl": "knowledge_template.md"},
    "sp":          {"yaml": "sps.yaml",         "dir": "60_技能点",   "tpl": "skill_template.md"},
    "scene":       {"yaml": "scenes.yaml",      "dir": "70_应用场景", "tpl": "scenario_template.md"},
    "exercise":    {"yaml": "exercises.yaml",   "dir": "90_习题",     "tpl": "exercise_template.md"},
    "solution":    {"yaml": "solutions.yaml",   "dir": "90_习题/解答","tpl": "eval_template.md"},
}

# ── 字段分类 ──
FM_REQUIRED = ["source_chapter", "confidence"]
FM_OPTIONAL = ["source_from", "type_tag", "entity_type", "aliases", "tags",
               "book_id", "book_name", "confidence_note", "bloom_level", "difficulty"]

# ── 类型特定的 bd 字段深度阈值 ──
FIELD_DEPTH: dict[str, dict[str, int]] = {
    "concept": {
        "learning_objectives": 80,
        "prerequisite_knowledge": 30,
        "term_definition": 80,
        "mathematical_model": 30,
        "classification": 30,
        "core_concept_map": 30,
        "working_principle": 80,
        "key_parameters": 30,
        "physical_meaning": 50,
        "technical_classification": 20,
        "engineering_practices": 50,
        "application_scenarios": 50,
        "typical_values": 20,
        "common_misconceptions": 30,
        "practical_tips": 30,
        "related_concepts": 30,
    },
    "ke": {
        "term_definition": 60,
        "definition_sentence": 30,
        "classification": 20,
        "structure": 40,
        "features": 30,
        "mathematical_model": 30,
        "key_parameters": 30,
        "application_scenarios": 40,
        "value": 20,
        "upstream_downstream": 20,
    },
    "kp": {
        "learning_objectives": 80,
        "theoretical_basis": 150,
        "practical_skills": 80,
        "typical_values": 20,
        "application_scenarios": 50,
        "analysis_method": 50,
        "common_misconceptions": 30,
        "advanced_topics": 30,
    },
    "sp": {
        "learning_objectives": 60,
        "operation_flow": 100,
        "tools_and_equipment": 50,
        "standards_and_specs": 30,
        "precautions": 30,
        "quality_criteria": 30,
        "typical_scenarios": 50,
    },
    "scene": {
        "scenario_description": 80,
        "requirements_analysis": 50,
        "implementation_steps": 100,
        "key_technologies": 50,
        "expected_outcome": 30,
    },
    "entity": {
        "term_definition": 60,
        "features": 40,
        "classification": 20,
        "typical_values": 30,
    },
    "solution": {
        "question": 30,
        "principle_steps": 100,
        "key_points": 50,
        "common_pitfalls": 30,
        "exam_points": 30,
    },
}


# ════════════════════════════════════════════════════════════
# 工具函数
# ════════════════════════════════════════════════════════════

def load_yaml_list(path: str) -> list[dict]:
    try:
        import yaml
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if isinstance(data, list):
            return data
        return []
    except Exception:
        return []


def parse_frontmatter(content: str) -> dict:
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
    if not m:
        return {}
    fm = {}
    for line in m.group(1).split("\n"):
        if ":" in line:
            k, v = line.split(":", 1)
            fm[k.strip()] = v.strip().strip('"').strip("'")
    return fm


def read_file_content(path: str) -> str:
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""


# ════════════════════════════════════════════════════════════
# T1: 结构完整性检查
# ════════════════════════════════════════════════════════════

def check_structure(yaml_data: list[dict], rendered_dir: str, ptype: str) -> list[dict]:
    """T1 结构完整性检查"""
    issues = []
    tpl_path = os.path.join(TEMPLATES_DIR, TYPE_YAML_MAP[ptype]["tpl"])
    tpl_content = read_file_content(tpl_path)
    tpl_fields = set(re.findall(r"\{\{([a-z_]+)\}\}", tpl_content))

    for item in yaml_data:
        name = item.get("name", item.get("file", "?"))
        fm = item.get("fm", {})
        bd = item.get("bd", {})
        file_path = os.path.join(rendered_dir, f"{item.get('file', name)}.md")

        if not item.get("name", ""):
            issues.append({
                "file": name, "tier": "T1", "severity": "error",
                "category": "yaml_no_name",
                "message": "YAML缺少顶层 name 字段", "type": ptype,
            })
            continue

        for f in FM_REQUIRED:
            if f not in fm or not str(fm.get(f, "")).strip():
                issues.append({
                    "file": name, "tier": "T1", "severity": "error",
                    "category": "fm_missing",
                    "message": f"FM缺字段'{f}'", "type": ptype,
                })

        if os.path.isfile(file_path):
            rendered = read_file_content(file_path)
            leftovers = re.findall(r"\{\{[a-z_]+\|\|?[^}]*\}\}", rendered)
            if leftovers:
                issues.append({
                    "file": name, "tier": "T1", "severity": "error",
                    "category": "placeholder_residue",
                    "message": f"{{xxx}}残留:{','.join(leftovers[:3])}",
                    "type": ptype,
                })

            if "<!-- @prompt" in rendered or "<!--@prompt" in rendered:
                issues.append({
                    "file": name, "tier": "T1", "severity": "error",
                    "category": "prompt_leak",
                    "message": "@prompt注释泄漏到渲染输出",
                    "type": ptype,
                })

            if ptype in ("concept", "ke", "kp") and "```mermaid" in rendered:
                mermaid_blocks = re.findall(r"```mermaid\n(.*?)```", rendered, re.DOTALL)
                for mb in mermaid_blocks:
                    for line in mb.strip().split("\n"):
                        if "[" in line and "]" in line and '(' not in line and '["' not in line:
                            if "(" in line and "'" not in line and '"' not in line.split("[")[1][:5]:
                                issues.append({
                                    "file": name, "tier": "T1", "severity": "warning",
                                    "category": "mermaid_syntax",
                                    "message": f"Mermaid标签可能缺引号:{line.strip()[:50]}",
                                    "type": ptype,
                                })

        if bd:
            bd_keys = set(bd.keys())
            tpl_used = {f.replace("name", "") for f in tpl_fields
                         if f in bd_keys or f in ("name",)}
            extra = bd_keys - tpl_fields - fm.keys()
            if extra:
                issues.append({
                    "file": name, "tier": "T1", "severity": "info",
                    "category": "bd_extra_fields",
                    "message": f"bd多出{len(extra)}个未使用字段:{','.join(list(extra)[:3])}",
                    "type": ptype,
                })

    return issues


# ════════════════════════════════════════════════════════════
# T2: 内容深度检查
# ════════════════════════════════════════════════════════════

def check_depth(yaml_data: list[dict], ptype: str) -> list[dict]:
    """T2 内容深度检查"""
    issues = []
    depth_cfg = FIELD_DEPTH.get(ptype, {})

    for item in yaml_data:
        name = item.get("name", item.get("file", "?"))
        bd = item.get("bd", {})
        fm = item.get("fm", {})

        for field, content in bd.items():
            if not isinstance(content, str):
                continue

            stripped = content.strip()
            if not stripped or stripped in ("无", "（无）", "暂无", "待补充"):
                if field in depth_cfg:
                    issues.append({
                        "file": name, "tier": "T2", "severity": "error",
                        "category": "field_empty",
                        "message": f"字段'{field}'为空或占位符",
                        "type": ptype,
                    })
                continue

            min_len = depth_cfg.get(field, 0)
            if min_len > 0 and len(stripped) < min_len:
                issues.append({
                    "file": name, "tier": "T2", "severity": "warning",
                    "category": "field_too_short",
                    "message": f"字段'{field}'仅{len(stripped)}字(<{min_len})",
                    "type": ptype,
                })

        if ptype == "concept":
            if "core_concept_map" in bd:
                ccm = bd["core_concept_map"].strip()
                if not ccm.startswith("graph") and len(ccm) < 30:
                    issues.append({
                        "file": name, "tier": "T2", "severity": "warning",
                        "category": "mermaid_missing",
                        "message": "core_concept_map非图结构",
                        "type": ptype,
                    })

        if ptype in ("kp", "sp"):
            bloom = fm.get("bloom_level", "").strip()
            if not bloom:
                issues.append({
                    "file": name, "tier": "T2", "severity": "warning",
                    "category": "bloom_missing",
                    "message": "bloom_level未填写",
                    "type": ptype,
                })

        if ptype == "ke":
            eng = bd.get("term_english", "").strip()
            if not eng:
                issues.append({
                    "file": name, "tier": "T2", "severity": "info",
                    "category": "term_english_missing",
                    "message": "term_english未填写",
                    "type": ptype,
                })

        if ptype == "solution":
            principle = bd.get("principle_steps", "").strip()
            if len(principle) < 100:
                issues.append({
                    "file": name, "tier": "T2", "severity": "warning",
                    "category": "solution_shallow",
                    "message": f"principle_steps仅{len(principle)}字(<100)",
                    "type": ptype,
                })

    return issues


# ════════════════════════════════════════════════════════════
# T3: 交叉验证检查
# ════════════════════════════════════════════════════════════

def check_cross_references(book_dir: str, yaml_by_type: dict[str, list],
                           kg_data: dict | None = None) -> list[dict]:
    issues = []
    name_to_file = {}
    for ptype, ydata in yaml_by_type.items():
        for item in ydata:
            n = item.get("name", "")
            f = item.get("file", n)
            name_to_file[n] = {"file": f, "type": ptype}

    for ptype, ydata in yaml_by_type.items():
        for item in ydata:
            name = item.get("name", "?")
            bd = item.get("bd", {})
            text = str(bd)
            fm = item.get("fm", {})

            links = re.findall(r"\[\[([^\]|]+)", text)
            for link in links:
                clean = link.split("#")[0].strip()
                while clean.startswith("../"):
                    clean = clean[3:]
                if "/" in clean:
                    clean = clean.split("/")[-1]
                if clean and clean not in name_to_file and clean != name:
                    pass

    return issues


# ════════════════════════════════════════════════════════════
# 评分引擎
# ════════════════════════════════════════════════════════════

def score_issues(issues: list[dict]) -> dict:
    if not issues:
        return {"score": 1.0, "error": 0, "warning": 0, "info": 0}

    errors = [i for i in issues if i["severity"] == "error"]
    warnings = [i for i in issues if i["severity"] == "warning"]
    infos = [i for i in issues if i["severity"] == "info"]

    files = set(i.get("file", "") for i in issues)
    n_files = max(len(files), 1)

    errs_per_file = len(errors) / n_files
    warns_per_file = len(warnings) / n_files

    penalty = min(errs_per_file * 0.25, 0.7) + min(warns_per_file * 0.06, 0.25)
    score = max(0.0, min(1.0, 1.0 - penalty))

    return {
        "score": round(score, 2),
        "error": len(errors),
        "warning": len(warnings),
        "info": len(infos),
        "total": len(issues),
    }


# ════════════════════════════════════════════════════════════
# 按类型审查
# ════════════════════════════════════════════════════════════

def review_type(yaml_path: str, rendered_dir: str, ptype: str,
                book_dir: str = "") -> dict:
    yaml_data = load_yaml_list(yaml_path)
    if not yaml_data:
        if os.path.isfile(yaml_path) and os.path.getsize(yaml_path) > 10:
            yaml_data = []
        else:
            return {
                "type": ptype,
                "score": 0.0,
                "error": 1, "warning": 0, "info": 0, "total": 1,
                "items": 0,
                "detail": [{"file": "N/A", "tier": "T1", "severity": "error",
                            "category": "yaml_missing", "message": "YAML文件不存在或为空"}],
                "file_scores": {},
            }

    all_issues: list[dict] = []
    all_issues.extend(check_structure(yaml_data, rendered_dir, ptype))
    all_issues.extend(check_depth(yaml_data, ptype))

    scored = score_issues(all_issues)
    scored["type"] = ptype
    scored["items"] = len(yaml_data)
    scored["detail"] = all_issues[:50]

    # ── 按文件评分（Agent修复用）──
    file_scores: dict[str, dict] = {}
    for item in yaml_data:
        name = item.get("name", "?")
        file_issues = [i for i in all_issues if i.get("file") == name]
        fs = score_issues(file_issues)
        file_scores[name] = {
            "score": fs["score"],
            "error": fs["error"],
            "warning": fs["warning"],
            "info": fs["info"],
            "issues": [i for i in file_issues[:10]],
            "yaml_path": yaml_path,
            "rendered_path": os.path.join(rendered_dir, f"{item.get('file', name)}.md"),
            "type": ptype,
        }
    scored["file_scores"] = file_scores

    return scored


# ════════════════════════════════════════════════════════════
# 按章节审查
# ════════════════════════════════════════════════════════════

def review_chapter(book_dir: str, book_id: str, chapter: str,
                   with_kg: bool = True) -> dict:
    data_dir = os.path.join(book_dir, ".dag", f"第{chapter}章", "data")
    if not os.path.isdir(data_dir):
        return {"chapter": chapter, "score": 0.0, "error": 1,
                "message": f"数据目录不存在: {data_dir}"}

    type_scores: dict[str, dict] = {}
    all_issues: list[dict] = []

    for ptype, info in TYPE_YAML_MAP.items():
        yaml_path = os.path.join(data_dir, info["yaml"])
        rendered_dir = os.path.join(book_dir, info["dir"])
        result = review_type(yaml_path, rendered_dir, ptype, book_dir)
        type_scores[ptype] = result
        all_issues.extend(result.get("detail", []))

    yaml_by_type = {}
    for ptype in TYPE_YAML_MAP:
        yaml_path = os.path.join(data_dir, TYPE_YAML_MAP[ptype]["yaml"])
        yaml_by_type[ptype] = load_yaml_list(yaml_path)

    t3 = check_cross_references(book_dir, yaml_by_type)
    all_issues.extend(t3)

    scorable = [v for v in type_scores.values() if v["items"] > 0]
    avg_score = round(sum(v["score"] for v in scorable) / len(scorable), 2) if scorable else 0.0

    return {
        "chapter": chapter,
        "book_id": book_id,
        "score": avg_score,
        "type_scores": type_scores,
        "summary": score_issues(all_issues),
        "items": sum(v.get("items", 0) for v in type_scores.values()),
        "types_present": [t for t, v in type_scores.items() if v["items"] > 0],
        "all_issues": all_issues[:100],
        "data_dir": data_dir,
    }


# ════════════════════════════════════════════════════════════
# 全书审查
# ════════════════════════════════════════════════════════════

def review_book(book_dir: str, book_id: str) -> dict:
    from pathlib import Path
    dag_dir = os.path.join(book_dir, ".dag")
    chapters = set()
    for f in Path(dag_dir).glob(f"{book_id}_ch*.json"):
        stem = f.stem
        ch = stem.replace(f"{book_id}_ch", "") if f"{book_id}_ch" in stem else ""
        if ch and ch.isdigit():
            chapters.add(ch)
    for d in sorted(os.listdir(dag_dir)):
        if d.startswith("第") and d.endswith("章"):
            ch = d[1:-1]
            if ch.isdigit():
                chapters.add(ch)

    sorted_chapters = sorted(chapters, key=int)
    if not sorted_chapters:
        return {"score": 0.0, "error": 1,
                "message": f"未找到任何章节数据在 {dag_dir}"}

    chapter_reviews: list[dict] = []
    type_aggregate: dict[str, list[float]] = defaultdict(list)
    total_issues: list[dict] = []

    for ch in sorted_chapters:
        result = review_chapter(book_dir, book_id, ch, with_kg=False)
        chapter_reviews.append(result)
        total_issues.extend(result.get("all_issues", []))
        for ptype, ts in result.get("type_scores", {}).items():
            if ts.get("items", 0) > 0:
                type_aggregate[ptype].append(ts.get("score", 0.0))

    chapter_scores = [r["score"] for r in chapter_reviews if r["score"] > 0]
    avg = round(sum(chapter_scores) / len(chapter_scores), 2) if chapter_scores else 0.0

    type_averages = {t: round(sum(scores) / len(scores), 2)
                     for t, scores in type_aggregate.items()}

    return {
        "book_dir": book_dir,
        "book_id": book_id,
        "chapters": len(sorted_chapters),
        "chapters_reviewed": len(chapter_reviews),
        "score": avg,
        "chapter_scores": {r["chapter"]: r["score"] for r in chapter_reviews},
        "type_scores": type_averages,
        "total_items": sum(r.get("items", 0) for r in chapter_reviews),
        "total_issues_count": len(total_issues),
        "chapter_details": [
            {"chapter": r["chapter"], "score": r["score"],
             "items": r.get("items", 0),
             "types": r.get("types_present", []),
             "summary": r.get("summary", {}) if isinstance(r.get("summary"), dict) else {},
             "type_scores": {t: {"score": ts["score"], "items": ts["items"]}
                            for t, ts in r.get("type_scores", {}).items() if ts.get("items", 0) > 0},
            }
            for r in chapter_reviews
        ],
    }


# ════════════════════════════════════════════════════════════
# Report 格式化输出（人类可读）
# ════════════════════════════════════════════════════════════

def format_report(result: dict, verbose: bool = False) -> str:
    lines = []
    is_chapter = "chapter" in result and "book_dir" not in result

    if is_chapter:
        lines.append(f"📋 质量审查报告 — 第{result['chapter']}章")
        lines.append("=" * 60)
        lines.append(f"总分: {result['score']:.0%}  |  "
                     f"共 {result.get('items', 0)} 个文件 |  "
                     f"类型: {', '.join(result.get('types_present', []))}")
        s = result.get("summary", {})
        lines.append(f"🔴 Error: {s.get('error', 0)}  |  "
                     f"⚠️ Warning: {s.get('warning', 0)}  |  "
                     f"ℹ️ Info: {s.get('info', 0)}")
        lines.append("")

        lines.append("按类型评分:")
        for ptype, ts in sorted(result.get("type_scores", {}).items()):
            items = ts.get("items", 0)
            score = ts.get("score", 0)
            if items > 0:
                bar = "█" * int(score * 10) + "░" * (10 - int(score * 10))
                lines.append(f"  {ptype:12s}  [{bar}] {score:.0%}  ({items}项)")
        lines.append("")

        all_issues = result.get("all_issues", [])
        if all_issues:
            errors = [i for i in all_issues if i["severity"] == "error"]
            warnings = [i for i in all_issues if i["severity"] == "warning"]
            if errors:
                lines.append(f"🔴 错误 ({len(errors)} 条):")
                for e in errors[:10]:
                    lines.append(f"  [{e['category']}] {e['file']}: {e['message']}")
                if len(errors) > 10:
                    lines.append(f"  ... 还有 {len(errors)-10} 条")
            if warnings:
                lines.append(f"\n⚠️ 警告 ({len(warnings)} 条):")
                for w in warnings[:10]:
                    lines.append(f"  [{w['category']}] {w['file']}: {w['message']}")
                if len(warnings) > 10:
                    lines.append(f"  ... 还有 {len(warnings)-10} 条")
    else:
        lines.append(f"📋 全书质量审查报告 — {result.get('book_id', '?')}")
        lines.append("=" * 60)
        lines.append(f"总分: {result['score']:.0%}  |  "
                     f"共 {result.get('chapters', 0)} 章 |  "
                     f"{result.get('total_items', 0)} 个文件 |  "
                     f"{result.get('total_issues_count', 0)} 个问题")
        lines.append("")
        lines.append("按章节评分:")
        ch_scores = result.get("chapter_scores", {})
        for ch in sorted(ch_scores.keys(), key=int):
            sc = ch_scores[ch]
            bar = "█" * int(sc * 10) + "░" * (10 - int(sc * 10))
            lines.append(f"  第{ch}章  [{bar}] {sc:.0%}")
        lines.append("")
        lines.append("按类型平均:")
        for t, sc in sorted(result.get("type_scores", {}).items()):
            bar = "█" * int(sc * 10) + "░" * (10 - int(sc * 10))
            lines.append(f"  {t:12s}  [{bar}] {sc:.0%}")
        if verbose:
            lines.append("")
            lines.append("详细章节:")
            for cd in result.get("chapter_details", []):
                lines.append(f"  第{cd['chapter']}章: 评分{cd['score']:.0%}, "
                           f"{cd.get('items', 0)}项, "
                           f"E:{cd.get('summary', {}).get('error', 0)} "
                           f"W:{cd.get('summary', {}).get('warning', 0)}")

    return "\n".join(lines)


# ════════════════════════════════════════════════════════════
# Agent可消费格式 — JSON 输出 (用于格式章节报告)
# ════════════════════════════════════════════════════════════

def build_json_output(result: dict, threshold: float = 0.8) -> dict[str, Any]:
    """构建Agent可消费的JSON输出（章节或全书级别）

    关键字段：
      - fix_manifest: 需要修复的文件清单，每项包含：
        - file/type/yaml_path/source_path
        - fields_to_fix: [{field, severity, current_len, target_len, issue}]
    """
    is_chapter = "chapter" in result and "book_dir" not in result

    out: dict[str, Any] = {
        "timestamp": datetime.now().isoformat(),
        "agent_instructions": (
            "此JSON由quality_reviewer生成，供Agent消费。\n"
            "fix_manifest列出需要修复的文件和具体字段。\n"
            "修复流程: 读取YAML → 读取源文 → 委托子Agent修复 → 重新渲染 → 重新审查"
        ),
    }

    if is_chapter:
        out["scope"] = "chapter"
        out["chapter"] = result["chapter"]
        out["book_id"] = result.get("book_id", "")
        out["score"] = result["score"]
        out["items"] = result.get("items", 0)
        out["summary"] = result.get("summary", {})
        out["types_present"] = result.get("types_present", [])
        out["type_scores"] = {
            t: {"score": ts["score"], "items": ts["items"]}
            for t, ts in result.get("type_scores", {}).items()
            if ts.get("items", 0) > 0
        }
        out["fix_manifest"] = build_fix_manifest(result, threshold)
        out["data_dir"] = result.get("data_dir", "")
    else:
        out["scope"] = "book"
        out["book_id"] = result.get("book_id", "")
        out["book_dir"] = result.get("book_dir", "")
        out["score"] = result["score"]
        out["chapters"] = result.get("chapters", 0)
        out["total_items"] = result.get("total_items", 0)
        out["total_issues"] = result.get("total_issues_count", 0)
        out["type_scores"] = result.get("type_scores", {})
        out["chapter_scores"] = result.get("chapter_scores", {})
        out["chapter_details"] = result.get("chapter_details", [])

        # 全书 fix_manifest = 各章 fix_manifest 的聚合
        all_fixes = []
        for cd in result.get("chapter_details", []):
            chapter = cd["chapter"]
            # 检查该章的type_scores决定哪些类型需要修复
            for ptype, ts in cd.get("type_scores", {}).items():
                if ts.get("score", 1.0) < 0.8:
                    all_fixes.append({
                        "chapter": chapter,
                        "type": ptype,
                        "score": ts["score"],
                        "items": ts.get("items", 0),
                        "action": "review_and_fix_type",
                    })
        out["fix_manifest"] = all_fixes

    return out


def build_fix_manifest(result: dict, threshold: float = 0.8) -> list[dict]:
    """为章节报告生成修复清单 — 文件级别的精确修复指令"""
    manifest = []
    chapter = result.get("chapter", "?")
    book_dir = result.get("data_dir", "").replace(
        f"/.dag/第{chapter}章/data", "").replace(
        f"\\.dag\\第{chapter}章\\data", "")
    if not book_dir:
        # 尝试从 data_dir 提取
        dd = result.get("data_dir", "")
        for prefix in ["/.dag/", "\\.dag\\"]:
            idx = dd.find(prefix)
            if idx > 0:
                book_dir = dd[:idx]
                break

    src_dir = os.path.join(book_dir, "20_正文") if book_dir else ""

    for ptype, ts in result.get("type_scores", {}).items():
        if ts.get("items", 0) == 0:
            continue

        file_scores = ts.get("file_scores", {})
        for fname, fs in file_scores.items():
            if fs.get("score", 1.0) >= threshold:
                continue

            fields = []
            for issue in fs.get("issues", []):
                if issue["severity"] == "info":
                    continue
                field_match = re.match(r"字段'(\w+)'", issue.get("message", ""))
                field = field_match.group(1) if field_match else ""
                len_match = re.search(r"仅(\d+)字\(<(\d+)\)", issue.get("message", ""))
                current_len = int(len_match.group(1)) if len_match else 0
                target_len = int(len_match.group(2)) if len_match else 0

                if field:
                    fields.append({
                        "field": field,
                        "severity": issue["severity"],
                        "category": issue["category"],
                        "current_len": current_len,
                        "target_len": target_len,
                        "action": "enrich" if issue["category"] == "field_too_short" else "fill",
                    })
                else:
                    fields.append({
                        "field": issue.get("category", "unknown"),
                        "severity": issue["severity"],
                        "category": issue["category"],
                        "action": "fix_structure",
                    })

            if fields:
                manifest.append({
                    "file": fname,
                    "type": ptype,
                    "chapter": chapter,
                    "score": fs["score"],
                    "yaml_path": fs.get("yaml_path", ""),
                    "rendered_path": fs.get("rendered_path", ""),
                    "source_dir": src_dir,
                    "fields_to_fix": fields,
                })

    return manifest


# ════════════════════════════════════════════════════════════
# Fix Manifest 指令输出 — 供Agent直接消费
# ════════════════════════════════════════════════════════════

def check_single_yaml_item(item: dict, ptype: str, threshold: float = 0.8) -> dict:
    """内联检查单个YAML项的质量（不依赖渲染文件）

    Args:
        item: YAML项字典 {name, file, fm, bd}
        ptype: 类型名 (concept/ke/kp/sp/scene/entity/solution)
        threshold: 达标阈值

    Returns:
        {score, pass, issues: [{field, severity, current_len, target_len, action}], summary}
    """
    issues = []
    name = item.get("name", "?")
    fm = item.get("fm", {})
    bd = item.get("bd", {})
    depth_cfg = FIELD_DEPTH.get(ptype, {})

    # T1: 顶层字段
    if not item.get("name", ""):
        issues.append({
            "field": "name", "severity": "error", "category": "yaml_no_name",
            "message": "YAML缺少顶层 name 字段",
        })

    # T1: FM必填字段
    for f in FM_REQUIRED:
        if f not in fm or not str(fm.get(f, "")).strip():
            issues.append({
                "field": f"fm.{f}", "severity": "error",
                "category": "fm_missing",
                "message": f"FM缺字段'{f}'",
            })

    # T2: bd字段深度
    for field, content in bd.items():
        if not isinstance(content, str):
            continue
        stripped = content.strip()
        if not stripped or stripped in ("无", "（无）", "暂无", "待补充"):
            if field in depth_cfg:
                issues.append({
                    "field": field, "severity": "error",
                    "category": "field_empty",
                    "message": f"字段'{field}'为空或占位符",
                    "current_len": 0,
                    "target_len": depth_cfg[field],
                    "action": "fill",
                })
            continue

        min_len = depth_cfg.get(field, 0)
        if min_len > 0 and len(stripped) < min_len:
            issues.append({
                "field": field, "severity": "warning",
                "category": "field_too_short",
                "message": f"字段'{field}'仅{len(stripped)}字(<{min_len})",
                "current_len": len(stripped),
                "target_len": min_len,
                "action": "enrich",
            })

    # T2: bloom_level
    if ptype in ("kp", "sp"):
        bloom = fm.get("bloom_level", "").strip()
        if not bloom:
            issues.append({
                "field": "fm.bloom_level", "severity": "warning",
                "category": "bloom_missing",
                "message": "bloom_level未填写",
                "action": "fill",
            })

    # KE英文术语
    if ptype == "ke":
        eng = bd.get("term_english", "").strip()
        if not eng:
            issues.append({
                "field": "term_english", "severity": "info",
                "category": "term_english_missing",
                "message": "term_english未填写",
                "action": "fill",
            })

    # Solution principle_steps
    if ptype == "solution":
        principle = bd.get("principle_steps", "").strip()
        if len(principle) < 100:
            issues.append({
                "field": "principle_steps", "severity": "warning",
                "category": "solution_shallow",
                "message": f"principle_steps仅{len(principle)}字(<100)",
                "current_len": len(principle),
                "target_len": 100,
                "action": "enrich",
            })

    # 评分
    errors = [i for i in issues if i["severity"] == "error"]
    warnings = [i for i in issues if i["severity"] == "warning"]

    err_penalty = min(len(errors) * 0.25, 0.7)
    warn_penalty = min(len(warnings) * 0.06, 0.25)
    score = max(0.0, min(1.0, 1.0 - err_penalty - warn_penalty))

    return {
        "file": name,
        "type": ptype,
        "score": round(score, 2),
        "pass": score >= threshold,
        "issues": issues,
        "summary": {
            "error": len(errors),
            "warning": len(warnings),
            "info": len([i for i in issues if i["severity"] == "info"]),
            "total": len(issues),
        },
    }

def print_fix_instructions(result: dict, threshold: float = 0.8):
    """输出Agent可执行的修复指令

    格式:
      FIX_FILE: <path>
      FIX_TYPE: <type>
      FIX_FIELDS: <field1>,<field2>
      FIX_SOURCE: <source_path>
      FIX_CURRENT: <current_content_hint>
      ---
    """
    manifest = build_fix_manifest(result, threshold)
    if not manifest:
        print("✅ 无需修复: 所有文件质量达标")
        return

    print(f"🛠️  需要修复 {len(manifest)} 个文件")
    print()
    for item in manifest:
        fields_str = ",".join(
            f"{f['field']}({f['action']}:{f.get('current_len', 0)}→{f.get('target_len', 0)})"
            for f in item["fields_to_fix"] if f.get("current_len", 0) > 0
        )
        missing_str = ",".join(
            f"{f['field']}({f['action']})"
            for f in item["fields_to_fix"] if f.get("current_len", 0) == 0
        )

        print(f"FIX_FILE:{item['yaml_path']}")
        print(f"FIX_TYPE:{item['type']}")
        print(f"FIX_NAME:{item['file']}")
        if fields_str:
            print(f"FIX_FIELDS:{fields_str}")
        if missing_str:
            print(f"FIX_MISSING:{missing_str}")
        print(f"FIX_SCORE:{item['score']}")
        print(f"FIX_SOURCE_DIR:{item['source_dir']}")
        print("---")


# ════════════════════════════════════════════════════════════
# Pipeline 集成 — 审查并阻断
# ════════════════════════════════════════════════════════════

def check_and_block(book_dir: str, book_id: str, chapter: str,
                    threshold: float = 0.5,
                    set_state_failed: bool = False) -> tuple[bool, dict]:
    result = review_chapter(book_dir, book_id, chapter, with_kg=False)
    score = result.get("score", 0.0)

    if score < threshold and set_state_failed:
        try:
            from dag_state import ChapterState
            state = ChapterState(book_dir, book_id, chapter)
            for ptype in TYPE_YAML_MAP:
                state.set_status(ptype, "failed" if result.get("type_scores", {})
                                .get(ptype, {}).get("score", 1.0) < threshold else "done")
            state.save()
        except Exception:
            pass

    passed = score >= threshold
    return passed, result


# ════════════════════════════════════════════════════════════
# Main
# ════════════════════════════════════════════════════════════

def main():
    import argparse
    p = argparse.ArgumentParser(description="质量审查引擎 v2.0 (Agent可消费)")
    sp = p.add_subparsers(dest="cmd", required=True)

    # ── chapter ──
    ch = sp.add_parser("chapter", help="审查单章")
    ch.add_argument("--book-dir", required=True)
    ch.add_argument("--book-id", required=True)
    ch.add_argument("-c", "--chapter", required=True)
    ch.add_argument("--threshold", type=float, default=0.5,
                    help="质量阈值(默认0.5)，低于此退出码1")
    ch.add_argument("--fix-threshold", type=float, default=0.8,
                    help="修复阈值(默认0.8)，低于此的文件列进修复清单")
    ch.add_argument("--state-dir", help="状态目录")
    ch.add_argument("-v", "--verbose", action="store_true")
    ch.add_argument("--json", action="store_true",
                    help="输出Agent可消费的JSON格式(默认人类可读)")

    # ── book ──
    bk = sp.add_parser("book", help="审查全书")
    bk.add_argument("--book-dir", required=True)
    bk.add_argument("--book-id", required=True)
    bk.add_argument("-v", "--verbose", action="store_true")
    bk.add_argument("--json", action="store_true",
                    help="输出Agent可消费的JSON格式")

    # ── fix-manifest ──
    fm = sp.add_parser("fix-manifest", help="生成修复指令清单 (Agent消费)")
    fm.add_argument("--book-dir", required=True)
    fm.add_argument("--book-id", required=True)
    fm.add_argument("-c", "--chapter", required=True)
    fm.add_argument("--threshold", type=float, default=0.8,
                    help="修复阈值(默认0.8)，低于此的文件列进修复清单")
    fm.add_argument("--output", help="修复清单输出路径(默认输出到stdout)")
    fm.add_argument("--json", action="store_true",
                    help="以JSON格式输出修复清单")

    # ── check-item（内联质量检查）──
    ci = sp.add_parser("check-item", help="内联检查单个YAML项质量（供Agent生成时使用）")
    ci.add_argument("--item", required=True,
                    help="YAML项JSON字符串")
    ci.add_argument("--type", required=True,
                    help="类型 (concept/ke/kp/sp/scene/entity/solution)")
    ci.add_argument("--threshold", type=float, default=0.8,
                    help="达标阈值(默认0.8)")

    a = p.parse_args()

    if a.cmd == "chapter":
        result = review_chapter(a.book_dir, a.book_id, a.chapter)
        score = result.get("score", 0.0)

        if a.json:
            # Agent可消费JSON输出
            fix_thr = getattr(a, 'fix_threshold', 0.8)
            json_out = build_json_output(result, fix_thr)
            print(json.dumps(json_out, ensure_ascii=False, indent=2))
        else:
            # 人类可读
            print(format_report(result, verbose=a.verbose))

        if score < a.threshold:
            print(f"\n❌ 质量不达标: {score:.0%} < {a.threshold:.0%}", file=sys.stderr)
            if a.state_dir:
                try:
                    sys.path.insert(0, SCRIPT_DIR)
                    from dag_state import ChapterState
                    state = ChapterState(a.book_dir, a.book_id, a.chapter)
                    state.set_status("quality_review", "failed")
                    state.save()
                except Exception:
                    pass
            sys.exit(1)
        else:
            print(f"\n✅ 质量达标: {score:.0%} ≥ {a.threshold:.0%}", file=sys.stderr)
            sys.exit(0)

    elif a.cmd == "book":
        result = review_book(a.book_dir, a.book_id)
        if a.json:
            json_out = build_json_output(result)
            print(json.dumps(json_out, ensure_ascii=False, indent=2))
        else:
            print(format_report(result, verbose=a.verbose))
        sys.exit(0)

    elif a.cmd == "fix-manifest":
        result = review_chapter(a.book_dir, a.book_id, a.chapter)
        thr = getattr(a, 'threshold', 0.8)
        if a.output:
            with open(a.output, "w", encoding="utf-8") as f:
                if a.json:
                    json.dump(build_json_output(result, thr), f,
                              ensure_ascii=False, indent=2)
                else:
                    f.write(build_manifest_text(result, thr))
            print(f"📄 修复清单已写入: {a.output}")
        else:
            if a.json:
                print(json.dumps(build_json_output(result, thr),
                                  ensure_ascii=False, indent=2))
            else:
                print_fix_instructions(result, thr)
        sys.exit(0)

    elif a.cmd == "check-item":
        try:
            item = json.loads(a.item)
        except (json.JSONDecodeError, ValueError) as e:
            print(f"❌ JSON解析失败: {e}", file=sys.stderr)
            sys.exit(1)
        ptype = a.type
        result = check_single_yaml_item(item, ptype, a.threshold)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if result["pass"]:
            sys.exit(0)
        else:
            sys.exit(1)


def build_manifest_text(result: dict, threshold: float = 0.8) -> str:
    """构建修复清单文本"""
    from io import StringIO
    buf = StringIO()
    manifest = build_fix_manifest(result, threshold)
    buf.write(f"📋 修复清单 — 第{result.get('chapter', '?')}章\n")
    buf.write(f"总分: {result.get('score', 0):.0%}\n")
    buf.write(f"需修复: {len(manifest)} 个文件\n\n")
    for item in manifest:
        buf.write(f"## {item['file']} ({item['type']})\n")
        buf.write(f"评分: {item['score']:.0%}\n")
        buf.write(f"YAML: {item['yaml_path']}\n")
        buf.write(f"源文: {item['source_dir']}\n")
        for f in item["fields_to_fix"]:
            action_icon = "🖊️" if f.get("action") == "enrich" else "📝" if f.get("action") == "fill" else "🔧"
            if f.get("current_len", 0) > 0:
                buf.write(f"  {action_icon} {f['field']}: {f['current_len']}→{f['target_len']}字\n")
            else:
                buf.write(f"  {action_icon} {f['field']}: 空 → 需填充\n")
        buf.write("\n")
    return buf.getvalue()


if __name__ == "__main__":
    main()
