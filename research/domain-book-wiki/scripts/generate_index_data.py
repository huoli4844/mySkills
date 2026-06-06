#!/usr/bin/env python3
"""
generate_index_data.py — 从 kb_graph 或文件扫描生成索引JSON配置文件 (v42.0 拆分重构)

v42.0: 图谱分析函数拆分到 graph_analytics.py。
本文件保留 CLI + 索引生成编排逻辑。

用法:
  python3 generate_index_data.py --wiki-root /path/to/wiki --book-id 01_示例书籍 --level l2
  python3 generate_index_data.py --wiki-root /path/to/wiki --book-id 01_示例书籍 --level l3
  python3 generate_index_data.py --wiki-root /path/to/wiki --book-id 01_示例书籍 --level l4

--level 参数: l2（单书总揽）, l3（领域总控）, l4（知识库总控）, all（全部）
输出: 在 {book_dir}/.dag/ 生成 index_*.json 供 index-assembler.py 使用
"""

import argparse
import json
import os
import sys

from log_utils import get_logger

log = get_logger(__name__)


# 从 dag_controller 导入路径注册表
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)
from dag_constants import DIR  # noqa: E402
from dag_state import WorkspacePaths, load_workspace_config  # noqa: E402
from graph_analytics import _build_graph_section, _get_enriched_nodes, _get_kg_data  # noqa: E402
from parse_utils import parse_frontmatter  # noqa: E402


