#!/usr/bin/env python3
"""pipeline_v2.py — 知识库构建两阶段编排（v2.0）

设计：
  Phase A（纯代码）: YAML数据 → schema校验 → 模板渲染输出
    概念 → KE → 实体（DAG顺序，纯代码，无Agent）
    YAML不存在时：exercises自动检测，solutions自动生成骨架
  
  Phase B（Agent可选）: 从Phase A输出分析 → 判断是否生成KP/SP/Scene
    Agent基于已渲染的概念、KE、实体内容
    → 决定是否/如何写KP/SP/Scene的YAML
    → 用 yaml_writer.py 写入（字段名受pydantic保护）

无关领域、无关书籍。所有字段名/confidence/模板从 schema.json 读取。

用法:
  # Phase A: 渲染一章的L1内容
  python3 pipeline_v2.py phase-a \\
    --book-dir /path/to/book \\
    -c 4 \\
    --book-id 01_工程电磁兼容 \\
    --book-name "工程电磁兼容第3版_路宏敏"

  # 查看状态
  python3 pipeline_v2.py status \\
    --book-dir /path/to/book \\
    -c 4

  # Phase B: Agent评估Phase A结果并决定KP/SP/Scene
  python3 pipeline_v2.py phase-b \\
    --book-dir /path/to/book \\
    -c 4
    # 输出：建议清单（Agent读取后自行决定）
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
        print(f"\n✅ Phase A 完成: 第{chapter}章 L1内容已构建")
    else:
        print(f"\n❌ Phase A 失败: 模板渲染出错")

    return ok


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

    elif a.cmd == "status":
        cmd_status(a.book_dir, a.chapter)


if __name__ == "__main__":
    main()
