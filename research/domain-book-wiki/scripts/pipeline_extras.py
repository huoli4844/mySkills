"""pipeline_extras.py — Pipeline 扩展命令（fill-solutions / rollback）

v40.1: 从 dag_pipeline.py 拆分，减少核心文件体量。
包含: pipeline_fill_solutions, pipeline_rollback, _get_downstream_phases
"""

from __future__ import annotations


import os

from dag_constants import (
    DAG_DEPENDS,
    DAG_ORDER,
    DIR,
    DIR_BY_PHASE,
    PipelineArgs,
)
from dag_state import (
    _book_name,
    _load_state,
    _save_state,
    _state_path,
    _wr,
)
from log_utils import get_logger
from pipeline_auto import _fill_skeleton_solutions
from script_runner import run_content_check

log = get_logger(__name__)


def pipeline_fill_solutions(args: PipelineArgs) -> None:
    """为骨架解答生成更丰富的初始内容（从关联概念/KE/KP 提取摘要）"""
    wr = _wr(args)
    ch = args.chapter or "0"
    book_id = args.book_id
    book_name = args.book_name or _book_name(book_id)

    sol_dir = os.path.join(wr, DIR["SOLUTIONS"])
    if not os.path.isdir(sol_dir):
        log.error(f"解答目录不存在: {sol_dir}")
        return

    filled = _fill_skeleton_solutions(wr, sol_dir, book_id, book_name, ch)
    if filled > 0:
        log.success(f"填充了 {filled} 个骨架解答")
        # 重新运行内容检查验证
        cc = run_content_check(wr, quiet=False, json_mode=True)
        sol_fails = len([i for i in cc.items if i.get("severity") == "FAIL" and "Solution" in i.get("type", "")])
        log.info(f"填充后 Solution FAIL 数: {sol_fails}")
    else:
        log.info("无需填充的骨架解答")