def main():
    p = argparse.ArgumentParser(description="生成索引JSON配置文件")
    p.add_argument("--wiki-root", "-w", required=True, help="wiki根目录")
    p.add_argument("--book-id", required=True, help="书籍ID，如 01_示例书籍")
    p.add_argument("--book-name", default=None, help="书籍名称")
    p.add_argument("--book-dir", default=None, help="书籍实际目录（nested布局下推导domain路径）")
    p.add_argument("--domain-id", default="", help="领域ID，如 01_示例领域")
    p.add_argument("--domain-name", default="", help="领域名称")
    p.add_argument("--kb-name", default="", help="知识库名称")
    p.add_argument(
        "--level",
        choices=["l2", "l3", "l4", "all"],
        default="all",
        help="索引层级: l2(单书总揽) / l3(领域总控) / l4(知识库总控) / all(全部)",
    )
    args = p.parse_args()

    _C = DIR["CONCEPTS"]
    _K = DIR["KP"]
    _S = DIR["SP"]
    _SN = DIR["SCENE"]
    _E = DIR["ENTITIES"]
    _SRC = DIR["SOURCE"]
    _OV = DIR["OVERVIEW"]
    _F = DIR["FIELD"]
    _L = DIR["LIBRARY"]
    _SRC = DIR["SOURCE"]

    # v43.1: 使用 WorkspacePaths 集中推导所有路径
    if args.book_dir and os.path.isdir(args.book_dir):
        wp = WorkspacePaths(args.book_dir)
    else:
        # 回退：从 wiki-root 推导（向后兼容 flat 布局）
        _ws_config = load_workspace_config(args.wiki_root)
        if _ws_config.get("layout") == "flat":
            wp = WorkspacePaths(args.wiki_root)
        else:
            wp = WorkspacePaths(os.path.join(args.wiki_root, DIR["FIELD"], DIR["LIBRARY"], args.book_id))

    BOOK_DIR = wp.book_dir
    WIKI_ROOT = wp.kb_root
    DOMAIN_CTRL = wp.l3_dir
    KB_CTRL = wp.l4_dir
    BOOK_OVERVIEW = wp.l2_dir
    BOOK_NAME = args.book_name or wp.book_name
    DOMAIN_ID = args.domain_id or wp.domain_name
    DOMAIN_NAME = args.domain_name or wp.domain_name
    KB_NAME = args.kb_name or os.path.basename(wp.kb_root)

    for d in [BOOK_OVERVIEW, DOMAIN_CTRL, KB_CTRL, f"{BOOK_DIR}/.dag"]:
        os.makedirs(d, exist_ok=True)

    OUTPUT_DIR = f"{BOOK_DIR}/.dag"

    # 尝试从 kb_graph 获取增强数据
    kg_data = _get_kg_data(WIKI_ROOT, args.book_id)
    if kg_data:
        log.info(f"  📊 使用 kb_graph 增强数据 ({kg_data['stats']['total']} nodes, "
            f"avg {kg_data['stats']['avg_edges']} edges/node)")
        # 补充拓扑增强字段
        try:
            from kb_graph import KGraph

            kg = KGraph(WIKI_ROOT)
            if os.path.exists(kg.db_path):
                enriched = _get_enriched_nodes(kg, args.book_id, kg_data)
                if enriched:
                    for nid, fields in enriched.items():
                        if nid in kg_data.get("nodes", {}):
                            kg_data["nodes"][nid].update(fields)
                    log.success(f"  ✅ 拓扑增强: {len(enriched)} 节点已补充度/上下游信息")
        except Exception as e:
            log.warning(f"图谱增强跳过: {e}")
    else:
        log.info("  ℹ️  kb_graph 不可用，回退到文件扫描")

    def scan_files(subdir):
        """扫描目录中的 .md 文件（回退方案）"""
        full = f"{BOOK_DIR}/{subdir}"
        if not os.path.isdir(full):
            return []
        files = []
        for f in sorted(os.listdir(full)):
            if f.endswith(".md"):
                files.append(f[:-3])
        return files

    def build_item(name, wikilink, item_type=None, node_id=None):
        """构建索引条目，含 kb_graph 增强字段 + 拓扑信息"""
        item = {"name": name, "chapter_num": "0", "wikilink": wikilink}

        # 若有 kb_graph 数据，补充元数据
        if kg_data and node_id and node_id in kg_data["nodes"]:
            nd = kg_data["nodes"][node_id]
            item["chapter_num"] = nd["chapter_num"]
            item["confidence"] = nd["confidence"]
            item["edge_count"] = nd["edge_count"]
            item["type"] = nd["type"]
            # Bloom 层级和难度（v36.0 新增）
            item["bloom_level"] = nd.get("bloom_level", "")
            item["difficulty"] = nd.get("difficulty", "")
            # 拓扑增强字段（来自 _get_enriched_nodes）
            for field in ("degree", "out_degree", "in_degree", "downstream_count", "upstream_count", "in_scene"):
                if field in nd:
                    item[field] = nd[field]
        else:
            item["type"] = item_type or ""

        return item

    def make_index_json(index_type, template, filename, items, output_dir, **extra):
        """生成索引 JSON，含 kb_graph 增强统计"""
        data = {
            "index_type": index_type,
            "template": template,
            "filename": filename,
            "items": items,
            "output_dir": output_dir,
            **extra,
        }
        # 添加 kb_graph 统计到 extra
        if kg_data and "kg_stats" not in extra:
            data["kg_stats"] = kg_data["stats"]
        path = f"{OUTPUT_DIR}/{index_type}_{args.book_id}_{args.level}.json"
        with open(path, "w") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return path

    # ===== v47.0 P0: 始终优先扫描实际文件（消除断链） =====
    def _scan_files_with_fm(subdir: str) -> list[dict]:
        """扫描目录中的 .md 文件，读取 frontmatter 获取 name/chapter_num/type。
        
        Returns:
            [{fname, name, chapter_num, type}, ...] 按文件名排序
        """
        full = f"{BOOK_DIR}/{subdir}"
        if not os.path.isdir(full):
            return []
        entries = []
        for f in sorted(os.listdir(full)):
            if not f.endswith(".md"):
                continue
            fname = f[:-3]  # 去掉 .md
            entry = {"fname": fname, "name": fname, "chapter_num": "0", "type": ""}
            # 读取 frontmatter
            try:
                with open(os.path.join(full, f), encoding="utf-8") as fh:
                    content = fh.read()
                fm = parse_frontmatter(content)
                entry["name"] = fm.get("name", fname)
                entry["chapter_num"] = str(fm.get("chapter_num", "0"))
                entry["type"] = fm.get("type", "")
            except Exception as e:
                log.debug(f"Frontmatter解析失败: {e}")
                pass
            entries.append(entry)
        return entries

    # 扫描四个核心目录
    concept_entries = _scan_files_with_fm(_C)
    kp_entries = _scan_files_with_fm(_K)
    sp_entries = _scan_files_with_fm(_S)
    scene_entries = _scan_files_with_fm(_SN)
    # 保留实体文件扫描（用于 stats）
    if kg_data:
        all_nodes = kg_data["nodes"].values()
        entity_files = sorted(
            set(v["id"].split("/")[-1] for v in all_nodes if v["type"] == "entity" and "/" in v["id"])
        )
    else:
        entity_files = scan_files(_E)

    concepts_only = [e["fname"] for e in concept_entries]
    kp_files = [e["fname"] for e in kp_entries]
    sp_files = [e["fname"] for e in sp_entries]
    scene_files = [e["fname"] for e in scene_entries]

    log.info(f"  📁 文件扫描: {len(concept_entries)} 概念, {len(kp_entries)} 知识点, "
             f"{len(sp_entries)} 技能点, {len(scene_entries)} 场景")

    def _make_items(entries: list[dict], prefix: str) -> list[dict]:
        """构建条目列表，使用扫描得到的 frontmatter 元数据 + 附加 kg_graph 节点信息。
        
        Args:
            entries: _scan_files_with_fm 返回的条目列表 [{fname, name, chapter_num, type}, ...]
            prefix: wikilink 路径前缀（如 ../30_核心概念）
        """
        items = []
        for e in entries:
            fname = e["fname"]
            node_id = f"{args.book_id}/{prefix.split('/')[-1]}/{fname}"
            wikilink = f"[[{prefix}/{fname}]]"
            item = build_item(e["name"], wikilink, item_type=e.get("type", ""), node_id=node_id)
            # 用 frontmatter 中的 chapter_num 覆盖
            if e.get("chapter_num") and e["chapter_num"] != "0":
                item["chapter_num"] = e["chapter_num"]
            items.append(item)
        return items

    def _build_wikilink_table(items, title):
        """构建 wikilink 表格字符串（不含标题，模板已提供）"""
        if not items:
            return "暂无\n"
        lines = ["", "| # | 名称 | 链接 |", "|:--|:-----|:-----|"]
        for i, item in enumerate(items, 1):
            name = item.get("name", f"item_{i}")
            link = item.get("wikilink", f"[[{name}]]")
            lines.append(f"| {i} | {name} | {link} |")
        return "\n".join(lines)

    def _kg_stats():
        """获取 kb_graph 统计（含各类型计数）"""
        if kg_data:
            s = kg_data["stats"].copy()
            s["concept_count"] = len(concepts_only)
            s["knowledge_count"] = len(kp_files)
            s["skill_count"] = len(sp_files)
            s["scenario_count"] = len(scene_files)
            s["entity_count"] = len(entity_files)
            return s
        return {
            "concept_count": len(concepts_only),
            "knowledge_count": len(kp_files),
            "skill_count": len(sp_files),
            "scenario_count": len(scene_files),
            "entity_count": len(entity_files),
        }

    # v43.15: 构建 4 类 wikilink 索引表（L2/L3/L4 共用）
    #   book_overview 在 10_总揽/ 下，用相对路径 ../{dir}/{file} 避免表格中管道符问题
    _rel_C = f"../{_C}"
    _rel_K = f"../{_K}"
    _rel_S = f"../{_S}"
    _rel_SN = f"../{_SN}"

    concept_items = _make_items(concept_entries, _rel_C)
    kp_items = _make_items(kp_entries, _rel_K)
    sp_items = _make_items(sp_entries, _rel_S)
    scene_items = _make_items(scene_entries, _rel_SN)

    def _filter_isolated(items, prefix):
        if not kg_data:
            return items
        filtered, skipped = [], []
        for item in items:
            node_id = f"{args.book_id}/{prefix.split('/')[-1]}/{item['name']}"
            nd = kg_data["nodes"].get(node_id)
            if nd and nd.get("edge_count", 0) <= 0:
                skipped.append(item["name"])
            else:
                filtered.append(item)
        if skipped:
            log.info(f"    ℹ️  过滤 {len(skipped)} 个孤立节点: {', '.join(skipped[:3])}{'...' if len(skipped) > 3 else ''}")
        return filtered if filtered else items

    concept_items_f = _filter_isolated(concept_items, _C)
    kp_items_f = _filter_isolated(kp_items, _K)
    sp_items_f = _filter_isolated(sp_items, _S)
    scene_items_f = _filter_isolated(scene_items, _SN)

    # ===== L2: 单书总揽 =====
    if args.level in ("l2", "all"):
        # 构建图驱动的 book_overview 内容（v35.0: 返回 dict）
        graph_data = {}
        try:
            from kb_graph import KGraph

            kg = KGraph(WIKI_ROOT)
            if os.path.exists(kg.db_path):
                graph_data = _build_graph_section(kg, args.book_id, kg_data["stats"] if kg_data else None)
        except Exception as e:
            log.warning(f"图谱分析跳过: {e}")

        make_index_json(
            "book_overview",
            "book_overview.md",
            f"book_overview_{args.book_id}_0.md",
            [build_item(BOOK_NAME, f"[[{BOOK_DIR}/{DIR['SOURCE']}/第N章|{BOOK_NAME}]]")],
            BOOK_OVERVIEW,
            book_id=args.book_id,
            book_name=BOOK_NAME,
            stats=_kg_stats(),
            kg_stats=kg_data["stats"] if kg_data else None,
            chain_connectivity=graph_data.get("chain_connectivity", "（待补充）"),
            node_connectivity=graph_data.get("node_connectivity", ""),
            graph_quality=graph_data.get("graph_quality", ""),
            top_nodes=graph_data.get("top_nodes", ""),
            mindmap_content=graph_data.get("mindmap", ""),
            chapter_distribution=graph_data.get("chapter_distribution", ""),
            learning_path=graph_data.get("learning_path", "（待补充）"),
            error_attribution=graph_data.get("error_attribution", "（暂无）"),
            learning_path_v2=graph_data.get("learning_path_v2", "（待补充）"),
            todo_items=graph_data.get("todo_items", "（无待修复项）"),
            # v43.15: 4 类索引用表格字符串内嵌
            concept_index=_build_wikilink_table(concept_items_f, "核心概念"),
            knowledge_index=_build_wikilink_table(kp_items_f, "知识点"),
            skill_index=_build_wikilink_table(sp_items_f, "技能点"),
            scenario_index=_build_wikilink_table(scene_items_f, "应用场景"),
        )

        log.success(f"  ✅ L2索引JSON → {OUTPUT_DIR}/")

    # ===== L3: 领域总控 =====
    if args.level in ("l3", "all"):
        # 构建跨书图谱总览
        graph_section_l3 = ""
        try:
            from kb_graph import KGraph

            kg = KGraph(WIKI_ROOT)
            if os.path.exists(kg.db_path):
                graph_section_l3 = _build_graph_section(
                    kg,
                    args.book_id,
                    kg_data["stats"] if kg_data else None,
                    like_pattern="%",  # 全库（含多书）
                )
                # 替换标题以适配L3语境
                graph_section_l3 = (
                    graph_section_l3.replace("## 📊 图连接性全景", "## 📊 跨书图连接性全景")
                    .replace("## 🔍 图质量摘要", "## 🔍 领域图质量摘要")
                    .replace("## 🗺 知识图谱全景", "## 🗺 跨书知识图谱全景")
                )
        except Exception as e:
            log.warning(f"领域级图谱分析跳过: {e}")

        make_index_json(
            "domain_overview",
            "domain_overview.md",
            f"domain_overview_{DOMAIN_ID}_0.md",
            [build_item(BOOK_NAME, f"[[{args.book_id}/{DIR['OVERVIEW']}/book_overview_{args.book_id}_0|{BOOK_NAME}]]")],
            DOMAIN_CTRL,
            domain_id=DOMAIN_ID,
            domain_name=DOMAIN_NAME,
            stats=_kg_stats(),
            kg_stats=kg_data["stats"] if kg_data else None,
            graph_section=graph_section_l3,
            # v43.15: 4 类索引用表格字符串内嵌
            concept_index=_build_wikilink_table(concept_items_f, "核心概念"),
            knowledge_index=_build_wikilink_table(kp_items_f, "知识点"),
            skill_index=_build_wikilink_table(sp_items_f, "技能点"),
            scenario_index=_build_wikilink_table(scene_items_f, "应用场景"),
        )

        log.success(f"  ✅ L3索引JSON → {OUTPUT_DIR}/")

    # ===== L4: 知识库总控 =====
    if args.level in ("l4", "all"):
        # 构建全库图谱总览
        graph_section_l4 = ""
        try:
            from kb_graph import KGraph

            kg = KGraph(WIKI_ROOT)
            if os.path.exists(kg.db_path):
                graph_section_l4 = _build_graph_section(
                    kg, args.book_id, kg_data["stats"] if kg_data else None, like_pattern="%"
                )
                graph_section_l4 = (
                    graph_section_l4.replace("## 📊 图连接性全景", "## 📊 全库图连接性全景")
                    .replace("## 🔍 图质量摘要", "## 🔍 全库图质量摘要")
                    .replace("## 🗺 知识图谱全景", "## 🗺 全库知识图谱全景")
                )
        except Exception as e:
            log.warning(f"全库级图谱分析跳过: {e}")

        make_index_json(
            "kb_overview",
            "kb_overview.md",
            f"kb_overview_{KB_NAME}_0.md",
            [build_item(DOMAIN_NAME, f"[[{DOMAIN_NAME}|{DOMAIN_NAME}]]")],
            KB_CTRL,
            kb_name=KB_NAME,
            stats=_kg_stats(),
            kg_stats=kg_data["stats"] if kg_data else None,
            graph_section=graph_section_l4,
            # v43.15: 4 类索引用表格字符串内嵌
            concept_index=_build_wikilink_table(concept_items_f, "核心概念"),
            knowledge_index=_build_wikilink_table(kp_items_f, "知识点"),
            skill_index=_build_wikilink_table(sp_items_f, "技能点"),
            scenario_index=_build_wikilink_table(scene_items_f, "应用场景"),
        )

        log.success(f"  ✅ L4索引JSON → {OUTPUT_DIR}/")

    log.info("   运行: dag_controller.py phase l2_indices|l3_indices|l4_indices assemble")

    # ── v44.0 P1-2: 索引内容验证闸门 ──
    _validate_index_content(OUTPUT_DIR, args.book_id, args.level)


