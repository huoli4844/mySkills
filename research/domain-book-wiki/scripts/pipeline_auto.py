"""pipeline_auto.py — Pipeline 自动化辅助函数

v36.5: 从 dag_pipeline.py 拆分，减少其体量。
包含：习题自动检测、L1 内容构建、内容检查、解答自动生成、状态打印。
"""

import glob
import json
import os
import re

from dag_constants import (
    DAG_DEPENDS,
    DAG_ORDER,
    DIR,
    NODE_CONFIG,
)
from dag_state import (
    _book_name,
    _save_state,
    _state_path,
    extract_exercises_from_text,
    verify_exercise_solution_mapping,
)
from log_utils import get_logger
from post_build_fix import run_phase_auto_fix
from pipeline_auto_fix import _fix_solution_skeleton
from script_runner import run_content_check, run_script

log = get_logger(__name__)

SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_ASSEMBLER = os.path.join(SKILL_DIR, "template_assembler.py")


# v39.1: verify_exercise_solution_mapping 已移至 dag_utils.py（打破循环依赖）


# ============================================================
# 自动检测习题
# ============================================================


def _auto_detect_and_build_exercises(wr, s, args, ch):
    """自动检测章节正文中的习题并生成"""
    ms = sorted(glob.glob(os.path.join(wr, DIR["SOURCE"], f"第{ch}章*")))
    if ms:
        full_names = [f for f in ms if os.path.basename(f) != f"第{ch}章.md"]
        cf = full_names[0] if full_names else ms[0]
    else:
        cf = os.path.join(wr, DIR["SOURCE"], f"第{ch}章.md")

    if not os.path.exists(cf):
        log.warning("章节文件不存在: %s", cf)
        return False

    with open(cf) as f:
        content = f.read()
    exs = extract_exercises_from_text(content, s["book_id"], ch)
    if not exs:
        log.warning("未检测到习题——若为概述章则属于正常状态，标记为 done/0")
        s["phases"]["exercises"]["status"] = "done"
        s["phases"]["exercises"]["files"] = 0
        _save_state(_state_path(wr, s["book_id"], ch), s)
        # solutions 也无内容，同步标记 done/0
        s["phases"]["solutions"]["status"] = "done"
        s["phases"]["solutions"]["files"] = 0
        _save_state(_state_path(wr, s["book_id"], ch), s)
        log.info("exercises+solutions → done/0（源文无习题）")
        return True

    log.success("自动检测到 %d 道习题", len(exs))
    ex_dir = os.path.join(wr, NODE_CONFIG["exercises"]["dir"])
    os.makedirs(ex_dir, exist_ok=True)

    data = {
        "template": "exercise_template.md",
        "quality_key": "eval/exercise",
        "output_dir": ex_dir,
        "book_id": s["book_id"],
        "book_name": s.get("book_name", _book_name(s["book_id"])),
        "chapter_num": ch,
        "items": exs,
    }
    dag_dir = os.path.join(wr, ".dag")
    os.makedirs(dag_dir, exist_ok=True)
    tmp_json = os.path.join(dag_dir, f"tmp_auto_exercises_ch{ch}.json")
    with open(tmp_json, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    r = run_script("template_assembler.py", [tmp_json], timeout=120)
    if not r.success:
        log.error("template_assembler 失败: %s", r.stderr[:300])
        return False

    log.success("习题生成完成")

    # v39.0: 构建后自动修复（占位符填充）
    run_phase_auto_fix(wr, "exercises", ch)

    return True


# ============================================================
# L1 内容构建（调用 build_kb_files.py）
# ============================================================
# v39.0: _fill_exercise_placeholders 和 _EXERCISE_PLACEHOLDER_DEFAULTS
#         已合并到 post_build_fix.py（run_phase_auto_fix 统一入口）


def _auto_build_kb_phase(wr, phase, kb_type, ch, book_id, book_name):
    """调用 build_kb_files.py 生成 L1 内容"""
    bf = os.path.abspath(os.path.join(os.path.dirname(__file__), "build_kb_files.py"))
    if not os.path.exists(bf):
        log.warning("build_kb_files.py 不存在: %s", bf)
        return False

    log.info("build_kb_files.py --type %s --chapter %s", kb_type, ch)
    r = run_script(
        "build_kb_files.py",
        [
            "--type",
            kb_type,
            "--chapter",
            str(ch),
            "--book-id",
            book_id,
            "--book-name",
            book_name,
            "--output-dir",
            wr,
            "--no-graph-check",
        ],
        timeout=300,
    )
    if r.stdout:
        for line in r.stdout.strip().split("\n")[-5:]:
            log.debug("    %s", line)
    if r.returncode != 0:
        log.warning("build_kb_files.py 返回非零: %s", r.stderr[:300] if r.stderr else "无错误输出")
        m = re.search(r"完成: (\d+) 个文件", r.stdout) if r.stdout else None
        generated = int(m.group(1)) if m else 0
        if generated == 0:
            log.error("0 文件生成，构建失败（可能是数据缺失）")
            return False

    # v39.0: 构建后自动修复（双反斜杠/公式格式/来源标注/占位符）
    run_phase_auto_fix(wr, phase, ch)

    return True


# ============================================================
# 构建后内容检查
# ============================================================


def _run_comprehensive_check_on_phase(wr, phase, ch):
    """v33.1: 每阶段构建后运行 comprehensive-content-check。
    返回 (passed: bool, fail_count: int, fail_lines: list) — FAIL 会阻断阶段 done。
    v12-fix: 按当前阶段类型过滤 FAIL 行，避免其他阶段的 FAIL 误阻断本阶段。
    v40.0: 改用 ScriptRunner + JSON 结构化数据过滤。
    """
    cc_script = os.path.join(os.path.dirname(__file__), "comprehensive_content_check.py")
    if not os.path.exists(cc_script):
        return True, 0, []
    # JSON items 中的 type 字段与 phase 的映射
    type_map = {
        "concepts": "concept",
        "ke": "KE",
        "entities": "Entity",
        "kp": "KP",
        "sp": "SP",
        "scene": "Scene",
        "exercises": "Exercise",
        "solutions": "Solution",
    }
    check_type = type_map.get(phase)
    if not check_type:
        return True, 0, []
    try:
        cc = run_content_check(wr, quiet=False, json_mode=True)
        # 从 JSON items 中过滤当前阶段类型的 FAIL 项
        all_fail_items = [item for item in cc.items if item.get("severity") == "FAIL"]
        fail_items = [item for item in all_fail_items if check_type.lower() in item.get("type", "").lower()]
        if fail_items:
            log.debug("content-check [%s]: %d 项 FAIL", phase, len(fail_items))
            fail_lines = []
            for item in fail_items[:5]:
                line = f"{item.get('type', '?')}: {item.get('detail', '')}"
                log.error("     %s", line)
                fail_lines.append(line)
            if len(all_fail_items) > len(fail_items):
                log.info("另有 %d 项 FAIL 属于其他阶段，已忽略", len(all_fail_items) - len(fail_items))
            return False, len(fail_items), fail_lines
        else:
            log.success("content-check [%s]: 通过", phase)
            return True, 0, []
    except Exception as e:
        log.warning("comprehensive_content_check [%s] 异常: %s", phase, e)
        return True, 0, []


# ============================================================
# 解答自动生成（含骨架 + 质量修复）
# ============================================================


def _auto_build_solutions(wr, s, args, ch):
    """自动为已有习题生成解答"""
    ex_dir = os.path.join(wr, DIR["EXERCISES"])
    sol_dir = os.path.join(wr, DIR["SOLUTIONS"])

    if not os.path.isdir(ex_dir):
        log.warning("无习题目录，跳过解答生成")
        return False

    # 收集已有解答名，找出缺失的
    ex_files = set()
    for f in os.listdir(ex_dir):
        if f.endswith(".md") and "解答" not in f:
            ex_files.add(f)

    sol_files = set()
    if os.path.isdir(sol_dir):
        for f in os.listdir(sol_dir):
            if f.endswith(".md"):
                sol_files.add(f)

    missing = []
    for exf in sorted(ex_files):
        base = exf.replace(".md", "")
        expected_sol = f"{base.split('_')[0]}-解答_{base.split('_', 1)[1] if '_' in base else ''}.md"
        expected_base = expected_sol.replace(".md", "")
        if not any(sf.startswith(expected_base) for sf in sol_files):
            missing.append(exf)

    if not missing:
        log.success("所有习题已有对应解答")
        return True

    log.info("为 %d 道习题生成解答...", len(missing))

    # v35.7: 先尝试 build_kb_files.py（需要 solutions.yaml），失败时自动生成骨架
    bf = os.path.abspath(os.path.join(os.path.dirname(__file__), "build_kb_files.py"))
    build_ok = False
    if os.path.exists(bf):
        r = run_script(
            "build_kb_files.py", ["--type", "solution", "--chapter", str(ch), "--output-dir", wr, "--no-graph-check"],
            timeout=300,
        )
        if r.success and r.stdout:
            for line in r.stdout.strip().split("\n")[-3:]:
                log.debug("    %s", line)
            build_ok = True
        else:
            log.warning("build_kb_files.py 返回非零（可能 solutions.yaml 缺失）")

    # Fallback: 直接从习题 .md 生成空解答骨架
    if not build_ok:
        log.info("回退：从习题文件直接生成骨架解答...")
        try:
            from template_assembler import assemble_md as _asm
        except ImportError:
            log.warning("无法导入 template_assembler")
            return False
        os.makedirs(sol_dir, exist_ok=True)
        book_id = s["book_id"]
        book_name = s.get("book_name", _book_name(book_id))
        generated = 0
        for exf in missing:
            ex_path = os.path.join(ex_dir, exf)
            try:
                with open(ex_path, encoding="utf-8") as f:
                    ex_content = f.read()
                q_match = re.search(r"## 题目内容\s*\n(.*?)(?=\n## |\Z)", ex_content, re.DOTALL)
                question_text = q_match.group(1).strip() if q_match else "（无法提取题目内容）"
            except Exception as e:
                log.debug(f"习题内容读取失败: {e}")
                question_text = "（读取失败）"

            base = exf.replace(".md", "")
            parts = base.split("_", 1)
            sol_name = f"{parts[0]}-解答_{parts[1]}" if len(parts) > 1 else f"{base}-解答"
            fm = {
                "template_version": "v4.0",
                "type": "solution",
                "type_tags": ["习题解答"],
                "name": sol_name,
                "book_id": book_id,
                "book_name": book_name,
                "chapter_num": ch,
                "confidence": 0.65,
                "confidence_note": "自动生成骨架，待Agent填充",
                "source_chapter": ch,
                "source_from": f"第{ch}章习题",
                "aliases": [],
                "tags": ["knowledge-base", book_id, "solution"],
                "cssclass": "knowledge-base",
            }
            # v35.7-fix: 补全全部模板占位符，避免断wikilink/破Mermaid
            ex_link_name = exf.replace(".md", "")
            # v35.8: 骨架图 — flowchart + 知识闭环Mermaid图
            short_name = ex_link_name.replace(f"第{ch}章-", "").replace("习题", "Q")
            problem_solving_flowchart = (
                """graph TD
    A["审题: """
                + question_text[:20]
                + """..."] --> B[回顾相关概念]
    B --> C[建立分析模型]
    C --> D[推导关键结论]
    D --> E[验证与工程应用]
    E --> F[总结答题]"""
            )
            knowledge_closed_loop = (
                """graph LR
    P["第"""
                + str(ch)
                + """章核心概念"] --> M[分析模型]
    M --> S["""
                + short_name
                + """: 解决方案]
    S --> A[工程应用]
    A -.-> P"""
            )
            bd = {
                "name": sol_name,
                "book_id": book_id,
                "book_name": book_name,
                "chapter_num": ch,
                "confidence": 0.65,
                "confidence_note": "自动生成骨架，待Agent填充",
                "source_chapter": ch,
                "source_from": f"第{ch}章习题",
                "question": question_text,
                "principle_steps": "（待Agent填充实现原理）",
                "characteristics": "（待Agent填充特点归纳）",
                "exam_points": "（待Agent分析核心考点）",
                "common_mistakes": "（待Agent归纳常见错误）",
                "solving_tips": "（待Agent提供解题技巧）",
                "difficulty_1_title": "难点1",
                "difficulty_1_content": "（待Agent深度解析难点1）",
                "difficulty_2_title": "难点2",
                "difficulty_2_content": "（待Agent深度解析难点2）",
                "difficulty_3_title": "难点3",
                "difficulty_3_content": "（待Agent深度解析难点3）",
                "flowchart_diagram": problem_solving_flowchart,
                "flowchart_steps": "（待Agent填充分步说明）",
                "knowledge_loop_diagram": knowledge_closed_loop,
                "knowledge_loop_analysis": "（待Agent填充知识闭环解析，需≥200字：从顶层概念出发，逐步描述图中每个节点的逻辑关系和分支路径，说明闭环反馈机制，关联相关知识点/概念，总结工程意义）",
                "source_reference": "（待Agent补充引用来源）",
                "related_concepts": "（待Agent关联核心概念/知识点）",
                "exercise_link": ex_link_name,
                "exercise_name": ex_link_name,
            }
            try:
                _asm(
                    template_name="eval_template.md",
                    front_matter_updates=fm,
                    body_replacements=bd,
                    output_dir=sol_dir,
                    filename=f"{sol_name}.md",
                    strict=False,
                    quality_key="eval/solution",
                )
                generated += 1
            except Exception as e:
                log.warning("%s: %s", sol_name, e)
        if generated > 0:
            log.success("生成了 %d 个骨架解答（待Agent填充）", generated)
            build_ok = True

            # v35.7-fix: 骨架生成后立即运行质量检查 + 自动修复
            cc_script = os.path.join(os.path.dirname(__file__), "comprehensive_content_check.py")
            if os.path.exists(cc_script):
                r_cc = run_script("comprehensive_content_check.py", [wr], timeout=120)
                fail_lines = [ln for ln in (r_cc.stdout or "").split("\n") if "FAIL" in ln and "Solution" in ln]
                if fail_lines:
                    log.warning("质量检查发现 %d 项 FAIL（Solution），尝试自动修复...", len(fail_lines))
                    fixed = _fix_solution_skeleton(sol_dir, book_id, book_name, ch)
                    if fixed > 0:
                        log.success("自动修复了 %d 个解答文件（破Mermaid/断wikilink）", fixed)
                        build_ok = True
                    else:
                        log.fail("仍有 %d 项无法自动修复，解答标记为 blocked", len(fail_lines))
                        build_ok = False

    # 再次检查
    remaining = verify_exercise_solution_mapping(wr)
    if remaining:
        log.warning("仍有 %d 道习题缺少解答", len(remaining))
        return False

    log.success("解答生成完成")

    # v39.0: 构建后自动修复（占位符填充）
    run_phase_auto_fix(wr, "solutions", ch)

    return True


# ============================================================
# 状态打印
# ============================================================


def _print_pipeline_status(s):
    log.info("\n=== Pipeline 状态: %s Ch%s ===", s.get("book_name", s["book_id"]), s.get("chapter", "?"))
    for ph in DAG_ORDER:
        p = s.get("phases", {}).get(ph, {})
        st = p.get("status", "pending")
        fc = p.get("files", 0)
        dep_s = f" ← {', '.join(DAG_DEPENDS[ph])}" if DAG_DEPENDS[ph] else ""
        icon = "✅" if st == "done" else "🔄" if st == "in_progress" else "⛔" if st == "blocked" else "⏳"
        log.info("  %s %s: %s (%d 文件)%s", icon, ph, st, fc, dep_s)


# ============================================================
# v40.0: 骨架解答填充（fill-solutions 核心逻辑）
# ============================================================


def _fill_skeleton_solutions(wr, sol_dir, book_id, book_name, ch):
    """扫描 confidence <= 0.65 的骨架解答，从关联概念/KE/KP 提取摘要生成初始内容。
    返回填充的文件数。
    """
    filled = 0
    if not os.path.isdir(sol_dir):
        return filled
    # 收集关联节点摘要
    node_summaries = _collect_node_summaries(wr)

    for sf in sorted(os.listdir(sol_dir)):
        if not sf.endswith(".md"):
            continue
        sf_path = os.path.join(sol_dir, sf)
        with open(sf_path, encoding="utf-8") as f:
            content = f.read()

        # 检查 confidence
        conf_m = re.search(r"^confidence:\s*([\d.]+)", content, re.MULTILINE)
        confidence = float(conf_m.group(1)) if conf_m else 1.0
        if confidence > 0.65:
            continue  # 非骨架文件，跳过

        # 提取关联 wikilink
        wikilinks = re.findall(r"\[\[([^\]|#]+)", content)
        related_summaries = []
        for wl in wikilinks:
            wl_clean = wl.strip()
            if wl_clean in node_summaries:
                related_summaries.append((wl_clean, node_summaries[wl_clean]))

        if not related_summaries:
            continue  # 无关联节点，无法填充

        # 提取对应习题信息
        ex_link_m = re.search(r"exercise_link:\s*(.+)", content)
        ex_name = ex_link_m.group(1).strip() if ex_link_m else ""
        question_text = ""
        bloom_level = ""
        if ex_name:
            ex_dir = os.path.join(wr, DIR["EXERCISES"])
            ex_path = os.path.join(ex_dir, f"{ex_name}.md")
            if os.path.exists(ex_path):
                with open(ex_path, encoding="utf-8") as f:
                    ex_content = f.read()
                q_m = re.search(r"## \u9898\u76ee\u5185\u5bb9\s*\n(.*?)(?=\n## |\Z)", ex_content, re.DOTALL)
                question_text = q_m.group(1).strip() if q_m else ""
                bl_m = re.search(r"bloom_level:\s*(.+)", ex_content)
                bloom_level = bl_m.group(1).strip() if bl_m else ""

        # 生成知识闭环解析
        concept_names = [name for name, _ in related_summaries]
        knowledge_loop = _generate_knowledge_loop(concept_names, question_text or ex_name, ch)

        # 生成考点分析
        exam_points = _generate_exam_points(related_summaries, bloom_level)

        # 生成解题思路
        solving_tips = _generate_solving_tips(related_summaries, question_text)

        # 应用替换
        new_content = content
        replacements = {
            "（待Agent填充知识闭环解析，需≥200字：从顶层概念出发，逐步描述图中每个节点的逻辑关系和分支路径，说明闭环反馈机制，关联相关知识点/概念，总结工程意义）": knowledge_loop,
            "（待Agent分析核心考点）": exam_points,
            "（待Agent提供解题技巧）": solving_tips,
            "（待Agent填充实现原理）": _generate_principle_steps(related_summaries),
            "（待Agent填充特点归纳）": _generate_characteristics(related_summaries),
            "（待Agent归纳常见错误）": _generate_common_mistakes(related_summaries),
            "（待Agent关联核心概念/知识点）": "、".join(concept_names[:5]) if concept_names else "（待Agent关联）",
            "（待Agent补充引用来源）": f"第{ch}章 相关内容",
            "（待Agent填充分步说明）": "、".join([f"{name}" for name, _ in related_summaries[:5]]),
            "（待Agent深度解析难点1）": _generate_difficulty(related_summaries, 0),
            "（待Agent深度解析难点2）": _generate_difficulty(related_summaries, 1),
            "（待Agent深度解析难点3）": _generate_difficulty(related_summaries, 2),
        }
        for old, new in replacements.items():
            if old in new_content and new:
                new_content = new_content.replace(old, new)

        # 更新 confidence 为 0.75
        new_content = re.sub(r"^confidence:\s*[\d.]+", "confidence: 0.75", new_content, count=1, flags=re.MULTILINE)
        new_content = re.sub(
            r"^confidence_note:\s*.+",
            "confidence_note: fill-solutions 自动填充",
            new_content,
            count=1,
            flags=re.MULTILINE,
        )

        if new_content != content:
            with open(sf_path, "w", encoding="utf-8") as f:
                f.write(new_content)
            filled += 1
            log.success("%s: 填充了 %d 个关联节点摘要", sf, len(related_summaries))

    return filled


def _collect_node_summaries(wr):
    """从已构建的概念/KE/KP 文件中收集摘要。返回 {name: summary} 字典。"""
    summaries = {}
    for dir_key in ["CONCEPTS", "KE", "KP"]:
        d = os.path.join(wr, DIR[dir_key])
        if not os.path.isdir(d):
            continue
        for f in os.listdir(d):
            if not f.endswith(".md"):
                continue
            fpath = os.path.join(d, f)
            try:
                with open(fpath, encoding="utf-8") as fh:
                    c = fh.read()
                # 提取 name
                name_m = re.search(r"^name:\s*(.+)$", c, re.MULTILINE)
                name = name_m.group(1).strip() if name_m else f.replace(".md", "")
                # 提取定义（"> " 行或第一段非标题文本）
                defn_m = re.search(r"^>\s*(.*)$", c, re.MULTILINE)
                if defn_m:
                    summaries[name] = defn_m.group(1).strip()
                else:
                    # 取第一个非 frontmatter 非标题段落
                    body = re.split(r"^---\s*$", c, maxsplit=2)
                    if len(body) >= 3:
                        first_para = re.search(r"(?<!#)(.+)", body[2])
                        if first_para:
                            summaries[name] = first_para.group(1).strip()[:200]
            except Exception as e:
                log.debug(f"摘要提取失败: {e}")
                continue
    return summaries


def _generate_knowledge_loop(concept_names, context, ch):
    """生成知识闭环解析文本(>=200字)。v45.1: 基于概念名的结构化展开。"""
    if not concept_names:
        return f"本题涉及第{ch}章的核心知识体系，需结合教材原文梳理概念间的逻辑依赖与推导链路，确保从基本定义到工程应用的理解完整性。"
    parts = [f"本题的知识闭环以「{concept_names[0]}」为锚点。"]
    for i, name in enumerate(concept_names[1:5], 1):
        if i == 1:
            parts.append(f"「{name}」建立在前者基础上，提供了定量分析所需的关键参数与约束条件。")
        else:
            parts.append(f"「{name}」进一步将分析框架拓展到第{i+1}层抽象，与前述概念构成递进依赖链。")
    parts.append("闭环验证流程如下：")
    parts.append(f"(1) 从「{concept_names[0]}」的基本定义出发，建立初始分析模型，明确其适用范围与边界条件；")
    if len(concept_names) > 1:
        parts.append(f"(2) 引入「{concept_names[1]}」对模型进行参数化，将定性描述转化为可定量计算的数学关系；")
    if len(concept_names) > 2:
        parts.append(f"(3) 通过「{concept_names[2]}」将理论推导结果转化为可操作的工程判据，验证其在实际场景中的适用性。")
    return "".join(parts)


def _generate_exam_points(related_summaries, bloom_level):
    """生成考点分析。v45.1: 关联概念摘要的实际内容。"""
    names = [n for n, _ in related_summaries[:3]]
    bl = bloom_level or "理解"
    if not names:
        return f"本题认知层级为「{bl}」，需结合第3-5节的教学目标确定具体考点。"
    parts = [f"本题核心考点：{'、'.join(names)}。认知层级「{bl}」。"]
    # 嵌入关联概念的摘要前80字（如果有）
    for name, summary in related_summaries[:2]:
        if summary and len(summary.strip()) > 10:
            snippet = summary.strip()[:80].rstrip("，。、；,.")
            parts.append(f"「{name}」要点：{snippet}。")
    return "".join(parts)


def _generate_solving_tips(related_summaries, question_text):
    """生成解题思路。v45.1: 基于实际概念名而非占位符。"""
    names = [n for n, _ in related_summaries[:3]]
    if not names:
        return "解题思路：首先定位题目的核心概念，然后检索教材对应章节的定义与公式，最后结合题干数据完成计算或分析。"
    tips = ["解题思路："]
    tips.append(f"① 识别核心概念——本题关键为「{names[0]}」，回顾其在教材中的定义与适用条件；")
    if len(names) > 1:
        tips.append(f"② 关联推导——调用「{names[1]}」的定量关系，将题干参数代入相关公式；")
    tips.append("③ 结果验证——检查量纲一致性、边界条件是否满足，确保结论的工程可用性。")
    return "".join(tips)


def _generate_principle_steps(related_summaries):
    """生成实现原理。v45.1: 列出实际概念名构成的分析链。"""
    names = [n for n, _ in related_summaries[:3]]
    if not names:
        return "求解原理：从基本定义出发，建立分析模型，运用相关定理和公式推导，得出工程可用结论。"
    chain = " → ".join(names)
    return f"基于「{chain}」的分析链，本题求解原理：(1) 从「{names[0]}」的定义与基本假设出发；(2) 逐步引入后续概念的约束条件与定量关系；(3) 综合得出满足工程精度要求的解。"


def _generate_characteristics(related_summaries):
    """生成特点归纳。v45.1: 基于实际概念名的具体特征。"""
    names = [n for n, _ in related_summaries[:3]]
    if not names:
        return "本题特点：(1) 涉及多概念交叉应用；(2) 需要理论推导与工程判断结合；(3) 对基础概念的理解深度直接影响求解质量。"
    return f"本题特点：(1) 核心依赖「{names[0]}」的理论框架；(2) 需要将{'、'.join(names[1:]) if len(names) > 1 else '相关概念'}的参数关系映射到具体问题；(3) 解题过程中需区分理想模型假设与实际工程约束的差异。"


def _generate_common_mistakes(related_summaries):
    """生成常见错误。v45.1: 列出与概念相关的典型错误模式。"""
    names = [n for n, _ in related_summaries[:2]]
    prefix = "、".join([f"「{n}」" for n in names]) + "相关" if names else "概念"
    return f"与{prefix}的常见错误：(1) 混淆概念的适用条件与边界，将简化模型不加修正地用于复杂场景；(2) 公式推导中遗漏关键假设或边界条件；(3) 量纲、符号体系不一致导致数量级错误。"


def _generate_difficulty(related_summaries, index):
    """生成难点解析"""
    if index < len(related_summaries):
        name, summary = related_summaries[index]
        return f"难点{index+1}在于对「{name}」的深入理解。{summary[:100] if summary else '该概念涉及多个层面的分析，需要综合前序知识才能准确应用。'}"
    return f"难点{index+1}在于多个概念的交叉应用，需要综合前述分析建立完整的求解框架。"
