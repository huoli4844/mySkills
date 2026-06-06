"""parse_utils.py — 统一解析工具

v38.0: 消除 frontmatter 解析、body 提取、占位符检测的重复代码。
被 template_assembler.py、kb_graph.py、comprehensive_content_check.py、
dag_quality.py 等多个模块共同使用。

核心函数：
    parse_frontmatter(content) → dict       解析 YAML frontmatter
    split_fm_body(content) → (fm_str, body) 分离 frontmatter 和 body
    has_placeholder(text) → bool             检测未替换的占位符
    safe_filename(name) → str                文件名安全化
"""

import json
import re
from typing import Any

# ── Frontmatter 解析 ────────────────────────────────────

# 匹配 YAML frontmatter（--- ... ---）
_FM_PATTERN = re.compile(r"^---\n(.*?)\n---", re.DOTALL)

# 占位符检测：{{placeholder}} 和中文骨架占位符
_PLACEHOLDER_PATTERN = re.compile(r"\{\{[^}]+\}\}|（待补充）")
_SKELETON_PATTERNS = [
    re.compile(r"（待填充[^）]*）"),
    re.compile(r"（待Agent[^）]*）"),
    re.compile(r"（待补充[^）]*）"),
    re.compile(r"（暂无[^）]*）"),
]


def parse_frontmatter(content: str) -> dict[str, Any]:
    """解析 YAML frontmatter，返回字典。

    支持：
    - 基本键值对 (key: value)
    - JSON 数组 (key: [a, b, c])
    - 数字自动转换 (key: 3.14 → float)
    - 引号去除 (key: "value" → value)

    Args:
        content: 完整的 .md 文件内容（以 --- 开头）

    Returns:
        frontmatter 字典；若无 frontmatter 则返回空字典

    Examples:
        >>> parse_frontmatter("---\\nname: 测试\\ntype: concept\\n---\\nbody")
        {'name': '测试', 'type': 'concept'}
    """
    match = _FM_PATTERN.match(content)
    if not match:
        return {}

    fm: dict[str, Any] = {}
    for line in match.group(1).strip().split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue

        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()

        # 去除引号
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
            value = value[1:-1]
        # JSON 数组
        elif value.startswith("[") and value.endswith("]"):
            try:
                value = json.loads(value)
            except (json.JSONDecodeError, ValueError):
                pass
        # 数字
        elif value.replace(".", "", 1).isdigit() and value:
            try:
                value = float(value) if "." in value else int(value)
            except ValueError:
                pass

        fm[key] = value

    return fm


def split_fm_body(content: str) -> tuple[str, str]:
    """分离 frontmatter 原始文本和 body。

    Args:
        content: 完整的 .md 文件内容

    Returns:
        (raw_frontmatter, body) 元组。
        若无 frontmatter，raw_frontmatter 为空字符串。
    """
    if not content.startswith("---"):
        return "", content

    parts = content.split("---", 2)
    if len(parts) < 3:
        return "", content

    raw_fm = parts[1].strip()
    body = parts[2].strip()
    return raw_fm, body


def extract_fm_field(content: str, field: str) -> str | None:
    """快速提取 frontmatter 中的单个字段值。

    比 parse_frontmatter() 更轻量，适合只需要一两个字段的场景。

    Args:
        content: 完整的 .md 文件内容
        field: 字段名（如 "name", "type", "confidence"）

    Returns:
        字段值字符串，或 None（字段不存在）
    """
    match = _FM_PATTERN.match(content)
    if not match:
        return None
    for line in match.group(1).strip().split("\n"):
        if line.strip().startswith(field + ":"):
            _, _, val = line.partition(":")
            return val.strip().strip("\"'")
    return None


# ── 占位符检测 ───────────────────────────────────────────


def has_placeholder(text: str) -> bool:
    """检测 body 是否残留未替换的占位符。

    检查：
    1. {{placeholder}} 格式
    2. 中文骨架占位符（待填充/待Agent/待补充/暂无）

    Args:
        text: 要检查的文本

    Returns:
        True 表示存在占位符
    """
    if _PLACEHOLDER_PATTERN.search(text):
        return True
    return any(pat.search(text) for pat in _SKELETON_PATTERNS)


def find_placeholders(text: str) -> list:
    """查找所有未替换的占位符，返回列表。"""
    matches = _PLACEHOLDER_PATTERN.findall(text)
    return list(set(matches))


# ── 文件名安全化 ─────────────────────────────────────────

_UNSAFE_CHARS = set('\\/:*?"<>|')


def safe_filename(name: str) -> str:
    """移除文件名中的非法字符。

    Args:
        name: 原始文件名

    Returns:
        安全化后的文件名（不含扩展名）
    """
    return "".join(c for c in name if c not in _UNSAFE_CHARS)


# ── 内容提取工具 ─────────────────────────────────────────


def extract_section(body: str, heading_prefix: str) -> str:
    """提取 ### 或 #### 子节下的 body 文本。

    Args:
        body: markdown body 内容
        heading_prefix: 标题前缀（如 "### 1. 精准释义"）

    Returns:
        该标题下的文本内容
    """
    pattern = re.escape(heading_prefix)
    idx = re.search(pattern, body)
    if not idx:
        return ""
    start = idx.end()
    # 只匹配 ### 或更高级标题（排除正文中 ## 子节标题干扰）
    next_match = re.search(r"\n#{1,3}\s+\d", body[start:])
    if next_match:
        return body[start : start + next_match.start()]
    return body[start:]


def section_has_real_content(body: str, heading_prefix: str, min_chars: int = 10) -> bool:
    """判断某节是否有实质内容（排除 Mermaid 图、空行、纯标点）。

    Args:
        body: markdown body 内容
        heading_prefix: 标题前缀
        min_chars: 最低有效字符数

    Returns:
        True 表示有实质内容
    """
    sec = extract_section(body, heading_prefix)
    # 去除代码块
    sec = re.sub(r"```.*?```", "", sec, flags=re.DOTALL)
    sec = re.sub(r"\s+", "", sec)
    sec = re.sub(
        r"[，。、；：！？（）【】《》\u201c\u201d\u2018\u2019「」『』—…\-\*#\n\r\t]",
        "",
        sec,
    )
    return len(sec) >= min_chars
