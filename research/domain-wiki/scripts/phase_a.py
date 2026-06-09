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
