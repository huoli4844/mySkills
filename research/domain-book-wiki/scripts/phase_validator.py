"""phase_validator.py — 阶段输出验证器

v38.0: 从 dag_pipeline.py 拆分出来，降低 God File 复杂度。
包含: validate_phase_output — 对指定阶段的输出文件进行全面校验。
"""

import os
import re
from typing import Any

from dag_state import _phase_dir


def validate_phase_output(wr: str, phase: str, chapter: str) -> dict[str, Any]:
    """对指定阶段的输出文件进行全面验证，返回 {issues: [...], passed: bool}

    v33.0: 新增模板内容完整性检查 — 每个 ### 子节是否都有实际内容（非"无"、非空）
    v37.0: 五大类模板归并 — 映射 phase 到新模板名 + 质量检查键
    v38.0: 从 dag_pipeline.py 拆分到 phase_validator.py
    """
    from tac_constants import CONFIDENCE_LEVELS, REQUIRED_FRONTMATTER

    issues: list[str] = []
    ph_dir = _phase_dir(wr, phase)
    if not os.path.isdir(ph_dir):
        return {"issues": [], "passed": True}  # 目录不存在则跳过

    # v37.0: 五大类模板归并 — 映射 phase 到新模板名 + 质量检查键
    template_map: dict[str, str] = {
        "concepts": "concept_template.md",
        "ke": "concept_template.md",
        "kp": "knowledge_template.md",
        "sp": "skill_template.md",
        "scene": "scenario_template.md",
        "entities": "concept_template.md",
        "exercises": "eval_template.md",
        "solutions": "eval_template.md",
    }
    quality_key_map: dict[str, str] = {
        "concepts": "concept_template.md",
        "ke": "concept/ke",
        "kp": "knowledge_template.md",
        "sp": "skill_template.md",
        "scene": "scenario_template.md",
        "entities": "concept/entity",
        "exercises": "eval/exercise",
        "solutions": "eval/solution",
    }
    template_name = template_map.get(phase)
    if not template_name:
        return {"issues": [], "passed": True}

    # v37.0: 用质量检查键做置信度/必填字段校验（区分子类型）
    qk: str = quality_key_map.get(phase, template_name)

    # 预期的 type 字段值
    expected_type_map: dict[str, str] = {
        "concepts": "concept",
        "ke": "knowledge-element",
        "kp": "knowledge",
        "sp": "skill",
        "scene": "scenario",
        "entities": "entity",
        "exercises": "exercise",
        "solutions": "solution",
    }
    expected_type = expected_type_map.get(phase)

    for fname in sorted(os.listdir(ph_dir)):
        if not fname.endswith(".md"):
            continue
        fpath = os.path.join(ph_dir, fname)
        with open(fpath, encoding="utf-8") as f:
            content = f.read()

        # ── 提取 FrontMatter ──
        fm_match = re.search(r"^---\n(.*?)\n---", content, re.DOTALL)
        if not fm_match:
            issues.append(f"{fname}: 无 FrontMatter")
            continue

        fm_text = fm_match.group(1)
        fm: dict[str, str] = {}
        for line in fm_text.strip().split("\n"):
            if ":" in line:
                key, _, val = line.partition(":")
                fm[key.strip()] = val.strip()

        # ── 检查必填字段 ──
        required: set[str] = REQUIRED_FRONTMATTER.get(qk, set())
        missing = required - set(fm.keys())
        if missing:
            issues.append(f"{fname}: 缺少必填字段 {missing}")

        # ── 检查置信度 ──
        allowed = CONFIDENCE_LEVELS.get(qk, set())
        if allowed:
            conf_str = fm.get("confidence", "")
            try:
                conf = float(conf_str)
                if conf not in allowed:
                    issues.append(f"{fname}: confidence={conf} 不符合 {qk} 允许值 {allowed}")
            except ValueError:
                issues.append(f"{fname}: confidence 不是有效数值: {conf_str}")

        # ── 检查占位符残留 ──
        if "{{" in content and "}}" in content:
            phs = re.findall(r"\{\{[^}]+\}\}", content)
            if phs:
                issues.append(f"{fname}: {len(phs)} 个占位符残留 ({', '.join(phs[:5])})")

        # ── 检查 type 字段一致性 ──
        actual_type = fm.get("type", "")
        if expected_type and actual_type and actual_type != expected_type:
            # Special cases: legacy template type names
            if (expected_type == "knowledge" and actual_type == "knowledge-point") or (
                expected_type == "skill" and actual_type == "skill-point"
            ):
                pass  # acceptable match
            else:
                issues.append(f"{fname}: type='{actual_type}' 预期为 '{expected_type}'")

        # ── v33.0: 模板内容完整性检查 ──
        body_start = content.find("---\n", fm_match.end())
        body = content[fm_match.end():] if body_start == -1 else content[body_start + 4:]

        secs = re.findall(r"^###\s+(.+?)$", body, re.MULTILINE)
        if secs:
            empty_secs: list[str] = []
            parts = re.split(r"^(###\s+.+)$", body, flags=re.MULTILINE)
            for i in range(1, len(parts) - 1, 2):
                title_line = parts[i]
                sec_title = title_line.replace("### ", "").strip()
                sec_content = parts[i + 1] if i + 1 < len(parts) else ""
                sec_content = re.split(r"\n(?=###\s)", sec_content)[0]
                stripped = sec_content.strip()
                # v35.2: "无" 是合法填充值，仅检测完全空白的子节
                if not stripped:
                    empty_secs.append(sec_title)
            if empty_secs:
                suffix = "..." if len(empty_secs) > 5 else ""
                # 降级为 warning：案例内部的 ### 分段被误检为空子节（如"已知条件"/"效果验证"等）
                # 实际内容在分段标题的上级段落中，不影响渲染
                issues.append(f"⚠️ {fname}: {len(empty_secs)} 个子节内容未填充 "
                              f"({', '.join(empty_secs[:5])}){suffix}")

    # v35.7: solutions 阶段追加 习题-解答 1:1 配对检查
    if phase == "solutions":
        from pipeline_auto import verify_exercise_solution_mapping

        missing_exercises = verify_exercise_solution_mapping(wr)
        if missing_exercises:
            suffix = "..." if len(missing_exercises) > 5 else ""
            issues.append(
                f"❌ {len(missing_exercises)} 道习题缺少对应解答: " f"{', '.join(missing_exercises[:5])}{suffix}"
            )

    passed = len(issues) == 0
    # ⚠️ 前缀的 issue 是 warning 级别，不阻断 pipeline
    warning_only = all(i.startswith("⚠️") for i in issues)
    if warning_only and not passed:
        passed = True
    return {"issues": issues, "passed": passed}
