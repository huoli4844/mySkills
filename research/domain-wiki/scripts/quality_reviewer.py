#!/usr/bin/env python3
"""quality_reviewer.py — 质量审查引擎（v2.1 模块化）

职责：CLI入口 + 三阶检查引擎(T1/T2/T3) + 内联检查。
配置数据 → review_field_depth.py
格式化输出 → review_format.py

用法:
  # 内联检查单项YAML（写一个过一件）
  python3 quality_reviewer.py check-item --type concept --threshold 0.9 \\
    --item '{"name":"...","fm":{...},"bd":{...}}'

  # 审查单章
  python3 quality_reviewer.py chapter --book-dir /path --book-id 01_ID -c 3

  # 生成修复清单
  python3 quality_reviewer.py fix-manifest --book-dir /path --book-id 01_ID -c 3
"""

from __future__ import annotations

import argparse
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

TEMPLATES_DIR = os.path.join(SKILL_DIR, "assets", "templates")

# ── 导入配置数据层 ──
from review_field_depth import (  # noqa: E402
    FM_REQUIRED, FM_OPTIONAL, FIELD_DEPTH, TYPE_YAML_MAP,
)

# ── 导入格式化输出层 ──
from review_format import (  # noqa: E402
    format_report, build_json_output, build_fix_manifest,
    print_fix_instructions, build_manifest_text,
)


# ════════════════════════════════════════════════════════════
# 工具函数
# ════════════════════════════════════════════════════════════

def load_yaml_list(path: str) -> list[dict]:
    if not os.path.isfile(path):
        return []
    try:
        import yaml
    except ImportError:
        return []
    try:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return data if isinstance(data, list) else []
    except (yaml.YAMLError, OSError):
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
    issues = []
    tpl_path = os.path.join(TEMPLATES_DIR, TYPE_YAML_MAP[ptype]["tpl"])
    tpl_content = read_file_content(tpl_path)
    tpl_fields = set(re.findall(r"\{\{(\w+)\}\}", tpl_content))

    for item in yaml_data:
        name = item.get("name", item.get("file", "?"))
        fm = item.get("fm", {})
        bd = item.get("bd", {})
        file_path = os.path.join(rendered_dir, f"{item.get('file', name)}.md")

        if not item.get("name", ""):
            issues.append({"file": name, "tier": "T1", "severity": "error",
                           "category": "yaml_no_name",
                           "message": "YAML缺少顶层 name 字段", "type": ptype})
            continue

        for f in FM_REQUIRED:
            if f not in fm or not str(fm.get(f, "")).strip():
                issues.append({"file": name, "tier": "T1", "severity": "error",
                               "category": "fm_missing",
                               "message": f"FM缺字段'{f}'", "type": ptype})

        if os.path.isfile(file_path):
            rendered = read_file_content(file_path)
            for pat, cat in [(r"\{\{[a-z_]+\|\|?[^}]*\}\}", "placeholder_residue"),
                             (r"<!--\s*@prompt", "prompt_leak")]:
                matches = re.findall(pat, rendered)
                if matches:
                    issues.append({"file": name, "tier": "T1", "severity": "error",
                                   "category": cat,
                                   "message": f"{cat}:{','.join(matches[:3])}",
                                   "type": ptype})

            if ptype in ("concept", "ke", "kp") and "```mermaid" in rendered:
                for mb in re.findall(r"```mermaid\n(.*?)```", rendered, re.DOTALL):
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
            extra = set(bd.keys()) - tpl_fields - fm.keys() - {"name"}
            if extra:
                issues.append({"file": name, "tier": "T1", "severity": "info",
                               "category": "bd_extra_fields",
                               "message": f"bd多出{len(extra)}个未使用字段:{','.join(list(extra)[:3])}",
                               "type": ptype})
    return issues


# ════════════════════════════════════════════════════════════
# T2: 内容深度检查
# ════════════════════════════════════════════════════════════

