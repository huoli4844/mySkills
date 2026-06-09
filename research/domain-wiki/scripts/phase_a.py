#!/usr/bin/env python3
"""phase_a.py — Phase A 构建引擎（从 pipeline_v2.py 拆出）

用法:
  python3 scripts/pipeline_v2.py phase-a    # 仍通过 pipeline_v2.py CLI 调用
  from phase_a import phase_a               # 编程调用
"""

import json
import os
import subprocess
import sys
from collections import defaultdict
from typing import Optional

# ── 路径 ──
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(SCRIPT_DIR)

YAML_WRITER = os.path.join(SCRIPT_DIR, "yaml_writer.py")
TEMPLATE_ENGINE = os.path.join(SCRIPT_DIR, "template_engine.py")
VALIDATE_MERMAID = os.path.join(SCRIPT_DIR, "validate_mermaid.py")
WIKILINK_FIXER = os.path.join(SCRIPT_DIR, "wikilink_fixer.py")
WIKILINK_DEEP_FIXER = os.path.join(SCRIPT_DIR, "wikilink_deep_fixer.py")
QUALITY_REVIEWER = os.path.join(SCRIPT_DIR, "quality_reviewer.py")

sys.path.insert(0, SCRIPT_DIR)
from dag_state import ChapterState  # noqa: E402


# ── 阶段定义 ──

PHASE_A_STEPS = {
    "chapter_toc": "章节目录",
    "concepts": "核心概念",
    "ke": "知识要素",
    "entities": "实体",
    "kp": "知识点",
    "sp": "技能点",
    "scene": "应用场景",
    "exercises": "习题",
    "solutions": "解答",
}


# ── 工具 ──

def run_script(script_path: str, args: list[str], retry: int = 1) -> bool:
    """运行 Python 脚本，支持自动重试"""
    python = sys.executable
    for attempt in range(1, retry + 1):
        if attempt > 1:
            print(f"  🔄 重试第{attempt}次...")
        r = subprocess.run([python, script_path] + args,
                           capture_output=True, text=True)
        if r.stdout:
            print(r.stdout, end='')
        if r.stderr:
            print(r.stderr, end='', file=sys.stderr)
        if r.returncode == 0:
            return True
        if attempt < retry:
            print(f"  ⚠️ 重试中...")
    return False


def get_chapter_dir(book_dir: str, chapter: str) -> str:
    return os.path.join(book_dir, ".dag", f"第{chapter}章", "data")


def get_source_path(book_dir: str, chapter: str) -> Optional[str]:
    src_dir = os.path.join(book_dir, "20_正文")
    if not os.path.isdir(src_dir):
        return None
    files = sorted(f for f in os.listdir(src_dir) if f.startswith(f"第{chapter}章"))
    return os.path.join(src_dir, files[0]) if files else None


# ── 预验证 (preflight) ──

