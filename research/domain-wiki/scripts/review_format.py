"""review_format.py — 质量审查格式化输出

职责：将审查结果格式化为人类可读报告、Agent可消费JSON、修复指令清单。
零运行时依赖 quality_reviewer.py 引擎函数（只依赖 review_field_depth 的配置数据）。
"""

from __future__ import annotations

import json
import os
import re
from collections import defaultdict
from datetime import datetime
from typing import Any

from review_field_depth import FIELD_DEPTH, TYPE_YAML_MAP


# ════════════════════════════════════════════════════════════
# Report 格式化输出（人类可读）
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
# Agent可消费JSON输出
# ════════════════════════════════════════════════════════════

def build_json_output(result: dict, threshold: float = 0.8) -> dict[str, Any]:
    """构建Agent可消费的JSON输出（章节或全书级别）"""
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


# ════════════════════════════════════════════════════════════
# 修复清单生成
# ════════════════════════════════════════════════════════════

def build_fix_manifest(result: dict, threshold: float = 0.8) -> list[dict]:
    """为章节报告生成修复清单 — 文件级别的精确修复指令"""
    manifest = []
    chapter = result.get("chapter", "?")
    book_dir = result.get("data_dir", "").replace(
        f"/.dag/第{chapter}章/data", "").replace(
        f"\\.dag\\第{chapter}章\\data", "")
    if not book_dir:
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
# 修复指令输出（Agent直接消费）
# ════════════════════════════════════════════════════════════

def print_fix_instructions(result: dict, threshold: float = 0.8):
    """输出Agent可执行的修复指令

    格式:
      FIX_FILE: <path>
      FIX_TYPE: <type>
      FIX_FIELDS: <field1>,<field2>
      FIX_SOURCE: <source_path>
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
