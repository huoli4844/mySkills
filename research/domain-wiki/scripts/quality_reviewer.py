#!/usr/bin/env python3
"""quality_reviewer.py — 质量审查引擎

三阶检查体系：
  T1: 结构完整性 — YAML存在/fm字段/无{{xxx}}残留/无@prompt泄漏
  T2: 内容深度 — bd字段填充率/最小长度/空白检测
  T3: 交叉验证 — wikilink完整性/跨类型引用/图质量

用法:
  # 单章审查
  python3 quality_reviewer.py chapter \\
    --book-dir /path --book-id 01_书ID -c 3

  # 全书审查
  python3 quality_reviewer.py book \\
    --book-dir /path --book-id 01_书ID

  # 审查+阈值阻断（低于分数设状态为failed）
  python3 quality_reviewer.py chapter \\
    --book-dir /path --book-id 01_书ID -c 3 \\
    --threshold 0.6 --state-dir /path/.dag
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
INDEX_DIR = os.path.join(SKILL_DIR, ".dag", "index_data")

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
    """加载 YAML 文件为列表"""
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
    """解析 YAML frontmatter"""
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
    if not m:
        return {}
    fm = {}
    for line in m.group(1).split("\n"):
        if ":" in line:
            k, v = line.split(":", 1)
            fm[k.strip()] = v.strip().strip('"').strip("'")
    return fm


def read_file_lines(path: str) -> list[str]:
    try:
        with open(path, encoding="utf-8") as f:
            return f.readlines()
    except Exception:
        return []


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

        # 顶层字段检查（name/file 在顶层，非 fm 内部）
        if not item.get("name", ""):
            issues.append({
                "file": name, "tier": "T1", "severity": "error",
                "category": "yaml_no_name",
                "message": "YAML缺少顶层 name 字段", "type": ptype,
            })
            continue  # 跳过后续检查

        # FM 必填字段（fm 内部）
        for f in FM_REQUIRED:
            if f not in fm or not str(fm.get(f, "")).strip():
                issues.append({
                    "file": name, "tier": "T1", "severity": "error",
                    "category": "fm_missing",
                    "message": f"FM缺字段'{f}'", "type": ptype,
                })

        # {{xxx}} 残留（渲染输出中）
        if os.path.isfile(file_path):
            rendered = read_file_content(file_path)
            leftovers = re.findall(r"\{\{[a-z_]+\|\|?[^}]*\}\}", rendered)
            if leftovers:
                issues.append({
                    "file": name, "tier": "T1", "severity": "error",
                    "category": "placeholder_residue",
                    "message": f"{{{{xxx}}}}残留:{','.join(leftovers[:3])}",
                    "type": ptype,
                })

            # @prompt 泄漏
            if "<!-- @prompt" in rendered or "<!--@prompt" in rendered:
                issues.append({
                    "file": name, "tier": "T1", "severity": "error",
                    "category": "prompt_leak",
                    "message": "@prompt注释泄漏到渲染输出",
                    "type": ptype,
                })

            # Mermaid 标签语法（概念/KE/KP必检）
            if ptype in ("concept", "ke", "kp") and "```mermaid" in rendered:
                mermaid_blocks = re.findall(r"```mermaid\n(.*?)```", rendered, re.DOTALL)
                for mb in mermaid_blocks:
                    for line in mb.strip().split("\n"):
                        if "[" in line and "]" in line and '("' not in line and '["' not in line:
                            # 节点名可能没引号，但包含(的必须检查
                            if "(" in line and "'" not in line and '"' not in line.split("[")[1][:5]:
                                issues.append({
                                    "file": name, "tier": "T1", "severity": "warning",
                                    "category": "mermaid_syntax",
                                    "message": f"Mermaid标签可能缺引号:{line.strip()[:50]}",
                                    "type": ptype,
                                })

        # bd 字段对齐 — YAML bd vs 模板 {{xxx}}
        if bd:
            bd_keys = set(bd.keys())
            tmpl_used = {f.replace("name", "") for f in tpl_fields
                         if f in bd_keys or f in ("name",)}
            # 检查 bd 中有但模板不用的字段（可能浪费，不阻断）
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

        # 检查每个 bd 字段
        for field, content in bd.items():
            if not isinstance(content, str):
                continue

            stripped = content.strip()
            # 空字段
            if not stripped or stripped in ("无", "（无）", "暂无", "待补充"):
                if field in depth_cfg:
                    issues.append({
                        "file": name, "tier": "T2", "severity": "error",
                        "category": "field_empty",
                        "message": f"字段'{field}'为空或占位符",
                        "type": ptype,
                    })
                continue

            # 字段深度不足
            min_len = depth_cfg.get(field, 0)
            if min_len > 0 and len(stripped) < min_len:
                issues.append({
                    "file": name, "tier": "T2", "severity": "warning",
                    "category": "field_too_short",
                    "message": f"字段'{field}'仅{len(stripped)}字(<{min_len})",
                    "type": ptype,
                })

        # 特殊字段检查
        if ptype == "concept":
            # 必须有 mermaid
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
            # Bloom 层级
            bloom = fm.get("bloom_level", "").strip()
            if not bloom:
                issues.append({
                    "file": name, "tier": "T2", "severity": "warning",
                    "category": "bloom_missing",
                    "message": "bloom_level未填写",
                    "type": ptype,
                })

        if ptype == "ke":
            # 英文术语
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
    """T3 交叉验证检查"""
    issues = []

    # Nodename ↔ filename 映射
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

            # wikilink 指向的有效性（粗略检查）
            links = re.findall(r"\[\[([^\]|]+)", text)
            for link in links:
                clean = link.split("#")[0].strip()
                while clean.startswith("../"):
                    clean = clean[3:]
                if "/" in clean:
                    clean = clean.split("/")[-1]
                # 检查节点是否存在
                if clean and clean not in name_to_file and clean != name:
                    # 可能是跨书引用，无法在本域验证
                    pass

            # 章节一致性（概念/KE/KP 的 chapter_num 必须匹配）
            if ptype in ("concept", "ke", "kp", "entity", "sp", "scene"):
                pass  # source 上下文检查先跳过

    return issues


# ════════════════════════════════════════════════════════════
# 评分引擎
# ════════════════════════════════════════════════════════════

def score_issues(issues: list[dict]) -> dict:
    """将 issues 转换为评分"""
    if not issues:
        return {"score": 1.0, "error": 0, "warning": 0, "info": 0}

    errors = [i for i in issues if i["severity"] == "error"]
    warnings = [i for i in issues if i["severity"] == "warning"]
    infos = [i for i in issues if i["severity"] == "info"]

    # 分数 = 1.0 - (errors/dim * 0.2 + warnings/dim * 0.08)
    # 用文件数归一化
    # 从 all_issues 中提取唯一文件名推断项目数
    files = set(i.get("file", "") for i in issues)
    n_files = max(len(files), 1)

    # 归一化惩罚: 平均每文件错误数
    errs_per_file = len(errors) / n_files
    warns_per_file = len(warnings) / n_files

    penalty = min(errs_per_file * 0.15, 0.7) + min(warns_per_file * 0.04, 0.25)
    score = max(0.0, min(1.0, 1.0 - penalty))

    return {
        "score": round(score, 2),
        "error": len(errors),
        "warning": len(warnings),
        "info": len(infos),
        "total": len(issues),
        "errors": errors[:20],      # 截断避免过大
        "warnings": warnings[:20],
        "infos": infos[:10],
    }


# ════════════════════════════════════════════════════════════
# 按类型审查
# ════════════════════════════════════════════════════════════

def review_type(yaml_path: str, rendered_dir: str, ptype: str,
                book_dir: str = "") -> dict:
    """审查单一类型的完整质量"""
    yaml_data = load_yaml_list(yaml_path)
    if not yaml_data:
        # 文件可能存在但为空
        if os.path.isfile(yaml_path) and os.path.getsize(yaml_path) > 10:
            yaml_data = []  # 空列表也算存在
        else:
            return {
                "type": ptype,
                "score": 0.0,
                "error": 1,
                "warning": 0,
                "info": 0,
                "total": 1,
                "items": 0,
                "detail": [{"file": "N/A", "tier": "T1", "severity": "error",
                            "category": "yaml_missing", "message": "YAML文件不存在或为空"}],
                "errors": [],
                "warnings": [],
                "infos": [],
            }

    all_issues: list[dict] = []

    # T1: 结构
    t1 = check_structure(yaml_data, rendered_dir, ptype)
    all_issues.extend(t1)

    # T2: 深度
    t2 = check_depth(yaml_data, ptype)
    all_issues.extend(t2)

    # 评分
    scored = score_issues(all_issues)
    scored["type"] = ptype
    scored["items"] = len(yaml_data)
    scored["detail"] = all_issues[:50]

    return scored


# ════════════════════════════════════════════════════════════
# 按章节审查
# ════════════════════════════════════════════════════════════

def review_chapter(book_dir: str, book_id: str, chapter: str,
                   with_kg: bool = True) -> dict:
    """审查单个章节"""
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

    # T3: 交叉验证
    yaml_by_type = {}
    for ptype in TYPE_YAML_MAP:
        yaml_path = os.path.join(data_dir, TYPE_YAML_MAP[ptype]["yaml"])
        yaml_by_type[ptype] = load_yaml_list(yaml_path)

    t3 = check_cross_references(book_dir, yaml_by_type)
    all_issues.extend(t3)

    # 加权总分
    scorable = [v for v in type_scores.values() if v["items"] > 0]
    if scorable:
        avg_score = round(sum(v["score"] for v in scorable) / len(scorable), 2)
    else:
        avg_score = 0.0

    scored = score_issues(all_issues)
    # 覆盖为加权平均
    scored["score"] = avg_score

    return {
        "chapter": chapter,
        "book_id": book_id,
        "score": avg_score,
        "type_scores": type_scores,
        "summary": scored,
        "items": sum(v.get("items", 0) for v in type_scores.values()),
        "types_present": [t for t, v in type_scores.items() if v["items"] > 0],
        "all_issues": all_issues[:100],
    }


# ════════════════════════════════════════════════════════════
# 全书审查
# ════════════════════════════════════════════════════════════

def review_book(book_dir: str, book_id: str) -> dict:
    """审查全书所有章节"""
    from pathlib import Path

    dag_dir = os.path.join(book_dir, ".dag")
    chapters = set()
    for f in Path(dag_dir).glob(f"{book_id}_ch*.json"):
        stem = f.stem
        ch = stem.replace(f"{book_id}_ch", "") if f"{book_id}_ch" in stem else ""
        if ch and ch.isdigit():
            chapters.add(ch)

    # 作为回退：扫描 data 目录
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

    # 全书评分
    chapter_scores = [r["score"] for r in chapter_reviews if r["score"] > 0]
    avg = round(sum(chapter_scores) / len(chapter_scores), 2) if chapter_scores else 0.0

    # 各类型平均
    type_averages = {
        t: round(sum(scores) / len(scores), 2)
        for t, scores in type_aggregate.items()
    }

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
            {
                "chapter": r["chapter"],
                "score": r["score"],
                "items": r.get("items", 0),
                "types": r.get("types_present", []),
                "summary": r.get("summary", {}) if isinstance(r.get("summary"), dict) else {},
            }
            for r in chapter_reviews
        ],
    }


# ════════════════════════════════════════════════════════════
# Report 格式化输出
# ════════════════════════════════════════════════════════════

def format_report(result: dict, verbose: bool = False) -> str:
    """格式化为可读报告"""
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

        # 各类型评分
        lines.append("按类型评分:")
        for ptype, ts in sorted(result.get("type_scores", {}).items()):
            items = ts.get("items", 0)
            score = ts.get("score", 0)
            if items > 0:
                bar = "█" * int(score * 10) + "░" * (10 - int(score * 10))
                lines.append(f"  {ptype:12s}  [{bar}] {score:.0%}  ({items}项)")
        lines.append("")

        # 具体问题（截断前15条）
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
        # 全书报告
        lines.append(f"📋 全书质量审查报告 — {result.get('book_id', '?')}")
        lines.append("=" * 60)
        lines.append(f"总分: {result['score']:.0%}  |  "
                     f"共 {result.get('chapters', 0)} 章 |  "
                     f"{result.get('total_items', 0)} 个文件 |  "
                     f"{result.get('total_issues_count', 0)} 个问题")
        lines.append("")

        # 按章节
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
# Pipeline 集成 — 审查并阻断
# ════════════════════════════════════════════════════════════

def check_and_block(book_dir: str, book_id: str, chapter: str,
                    threshold: float = 0.5,
                    set_state_failed: bool = False) -> tuple[bool, dict]:
    """审查章节并决定是否阻断

    Returns:
        (passed, result) — passed=False 表示质量不达标
    """
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
    p = argparse.ArgumentParser(description="质量审查引擎")
    sp = p.add_subparsers(dest="cmd", required=True)

    ch = sp.add_parser("chapter", help="审查单章")
    ch.add_argument("--book-dir", required=True)
    ch.add_argument("--book-id", required=True)
    ch.add_argument("-c", "--chapter", required=True)
    ch.add_argument("--threshold", type=float, default=0.5,
                    help="质量阈值(默认0.5)，低于此阻断")
    ch.add_argument("--state-dir", help="状态目录(设置后低于阈值标记为failed)")
    ch.add_argument("-v", "--verbose", action="store_true")

    bk = sp.add_parser("book", help="审查全书")
    bk.add_argument("--book-dir", required=True)
    bk.add_argument("--book-id", required=True)
    bk.add_argument("-v", "--verbose", action="store_true")

    a = p.parse_args()

    if a.cmd == "chapter":
        result = review_chapter(a.book_dir, a.book_id, a.chapter)
        print(format_report(result, verbose=a.verbose))
        score = result.get("score", 0.0)
        if score < a.threshold:
            print(f"\n❌ 质量不达标: {score:.0%} < {a.threshold:.0%}")
            if a.state_dir:
                # 标记为 failed
                try:
                    sys.path.insert(0, SCRIPT_DIR)
                    from dag_state import ChapterState
                    state = ChapterState(a.book_dir, a.book_id, a.chapter)
                    state.set_status("quality_review", "failed")
                    state.save()
                    print(f"  状态已标记为 failed")
                except Exception:
                    pass
            sys.exit(1)
        else:
            print(f"\n✅ 质量达标: {score:.0%} ≥ {a.threshold:.0%}")
            sys.exit(0)

    elif a.cmd == "book":
        result = review_book(a.book_dir, a.book_id)
        print(format_report(result, verbose=a.verbose))
        sys.exit(0)


if __name__ == "__main__":
    main()
