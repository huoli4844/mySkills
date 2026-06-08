#!/usr/bin/env python3.12
"""yaml_auto_fill.py — 模板驱动的 YAML 自动填充引擎

从模板 .md 文件中提取 {{field}} → 分类为机械/派生/LLM → 自动填充机械字段
→ LLM 字段输出结构化 prompt → 最终组装 YAML。

设计原则: Python 做一切能机械做的事，Agent 只做需要理解的事。

用法:
  python3.12 yaml_auto_fill.py analyze                       # 分析所有模板字段分类
  python3.12 yaml_auto_fill.py skeleton -w BOOK_DIR -c 1 -t kp  # 生成 KP 骨架
  python3.12 yaml_auto_fill.py fill -w BOOK_DIR -c 1 -t kp  # 机械填充 KP YAML
  python3.12 yaml_auto_fill.py llm-prompt -w BOOK_DIR -c 1 -t kp  # 生成 LLM 填充提示
"""

import argparse
import json
import os
import re
import sys
from typing import Any

import yaml

from dag_constants import DIR, BUILDER_CONFIG, PipelineError

_CONFIDENCE = {
    "concept": 0.95, "ke": 0.85, "entity": 0.85,
    "kp": 0.85, "sp": 0.75, "scene": 0.65,
    "exercise": 0.65, "solution": 0.85,
}

from log_utils import get_logger

log = get_logger(__name__)

# ── 模板字段分类 ───────────────────────────────────────────

# 元字段: Python 从上下文自动填
META_FIELDS = {
    "type", "type_tag", "name", "book_id", "book_name", "chapter_num",
    "confidence", "confidence_note", "source_chapter", "aliases", "tags",
    "entity_type", "classification", "domain", "scenario_type",
    "template_version",
}

# 源文自动提取: Python 能正则/规则提取
AUTO_EXTRACT_FIELDS = {
    "definition_sentence", "term_definition",
    "source_from",           # 从 TOC 定位 L{n}-{m}
}

# 派生字段: 可推算出
DERIVED_FIELDS = {
    "difficulty",              # bloom_level → ⭐ 映射
    "bloom_level_description",  # 从 bloom_level 生成
    "bloom_progression",       # 从 bloom_level 推演
    "bloom_alignment",        # 从 bloom_level 推演
}

# ── 需要 LLM 的字段: 必须理解源文才能写 ──
# 其余不在以上三类的全部归为 LLM 字段

# ── 模板解析 ────────────────────────────────────────────────


def parse_template(tpl_path: str) -> dict[str, dict[str, Any]]:
    """解析模板 .md 文件，提取所有 {{field}} 占位符及其元数据。

    返回 {field_name: {index, section, context}}
    """
    with open(tpl_path, encoding="utf-8") as f:
        content = f.read()

    fields = {}
    lines = content.split("\n")
    current_section = ""

    for i, line in enumerate(lines):
        # 追踪当前节标题
        sec_match = re.match(r"^#{2,4}\s+(.+)", line)
        if sec_match:
            current_section = sec_match.group(1).strip()

        # 提取 {{field}}
        for m in re.finditer(r"\{\{(\w+)\}\}", line):
            field = m.group(1)
            if field not in fields:
                fields[field] = {
                    "index": len(fields),
                    "line": i + 1,
                    "section": current_section,
                    "context": line.strip()[:80],
                }

    return fields


def classify_field(field: str) -> str:
    """分类字段: meta / auto / derived / llm"""
    if field in META_FIELDS:
        return "meta"
    if field in AUTO_EXTRACT_FIELDS:
        return "auto"
    if field in DERIVED_FIELDS:
        return "derived"
    # skip template-only fields (diagram placeholders)
    if field.endswith("_diagram"):
        return "diagram"
    return "llm"


