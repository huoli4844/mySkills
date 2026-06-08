#!/usr/bin/env python3
"""
index-assembler.py — L2/L3/L4 索引文件生成器

从模板 + 已有节点列表生成索引文件：
- L2: concept_index, knowledge_index, skill_index, scenario_index, book_overview
- L3: concept_index, knowledge_index, skill_index, scenario_index, domain_overview
- L4: concept_index, knowledge_index, skill_index, scenario_index, kb_overview

v45.1-todo: 755行, 建议拆分为:
  - index_assembler.py(公共入口+CLI, ~200行)
  - index_builders.py(L2/L3/L4 各自构建逻辑, ~555行)

用法:
  python3 index-assembler.py <index.json>

JSON格式:
{
  "index_type": "concept_index | knowledge_index | skill_index | scenario_index | book_overview | domain_overview | kb_overview",
  "output_dir": "/path/to/output",
  "book_id": "01_示例书籍",
  "book_name": "01_示例书籍",
  "chapter_num": "1",
  "domain_id": "01_示例领域",
  "domain_name": "示例领域",
  "kb_id": "my-kb",
  "name": "索引名称",
  "items": [
    { "name": "概念名", "wikilink": "[[30_核心概念/传导耦合|传导耦合]]", ... 节点特有字段 }
  ],
  "stats": {
    "concept_count": 14,
    "knowledge_count": 7,
    ...
  }
}
"""

import json
import os
import re
import sys
from datetime import datetime

from dag_constants import PipelineError
from log_utils import get_logger

log = get_logger(__name__)


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_ROOT = os.path.normpath(os.path.join(SCRIPT_DIR, ".."))
TEMPLATE_DIR = os.path.join(SKILL_ROOT, "assets", "templates")

# === 辅助函数 ===


def load_template(template_name):
    path = os.path.join(TEMPLATE_DIR, template_name)
    if not os.path.exists(path):
        log.error(f"  ❌ 模板不存在: {path}")
        return None
    with open(path, encoding="utf-8") as f:
        return f.read()


def fill_template(template_text, replacements):
    """替换 {{key}} 占位符（先去除模板自带的 frontmatter，因为所有调用者都自己生成 frontmatter）"""
    # 去除模板自带的 frontmatter（---...--- 段）
    body = re.sub(r"^---\s*\n.*?\n---\s*\n", "", template_text, count=1, flags=re.DOTALL)
    for key, value in replacements.items():
        body = body.replace("{{" + key + "}}", str(value))
    return body


def build_fm_line(key, value):
    """构建 YAML front matter 一行"""
    if isinstance(value, list):
        return f"{key}: {json.dumps(value, ensure_ascii=False)}"
    elif isinstance(value, bool):
        return f"{key}: {'true' if value else 'false'}"
    elif isinstance(value, int | float):
        return f"{key}: {value}"
    else:
        return f"{key}: {value!s}"


# === 索引生成函数 ===


def build_concept_index(data):
    """生成概念索引（兼容L2/L3/L4）"""
    template = load_template("concept_index.md")
    if not template:
        return ""

    title = data.get("name", "概念索引")
    items = data.get("items", [])
    _stats = data.get("stats", {})

    # Build wikilink rows (按拓扑重要性排序)
    rows = []
    # 如果有 degree 字段，按 degree 降序；否则保持原序
    items_with_degree = [item for item in items if item.get("degree") is not None]
    items_without = [item for item in items if item.get("degree") is None]
    items_with_degree.sort(key=lambda x: x["degree"], reverse=True)
    sorted_items = items_with_degree + items_without

    for i, item in enumerate(sorted_items, 1):
        name = item.get("name", f"item_{i}")
        link = item.get("wikilink", f"[[30_核心概念/{name}|{name}]]")
        degree = item.get("degree", "")
        downstream = item.get("downstream_count", "")
        upstream = item.get("upstream_count", "")
        topo_col = f"度{degree}/下{downstream}/上{upstream}" if degree else ""
        rows.append(f"| {i} | {name} | {link} | {topo_col} |")
    by_chapter = "\n".join(rows) if rows else "暂无概念"

    front_matter = {
        "template_version": "v3.0",
        "type": "concept_index",
        "type_tags": ["索引", "概念"],
        "name": title,
        "book_id": data.get("book_id", ""),
        "book_name": data.get("book_name", ""),
        "chapter_num": data.get("chapter_num", ""),
        "source_chapter": f"第{data.get('chapter_num', '?')}章",
        "reviewer": "系统自动",
        "review_date": datetime.now().strftime("%Y-%m-%d"),
        "total_count": len(items),
        "aliases": data.get("aliases", []),
        "tags": data.get("tags", ["knowledge-base", "index"]),
        "cssclass": "knowledge-base",
    }

    fm_text = "---\n" + "\n".join(build_fm_line(k, v) for k, v in front_matter.items()) + "\n---\n"

    body = fill_template(
        template,
        {
            "concepts_concept": by_chapter,
            "concepts_principle": "（暂无）",
            "concepts_model": "（暂无）",
            "concepts_formula": "（暂无）",
            "concepts_algorithm": "（暂无）",
            "concepts_method": "（暂无）",
            "concepts_parameter": "（暂无）",
            "concepts_metric": "（暂无）",
            "concepts_rule": "（暂无）",
            "concepts_equipment": "（暂无）",
            "concepts_standard": "（暂无）",
            "concepts_tool": "（暂无）",
            "by_chapter": f"## 第{data.get('chapter_num', '?')}章\n{by_chapter}",
            "total_count": str(len(items)),
            "type_distribution": f"概念: {len(items)}" if items else "无",
        },
    )

    return fm_text + body


