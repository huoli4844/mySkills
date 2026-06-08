#!/usr/bin/env python3
"""pipeline_v2.py — 知识库构建两阶段编排（v2.1）

设计：
  Phase A（纯代码）: YAML数据 → schema校验 → 模板渲染 → 质量门
    Step 1: 校验YAML（pydantic schema验证）
    Step 2: 模板渲染（schema.json + 模板.md 驱动）
    Step 3: 质量门（Mermaid验证 + wikilink双向修复自动执行）
    
  Phase B（Agent可选）: 从Phase A输出分析 → 判断是否生成KP/SP/Scene
    Agent基于已渲染的概念、KE、实体内容
    → 决定是否/如何写KP/SP/Scene的YAML
    → 用 yaml_writer.py 写入（字段名受pydantic保护）

无关领域、无关书籍。所有字段名/confidence/模板从 schema.json 读取。

用法:
  # Phase A: 渲染一章的L1内容（含自动质量门）
  python3 pipeline_v2.py phase-a \\
    --book-dir /path/to/book \\
    -c N \\
    --book-id 01_书籍ID \\
    --book-name "书籍名称"

  # 质量门（单独运行，对全书做 wikilink + Mermaid 检查）
  python3 pipeline_v2.py quality-gate \\
    --book-dir /path/to/book

  # 查看状态
  python3 pipeline_v2.py status \\
    --book-dir /path/to/book \\
    -c N

  # Phase B: Agent评估Phase A结果并决定KP/SP/Scene
  python3 pipeline_v2.py phase-b \\
    --book-dir /path/to/book \\
    -c N
"""

import argparse
import json
import os
import re
import sys
from typing import Any, Optional

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


# ════════════════════════════════════════════════════════════
# 工具函数
# ════════════════════════════════════════════════════════════

def get_chapter_dir(book_dir: str, chapter: str) -> str:
    return os.path.join(book_dir, ".dag", f"第{chapter}章", "data")


def get_source_path(book_dir: str, chapter: str) -> Optional[str]:
    """查找章节源文件"""
    src_dir = os.path.join(book_dir, "20_正文")
    if not os.path.isdir(src_dir):
        return None
    files = sorted(f for f in os.listdir(src_dir) if f.startswith(f"第{chapter}章"))
    if files:
        return os.path.join(src_dir, files[0])
    return None


def run_script(script_path: str, args: list[str]) -> bool:
    """运行Python脚本，返回是否成功"""
    import subprocess
    python = sys.executable
    cmd = [python, script_path] + args
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.stdout:
        print(r.stdout, end='')
    if r.stderr:
        print(r.stderr, end='', file=sys.stderr)
    return r.returncode == 0


# ════════════════════════════════════════════════════════════
# Phase A: 纯代码构建
# ════════════════════════════════════════════════════════════

