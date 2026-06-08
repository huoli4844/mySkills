"""yaml_signals.py — 信号词匹配 + 源文分段 + 字段工作台

从源文自动提取信号词，匹配到各字段的必填内容。
供 yaml_writer.py 的 self-instruct 命令使用。
"""

from __future__ import annotations

import os
import re as _re
from typing import Any


# ── 语言层信号词（通用中文技术写作模式，领域无关）──
_LANG_SIGNALS: dict[str, list[str]] = {
    "definition": ["是指", "指的是", "指", "称为", "叫做", "定义为", "就是", "即", "意味着", "指的是"],
    "formula": ["公式", "表达式", "关系式", "为", "等于", "由...决定", "可表示为"],
    "structure": ["由...组成", "包含", "分为", "包括", "构成", "由...构成"],
    "number": ["值", "参数", "量", "系数", "率", "比", "度", "范围", "大小"],
    "negation": ["不能", "不要", "误区", "错误的", "注意不要", "切忌", "并非"],
    "cause_effect": ["导致", "由于", "因为", "所以", "因此", "从而", "引起", "影响", "使"],
    "evolution": ["演变", "发展", "改进", "优化", "趋势", "从...到"],
    "example": ["例如", "比如", "如", "示例", "案例", "情况下", "场景"],
    "application": ["用于", "应用", "使用", "利用", "适用", "适合", "可"],
}


def _parse_source_sections(raw_text: str) -> dict[str, str]:
    """将源文按 ##/### 标题分段"""
    sections = {}
    current_heading = "前言/概述"
    current_lines = []
    for line in raw_text.split("\n"):
        stripped = line.strip()
        if stripped.startswith("##"):
            if current_lines:
                sections[current_heading] = "\n".join(current_lines)
            current_heading = stripped.lstrip("#").strip()
            current_lines = []
        else:
            current_lines.append(stripped)
    if current_lines:
        sections[current_heading] = "\n".join(current_lines)
    return sections


def _extract_formulas(raw_text: str) -> list[tuple[int, str]]:
    """提取源文中的 $$..$$ 公式"""
    formulas = []
    for i, line in enumerate(raw_text.split("\n"), 1):
        if "$$" in line:
            formulas.append((i, line.strip()))
        m = _re.findall(r"\$\$(.*?)\$\$", line)
        for fm in m:
            formulas.append((i, fm.strip()))
    return formulas


def _extract_domain_signals(source_sections: dict[str, str]) -> dict[str, list[str]]:
    """从源文自动提取领域信号词（运行时零配置）"""
    signals: dict[str, list[str]] = {"unit": [], "technical": [], "application": []}
    all_text = "\n".join(source_sections.values())

    # 单位词
    unit_matches = _re.findall(r"\d+\s*([a-zA-Z/°μΩρτφλπδβεκηωσ±×·]+)", all_text)
    signals["unit"] = sorted(set(u.strip() for u in unit_matches if len(u.strip()) > 1))[:30]

    # 节标题术语
    for heading in source_sections:
        words = _re.findall(r"[\u4e00-\u9fff]{4,}", heading)
        for w in words:
            if w not in ("本章介绍", "本章内容", "本章小结", "本章重点"):
                if len(w) >= 4:
                    signals["application"].append(w)

    # 高频技术词
    freq: dict[str, int] = {}
    for match in _re.findall(r"[\u4e00-\u9fff]{3,8}", all_text):
        freq[match] = freq.get(match, 0) + 1
    stop_words = {"因此", "可以", "所以", "由于", "其中", "通常", "一般", "如果", "对于", "这样", "之间", "以上", "以下", "如下", "如图", "表中", "式中", "所示", "可知", "不是", "具有", "成为", "称为", "具有", "这就是", "根据", "通过", "表示", "以及", "那么", "就是", "这个", "一个", "一种", "这些"}
    signals["technical"] = sorted([w for w, c in freq.items() if c > 3 and w not in stop_words])[:50]

    return signals


