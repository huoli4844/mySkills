#!/usr/bin/env python3
"""pipeline_v2.py — 知识库构建两阶段编排（v3.0 集成状态管理+L3/L4指标）

设计：
  Phase A（纯代码）: YAML数据 → schema校验 → 模板渲染 → 质量门 → 状态持久化
  Phase B（Agent可选）: 从Phase A输出分析 → 判断是否生成KP/SP/Scene
  状态管理: 每章状态文件记录阶段完成度，支持断点续传(--resume)
  Run命令: 自动识别下一个可运行阶段并执行

用法:
  # Phase A: 渲染一章的L1内容（含自动质量门）
  python3 pipeline_v2.py phase-a \\
    --book-dir /path/to/book \\
    -c N --book-id 01_书ID --book-name "书名"

  # Phase A + 断点续传（跳过已完成的阶段）
  python3 pipeline_v2.py phase-a \\
    --book-dir /path/to/book -c N \\
    --book-id 01_书ID --book-name "书名" --resume

  # run：自动运行所有待处理的阶段
  python3 pipeline_v2.py run \\
    --book-dir /path/to/book -c N \\
    --book-id 01_书ID --book-name "书名"

  # 质量门（全书批检）
  python3 pipeline_v2.py quality-gate --book-dir /path/to/book

  # 章节状态
  python3 pipeline_v2.py status --book-dir /path/to/book -c N

  # 全书总览
  python3 pipeline_v2.py overview --book-dir /path/to/book --book-id 01_书ID

  # 构建索引
  python3 pipeline_v2.py build-indices \\
    --book-dir /path/to/book --book-id 01_书ID --book-name "书名"
"""

import argparse
import json
import os
import re
import subprocess
import sys
from typing import Optional

try:
    import yaml as _yaml
except ImportError:
    _yaml = None

# ── 路径 ──
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(SCRIPT_DIR)
YAML_WRITER = os.path.join(SCRIPT_DIR, "yaml_writer.py")
TEMPLATE_ENGINE = os.path.join(SCRIPT_DIR, "template_engine.py")
INDEX_BUILDER = os.path.join(SCRIPT_DIR, "index_builder.py")
WIKILINK_FIXER = os.path.join(SCRIPT_DIR, "wikilink_fixer.py")
WIKILINK_DEEP_FIXER = os.path.join(SCRIPT_DIR, "wikilink_deep_fixer.py")
VALIDATE_MERMAID = os.path.join(SCRIPT_DIR, "validate_mermaid.py")
DAG_STATE = os.path.join(SCRIPT_DIR, "dag_state.py")

# 引入状态管理
sys.path.insert(0, SCRIPT_DIR)
from dag_state import ChapterState, PipelineError, phase_status_summary  # noqa: E402


# ════════════════════════════════════════════════════════════
# 工具函数
# ════════════════════════════════════════════════════════════

def get_chapter_dir(book_dir: str, chapter: str) -> str:
    return os.path.join(book_dir, ".dag", f"第{chapter}章", "data")


def get_source_path(book_dir: str, chapter: str) -> Optional[str]:
    src_dir = os.path.join(book_dir, "20_正文")
    if not os.path.isdir(src_dir):
        return None
    files = sorted(f for f in os.listdir(src_dir) if f.startswith(f"第{chapter}章"))
    return os.path.join(src_dir, files[0]) if files else None


def run_script(script_path: str, args: list[str], retry: int = 1) -> bool:
    """运行Python脚本，支持自动重试"""
    python = sys.executable
    for attempt in range(1, retry + 1):
        if attempt > 1:
            print(f"  🔄 重试第{attempt}次...")
        r = subprocess.run([python, script_path] + args, capture_output=True, text=True)
        if r.stdout:
            print(r.stdout, end='')
        if r.stderr:
            print(r.stderr, end='', file=sys.stderr)
        if r.returncode == 0:
            return True
        if attempt < retry:
            print(f"  ⚠️ 重试中...")
    return False


# ════════════════════════════════════════════════════════════
# Phase A: 纯代码构建（集成状态管理）
# ════════════════════════════════════════════════════════════

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


def phase_a(book_dir: str, chapter: str, book_id: str, book_name: str,
            resume: bool = False):
    """Phase A: 校验YAML → 渲染输出（纯代码，零Agent，带状态追踪）"""
    data_dir = get_chapter_dir(book_dir, chapter)
    state = ChapterState(book_dir, book_id, chapter)

    if resume:
        # 获取下一个未完成的 Phase A 阶段
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
        # 习题和解答不阻断（可选）
        pass

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

    print(f"\n✅ Step 2 完成")
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
    return True


# ════════════════════════════════════════════════════════════
# Run: 自动按序处理所有待处理阶段
# ════════════════════════════════════════════════════════════

