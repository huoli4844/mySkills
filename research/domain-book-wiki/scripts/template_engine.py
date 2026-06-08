#!/usr/bin/env python3
"""Template engine: load, parse, fill templates, mermaid helpers"""

import os
import re

from log_utils import get_logger
from parse_utils import parse_frontmatter as _parse_fm

log = get_logger(__name__)


# ── 模板加载与解析 ──────────────────────────────────────────


def load_template(template_name: str) -> str:
    """从 assets/templates/ 加载模板文件（完整内容，含Front Matter）"""
    skill_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    template_path = os.path.join(skill_root, "assets", "templates", template_name)

    if not os.path.exists(template_path):
        raise FileNotFoundError(f"模板文件不存在: {template_path}")

    with open(template_path, encoding="utf-8") as f:
        return f.read()


def parse_template(template_content: str) -> dict:
    """解析模板，分离Front Matter和Body

    返回：
        {
            'front_matter': {...},  # 解析后的YAML（字典）
            'body_template': str,       # Body部分的模板（含占位符）
            'raw_front_matter': str     # Front Matter原始文本（用于替换）
        }
    """
    if not template_content.startswith("---"):
        raise ValueError("模板必须包含Front Matter（以---开头）")

    parts = template_content.split("---", 2)
    if len(parts) < 3:
        raise ValueError("模板格式错误：无法分割Front Matter和Body")

    raw_fm = parts[1].strip()
    body_template = parts[2].strip()

    fm_dict = _parse_fm("---" + "\n" + raw_fm + "\n" + "---")

    return {"front_matter": fm_dict, "body_template": body_template, "raw_front_matter": raw_fm}


def fill_template(body_template: str, replacements: dict) -> str:
    """替换模板Body上的占位符（格式：{{key}}），并清理 Jinja2 条件句

    v39.1: 自动展开 YAML 多行字符串中的 \\n 字面量为实际换行符
    """
    result = body_template
    for key, value in replacements.items():
        placeholder = "{{" + key + "}}"
        val_str = str(value)
        if "\\n" in val_str:
            val_str = re.sub(r"\\n(?![a-zA-Z])", "\n", val_str)
        result = result.replace(placeholder, val_str)
    # Clean up Jinja2 conditionals (strip them WITHOUT evaluating — LIMITATION!)
    if re.search(r"\{%[- ]+(if|endif|for|raw|end)", result):
        matches = re.findall(r"\{%[- ]+[^%]+%\}", result)
        log.warning(f"  ⚠️  WARNING: {len(matches)} Jinja2 blocks STRIPPED (not evaluated). "
            f"All conditional content will always render regardless of conditions.")
    result = re.sub(r"\{%[- ]+if[^%]+%\}", "", result)
    result = re.sub(r"\{%[- ]+endif[^%]*%\}", "", result)
    # Warn about unmatched template placeholders
    unmatched = re.findall(r"\{\{[a-z_][a-z0-9_]*\|\|[a-z_][a-z0-9_]*\}\}", result)
    unmatched += re.findall(r"\{\{[a-z_][a-z0-9_]*\}\}", result)
    if unmatched:
        uniq = sorted(set(unmatched))
        log.info(f"  WARNING: {len(uniq)} template placeholders missing from body_replacements: {', '.join(uniq[:6])}")
    # v50.0: 去除 HTML 注释（模板中的Agent提示，不输出到文件）
    result = re.sub(r'<!--.*?-->', '', result, flags=re.DOTALL)
    return result


def _strip_wu_sections(body: str) -> str:
    """C2: 删除内容恰好为'无'或'无。'的 ### / #### 子节"""
    import re as _re

    pattern = _re.compile(r"^#{3,4}\s+[^\n]+\n\s*(?:无[。]?)\s*\n?", _re.MULTILINE)
    stripped = pattern.sub("", body)
    stripped = _re.sub(r"\n{3,}", "\n\n", stripped)
    return stripped


# ── 占位符残留检查 ───────────────────────────────────────────

# P8 fix: （暂无）是故意填写的空节标记，不是占位符（见 SKILL.md 坑 #14）
PLACEHOLDER_PATTERN = re.compile(r"\{\{[^}]+\}\}|（待补充）")


def check_placeholders(content: str, filename: str) -> int:
    """检查组装后的内容中是否存在未替换的 {{placeholder}}，返回残留数"""
    matches = PLACEHOLDER_PATTERN.findall(content)
    if matches:
        log.warning(f"  ⚠️  {filename}: {len(matches)} 个占位符残留 — {', '.join(matches[:8])}")
    return len(matches)


