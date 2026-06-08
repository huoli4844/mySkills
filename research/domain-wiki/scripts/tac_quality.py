"""tac_quality.py — 模板质量检查引擎 (v42.0 从 template_assembler.py 拆分)

包含:
  - _CHECK_HANDLERS: 策略模式检查注册表
  - 全部 @_register_check 处理函数
  - run_type_quality_checks(): 类型级质量检查运行器
  - validate_frontmatter(): Front Matter 校验
  - comprehensive_content_check(): 统一质量检查编排入口
"""

import os
import re
import sys
from collections.abc import Callable
from typing import Any

from log_utils import get_logger

log = get_logger(__name__)

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

from tac_constants import (  # noqa: E402
    CONFIDENCE_LEVELS,
    DEFINITION_MARKERS,
    REQUIRED_FRONTMATTER,
    TYPE_QUALITY_CHECKS,
)

# ── Check Handler Registry ─────────────────────────────────
# 策略模式：每个 check_id 的处理逻辑注册为独立函数，
# 新增检查只需添加 @register_check 装饰器，无需修改主循环。

_CHECK_HANDLERS: dict[str, Callable] = {}


def _register_check(check_id: str):
    """装饰器：注册检查处理函数"""

    def decorator(fn):
        _CHECK_HANDLERS[check_id] = fn
        return fn

    return decorator


def _get_body(content: str) -> str:
    """提取 frontmatter 之后的正文"""
    return content.split("---", 2)[2] if content.count("---") >= 2 else content


# ── Simple frontmatter checks ──────────────────────────────


@_register_check("has_frontmatter")
def _check_has_frontmatter(content: str, fm: dict, has_fm: bool, filepath: str) -> Any:
    return "pass" if has_fm else "fail"


@_register_check("has_name")
def _check_has_name(content: str, fm: dict, has_fm: bool, filepath: str) -> Any:
    return "pass" if fm.get("name", "") else "fail"


@_register_check("has_type_concept")
def _check_type_concept(content: str, fm: dict, has_fm: bool, filepath: str) -> Any:
    return "pass" if fm.get("type") == "concept" else "fail"


@_register_check("has_type_ke")
def _check_type_ke(content: str, fm: dict, has_fm: bool, filepath: str) -> Any:
    return "pass" if fm.get("type") == "knowledge-element" else "fail"


@_register_check("has_type_knowledge")
def _check_type_knowledge(content: str, fm: dict, has_fm: bool, filepath: str) -> Any:
    return "pass" if fm.get("type") in ("knowledge", "knowledge-point") else "fail"


@_register_check("has_type_skill")
def _check_type_skill(content: str, fm: dict, has_fm: bool, filepath: str) -> Any:
    return "pass" if fm.get("type") == "skill" else "fail"


@_register_check("has_type_scenario")
def _check_type_scenario(content: str, fm: dict, has_fm: bool, filepath: str) -> Any:
    return "pass" if fm.get("type") == "scenario" else "fail"


@_register_check("has_type_entity")
def _check_type_entity(content: str, fm: dict, has_fm: bool, filepath: str) -> Any:
    return "pass" if fm.get("type") == "entity" else "fail"


@_register_check("has_type_exercise")
def _check_type_exercise(content: str, fm: dict, has_fm: bool, filepath: str) -> Any:
    return "pass" if fm.get("type") == "exercise" else "fail"


@_register_check("has_type_solution")
def _check_type_solution(content: str, fm: dict, has_fm: bool, filepath: str) -> Any:
    return "pass" if fm.get("type") == "solution" else "fail"


@_register_check("has_confidence_095")
def _check_conf_095(content: str, fm: dict, has_fm: bool, filepath: str) -> Any:
    return "pass" if str(fm.get("confidence", "")) == "0.95" else "fail"


@_register_check("has_confidence_085")
def _check_conf_085(content: str, fm: dict, has_fm: bool, filepath: str) -> Any:
    return "pass" if str(fm.get("confidence", "")) == "0.85" else "fail"


