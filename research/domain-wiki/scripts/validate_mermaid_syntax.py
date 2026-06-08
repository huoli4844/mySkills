#!/usr/bin/env python3
"""
validate-mermaid.py — Mermaid 图语法校验脚本

检测知识库 md 文件中 ```mermaid 代码块的常见语法错误。

问题分类：
🔴 ERROR — 必定导致渲染失败
🟡 WARNING — 可能导致渲染异常或样式丢失

用法：
    python3 validate-mermaid.py /path/to/wiki              # 校验全部
    python3 validate-mermaid.py /path/to/wiki --fix         # 自动修复可修复的问题
    python3 validate-mermaid.py /path/to/wiki --scan-only   # 仅输出文件名+错误数
"""

import os
import re
import sys

from dag_constants import PipelineError
from log_utils import get_logger

log = get_logger(__name__)



def check_mermaid_block(block: str, filepath: str, block_index: int) -> list:
    """Check a single ```mermaid block for syntax errors."""
    errors = []
    lines = block.split("\n")

    # Skip first line (```mermaid) and last line (```)
    # block content starts with \n (from ```mermaid\n), so lines[0] is empty
    body = lines[1:] if len(lines) > 2 else []
    # Remove trailing empty line if present
    while body and body[-1].strip() == "":
        body = body[:-1]
    body_text = "\n".join(body)

    # --- 🔴 ERROR CHECKS ---

    # 1. HTML font tags (never valid in Mermaid)
    for lineno, line in enumerate(body, 2):
        if re.search(r"<font[^>]*>", line, re.IGNORECASE):
            errors.append((lineno, "🔴", f"HTML <font> 标签在 Mermaid 中无效: {line.strip()[:60]}"))
        if "</font>" in line:
            errors.append((lineno, "🔴", f"HTML </font> 标签在 Mermaid 中无效: {line.strip()[:60]}"))

    # 2. Escaped quotes \" inside node text ["..."] or ['...']
    # Mermaid does NOT support \" escape inside quoted strings
    for lineno, line in enumerate(body, 2):
        # Check for \" inside "..." (double-quoted node text)
        if re.search(r'\["' + re.escape('\\"'), line) or re.search(re.escape('\\"') + r'"\]', line):
            errors.append((lineno, "🔴", f'转义引号 \\" 在 Mermaid 节点文本中无效: {line.strip()[:60]}'))
        # Also check '...' with \'
        if re.search(r"\['" + re.escape("\\'"), line) or re.search(re.escape("\\'") + r"']", line):
            errors.append((lineno, "🔴", f"转义引号 \\' 在 Mermaid 节点文本中无效: {line.strip()[:60]}"))

    # 3. Unclosed node brackets [text without closing ]
    for lineno, line in enumerate(body, 2):
        # Find node definitions [...]
        opens = line.count("[")
        closes = line.count("]")
        # Check if it's really unclosed (inside a node definition)
        if opens > closes and "[" in line and '["' in line and '"]' not in line:
            errors.append((lineno, "🔴", f"节点定义缺少闭合 ]: {line.strip()[:60]}"))

    # 4. Unclosed strings inside nodes
    for lineno, line in enumerate(body, 2):
        # Check for unclosed " inside [...]
        for m in re.finditer(r"\[([^\]]*)\]", line):
            inner = m.group(1)
            if inner.count('"') % 2 != 0:
                errors.append((lineno, "🔴", f"节点文本中引号不匹配: {line.strip()[:60]}"))

    # 5. Check for literal \n inside node text (should use <br/>)
    for lineno, line in enumerate(body, 2):
        if "\n" in line and ('["' in line or "['" in line):
            errors.append((lineno, "🔴", "Mermaid 节点文本应使用 <br/> 而非 \\n 换行: " + line.strip()[:60]))

    # 5b. Formula characters in Mermaid node text (Unicode math symbols banned)
    FORMULA_CHARS = re.compile(r"[θλσφπαβγωΔΣΩ≈°²³¹]")
    # Unicode subscripts (₁₂₃₄₅₆₇₈₉) and superscripts (⁰¹²³⁴⁵⁶⁷⁸⁹)
    # Use literal Unicode chars in the regex
    UNICODE_SUBSUP = re.compile("[\u2080-\u2089\u2070-\u2079]")
    # Additional math operators that should not appear in node text: = ∑ ∫ ∏ {} +
    # But we need to be careful: = can appear in node labels like D0["N=10"] as false positive
    # Check = only when accompanied by other formula indicators
    MATH_OPS_IN_NODE = re.compile(r"[∑∫∏∂∇√∞]")
    for lineno, line in enumerate(body, 2):
        for m in re.finditer(r"\[([^\]\n]*)\]", line):
            inner = m.group(1)
            # v37.0: 已加引号的节点文本 ["..."] 是合法文本，跳过公式字符检查
            stripped_inner = inner.strip()
            if (stripped_inner.startswith('"') and stripped_inner.endswith('"')) or (
                stripped_inner.startswith("'") and stripped_inner.endswith("'")
            ):
                continue
            has_problems = False
            # Check Greek letters
            if FORMULA_CHARS.search(inner):
                has_problems = True
            # Check Unicode subscripts
            if UNICODE_SUBSUP.search(inner):
                has_problems = True
            # Check math operators
            if MATH_OPS_IN_NODE.search(inner):
                has_problems = True
            # Check = inside node text (indicating an equation)
            if "=" in inner and not inner.strip().startswith('"') and not inner.strip().startswith("'"):
                # = inside a node like [a=b] is almost always a formula
                has_problems = True
            if has_problems:
                errors.append((lineno, "🔴", "Mermaid 节点文本含公式符号，请改用中文描述: " + line.strip()[:60]))
                break

    # 5c. Dollar sign in Mermaid blocks (LaTeX delimiter)
    for lineno, line in enumerate(body, 2):
        if "$" in line:
            errors.append((lineno, "🔴", "Mermaid 中不应出现 $ 符号（LaTeX 分隔符）: " + line.strip()[:50]))

    # 5d. Layout direction check - flow diagrams should use graph LR
    # Detect diagram type from block content
    has_flow_keywords = any(kw in block for kw in ["解题思路", "推导流程", "操作流程"])
    has_network_keywords = any(kw in block for kw in ["知识闭环", "知识脉络"])
    for lineno, line in enumerate(body, 2):
        if "graph " in line:
            if has_flow_keywords:
                if "graph TD" in line:
                    errors.append((lineno, "🟡", "解题思路/推导流程/操作流程图应使用 graph LR（水平排列）"))
            elif has_network_keywords and "graph LR" in line:
                errors.append((lineno, "🟡", "知识脉络/知识闭环图应使用 graph TD（纵向排列）"))

    # 5e. Subgraph blank line — blank line right after subgraph declaration
    # Mermaid treats blank lines inside subgraph as end-of-subgraph
    for lineno, line in enumerate(body, 2):
        m = re.match(r"(\s*)subgraph\s+(\w+)\[", line)
        if m:
            _indent = m.group(1)
            name = m.group(2)
            # Check next line
            if lineno < len(body) + 1:
                next_line = body[lineno - 1] if lineno <= len(body) else ""
                if next_line.strip() == "":
                    errors.append(
                        (lineno + 1, "🔴", f'subgraph "{name}" 后紧跟空白行 — Mermaid 将空白行视为 subgraph 结束')
                    )

    # 5f. Split subgraphs — cross-subgraph edges (end\\nX --> Y\\nsubgraph DF2[""])
    # Check for pattern: end then a cross-arrow then another subgraph
    for i, line in enumerate(body):
        if line.strip() == "end" and i + 1 < len(body):
            next_line = body[i + 1].strip()
            # If next line is an arrow going to a node outside current subgraph
            if re.match(r"\w+\s+(?:-->|-\.->)", next_line):
                # Check if there's another subgraph after the arrow
                for j in range(i + 2, min(i + 4, len(body))):
                    if "subgraph " in body[j]:
                        errors.append(
                            (
                                i + 2,
                                "🔴",
                                f"跨 subgraph 箭头（{next_line[:40]}）— 拆分 subgraph 导致渲染异常，应合并为单个 subgraph",
                            )
                        )
                        break

    # 5g. Unquoted <br/> in node text — node[...] without quotes around <br/>
    for lineno, line in enumerate(body, 2):
        # Match node definitions like D4[text<br/>more] (no quotes)
        # Exclude already-quoted: D4["text<br/>more"]
        if re.search(r'\[\w[^\[\]"]*<br/>[^\\[\\]"\']*\\]', line):
            errors.append((lineno, "🔴", f"含 <br/> 的节点缺少双引号包裹: {line.strip()[:60]}"))

    # Catch subgraph declarations matching quoted or unquoted forms
    subgraph_count = 0
    for body_line in body:
        if "subgraph" in body_line and ("[" in body_line or '"' in body_line):
            subgraph_count += 1
    end_count = 0
    for body_line in body:
        if body_line.strip() == "end":
            end_count += 1
    if subgraph_count > end_count:
        errors.append(
            (
                0,
                "🔴",
                f"subgraph 数量({subgraph_count}) > end 数量({end_count}) — 缺少 end (file: {os.path.basename(filepath)})",
            )
        )

    # --- 新增: 跨 subgraph 边缘检测 — subgraph 间的箭头导致渲染失败 ---
    in_subgraph = False
    current_sg_name = ""
    sg_nodes = {}  # node_id -> subgraph_name
    all_edges = []  # (src, dst)
    for _lineno, line in enumerate(body, 2):
        sm = re.match(r'\s*subgraph\s+("[^"]*"|\w+)', line)
        if sm:
            in_subgraph = True
            current_sg_name = sm.group(1)
            continue
        if line.strip() == "end" and in_subgraph:
            in_subgraph = False
            current_sg_name = ""
            continue
        if in_subgraph and current_sg_name:
            for m in re.finditer(r"\b([A-Z][A-Za-z0-9]*)\[", line):
                sg_nodes[m.group(1)] = current_sg_name
        for m in re.finditer(r"\b([A-Z][A-Za-z0-9]*)\s*-->\s*(?:\|[^|]*\|\s*)?([A-Z][A-Za-z0-9]*)", line):
            all_edges.append((m.group(1), m.group(2)))

    for src, dst in all_edges:
        if src in sg_nodes and dst in sg_nodes and sg_nodes[src] != sg_nodes[dst]:
            errors.append(
                (
                    0,
                    "🔴",
                    f"跨 subgraph 箭头: {src}({sg_nodes[src]}) → {dst}({sg_nodes[dst]}) — Mermaid 不支持 subgraph 间连线，会导致整张图渲染失败",
                )
            )

    # --- 检查 %%{init} 格式（仅检查语法完整性）---

    # 6. Old-style `style X fill:` declarations (should use classDef + class)
    for lineno, line in enumerate(body, 2):
        stripped = line.strip()
        if re.match(r"style\s+\w+\s+fill:", stripped):
            errors.append((lineno, "🟡", f"旧式 style 声明，建议改用 classDef+class: {stripped[:50]}"))

    # 7. Orphan nodes (defined but never referenced in arrows, and not referenced by style)
    # Extract all node IDs (things like CONa, KP, S0, etc.)
    # Skip subgraph names (FC, KC, etc.)
    subgraph_names = set()
    for m in re.finditer(r'subgraph\s+(?:"([^"]+)"|(\w+))\[?', body_text):
        name = m.group(1) or m.group(2)
        subgraph_names.add(name)

    node_ids = set()
    for m in re.finditer(r'(\w+)\[(?:"[^"]*"|[^\]]*)\]', body_text):
        nid = m.group(1)
        if nid not in subgraph_names:
            node_ids.add(nid)

    # Extract all references: arrows and class declarations
    ref_ids = set()
    # Pattern: S0 --> S1  or S0 --> |label| S1 (arrow between two nodes)
    # Handles: A["text"] --> B[text], A[text] --> B, A --> B
    for m in re.finditer(r"(\w+)(?:\[[^\]]*\])?\s*(?:-->|-\\.->)\s*(?:\|[^|]*\|\s*)?(\w+)", body_text):
        ref_ids.add(m.group(1))
        ref_ids.add(m.group(2))
    # Pattern: | label| Node  (pipe before target)
    for m in re.finditer(r"\|[^|]*\|\s*(\w+)", body_text):
        ref_ids.add(m.group(1))
    # Pattern: Node |label|  (pipe after source)
    for m in re.finditer(r"(\w+)\s*\|", body_text):
        ref_ids.add(m.group(1))
    # Pattern: class X,Y,Z className
    for m in re.finditer(r"class\s+([\w,]+)", body_text):
        for cid in m.group(1).split(","):
            ref_ids.add(cid.strip())

    for nid in sorted(node_ids):
        if nid not in ref_ids:
            for lineno, line in enumerate(body, 2):
                if f' {nid}["' in line or f'{nid}["' in line:
                    errors.append((lineno, "🟡", f'节点 "{nid}" 定义了但未在箭头或 class 中出现'))
                    break

    # 8. Missing init config (recommended)
    has_config = "%%{" in body_text
    if not has_config:
        errors.append((0, "🟡", "缺少 %%{init:...} 紧凑配置（推荐添加以控制图表尺寸）"))

    return errors