def _get_prompt_query(prompt_text: str) -> list[str]:
    """从 @prompt 提取关键词"""
    if not prompt_text:
        return []
    stop = {"的", "了", "在", "是", "和", "或", "与", "用", "以", "对", "为", "从", "到", "等", "都", "要", "可", "中", "将", "", "通过", "进行", "包括", "使用", "需要", "提供", "描述"}
    keywords = [w for w in _re.findall(r"[\u4e00-\u9fff]{2,}", prompt_text) if w not in stop]
    return keywords[:10]


def _split_sentences(text: str) -> list[str]:
    """将文本按句号分段"""
    return [s.strip() for s in _re.split(r"[。！？；\n]", text) if len(s.strip()) > 5]


def _score_sentence(sentence: str, keywords: list[str], bd_name: str,
                    prompt_text: str, signals: dict[str, list[str]]) -> float:
    """给一句话打分（匹配信号词强度）"""
    score = 0.0
    # 关键词匹配
    for kw in keywords:
        if kw in sentence:
            score += 1.5
    # 语言层信号词
    for sig_type, sigs in _LANG_SIGNALS.items():
        for s in sigs:
            if s in sentence:
                score += 1.0
                break
    # 领域信号词
    for sig_type, sigs in signals.items():
        for s in sigs[:20]:
            if s in sentence:
                score += 0.5
                break
    # 数字密度加分
    num_count = len(_re.findall(r'\d+', sentence))
    score += num_count * 0.3
    # 长度惩罚（太短或太长）
    if len(sentence) < 10:
        score -= 2.0
    if len(sentence) > 200:
        score -= 1.0
    return score


def _match_field_to_source(bd_name: str, section_title: str,
                            source_sections: dict[str, str],
                            prompt_text: str,
                            domain_signals: dict[str, list[str]]) -> list[str]:
    """将字段匹配到源文最相关的段落"""
    if not source_sections:
        return []

    keywords = _get_prompt_query(prompt_text)
    # 从字段名提取关键词
    field_kw = _re.findall(r"[\u4e00-\u9fff]{2,}", bd_name)
    keywords.extend(f for f in field_kw if f not in keywords)

    scored = []
    for heading, content in source_sections.items():
        # 节标题匹配加分
        heading_score = 1.5 if section_title and section_title in heading else 0
        # 节内容每句话评分
        for sentence in _split_sentences(content):
            s = _score_sentence(sentence, keywords, bd_name, prompt_text, domain_signals)
            if heading_score > 0:
                s += heading_score
            if len(sentence) >= 20:
                scored.append((s, sentence))

    scored.sort(key=lambda x: -x[0])
    # 取Top3去重，最少10字
    seen = set()
    results = []
    for _, sen in scored:
        short = sen[:60].strip()
        if short not in seen and len(sen) >= 10:
            seen.add(short)
            results.append(sen.strip()[:200])
            if len(results) >= 3:
                break
    return results


def _find_section_title(tpl_content: str, field_name: str) -> str:
    """从模板内容查找字段对应的节标题"""
    # 模式: ### 节标题\n...{{field_name}}...
    pattern = r"(#{2,3}\s+.+?)\n.*?\{\{" + _re.escape(field_name) + r"\}\}"
    m = _re.search(pattern, tpl_content, _re.DOTALL)
    if m:
        return m.group(1).strip()
    return "(未知节)"


def _output_dir(type_name: str) -> str:
    """类型→输出目录"""
    dir_map = {
        "concept": "30_核心概念", "ke": "40_知识要素", "entity": "80_实体",
        "kp": "50_知识点", "sp": "60_技能点", "scene": "70_应用场景",
        "exercise": "90_习题", "solution": "90_习题/解答",
    }
    return dir_map.get(type_name, "?")


def _load_source_section(book_dir: str, chapter_num: str) -> str:
    """加载源文第N章"""
    src_dir = os.path.join(book_dir, "20_正文")
    if not os.path.isdir(src_dir):
        return ""
    files = sorted(f for f in os.listdir(src_dir) if f.startswith(f"第{chapter_num}章"))
    if not files:
        return ""
    with open(os.path.join(src_dir, files[0]), encoding="utf-8") as f:
        return f.read()
