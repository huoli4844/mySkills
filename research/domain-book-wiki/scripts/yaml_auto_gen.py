"""yaml_auto_gen.py — LLM 驱动的 YAML 自动生成框架

v45.2: 新增。将"Agent 手工读源文→判断三标准→写 YAML"流程化为可编程管道。
配合 pipeline batch 实现全自动知识库构建。

设计理念:
  1. Python 负责: TOC 解析、容器提取、骨架生成、格式校验
  2. Agent/LLM 负责: 三标准判断、定义句提取、概念归类
  3. 交互模式: 收集所有容器候选 → 批量交给 Agent 判断 → 一次写入

用法:
  # 预览模式: 扫描章节，输出候选概念列表
  python3 yaml_auto_gen.py scan -w BOOK_DIR -c 1

  # 生成骨架: 对指定章节生成 YAML 骨架文件
  python3 yaml_auto_gen.py skeleton -w BOOK_DIR -c 1

  # 批量扫描整本书
  python3 yaml_auto_gen.py scan-all -w BOOK_DIR --book-id XX
"""

import json
import os
import re
from typing import Any

from dag_constants import DIR, PipelineError
from log_utils import get_logger

log = get_logger(__name__)

# 章节规模阈值
SMALL_CHAPTER = 500       # <500 行 → 小章
MEDIUM_CHAPTER = 1500     # 500-1500 → 中等章
LARGE_CHAPTER = 1500      # >1500 → 大章


def load_chapter_toc(wr: str, ch: str) -> dict[str, Any]:
    """加载章节 TOC JSON。"""
    toc_path = os.path.join(wr, ".dag", f"第{ch}章", "chapter_toc.json")
    if not os.path.exists(toc_path):
        raise PipelineError(f"chapter_toc.json 不存在: {toc_path}")
    with open(toc_path, encoding="utf-8") as f:
        return json.load(f)


def load_source_text(wr: str, ch: str) -> str:
    """加载章节源文全文。"""
    import glob

    pattern = os.path.join(wr, DIR["SOURCE"], f"第{ch}章*.md")
    files = sorted(glob.glob(pattern))
    if not files:
        raise PipelineError(f"未找到源文件: {pattern}")
    with open(files[0], encoding="utf-8") as f:
        return f.read()


def _parse_source_headings(wr: str, ch: str) -> tuple[list[dict], int]:
    """直接从源文解析标题结构（无需 TOC JSON 回退方案）。

    返回: (containers, container_level)
      containers 格式与 chapter_toc.json 兼容
      container_level 是自适应检测到的容器层级
    """
    source = load_source_text(wr, ch)
    lines = source.split("\n")
    total_lines = len(lines)

    # Step 1: 提取所有 ## / ### 标题及其行号
    raw_headings = []
    skip_keywords = ["内容提要", "思考题", "习题"]
    # 单独过滤结尾关键字
    skip_ends = ["小结"]
    for i, line in enumerate(lines, start=1):
        m = re.match(r"^(#{2,3})\s+(.+)", line)
        if not m:
            continue
        title = m.group(2).strip()
        # 清理标题中的转义伪影（如 5.3.\*1 → 5.3.*1）
        title = title.replace("\\*", "*")
        # 过滤非内容标题（开头匹配）
        if any(title.startswith(w) for w in skip_keywords):
            continue
        # 过滤结尾关键字（如"3.4 小结"）
        if any(title.endswith(w) for w in skip_ends):
            continue
        # 跳过章标题（如"第3章 屏蔽" — 它们是章节标题不是概念）
        if re.match(r"^第\d+章\s", title):
            continue
        # 过滤纯编号条目（1. xxx, 2. xxx, 3、xxx — 它们是子条目不是独立标题）
        if re.match(r"^\d[、．]", title) or re.match(r"^\d\. (?!\d)", title):
            continue
        raw_headings.append({"line": i, "title": title, "level": len(m.group(1))})

    if not raw_headings:
        return [], 3

    # Step 1.5: 检测每个标题的编号深度
    # 如 "3.1 屏蔽原理" → depth=2, "3.1.1 自屏蔽" → depth=3
    for h in raw_headings:
        parts = h["title"].split()
        num_part = parts[0] if parts else ""
        h["num_depth"] = len(num_part.split(".")) if re.match(r"^[\d.]+$", num_part) else 1
        h["num_prefix"] = num_part  # 数字编号前缀

    # Step 2: 计算每个标题的 line_end（同编号深度或更浅的下一个标题的前一行）
    for idx, h in enumerate(raw_headings):
        next_start = total_lines + 1
        for j in range(idx + 1, len(raw_headings)):
            # 跳到同深度或更浅深度的下一个标题（同级/父级跳转）
            nj = raw_headings[j]
            if nj["level"] == h["level"] and nj["num_depth"] <= h["num_depth"]:
                next_start = nj["line"]
                break
        h["line_end"] = next_start - 1
        h["span_lines"] = h["line_end"] - h["line"] + 1

    # Step 3: 自适应检测容器层级
    level_stats = {}
    for h in raw_headings:
        lv = h["level"]
        if lv not in level_stats:
            level_stats[lv] = {"count": 0, "total_lines": 0}
        level_stats[lv]["count"] += 1
        level_stats[lv]["total_lines"] += h["span_lines"]

    for lv in level_stats:
        cnt = level_stats[lv]["count"]
        level_stats[lv]["avg_lines"] = (
            round(level_stats[lv]["total_lines"] / cnt, 1) if cnt > 0 else 0
        )

    # 找最佳容器层：标题数 ≥ 2 且平均行数在 [20, 300] 的最深层
    container_level = 3  # 默认
    has_l3 = any(h["level"] == 3 for h in raw_headings)
    for lv in sorted(level_stats.keys(), reverse=True):
        s = level_stats[lv]
        if s["count"] >= 2 and 20 <= s["avg_lines"] <= 300:
            container_level = lv
            break

    # 兜底：没有 ### 标题时，只要 ## 标题 ≥ 3 个就用 Lv2 作为容器层
    if not has_l3 and level_stats.get(2, {}).get("count", 0) >= 3:
        container_level = 2

    # Step 4: 构建容器（只取容器层的标题）
    containers = []
    seen_titles = set()
    for h in raw_headings:
        if h["level"] != container_level:
            continue
        title = h["title"]
        if title in seen_titles:
            continue
        seen_titles.add(title)

        # 统计支撑材料
        sl = max(0, h["line"] - 1)
        el = min(total_lines, h["line_end"])
        container_text = "\n".join(lines[sl:el])
        support_count = 0
        support_count += len(re.findall(r"\$\$.*?\$\$", container_text, re.DOTALL))
        support_count += len(re.findall(r"!\[.*?\]\(.*?\)", container_text))

        containers.append({
            "title": title,
            "level": container_level,
            "line": h["line"],
            "line_end": h["line_end"],
            "span_lines": h["span_lines"],
            "support_count": support_count,
        })

    return containers, container_level