def build_knowledge_index(data):
    """生成知识点索引（Bloom 层级 + 图驱动排序）"""
    template = load_template("knowledge_index.md")
    if not template:
        return ""

    items = data.get("items", [])
    # 按拓扑重要性排序
    items_with_degree = [item for item in items if item.get("degree") is not None]
    items_without = [item for item in items if item.get("degree") is None]
    items_with_degree.sort(key=lambda x: x["degree"], reverse=True)
    sorted_items = items_with_degree + items_without

    # 全量列表（按章节）
    rows = []
    for i, item in enumerate(sorted_items, 1):
        name = item.get("name", f"item_{i}")
        link = item.get("wikilink", f"[[40_知识点/{name}|{name}]]")
        upstream = item.get("upstream_count", "")
        downstream = item.get("downstream_count", "")
        topo_col = f"上游KE{upstream}/下游SP{downstream}" if (upstream or downstream) else ""
        rows.append(f"| {i} | {name} | {link} | {topo_col} |")
    by_chapter = "\n".join(rows) if rows else "暂无知识点"

    # ── 按 Bloom 层级过滤（v36.0）──
    _bloom_order = {"记忆": 0, "理解": 1, "应用": 2, "分析": 3, "评价": 4, "创造": 5}
    bloom_emoji = {"记忆": "📖", "理解": "📝", "应用": "🔧", "分析": "🔍", "评价": "⭐", "创造": "💡"}

    def _filter_by_bloom(bl_level):
        """按 Bloom 层级过滤并生成 wikilink 列表"""
        matched = [item for item in sorted_items if item.get("bloom_level", "") == bl_level]
        if not matched:
            return "（无）"
        lines = []
        for item in matched:
            name = item.get("name", "?")
            link = item.get("wikilink", f"[[40_知识点/{name}|{name}]]")
            diff = item.get("difficulty", "")
            diff_tag = f"（{diff}）" if diff else ""
            deg = item.get("degree", "")
            deg_tag = f" 度={deg}" if deg else ""
            lines.append(f"- {link} {diff_tag}{deg_tag}")
        return "\n".join(lines)

    knowledge_remember = _filter_by_bloom("记忆")
    knowledge_understand = _filter_by_bloom("理解")
    knowledge_apply = _filter_by_bloom("应用")
    knowledge_analyze = _filter_by_bloom("分析")

    # ── 按难度过滤 ──
    def _filter_by_difficulty(diff_level):
        matched = [item for item in sorted_items if item.get("difficulty", "") == diff_level]
        if not matched:
            return "（无）"
        lines = []
        for item in matched:
            name = item.get("name", "?")
            link = item.get("wikilink", f"[[40_知识点/{name}|{name}]]")
            bl = item.get("bloom_level", "")
            bl_tag = f"（{bl}）" if bl else ""
            lines.append(f"- {link} {bl_tag}")
        return "\n".join(lines)

    knowledge_easy = _filter_by_difficulty("易")
    knowledge_medium = _filter_by_difficulty("中")
    knowledge_hard = _filter_by_difficulty("难")

    # ── Bloom 分布统计 ──
    bloom_counts = {"记忆": 0, "理解": 0, "应用": 0, "分析": 0, "评价": 0, "创造": 0}
    total_bloom = 0
    for item in sorted_items:
        bl = item.get("bloom_level", "")
        if bl in bloom_counts:
            bloom_counts[bl] += 1
            total_bloom += 1
    bloom_dist_parts = []
    for bl in ["记忆", "理解", "应用", "分析", "评价", "创造"]:
        cnt = bloom_counts[bl]
        if cnt > 0:
            bloom_dist_parts.append(f"{bloom_emoji.get(bl, '')}{bl}{cnt}")
    bloom_dist = (
        f"知识点: {len(items)} | Bloom 分布: {' | '.join(bloom_dist_parts)}"
        if bloom_dist_parts
        else f"知识点: {len(items)}"
    )

    front_matter = {
        "template_version": "v3.0",
        "type": "knowledge_index",
        "type_tags": ["索引", "知识点"],
        "name": data.get("name", "知识点索引"),
        "book_id": data.get("book_id", ""),
        "book_name": data.get("book_name", ""),
        "chapter_num": data.get("chapter_num", ""),
        "reviewer": "系统自动",
        "review_date": datetime.now().strftime("%Y-%m-%d"),
        "total_count": len(items),
        "aliases": data.get("aliases", []),
        "tags": data.get("tags", ["knowledge-base", "index"]),
        "cssclass": "knowledge-base",
    }

    fm_text = "---\n" + "\n".join(build_fm_line(k, v) for k, v in front_matter.items()) + "\n---\n"

    body = fill_template(
        template,
        {
            "knowledge_remember": knowledge_remember,
            "knowledge_understand": knowledge_understand,
            "knowledge_apply": knowledge_apply,
            "knowledge_analyze": knowledge_analyze,
            "knowledge_easy": knowledge_easy,
            "knowledge_medium": knowledge_medium,
            "knowledge_hard": knowledge_hard,
            "by_chapter": f"## 第{data.get('chapter_num', '?')}章\n{by_chapter}",
            "total_count": str(len(items)),
            "bloom_distribution": bloom_dist,
        },
    )

    return fm_text + body