def pipeline_fix(args: PipelineArgs) -> None:
    """v47.0: 增量修复命令 — 扫描生成文件中"无"字段，生成修复队列。

    用法: python3 dag_controller.py pipeline fix -w $BOOK_DIR --book-id XX -c N --field "solved_problem"

    功能:
      - 扫描指定章节的生成文件中"无"字段（FM + 正文内容段）
      - 生成 fix_queue.json 列出待修复字段清单
      - --auto-fill 模式尝试从文件其他部分推断内容
      - 无法自动推断的字段标记 requires_agent=true

    输出: <book_dir>/.dag/fix_queue.json
    """
    import json
    import re
    from pathlib import Path

    wr = _wr(args)
    ch = str(args.chapter or "0")
    book_id = args.book_id
    field_filter = getattr(args, "field", None)  # 可选，只检查指定字段
    auto_fill = getattr(args, "auto_fill", False)

    # 收集所有 L1 内容目录下的 .md 文件
    scan_dirs = []
    for ph, dir_name in DIR_BY_PHASE.items():
        if ph == "solutions":
            continue  # 解答目录可能不存在，跳过
        d = os.path.join(wr, dir_name)
        if os.path.isdir(d):
            scan_dirs.append((ph, d))

    if not scan_dirs:
        log.warning("未找到任何内容目录")
        return

    # 待修复队列
    fix_queue = []
    auto_filled = 0

    # ── 定义"无"字段的检测规则 ──
    # FM 字段: entity_type, domain, classification, source_from
    FM_FIELDS = ["entity_type", "domain", "classification", "source_from"]

    # 正文内容段: 标题 → 字段名映射
    CONTENT_SECTION_MAP = {
        "解决的问题": "solved_problem",
        "术语定义": "term_definition",
        "精准释义": "precise_interpretation",
        "分类与学科归属": "classification_body",
        "工作原理/构成要素": "working_principle",
        "数学模型": "mathematical_model",
        "关键参数": "key_parameters",
        "物理含义/特征": "physical_meaning",
        "技术分类": "technical_classification",
        "应用场景": "application_scenarios",
        "典型系统": "typical_systems",
        "使用价值": "usage_value",
        "工程实践要点": "engineering_practice",
        "常见误区": "common_misconceptions",
        "与相关概念的关系": "related_concepts",
        "相近概念辨析": "similar_concept_comparison",
        "发展/演进": "development_evolution",
        "关联知识要素": "related_kes",
        "图谱解析": "diagram_analysis",
        "前置知识": "prerequisites",
        "自学检验": "self_check",
    }

    for phase, scan_dir in scan_dirs:
        md_files = sorted(Path(scan_dir).glob("*.md"))
        for fp in md_files:
            try:
                content = fp.read_text(encoding="utf-8")
            except Exception as e:
                log.debug(f"读取文件失败: {e}")
                continue
            file_path = str(fp)

            # ── 检查 FM 字段 ──
            fm_match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
            fm_text = fm_match.group(1) if fm_match else ""

            for fm_field in FM_FIELDS:
                if field_filter and fm_field != field_filter:
                    continue
                # 匹配 FM 行: field_name: value
                fm_line_pat = re.compile(rf"^{re.escape(fm_field)}:\s*(.+)$", re.MULTILINE)
                fm_line_match = fm_line_pat.search(fm_text)
                if fm_line_match:
                    val = fm_line_match.group(1).strip()
                    if val in ("无", "", "null", "None"):
                        item = {
                            "field": fm_field,
                            "file": file_path,
                            "current_value": val,
                            "source": "frontmatter",
                            "phase": phase,
                            "requires_agent": True,
                            "auto_fill_hint": None,
                        }

                        # auto-fill 尝试推断
                        inferred = _try_infer_field(content, fm_field, fm_text, file_path)
                        if inferred is not None:
                            if auto_fill:
                                # 执行自动填充
                                new_content = re.sub(
                                    rf"(^{re.escape(fm_field)}:\s*).*$",
                                    rf"\1{inferred}",
                                    content,
                                    flags=re.MULTILINE,
                                )
                                try:
                                    fp.write_text(new_content, encoding="utf-8")
                                    auto_filled += 1
                                    item["auto_filled"] = True
                                    item["inferred_value"] = inferred
                                    item["requires_agent"] = False
                                    log.info(f"  ✅ 自动填充 {os.path.basename(file_path)} #{fm_field} = {inferred[:40]}...")
                                except Exception as e:
                                    log.warning(f"自动填充写入失败: {e}")
                                    item["requires_agent"] = True
                                    item["auto_fill_hint"] = inferred
                            else:
                                item["requires_agent"] = False
                                item["auto_fill_hint"] = inferred
                                item["inferred_value"] = inferred

                        fix_queue.append(item)

            # ── 检查正文内容段 ──
            for section_hint, field_name in CONTENT_SECTION_MAP.items():
                if field_filter and field_name != field_filter:
                    continue
                # 匹配 "### N. 章标题" 或 "#### N. 节标题"
                section_pat = re.compile(
                    rf"(?:###|####)\s+\d+\.?\s*{re.escape(section_hint)}",
                    re.IGNORECASE,
                )
                sec_match = section_pat.search(content)
                if not sec_match:
                    continue

                # 提取该节内容（到下一个同级或上级标题为止）
                sec_start = sec_match.end()
                next_heading = re.search(r"^(?:###|####|##)\s", content[sec_start:], re.MULTILINE)
                sec_end = sec_start + next_heading.start() if next_heading else len(content)
                section_body = content[sec_start:sec_end].strip()

                if not section_body or section_body in ("无", "null", "None", "[]", "['无']", "['']"):
                    item = {
                        "field": field_name,
                        "file": file_path,
                        "current_value": section_body[:80],
                        "source": "content_section",
                        "phase": phase,
                        "requires_agent": True,
                        "auto_fill_hint": None,
                    }

                    # auto-fill 尝试推断
                    inferred = _try_infer_content_section(content, field_name, fm_text)
                    if inferred is not None:
                        if auto_fill:
                            # 用推断值替换空内容
                            replacement = f"\n{inferred}"
                            new_content = content[:sec_start] + replacement + content[sec_start + len(section_body):]
                            try:
                                fp.write_text(new_content, encoding="utf-8")
                                auto_filled += 1
                                item["auto_filled"] = True
                                item["inferred_value"] = inferred[:200]
                                item["requires_agent"] = False
                                log.info(f"  ✅ 自动填充 {os.path.basename(file_path)} #{field_name}")
                            except Exception as e:
                                log.warning(f"自动填充写入失败: {e}")
                                item["requires_agent"] = True
                                item["auto_fill_hint"] = inferred[:200]
                        else:
                            item["requires_agent"] = False
                            item["auto_fill_hint"] = inferred[:200]
                            item["inferred_value"] = inferred[:200]

                    fix_queue.append(item)

    # ── 输出结果 ──
    dag_dir = os.path.join(wr, ".dag")
    os.makedirs(dag_dir, exist_ok=True)
    output_path = os.path.join(dag_dir, "fix_queue.json")

    summary = {
        "book_id": book_id,
        "chapter": ch,
        "total_items": len(fix_queue),
        "auto_filled": auto_filled,
        "requires_agent": sum(1 for x in fix_queue if x.get("requires_agent")),
        "auto_fillable": sum(1 for x in fix_queue if not x.get("requires_agent", True)),
        "fix_queue": fix_queue,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    # ── 终端输出 ──
    log.info(f"📋 修复队列已生成: {output_path}")
    log.info(f"   总计待修复: {len(fix_queue)} 项")
    log.info(f"   需 Agent 修复: {summary['requires_agent']} 项")
    log.info(f"   可自动填充: {summary['auto_fillable']} 项")
    if auto_fill:
        log.success(f"   已自动填充: {auto_filled} 项")

    # 分组按字段统计
    from collections import Counter
    field_counts = Counter(item["field"] for item in fix_queue)
    for field, count in field_counts.most_common(10):
        requires = sum(1 for x in fix_queue if x["field"] == field and x.get("requires_agent"))
        log.info(f"   {field}: {count} 项 (需 Agent: {requires})")


def _try_infer_field(content: str, fm_field: str, fm_text: str, file_path: str) -> str | None:
    """尝试从文件内容推断 FM 字段值。

    Args:
        content: 完整文件内容
        fm_field: FM 字段名
        fm_text: FM 文本（仅 --- 块内）
        file_path: 文件路径（用于上下文日志）

    Returns:
        推断值，无法推断返回 None
    """
    import re

    if fm_field == "source_from":
        # 从正文中的 "来源：第X章 §Y 节" 提取
        src_match = re.search(r"来源：第(\d+)章\s*§+([\d.]+)\s*节", content)
        if src_match:
            return f"§{src_match.group(2)}"
        # 从 chapter_num 推断
        ch_match = re.search(r"chapter_num:\s*(\d+)", fm_text)
        if ch_match:
            return f"第{ch_match.group(1)}章"

    if fm_field == "classification":
        # 从 "### 3. 分类与学科归属" 节提取分类信息
        class_match = re.search(
            r"###\s*\d+\.?\s*分类与学科归属.*?\n-\s*\*\*分类\*\*[：:]\s*(.+?)(?:\n|$)",
            content, re.DOTALL,
        )
        if class_match:
            return class_match.group(1).strip()

    if fm_field == "domain":
        # 从 "学科领域" 提取
        domain_match = re.search(r"\*\*学科领域\*\*[：:]\s*(.+?)(?:\n|$)", content)
        if domain_match:
            return domain_match.group(1).strip()

    if fm_field == "entity_type":
        # 从 type 字段推断
        type_match = re.search(r"type:\s*(.+)", fm_text)
        if type_match:
            t = type_match.group(1).strip()
            if t == "concept":
                return "核心概念"
            elif t == "knowledge-element":
                return "知识要素"
            elif t == "entity":
                return "实体"

    return None


def _try_infer_content_section(content: str, field_name: str, fm_text: str) -> str | None:
    """尝试从文件其他部分推断正文内容段的值。

    主要推断策略:
      - solved_problem: 从 term_definition 首句提取问题描述
      - term_definition: 从 definition_sentence / 文件第一段提取
      - precise_interpretation: 从 term_definition 提取引文
    """
    import re

    if field_name == "solved_problem":
        # 从术语定义中推断解决的问题
        def_match = re.search(
            r"###\s*\d+\.?\s*术语定义\s*\n+(.+?)(?:\n###|\n##|\Z)",
            content, re.DOTALL,
        )
        if def_match:
            def_text = def_match.group(1).strip()
            # 提取 **术语名** 后面的内容作为问题描述
            bold_match = re.search(r"\*\*[^*]+\*\*\s*(?:（[^）]*）)?\s*(.+)", def_text)
            if bold_match:
                desc = bold_match.group(1).strip()
                # 如果描述以"是"开头，尝试提取问题
                if len(desc) > 10:
                    return f"解决{desc[:60]}..." if len(desc) > 60 else f"解决{desc}"

    if field_name == "term_definition":
        # 从 FM 的 name 字段 + 第一部分内容推断
        name_match = re.search(r"name:\s*(.+)", fm_text)
        concept_name = name_match.group(1).strip() if name_match else ""
        if concept_name:
            # 找第一个 ## 之后的实质性段落
            after_heading = re.search(r"^# .+\n\n(.+?)(?:\n##|\Z)", content, re.DOTALL)
            if after_heading:
                para = after_heading.group(1).strip()
                if para and para not in ("无", ""):
                    return f"**{concept_name}** {para[:200]}"

    if field_name == "precise_interpretation":
        # 从语源/出处提取
        src_match = re.search(r">\s*(.+?)\n>\s*来源：", content, re.DOTALL)
        if src_match:
            quote = src_match.group(1).strip()
            if quote and quote != "无":
                return f"> {quote}\n> 来源：待补充"

    return None


def pipeline_rollback(args: PipelineArgs) -> None:
    """回滚指定阶段：重置状态 + 阻断下游（不删除文件，增量构建多章共存）"""
    wr = _wr(args)
    book_id = args.book_id
    ch = args.chapter or "0"
    phase = args.phase

    if phase not in DAG_ORDER:
        log.error(f"未知阶段: {phase}")
        return

    st = _load_state(_state_path(wr, book_id, ch))
    phases = st.get("phases", {})

    # 查找下游阶段
    downstream = _get_downstream_phases(phase)
    all_to_reset = [phase, *downstream]

    log.info(f"回滚阶段: {phase}")
    if downstream:
        log.info(f"下游阶段也将重置: {', '.join(downstream)}")

    for ph in all_to_reset:
        # 1. 重置状态为 pending
        if ph in phases:
            phases[ph]["status"] = "pending"
            phases[ph].pop("completed_at", None)
            log.info(f"  ↩️ {ph}: 状态重置为 pending")

        # 2. 增量构建：不删除文件，仅重置状态（多章共存，互不干扰）
        #    如需重建同一章节，build_kb_files.py 会覆盖同名文件

    _save_state(_state_path(wr, book_id, ch), st)
    log.success(f"回滚完成，共重置 {len(all_to_reset)} 个阶段")


def _get_downstream_phases(phase: str) -> list[str]:
    """递归查找依赖于指定阶段的所有下游阶段"""
    downstream = []
    for p in DAG_ORDER:
        deps = DAG_DEPENDS.get(p, [])
        if phase in deps and p not in downstream:
            downstream.append(p)
            # 递归查找
            for d in _get_downstream_phases(p):
                if d not in downstream:
                    downstream.append(d)
    return downstream


# ---------------------------------------------------------------------------
# v50.7: 内容深度 Agent 二次审核
# ---------------------------------------------------------------------------

# 类型 → 关键审核节段映射（提取哪些 ### 节内容供 Agent 评审）
_REVIEW_SECTIONS = {
    "concept": ["mathematical_model", "theoretical_basis", "application_scenarios",
                 "engineering_practices", "core_concept_map_analysis"],
    "kp": ["theoretical_basis", "key_details", "derivation_analysis",
           "application_scenarios", "typical_examples"],
    "sp": ["core_operation", "operation_flow_analysis", "typical_practical_cases",
           "competency_standards"],
    "scene": ["scene_elements", "node_descriptions", "solution_detail",
              "boundary_conditions", "key_techniques"],
}

# 无标记计数阈值 → 质量分层
def _tier_from_stats(line_count: int, wu_count: int, wikilink_count: int) -> str:
    if wu_count >= 13:
        return "D"
    if wu_count >= 8:
        return "C"
    if line_count >= 250 and wu_count <= 3 and wikilink_count >= 10:
        return "A"
    if line_count >= 130 and wu_count <= 7:
        return "B"
    return "C"


def _get_type_from_dir(dir_name: str) -> str | None:
    """目录名 → 节点类型"""
    _DIR_TYPE_MAP = {
        "30_核心概念": "concept", "40_知识要素": "ke",
        "50_知识点": "kp", "60_技能点": "sp",
        "70_应用场景": "scene", "80_实体": "entity",
        "90_习题": "exercise", "90_习题/解答": "solution",
    }
    return _DIR_TYPE_MAP.get(dir_name)


def collect_content_review_batch(wr: str, book_id: str, chapter: str) -> str:
    """收集当前章已生成文件的节段内容 + 统计指标，打包为 review_batch.json。

    Returns:
        review_batch.json 路径（供 Agent 读取）
    """
    import json
    import re

    batch = {
        "book_id": book_id,
        "chapter": chapter,
        "wiki_root": wr,
        "files": [],
        "summary": {"total": 0, "A": 0, "B": 0, "C": 0, "D": 0},
    }

    # 扫描所有 L1 内容目录
    for phase, dir_name in DIR_BY_PHASE.items():
        if phase == "solutions":
            continue  # 解答由脚本自动生成，不评审
        node_type = _get_type_from_dir(dir_name)
        if not node_type:
            continue
        content_dir = os.path.join(wr, dir_name)
        if not os.path.isdir(content_dir):
            continue

        review_fields = _REVIEW_SECTIONS.get(node_type, [])

        for fname in sorted(os.listdir(content_dir)):
            if not fname.endswith(".md"):
                continue
            fpath = os.path.join(content_dir, fname)
            with open(fpath, encoding="utf-8") as f:
                content = f.read()

            # 获取 frontmatter name
            name_match = re.search(r"^name:\s*(.+)$", content, re.MULTILINE)
            name = name_match.group(1).strip() if name_match else fname.replace(".md", "")

            # 行数 + "无"密度 + wikilink 计数
            lines = content.split("\n")
            line_count = len(lines)
            wu_count = len(re.findall(r'^\s*无[。]?\s*$', content, re.MULTILINE))
            wikilink_count = len(re.findall(r'\[\[', content))
            tier = _tier_from_stats(line_count, wu_count, wikilink_count)

            # 提取关键节段内容
            sections = {}
            for field in review_fields:
                # 在 body 中找 ### 标题与字段名相近的节
                # Front Matter 中已有字段值
                fm_match = re.search(rf"^{field}:\s*(.+)$", content, re.MULTILINE)
                if fm_match:
                    val = fm_match.group(1).strip()
                    sections[field] = val[:200] if val and val != "无" else "无"

                # 尝试在 body 中找对应 ### 节
                # 字段名 → 可能的中文标题
                zh_titles = {
                    "mathematical_model": "数学模型",
                    "theoretical_basis": "理论基础",
                    "application_scenarios": "应用场景",
                    "engineering_practices": "工程实践",
                    "core_concept_map_analysis": "概念图解析",
                    "key_details": "关键细节",
                    "derivation_analysis": "推导分析",
                    "typical_examples": "典型例题",
                    "core_operation": "核心操作",
                    "operation_flow_analysis": "操作流程解析",
                    "typical_practical_cases": "典型实操案例",
                    "competency_standards": "能力标准",
                    "scene_elements": "场景要素",
                    "node_descriptions": "节点描述",
                    "solution_detail": "方案详解",
                    "boundary_conditions": "边界条件",
                    "key_techniques": "关键技术",
                }
                zh = zh_titles.get(field)
                if zh:
                    body = content.split("---\n", 2)[-1] if content.count("---") >= 2 else content
                    sec_match = re.search(
                        rf"###\s+\d*\.?\s*{zh}\s*\n(.*?)(?=\n###\s|\Z)",
                        body, re.DOTALL
                    )
                    if sec_match:
                        sec_content = sec_match.group(1).strip()[:300]
                        sections[f"{field}_body"] = sec_content if sec_content else "无"

            file_entry = {
                "name": name,
                "file": fname,
                "type": node_type,
                "phase": phase,
                "stats": {
                    "lines": line_count,
                    "wu_count": wu_count,
                    "wikilinks": wikilink_count,
                    "tier": tier,
                },
                "sections": sections,
            }
            batch["files"].append(file_entry)
            batch["summary"]["total"] += 1
            batch["summary"][tier] = batch["summary"].get(tier, 0) + 1

    # 写入 review_batch.json
    batch_dir = os.path.join(wr, ".dag", f"第{chapter}章")
    os.makedirs(batch_dir, exist_ok=True)
    batch_path = os.path.join(batch_dir, "review_batch.json")
    with open(batch_path, "w", encoding="utf-8") as f:
        json.dump(batch, f, ensure_ascii=False, indent=2)

    log.info(f"内容审核批次已生成: {batch_path}")
    log.info(f"  {batch['summary']['total']} 文件 — "
             f"A:{batch['summary'].get('A',0)} B:{batch['summary'].get('B',0)} "
             f"C:{batch['summary'].get('C',0)} D:{batch['summary'].get('D',0)}")

    if batch["summary"].get("D", 0) > 0:
        d_files = [f for f in batch["files"] if f["stats"]["tier"] == "D"]
        log.warning(f"  D-tier 空壳文件 ({len(d_files)}):")
        for f in d_files[:5]:
            log.warning(f"    {f['type']}/{f['file']} (wu={f['stats']['wu_count']})")

    return batch_path


def pipeline_review(args: PipelineArgs) -> None:
    """v50.7: 内容深度 Agent 二次审核 — 收集关键节段 → 生成 review_batch.json。

    用法: dag_controller.py pipeline review -w BOOK_DIR --book-id XX
         （扫描当前章，自动从 pipeline state 获取章节号）
    """
    wr = _wr(args)
    book_id = args.book_id

    # 自动确定章节号：从 pipeline state 文件推断，或从 args
    ch = str(getattr(args, "chapter", "0") or "0")
    if ch == "0":
        # 尝试从 .dag/ 推断最新处理的章节
        dag_dir = os.path.join(wr, ".dag")
        if os.path.isdir(dag_dir):
            chapters = sorted(
                d for d in os.listdir(dag_dir)
                if d.startswith("第") and d.endswith("章")
            )
            if chapters:
                import re
                m = re.search(r"第(\d+)章", chapters[-1])
                if m:
                    ch = m.group(1)
                    log.info(f" 自动检测到章节: 第{ch}章")

    batch_path = collect_content_review_batch(wr, book_id, ch)
    log.info(f"运行: cat {batch_path}")
    log.info("然后 Agent 读取 review_batch.json → 对 D/C-tier 文件执行深度修复")
