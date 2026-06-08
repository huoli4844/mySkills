#!/usr/bin/env python3
"""validate_render.py — 构建产物渲染级校验 (v47.0 新增)

实现三项渲染级校验：
  1. Mermaid 语法验证：%%{init} 语法合法性、classDef 引用完整性、节点数 ≤ 30
  2. LaTeX 校验：花括号平衡、\\left/\\right 配对、空 \\frac 检测
  3. wikilink 全量可达性扫描：提取所有 [[...]] 链接，验证目标文件存在

用法:
  python3 validate_render.py <wiki_root> [--book-id BOOK_ID] [--check mermaid|latex|wikilink|all]
  python3 validate_render.py <wiki_root> --check all --json  # JSON 输出模式

集成:
  - 作为独立校验脚本运行
  - 被 dag_pipeline_run.py 的 pipeline_validate 调用
"""

from __future__ import annotations


import argparse
import json
import os
import re
import sys
from typing import Any

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

from dag_constants import DIR, PipelineError  # noqa: E402
from log_utils import get_logger  # noqa: E402

log = get_logger(__name__)


# ═══════════════════════════════════════════════════════════
# 通用工具
# ═══════════════════════════════════════════════════════════

def _find_md_files(root_dir: str) -> list[str]:
    """递归查找所有 .md 文件"""
    files = []
    for dirpath, _, filenames in os.walk(root_dir):
        for fn in filenames:
            if fn.endswith(".md"):
                files.append(os.path.join(dirpath, fn))
    return files


def _read_file(path: str) -> str | None:
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        log.debug(f"文件读取失败: {e}")
        return None


# ═══════════════════════════════════════════════════════════
# 1. Mermaid 语法验证
# ═══════════════════════════════════════════════════════════

_MERMAID_BLOCK_RE = re.compile(r"```mermaid\s*\n(.*?)```", re.DOTALL)
_NODE_ID_RE = re.compile(r"(\w+)(?=\[|\(|\{|>|\|)")
_CLASSDEF_RE = re.compile(r"classDef\s+(\w+)")
_CLASS_APPLY_RE = re.compile(r"class\s+[\w,\s]+\s+(\w+)")
_INIT_RE = re.compile(r"%%\{init:")


def check_mermaid(content: str, filepath: str = "") -> list[dict]:
    """检查单个 .md 文件中的所有 Mermaid 块。
    
    Returns:
        [{file, block_index, severity, message}, ...]
    """
    issues = []
    blocks = _MERMAID_BLOCK_RE.findall(content)

    for bi, block in enumerate(blocks):
        block = block.strip()
        if not block:
            continue

        # 1. %%{init} 语法检查
        init_matches = _INIT_RE.findall(block)
        for im in init_matches:
            # 检查闭合
            close_count = block.count("}%%")
            open_count = block.count("%%{")
            if open_count != close_count:
                issues.append({
                    "file": filepath,
                    "block_index": bi,
                    "severity": "error",
                    "category": "mermaid_init",
                    "message": f"%%{{init 块未正确闭合 (open={open_count}, close={close_count})",
                })

        # 2. classDef 引用检查
        classdefs = set(_CLASSDEF_RE.findall(block))
        class_applies = set()
        for line in block.split("\n"):
            m = re.search(r"class\s+([\w,\s]+)\s+(\w+)", line)
            if m:
                class_applies.add(m.group(2))
            # 也检查 ::: 语法
            m2 = re.search(r":::(\w+)", line)
            if m2:
                class_applies.add(m2.group(1))

        unused_classdefs = classdefs - class_applies
        if unused_classdefs:
            for cd in sorted(unused_classdefs):
                issues.append({
                    "file": filepath,
                    "block_index": bi,
                    "severity": "warning",
                    "category": "mermaid_classdef_unused",
                    "message": f"classDef '{cd}' 定义但未被引用",
                })

        # 3. 节点数检查 (≤30)
        nodes = set()
        for line in block.split("\n"):
            # 匹配节点定义:  node[text], node(text), node{text}, node>text]
            for match in re.finditer(r"(\w+)(?:\[.*?\]|\(.*?\)|\{.*?\}|>.*?\])", line):
                nodes.add(match.group(1))
        if len(nodes) > 30:
            issues.append({
                "file": filepath,
                "block_index": bi,
                "severity": "warning",
                "category": "mermaid_node_count",
                "message": f"Mermaid 节点数 {len(nodes)} > 30（建议拆分或简化）",
            })

    return issues


# ═══════════════════════════════════════════════════════════
# 2. LaTeX 校验
# ═══════════════════════════════════════════════════════════

_DOLLAR_BLOCK_RE = re.compile(r"\$\$(.*?)\$\$", re.DOTALL)
_INLINE_MATH_RE = re.compile(r"(?<!\$)\$(?!\$)(.*?)(?<!\$)\$(?!\$)")