@_register_check("has_confidence_075")
def _check_conf_075(content: str, fm: dict, has_fm: bool, filepath: str) -> Any:
    return "pass" if str(fm.get("confidence", "")) == "0.75" else "fail"


@_register_check("has_confidence_065")
def _check_conf_065(content: str, fm: dict, has_fm: bool, filepath: str) -> Any:
    return "pass" if str(fm.get("confidence", "")) == "0.65" else "fail"


# ── Body content checks ────────────────────────────────────


@_register_check("has_definition")
def _check_has_definition(content: str, fm: dict, has_fm: bool, filepath: str) -> Any:
    body = _get_body(content)
    return "pass" if re.search(r"^>\s", body, re.MULTILINE) else "fail"


@_register_check("has_marker_word")
def _check_has_marker_word(content: str, fm: dict, has_fm: bool, filepath: str) -> Any:
    body = _get_body(content)
    defn_match = re.search(r"^>\s*([^\n]+)", body, re.MULTILINE)
    defn_text = defn_match.group(1).strip() if defn_match else ""
    has_marker = any(m in defn_text for m in DEFINITION_MARKERS)
    return "pass" if has_marker else "fail"


@_register_check("no_placeholder")
def _check_no_placeholder(content: str, fm: dict, has_fm: bool, filepath: str) -> Any:
    phs = re.findall(r"\{\{[^}]+\}\}", content)
    return "pass" if not phs else "fail"


@_register_check("has_mermaid_flow")
def _check_has_mermaid_flow(content: str, fm: dict, has_fm: bool, filepath: str) -> Any:
    return "pass" if "```mermaid" in content else "fail"


@_register_check("has_mermaid")
def _check_has_mermaid(content: str, fm: dict, has_fm: bool, filepath: str) -> Any:
    return "pass" if "```mermaid" in content else "fail"


@_register_check("has_analysis_text")
def _check_has_analysis_text(content: str, fm: dict, has_fm: bool, filepath: str) -> Any:
    return "pass" if any(kw in content for kw in ("解析", "分步说明", "操作流程")) else "fail"


@_register_check("has_question")
def _check_has_question(content: str, fm: dict, has_fm: bool, filepath: str) -> Any:
    return "pass" if "题目" in content else "fail"


@_register_check("has_answer")
def _check_has_answer(content: str, fm: dict, has_fm: bool, filepath: str) -> Any:
    return "pass" if ("参考答案" in content or "解答" in content) else "fail"


@_register_check("has_content")
def _check_has_content(content: str, fm: dict, has_fm: bool, filepath: str) -> Any:
    body = _get_body(content)
    return "pass" if len(body.strip()) > 50 else "fail"


@_register_check("has_boundary")
def _check_has_boundary(content: str, fm: dict, has_fm: bool, filepath: str) -> Any:
    return "pass" if ("边界" in content or "条件" in content) else "fail"


# ── Citation checks ─────────────────────────────────────────


@_register_check("has_source_citation")
def _check_has_source_citation(content: str, fm: dict, has_fm: bool, filepath: str) -> Any:
    body = _get_body(content)
    source_marker = "来源：" in body or "来源:" in body
    if not source_marker:
        log.info("    📝 缺少来源标注：定义下方需有 > 来源：第X章 §X.X")
    return "pass" if source_marker else "fail"


@_register_check("has_formula_citation")
def _check_has_formula_citation(content: str, fm: dict, has_fm: bool, filepath: str) -> Any:
    from formula_utils import find_formula_blocks, has_citation_after

    body = _get_body(content)
    lines = body.split("\n")
    blocks = find_formula_blocks(lines)
    if not blocks:
        return "pass"  # 无公式，自动通过
    all_cited = all(has_citation_after(lines, blk.end_line) for blk in blocks)
    if not all_cited:
        log.info("    📝 公式缺少来源标注：每个 $$ 公式块下方必须有 > 来源：...")
    return "pass" if all_cited else "fail"