def extract_container_candidates(
    wr: str, ch: str, min_lines: int = 30
) -> list[dict[str, Any]]:
    """从 chapter_toc.json 或源文标题提取候选概念容器。

    优先读取 chapter_toc.json（pipeline auto 生成的带容器分段的 TOC）。
    回退到直接从源文提取 ### 标题作为候选。

    返回每个候选容器:
      {
        "title": str,          # 容器标题
        "level": int,          # 标题层级 (2/3/4)
        "line_start": int,     # 起始行号
        "line_end": int,       # 结束行号 (含)
        "line_count": int,     # 行数
        "support_count": int,  # 支撑材料数 (公式+图+表)
        "has_substructure": bool,  # 是否有子标题
        "passes_filter": bool,     # 是否通过三标准
        "is_concept": bool,        # 是否判定为核心概念
      }
    """
    # 优先尝试 TOC JSON，回退到直接解析源文标题
    try:
        toc = load_chapter_toc(wr, ch)
        containers = toc.get("containers", [])
        min_concept_level = toc.get("container_level", 3)  # 自适应容器层级
        log.info(f"  📋 使用 chapter_toc.json 容器分段 (Lv{min_concept_level})")
    except PipelineError:
        containers, min_concept_level = _parse_source_headings(wr, ch)
        log.info(f"  📋 chapter_toc.json 不存在，直接从源文 ### 标题提取候选 (Lv{min_concept_level})")

    source_text = load_source_text(wr, ch)
    source_lines = source_text.split("\n")

    candidates = []
    for c in containers:
        title = c.get("title", "")
        level = c.get("level", 2)
        line_start = c.get("line", c.get("line_start", 0))
        line_end = c.get("line_end", 0)

        # 跳过非概念级容器 (level 1 = 章标题, level >= 4 = 太细)
        if level < 2 or level >= 4:
            continue

        # 计算行数
        if isinstance(line_start, int) and isinstance(line_end, int):
            line_count = max(0, line_end - line_start + 1)
        else:
            line_count = 0

        # 提取容器内文本
        container_text = ""
        if line_start and line_end and 0 < line_start <= len(source_lines):
            sl = max(0, line_start - 1)  # 转0-index
            el = min(len(source_lines), line_end)
            container_text = "\n".join(source_lines[sl:el])

        # 统计支撑材料
        support_count = c.get("support_count", 0)
        if not support_count:
            support_count += len(re.findall(r"\$\$.*?\$\$", container_text, re.DOTALL))
            support_count += len(re.findall(r"!\[.*?\]\(.*?\)", container_text))
            support_count += len(re.findall(r"图\s*\d+[-\.]?\d*", container_text))
            support_count += len(re.findall(r"表\s*\d+[-\.]?\d*", container_text))

        # 检查子结构
        has_substructure = c.get("has_substructure", False) or (
            bool(re.search(r"^#{3,5}\s", container_text, re.MULTILINE))
            and line_count >= 20
        )

        # 三标准判断（调低阈值以覆盖更多候选供 Agent 判断）
        passes = (
            line_count >= 5  # 最低行数（对单一 ## 级别的教材放宽到5行）
            and support_count >= 1  # 最少支撑材料
            and level == min_concept_level  # 容器层级（自适应：## 或 ###）
        )

        candidates.append({
            "title": title,
            "level": level,
            "line_start": line_start,
            "line_end": line_end,
            "line_count": line_count,
            "support_count": support_count,
            "has_substructure": has_substructure,
            "passes_filter": passes,
            "is_concept": False,  # Agent 最终判定
        })

    return candidates