def _validate_index_content(output_dir: str, book_id: str, level: str) -> None:
    """验证生成的索引 JSON 中无占位符/空内容。

    检测模式:
      - 关键字段值为「（待补充）」「（暂无）」「（无待修复项）」（正常情况除外）
      - items 全部 chapter_num == "0"（数据缺失信号）
      - mindmap_content 为空（将产生空 Mermaid 块）
    """
    import glob as _glob

    placeholder_patterns = ["（待补充）", "（暂无）"]
    json_files = _glob.glob(os.path.join(output_dir, f"*_{book_id}_{level}.json"))
    issues: list[str] = []

    for jf in json_files:
        try:
            with open(jf, encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            log.debug(f"JSON加载失败: {e}")
            continue

        fname = os.path.basename(jf)

        # 1. 检测占位符内容
        for key in ("chain_connectivity", "node_connectivity", "graph_quality",
                     "top_nodes", "learning_path", "learning_path_v2",
                     "chapter_distribution", "error_attribution", "todo_items"):
            val = str(data.get(key, ""))
            for pp in placeholder_patterns:
                if pp in val:
                    issues.append(f"{fname}: {key} 含占位符「{pp}」")
                    break

        # 2. 检测 items 全部 chapter_num == "0"
        items = data.get("items", [])
        if items and all(str(it.get("chapter_num", "0")) == "0" for it in items):
            issues.append(f"{fname}: 全部 {len(items)} 个 items 的 chapter_num 均为 0（数据可能缺失）")

        # 3. 检测空 mindmap
        mindmap = str(data.get("mindmap_content", ""))
        if mindmap in ("", "None", "null"):
            issues.append(f"{fname}: mindmap_content 为空（将产生空 Mermaid 块）")

        # 4. 检测 stats 全 0（知识链连通率虚高信号）
        stats = data.get("stats", {})
        if stats:
            non_zero = sum(1 for v in stats.values() if isinstance(v, int | float) and v > 0)
            if non_zero == 0 and len(stats) >= 4:
                issues.append(f"{fname}: stats 全部为 0（索引数据可能未正确生成）")

    if issues:
        log.warning(f"⚠️  索引内容验证发现 {len(issues)} 个问题:")
        for issue in issues:
            log.warning(f"  - {issue}")
        log.info("  建议: 检查对应章节数据是否完整，重跑 generate_index_data.py")
    else:
        log.success(f"  ✅ 索引内容验证通过: {len(json_files)} 个 JSON 文件正常")


if __name__ == "__main__":
    main()