def step_0_preflight(book_dir: str, chapter: str) -> bool:
    """Step 0: YAML写入后/渲染前 的完整性闸门。
    
    检查项（与 yaml_writer validate 互补，不重复pydantic校验）:
      1. YAML文件存在且非空
      2. YAML语法正确
      3. bd字段 vs 模板字段 的缺失/多余
      4. confidence 范围
      5. mathematical_model 有公式类文本但无 $$ 包裹
      6. 概念覆盖度（概念数 vs 源文段落数）
      7. 习题-解答数量匹配
    发现问题时不阻断pipeline，输出完整清单供修复。
    """
    import re as _re
    import glob as _glob
    import yaml as _yaml

    data_dir = get_chapter_dir(book_dir, chapter)
    if not os.path.isdir(data_dir):
        print("  ⚠️  data 目录不存在（跳过 preflight）")
        return True

    # 从模板文件加载各类型的 bd 字段列表
    tpl_dir = os.path.join(SKILL_DIR, "assets", "templates")
    tpl_map = {
        "concept": ("concepts.yaml", "concept_template.md", "核心概念"),
        "ke": ("kes.yaml", "ke_template.md", "知识要素"),
        "entity": ("entities.yaml", "entity_template.md", "实体"),
        "kp": ("kps.yaml", "knowledge_template.md", "知识点"),
        "sp": ("sps.yaml", "skill_template.md", "技能点"),
        "scene": ("scenes.yaml", "scenario_template.md", "应用场景"),
        "exercise": ("exercises.yaml", "exercise_template.md", "习题"),
        "solution": ("solutions.yaml", "eval_template.md", "解答"),
    }

    # 预加载所有模板字段
    tpl_fields = {}
    for type_name, (yf, tpl_name, cn_label) in tpl_map.items():
        tpl_path = os.path.join(tpl_dir, tpl_name)
        fields = set()
        if os.path.exists(tpl_path):
            with open(tpl_path, encoding="utf-8") as _f:
                _txt = _f.read()
            # 提取所有 {{xxx}} 占位符
            for _m in _re.finditer(r"\{\{([a-z_][a-z0-9_]*)\}\}", _txt):
                fields.add(_m.group(1))
            # 排除自动填充的 fm 字段
            _fm_fields = {"name", "book_id", "book_name", "chapter_num",
                          "confidence", "confidence_note", "source_chapter",
                          "source_from", "entity_type", "aliases", "tags",
                          "type", "type_tag", "bloom_level", "difficulty",
                          "exercise_link", "exercise_name",
                          "bloom_progression_analysis"}
            tpl_fields[type_name] = fields - _fm_fields
        else:
            tpl_fields[type_name] = set()

    total_issues = 0
    total_items = 0
    items_concept = 0

    for type_name, (yf, tpl_name, cn_label) in tpl_map.items():
        fpath = os.path.join(data_dir, yf)
        issues = []
        item_count = 0

        if not os.path.exists(fpath):
            issues.append(f"❌ 文件不存在")
        elif os.path.getsize(fpath) == 0:
            issues.append(f"❌ 空文件")
        else:
            with open(fpath, encoding="utf-8") as _f:
                try:
                    data = _yaml.safe_load(_f)
                except _yaml.YAMLError as _e:
                    issues.append(f"❌ YAML语法错误: {_e}")
                    data = None

            if data is None:
                issues.append(f"❌ 解析结果为 None")
            elif not isinstance(data, list):
                issues.append(f"❌ 格式错误: 期望list，得到 {type(data).__name__}")
            else:
                item_count = len(data)
                canon = tpl_fields.get(type_name, set())
                for idx, item in enumerate(data):
                    if not isinstance(item, dict):
                        continue
                    name = item.get("name", f"[{idx}]")
                    bd = item.get("bd", {})
                    if not isinstance(bd, dict):
                        issues.append(f"⚠️ [{name}] bd不是dict")
                        continue
                    bd_keys = set(bd.keys())
                    missing = canon - bd_keys
                    extra = bd_keys - canon
                    if missing:
                        issues.append(f"📋 [{name}] 缺{len(missing)}字段: {', '.join(sorted(missing)[:5])}")
                    if extra:
                        issues.append(f"📋 [{name}] 多余{len(extra)}字段: {', '.join(sorted(extra)[:5])}")

                    # confidence 范围
                    fm = item.get("fm", {})
                    conf = fm.get("confidence", 0)
                    if isinstance(conf, (int, float)) and (conf > 0.95 or conf < 0.5):
                        issues.append(f"⚠️ [{name}] confidence={conf} 超出[0.5,0.95]")

                    # mathematical_model 公式格式
                    mm = bd.get("mathematical_model", "")
                    if mm and mm != "无":
                        has_fc = any(c in mm for c in {"lg", "log", "dB", "=", "ω", "π", "Ω", "λ"})
                        no_dollar = "$$" not in mm
                        if has_fc and no_dollar:
                            issues.append(f"📐 [{name}] mathematical_model 有公式但未用 $$ 包裹")

                    # 字段字数检查（对 concept/ke 的 term_definition）
                    td = bd.get("term_definition", "")
                    if td and td != "无" and type_name in ("concept", "ke") and len(td) < 80:
                        issues.append(f"📖 [{name}] term_definition 仅{len(td)}字（建议≥80）")

                # 记录概念数用于覆盖度检测
                if yf == "concepts.yaml":
                    items_concept = item_count

        total_items += item_count
        n = len(issues)
        total_issues += n
        icon = "✅" if n == 0 else f"⚠️ {n}项"
        print(f"  {icon} {yf:<18s} ({cn_label}, {item_count}项)")
        for iss in issues:
            print(f"      {iss}")

    # 概念覆盖度检查
    src_dir = os.path.join(book_dir, "20_正文")
    src_files = sorted(_glob.glob(os.path.join(src_dir, f"第{chapter}章*.md")))
    if src_files and items_concept > 0:
        with open(src_files[0], encoding="utf-8") as _sf:
            _src = _sf.read()
        _headings = _re.findall(r"^#{2,3}\s+(.+)", _src, _re.MULTILINE)
        _content_headings = [
            h for h in _headings
            if not _re.match(r"^第\d+章\s", h.strip())
            and h.strip() not in ("内容提要", "思考题", "小结", "习题")
        ]
        hcount = len(_content_headings)
        if hcount >= 3 and items_concept < max(3, hcount // 3):
            ratio = items_concept / hcount * 100
            print(f"  ⚠️ 概念覆盖度低: {items_concept}概念 vs {hcount}段标题 ({ratio:.0f}%)")
            total_issues += 1

    # 习题-解答配对
    ex_path = os.path.join(data_dir, "exercises.yaml")
    sol_path = os.path.join(data_dir, "solutions.yaml")
    if os.path.exists(ex_path) and os.path.exists(sol_path):
        with open(ex_path) as _f:
            ex_data = _yaml.safe_load(_f) or []
        with open(sol_path) as _f:
            sol_data = _yaml.safe_load(_f) or []
        if len(ex_data) != len(sol_data):
            print(f"  ⚠️ 习题({len(ex_data)}) ≠ 解答({len(sol_data)}) 数量不匹配")
            total_issues += 1
        else:
            print(f"  ✅ 习题-解答配对: {len(ex_data)} = {len(sol_data)}")

    print("")
    if total_issues == 0:
        print(f"  🎉 Preflight 通过: {total_items}项数据，无问题")
    else:
        print(f"  📋 Preflight 发现 {total_issues} 项问题，请修复后重试")
    return total_issues == 0


# ── Phase A ──

def phase_a(book_dir: str, chapter: str, book_id: str, book_name: str,
            resume: bool = False) -> bool:
    """Phase A: 校验YAML → 渲染输出（纯代码，零Agent，带状态追踪）"""
    data_dir = get_chapter_dir(book_dir, chapter)
    state = ChapterState(book_dir, book_id, chapter)

    if resume:
        for pname in PHASE_A_STEPS:
            can, reason = state.can_run(pname)
            if can:
                break
        else:
            print(f"  ✅ 第{chapter}章 Phase A 所有阶段已完成")
            return True
        print(f"  📍 断点续传: 从 {pname}({PHASE_A_STEPS[pname]}) 开始")

    for yf, pname in [
        ('concepts.yaml', 'concepts'),
        ('kes.yaml', 'ke'),
        ('entities.yaml', 'entities'),
        ('kps.yaml', 'kp'),
        ('sps.yaml', 'sp'),
        ('scenes.yaml', 'scene'),
    ]:
        if resume and state.get_status(pname) == "done":
            continue
        yp = os.path.join(data_dir, yf)
        if not os.path.isfile(yp):
            print(f"❌ 缺少 {yf}")
            state.set_status(pname, "failed")
            state.save()
            return False

    if not resume or state.can_run("solutions")[0]:
        pass  # 习题和解答不阻断

    # Step 0: Preflight — YAML完整性闸门（写入后/渲染前）
    print("\n" + "=" * 60)
    print("Phase A Step 0: Preflight — YAML数据完整性检查")
    print("=" * 60)
    if not resume or state.get_status("chapter_toc") != "done":
        pf_ok = step_0_preflight(book_dir, chapter)
        print("")

    # Step 1: schema校验所有YAML
    print("=" * 60)
    print("Phase A Step 1: 校验YAML数据")
    print("=" * 60)

    yaml_files = sorted(f for f in os.listdir(data_dir) if f.endswith(('.yaml', '.yml')))
    yaml_map = {
        'concepts.yaml': 'concept', 'kes.yaml': 'ke', 'entities.yaml': 'entity',
        'kps.yaml': 'kp', 'sps.yaml': 'sp', 'scenes.yaml': 'scene',
        'exercises.yaml': 'exercise', 'solutions.yaml': 'solution',
    }

    all_ok = True
    for yf in yaml_files:
        yp = os.path.join(data_dir, yf)
        type_name = yaml_map.get(yf)
        if type_name:
            if not run_script(YAML_WRITER, ['validate', '--yaml-path', yp, '--type', type_name]):
                all_ok = False

    if not all_ok:
        print("\n❌ YAML 校验失败，请修复后重试")
        return False
    print("\n✅ 全部YAML校验通过")
    state.set_status("chapter_toc", "done")
    state.save()

    # Step 2: 模板渲染
    print("\n" + "=" * 60)
    print("Phase A Step 2: 模板渲染")
    print("=" * 60)

    ok = run_script(TEMPLATE_ENGINE, [
        'render-chapter',
        '--data-dir', data_dir,
        '--output-dir', book_dir,
        '--book-id', book_id,
        '--book-name', book_name,
        '-c', chapter,
    ])

    if not ok:
        print("\n❌ Step 2 失败: 模板渲染出错")
        return False

    print("\n✅ Step 2 完成")
    for pname in ["concepts", "ke", "entities", "kp", "sp", "scene"]:
        state.set_status(pname, "done")
    state.save()

    # Step 3: 质量门
    print("\n" + "=" * 60)
    print("Phase A Step 3: 质量门 — Mermaid验证 + wikilink修复")
    print("=" * 60)

    mr = run_script(VALIDATE_MERMAID, ['--book-dir', book_dir])
    print(f"  {'✅' if mr else '⚠️'} Mermaid验证")

    wf1 = run_script(WIKILINK_DEEP_FIXER, [book_dir])
    print(f"  {'✅' if wf1 else '⚠️'} 章节关联wikilink")

    wf2 = run_script(WIKILINK_FIXER, [book_dir])
    print(f"  {'✅' if wf2 else '⚠️'} 反向链接补全")

    ok_q = mr and (wf1 is not False) and (wf2 is not False)
    state.set_status("exercises", "done")
    state.set_status("solutions", "done")
    state.save()

    if ok_q:
        print(f"\n✅ Phase A 全部完成: 第{chapter}章")
    else:
        print(f"\n✅ Phase A 完成 (有质量警告): 第{chapter}章")

    # Step 4: 质量审查
    print("\n" + "=" * 60)
    print("Phase A Step 4: 质量审查 + 修复指令生成")
    print("=" * 60)

    python = sys.executable
    qr = subprocess.run(
        [python, QUALITY_REVIEWER, "chapter",
         "--book-dir", book_dir, "--book-id", book_id,
         "-c", chapter, "--json", "--threshold", "0.3",
         "--fix-threshold", "0.8"],
        capture_output=True, text=True
    )

    if qr.returncode == 0:
        print("  ✅ 质量审查通过")
        if qr.stdout:
            try:
                jr = json.loads(qr.stdout)
                print(f"  📊 评分: {jr.get('score', 0):.0%}")
            except (json.JSONDecodeError, ValueError):
                pass
    elif qr.returncode == 1:
        print("  ⚠️  质量审查发现异常（可接受）")
        if qr.stdout:
            try:
                jr = json.loads(qr.stdout)
                score = jr.get("score", 0)
                print(f"  📊 评分: {score:.0%}")
                manifest = jr.get("fix_manifest", [])
                if manifest:
                    print(f"  🛠️  {len(manifest)}个文件需修复:")
                    type_counts = defaultdict(int)
                    for item in manifest:
                        type_counts[item["type"]] += 1
                    for t, c in sorted(type_counts.items()):
                        print(f"    {t}: {c}项")
                    print("  💡 运行: pipeline_v2.py review-fix ...")
            except (json.JSONDecodeError, ValueError):
                pass
    else:
        print(f"  ⚠️  审查异常: {qr.returncode}")
        if qr.stderr:
            print(qr.stderr[:300])

    return True