def scan_file(filepath: str, fix: bool = False) -> list:
    """Scan one file for mermaid syntax errors."""
    import re
    with open(filepath, encoding="utf-8") as f:
        content = f.read()

    errors = []
    modified = False

    # v43.8: 嵌套 fence 预检
    fence_lines = re.findall(r"^```(?:mermaid)?\s*$", content, re.MULTILINE)
    depth = 0
    inner_fence_count = 0
    for fl in fence_lines:
        if fl.startswith("```mermaid"):
            if depth > 0:
                inner_fence_count += 1
            depth += 1
        elif fl == "```":
            depth = max(0, depth - 1)
    if inner_fence_count > 0:
        errors.append((filepath, -1, 0, "🔴 ERROR",
            f"嵌套 mermaid fence: {inner_fence_count} 个 ```mermaid 出现在另一个块内部"))

    # v43.18: 自动修复 %%{init} Obsidian 兼容性
    # 1. 单引号 → 双引号
    if "'theme':" in content or "'base':" in content or "'fontSize':" in content:
        content = re.sub(r"%%\{init: \{'theme': 'base', 'themeVariables': \{'fontSize': '(\d+)px'\}\}\}",
                         r'%%{init: {"theme": "base", "themeVariables": {"fontSize": "\1px"}}}%%',
                         content)
        modified = True
    # 2. 已经有双引号但缺 }%% 闭合
    elif re.search(r'%%\{init: \{"theme": "base".*?\}\}\n', content) and '}%%' not in content:
        content = re.sub(r'(%%\{init: \{"theme": "base".*?\}\})\n', r'\1%%\n', content)
        modified = True
    pos = 0
    block_index = 0
    while True:
        start = content.find("```mermaid", pos)
        if start < 0:
            break
        end = content.find("```", start + 10)
        if end < 0:
            break
        end += 3

        block = content[start:end]
        block_errors = check_mermaid_block(block, filepath, block_index)
        for lineno, sev, msg in block_errors:
            errors.append((filepath, block_index, lineno, sev, msg))

        # Auto-fix if requested
        if fix:
            fixed = block

            # Fix 1: Remove <font> tags
            fixed = re.sub(r"<font[^>]*>", "", fixed)
            fixed = fixed.replace("</font>", "")

            # Fix 2: Fix escaped quotes inside [...] (remove backslash before quote)
            # Pattern: inside [...], replace \" with "
            def fix_escaped_quotes(m):
                inner = m.group(1)
                inner = inner.replace('\\"', '"')
                return "[" + inner + "]"

            fixed = re.sub(r"\[([^\]]*)\]", fix_escaped_quotes, fixed)

            # Fix 3: Convert old `style X fill:` to classDef
            # (This is complex, skip for now - just report)

            # Fix 4: Add %%{init} config if missing
            if "%%{" not in fixed:
                init_config = "%%{init: {'theme': 'base', 'themeVariables': {'fontSize': '12px'}}}\n"
                # Insert after the ```mermaid line
                lines = fixed.split("\n")
                if len(lines) >= 2:
                    lines.insert(1, init_config.strip())
                fixed = "\n".join(lines)

            if fixed != block:
                content = content[:start] + fixed + content[end:]
                modified = True
                end = start + len(fixed)

        pos = end
        block_index += 1

    if modified:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

    return errors