def phase_a(book_dir: str, chapter: str, book_id: str, book_name: str):
    """Phase A: 校验YAML → 渲染输出（纯代码，零Agent）"""
    data_dir = get_chapter_dir(book_dir, chapter)

    if not os.path.isdir(data_dir):
        print(f"❌ 数据目录不存在: {data_dir}")
        print(f"   请先在 {data_dir} 中放入YAML文件")
        print(f"   或用 yaml_writer.py skeleton --type <type> 生成骨架")
        return False

    # Step 1: schema校验所有YAML
    print("=" * 60)
    print("Phase A Step 1: 校验YAML数据")
    print("=" * 60)

    yaml_files = sorted(f for f in os.listdir(data_dir) if f.endswith(('.yaml', '.yml')))
    yaml_map = {
        'concepts.yaml': 'concept',
        'kes.yaml': 'ke',
        'entities.yaml': 'entity',
        'kps.yaml': 'kp',
        'sps.yaml': 'sp',
        'scenes.yaml': 'scene',
        'exercises.yaml': 'exercise',
        'solutions.yaml': 'solution',
    }

    # 检查6个核心L1 YAML是否存在
    required_l1 = ['concepts.yaml', 'kes.yaml', 'entities.yaml',
                   'kps.yaml', 'sps.yaml', 'scenes.yaml']
    missing_l1 = [f for f in required_l1 if not os.path.isfile(os.path.join(data_dir, f))]

    if missing_l1:
        print(f"❌ 缺少必备的L1 YAML文件: {', '.join(missing_l1)}")
        print(f"   请先用 yaml_writer.py 写入这些文件")
        return False

    # 校验每个YAML
    all_ok = True
    for yf in yaml_files:
        yp = os.path.join(data_dir, yf)
        type_name = yaml_map.get(yf)
        if type_name:
            ok = run_script(YAML_WRITER, ['validate', '--yaml-path', yp, '--type', type_name])
            if not ok:
                all_ok = False

    if not all_ok:
        print(f"\n❌ YAML 校验失败，请用 yaml_writer.py 修复后重试")
        return False

    print(f"\n✅ 全部YAML校验通过")

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

    if ok:
        print(f"\n✅ Phase A Step 2 完成: 第{chapter}章 L1内容已构建")
    else:
        print(f"\n❌ Phase A Step 2 失败: 模板渲染出错")
        return False

    # Step 3: 质量门 — Mermaid验证 + wikilink修复
    print("\n" + "=" * 60)
    print("Phase A Step 3: 质量门 — Mermaid验证 + wikilink修复")
    print("=" * 60)

    ok_q = True

    # 3a: Mermaid验证
    mr = run_script(VALIDATE_MERMAID, ['--book-dir', book_dir])
    if mr:
        print("  ✅ Mermaid语法验证通过")
    else:
        print("  ⚠️  Mermaid验证发现异常，请手动检查")
        ok_q = False

    # 3b: wikilink深层修复（出链=0 → 同章自动关联）
    wf1 = run_script(WIKILINK_DEEP_FIXER, [book_dir])
    print(f"  {'✅' if wf1 else '⚠️'} 章节关联wikilink修复完成")

    # 3c: wikilink非对称修复（A→B → B也→A）
    wf2 = run_script(WIKILINK_FIXER, [book_dir])
    print(f"  {'✅' if wf2 else '⚠️'} 反向链接补全完成")

    if ok_q:
        print(f"\n✅ Phase A 全部完成: 第{chapter}章 (校验→渲染→质量门)")
    else:
        print(f"\n✅ Phase A 完成 (有质量警告): 第{chapter}章")

    return ok_q and ok


# ════════════════════════════════════════════════════════════
# Index Building
# ════════════════════════════════════════════════════════════

def build_indices(book_dir: str, book_id: str, book_name: str):
    """构建 L2/L3/L4 索引：扫描 .md 文件 → 生成索引 YAML → 渲染输出"""
    from pathlib import Path

    print("=" * 60)
    print("Build Indices: 构建索引数据")
    print("=" * 60)

    # Step 1: 运行 index_builder.py 生成索引 YAML
    ok = run_script(INDEX_BUILDER, [
        book_dir,
        "--book-id", book_id,
        "--book-name", book_name,
    ])
    if not ok:
        print("❌ 索引数据生成失败")
        return False
    print("  ✅ 索引YAML数据生成完成")

    # Step 2: 渲染索引到 10_总揽
    idx_dir = os.path.join(book_dir, ".dag", "index_data")
    if not os.path.isdir(idx_dir):
        print("❌ 索引数据目录不存在")
        return False

    output_dir = os.path.join(book_dir, "10_总揽")
    os.makedirs(output_dir, exist_ok=True)

    index_types = [
        ("book_overview.yaml", "book_overview", "book_overview.md"),
        ("concept_index.yaml", "concept_index", "concept_index.md"),
        ("knowledge_index.yaml", "knowledge_index", "knowledge_index.md"),
        ("skill_index.yaml", "skill_index", "skill_index.md"),
        ("scenario_index.yaml", "scenario_index", "scenario_index.md"),
    ]

    rendered = 0
    for yf, idx_type, template_file in index_types:
        yp = os.path.join(idx_dir, yf)
        if not os.path.isfile(yp):
            print(f"  ⏳ 跳过 {yf}（不存在）")
            continue

        # 读取 YAML → 提取 body（frontmatter 之后的部分）→ 写为 .md
        with open(yp, encoding="utf-8") as f:
            raw = f.read()
        body_match = re.split(r'^---\s*\n.*?\n---\s*\n', raw, maxsplit=1, flags=re.DOTALL)
        md_body = body_match[1] if len(body_match) > 1 else raw

        out_name = template_file.replace(".md", ".md")
        out_path = os.path.join(output_dir, out_name)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(md_body)
        rendered += 1
        print(f"  📄 {out_name} ({len(md_body)} chars)")

    print(f"  ✅ 已渲染 {rendered} 个索引文件到 10_总揽/")
    total = len([f for f in os.listdir(output_dir) if f.endswith('.md')])
    print(f"  10_总揽 现有 {total} 个文件")
    return True