def extract_definition_sentences(text: str, title: str, max_len: int = 200) -> list[str]:
    """从容器文本中提取候选定义句。

    规则: 前 max_len 字符内含标记词(是指/称为/即/定义为/指的是)。
    返回符合规则的句子列表。
    """
    # 取文本前 max_len 字符
    head = text[:max_len]

    # 分句
    sentences = re.split(r"[。；\n]", head)
    candidates = []

    markers = ["是指", "称为", "即", "定义为", "指的是", "所谓"]

    for sent in sentences:
        sent = sent.strip()
        if len(sent) < 5:
            continue
        # 跳过纯标题行
        if re.match(r"^#+\s", sent):
            continue
        for marker in markers:
            if marker in sent:
                candidates.append(sent)
                break

    return candidates


def generate_yaml_skeleton(
    wr: str, ch: str, concept_candidates: list[dict], ke_candidates: list[dict]
) -> dict[str, Any]:
    """为章节生成 YAML 骨架结构。

    返回 dict，可直接写入 concepts.yaml / kes.yaml 等。
    """

    chapter_title = f"第{ch}章"
    source_text = load_source_text(wr, ch)

    # 尝试从源文件第一行获取章标题
    first_line = source_text.split("\n")[0].strip().lstrip("#").strip()
    if first_line:
        chapter_title = first_line

    result = {
        "chapter": ch,
        "title": chapter_title,
        "concepts": [],
        "kes": [],
        "entities": [],
    }

    for c in concept_candidates:
        title = c.get("title", "")
        container_text = source_text.split("\n")
        sl = max(0, c.get("line_start", 1) - 1)
        el = min(len(container_text), c.get("line_end", len(container_text)))
        ct = "\n".join(container_text[sl:el])

        def_sentences = extract_definition_sentences(ct, title)
        definition = def_sentences[0] if def_sentences else ""

        # 提取公式引用
        formulas = re.findall(r"\$\$(.*?)\$\$", ct, re.DOTALL)
        formula_refs = [f.strip()[:100] for f in formulas[:5]]

        # 提取图片引用
        figure_refs = re.findall(r"图\s*(\d+[-\.]?\d*)", ct)[:5]

        concept_entry = {
            "name": title,
            "file": title,
            "fm": {
                "type": "core_concept",
                "confidence": 0.95,
                "bloom_level": "知道→理解",
                "chapter": ch,
                "tags": ["core_concept"],
            },
            "bd": {
                "definition_sentence": definition,
                "learning_objectives": [],
                "prerequisites": [],
                "core_content": "",
                "formula_references": formula_refs,
                "figure_references": figure_refs,
                "key_elements": [],
                "related_knowledge_points": [],
                "self_check": [],
                "additional_explanations": [],
            },
        }
        result["concepts"].append(concept_entry)

    for ke in ke_candidates:
        ke_entry = {
            "name": ke.get("title", ""),
            "file": ke.get("title", ""),
            "fm": {
                "type": "knowledge_element",
                "confidence": 0.85,
                "chapter": ch,
            },
            "bd": {
                "definition": "",
                "formula": "",
                "unit": "",
                "source_concept": "",
            },
        }
        result["kes"].append(ke_entry)

    return result