def scan_dir(wiki_root: str, fix: bool = False, scan_only: bool = False, json_output: bool = False):
    """Scan all md files under wiki_root for mermaid syntax errors."""
    from dag_constants import DIR
    target_dirs = [DIR["CONCEPTS"], DIR["KE"], DIR["KP"], DIR["SP"], DIR["SCENE"], DIR["EXERCISES"], DIR["SOLUTIONS"]]

    all_errors = []
    total_files = 0
    files_with_issues = 0

    for dirname in target_dirs:
        d = os.path.join(wiki_root, dirname)
        if not os.path.isdir(d):
            continue
        for fn in sorted(os.listdir(d)):
            if not fn.endswith(".md"):
                continue
            fp = os.path.join(d, fn)
            errors = scan_file(fp, fix=fix)
            total_files += 1
            if errors:
                files_with_issues += 1
                all_errors.extend(errors)

                # Group errors by file for concise output
                _file_severity = max(e[3] for e in errors)
                error_count = len(errors)

                if scan_only:
                    # Compact output: just file name and count
                    has_red = any(e[3] == "🔴" for e in errors)
                    has_yellow = any(e[3] == "🟡" for e in errors)
                    symbols = ""
                    if has_red:
                        symbols += "🔴"
                    if has_yellow:
                        symbols += "🟡"
                    log.info(f"{fn}: {symbols} {error_count} issues")
                elif not fix:
                    # Full output
                    log.info(f"\n=== {dirname}/{fn} ({error_count} issues) ===")
                    for _f, _bi, lineno, sev, msg in errors:
                        loc = f"L{lineno}" if lineno > 0 else "overall"
                        log.info(f"  {sev} [{loc}] {msg}")

    # Summary
    log.info("\n--- Summary ---")
    log.info(f"Files scanned: {total_files}")
    log.info(f"Files with issues: {files_with_issues}")
    log.info(f"Total issues: {len(all_errors)}")

    red_count = sum(1 for e in all_errors if e[3] == "🔴")
    yellow_count = sum(1 for e in all_errors if e[3] == "🟡")

    if json_output:
        # v40.0: 结构化 JSON 输出（供 ScriptRunner 解析）
        import json as _json
        from collections import defaultdict as _dd

        _by_file = _dd(list)
        for e in all_errors:
            _by_file[e[0]].append(e)
        files_info = []
        for fn, errs in _by_file.items():
            files_info.append(
                {
                    "file": fn,
                    "errors": sum(1 for e in errs if e[3] == "🔴"),
                    "warnings": sum(1 for e in errs if e[3] == "🟡"),
                }
            )
        log.info(f"JSON_OUTPUT:{_json.dumps({'scanned': total_files, 'errors': red_count, 'warnings': yellow_count, 'files': files_info}, ensure_ascii=False)}")
        return len(all_errors) == 0

    log.info(f"  🔴 Errors: {red_count}")
    log.info(f"  🟡 Warnings: {yellow_count}")

    if fix:
        log.info("Auto-fix applied (removed font tags, fixed escaped quotes)")

    return len(all_errors) == 0


if __name__ == "__main__":
    try:
        if len(sys.argv) < 2:
            log.info(__doc__)
            raise PipelineError("用法: python3 validate_mermaid_syntax.py <wiki_root> [--fix] [--scan-only] [--json]")

        wiki_root = sys.argv[1]
        fix = "--fix" in sys.argv
        scan_only = "--scan-only" in sys.argv
        json_out = "--json" in sys.argv

        ok = scan_dir(wiki_root, fix=fix, scan_only=scan_only, json_output=json_out)
        if not ok:
            raise PipelineError("Mermaid validation FAILED")
    except PipelineError as e:
        log.error(str(e))
        raise