def build_skill_index(data):
    """生成技能点索引（图驱动排序）"""
    template = load_template("skill_index.md")
    if not template:
        return ""

    items = data.get("items", [])
    items_with_degree = [item for item in items if item.get("degree") is not None]
    items_without = [item for item in items if item.get("degree") is None]
    items_with_degree.sort(key=lambda x: x["degree"], reverse=True)
    sorted_items = items_with_degree + items_without

    rows = []
    for i, item in enumerate(sorted_items, 1):
        name = item.get("name", f"item_{i}")
        link = item.get("wikilink", f"[[50_技能点/{name}|{name}]]")
        downstream = item.get("downstream_count", "")
        topo_col = f"支撑Scene数: {downstream}" if downstream else ""
        rows.append(f"| {i} | {name} | {link} | {topo_col} |")
    by_chapter = "\n".join(rows) if rows else "暂无技能点"

    front_matter = {
        "template_version": "v3.0",
        "type": "skill_index",
        "type_tags": ["索引", "技能点"],
        "name": data.get("name", "技能点索引"),
        "book_id": data.get("book_id", ""),
        "book_name": data.get("book_name", ""),
        "chapter_num": data.get("chapter_num", ""),
        "reviewer": "系统自动",
        "review_date": datetime.now().strftime("%Y-%m-%d"),
        "total_count": len(items),
        "aliases": data.get("aliases", []),
        "tags": data.get("tags", ["knowledge-base", "index"]),
        "cssclass": "knowledge-base",
    }

    fm_text = "---\n" + "\n".join(build_fm_line(k, v) for k, v in front_matter.items()) + "\n---\n"

    body = fill_template(
        template,
        {
            "skills_l1": by_chapter,
            "skills_l2": "（暂无）",
            "skills_easy": "（暂无）",
            "skills_medium": "（暂无）",
            "skills_hard": "（暂无）",
            "by_chapter": f"## 第{data.get('chapter_num', '?')}章\n{by_chapter}",
            "total_count": str(len(items)),
            "level_distribution": f"技能点: {len(items)}" if items else "无",
        },
    )

    return fm_text + body