@_register_check("has_figure_citation")
def _check_has_figure_citation(content: str, fm: dict, has_fm: bool, filepath: str) -> Any:
    body = _get_body(content)
    img_refs = re.findall(r"!\[.*?\]\(.*?\)", body)
    if not img_refs:
        return "pass"
    lines = body.split("\n")
    for i, line in enumerate(lines):
        if re.search(r"!\[(.*?)\]\((.*?)\)", line):
            cited = any("来源：" in lines[j] or "来源:" in lines[j] for j in range(i + 1, min(i + 10, len(lines))))
            if not cited:
                log.info("    📝 图片缺少来源标注：每个 ![]() 下方必须有 > 来源：...")
                return "fail"
    return "pass"


@_register_check("additional_explanations")
def _check_additional_explanations(content: str, fm: dict, has_fm: bool, filepath: str) -> Any:
    body = _get_body(content)
    count = len(re.findall(r"^>", body, re.MULTILINE))
    if count < 3:
        log.info(f"    📝 仅有 {count} 个 > 引用块，建议从正文提取更多解释性段落")
    return "pass" if count >= 3 else "fail"


# ── Source retrieval check ──────────────────────────────────


@_register_check("has_source_retrieval")
def _check_has_source_retrieval(content: str, fm: dict, has_fm: bool, filepath: str) -> Any:
    """检查定义文本是否可在正文中找到来源。返回 (result, stop_loop) 元组。"""
    src_ch = fm.get("source_chapter", "")
    body = _get_body(content)
    defn_match = re.search(r"^>\s*([^\n]+)", body, re.MULTILINE)
    defn_text = defn_match.group(1).strip() if defn_match else ""
    if not defn_text:
        return "fail", True

    # 向上查找 20_正文/ 目录
    fdir = os.path.dirname(filepath)
    src_dir = None
    p = fdir
    for _ in range(5):
        candidate = os.path.join(p, "20_正文")
        if os.path.isdir(candidate):
            src_dir = candidate
            break
        p = os.path.dirname(p)
    if src_dir is None:
        parent = os.path.dirname(fdir)
        if os.path.isdir(os.path.join(parent, "20_正文")):
            src_dir = os.path.join(parent, "20_正文")
    if src_dir is None:
        return "skip", True

    # 查找匹配的正文文件
    src_files = []
    for f in sorted(os.listdir(src_dir)):
        if not f.endswith(".md"):
            continue
        if src_ch and src_ch.replace("第", "").replace("章", "").strip() in f:
            src_files.append(os.path.join(src_dir, f))
    if not src_files:
        src_files = [os.path.join(src_dir, f) for f in sorted(os.listdir(src_dir)) if f.endswith(".md")]

    def _norm_match(text):
        """剥离图片/链接/LaTeX符号，保留纯中文+英文+数字"""
        t = re.sub(r"!\[.*?\]\(.*?\)", "", text)
        t = re.sub(r"\[.*?\]\(.*?\)", "", t)
        t = re.sub(r"!\[.*?\]\[.*?\]", "", t)
        t = re.sub(r"[#*>`~]", "", t)
        t = re.sub(
            r"[\uff0c\u3002\u3001\uff1b\uff1a\u201c\u201d\u2018\u2019\uff01\uff08\uff09\uff1a\uff1f\s\-\u2014\u2026]",
            "",
            t,
        )
        t = re.sub(r"[_^{}\\]", "", t)
        t = re.sub(r"[=+\-*/<>]", "", t)
        return t

    defn_clean = _norm_match(defn_text[:150])
    defn_chinese = re.sub(r"[^\u4e00-\u9fff]", "", defn_text[:150])
    found = False
    for sf in src_files[:3]:
        try:
            with open(sf, encoding="utf-8") as fh:
                src_text = fh.read()
            src_clean = _norm_match(src_text)
            if defn_clean and defn_clean in src_clean:
                found = True
                break
            src_chinese_raw = re.sub(r"[^\u4e00-\u9fff]", "", re.sub(r"!\[.*?\]\(.*?\)", "", src_text))
            if len(defn_chinese) >= 10 and defn_chinese in src_chinese_raw:
                found = True
                break
            if len(defn_chinese) >= 6:
                frags = [defn_chinese[i : i + 2] for i in range(len(defn_chinese) - 1)]
                hit = sum(1 for fg in frags if fg in src_chinese_raw)
                if frags and hit / len(frags) >= 0.7:
                    found = True
                    break
        except OSError:
            continue

    if not found and defn_text:
        short = defn_text[:60].replace(chr(10), " ")
        log.info(f"    📝 定义 【{short}...】 在 {len(src_files)} 个正文文件中未找到")
    result = "pass" if found else "fail"
    # 原始行为：fail/skip 时 break 终止后续检查，pass 时继续
    return result, (result != "pass")


