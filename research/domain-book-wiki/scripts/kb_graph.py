"""
kb_graph.py — 知识图谱引擎

从 .md 知识库构建 SQLite 知识图谱（nodes + edges + FTS5）。
只读不写，不修改任何 .md 文件。

用法：
  from kb_graph import KGraph
  kg = KGraph("/path/to/wiki_root")
  kg.build()              # 全量重建
  kg.query("传导耦合")     # 查询节点+关联
  kg.validate()            # 图质量验证

CLI：
  python3 kb_graph.py /path/to/wiki build
  python3 kb_graph.py /path/to/wiki query "传导耦合"
  python3 kb_graph.py /path/to/wiki validate
"""

import json
import os
import re
import sqlite3
import sys
from typing import Any

# v36.5: 质量检查方法已拆分到 graph_quality.py
from dag_constants import PipelineError
from graph_quality import KGraphQualityMixin

# v39.2: 构建和查询方法已拆分到独立 Mixin
from kb_graph_builder import KGraphBuilderMixin
# v50.7: KGraphQueryMixin 恢复为独立模块（修复前向引用）
from kb_graph_query import KGraphQueryMixin  # noqa: F811
from log_utils import get_logger

# v38.0: 统一解析工具（消除重复 FM 解析）
from parse_utils import parse_frontmatter as _parse_fm_util

log = get_logger(__name__)