def cmd_run(book_dir: str, chapter: str, book_id: str, book_name: str):
    """自动按依赖顺序处理所有待处理的阶段"""
    state = ChapterState(book_dir, book_id, chapter)
    print(f"🚀 Auto-Run 第{chapter}章 ({book_name})")
    print(state.summary())
    print()

    while True:
        next_phase = state.next_pending()
        if next_phase is None:
            print(f"\n✅ 所有阶段完成!")
            print(state.summary())
            return True

        print(f"\n{'=' * 60}")
        print(f"▶ 执行阶段: {next_phase}")
        print(f"{'=' * 60}")

        success = False
        try:
            if next_phase in PHASE_A_STEPS:
                # Phase A 一次性完成所有 L1 阶段
                success = phase_a(book_dir, chapter, book_id, book_name, resume=True)
            elif next_phase == "l2_indices":
                success = build_indices(book_dir, book_id, book_name)
                if success:
                    state.set_status("l2_indices", "done")
                    state.save()
            elif next_phase == "l3_indices":
                L3_L4_BUILDER = os.path.join(SCRIPT_DIR, "l3_l4_builder.py")
                success = run_script(L3_L4_BUILDER, ["l3", "--book-dir", book_dir, "--book-id", book_id, "--book-name", book_name])
                if success:
                    state.set_status("l3_indices", "done")
                    state.save()
            elif next_phase == "l4_indices":
                L3_L4_BUILDER = os.path.join(SCRIPT_DIR, "l3_l4_builder.py")
                success = run_script(L3_L4_BUILDER, ["l4", "--book-dir", book_dir, "--book-id", book_id])
            else:
                print(f"  ⏳ 阶段 {next_phase} 跳过（无处理器）")
                state.set_status(next_phase, "done")
                state.save()
                success = True
        except Exception as e:
            print(f"  ❌ 阶段 {next_phase} 失败: {e}")
            state.set_status(next_phase, "failed")
            state.save()
            return False

        if not success:
            print(f"  ❌ 阶段 {next_phase} 执行失败")
            state.set_status(next_phase, "failed")
            state.save()
            return False


# ════════════════════════════════════════════════════════════
# Index Building
# ════════════════════════════════════════════════════════════

def build_indices(book_dir: str, book_id: str, book_name: str):
    """构建 L2 索引"""
    print("=" * 60)
    print("Build Indices: 构建L2索引数据")
    print("=" * 60)

    ok = run_script(INDEX_BUILDER, [book_dir, "--book-id", book_id, "--book-name", book_name])
    if not ok:
        print("❌ 索引数据生成失败")
        return False

    # 渲染到 10_总揽
    idx_dir = os.path.join(book_dir, ".dag", "index_data")
    if not os.path.isdir(idx_dir):
        print("❌ 索引数据目录不存在")
        return False

    output_dir = os.path.join(book_dir, "10_总揽")
    os.makedirs(output_dir, exist_ok=True)

    index_files = [
        "book_overview.yaml", "concept_index.yaml", "knowledge_index.yaml",
        "skill_index.yaml", "scenario_index.yaml",
    ]

    rendered = 0
    for yf in index_files:
        yp = os.path.join(idx_dir, yf)
        if not os.path.isfile(yp):
            print(f"  ⏳ 跳过 {yf}（不存在）")
            continue
        with open(yp, encoding="utf-8") as f:
            raw = f.read()
        body_match = re.split(r"^---\s*\n.*?\n---\s*\n", raw, maxsplit=1, flags=re.DOTALL)
        md_body = body_match[1] if len(body_match) > 1 else raw
        out_md = yf.replace(".yaml", ".md")
        out_path = os.path.join(output_dir, out_md)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(md_body)
        rendered += 1
        print(f"  📄 {out_md} ({len(md_body)} chars)")

    print(f"  ✅ 已渲染 {rendered} 个索引文件到 10_总揽/")
    return True


# ════════════════════════════════════════════════════════════
# Quality Gate
# ════════════════════════════════════════════════════════════

def quality_gate(book_dir: str):
    """全书质量门"""
    print("=" * 60)
    print("Quality Gate: 质量门 — 全书检查")
    print("=" * 60)

    mr = run_script(VALIDATE_MERMAID, ['--book-dir', book_dir])
    print(f"  {'✅' if mr else '⚠️'} Mermaid验证")

    wf1 = run_script(WIKILINK_DEEP_FIXER, [book_dir])
    print(f"  {'✅' if wf1 else '⚠️'} 章节关联wikilink")

    wf2 = run_script(WIKILINK_FIXER, [book_dir])
    print(f"  {'✅' if wf2 else '⚠️'} 反向链接补全")

    print(f"\n{'✅' if mr and (wf1 is not False) and (wf2 is not False) else '⚠️'} Quality Gate 完成")