def check_depth(yaml_data: list[dict], ptype: str) -> list[dict]:
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
                    issues.append({"file": name, "tier": "T2", "severity": "error",
                                   "category": "field_empty",
                                   "message": f"字段'{field}'为空或占位符",
                                   "type": ptype})
                continue
            min_len = depth_cfg.get(field, 0)
            if min_len > 0 and len(stripped) < min_len:
                issues.append({"file": name, "tier": "T2", "severity": "warning",
                               "category": "field_too_short",
                               "message": f"字段'{field}'仅{len(stripped)}字(<{min_len})",
                               "type": ptype})

        # 类型特殊检查
        if ptype == "concept":
            ccm = bd.get("core_concept_map", "").strip()
            if ccm and not ccm.startswith("graph") and len(ccm) < 30:
                issues.append({"file": name, "tier": "T2", "severity": "warning",
                               "category": "mermaid_missing",
                               "message": "core_concept_map非图结构", "type": ptype})
        if ptype in ("kp", "sp") and not fm.get("bloom_level", "").strip():
            issues.append({"file": name, "tier": "T2", "severity": "warning",
                           "category": "bloom_missing",
                           "message": "bloom_level未填写", "type": ptype})
        if ptype == "ke" and not bd.get("term_english", "").strip():
            issues.append({"file": name, "tier": "T2", "severity": "info",
                           "category": "term_english_missing",
                           "message": "term_english未填写", "type": ptype})
        if ptype == "solution":
            principle = bd.get("principle_steps", "").strip()
            if len(principle) < 100:
                issues.append({"file": name, "tier": "T2", "severity": "warning",
                               "category": "solution_shallow",
                               "message": f"principle_steps仅{len(principle)}字(<100)",
                               "type": ptype})
    return issues


# ════════════════════════════════════════════════════════════
# T3: 交叉验证检查
# ════════════════════════════════════════════════════════════

def check_cross_references(yaml_by_type: dict[str, list]) -> list[dict]:
    issues = []
    name_to_file = {}
    for ptype, ydata in yaml_by_type.items():
        for item in ydata:
            n = item.get("name", "")
            name_to_file[n] = {"file": item.get("file", n), "type": ptype}
    for ptype, ydata in yaml_by_type.items():
        for item in ydata:
            text = str(item.get("bd", {}))
            for link in re.findall(r"\[\[([^\]|]+)", text):
                clean = link.split("#")[0].strip()
                while clean.startswith("../"):
                    clean = clean[3:]
                if "/" in clean:
                    clean = clean.split("/")[-1]
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
    n_files = max(len(set(i.get("file", "") for i in issues)), 1)

    errs_per_file = len(errors) / n_files
    warns_per_file = len(warnings) / n_files
    penalty = min(errs_per_file * 0.25, 0.7) + min(warns_per_file * 0.06, 0.25)
    score = max(0.0, min(1.0, 1.0 - penalty))

    return {"score": round(score, 2), "error": len(errors),
            "warning": len(warnings), "info": len(infos), "total": len(issues)}


# ════════════════════════════════════════════════════════════
# 按类型审查
# ════════════════════════════════════════════════════════════

def review_type(yaml_path: str, rendered_dir: str, ptype: str) -> dict:
    yaml_data = load_yaml_list(yaml_path)
    if not yaml_data:
        if os.path.isfile(yaml_path) and os.path.getsize(yaml_path) > 10:
            yaml_data = []
        else:
            return {"type": ptype, "score": 0.0, "error": 1, "warning": 0,
                    "info": 0, "total": 1, "items": 0,
                    "detail": [{"file": "N/A", "tier": "T1", "severity": "error",
                               "category": "yaml_missing",
                               "message": "YAML文件不存在或为空"}],
                    "file_scores": {}}

    all_issues = check_structure(yaml_data, rendered_dir, ptype) + \
                 check_depth(yaml_data, ptype)

    scored = score_issues(all_issues)
    scored["type"] = ptype
    scored["items"] = len(yaml_data)
    scored["detail"] = all_issues[:50]

    # 按文件评分
    file_scores: dict[str, dict] = {}
    for item in yaml_data:
        name = item.get("name", "?")
        fi = [i for i in all_issues if i.get("file") == name]
        fs = score_issues(fi)
        file_scores[name] = {
            "score": fs["score"], "error": fs["error"],
            "warning": fs["warning"], "info": fs["info"],
            "issues": fi[:10], "yaml_path": yaml_path,
            "rendered_path": os.path.join(rendered_dir, f"{item.get('file', name)}.md"),
            "type": ptype,
        }
    scored["file_scores"] = file_scores
    return scored


# ════════════════════════════════════════════════════════════
# 按章节 / 全书审查
# ════════════════════════════════════════════════════════════

def review_chapter(book_dir: str, book_id: str, chapter: str) -> dict:
    data_dir = os.path.join(book_dir, ".dag", f"第{chapter}章", "data")
    if not os.path.isdir(data_dir):
        return {"chapter": chapter, "score": 0.0, "error": 1,
                "message": f"数据目录不存在: {data_dir}"}

    type_scores: dict[str, dict] = {}
    all_issues: list[dict] = []

    for ptype, info in TYPE_YAML_MAP.items():
        result = review_type(os.path.join(data_dir, info["yaml"]),
                             os.path.join(book_dir, info["dir"]), ptype)
        type_scores[ptype] = result
        all_issues.extend(result.get("detail", []))

    yaml_by_type = {pt: load_yaml_list(os.path.join(data_dir, TYPE_YAML_MAP[pt]["yaml"]))
                    for pt in TYPE_YAML_MAP}
    all_issues.extend(check_cross_references(yaml_by_type))

    scorable = [v for v in type_scores.values() if v["items"] > 0]
    avg_score = round(sum(v["score"] for v in scorable) / len(scorable), 2) if scorable else 0.0

    return {
        "chapter": chapter, "book_id": book_id, "score": avg_score,
        "type_scores": type_scores, "summary": score_issues(all_issues),
        "items": sum(v.get("items", 0) for v in type_scores.values()),
        "types_present": [t for t, v in type_scores.items() if v["items"] > 0],
        "all_issues": all_issues[:100], "data_dir": data_dir,
    }