def analyze_all_templates(tpl_dir: str) -> dict:
    """分析所有模板，输出字段分类报告"""
    import glob

    report = {}
    for tpl_path in sorted(glob.glob(os.path.join(tpl_dir, "*_template.md"))):
        name = os.path.basename(tpl_path).replace("_template.md", "")
        fields = parse_template(tpl_path)
        cats = {"meta": [], "auto": [], "derived": [], "llm": [], "diagram": []}
        for fname, finfo in fields.items():
            cat = classify_field(fname)
            cats[cat].append(f"{fname} (§{finfo['section']})")

        report[name] = {
            "file": os.path.basename(tpl_path),
            "total": len(fields),
            "meta": len(cats["meta"]),
            "auto": len(cats["auto"]),
            "derived": len(cats["derived"]),
            "llm": len(cats["llm"]),
            "llm_fields": cats["llm"],
            "meta_fields": cats["meta"],
            "auto_fields": cats["auto"],
        }
    return report


# ── 源文提取 ────────────────────────────────────────────────


def load_source_text(book_dir: str, ch: str) -> tuple[str, str, list[str]]:
    """加载章节源文。返回 (完整文本, 文件路径, 行列表)"""
    src_dir = os.path.join(book_dir, DIR["SOURCE"])
    for fname in sorted(os.listdir(src_dir)):
        m = re.match(rf"第{ch}章\s.*\.md$", fname)
        if m:
            fpath = os.path.join(src_dir, fname)
            with open(fpath, encoding="utf-8") as f:
                text = f.read()
            return text, fpath, text.split("\n")
    return "", "", []


def load_toc(book_dir: str, ch: str) -> dict:
    """加载 chapter_toc.json"""
    toc_path = os.path.join(book_dir, ".dag", f"第{ch}章", "chapter_toc.json")
    if os.path.exists(toc_path):
        with open(toc_path, encoding="utf-8") as f:
            return json.load(f)
    return {}


def extract_definition_sentence(
    text: str, max_search: int = 300
) -> str:
    """从文本前 max_search 字符中提取定义句(含标记词)"""
    head = text[:max_search]
    markers = ["是指", "称为", "即", "定义为", "指的是", "所谓", "又称"]
    sentences = re.split(r"[。；\n]", head)
    for sent in sentences:
        sent = sent.strip()
        if len(sent) < 5:
            continue
        if re.match(r"^#+\s", sent):
            continue
        for marker in markers:
            if marker in sent:
                # 清理 Markdown 格式
                clean = re.sub(r"\*\*", "", sent)
                return clean[:200]
    return ""


def extract_formulas(text: str) -> list[str]:
    """从源文中提取 LaTeX 公式"""
    formulas = []
    # $$ ... $$ 块
    for m in re.finditer(r"\$\$(.+?)\$\$", text, re.DOTALL):
        f = m.group(1).strip()[:100]
        if f and f not in formulas:
            formulas.append(f)
    # 行内 $...$ (但不匹配 $$)
    for m in re.finditer(r"(?<!\$)\$(?!\$)(.+?)(?<!\$)\$(?!\$)", text):
        f = m.group(1).strip()[:60]
        if f and len(f) > 2 and f not in formulas:
            formulas.append(f)
    return formulas[:10]


def extract_figures(text: str) -> list[str]:
    """从源文中提取图引用"""
    figs = re.findall(r"图\s*(\d+[-\.]?\d*)", text)
    return sorted(set(figs), key=lambda x: tuple(map(int, re.findall(r"\d+", x))))[:10]


def extract_tables(text: str) -> list[str]:
    """从源文中提取表引用"""
    tabs = re.findall(r"表\s*(\d+[-\.]?\d*)", text)
    return sorted(set(tabs))[:10]


