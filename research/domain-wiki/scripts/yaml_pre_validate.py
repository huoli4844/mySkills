#!/usr/bin/env python3.12
"""yaml_pre_validate.py — Agent 写完 YAML 后秒级快速校验。

校验内容包括：
- Schema 结构校验
- Confidence/字段名/命名格式等业务规则
- v52.2+: 源文公式交叉校验（需 --book-dir -c 参数）

用法:
  python3.12 yaml_pre_validate.py .dag/第1章/data/concepts.yaml
  python3.12 yaml_pre_validate.py --chapter-dir .dag/第1章/data/   # 批量
  python3.12 yaml_pre_validate.py --book-dir /path/to/book -c 1    # 整章

退出码: 0=全部通过, 1=有错误, 2=有警告
"""

from __future__ import annotations


import argparse
import os
import re
import sys
import yaml
from typing import Any

from dag_constants import PipelineError

# ── 类型名映射: yaml_pre_validate 内部名 → dag_constants.REQUIRED_BD_FIELDS key ──
_TYPE_TO_BD_KEY = {
    "concept": "concept",
    "knowledge-element": "ke",
    "entity": "entity",
    "knowledge": "kp",
    "skill": "sp",
    "scenario": "scene",
    "exercise": "exercise",
    "solution": "solution",
}

# ── 类型常量 (与 dag_constants.py 保持一致) ──

_CONFIDENCE = {
    "concept": 0.95,
    "knowledge-element": 0.85,
    "entity": 0.85,
    "knowledge": 0.85,
    "skill": 0.75,
    "scenario": 0.65,
    "exercise": 0.65,
    "solution": 0.85,
}

_BLOOM_RANGES: dict[str, list[str]] = {
    "knowledge": ["知道→理解", "知道→应用", "理解→应用", "知道→分析", "应用→分析", "理解→分析", "应用→评价"],
    "skill": ["应用", "理解→应用", "应用→分析", "分析", "知道→应用"],
    "scenario": ["分析→评价", "分析→评价→创造", "评价→创造", "应用→分析→评价"],
}

# 定义句标记词
_DEFINITION_MARKERS = ["是指", "称为", "即", "指的是", "定义为", "就是", "所谓"]


def _detect_type(path: str) -> str | None:
    """从文件名/路径推断节点类型"""
    basename = os.path.basename(path)
    name = basename.rsplit(".", 2)[0] if basename.endswith((".yaml", ".yml")) else basename
    type_map = {
        "concepts": "concept",
        "kes": "knowledge-element",
        "entities": "entity",
        "kps": "knowledge",
        "sps": "skill",
        "scenes": "scenario",
        "exercises": "exercise",
        "solutions": "solution",
    }
    for key, val in type_map.items():
        if key in name.lower():
            return val
    return None