def review_book(book_dir: str, book_id: str) -> dict:
    from pathlib import Path
    dag_dir = os.path.join(book_dir, ".dag")
    chapters = set()
    for f in Path(dag_dir).glob(f"{book_id}_ch*.json"):
        ch = f.stem.replace(f"{book_id}_ch", "")
        if ch and ch.isdigit():
            chapters.add(ch)
    for d in sorted(os.listdir(dag_dir)):
        if d.startswith("第") and d.endswith("章"):
            ch = d[1:-1]
            if ch.isdigit():
                chapters.add(ch)

    sorted_chapters = sorted(chapters, key=int)
    if not sorted_chapters:
        return {"score": 0.0, "error": 1, "message": f"未找到章节数据在 {dag_dir}"}

    chapter_reviews = []
    type_aggregate: dict[str, list[float]] = defaultdict(list)
    total_issues = []

    for ch in sorted_chapters:
        result = review_chapter(book_dir, book_id, ch)
        chapter_reviews.append(result)
        total_issues.extend(result.get("all_issues", []))
        for ptype, ts in result.get("type_scores", {}).items():
            if ts.get("items", 0) > 0:
                type_aggregate[ptype].append(ts.get("score", 0.0))

    ch_scores = [r["score"] for r in chapter_reviews if r["score"] > 0]
    avg = round(sum(ch_scores) / len(ch_scores), 2) if ch_scores else 0.0
    type_averages = {t: round(sum(scores) / len(scores), 2)
                     for t, scores in type_aggregate.items()}

    return {
        "book_dir": book_dir, "book_id": book_id,
        "chapters": len(sorted_chapters), "chapters_reviewed": len(chapter_reviews),
        "score": avg, "chapter_scores": {r["chapter"]: r["score"] for r in chapter_reviews},
        "type_scores": type_averages,
        "total_items": sum(r.get("items", 0) for r in chapter_reviews),
        "total_issues_count": len(total_issues),
        "chapter_details": [
            {"chapter": r["chapter"], "score": r["score"], "items": r.get("items", 0),
             "types": r.get("types_present", []),
             "summary": r.get("summary", {}) if isinstance(r.get("summary"), dict) else {},
             "type_scores": {t: {"score": ts["score"], "items": ts["items"]}
                            for t, ts in r.get("type_scores", {}).items() if ts.get("items", 0) > 0},
            } for r in chapter_reviews
        ],
    }


# ════════════════════════════════════════════════════════════
# 内联检查单项YAML
# ════════════════════════════════════════════════════════════