def locate_in_source(lines: list[str], keyword: str) -> str:
    """在源文中定位关键词所在容器的行号范围。

    先精确匹配 keyword，失败则尝试 3-4 字子串匹配。
    跳过 YAML frontmatter (--- ... ---)。
    """
    # 找到正文起始行（跳过 frontmatter）
    body_start = 0
    in_frontmatter = False
    fm_count = 0
    for i, line in enumerate(lines):
        if line.strip() == "---":
            fm_count += 1
            if fm_count == 1:
                in_frontmatter = True
            elif fm_count >= 2:
                body_start = i + 1
                break
        elif fm_count == 0:
            body_start = i if line.strip() else i + 1
            if not line.strip():
                continue
            break

    # 只搜索正文部分
    body = lines[body_start:]

    # 1. 精确匹配
    for i, line in enumerate(body):
        if keyword in line:
            return _locate_range(body, i, offset=body_start)

    # 2. 尝试子串匹配
    for l in [4, 3, 2]:
        for j in range(0, len(keyword) - l + 1):
            sub = keyword[j:j + l]
            if len(sub) < 3:
                continue
            for i, line in enumerate(body):
                if sub in line:
                    return _locate_range(body, i, offset=body_start)

    return ""


def _locate_range(lines: list[str], match_line: int, offset: int = 0) -> str:
    """从匹配行定位容器范围"""
    # 向前找最近的 ##/### 标题
    start = match_line
    for j in range(match_line, -1, -1):
        if re.match(r"^#{2,4}\s", lines[j]):
            start = j
            break
    # 向后找下一个 ## 标题
    end = min(match_line + 100, len(lines))
    for j in range(match_line + 1, min(len(lines), match_line + 200)):
        if re.match(r"^#{2,3}\s", lines[j]):
            end = j
            break
    section_title = lines[start].strip().lstrip("#").strip()
    real_start = start + offset + 1
    real_end = end + offset
    return f"§{section_title} L{real_start}-{real_end}"


# ── 元字段填充 ──────────────────────────────────────────────


def fill_meta(item: dict, node_type: str, book_id: str, ch: str,
              book_name: str = "") -> dict:
    """填充元字段到 YAML item 的 fm/bd 中（同时写入两份以确保模板解析）"""
    fm = item.setdefault("fm", {})
    bd = item.setdefault("bd", {})

    cfg = BUILDER_CONFIG.get(node_type, {})
    confidence = _CONFIDENCE.get(node_type, 0.85)

    meta_defaults = {
        "source_chapter": ch,
        "confidence": confidence,
        "confidence_note": "auto-filled by yaml_auto_fill (python3.12)",
        "bloom_level": "理解→应用",
        "book_id": book_id,
        "book_name": book_name or "",
        "chapter_num": ch,
    }

    for key, val in meta_defaults.items():
        if key not in fm:
            fm[key] = val
        # 如果模板在 bd 中也有此字段，也填入
        if key in bd:
            bd[key] = val

    return item


def fill_derived(item: dict, node_type: str) -> dict:
    """填充派生字段"""
    bd = item.setdefault("bd", {})
    fm = item.get("fm", {})

    # 从 fm 或 bd 获取 bloom_level
    bl = str(fm.get("bloom_level", "") or bd.get("bloom_level", "") or "理解→应用")

    # difficulty 映射
    if bd.get("difficulty", "") in ("", "待补充", None):
        if "创造" in bl:
            bd["difficulty"] = "⭐⭐⭐ 高级"
        elif "分析" in bl or "评价" in bl:
            bd["difficulty"] = "⭐⭐ 中级"
        elif "应用" in bl:
            bd["difficulty"] = "⭐⭐ 中级"
        else:
            bd["difficulty"] = "⭐ 基础"

    # bloom_progression
    if bd.get("bloom_progression", "") in ("", "待补充", None):
        bd["bloom_progression"] = "无"

    return item


# ── 源文自动提取 ────────────────────────────────────────────