def build_scenario_index(data):
    """生成场景索引"""
    template = load_template("scenario_index.md")
    if not template:
        return ""

    items = data.get("items", [])
    rows = []
    for i, item in enumerate(items, 1):
        name = item.get("name", f"item_{i}")
        link = item.get("wikilink", f"[[60_应用场景/{name}|{name}]]")
        rows.append(f"| {i} | {name} | {link} |")
    by_chapter = "\n".join(rows) if rows else "暂无场景"

    front_matter = {
        "template_version": "v3.0",
        "type": "scenario_index",
        "type_tags": ["索引", "场景"],
        "name": data.get("name", "场景索引"),
        "book_id": data.get("book_id", ""),
        "book_name": data.get("book_name", ""),
        "chapter_num": data.get("chapter_num", ""),
        "reviewer": "系统自动",
        "review_date": datetime.now().strftime("%Y-%m-%d"),
        "total_count": len(items),
        "aliases": data.get("aliases", []),
        "tags": data.get("tags", ["knowledge-base", "index"]),
        "cssclass": "knowledge-base",
    }

    fm_text = "---\n" + "\n".join(build_fm_line(k, v) for k, v in front_matter.items()) + "\n---\n"

    body = fill_template(
        template,
        {
            "scenarios_l1": by_chapter,
            "scenarios_l2": "（暂无）",
            "scenarios_easy": "（暂无）",
            "scenarios_medium": "（暂无）",
            "scenarios_hard": "（暂无）",
            "by_chapter": f"## 第{data.get('chapter_num', '?')}章\n{by_chapter}",
            "total_count": str(len(items)),
            "level_distribution": f"场景: {len(items)}" if items else "无",
        },
    )

    return fm_text + body


def build_book_overview(data):
    """生成L2书籍总揽"""
    template = load_template("book_overview.md")
    if not template:
        return ""

    front_matter = {
        "template_version": "v3.0",
        "type": "book_overview",
        "overview_level": "L2",
        "name": data.get("name", "资料总揽"),
        "book_id": data.get("book_id", ""),
        "book_name": data.get("book_name", ""),
        "chapter_num": data.get("chapter_num", ""),
        "domain": data.get("domain", ""),
        "reviewer": "系统自动",
        "review_date": datetime.now().strftime("%Y-%m-%d"),
    }

    fm_text = "---\n" + "\n".join(build_fm_line(k, v) for k, v in front_matter.items()) + "\n---\n"

    # v43.15: 自动生成简介（从章节目录和章节分布构建）
    stats = data.get("stats", {})
    c_count = stats.get("concept_count", 0)
    k_count = stats.get("knowledge_count", 0)
    s_count = stats.get("skill_count", 0)
    sc_count = stats.get("scenario_count", 0)
    e_count = stats.get("entity_count", 0)
    total = c_count + k_count + s_count + sc_count + e_count
    book_name = data.get("book_name", "") or data.get("name", "")

    # 尝试从 chapter_toc 或文件系统获取章节标题
    ch_titles = {}
    src_dir = data.get("_src_dir", "")
    if not src_dir:
        # 从 output_dir 反推
        od = data.get("output_dir", "")
        src_dir = os.path.join(os.path.dirname(od), "20_正文")
    if os.path.isdir(src_dir):
        for f in sorted(os.listdir(src_dir)):
            if f.startswith("第") and f.endswith(".md"):
                # 提取 "第N章 标题" → (N, "标题")
                import re as _re
                m = _re.match(r"第(\d+)章\s+(.+)\.md", f)
                if m:
                    ch_titles[int(m.group(1))] = m.group(2)

    # 构建章节目录描述
    ch_desc_parts = []
    if ch_titles:
        for ch_num in sorted(ch_titles.keys()):
            ch_desc_parts.append(f"第{ch_num}章「{ch_titles[ch_num]}」")
    ch_desc = "、".join(ch_desc_parts) if ch_desc_parts else "涵盖核心理论到工程应用"

    description = data.get("description") or ""
    if not description or description in ("（待补充）", ""):
        top = data.get("top_nodes", "")
        top_concepts = []
        if top:
            for line in top.split("\n"):
                parts = line.split("|")
                if len(parts) >= 4 and "concept" in parts[3]:
                    top_concepts.append(parts[2].strip())


        # 按章获取概念摘要（用于生成详细描述）
        ch_summary = {}
        if top:
            for line in top.split("\n"):
                parts = line.split("|")
                if len(parts) >= 4 and "concept" in parts[3]:
                    name = parts[2].strip()
                    ch_summary[name] = ch_summary.get(name, True)

        # 从章节分布表提取各章概念数
        ch_concept_map = {}
        if ch_dist_text := data.get("chapter_distribution", ""):
            for line in ch_dist_text.split("\n"):
                p = [x.strip() for x in line.split("|")]
                if len(p) >= 3 and p[1].startswith("第"):
                    try:
                        ch_concept_map[p[1]] = int(p[2]) if p[2].isdigit() else 0
                    except Exception as e:
                        log.debug(f"概念计数解析失败: {e}")
                        pass

        # ── 生成书籍描述（从 config/book_info.yaml 加载，无文件时自动降级）──
        description = _build_book_description(
            book_name=book_name,
            ch_titles=ch_titles,
            ch_desc=ch_desc,
            total=total, c_count=c_count, e_count=e_count,
            k_count=k_count, s_count=s_count, sc_count=sc_count,
            wiki_root=os.path.dirname(od) if isinstance(od, str) else ".",
        )

    body = fill_template(
        template,
        {
            "name": data.get("name", "资料总揽"),
            "description": description,
            "chain_connectivity": data.get("chain_connectivity", "（图谱未构建）"),
            "node_connectivity": data.get("node_connectivity", ""),
            "graph_quality": data.get("graph_quality", ""),
            "top_nodes": data.get("top_nodes", ""),
            "mindmap_content": data.get("mindmap_content", ""),
            "chapter_distribution": data.get("chapter_distribution", ""),
            "learning_path": data.get("learning_path", "（待补充）"),
            "learning_path_v2": data.get("learning_path_v2", "（待补充）"),
            "todo_items": data.get("todo_items", "（无待修复项）"),
            "concept_index": data.get("concept_index", "（待补充）"),
            "knowledge_index": data.get("knowledge_index", "（待补充）"),
            "skill_index": data.get("skill_index", "（待补充）"),
            "scenario_index": data.get("scenario_index", "（待补充）"),
            "concept_count": str(c_count),
            "knowledge_count": str(k_count),
            "skill_count": str(s_count),
            "scenario_count": str(sc_count),
            "entity_count": str(e_count),
            "exercise_count": str(data.get("stats", {}).get("exercise_count", 0)),
            "review_date": datetime.now().strftime("%Y-%m-%d"),
        },
    )

    # v43.15: 后处理 — 空 mermaid 块替换为占位文本，避免 Obsidian 渲染错误
    mindmap = (data.get("mindmap_content") or "").strip()
    if not mindmap:
        body = body.replace("```mermaid\n\n```", "（暂无知识图谱全景数据）")

    return fm_text + body