def check_single_yaml_item(item: dict, ptype: str, threshold: float = 0.8) -> dict:
    """内联检查单个YAML项的质量（不依赖渲染文件）"""
    issues = []
    name = item.get("name", "?")
    fm = item.get("fm", {})
    bd = item.get("bd", {})
    depth_cfg = FIELD_DEPTH.get(ptype, {})

    if not item.get("name", ""):
        issues.append({"field": "name", "severity": "error",
                       "category": "yaml_no_name",
                       "message": "YAML缺少顶层 name 字段"})

    for f in FM_REQUIRED:
        if f not in fm or not str(fm.get(f, "")).strip():
            issues.append({"field": f"fm.{f}", "severity": "error",
                           "category": "fm_missing",
                           "message": f"FM缺字段'{f}'"})

    for field, content in bd.items():
        if not isinstance(content, str):
            continue
        stripped = content.strip()
        if not stripped or stripped in ("无", "（无）", "暂无", "待补充"):
            if field in depth_cfg:
                issues.append({"field": field, "severity": "error",
                               "category": "field_empty",
                               "message": f"字段'{field}'为空或占位符",
                               "current_len": 0, "target_len": depth_cfg[field],
                               "action": "fill"})
            continue
        min_len = depth_cfg.get(field, 0)
        if min_len > 0 and len(stripped) < min_len:
            issues.append({"field": field, "severity": "warning",
                           "category": "field_too_short",
                           "message": f"字段'{field}'仅{len(stripped)}字(<{min_len})",
                           "current_len": len(stripped), "target_len": min_len,
                           "action": "enrich"})

    if ptype in ("kp", "sp") and not fm.get("bloom_level", "").strip():
        issues.append({"field": "fm.bloom_level", "severity": "warning",
                       "category": "bloom_missing", "message": "bloom_level未填写",
                       "action": "fill"})

    if ptype == "ke" and not bd.get("term_english", "").strip():
        issues.append({"field": "term_english", "severity": "info",
                       "category": "term_english_missing",
                       "message": "term_english未填写", "action": "fill"})

    if ptype == "solution":
        principle = bd.get("principle_steps", "").strip()
        if len(principle) < 100:
            issues.append({"field": "principle_steps", "severity": "warning",
                           "category": "solution_shallow",
                           "message": f"principle_steps仅{len(principle)}字(<100)",
                           "current_len": len(principle), "target_len": 100,
                           "action": "enrich"})

    errors = [i for i in issues if i["severity"] == "error"]
    warnings = [i for i in issues if i["severity"] == "warning"]
    err_penalty = min(len(errors) * 0.25, 0.7)
    warn_penalty = min(len(warnings) * 0.06, 0.25)
    score = max(0.0, min(1.0, 1.0 - err_penalty - warn_penalty))

    return {
        "file": name, "type": ptype, "score": round(score, 2),
        "pass": score >= threshold, "issues": issues,
        "summary": {"error": len(errors), "warning": len(warnings),
                    "info": len([i for i in issues if i["severity"] == "info"]),
                    "total": len(issues)},
    }


# ════════════════════════════════════════════════════════════
# Pipeline 集成 — 审查并阻断
# ════════════════════════════════════════════════════════════

def check_and_block(book_dir: str, book_id: str, chapter: str,
                    threshold: float = 0.5,
                    set_state_failed: bool = False) -> tuple[bool, dict]:
    result = review_chapter(book_dir, book_id, chapter)
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
    return score >= threshold, result


# ════════════════════════════════════════════════════════════
# Main
# ════════════════════════════════════════════════════════════

def main():
    p = argparse.ArgumentParser(description="质量审查引擎 v2.1 (模块化)")
    sp = p.add_subparsers(dest="cmd", required=True)

    ch = sp.add_parser("chapter", help="审查单章")
    ch.add_argument("--book-dir", required=True)
    ch.add_argument("--book-id", required=True)
    ch.add_argument("-c", "--chapter", required=True)
    ch.add_argument("--threshold", type=float, default=0.5)
    ch.add_argument("--fix-threshold", type=float, default=0.8)
    ch.add_argument("--state-dir")
    ch.add_argument("-v", "--verbose", action="store_true")
    ch.add_argument("--json", action="store_true")

    bk = sp.add_parser("book", help="审查全书")
    bk.add_argument("--book-dir", required=True)
    bk.add_argument("--book-id", required=True)
    bk.add_argument("-v", "--verbose", action="store_true")
    bk.add_argument("--json", action="store_true")

    fm = sp.add_parser("fix-manifest", help="生成修复指令清单")
    fm.add_argument("--book-dir", required=True)
    fm.add_argument("--book-id", required=True)
    fm.add_argument("-c", "--chapter", required=True)
    fm.add_argument("--threshold", type=float, default=0.8)
    fm.add_argument("--output")
    fm.add_argument("--json", action="store_true")

    ci = sp.add_parser("check-item", help="内联检查单项YAML")
    ci.add_argument("--item", required=True)
    ci.add_argument("--type", required=True)
    ci.add_argument("--threshold", type=float, default=0.8)

    a = p.parse_args()

    if a.cmd == "chapter":
        result = review_chapter(a.book_dir, a.book_id, a.chapter)
        score = result.get("score", 0.0)
        if a.json:
            fix_thr = getattr(a, 'fix_threshold', 0.8)
            print(json.dumps(build_json_output(result, fix_thr),
                             ensure_ascii=False, indent=2))
        else:
            print(format_report(result, verbose=a.verbose))
        if score < a.threshold:
            print(f"\n❌ 质量不达标: {score:.0%} < {a.threshold:.0%}", file=sys.stderr)
            sys.exit(1)
        print(f"\n✅ 质量达标: {score:.0%} ≥ {a.threshold:.0%}", file=sys.stderr)
        sys.exit(0)

    elif a.cmd == "book":
        result = review_book(a.book_dir, a.book_id)
        if a.json:
            print(json.dumps(build_json_output(result),
                             ensure_ascii=False, indent=2))
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
        result = check_single_yaml_item(item, a.type, a.threshold)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(0 if result["pass"] else 1)


if __name__ == "__main__":
    main()