# ── Mermaid valid (no-op, handled elsewhere) ─────────────────


@_register_check("mermaid_valid")
def _check_mermaid_valid(content: str, fm: dict, has_fm: bool, filepath: str) -> Any:
    return "pass"  # 实际检查由 validate-mermaid-syntax.py 完成


def run_type_quality_checks(filepath: str, template_name: str) -> dict:
    """对单个 .md 文件运行类型级质量检查

    返回：
        {
            "passed": bool,
            "critical": [问题描述],
            "warnings": [问题描述],
            "checks": {check_id: "pass"/"fail"/"skip"}
        }
    """
    checks = TYPE_QUALITY_CHECKS.get(template_name, [])
    if not checks:
        return {"passed": True, "critical": [], "warnings": [], "checks": {}}

    with open(filepath, encoding="utf-8") as f:
        content = f.read()

    # 解析 frontmatter
    fm_match = re.search(r"^---\n(.*?)\n---", content, re.DOTALL)
    has_fm = bool(fm_match)
    fm = {}
    if has_fm:
        for line in fm_match.group(1).strip().split("\n"):
            if ":" in line:
                k, _, v = line.partition(":")
                fm[k.strip()] = v.strip()

    critical_issues = []
    warnings = []
    check_results = {}

    for severity, check_id, description in checks:
        handler = _CHECK_HANDLERS.get(check_id)
        if handler is None:
            result = "skip"
        else:
            handler_result = handler(content, fm, has_fm, filepath)
            # 支持 (result, stop_loop) 元组返回值
            if isinstance(handler_result, tuple):
                result, _stop_loop = handler_result
            else:
                result = handler_result
                _stop_loop = False

        check_results[check_id] = result
        if result == "fail":
            if severity == "critical":
                critical_issues.append(f"[{check_id}] {description}")
            else:
                warnings.append(f"[{check_id}] {description}")

        # has_source_retrieval 等检查失败时终止后续检查
        if handler and isinstance(handler_result, tuple) and handler_result[1]:
            break

    passed = len(critical_issues) == 0
    return {
        "passed": passed,
        "critical": critical_issues,
        "warnings": warnings,
        "checks": check_results,
    }


def validate_frontmatter(fm: dict, template_name: str, filename: str) -> list:
    """验证 Front Matter 的必填字段和置信度合规性，返回错误列表（空=通过）

    v41.0: schema migration 兼容层——缺失字段自动填默认值而非崩溃
    """
    errors = []

    # v41.0: 自动填充缺失字段（schema migration 兼容）
    _FM_DEFAULTS = {
        "confidence_note": "auto-generated",
        "source_chapter": 0,
        "type": template_name.replace("_template.md", "").replace(".md", ""),
    }
    required = REQUIRED_FRONTMATTER.get(template_name, set())
    for key in required:
        if key not in fm and key in _FM_DEFAULTS:
            fm[key] = _FM_DEFAULTS[key]
            log.info(f"  ℹ️  {filename}: 自动填充缺失字段 '{key}' = {fm[key]!r}")

    # 1. 必填字段检查（含占位符值检测）
    missing = required - set(fm.keys())
    if missing:
        errors.append(f"缺少必填 FrontMatter 字段: {', '.join(sorted(missing))}")
    else:
        # 值未填充（仍是 {{placeholder}}）视为缺失
        placeholder_pattern = re.compile(r"^\{\{[^}]+\}\}$")
        for key in required:
            val = fm.get(key)
            if isinstance(val, str) and placeholder_pattern.match(val):
                errors.append(f"字段 '{key}' 值未填充（占位符残留: {val}）")

    # 2. 置信度值合规性检查
    allowed = CONFIDENCE_LEVELS.get(template_name, set())
    if allowed:
        conf = fm.get("confidence")
        if conf is None:
            errors.append("缺少 confidence 字段")
        elif isinstance(conf, str) and re.match(r"^\{\{", conf):
            errors.append(f"confidence 未填充（占位符残留: {conf}）")
        elif conf not in allowed:
            errors.append(f"confidence={conf} 不符合 {template_name} 的允许值 {allowed}")

    return errors