# ── SQLite 建表 ────────────────────────────────────────────

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS nodes (
    id          TEXT PRIMARY KEY,
    type        TEXT NOT NULL,
    name        TEXT NOT NULL,
    book_id     TEXT DEFAULT '',
    chapter_num TEXT DEFAULT '',
    confidence  REAL DEFAULT 0.0,
    source_chapter TEXT DEFAULT '',
    summary     TEXT DEFAULT '',
    dir         TEXT DEFAULT '',
    mtime       REAL DEFAULT 0,
    file_path   TEXT DEFAULT '',
    bloom_level TEXT DEFAULT '',
    difficulty  TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS edges (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id   TEXT NOT NULL,
    target_id   TEXT NOT NULL,
    rel_type    TEXT NOT NULL DEFAULT 'RELATED_TO',
    section     TEXT DEFAULT '',
    weight      REAL NOT NULL DEFAULT 1.0,
    FOREIGN KEY (source_id) REFERENCES nodes(id),
    FOREIGN KEY (target_id) REFERENCES nodes(id)
);
CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(source_id);
CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(target_id);

CREATE VIRTUAL TABLE IF NOT EXISTS nodes_fts USING fts5(
    name, type, summary, frontmatter_text
);

CREATE TABLE IF NOT EXISTS _file_hashes (
    file_path   TEXT PRIMARY KEY,
    content_hash TEXT NOT NULL,
    mtime       REAL NOT NULL,
    node_id     TEXT DEFAULT '',
    built_at    TEXT DEFAULT ''
);
"""

# ── 节标题 → 关系类型映射 ──────────────────────────────────
# 从模板文件中提取。匹配方式：子串匹配（"核心概念图谱" 命中 "3. 核心概念图谱"）
# 注意：补充了实际文件中发现的所有变体。

SECTION_REL_MAP: dict[str, str] = {
    # concept_template.md — 结构分层（v37.0: 概念类归并模板）
    "核心概念图谱": "PART_OF",
    "核心概念图谱解析": "PART_OF",  # 实际文件中的变体
    "工作原理/构成要素": "PART_OF",
    "技术分类": "PART_OF",
    # 应用
    "应用场景": "APPLIES_TO",
    "典型系统": "RELATED_TO",
    # 关联
    "与相关概念的关系": "RELATED_TO",
    "相近概念辨析": "CONTRASTS_WITH",
    "易混淆辨析": "CONTRASTS_WITH",
    "易混淆知识点辨析": "CONTRASTS_WITH",
    "易混淆技能辨析": "CONTRASTS_WITH",
    "发展/演进": "EVOLVED_FROM",
    "发展演进": "EVOLVED_FROM",  # 匹配 "发展演进 + 知识脉络图" 等
    "知识脉络图解析": "EVOLVED_FROM",  # 变体：发展演进后的解析段落
    # 约束
    "常见误区": "LIMITED_BY",
    "操作边界": "LIMITED_BY",
    "边界条件": "LIMITED_BY",
    # 前置
    "前置知识点": "PREREQUISITE_OF",
    "前置技能": "PREREQUISITE_OF",
    # 知识要素引用
    "使用到的知识要素": "RELATED_TO",
    "关联概念": "RELATED_TO",
    "关联知识要素": "RELATED_TO",
    "关联知识点": "RELATED_TO",
    "关联概念/知识点/知识要素": "RELATED_TO",
    "支撑概念": "RELATED_TO",
    "支撑知识要素": "RELATED_TO",
    # 技能/场景支撑
    "支撑的技能点/场景": "APPLIES_TO",
    "支撑知识点": "APPLIES_TO",
    "支撑技能点": "APPLIES_TO",
    "支撑的场景": "APPLIES_TO",
    "适配场景": "APPLIES_TO",
    # 解答
    "关联习题": "ANSWERS",
    "关联习题解答": "ANSWERS",
}

# 这些节中的 wikilink 不建边（纯元数据/排版）
SKIP_SECTIONS = {"术语定义", "精准释义", "知识点名称", "技能点名称", "场景名称"}


class KGraph(KGraphBuilderMixin, KGraphQueryMixin, KGraphQualityMixin):
    """知识图谱 SQLite 管理 + 查询 + 构建 + 质量检查。

    v36.5: 质量检查方法已拆分到 graph_quality.KGraphQualityMixin。
    v39.2: 构建方法拆分到 kb_graph_builder.KGraphBuilderMixin，
           查询方法拆分到 kb_graph_query.KGraphQueryMixin。
    """

    def __init__(self, wiki_root: str):
        self.wiki_root = os.path.abspath(wiki_root)
        self.db_path = os.path.join(self.wiki_root, ".dag", "kb_graph.db")
        os.makedirs(os.path.join(self.wiki_root, ".dag"), exist_ok=True)

    # ── 内部工具 ──────────────────────────────────────────

    def _conn(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        with self._conn() as c:
            c.executescript(SCHEMA_SQL)
        # v46.0: 迁移 — 为旧数据库添加 weight 列
        self._migrate_add_weight()

    def _book_dirs(self) -> list[str]:
        """找出 wiki_root 下所有书籍目录"""
        # v43.13: 修复硬编码路径——知识库按 领域/书籍 而非 01_领域/01_资料库/ 组织
        found = []
        for domain_dir in os.listdir(self.wiki_root):
            domain_path = os.path.join(self.wiki_root, domain_dir)
            if not os.path.isdir(domain_path) or domain_dir.startswith('.'):
                continue
            for book_dir in os.listdir(domain_path):
                book_path = os.path.join(domain_path, book_dir)
                if os.path.isdir(book_path) and not book_dir.startswith('.'):
                    found.append(book_path)
        return sorted(found)

    def _type_dir_map(self, book_dir: str) -> dict[str, str]:
        """DIR 路径 → 节点类型映射（基于 domain-book-wiki 的目录结构）"""
        # v43.13: 修正目录编号——匹配真实目录 30/40/50/60/70/80/90/10
        dir_to_type = {
            "30_核心概念": "concept",
            "40_知识要素": "knowledge-element",
            "50_知识点": "knowledge",
            "60_技能点": "skill",
            "70_应用场景": "scenario",
            "80_实体": "entity",
            "90_习题": "exercise",
            "解答": "solution",
            "10_总揽": "index",
            "00_领域总控": "index",
            "00_知识库总控": "index",
        }
        result = {}
        for dname, ntype in dir_to_type.items():
            full = os.path.join(book_dir, dname)
            if os.path.isdir(full):
                result[full] = ntype
            # 特殊：解答在 90_习题/解答 下
            if dname == "解答":
                sol_dir = os.path.join(book_dir, "90_习题", "解答")
                if os.path.isdir(sol_dir):
                    result[sol_dir] = ntype
        # 全局总控目录
        for gd in ["00_知识库总控", "00_领域总控"]:
            full = os.path.join(self.wiki_root, gd)
            if os.path.isdir(full):
                result[full] = "index"
            # 也可能在 01_领域/下
            domain_ctrl = os.path.join(self.wiki_root, "01_领域", gd)
            if os.path.isdir(domain_ctrl):
                result[domain_ctrl] = "index"
        return result

    # ── .md 解析 ──────────────────────────────────────────

    def _parse_frontmatter(self, content: str) -> dict[str, Any]:
        """解析 frontmatter，返回字典（v38.0: 委托 parse_utils）"""
        return _parse_fm_util(content)

    def _split_sections(self, body: str) -> list[dict]:
        """将 body 按 ### 和 ## 拆分，返回 [{heading, content}]"""
        sections = []
        # 匹配 ## 或 ### 开头的行
        pattern = r"^(#{2,3})\s+(.*?)$"
        lines = body.split("\n")
        current_heading = None
        current_level = 0
        current_content = []
        for line in lines:
            m = re.match(pattern, line)
            if m:
                if current_heading:
                    sections.append(
                        {
                            "heading": current_heading,
                            "level": current_level,
                            "content": "\n".join(current_content).strip(),
                        }
                    )
                current_level = len(m.group(1))
                current_heading = m.group(2).strip()
                current_content = []
            else:
                current_content.append(line)
        if current_heading:
            sections.append(
                {
                    "heading": current_heading,
                    "level": current_level,
                    "content": "\n".join(current_content).strip(),
                }
            )
        return sections

    def _extract_wikilinks(self, text: str) -> list[str]:
        """从文本中提取所有 [[路径/名称]] wikilink，返回目标路径列表"""
        links = re.findall(r"\[\[([^\]]+?)(?:\|[^\]]+)?\]\]", text)
        result = []
        for link in links:
            link = link.strip()
            if not link:
                continue
            if link.startswith(".."):
                continue
            if link.startswith("http"):
                continue
            result.append(link)
        return result

    def _infer_rel_type(self, heading: str) -> str:
        """根据节标题推断关系类型"""
        for keyword, rel_type in SECTION_REL_MAP.items():
            if keyword in heading:
                return rel_type
        return "RELATED_TO"

    def _make_node_id(self, file_path: str, book_dir: str | None = None) -> str:
        """从文件路径和书籍目录生成唯一节点 ID"""
        rel = os.path.relpath(file_path, self.wiki_root)
        if rel.endswith(".md"):
            rel = rel[:-3]
        # 对书籍内的文件，用 {book_id}/{dir}/{name} 格式
        if book_dir:
            bname = os.path.basename(book_dir)
            if bname.startswith("01_"):
                rel = rel.replace(f"01_领域/01_资料库/{bname}/", f"{bname}/")
        return rel

    def _should_skip(self, heading: str) -> bool:
        """是否跳过此节中的 wikilink"""
        return any(skip in heading for skip in SKIP_SECTIONS)

    # ── v46.0: 加权知识图谱 ──────────────────────────────

    # 关系类型基础权重
    REL_TYPE_WEIGHTS: dict[str, float] = {  # noqa: RUF012
        "COMPOSED_OF": 5.0,       # 组成关系（最强）
        "PART_OF": 4.0,           # 部分关系
        "PREREQUISITE_OF": 4.5,   # 前置依赖
        "TESTS": 4.0,             # 考核关系
        "ANSWERS": 3.5,           # 解答关系
        "APPLIES_TO": 3.0,        # 应用关系
        "CONTRASTS_WITH": 2.5,    # 对比关系
        "EVOLVED_FROM": 2.0,      # 演化关系
        "LIMITED_BY": 1.5,        # 约束关系
        "RELATED_TO": 1.0,        # 一般关联（默认）
    }

    # 类型亲和力矩阵 — 同类型加分
    TYPE_AFFINITY: dict[str, dict[str, float]] = {  # noqa: RUF012
        "concept": {
            "knowledge-element": 1.2, "concept": 0.8, "entity": 1.0,
            "knowledge": 1.2, "skill": 1.0, "scenario": 0.8,
        },
        "knowledge-element": {
            "concept": 1.2, "knowledge-element": 0.5,
        },
        "knowledge": {
            "concept": 1.2, "knowledge": 0.8, "skill": 1.5, "scenario": 1.0,
        },
        "skill": {
            "knowledge": 1.5, "skill": 0.8, "scenario": 1.5,
        },
        "scenario": {
            "knowledge": 1.0, "skill": 1.5, "scenario": 0.8,
        },
    }

    @staticmethod
    def compute_edge_weight(
        rel_type: str,
        source_type: str | None = None,
        target_type: str | None = None,
    ) -> float:
        """计算边权重。

        权重 = 关系类型基础权重 × 类型亲和力（如果有）
        """
        base = KGraph.REL_TYPE_WEIGHTS.get(rel_type, 1.0)
        if source_type and target_type:
            affinity_map = KGraph.TYPE_AFFINITY.get(source_type, {})
            affinity = affinity_map.get(target_type, 1.0)
            return round(base * affinity, 2)
        return base

    def _migrate_add_weight(self) -> None:
        """v46.0: 为旧数据库的 edges 表添加 weight 列（如果不存在）"""
        try:
            with self._conn() as c:
                c.execute("ALTER TABLE edges ADD COLUMN weight REAL NOT NULL DEFAULT 1.0")
        except Exception as e:
            log.debug(f"添加weight列失败（可能已存在）: {e}")
            pass  # 列已存在

    # ── 构建方法 → kb_graph_builder.KGraphBuilderMixin ──
    # build, build_incremental, _process_file, _resolve_plaintext_edges,
    # _extract_names_from_plaintext, _extract_exercise_name, _stats,
    # _build_node_name_map, _build_name_to_id_pre, _full_target


# ── CLI ──────────────────────────────────────────────────


def main():
    if len(sys.argv) < 3:
        log.info("用法: python3 kb_graph.py <wiki_root> <command> [args...]")
        log.info("命令:")
        log.info("  build           — 全量重建知识图谱")
        log.info("  build-incr      — 增量构建（仅变更文件）")
        log.info("  query <name>    — 查询节点")
        log.info("  search <text>   — 全文搜索")
        log.info("  trace <name>    — 影响链追踪")
        log.info("  impact <name>   — 修改影响分析")
        log.info("  validate        — 图质量验证")
        log.info("  mermaid <name>  — 导出 Mermaid 子图")
        log.info("  connectivity    — L1阶段连通性检查")
        log.info("  similar         — 相似节点名检测")
        log.info("  centrality      — 度中心性计算")
        log.info("  bridge          — 桥接缺口检测")
        log.info("  path            — 路径完整性检查")
        log.info("  build-order     — 构建顺序建议")
        raise PipelineError("用法: python3 kb_graph.py <wiki_root> <command> [args...]")

    wiki_root = sys.argv[1]
    cmd = sys.argv[2]
    kg = KGraph(wiki_root)

    if cmd == "build":
        stats = kg.build()
        log.info(json.dumps(stats, ensure_ascii=False, indent=2))

    elif cmd == "build-incr":
        stats = kg.build_incremental()
        log.info(json.dumps(stats, ensure_ascii=False, indent=2))

    elif cmd == "query":
        name = " ".join(sys.argv[3:]) if len(sys.argv) > 3 else ""
        if not name:
            log.error("需要节点名")
            raise PipelineError("query 需要节点名")
        result = kg.query(name)
        log.info(json.dumps(result, ensure_ascii=False, indent=2, default=str))

    elif cmd == "search":
        text = " ".join(sys.argv[3:]) if len(sys.argv) > 3 else ""
        if not text:
            log.error("需要搜索词")
            raise PipelineError("search 需要搜索词")
        result = kg.search(text)
        log.info(json.dumps(result, ensure_ascii=False, indent=2, default=str))

    elif cmd == "trace":
        name = " ".join(sys.argv[3:]) if len(sys.argv) > 3 else ""
        if not name:
            log.error("需要节点名")
            raise PipelineError("trace 需要节点名")
        result = kg.trace(name)
        log.info(json.dumps(result, ensure_ascii=False, indent=2, default=str))

    elif cmd == "impact":
        name = " ".join(sys.argv[3:]) if len(sys.argv) > 3 else ""
        if not name:
            log.error("需要节点名")
            raise PipelineError("impact 需要节点名")
        result = kg.impact(name)
        log.info(json.dumps(result, ensure_ascii=False, indent=2, default=str))

    elif cmd == "validate":
        os.makedirs(os.path.join(wiki_root, ".dag"), exist_ok=True)
        kg._init_db()
        # 检查是否有数据
        with kg._conn() as c:
            cnt = c.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
            if cnt == 0:
                log.warning("知识图谱为空，先运行 build")
                raise PipelineError("知识图谱为空，先运行 build")
        issues = kg.validate()
        if issues:
            for issue in issues:
                icon = {"error": "❌", "warn": "⚠️", "info": "ℹ️"}
                log.info(f"{icon.get(issue['severity'], '?')} [{issue['type']}] {issue['message']}")
            log.info(f"\n总计: {len(issues)} 个问题")
        else:
            log.success("图结构完整，无问题")

    elif cmd == "mermaid":
        name = " ".join(sys.argv[3:]) if len(sys.argv) > 3 else ""
        if not name:
            log.error("需要节点名")
            raise PipelineError("mermaid 需要节点名")
        log.info(kg.export_mermaid(name))

    elif cmd == "connectivity":
        result = kg.check_l1_connectivity()
        log.info(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        if result["overall_passed"]:
            log.success("所有阶段间引用完整")
        else:
            for chk in result["checks"]:
                if not chk["passed"]:
                    log.warning(f"{chk['check_name']}: {', '.join(chk['issues'][:3])}")

    elif cmd == "similar":
        result = kg.check_similar_names()
        log.info(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        if result["total"] > 0:
            log.warning(f"发现 {result['total']} 对相似节点名")

    elif cmd == "centrality":
        result = kg.degree_centrality()
        log.info(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        if result["orphan_count"] > 0:
            log.warning(f"{result['orphan_count']} 个孤立节点")

    elif cmd == "bridge":
        result = kg.check_bridge_gaps()
        log.info(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        if result["total_gaps"] > 0:
            log.warning(f"{result['total_gaps']} 个桥接缺口")

    elif cmd == "path":
        result = kg.check_path_integrity()
        log.info(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        if result["broken_count"] > 0:
            log.warning(f"路径断裂: {result['broken_count']} 处")
        else:
            log.success("全部概念链完整")

    elif cmd == "build-order":
        result = kg.suggest_build_order()
        log.info(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        if result["cycle_warnings"]:
            for w in result["cycle_warnings"]:
                log.warning(f"{w}")

    else:
        log.error(f"未知命令: {cmd}")
        raise PipelineError(f"未知命令: {cmd}")


if __name__ == "__main__":
    try:
        main()
    except PipelineError as e:
        log.error(str(e))
        sys.exit(1)