def build_domain_overview(data):
    """生成L3领域总揽"""
    template = load_template("domain_overview.md")
    if not template:
        return ""

    front_matter = {
        "template_version": "v3.0",
        "type": "domain_overview",
        "overview_level": "L3",
        "name": data.get("name", "领域总揽"),
        "domain_id": data.get("domain_id", ""),
        "reviewer": "系统自动",
        "review_date": datetime.now().strftime("%Y-%m-%d"),
        "aliases": data.get("aliases", []),
        "tags": data.get("tags", ["knowledge-base", "domain"]),
        "cssclass": "knowledge-base",
    }

    fm_text = "---\n" + "\n".join(build_fm_line(k, v) for k, v in front_matter.items()) + "\n---\n"

    s = data.get("stats", {})
    # 图谱数据
    kg = data.get("kg_stats", {})
    kg_section = ""
    if kg:
        kg_section = (
            f"\n### 图感知统计\n\n"
            f"| 指标 | 数值 |\n"
            f"|:-----|:-----|\n"
            f"| 总节点数 | {kg.get('total', '?')} |\n"
            f"| 平均关联边数 | {kg.get('avg_edges', '?')} |\n"
            f"| 孤立节点（无入边） | {kg.get('orphans', '?')} |\n"
        )
        bd = kg.get("by_chapter", {})
        if bd:
            kg_section += "\n按章节分布：" + " | ".join(f"第{ch}章({c})" for ch, c in sorted(bd.items())) + "\n"
        cd = kg.get("confidence_dist", {})
        if cd:
            kg_section += "\n置信度分布：" + " | ".join(f"{k}({c})" for k, c in sorted(cd.items())) + "\n"
    graph_sec = data.get("graph_section", "")
    if isinstance(graph_sec, dict):
        graph_sec = json.dumps(graph_sec, ensure_ascii=False, indent=2)
    if isinstance(kg_section, dict):
        kg_section = json.dumps(kg_section, ensure_ascii=False, indent=2)
    graph_content = kg_section + graph_sec if (kg_section or graph_sec) else "（待补充）"

    body = fill_template(
        template,
        {
            "description": data.get("description", "（待补充）"),
            "book_index": data.get("book_index", "（待补充）"),
            "mindmap_content": data.get("mindmap_content", ""),
            "graph_section": graph_content,
            "learning_path": data.get("learning_path", "（待补充）"),
            "combined_skills": data.get("combined_skills", "（待补充）"),
            "combined_scenarios": data.get("combined_scenarios", "（待补充）"),
            "cross_book_conflicts": data.get("cross_book_conflicts", "（暂无跨书数据）"),
            # v43.15: 4 类索引用表格字符串内嵌
            "concept_index": data.get("concept_index", "（待补充）"),
            "knowledge_index": data.get("knowledge_index", "（待补充）"),
            "skill_index": data.get("skill_index", "（待补充）"),
            "scenario_index": data.get("scenario_index", "（待补充）"),
            "book_count": str(s.get("book_count", 0)),
            "total_concept_count": str(s.get("concept_count", 0)),
            "total_knowledge_count": str(s.get("knowledge_count", 0)),
            "total_skill_count": str(s.get("skill_count", 0)),
            "total_scenario_count": str(s.get("scenario_count", 0)),
        },
    )

    return fm_text + body


