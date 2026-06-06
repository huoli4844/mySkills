"""rules/bloom.py — Bloom层级检查 + 占位符检测 + 节提取工具"""

import re

from config import _FALLBACK_CONTENT_DEPTH, _FALLBACK_SECTION_COUNTS, get_config
from log_utils import get_logger

log = get_logger(__name__)

__all__ = [
    "_load_thresholds",
    "has_placeholder",
    "extract_section",
    "section_has_real_content",
    "check_content_depth",
]


def _load_thresholds():
    """从 config.py 加载阈值，覆盖硬编码兜底值"""
    try:
        cfg = get_config()
        return cfg.content_depth_thresholds, cfg.section_counts
    except Exception as e:
        log.warning(f"配置加载失败，使用兜底值: {e}")
        return _FALLBACK_CONTENT_DEPTH, _FALLBACK_SECTION_COUNTS


def has_placeholder(text):
    """检查 body 是否残留未替换的 {{placeholder}} 或中文骨架占位符"""
    if bool(re.search(r"\{\{.*?\}\}", text)):
        return True
    skeleton_patterns = [
        r"（待填充[^）]*）",
        r"（待Agent[^）]*）",
        r"（待补充[^）]*）",
        r"（暂无[^）]*）",
    ]
    if any(re.search(pat, text) for pat in skeleton_patterns):
        return True
    content_shell_patterns = [
        r"解答基于教材第\d+章",
        r"核心特征分析。",
        r"考点解析。",
        r"常见错误辨析。",
        r"解题技巧。",
        r"分步解题流程。",
        r"关联知识体系。",
        r"相关概念的定义和物理意义。",
        r"相关数学推导过程。",
        r"在实际工程中的应用。",
        r"\n(### .+\n)+[^\n]{1,20}\n(###|##)",
    ]
    return any(re.search(pat, text) for pat in content_shell_patterns)


def extract_section(body, heading_prefix):
    """提取 ### 子节下的 body 文本"""
    pattern = re.escape(heading_prefix)
    idx = re.search(pattern, body)
    if not idx:
        return ""
    start = idx.end()
    next_match = re.search(r"\n#{1,3}\s+\d", body[start:])
    if next_match:
        return body[start : start + next_match.start()]
    return body[start:]


def section_has_real_content(body, heading_prefix):
    """判断某节是否有实质内容（不含Mermaid图、空行、纯标点）"""
    sec = extract_section(body, heading_prefix)
    sec = re.sub(r"```.*?```", "", sec, flags=re.DOTALL)
    sec = re.sub(r"\s+", "", sec)
    sec = re.sub(r"[，。、；：！？（）【】《》\u201c\u201d\u2018\u2019「」『』—…*#\n\r\t-]", "", sec)
    return len(sec) >= 10


def check_content_depth(body, node_type, name):
    """检查body内容深度，返回(FAIL字符串, WARN字符串)"""
    all_thresholds, all_sec_counts = _load_thresholds()
    thresholds = all_thresholds.get(node_type)
    sec_counts = all_sec_counts.get(node_type)
    if not thresholds or not sec_counts:
        return None, None

    sec_lines = re.findall(r"^#{3,4}\s+\d+\.\s+.+$", body, re.MULTILINE)
    effective_total = max(len(sec_lines), sec_counts["total_secs"])
    wu_count = 0
    non_empty = 0

    for sec_line in sec_lines:
        sec_text = sec_line.strip()
        sec_body = extract_section(body, sec_text[:60])
        sec_text_only = re.sub(r"```.*?```", "", sec_body, flags=re.DOTALL)
        stripped = re.sub(r"\s", "", sec_text_only)
        if stripped.strip() in ("无", "暂无", "无。", "暂无。", ""):
            wu_count += 1
        else:
            non_empty += 1

    wu_ratio = wu_count / effective_total if effective_total > 0 else 0

    fail, warn = None, None
    if wu_ratio > thresholds["max_wu_ratio"]:
        fail = f"\"无\"比例 {wu_ratio:.0%}>{thresholds['max_wu_ratio']:.0%}"
    min_nes = thresholds["min_nonempty_secs"]
    if non_empty < min_nes:
        if fail:
            fail += f"; 非空{non_empty}<{min_nes}"
        else:
            warn = f"非空节数{non_empty}/{min_nes}"
    body_len = len(re.sub(r"\s", "", body))
    min_bc = thresholds["min_body_chars"]
    if body_len < min_bc:
        wmsg = f"body字数{body_len}<{min_bc}"
        if warn:
            warn += "; " + wmsg
        else:
            warn = wmsg
    return fail, warn