# ── 统一质量检查入口 ─────────────────────────────────────
# 整合 comprehensive-content-check.py 与 TYPE_QUALITY_CHECKS


def comprehensive_content_check(wiki_root: str) -> list:
    """统一质量检查入口。

    1. 调用 comprehensive-content-check.py 的 run_all() 执行全面内容检查
       （含各类型节点的子节填充度、Mermaid+解析文字、置信度、占位符等）
    2. 对每个 .md 节点文件额外执行 TYPE_QUALITY_CHECKS 类型级质量检查
       （含 FrontMatter 完整性、名称/类型/置信度、定义质量、来源检索等）

    返回:
        list of (severity, type, message) tuples
        其中 severity ∈ {"FAIL", "WARN", "INFO"}
    """
    results = []

    # ── Step 1：调用 comprehensive-content-check.py 的 run_all() ──
    try:
        import importlib.util

        ccc_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "comprehensive_content_check.py")
        spec = importlib.util.spec_from_file_location("comprehensive_content_check_mod", ccc_path)
        ccc_mod = importlib.util.module_from_spec(spec)
        # 保持与 comprehensive_content_check.py 一致的 sys.path 以便其自身 import dag_controller
        _ccc_dir = os.path.dirname(ccc_path)
        if _ccc_dir not in sys.path:
            sys.path.insert(0, _ccc_dir)
        spec.loader.exec_module(ccc_mod)
        ccc_results = ccc_mod.run_all(wiki_root)
        results.extend(ccc_results)
    except Exception as e:
        results.append(("FAIL", "system", f"comprehensive_content_check 调用失败: {e}"))

    # ── Step 2：对每个 .md 节点文件运行 TYPE_QUALITY_CHECKS ──

    # v37.0: 五大类模板归并 — type_check_key 映射到新模板键
    from dag_constants import DIR as _DIR
    type_to_dirname = {
        "concept_template.md": _DIR["CONCEPTS"],  # 核心概念
        "ke_template.md": _DIR["KE"],       # v47.0: 知识要素专用模板
        "entity_template.md": _DIR["ENTITIES"],  # v47.0: 实体专用模板
        "knowledge_template.md": _DIR["KP"],  # 知识点
        "skill_template.md": _DIR["SP"],  # 技能点
        "scenario_template.md": _DIR["SCENE"],  # 场景
        "eval/exercise": _DIR["EXERCISES"],  # 习题
        "eval/solution": _DIR["SOLUTIONS"],  # 解答
    }

    for template_name, rel_dir in type_to_dirname.items():
        check_dir = os.path.join(wiki_root, rel_dir)
        if not os.path.isdir(check_dir):
            continue
        for fname in sorted(os.listdir(check_dir)):
            if not fname.endswith(".md"):
                continue
            fpath = os.path.join(check_dir, fname)
            qc = run_type_quality_checks(fpath, template_name)

            # 将 dict 结果转为统一的 tuple 列表
            type_label = template_name.replace(".md", "")
            for issue in qc.get("critical", []):
                results.append(("FAIL", type_label, f"{fname}: {issue}"))
            for issue in qc.get("warnings", []):
                results.append(("WARN", type_label, f"{fname}: {issue}"))

    return results