def _load_yaml(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if data is None:
        return []
    if not isinstance(data, list):
        return [data]
    return data


def check_schema(path: str) -> list[dict]:
    """复用 schema.py 的结构校验"""
    try:
        from schema import validate_yaml
        return validate_yaml(path)
    except ImportError:
        return [{"path": "", "message": "schema.py not importable", "severity": "error"}]


def check_confidence(items: list[dict], node_type: str) -> list[dict]:
    """检查 confidence 值是否符合类型规范"""
    errors = []
    expected = _CONFIDENCE.get(node_type)
    if expected is None:
        return errors
    for i, item in enumerate(items):
        fm = item.get("fm", {})
        conf = fm.get("confidence")
        if conf is None:
            errors.append({
                "item": i, "field": "fm.confidence",
                "message": f"缺少 confidence 字段（应为 {expected}）",
                "severity": "error",
            })
        elif conf != expected:
            errors.append({
                "item": i, "field": "fm.confidence",
                "message": f"confidence={conf}，应为 {expected}",
                "severity": "warning",
            })
    return errors


def check_required_fields(items: list[dict], node_type: str) -> list[dict]:
    """检查 bd 中关键字段不为空。

    v50.0: 从 dag_constants.REQUIRED_BD_FIELDS 读取权威必填字段列表。
    通过 _TYPE_TO_BD_KEY 将 yaml_pre_validate 类型名映射到 dag_constants key。
    """
    bd_key = _TYPE_TO_BD_KEY.get(node_type)
    if not bd_key:
        return []

    from dag_constants import REQUIRED_BD_FIELDS
    required = REQUIRED_BD_FIELDS.get(bd_key, [])
    if not required:
        return []

    errors = []
    for i, item in enumerate(items):
        bd = item.get("bd", {})
        for field in required:
            val = bd.get(field, "")
            if isinstance(val, (list, dict)):
                if len(val) == 0:
                    errors.append({
                        "item": i, "field": f"bd.{field}",
                        "message": f"必填字段 '{field}' 为空列表/字典",
                        "severity": "error",
                    })
            elif not val or str(val).strip() in ("", "none", "None", "N/A"):
                # 将 "无" 排除在占位符判断之外——"空节必须写无"是本规范的明确要求
                errors.append({
                    "item": i, "field": f"bd.{field}",
                    "message": f"必填字段 '{field}' 为空或占位符",
                    "severity": "error",
                })
    return errors


def check_bloom(items: list[dict], node_type: str) -> list[dict]:
    """检查 bloom_level 是否在允许范围内（容错匹配）"""
    allowed = _BLOOM_RANGES.get(node_type)
    if not allowed:
        return []
    errors = []
    for i, item in enumerate(items):
        bd = item.get("bd", {})
        val = bd.get("bloom_level", bd.get("bloom_level_description", ""))
        if not val or str(val).strip() in ("", "无"):
            continue
        # 容错：去掉英文括号注释后检查包含关系
        import re
        val_clean = re.sub(r'\([A-Za-z]+\)', '', str(val))
        matched = any(a in val_clean for a in allowed)
        if not matched:
            short = str(val)[:80]
            errors.append({
                "item": i, "field": "bd.bloom_level",
                "message": f"bloom_level='{short}...' 不在允许范围 {allowed}",
                "severity": "error",
            })
    return errors


def check_definition_sentence(items: list[dict], node_type: str) -> list[dict]:
    """检查定义句是否含标记词（概念和KE要求）"""
    if node_type not in ("concept", "knowledge-element"):
        return []
    errors = []
    for i, item in enumerate(items):
        bd = item.get("bd", {})
        ds = bd.get("definition_sentence", "")
        if not ds or ds.strip() in ("", "无"):
            continue
        has_marker = any(m in ds for m in _DEFINITION_MARKERS)
        if not has_marker:
            errors.append({
                "item": i, "field": "bd.definition_sentence",
                "message": f"定义句缺少标记词（{', '.join(_DEFINITION_MARKERS[:3])}等）: '{ds[:80]}...'",
                "severity": "warning",
            })
    return errors


def check_name_format(items: list[dict], node_type: str) -> list[dict]:
    """检查概念名是否为名词短语"""
    if node_type != "concept":
        return []
    errors = []
    verb_markers = ["的", "被", "将", "对", "把", "使", "产生"]
    for i, item in enumerate(items):
        name = item.get("name", "")
        if any(name.startswith(m) for m in verb_markers):
            errors.append({
                "item": i, "field": "name",
                "message": f"概念名 '{name}' 疑似动词短语开头，应为名词短语",
                "severity": "warning",
            })
    return errors


def check_mathematical_model(items: list[dict], node_type: str) -> list[dict]:
    """检查理论型概念是否遗漏数学模型"""
    if node_type != "concept":
        return []
    errors = []
    for i, item in enumerate(items):
        bd = item.get("bd", {})
        mm = bd.get("mathematical_model", "")
        mm_str = str(mm) if not isinstance(mm, (list, dict)) else ""
        classification = str(bd.get("classification", ""))
        # 理论型概念（名称含"理论/模型/原理/效应/方程"）必须有公式
        theory_keywords = ["理论", "模型", "原理", "效应", "方程", "定理", "定律"]
        is_theory = any(k in item.get("name", "") or k in classification for k in theory_keywords)
        if is_theory and (not mm_str or mm_str.strip() in ("", "无", "none", "None")):
            errors.append({
                "item": i, "field": "bd.mathematical_model",
                "message": f"理论型概念 '{item.get('name','')}' 缺少数学模型（应为 LaTeX 公式）",
                "severity": "warning",
            })
    return errors


# v52.2: 源文公式交叉校验
# 破解误区: Agent 写 YAML 时常直接填 mathematical_model="无"
# 而不去源文中检查是否存在 $$...$$ 公式。
# 此函数打开源文件扫描，发现公式但 YAML 缺失时报警。
def check_source_mathematical_model(items: list[dict], node_type: str, wr: str | None = None, ch: str = "") -> list[dict]:
    """从源文件中提取公式，检查概念 YAML 的 mathematical_model 是否遗漏。

    读 20_正文/第{ch}章*.md → 扫描 $$...$$ → 与 bd.mathematical_model 对比。
    仅当 wr+ch 都提供时执行。
    """
    if node_type not in ("concept", "knowledge-element", "knowledge"):
        return []
    if not wr or not ch:
        return []

    import glob
    src_dir = os.path.join(wr, "20_正文")
    src_files = sorted(glob.glob(os.path.join(src_dir, f"第{ch}章*.md")))
    if not src_files:
        return []
    src_path = src_files[0]

    with open(src_path, encoding="utf-8") as f:
        src_text = f.read()

    # 提取所有 $$...$$ 公式
    formulas = re.findall(r'\$\$(.*?)\$\$', src_text, re.DOTALL)
    # 提取行内公式
    inline_formulas = re.findall(r'(?<!\$)\$(?!\$)(.*?)(?<!\$)\$(?!\$)', src_text)
    total_formula_count = len(formulas) + len(inline_formulas)

    errors = []
    for i, item in enumerate(items):
        bd = item.get("bd", {})
        mm = bd.get("mathematical_model", "")
        mm_str = str(mm) if not isinstance(mm, (list, dict)) else ""
        fr = bd.get("formula_references", "")
        fr_str = str(fr) if not isinstance(fr, (list, dict)) else ""
        name = item.get("name", "")
        source_section = bd.get("source_from", "")

        # 判断源文对应节段是否有公式
        # 优先从 source_from 确定范围，无法确定时用全文件
        has_formula_in_source = False
        if source_section:
            # 尝试从 source_section 定位节段
            section_start = src_text.find(source_section)
            if section_start >= 0:
                section_end = min(section_start + 2000, len(src_text))
                section_text = src_text[section_start:section_end]
                if re.search(r'\$\$', section_text) or re.search(r'(?<!\$)\$(?!\$)[^$]+\$(?!\$)', section_text):
                    has_formula_in_source = True
            else:
                # 用概念名称定位
                name_start = src_text.find(name)
                if name_start >= 0:
                    section_end = min(name_start + 2000, len(src_text))
                    section_text = src_text[name_start:section_end]
                    if re.search(r'\$\$', section_text):
                        has_formula_in_source = True
        else:
            # 无 source_from: 全文件扫描
            has_formula_in_source = total_formula_count > 0

        # 源文有公式但 YAML 没有 → 报警
        if has_formula_in_source:
            mm_has_math = bool(re.search(r'\$\$', mm_str))
            fr_has_math = bool(re.search(r'\$\$', fr_str))

            if not mm_has_math and not fr_has_math and mm_str.strip() in ("", "无", "none", "None"):
                errors.append({
                    "item": i, "field": "bd.mathematical_model",
                    "message": f"'{name}' 的 source_from 节段含 $$ 公式，但 mathematical_model 和 formula_references 均为空。必须从源文提取公式。",
                    "severity": "warning",
                })
            elif not mm_has_math and mm_str.strip() in ("", "无", "none", "None"):
                errors.append({
                    "item": i, "field": "bd.mathematical_model",
                    "message": f"'{name}' 的源文有公式，但 mathematical_model 为 '{mm_str}'。应从源文提取 LaTeX 公式。",
                    "severity": "warning",
                })

    return errors


# v52.2: 检查 source_from 不应包含"第N章 "前缀（模板自动添加"第{{source_chapter}}章 "）
def check_source_from_format(items: list[dict], node_type: str) -> list[dict]:
    errors = []
    for i, item in enumerate(items):
        fm = item.get("fm", {})
        sf = fm.get("source_from", "")
        if re.match(r'^第\d+章\s', sf):
            errors.append({
                "item": i, "field": "fm.source_from",
                "message": f"source_from 含冗余'第N章 '前缀(值='{sf[:40]}')，模板会额外添加导致重复",
                "severity": "warning",
            })
    return errors


def check_template_field_names(items: list[dict], node_type: str) -> list[dict]:
    """v50.7: 检查 YAML bd 字段名是否与模板 {{xxx}} 占位符匹配。

    Agent 常见错误：记错字段名（如 skill_description 应为 skill_objectives）
    导致 {{placeholder}} 残留。此检查在 build 之前阻断此类错误。
    """
    if node_type == "unknown":
        return []

    # 类型 → 模板文件名映射
    _TEMPLATE_MAP = {
        "concept": "concept_template.md",
        "knowledge-element": "concept_template.md",
        "entity": "concept_template.md",
        "knowledge": "knowledge_template.md",
        "skill": "skill_template.md",
        "scenario": "scenario_template.md",
        "exercise": "exercise_template.md",
        "solution": "eval_template.md",
    }
    tmpl_name = _TEMPLATE_MAP.get(node_type)
    if not tmpl_name:
        return []

    # 模板路径：script_dir/../assets/templates/
    script_dir = os.path.dirname(os.path.abspath(__file__))
    tmpl_path = os.path.join(script_dir, "..", "assets", "templates", tmpl_name)
    if not os.path.exists(tmpl_path):
        return [{"item": 0, "field": "_template",
                  "message": f"模板文件不存在: {tmpl_path}", "severity": "warning"}]

    with open(tmpl_path, encoding="utf-8") as f:
        tmpl_content = f.read()

    # 提取模板中的 {{xxx}}
    import re
    template_fields = set(re.findall(r'\{\{([a-zA-Z_][a-zA-Z0-9_]*)\}\}', tmpl_content))

    errors = []
    for i, item in enumerate(items):
        bd = item.get("bd", {})
        yaml_fields = set(bd.keys())

        # 报告 YAML 中有但模板中不存在的字段（可能是 Agent 自创字段名）
        unrecognized = yaml_fields - template_fields
        # 排除 build 自动注入的标准字段
        _STD_BD = {"name", "id_field", "source_chapter", "source_page",
                   "source_from", "book_id", "book_name", "chapter_num",
                   "reviewer", "review_date"}
        unrecognized = unrecognized - _STD_BD

        if unrecognized:
            errors.append({
                "item": i, "field": "bd",
                "message": f"不识别字段名: {', '.join(sorted(unrecognized)[:6])}（不在模板 {{xxx}} 中）",
                "severity": "warning",
            })

        # 报告模板中有但 YAML 中缺失的字段（Agent 遗漏了）
        missing = template_fields - yaml_fields - _STD_BD
        # 只报告非 "无" 默认字段 — 检查 item.bd 中是否有该字段，有但值为空不报
        # 彻底缺失（bd 中根本没有这个 key）才报
        for field in sorted(missing):
            if field not in bd:
                errors.append({
                    "item": i, "field": f"bd.{field}",
                    "message": f"bd 中缺失字段 '{field}'（模板 {{xxx}} 需要）",
                    "severity": "warning",
                })

    return errors


def check_file_naming(items: list[dict], node_type: str) -> list[dict]:
    """v50.0: 检查 file 字段命名规范。习题/解答必须使用 第N章-习题N 格式。"""
    if node_type not in ("exercise", "solution"):
        return []
    import re
    errors = []
    _pattern = re.compile(r'^第\d+章-习题\d+(-解答)?$')
    for i, item in enumerate(items):
        fname = item.get("file", "")
        if not _pattern.match(fname):
            errors.append({
                "item": i, "field": "file",
                "message": f"文件名 '{fname}' 不符合规范，应为 第N章-习题N (或 第N章-习题N-解答)",
                "severity": "warning",
            })
    return errors


def validate_file(yaml_path: str, wr: str | None = None, ch: str = "") -> dict[str, Any]:
    """校验单个 YAML 文件，返回结构化结果"""
    node_type = _detect_type(yaml_path)
    if not node_type:
        return {"path": yaml_path, "type": "unknown", "errors": [{
            "item": 0, "field": "", "message": "无法识别节点类型",
            "severity": "error"
        }], "warnings": 0, "errors_count": 1, "pass": False}

    try:
        items = _load_yaml(yaml_path)
    except Exception as e:
        return {"path": yaml_path, "type": node_type, "errors": [{
            "item": 0, "field": "", "message": f"YAML 解析失败: {e}",
            "severity": "error"
        }], "warnings": 0, "errors_count": 1, "pass": False}

    if not items:
        return {"path": yaml_path, "type": node_type, "errors": [{
            "item": 0, "field": "", "message": "YAML 文件为空（无数据项）",
            "severity": "warning"
        }], "warnings": 1, "errors_count": 0, "pass": True}

    all_results = []

    # 1. Schema（降级为 warning：schema 可能与 YAML 版本不同步）
    schema_results = check_schema(yaml_path)
    for r in schema_results:
        r["severity"] = "warning"
    all_results.extend(schema_results)

    # 2. 业务规则
    all_results.extend(check_confidence(items, node_type))
    all_results.extend(check_required_fields(items, node_type))
    all_results.extend(check_bloom(items, node_type))
    all_results.extend(check_definition_sentence(items, node_type))
    all_results.extend(check_name_format(items, node_type))
    all_results.extend(check_mathematical_model(items, node_type))
    all_results.extend(check_file_naming(items, node_type))  # v50.0
    # v52.2: source_from 格式校验 — 不应含"第N章 "前缀（模板自动添加）
    all_results.extend(check_source_from_format(items, node_type))
    # v52.2: 源文公式交叉校验（需 wr+ch）
    if wr and ch:
        all_results.extend(check_source_mathematical_model(items, node_type, wr, ch))
    # v50.7: 模板字段名校验 — Agent 自创字段名 vs 模板 {{xxx}}
    all_results.extend(check_template_field_names(items, node_type))

    errors = [r for r in all_results if r.get("severity") == "error"]
    warnings = [r for r in all_results if r.get("severity") == "warning"]

    return {
        "path": yaml_path,
        "type": node_type,
        "items_count": len(items),
        "errors": all_results,
        "errors_count": len(errors),
        "warnings": len(warnings),
        "pass": len(errors) == 0,
    }


def validate_chapter_dir(chapter_data_dir: str, wr: str | None = None, ch: str = "") -> list[dict]:
    """校验整章 data 目录下所有 YAML"""
    results = []
    for fname in sorted(os.listdir(chapter_data_dir)):
        if fname.endswith((".yaml", ".yml")):
            results.append(validate_file(os.path.join(chapter_data_dir, fname), wr=wr, ch=ch))
    return results


def validate_book_chapter(book_dir: str, chapter: str) -> list[dict]:
    """校验书级某章（通过 WorkspacePaths）"""
    from dag_state import WorkspacePaths
    wp = WorkspacePaths(book_dir)
    data_dir = wp.data_dir(chapter)
    if not os.path.isdir(data_dir):
        return [{"path": data_dir, "type": "", "errors": [{
            "item": 0, "field": "", "message": f"数据目录不存在: {data_dir}",
            "severity": "error"}], "errors_count": 1, "warnings": 0, "pass": False}]
    return validate_chapter_dir(data_dir, wr=book_dir, ch=chapter)


def format_results(results: list[dict], verbose: bool = False) -> tuple[str, bool]:
    """格式化输出，返回 (output, all_pass)"""
    lines = []
    total_errors = 0
    total_warnings = 0
    total_items = 0

    for r in results:
        path = r["path"]
        fname = os.path.basename(path)
        ntype = r.get("type", "?")
        nitems = r.get("items_count", 0)
        total_items += nitems
        errs = r.get("errors_count", 0)
        warns = r.get("warnings", 0)
        total_errors += errs
        total_warnings += warns

        if r["pass"] and warns == 0:
            status = "✅"
        elif r["pass"]:
            status = "⚠️ "
        else:
            status = "❌"

        lines.append(f"{status} {fname} [{ntype}] {nitems}项 | {errs}错 {warns}警")

        if verbose or errs > 0 or warns > 0:
            for e in r.get("errors", []):
                marker = "  ❌" if e.get("severity") == "error" else "  ⚠️ "
                item_idx = e.get("item", "")
                field = e.get("field", "")
                loc = f"[{item_idx}].{field}" if field else f"[{item_idx}]"
                lines.append(f"{marker} {loc}: {e['message']}")

    lines.append("")
    lines.append(f"总计: {len(results)}文件, {total_items}项, {total_errors}错误, {total_warnings}警告")
    return "\n".join(lines), total_errors == 0


def main():
    parser = argparse.ArgumentParser(description="YAML 快速预校验 — Agent 写 YAML 后秒级检查")
    parser.add_argument("yaml_path", nargs="?", help="单个 YAML 文件路径")
    parser.add_argument("--chapter-dir", help="整章 data 目录 (批量)")
    parser.add_argument("--book-dir", help="书目录 (-c 指定章)")
    parser.add_argument("-c", "--chapter", help="章节号")
    parser.add_argument("-v", "--verbose", action="store_true", help="详细输出")
    args = parser.parse_args()

    if args.book_dir and args.chapter:
        results = validate_book_chapter(args.book_dir, args.chapter)
    elif args.chapter_dir:
        results = validate_chapter_dir(args.chapter_dir)
    elif args.yaml_path:
        results = [validate_file(args.yaml_path)]
    else:
        parser.print_help()
        raise PipelineError("请指定 YAML 文件或目录")

    output, all_pass = format_results(results, verbose=args.verbose)
    print(output)
    if not all_pass:
        raise PipelineError("YAML pre-validation FAILED")


if __name__ == "__main__":
    main()