MERMAID_INIT = '%%{init: {"theme": "base", "themeVariables": {"fontSize": "12px"}}}%%'


def add_mermaid_init(content: str) -> str:
    """自动为所有 ```mermaid 代码块添加 %%{init} 紧凑配置（若无）"""

    def _add_init(m):
        block = m.group(0)
        if "%%{" in block:
            return block
        lines = block.split("\n")
        if len(lines) >= 1:
            lines.insert(1, MERMAID_INIT)
        return "\n".join(lines)

    return re.sub(r"```mermaid\n.*?```", _add_init, content, flags=re.DOTALL)


def _wrap_mermaid_fields(content: str) -> str:
    """v43.8: 区域保护模式 — 先保护所有已包裹块，再处理裸露内容，最后统一规范化。

    杜绝 v43.7 的二次包裹 bug：_wrap_unwrapped 会把已包裹块内部的 graph
    行再次匹配，导致嵌套 ```mermaid``` fences。

    流程：
      1. 提取所有 ```mermaid...``` 块 → 替换为占位符
      2. 对非 mermaid 区域包裹裸露的 mermaid 内容
      3. 归一化所有被保护的块（strip → add init → re-wrap）
      4. 最后防线：修复块内误吞的标题
    """
    MERMAID_KEYWORDS = (
        "flowchart ",
        "graph ",
        "sequenceDiagram",
        "classDiagram",
        "stateDiagram",
        "erDiagram",
        "gantt",
        "pie",
    )

    def _normalize_block(block: str) -> str:
        inner = re.sub(r"^```mermaid\s*\n", "", block)
        inner = re.sub(r"\n```\s*$", "", inner)
        inner = inner.strip()
        if inner in ("无", "无。", "", None):
            return "无"
        inner = inner.replace("→", ">")
        inner = re.sub(r'^%%\{init:.*?\n?', '', inner, flags=re.DOTALL)
        inner = MERMAID_INIT + "\n" + inner
        return "```mermaid\n" + inner + "\n```"

    def _wrap_unwrapped(match):
        inner = match.group(0).strip()
        if inner in ("无", "无。", "", None):
            return inner
        inner = inner.replace("→", ">")
        inner_with_init = MERMAID_INIT + "\n" + inner if not inner.startswith("%%{") else inner
        return "```mermaid\n" + inner_with_init + "\n```"

    placeholders = {}
    ph_counter = [0]

    def _protect(m):
        key = f"__MERMAID_P{ph_counter[0]}__"
        ph_counter[0] += 1
        placeholders[key] = m.group(0)
        return "\n" + key + "\n"

    content = re.sub(r"```mermaid\n.*?\n```\s*", _protect, content, flags=re.DOTALL)

    for kw in MERMAID_KEYWORDS:
        content = re.sub(
            rf"(?<!```)\n({kw}[^\n]+(?:\n[ \t]+[^\n]+)*)",
            lambda m: "\n" + _wrap_unwrapped(m),
            content,
        )

    for key, block in placeholders.items():
        content = content.replace(key, _normalize_block(block))

    content = _fix_mermaid_block_boundaries(content)

    return content


def _fix_mermaid_block_boundaries(content: str) -> str:
    """v35.2: 最后防线 — 修复 Mermaid 块内误包含的 Markdown 标题。

    如果 ```mermaid...``` 块内出现了 ### 或 ## 标题行，说明闭合 ``` 放错了位置，
    在这些标题前插入闭合 ```，在标题后重新打开 ```mermaid...``` 块。
    """

    def _fix_one_block(match):
        block = match.group(0)
        inner_match = re.match(r"```mermaid\n(.*?)\n```\s*$", block, re.DOTALL)
        if not inner_match:
            return block
        inner = inner_match.group(1)
        heading_match = re.search(r"\n(#{2,3}\s+[^\n]+)", inner)
        if not heading_match:
            return block

        pos = heading_match.start()
        heading_line = heading_match.group(1)
        before = inner[:pos]
        after = inner[pos:]
        return "```mermaid\n" + before.rstrip() + "\n```\n\n" + heading_line + "\n" + after[len(heading_line):].strip()

    return re.sub(r"```mermaid\n.*?\n```\s*", _fix_one_block, content, flags=re.DOTALL)