def fill_auto_extract(item: dict, source_text: str, source_lines: list[str],
                      keyword: str = "") -> dict:
    """从源文自动提取 definition_sentence, source_from, formulas, figures"""
    bd = item.setdefault("bd", {})
    fm = item.setdefault("fm", {})
    name = item.get("name", "")

    # definition_sentence
    if "definition_sentence" in bd:
        val = str(bd.get("definition_sentence", ""))
        if not val or val in ("无", "待补充"):
            ds = extract_definition_sentence(source_text)
            if ds:
                bd["definition_sentence"] = ds

    # term_definition
    if "term_definition" in bd:
        val = str(bd.get("term_definition", ""))
        if not val or val in ("无", "待补充"):
            ds = extract_definition_sentence(source_text)
            if ds:
                bd["term_definition"] = ds

    # source_from — 检查 fm 和 bd
    sf_fm = str(fm.get("source_from", ""))
    sf_bd = str(bd.get("source_from", ""))
    needs_source = (not sf_fm or sf_fm in ("无", "待补充", "")) and \
                   (not sf_bd or sf_bd in ("无", "待补充", ""))
    if needs_source:
        kw = keyword or name
        loc = locate_in_source(source_lines, kw)
        if loc:
            fm["source_from"] = loc
            bd["source_from"] = loc

    # bloom_level — 从 fm 复制到 bd (模板可能从 bd 读)
    if "bloom_level" in bd:
        val = str(bd.get("bloom_level", ""))
        if not val or val in ("待补充", ""):
            if fm.get("bloom_level"):
                bd["bloom_level"] = fm["bloom_level"]

    return item


# ── YAML 骨架生成 ──────────────────────────────────────────


def generate_skeleton(node_type: str, name: str, book_id: str, ch: str,
                      tpl_dir: str, book_name: str = "") -> dict:
    """为单个节点生成完整 YAML 骨架(所有字段预填"待补充")"""
    # 从模板解析所有字段
    type_to_tpl = {
        "concept": "concept_template.md",
        "ke": "ke_template.md",
        "entity": "entity_template.md",
        "kp": "knowledge_template.md",
        "sp": "skill_template.md",
        "scene": "scenario_template.md",
        "exercise": "exercise_template.md",
        "solution": "eval_template.md",
    }
    tpl_file = type_to_tpl.get(node_type)
    if not tpl_file:
        raise ValueError(f"Unknown node_type: {node_type}")

    tpl_path = os.path.join(tpl_dir, tpl_file)
    all_fields = parse_template(tpl_path)

    # 构建 fm + bd
    fm = {}
    bd = {}
    for fname in sorted(all_fields.keys()):
        cat = classify_field(fname)
        # 跳过 diagram 占位符(模板内使用不存 YAML)
        if cat == "diagram":
            continue

        if fname in META_FIELDS:
            # 元字段留空，fill_meta 会填
            continue
        elif fname in DERIVED_FIELDS:
            bd[fname] = "待补充"  # fill_derived 会填
        else:
            # 全放 bd(模板 assembler 会从 fm/bd 两个来源查找)
            bd[fname] = "待补充"

    item = {
        "name": name,
        "file": name,
        "fm": fm,
        "bd": bd,
    }

    # 填充元字段
    item = fill_meta(item, node_type, book_id, ch, book_name)
    item = fill_derived(item, node_type)

    return item


# ── 机械填充完整流程 ────────────────────────────────────────


def mechanical_fill(node_type: str, name: str, book_id: str, ch: str,
                    source_text: str, source_lines: list[str],
                    tpl_dir: str, book_name: str = "") -> dict:
    """完整的机械填充流程: 骨架 → 元字段 → 源文提取 → 派生"""
    item = generate_skeleton(node_type, name, book_id, ch, tpl_dir, book_name)
    item = fill_auto_extract(item, source_text, source_lines, keyword=name)
    # 再次填派生(可能依赖刚填的字段)
    item = fill_derived(item, node_type)
    return item


# ── LLM 提示生成 ────────────────────────────────────────────