def check_latex(content: str, filepath: str = "") -> list[dict]:
    """检查单个 .md 文件中的所有 LaTeX 公式块。

    Returns:
        [{file, block_index, severity, message}, ...]
    """
    issues = []

    # 提取所有 $$...$$ 块和内联 $...$ 块
    formula_blocks = []
    for m in _DOLLAR_BLOCK_RE.finditer(content):
        formula_blocks.append((m.group(1).strip(), m.start()))
    for m in _INLINE_MATH_RE.finditer(content):
        formula_blocks.append((m.group(1).strip(), m.start()))

    for fi, (formula, _pos) in enumerate(formula_blocks):
        # 1. 花括号平衡
        open_braces = formula.count("{")
        close_braces = formula.count("}")
        if open_braces != close_braces:
            issues.append({
                "file": filepath,
                "block_index": fi,
                "severity": "error",
                "category": "latex_brace_balance",
                "message": f"花括号不平衡 ({{={open_braces}, }}= {close_braces})",
            })

        # 2. \left / \right 配对
        left_count = len(re.findall(r"\\left[\(\[\{\|\.]", formula))
        right_count = len(re.findall(r"\\right[\)\]\}\|\.]", formula))
        if left_count != right_count:
            issues.append({
                "file": filepath,
                "block_index": fi,
                "severity": "error",
                "category": "latex_left_right",
                "message": f"\\left/\\right 不配对 (\\left={left_count}, \\right={right_count})",
            })

        # 3. 空 \frac 检测
        empty_fracs = re.findall(r"\\frac\{\s*\}", formula)
        if empty_fracs:
            issues.append({
                "file": filepath,
                "block_index": fi,
                "severity": "warning",
                "category": "latex_empty_frac",
                "message": f"发现 {len(empty_fracs)} 个空 \\frac 分子/分母",
            })

    return issues


# ═══════════════════════════════════════════════════════════
# 3. wikilink 全量可达性扫描
# ═══════════════════════════════════════════════════════════

_WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:[|#][^\]]+)?\]\]")


def _resolve_wikilink_target(wiki_root: str, link_target: str) -> str | None:
    """尝试将 wikilink 目标解析为实际文件路径。
    
    按规则依次尝试:
      1. 直接路径: {wiki_root}/{book}/目录/{target}.md
      2. 相对路径: 从各 book 目录尝试
      3. 短名: 在所有 .md 文件中匹配 basename
    """
    target_clean = link_target.strip().split("#")[0].split("|")[0]

    # 1. 尝试直接路径（相对 wiki_root）
    direct = os.path.join(wiki_root, target_clean + ".md")
    if os.path.exists(direct):
        return direct

    # 也尝试去掉前导 ../
    if target_clean.startswith("../"):
        nested = os.path.normpath(os.path.join(wiki_root, target_clean + ".md"))
        if os.path.exists(nested):
            return nested

    # 2. 在所有 .md 文件中搜索
    for dirpath, _, filenames in os.walk(wiki_root):
        for fn in filenames:
            if fn.endswith(".md"):
                # 按文件名（无扩展名）匹配
                if fn[:-3] == os.path.basename(target_clean):
                    return os.path.join(dirpath, fn)

    return None


def check_wikilinks(wiki_root: str, book_id: str | None = None) -> list[dict]:
    """全量扫描所有 .md 文件中的 wikilink，验证目标可达性。
    
    Returns:
        [{file, link, target, severity, message}, ...]
    """
    issues = []

    search_root = wiki_root
    if book_id:
        # 在 wiki_root 中查找匹配的 book 目录
        for dirpath, dirnames, _ in os.walk(wiki_root):
            for d in dirnames:
                if d.startswith(book_id) or d == book_id:
                    search_root = os.path.join(dirpath, d)
                    break

    md_files = _find_md_files(search_root)
    log.info(f"  wikilink 可达性扫描: {len(md_files)} 个 .md 文件")

    for filepath in md_files:
        content = _read_file(filepath)
        if not content:
            continue

        links = _WIKILINK_RE.findall(content)
        for link in links:
            target = _resolve_wikilink_target(wiki_root, link)
            if target is None:
                rel_path = os.path.relpath(filepath, wiki_root)
                issues.append({
                    "file": rel_path,
                    "full_path": filepath,
                    "link": link.strip(),
                    "severity": "warning",
                    "category": "wikilink_unreachable",
                    "message": f"wikilink [[{link.strip()}]] 目标不存在",
                })

    return issues


# ═══════════════════════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════════════════════

def validate_all(
    wiki_root: str,
    book_id: str | None = None,
    checks: set | None = None,
) -> dict[str, Any]:
    """运行全部渲染校验。
    
    Returns:
        {
            "passed": bool,
            "total_issues": int,
            "mermaid": [...],
            "latex": [...],
            "wikilink": [...],
        }
    """
    if checks is None:
        checks = {"mermaid", "latex", "wikilink"}

    result: dict[str, Any] = {
        "passed": True,
        "total_issues": 0,
        "mermaid": [],
        "latex": [],
        "wikilink": [],
    }

    search_root = wiki_root
    if book_id:
        for dirpath, dirnames, _ in os.walk(wiki_root):
            for d in dirnames:
                if d.startswith(book_id) or d == book_id:
                    search_root = os.path.join(dirpath, d)
                    break

    md_files = _find_md_files(search_root)
    log.info(f"扫描 {len(md_files)} 个 .md 文件")

    if "mermaid" in checks:
        for fp in md_files:
            content = _read_file(fp)
            if content:
                issues = check_mermaid(content, os.path.relpath(fp, wiki_root))
                result["mermaid"].extend(issues)

    if "latex" in checks:
        for fp in md_files:
            content = _read_file(fp)
            if content:
                issues = check_latex(content, os.path.relpath(fp, wiki_root))
                result["latex"].extend(issues)

    if "wikilink" in checks:
        result["wikilink"] = check_wikilinks(wiki_root, book_id)

    result["total_issues"] = (
        len(result["mermaid"]) + len(result["latex"]) + len(result["wikilink"])
    )

    errors = sum(
        1 for i in result["mermaid"] + result["latex"]
        if i.get("severity") == "error"
    )
    if errors > 0:
        result["passed"] = False

    return result


def main():
    p = argparse.ArgumentParser(description="validate_render — 渲染级校验")
    p.add_argument("wiki_root", help="Wiki 根目录")
    p.add_argument("--book-id", default=None, help="可选: 限定书籍ID")
    p.add_argument(
        "--check",
        choices=["mermaid", "latex", "wikilink", "all"],
        default="all",
        help="校验类别 (default: all)",
    )
    p.add_argument("--json", action="store_true", help="JSON 格式输出")
    args = p.parse_args()

    checks = {"mermaid", "latex", "wikilink"} if args.check == "all" else {args.check}

    result = validate_all(args.wiki_root, args.book_id, checks)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        _print_report(result)

    if not result["passed"]:
        raise PipelineError("Render validation FAILED")


def _print_report(result: dict[str, Any]) -> None:
    """打印人类可读的报告"""
    log.info("=" * 60)
    log.info("  渲染级校验报告")
    log.info("=" * 60)

    # Mermaid
    if result["mermaid"]:
        errors = [i for i in result["mermaid"] if i["severity"] == "error"]
        warnings = [i for i in result["mermaid"] if i["severity"] == "warning"]
        mermaid_total = len(result["mermaid"])
        icon = "❌" if errors else "⚠️"
        log.info(f"\n[1/3] Mermaid: {icon} {mermaid_total} 个问题 "
                  f"({len(errors)} errors, {len(warnings)} warnings)")
        for i in result["mermaid"][:8]:
            sev_icon = "🔴" if i["severity"] == "error" else "🟡"
            log.info(f"  {sev_icon} [{i['category']}] {i['file']}:{i.get('block_index','?')} — {i['message']}")
        if mermaid_total > 8:
            log.info(f"  ... 还有 {mermaid_total - 8} 个问题")
    else:
        log.success("\n[1/3] Mermaid: ✅ 通过")

    # LaTeX
    if result["latex"]:
        errors = [i for i in result["latex"] if i["severity"] == "error"]
        warnings = [i for i in result["latex"] if i["severity"] == "warning"]
        latex_total = len(result["latex"])
        icon = "❌" if errors else "⚠️"
        log.info(f"\n[2/3] LaTeX: {icon} {latex_total} 个问题 "
                  f"({len(errors)} errors, {len(warnings)} warnings)")
        for i in result["latex"][:8]:
            sev_icon = "🔴" if i["severity"] == "error" else "🟡"
            log.info(f"  {sev_icon} [{i['category']}] {i['file']} — {i['message']}")
        if latex_total > 8:
            log.info(f"  ... 还有 {latex_total - 8} 个问题")
    else:
        log.success("\n[2/3] LaTeX: ✅ 通过")

    # Wikilink
    if result["wikilink"]:
        wl_total = len(result["wikilink"])
        log.warning(f"\n[3/3] wikilink: ⚠️ {wl_total} 个不可达链接")
        for i in result["wikilink"][:8]:
            log.info(f"  🟡 {i['file']}: [[{i['link']}]] — 目标不存在")
        if wl_total > 8:
            log.info(f"  ... 还有 {wl_total - 8} 个断链")
    else:
        log.success("\n[3/3] wikilink: ✅ 全部可达")

    if result["passed"]:
        log.success(f"\n✅ 渲染校验通过 (共检查 {result['total_issues']} 个问题)")
    else:
        log.fail(f"\n❌ 渲染校验未通过 ({result['total_issues']} 个问题)")


if __name__ == "__main__":
    main()