# ════════════════════════════════════════════════════════════
# Phase B
# ════════════════════════════════════════════════════════════

def phase_b(book_dir: str, chapter: str):
    """Phase B: 输出KP/SP/Scene评估建议"""
    data_dir = get_chapter_dir(book_dir, chapter)
    if not os.path.isdir(data_dir):
        print(f"❌ 数据目录不存在: {data_dir}")
        return

    existing = {}
    for yf in ['concepts.yaml', 'kes.yaml', 'entities.yaml', 'kps.yaml', 'sps.yaml', 'scenes.yaml']:
        yp = os.path.join(data_dir, yf)
        if os.path.exists(yp):
            with open(yp) as f:
                items = _yaml.safe_load(f) if _yaml else json.load(f)
            existing[yf.replace('.yaml', '')] = items if isinstance(items, list) else []
        else:
            existing[yf.replace('.yaml', '')] = []

    print("=" * 60)
    print(f"Phase B 评估: 第{chapter}章")
    print("=" * 60)
    print("\n📊 现有数据概况:")
    for key in ['concepts', 'kes', 'entities', 'kps', 'sps', 'scenes']:
        count = len(existing.get(key, []))
        print(f"  {'✅' if count > 0 else '⏳'} {key:12s}: {count:2d}项")
    print(f"\n💡 Agent 评估建议:")
    print(f"  基于以上数据，判断是否需要生成 KP/SP/Scene")
    print(f"  用 yaml_writer.py 写入YAML后再次运行 phase-a")


# ════════════════════════════════════════════════════════════
# Status
# ════════════════════════════════════════════════════════════

def cmd_status(book_dir: str, chapter: str, book_id: str = ""):
    """显示章节构建状态"""
    state = ChapterState(book_dir, book_id or "?", chapter)
    print(state.summary())


# ════════════════════════════════════════════════════════════
# Main
# ════════════════════════════════════════════════════════════

def main():
    p = argparse.ArgumentParser(description="pipeline_v2 — 知识库构建两阶段编排 (v3.0)")
    sp = p.add_subparsers(dest="cmd")

    # phase-a
    pa = sp.add_parser("phase-a", help="Phase A: 校验YAML → 模板渲染（纯代码）")
    pa.add_argument("--book-dir", required=True)
    pa.add_argument("-c", "--chapter", required=True)
    pa.add_argument("--book-id", required=True)
    pa.add_argument("--book-name", required=True)
    pa.add_argument("--resume", action="store_true", help="断点续传模式（跳过已完成阶段）")

    # run
    pr = sp.add_parser("run", help="自动按序处理所有待处理阶段")
    pr.add_argument("--book-dir", required=True)
    pr.add_argument("-c", "--chapter", required=True)
    pr.add_argument("--book-id", required=True)
    pr.add_argument("--book-name", required=True)

    # phase-b
    pb = sp.add_parser("phase-b", help="Phase B: 输出KP/SP/Scene评估建议")
    pb.add_argument("--book-dir", required=True)
    pb.add_argument("-c", "--chapter", required=True)

    # quality-gate
    qg = sp.add_parser("quality-gate", help="质量门：Mermaid验证 + wikilink修复")
    qg.add_argument("--book-dir", required=True)

    # build-indices
    bi = sp.add_parser("build-indices", help="构建L2索引")
    bi.add_argument("--book-dir", required=True)
    bi.add_argument("--book-id", required=True)
    bi.add_argument("--book-name", required=True)

    # status
    st = sp.add_parser("status", help="显示章节构建状态")
    st.add_argument("--book-dir", required=True)
    st.add_argument("-c", "--chapter", required=True)
    st.add_argument("--book-id", default="")

    # overview
    ov = sp.add_parser("overview", help="全书状态总览")
    ov.add_argument("--book-dir", required=True)
    ov.add_argument("--book-id", required=True)

    a = p.parse_args()

    if not a.cmd:
        p.print_help()
        return

    try:
        if a.cmd == "phase-a":
            success = phase_a(a.book_dir, a.chapter, a.book_id, a.book_name, resume=a.resume)
            sys.exit(0 if success else 1)
        elif a.cmd == "run":
            success = cmd_run(a.book_dir, a.chapter, a.book_id, a.book_name)
            sys.exit(0 if success else 1)
        elif a.cmd == "phase-b":
            phase_b(a.book_dir, a.chapter)
        elif a.cmd == "quality-gate":
            quality_gate(a.book_dir)
        elif a.cmd == "build-indices":
            success = build_indices(a.book_dir, a.book_id, a.book_name)
            sys.exit(0 if success else 1)
        elif a.cmd == "status":
            cmd_status(a.book_dir, a.chapter, a.book_id)
        elif a.cmd == "overview":
            print(phase_status_summary(a.book_dir, a.book_id))
    except PipelineError as e:
        print(f"\n❌ Pipeline错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