def generate_llm_prompt(item: dict, node_type: str,
                        source_snippet: str,
                        tpl_dir: str = "") -> str:
    """为 LLM 生成结构化填充提示

    从模板文件中读取 HTML 注释（如 <!-- 每场景 ≥50 字... -->）作为每个字段的
    填充指引，附加到 LLM 提示中。
    """
    import re as _re

    bd = item.get("bd", {})
    # 找出所有"待补充"的值 → LLM 需要填
    to_fill = {k: v for k, v in bd.items() if v == "待补充"}

    if not to_fill:
        return "# 无需 LLM 填充(所有字段已机械填满)\n"

    # 从模板文件读取每个字段的 HTML 注释指引
    field_guides = {}
    if tpl_dir:
        tpl_name = f"{node_type}_template.md"
        tpl_path = os.path.join(tpl_dir, tpl_name)
        if os.path.exists(tpl_path):
            with open(tpl_path, encoding="utf-8") as _tf:
                _tpl_text = _tf.read()
            # 方案：直接在原始文本中，对每个 {{field}} 向前搜索最近的 HTML 注释
            for _m in _re.finditer(r"\{\{([a-z_][a-z0-9_]*)\}\}", _tpl_text):
                _fn = _m.group(1)
                _pos = _m.start()
                # 从 _pos 向前搜索 HTML 注释（最多向前看 300 个字符）
                _search_start = max(0, _pos - 300)
                _snippet = _tpl_text[_search_start:_pos]
                # 找到 snippet 中最后一个完整的 <!-- ... -->
                _cm = list(_re.finditer(r"<!--(.*?)-->", _snippet, _re.DOTALL))
                if _cm:
                    _last = _cm[-1]
                    # 注释在 snippet 中的位置 → 转回原始文本位置
                    _comment_end_in_orig = _search_start + _last.end()
                    # 注释和 {{field}} 之间不应有其他 {{}}
                    _between = _tpl_text[_comment_end_in_orig:_pos]
                    if "{{" not in _between:
                        _guide = _last.group(1).strip()
                        if len(_guide) > 10:
                            field_guides[_fn] = _guide

    lines = [
        f"# LLM 填充任务: {item['name']} ({node_type})",
        f"",
        f"## 源文上下文",
        f"```",
        source_snippet[:3000],
        f"```",
        f"",
        f"## 需要填充的字段 ({len(to_fill)} 个)",
        f"",
    ]
    for fname in sorted(to_fill.keys()):
        lines.append(f"### {fname}")
        lines.append(f"")
        # 如果模板中有该字段的 HTML 注释指引，附加上
        guide = field_guides.get(fname, "")
        if guide:
            lines.append(f"【模板指引】{guide}")
            lines.append(f"")
        lines.append(f'(请根据上方的源文上下文,为该字段填写高质量内容。如源文无相关材料,填"无")')
        lines.append(f"")

    lines.append("## 输出格式")
    lines.append("")
    lines.append("请以 YAML 格式输出，只包含需要填充的 bd 字段：")
    lines.append("```yaml")
    lines.append("bd:")
    for fname in sorted(to_fill.keys()):
        lines.append(f"  {fname}: <你的内容>")
    lines.append("```")

    return "\n".join(lines)