def build_kb_overview(data):
    """生成L4知识库总揽"""
    template = load_template("kb_overview.md")
    if not template:
        return ""

    front_matter = {
        "template_version": "v3.0",
        "type": "kb_overview",
        "overview_level": "L4",
        "name": data.get("name", "知识库总揽"),
        "kb_id": data.get("kb_id", ""),
        "reviewer": "系统自动",
        "review_date": datetime.now().strftime("%Y-%m-%d"),
        "aliases": data.get("aliases", []),
        "tags": data.get("tags", ["knowledge-base", "kb"]),
        "cssclass": "knowledge-base",
    }

    fm_text = "---\n" + "\n".join(build_fm_line(k, v) for k, v in front_matter.items()) + "\n---\n"

    s = data.get("stats", {})
    # 图谱数据
    kg = data.get("kg_stats", {})
    kg_section = ""
    if kg:
        kg_section = (
            f"\n### 全库图感知统计\n\n"
            f"| 指标 | 数值 |\n"
            f"|:-----|:-----|\n"
            f"| 总节点数 | {kg.get('total', '?')} |\n"
            f"| 平均关联边数 | {kg.get('avg_edges', '?')} |\n"
            f"| 孤立节点（无入边） | {kg.get('orphans', '?')} |\n"
        )
        bd = kg.get("by_chapter", {})
        if bd:
            kg_section += "\n按章节分布：" + " | ".join(f"第{ch}章({c})" for ch, c in sorted(bd.items())) + "\n"
        cd = kg.get("confidence_dist", {})
        if cd:
            kg_section += "\n置信度分布：" + " | ".join(f"{k}({c})" for k, c in sorted(cd.items())) + "\n"
    graph_sec = data.get("graph_section", "")
    if isinstance(graph_sec, dict):
        graph_sec = json.dumps(graph_sec, ensure_ascii=False, indent=2)
    graph_content = kg_section + graph_sec if (kg_section or graph_sec) else "（待补充）"

    body = fill_template(
        template,
        {
            "description": data.get("description", "（待补充）"),
            "domain_index": data.get("domain_index", "（待补充）"),
            "mindmap_content": data.get("mindmap_content", ""),
            "graph_section": graph_content,
            "learning_path": data.get("learning_path", "（待补充）"),
            "combined_skills": data.get("combined_skills", "（待补充）"),
            "combined_scenarios": data.get("combined_scenarios", "（待补充）"),
            "knowledge_blindspots": data.get("knowledge_blindspots", "（待补充）"),
            # v43.15: 4 类索引用表格字符串内嵌
            "concept_index": data.get("concept_index", "（待补充）"),
            "knowledge_index": data.get("knowledge_index", "（待补充）"),
            "skill_index": data.get("skill_index", "（待补充）"),
            "scenario_index": data.get("scenario_index", "（待补充）"),
            "domain_count": str(s.get("domain_count", 0)),
            "total_book_count": str(s.get("book_count", 0)),
            "total_concept_count": str(s.get("concept_count", 0)),
            "total_knowledge_count": str(s.get("knowledge_count", 0)),
            "total_skill_count": str(s.get("skill_count", 0)),
            "total_scenario_count": str(s.get("scenario_count", 0)),
        },
    )

    return fm_text + body