def scan_all_chapters(wr: str) -> list[dict[str, Any]]:
    """扫描整本书所有章节，生成候选报告。

    返回每章的摘要信息。
    """

    src_dir = os.path.join(wr, DIR["SOURCE"])
    if not os.path.isdir(src_dir):
        return []

    reports = []
    for fname in sorted(os.listdir(src_dir)):
        m = re.match(r"第(\d+)章\s.*\.md$", fname)
        if not m:
            continue
        ch = m.group(1)
        fpath = os.path.join(src_dir, fname)

        # 计算行数
        with open(fpath, encoding="utf-8") as f:
            lines = f.readlines()
        total_lines = len(lines)

        # 检查 TOC 是否存在
        toc_path = os.path.join(wr, ".dag", f"第{ch}章", "chapter_toc.json")
        toc_exists = os.path.exists(toc_path)

        # 粗略分类
        if total_lines < SMALL_CHAPTER:
            scale = "small"
            suggested_concepts = "1-2"
        elif total_lines < MEDIUM_CHAPTER:
            scale = "medium"
            suggested_concepts = "2-4"
        else:
            scale = "large"
            suggested_concepts = "4-8"

        # 尝试提取候选
        candidates = []
        try:
            candidates = extract_container_candidates(wr, ch)
        except Exception as e:
            log.warning(f"容器候选提取失败: {e}")
            pass

        passed = [c for c in candidates if c.get("passes_filter")]
        failed = [c for c in candidates if not c.get("passes_filter")]

        reports.append({
            "chapter": ch,
            "filename": fname,
            "total_lines": total_lines,
            "scale": scale,
            "suggested_concepts": suggested_concepts,
            "toc_exists": toc_exists,
            "candidates_total": len(candidates),
            "candidates_passed": len(passed),
            "candidates_failed": len(failed),
            "concept_names": [c["title"] for c in passed],
            "ke_names": [c["title"] for c in failed if c.get("line_count", 0) >= 20],
        })

    return reports


def print_scan_report(reports: list[dict[str, Any]]) -> None:
    """打印扫描报告。"""
    total_concepts = sum(r["candidates_passed"] for r in reports)
    total_kes = sum(
        len(r.get("ke_names", [])) for r in reports
    )
    total_lines = sum(r["total_lines"] for r in reports)

    log.info("=" * 70)
    log.info(f"  全书扫描报告: {len(reports)} 章, {total_lines} 行")
    log.info(f"  预估核心概念: {total_concepts} 个")
    log.info(f"  预估知识要素: {total_kes} 个")
    log.info("=" * 70)

    for r in reports:
        icon = "✅" if r["toc_exists"] else "⚠️"
        log.info(
            f"  {icon} 第{r['chapter']}章 [{r['scale']:6s}] {r['total_lines']:4d}行 "
            f"→ 概念{r['candidates_passed']}个, KE{len(r.get('ke_names',[]))}个"
        )
        if r.get("concept_names"):
            for name in r["concept_names"][:3]:
                log.info(f"      📌 {name}")
            if len(r["concept_names"]) > 3:
                log.info(f"      ... 共{len(r['concept_names'])}个")


# CLI 入口
if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser(description="YAML Auto Generator v45.2")
    sp = p.add_subparsers(dest="cmd")

    # scan: 单章扫描
    sc = sp.add_parser("scan", help="扫描单章候选概念")
    sc.add_argument("-w", "--wiki-root", required=True)
    sc.add_argument("-c", "--chapter", required=True)

    # scan-all: 全书扫描
    sa = sp.add_parser("scan-all", help="扫描全书候选概念")
    sa.add_argument("-w", "--wiki-root", required=True)
    sa.add_argument("--book-id")

    # skeleton: 生成 YAML 骨架
    sk = sp.add_parser("skeleton", help="生成 YAML 骨架")
    sk.add_argument("-w", "--wiki-root", required=True)
    sk.add_argument("-c", "--chapter", required=True)

    args = p.parse_args()

    if args.cmd == "scan":
        wr = os.path.abspath(args.wiki_root)
        candidates = extract_container_candidates(wr, args.chapter)
        for c in candidates:
            status = "✅ 概念" if c["passes_filter"] else "⬇️ KE"
            log.info(
                f"  {status} | Lv{c['level']} | {c['line_count']:4d}行 | "
                f"支撑{c['support_count']} | {'有子结构' if c['has_substructure'] else '无子结构'} | "
                f"{c['title']}"
            )
        passed = [c["title"] for c in candidates if c["passes_filter"]]
        log.info(f"\n概念候选: {passed}")

    elif args.cmd == "scan-all":
        wr = os.path.abspath(args.wiki_root)
        reports = scan_all_chapters(wr)
        print_scan_report(reports)

    elif args.cmd == "skeleton":
        wr = os.path.abspath(args.wiki_root)
        candidates = extract_container_candidates(wr, args.chapter)
        concepts = [c for c in candidates if c["passes_filter"]]
        kes = [c for c in candidates if not c["passes_filter"]]
        skeleton = generate_yaml_skeleton(wr, args.chapter, concepts, kes)
        print(json.dumps(skeleton, ensure_ascii=False, indent=2))