# ════════════════════════════════════════════════════════════
# Quality Gate
# ════════════════════════════════════════════════════════════

def quality_gate(book_dir: str):
    """全书质量门：Mermaid验证 + wikilink修复（双通道）"""
    print("=" * 60)
    print("Quality Gate: 质量门 — 全书检查")
    print("=" * 60)

    # 1. Mermaid验证
    mr = run_script(VALIDATE_MERMAID, ['--book-dir', book_dir])
    print(f"  {'✅' if mr else '⚠️'} Mermaid验证")

    # 2. wikilink深层修复
    wf1 = run_script(WIKILINK_DEEP_FIXER, [book_dir])
    print(f"  {'✅' if wf1 else '⚠️'} 章节关联wikilink")

    # 3. wikilink非对称修复
    wf2 = run_script(WIKILINK_FIXER, [book_dir])
    print(f"  {'✅' if wf2 else '⚠️'} 反向链接补全")

    print(f"\n{'✅' if mr and (wf1 is not False) and (wf2 is not False) else '⚠️'} Quality Gate 完成")


# ════════════════════════════════════════════════════════════
# Phase B: Agent 评估（输出建议清单）
# ════════════════════════════════════════════════════════════

def phase_b(book_dir: str, chapter: str):
    """Phase B: 输出KP/SP/Scene评估建议（Agent读取后决定）"""
    data_dir = get_chapter_dir(book_dir, chapter)

    if not os.path.isdir(data_dir):
        print(f"❌ 数据目录不存在: {data_dir}")
        return

    # 读取concepts/KE/entities等已有数据
    existing = {}
    for yf in ['concepts.yaml', 'kes.yaml', 'entities.yaml', 'kps.yaml', 'sps.yaml', 'scenes.yaml']:
        yp = os.path.join(data_dir, yf)
        if os.path.exists(yp):
            with open(yp) as f:
                items = _yaml.safe_load(f) if _yaml else json.load(f)
            existing[yf.replace('.yaml', '')] = items if isinstance(items, list) else []
        else:
            existing[yf.replace('.yaml', '')] = []

    # 读取渲染后的输出（检查是否有内容输出）
    output_map = {
        'concepts': '30_核心概念',
        'ke': '40_知识要素',
        'entities': '80_实体',
        'kps': '50_知识点',
        'sps': '60_技能点',
        'scenes': '70_应用场景',
    }

    chapter_prefix = f"第{chapter}章"
    rendered_files = {}
    for key, dir_name in output_map.items():
        out_dir = os.path.join(book_dir, dir_name)
        if os.path.isdir(out_dir):
            files = [f for f in os.listdir(out_dir)
                     if f.startswith(chapter_prefix) or
                     any(k in f for k in [f'-{chapter}', f'第{chapter}章'])]
            rendered_files[key] = files
        else:
            rendered_files[key] = []

    # 输出评估报告
    print("=" * 60)
    print(f"Phase B 评估: 第{chapter}章")
    print("=" * 60)

    print(f"\n📊 现有数据概况:")
    for key in ['concepts', 'kes', 'entities', 'kps', 'sps', 'scenes']:
        yaml_count = len(existing.get(key, []))
        md_count = len(rendered_files.get(key, []))
        status = "✅" if yaml_count > 0 else "⏳"
        print(f"  {status} {key:12s}: YAML {yaml_count:2d}项 → .md {md_count:2d}个文件")

    print(f"\n💡 Agent 评估建议:")
    print(f"  基于以上 {sum(len(v) for v in existing.values())} 个数据项，")
    print(f"  请Agent判断是否需要生成:")
    print(f"  - 知识点 (KP): 当前 {len(existing.get('kps',[]))} 项")
    print(f"  - 技能点 (SP): 当前 {len(existing.get('sps',[]))} 项")
    print(f"  - 应用场景 (Scene): 当前 {len(existing.get('scenes',[]))} 项")
    print(f"\n  提示: 用 yaml_writer.py 写入YAML数据后")
    print(f"  再次运行 phase-a 即可渲染")