# === 主入口 ===

def _build_book_description(
    book_name: str, ch_titles: list, ch_desc: str,
    total: int, c_count: int, e_count: int,
    k_count: int, s_count: int, sc_count: int,
    wiki_root: str = ".",
) -> str:
    """从 config/book_info.yaml 生成书籍总揽描述，无配置时自动降级。"""
    import yaml
    # 尝试从技能 config 加载
    skill_conf = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "book_info.yaml")
    local_conf = os.path.join(wiki_root, ".dag", "book_info.yaml")
    conf_data = {}
    for p in [local_conf, skill_conf]:
        try:
            with open(p, encoding="utf-8") as f:
                conf_data = yaml.safe_load(f) or {}
            break
        except Exception:
            continue

    domain = conf_data.get("domain", "本")
    ch_descs = conf_data.get("chapter_descriptions", {})
    tmpl = conf_data.get("book_template", "")

    # 生成各章描述文本
    ch_lines = []
    for idx, (num, title) in enumerate(ch_titles):
        idx_p1 = idx + 1
        desc = ch_descs.get(str(idx_p1), ch_descs.get(idx_p1, "")).format(domain=domain)
        if not desc:
            desc = ch_desc if idx == 0 else f"第{idx_p1}章相关内容。"
        ch_lines.append(f"- **{title}**：{desc}")

    if tmpl:
        return tmpl.format(
            book_name=book_name, domain=domain,
            chapter_count=len(ch_titles) or 8,
            ch_desc=ch_desc,
            chapter_descriptions="\n".join(ch_lines),
            total=total, c_count=c_count, e_count=e_count,
            k_count=k_count, s_count=s_count, sc_count=sc_count,
        )

    # 降级：无配置文件时生成简洁描述
    return (
        f"《{book_name}》是一本{domain}领域专业教材，共 {len(ch_titles) or 8} 章。\n\n"
        + "\n".join(ch_lines) + "\n\n"
        f"本知识库基于教材原文构建了 {total} 个知识节点（概念 {c_count}, "
        f"知识要素/实体 {e_count}, 知识点 {k_count}, 技能点 {s_count}, 场景 {sc_count}）。"
    )


if __name__ == "__main__":
    try:
        if len(sys.argv) < 2:
            log.info("用法: python3 index-assembler.py <index.json>")
            log.info("支持类型: concept_index, knowledge_index, skill_index, scenario_index, book_overview, domain_overview, kb_overview")
            raise PipelineError("用法: python3 index-assembler.py <index.json>")

        data_file = sys.argv[1]
        with open(data_file, encoding="utf-8") as f:
            data = json.load(f)

        index_type = data.get("index_type", "")
        output_dir = data.get("output_dir", ".")
        filename = data.get("filename", "")

        builders = {
            "concept_index": build_concept_index,
            "knowledge_index": build_knowledge_index,
            "skill_index": build_skill_index,
            "scenario_index": build_scenario_index,
            "book_overview": build_book_overview,
            "domain_overview": build_domain_overview,
            "kb_overview": build_kb_overview,
        }

        if index_type not in builders:
            log.error(f"❌ 未知索引类型: {index_type}")
            log.info(f"   支持: {', '.join(builders.keys())}")
            raise PipelineError(f"未知索引类型: {index_type}")

        result = builders[index_type](data)
        if not result:
            log.error(f"❌ {index_type}: 生成失败（模板缺失？）")
            raise PipelineError(f"{index_type}: 生成失败")

        os.makedirs(output_dir, exist_ok=True)
        if not filename:
            name = data.get("name", index_type)
            safe_name = "".join(c for c in name if c not in '\\/:*?"<>|')
            filename = f"{index_type}_{safe_name}.md"

        filepath = os.path.join(output_dir, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(result)
        log.success(f"  ✅ {os.path.basename(filepath)} ({len(result)} chars)")
    except PipelineError as e:
        log.error(str(e))
        raise
