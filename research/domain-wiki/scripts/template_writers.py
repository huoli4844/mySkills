#!/usr/bin/env python3
"""
template_writers.py — 文件写入 + 索引渲染 + CLI 入口

v50.7: 从 template_assembler.py 独立（v45.1 TODO: 拆分为 3 文件）。
包含文件写入（原子写入）、索引渲染、CLI 入口，不包含字段填充逻辑。
"""

from __future__ import annotations


import json
import os
import re
import sys

from dag_constants import PipelineError
from log_utils import get_logger

# 核心函数从 template_assembler 导入（避免循环依赖—只导入纯函数）
from template_assembler import (
    ASSEMBLER_CONFIG,
    NODE_CONFIG,
    _fn,
    assemble_by_config,
    check_placeholders,
    fill_template,
    load_template,
    parse_template,
    safe_filename,
    validate_frontmatter,
)

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# 统一组装入口（含占位符+置信度+元数据校验 + 原子写入）
# ---------------------------------------------------------------------------


def assemble_md(
    template_name: str,
    front_matter_updates: dict,
    body_replacements: dict,
    output_dir: str,
    filename: str,
    *,
    strict: bool = True,
    quality_key: str | None = None,
) -> str:
    """严格按模板组装MD文件（含写前校验）

    参数：
        template_name: 模板文件名（如 'concept_template.md'）
        front_matter_updates: Front Matter字段更新（字典）
        body_replacements: Body占位符替换（字典）
        output_dir: 输出目录
        filename: 输出文件名（不含路径）
        strict: 是否严格模式（置信度或元数据不合规则拒绝写入，默认True）
        quality_key: 质量检查键

    返回：
        filepath: 生成的MD文件完整路径
    """
    from template_assembler import ALLOWED_TEMPLATES, _wrap_mermaid_fields

    qk = quality_key or template_name
    if qk not in ALLOWED_TEMPLATES:
        log.warning(f"  ⚠️  {filename}: 未知质量键 '{qk}'，跳过校验")

    template_content = load_template(template_name)
    parsed = parse_template(template_content)

    fm = parsed["front_matter"].copy()
    for key, value in front_matter_updates.items():
        fm[key] = value

    # --- Layer 1: 写前校验 ---
    validate_errors = validate_frontmatter(fm, qk, filename)
    if validate_errors:
        for err in validate_errors:
            log.error(f"  ❌ {filename}: {err}")
        if strict:
            raise ValueError(
                f"FrontMatter 校验失败（{len(validate_errors)} 项），文件未写入:\n"
                + "\n".join(f"  - {e}" for e in validate_errors)
            )

    # --- 组装 Front Matter ---
    fm_lines = []
    for key, value in fm.items():
        if value is None:
            continue
        if isinstance(value, list | tuple):
            value_str = json.dumps(value, ensure_ascii=False)
        elif isinstance(value, int | float):
            value_str = str(value)
        else:
            value_str = str(value)
        fm_lines.append(f"{key}: {value_str}")

    front_matter_text = "---\n" + "\n".join(fm_lines) + "\n---\n"

    body = fill_template(parsed["body_template"], body_replacements)

    full_md = front_matter_text + body + "\n"

    check_placeholders(full_md, filename)
    full_md = _wrap_mermaid_fields(full_md)

    os.makedirs(output_dir, exist_ok=True)
    filepath = os.path.join(output_dir, filename)

    # 原子写入 — tempfile + os.replace
    import tempfile as _tmp

    fd, tmpname = _tmp.mkstemp(dir=output_dir, prefix="." + filename, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(full_md)
        os.replace(tmpname, filepath)
    except OSError:
        if os.path.exists(tmpname):
            os.unlink(tmpname)
        raise

    return filepath


# ---------------------------------------------------------------------------
# 兼容性包装函数
# ---------------------------------------------------------------------------


def assemble_concept_md(**kwargs):
    """向后兼容：概念组装。新代码请用 assemble_by_config(NODE_CONFIG['concept'], **kwargs)"""
    return assemble_by_config(NODE_CONFIG["concept"], **kwargs)


def assemble_book_overview_md(**kwargs):
    """生成 L2 book_overview MD。"""
    return assemble_by_config(ASSEMBLER_CONFIG["book_overview"], **kwargs)


def _assemble_index(data, output_dir, type_key, args=None):
    """v43.14: 索引/总揽专用渲染路径。

    与 per-item 组装不同，索引文件是「N 个 items → 1 个文件」，
    将所有 items 的 wikilink 渲染为单个 Markdown 表格。
    """
    import datetime

    items = data.get("items", [])
    index_type = data.get("index_type", type_key)
    book_id = data.get("book_id", "")
    book_name = data.get("book_name", "")
    filename = data.get("filename", f"{index_type}_{book_id}_0.md")

    type_labels = {
        "book_overview": ("book_overview", "资料总揽"),
        "concept_index": ("concept_index", "核心概念索引"),
        "knowledge_index": ("knowledge_index", "知识点索引"),
        "skill_index": ("skill_index", "技能点索引"),
        "scenario_index": ("scenario_index", "应用场景索引"),
        "domain_overview": ("domain_overview", "领域总揽"),
        "kb_overview": ("kb_overview", "知识库总揽"),
    }
    label = type_labels.get(index_type, (index_type, index_type))
    fm_type, display_name = label[0], label[1]

    lines = []
    lines.append("---")
    lines.append("template_version: v3.0")
    lines.append(f"type: {fm_type}")
    lines.append('type_tags: ["索引"]')
    lines.append(f"name: {display_name}")
    lines.append(f"book_id: {book_id}")
    lines.append(f"book_name: {book_name}")
    lines.append("chapter_num: 0")
    lines.append("reviewer: 系统自动")
    lines.append(f"review_date: {datetime.date.today().isoformat()}")
    lines.append(f"total_count: {len(items)}")
    lines.append("---")
    lines.append("")
    lines.append(f"# {display_name}")
    lines.append("")
    lines.append("| # | 名称 | 链接 |")
    lines.append("|:--|:-----|:-----|")

    for i, item in enumerate(items, 1):
        name = item.get("name", "?")
        wikilink = item.get("wikilink", f"[[{name}]]")
        lines.append(f"| {i} | {name} | {wikilink} |")

    lines.append("")
    lines.append(f"总计: **{len(items)}** 项")

    os.makedirs(output_dir, exist_ok=True)
    out_path = os.path.join(output_dir, filename)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    log.success(f"  ✅ {filename} ({len(items)} 项, {os.path.getsize(out_path)} bytes)")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main():
    if len(sys.argv) < 2 or not os.path.exists(sys.argv[1]):
        log.info("用法: python3 template_writers.py <data.json>")
        raise PipelineError("用法: python3 template_writers.py <data.json>")

    with open(sys.argv[1], encoding="utf-8") as f:
        data = json.load(f)

    item_type = data.get("template", "concept_template.md").replace(".md", "")
    type_map = {
        "book_overview": "book_overview",
        "concept_index": "index",
        "knowledge_index": "index",
        "skill_index": "index",
        "scenario_index": "index",
        "domain_overview": "book_overview",
        "kb_overview": "book_overview",
        "concept": "concept",
        "concept_template": "concept",
        "knowledge-element": "knowledge-element",
        "knowledge": "knowledge",
        "knowledge_template": "knowledge",
        "skill": "skill",
        "skill_template": "skill",
        "scenario": "scenario",
        "scenario_template": "scenario",
        "entity": "entity",
        "exercise": "exercise",
        "eval_template": "exercise",
        "solution": "solution",
    }
    quality_key = data.get("quality_key", "")
    if quality_key == "eval/solution":
        type_key = "solution"
    elif quality_key == "eval/exercise":
        type_key = "exercise"
    elif quality_key == "concept/ke":
        type_key = "knowledge-element"
    elif quality_key == "concept/entity":
        type_key = "entity"
    else:
        type_key = type_map.get(item_type, "concept")
    cfg = ASSEMBLER_CONFIG.get(type_key)
    if not cfg:
        log.info(f"未知类型: {item_type}")
        raise PipelineError(f"未知类型: {item_type}")

    if type_key in ("index", "book_overview"):
        idx_output_dir = data.get("output_dir", ".")
        _assemble_index(data, idx_output_dir, type_key)
        return

    output_dir = data.get("output_dir", None)
    if not output_dir or output_dir == ".":
        from dag_constants import DIR

        type_to_dir = {
            "concept": os.path.join(DIR["LIBRARY"], DIR["CONCEPTS"]),
            "knowledge-element": os.path.join(DIR["LIBRARY"], DIR["KE"]),
            "knowledge": os.path.join(DIR["LIBRARY"], DIR["KP"]),
            "skill": os.path.join(DIR["LIBRARY"], DIR["SP"]),
            "scenario": os.path.join(DIR["LIBRARY"], DIR["SCENE"]),
            "entity": os.path.join(DIR["LIBRARY"], DIR["ENTITIES"]),
            "exercise": os.path.join(DIR["LIBRARY"], DIR["EXERCISES"]),
            "solution": os.path.join(DIR["LIBRARY"], DIR["SOLUTIONS"]),
        }
        output_dir = type_to_dir.get(type_key, ".")
        log.info(f"  ↳ output_dir 未指定，使用 DIR 注册表: {output_dir}")

    kwargs = {
        "book_id": data.get("book_id", ""),
        "book_name": data.get("book_name", ""),
        "chapter_num": data.get("chapter_num", ""),
        "output_dir": output_dir,
        "items": data.get("items", []),
    }
    assemble_by_config(cfg, **kwargs)


if __name__ == "__main__":
    try:
        main()
    except PipelineError as e:
        log.error(str(e))
        raise