# ════════════════════════════════════════════════════════════
# Status
# ════════════════════════════════════════════════════════════

def cmd_status(book_dir: str, chapter: str):
    """显示章节构建状态"""
    data_dir = get_chapter_dir(book_dir, chapter)

    if not os.path.isdir(data_dir):
        print(f"📂 数据目录不存在: {data_dir}")
        return

    print(f"📊 第{chapter}章 构建状态:")
    print("-" * 50)

    yaml_map = {
        'concepts.yaml': ('concept', '30_核心概念', '✅'),
        'kes.yaml': ('ke', '40_知识要素', '✅'),
        'entities.yaml': ('entity', '80_实体', '✅'),
        'kps.yaml': ('kp', '50_知识点', '🔵'),
        'sps.yaml': ('sp', '60_技能点', '🔵'),
        'scenes.yaml': ('scene', '70_应用场景', '🟢'),
        'exercises.yaml': ('exercise', '90_习题', '🟢'),
        'solutions.yaml': ('solution', '90_习题/解答', '🟢'),
    }

    for yf, (tname, out_dir, tag) in sorted(yaml_map.items()):
        yp = os.path.join(data_dir, yf)
        yaml_ok = os.path.isfile(yp)

        # 检查输出
        output_path = os.path.join(book_dir, out_dir)
        md_count = 0
        if os.path.isdir(output_path):
            md_count = len([f for f in os.listdir(output_path)
                           if f.endswith('.md') and ('第' + chapter + '章' in f or
                                                     '-' + chapter + '章' in f)])

        yaml_status = "✅" if yaml_ok else "⏳"
        md_status = f"📄 {md_count}个" if md_count > 0 else "⏳ 无"
        print(f"  {tag} {tname:10s}: YAML {yaml_status}  →  {md_status}")


# ════════════════════════════════════════════════════════════
# Main
# ════════════════════════════════════════════════════════════

def main():
    p = argparse.ArgumentParser(description="pipeline_v2 — 知识库构建两阶段编排")
    sp = p.add_subparsers(dest="cmd")

    # phase-a
    pa = sp.add_parser("phase-a", help="Phase A: 校验YAML → 模板渲染（纯代码）")
    pa.add_argument("--book-dir", required=True, help="书籍工作目录")
    pa.add_argument("-c", "--chapter", required=True, help="章节号")
    pa.add_argument("--book-id", required=True)
    pa.add_argument("--book-name", required=True)

    # phase-b
    pb = sp.add_parser("phase-b", help="Phase B: 输出KP/SP/Scene评估建议")
    pb.add_argument("--book-dir", required=True)
    pb.add_argument("-c", "--chapter", required=True)

    # quality-gate
    qg = sp.add_parser("quality-gate", help="质量门：Mermaid验证 + wikilink修复")
    qg.add_argument("--book-dir", required=True)

    # build-indices
    bi = sp.add_parser("build-indices", help="构建L2/L3/L4索引（扫描扫描.md → 生成索引YAML → 渲染到10_总揽）")
    bi.add_argument("--book-dir", required=True)
    bi.add_argument("--book-id", required=True)
    bi.add_argument("--book-name", required=True)

    # status
    st = sp.add_parser("status", help="显示章节构建状态")
    st.add_argument("--book-dir", required=True)
    st.add_argument("-c", "--chapter", required=True)

    a = p.parse_args()

    if not a.cmd:
        p.print_help()
        return

    if a.cmd == "phase-a":
        success = phase_a(a.book_dir, a.chapter, a.book_id, a.book_name)
        sys.exit(0 if success else 1)

    elif a.cmd == "phase-b":
        phase_b(a.book_dir, a.chapter)

    elif a.cmd == "quality-gate":
        quality_gate(a.book_dir)

    elif a.cmd == "build-indices":
        build_indices(a.book_dir, a.book_id, a.book_name)

    elif a.cmd == "status":
        cmd_status(a.book_dir, a.chapter)


if __name__ == "__main__":
    main()