def get_source_snippet(source_lines: list[str], keyword: str,
                       context_lines: int = 100) -> str:
    """获取关键词附近的源文片段"""
    for i, line in enumerate(source_lines):
        if keyword in line:
            start = max(0, i - context_lines // 2)
            end = min(len(source_lines), i + context_lines // 2)
            return "\n".join(source_lines[start:end])
    # fallback: 返回前 context_lines 行
    return "\n".join(source_lines[:context_lines])


# ── CLI ─────────────────────────────────────────────────────


def cmd_analyze(args):
    """分析所有模板字段分类"""
    skill_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    tpl_dir = os.path.join(skill_dir, "assets", "templates")
    report = analyze_all_templates(tpl_dir)

    total_all = sum(r["total"] for r in report.values())
    total_meta = sum(r["meta"] for r in report.values())
    total_auto = sum(r["auto"] for r in report.values())
    total_derived = sum(r["derived"] for r in report.values())
    total_llm = sum(r["llm"] for r in report.values())
    auto_pct = (total_meta + total_auto + total_derived) / total_all * 100

    print(f"\n{'='*70}")
    print(f"  模板字段分类报告")
    print(f"{'='*70}")
    print(f"  机械可填 (meta+auto+derived): {total_meta + total_auto + total_derived}/{total_all} ({auto_pct:.0f}%)")
    print(f"  需要 LLM:                    {total_llm}/{total_all} ({100-auto_pct:.0f}%)")
    print(f"{'='*70}\n")

    for tname, tinfo in sorted(report.items()):
        mech = tinfo["meta"] + tinfo["auto"] + tinfo["derived"]
        print(f"  📄 {tname}: {mech}/{tinfo['total']} 机械可填 ({mech/tinfo['total']*100:.0f}%)")
        if tinfo["llm_fields"]:
            print(f"     LLM: {', '.join(tinfo['llm_fields'][:6])}")
            if len(tinfo["llm_fields"]) > 6:
                print(f"          ... +{len(tinfo['llm_fields'])-6} more")


def cmd_skeleton(args):
    """生成 YAML 骨架"""
    skill_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    tpl_dir = os.path.join(skill_dir, "assets", "templates")

    item = generate_skeleton(args.type, args.name, args.book_id,
                             args.chapter, tpl_dir, args.book_name or "")
    print(yaml.dump([item], allow_unicode=True, default_flow_style=False,
                    sort_keys=False, indent=2, width=120))


def cmd_fill(args):
    """机械填充"""
    skill_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    tpl_dir = os.path.join(skill_dir, "assets", "templates")
    book_dir = os.path.abspath(args.workspace)

    source_text, _, source_lines = load_source_text(book_dir, args.chapter)
    if not source_text:
        print(f"❌ 未找到第{args.chapter}章源文", file=sys.stderr)
        raise PipelineError(f"未找到第{args.chapter}章源文")

    # 从现有 YAML 读取名称列表(如果有的话)
    yaml_path = os.path.join(book_dir, ".dag", f"第{args.chapter}章", "data",
                             f"{args.type}s.yaml")
    names = []
    if os.path.exists(yaml_path) and not args.name:
        with open(yaml_path, encoding="utf-8") as f:
            existing = yaml.safe_load(f)
            if isinstance(existing, list):
                names = [item.get("name", "") for item in existing]

    if args.name:
        names = [args.name]

    if not names:
        print("❌ 未提供 name 参数且 YAML 中无条目", file=sys.stderr)
        raise PipelineError("未提供 name 参数且 YAML 中无条目")

    items = []
    for name in names:
        item = mechanical_fill(args.type, name, args.book_id, args.chapter,
                               source_text, source_lines, tpl_dir, args.book_name or "")
        items.append(item)

    # 输出或写入
    output = yaml.dump(items, allow_unicode=True, default_flow_style=False,
                       sort_keys=False, indent=2, width=120)

    if args.output:
        os.makedirs(os.path.dirname(args.output), exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"✅ 机械填充完成 → {args.output}")
    else:
        print(output)


def cmd_llm_prompt(args):
    """生成 LLM 填充提示"""
    skill_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    tpl_dir = os.path.join(skill_dir, "assets", "templates")
    book_dir = os.path.abspath(args.workspace)

    source_text, _, source_lines = load_source_text(book_dir, args.chapter)
    if not source_text:
        print(f"❌ 未找到第{args.chapter}章源文", file=sys.stderr)
        raise PipelineError(f"未找到第{args.chapter}章源文")

    # 先机械填充
    item = mechanical_fill(args.type, args.name, args.book_id, args.chapter,
                           source_text, source_lines, tpl_dir, args.book_name or "")

    # 生成 LLM 提示
    snippet = get_source_snippet(source_lines, args.name)
    prompt = generate_llm_prompt(item, args.type, snippet, tpl_dir=tpl_dir)
    print(prompt)


def cmd_validate_fix(args):
    """验证并自动修复 YAML：运行 yaml_pre_validate → 自动修复可修复项 → 重试最多 N 次"""
    import subprocess

    book_dir = os.path.abspath(args.workspace)
    skill_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    tpl_dir = os.path.join(skill_dir, "assets", "templates")
    validate_script = os.path.join(skill_dir, "scripts", "yaml_pre_validate.py")

    chapters = [args.chapter] if args.chapter else [str(c) for c in range(1, 9)]
    types = [args.type] if args.type else ["concept", "ke", "entity", "kp", "sp", "scene", "exercise", "solution"]

    total_fixed = 0
    for ch in chapters:
        data_dir = os.path.join(book_dir, ".dag", f"第{ch}章", "data")
        if not os.path.isdir(data_dir):
            continue

        for ntype in types:
            # map type name → yaml file
            type_to_file = {
                "concept": "concepts.yaml", "ke": "kes.yaml", "entity": "entities.yaml",
                "kp": "kps.yaml", "sp": "sps.yaml", "scene": "scenes.yaml",
                "exercise": "exercises.yaml", "solution": "solutions.yaml",
            }
            yf = type_to_file.get(ntype)
            if not yf:
                continue
            ypath = os.path.join(data_dir, yf)
            if not os.path.exists(ypath):
                continue

            for attempt in range(args.max_retries):
                # 运行 yaml_pre_validate
                result = subprocess.run(
                    [sys.executable, validate_script, ypath],
                    capture_output=True, text=True, timeout=30,
                )
                output = result.stdout + result.stderr

                # 提取错误
                errors = [l for l in output.split("\n") if "FAIL" in l or "ERROR" in l]
                if not errors:
                    break  # 全部通过

                # 自动修复
                auto_fixes = _auto_fix_yaml(ypath, ntype, errors)
                if auto_fixes == 0:
                    # 无法自动修复
                    if attempt == args.max_retries - 1:
                        print(f"  ⚠️ 第{ch}章 {ntype}: {len(errors)} 错误无法自动修复")
                        for e in errors[:3]:
                            print(f"     {e.strip()[:100]}")
                    break

                total_fixed += auto_fixes
                print(f"  第{ch}章 {ntype}: 第{attempt+1}次修复 +{auto_fixes}")

    if total_fixed:
        print(f"\n✅ 验证闭环完成: 自动修复 {total_fixed} 项")


def _auto_fix_yaml(ypath: str, ntype: str, errors: list[str]) -> int:
    """自动修复可修复的 YAML 错误。返回修复数量。"""
    fixed = 0
    with open(ypath, encoding="utf-8") as f:
        items = yaml.safe_load(f)

    if not isinstance(items, list):
        return 0

    for item in items:
        fm = item.get("fm", {})
        bd = item.get("bd", {})

        # 修复 1: bloom_level 值域修复
        bl = fm.get("bloom_level", "") or bd.get("bloom_level", "")
        if bl and bl not in ("知道→理解", "理解→应用", "应用→分析", "分析→评价", "评价→创造",
                              "知道", "理解", "应用", "分析", "评价", "创造",
                              "知道→理解→应用", "理解→应用→分析"):
            old_bl = bl
            if "创造" in str(bl):
                fm["bloom_level"] = "评价→创造"
            elif "评价" in str(bl):
                fm["bloom_level"] = "分析→评价"
            elif "分析" in str(bl):
                fm["bloom_level"] = "应用→分析"
            elif "应用" in str(bl):
                fm["bloom_level"] = "理解→应用"
            else:
                fm["bloom_level"] = "知道→理解"
            if "bloom_level" in bd:
                bd["bloom_level"] = fm["bloom_level"]
            print(f"    修复 bloom_level: {old_bl} → {fm['bloom_level']}")
            fixed += 1

        # 修复 2: confidence 值修复
        allowed_conf = {"concept": 0.95, "ke": 0.85, "entity": 0.85,
                        "kp": 0.85, "sp": 0.75, "scene": 0.65,
                        "exercise": 0.65, "solution": 0.85}
        conf = fm.get("confidence")
        if conf is not None and ntype in allowed_conf and conf != allowed_conf[ntype]:
            fm["confidence"] = allowed_conf[ntype]
            fixed += 1

        # 修复 3: 必填字段空值 → "无"
        from dag_constants import REQUIRED_BD_FIELDS
        required = REQUIRED_BD_FIELDS.get(ntype, [])
        for field in required:
            if field in bd and (bd[field] is None or str(bd[field]).strip() == ""):
                bd[field] = "无"
                fixed += 1

    if fixed:
        with open(ypath, "w", encoding="utf-8") as f:
            yaml.dump(items, f, allow_unicode=True, default_flow_style=False,
                      sort_keys=False, indent=2, width=120)

    return fixed


def main():
    parser = argparse.ArgumentParser(description="模板驱动的 YAML 自动填充引擎")
    sub = parser.add_subparsers(dest="cmd")

    # analyze
    sub.add_parser("analyze", help="分析所有模板字段分类")

    # skeleton
    p_sk = sub.add_parser("skeleton", help="生成 YAML 骨架")
    p_sk.add_argument("-t", "--type", required=True, choices=["concept", "ke", "entity", "kp", "sp", "scene", "exercise", "solution"])
    p_sk.add_argument("-n", "--name", required=True)
    p_sk.add_argument("--book-id", default="0001")
    p_sk.add_argument("-c", "--chapter", required=True)
    p_sk.add_argument("--book-name", default="")

    # fill
    p_fill = sub.add_parser("fill", help="机械填充 YAML")
    p_fill.add_argument("-w", "--workspace", required=True)
    p_fill.add_argument("-t", "--type", required=True)
    p_fill.add_argument("-n", "--name", default="")
    p_fill.add_argument("--book-id", default="0001")
    p_fill.add_argument("-c", "--chapter", required=True)
    p_fill.add_argument("--book-name", default="")
    p_fill.add_argument("-o", "--output", default="")

    # llm-prompt
    p_lp = sub.add_parser("llm-prompt", help="生成 LLM 填充提示")
    p_lp.add_argument("-w", "--workspace", required=True)
    p_lp.add_argument("-t", "--type", required=True)
    p_lp.add_argument("-n", "--name", required=True)
    p_lp.add_argument("--book-id", default="0001")
    p_lp.add_argument("-c", "--chapter", required=True)
    p_lp.add_argument("--book-name", default="")

    # validate-fix
    p_vf = sub.add_parser("validate-fix", help="验证并自动修复 YAML")
    p_vf.add_argument("-w", "--workspace", required=True)
    p_vf.add_argument("-t", "--type", default="")
    p_vf.add_argument("-c", "--chapter", default="")
    p_vf.add_argument("--book-id", default="0001")
    p_vf.add_argument("--book-name", default="")
    p_vf.add_argument("--max-retries", type=int, default=3)

    args = parser.parse_args()
    if args.cmd == "analyze":
        cmd_analyze(args)
    elif args.cmd == "skeleton":
        cmd_skeleton(args)
    elif args.cmd == "fill":
        cmd_fill(args)
    elif args.cmd == "llm-prompt":
        cmd_llm_prompt(args)
    elif args.cmd == "validate-fix":
        cmd_validate_fix(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
