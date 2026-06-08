"""pipeline_fix.py — 审查+修复流程

职责：运行 quality_reviewer → 解析JSON → 输出FIX指令 → 修复后重新渲染+审查。
是 pipeline_v2.py 中 review-fix 命令的逻辑实现。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections import defaultdict
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
QUALITY_REVIEWER = os.path.join(SCRIPT_DIR, "quality_reviewer.py")
TEMPLATE_ENGINE = os.path.join(SCRIPT_DIR, "template_engine.py")
VALIDATE_MERMAID = os.path.join(SCRIPT_DIR, "validate_mermaid.py")
WIKILINK_DEEP_FIXER = os.path.join(SCRIPT_DIR, "wikilink_deep_fixer.py")
WIKILINK_FIXER = os.path.join(SCRIPT_DIR, "wikilink_fixer.py")


def run_script(script_path: str, args: list[str], retry: int = 1) -> bool:
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
    return False


def review_and_fix(book_dir: str, book_id: str, chapter: str,
                   threshold: float = 0.8,
                   re_render: bool = False) -> bool:
    """审查章节质量，输出Agent可消费的修复指令"""
    print("=" * 60)
    print(f"📋 Review & Fix: 第{chapter}章")
    print("=" * 60)

    # Step 1: 运行审查并输出JSON
    print("\n▶ Step 1: 质量审查...")
    python = sys.executable
    r = subprocess.run(
        [python, QUALITY_REVIEWER, "chapter",
         "--book-dir", book_dir, "--book-id", book_id, "-c", chapter,
         "--json", "--threshold", "0.01",
         "--fix-threshold", str(threshold)],
        capture_output=True, text=True
    )

    try:
        review_json = json.loads(r.stdout)
    except (json.JSONDecodeError, ValueError):
        print("  ❌ 无法解析审查结果JSON")
        print(r.stdout[:1000])
        return False

    score = review_json.get("score", 0.0)
    fix_manifest = review_json.get("fix_manifest", [])
    type_scores = review_json.get("type_scores", {})

    print(f"\n  📊 评分: {score:.0%}  (阈值: {threshold:.0%})")

    if not fix_manifest:
        print("  ✅ 无修复需求")
        return True

    print(f"\n  🛠️  需修复 {len(fix_manifest)} 个文件")

    # Step 2: 按类型统计
    print("\n▶ Step 2: 生成修复指令...")
    type_fix_count: dict[str, int] = defaultdict(int)
    for item in fix_manifest:
        type_fix_count[item["type"]] += 1

    print(f"\n  按类型统计需修复:")
    data_dir = review_json.get("data_dir", os.path.join(book_dir, ".dag", f"第{chapter}章", "data"))
    src_dir = os.path.join(book_dir, "20_正文")

    for ptype, ts in sorted(type_scores.items()):
        count = type_fix_count.get(ptype, 0)
        score_val = ts.get("score", 1.0)
        status = "✅" if score_val >= threshold else "🛠️"
        print(f"    {status} {ptype:12s} 评分{score_val:.0%} 需修{count}项")

    print(f"\n  📁 数据目录: {data_dir}")
    print(f"  📁 源文目录: {src_dir}")

    # Step 3: 输出详细FIX指令
    print("\n▶ Step 3: 详细修复指令（Agent消费）")
    print("-" * 60)

    for item in fix_manifest:
        print(f"\n  FIX_FILE: {item['yaml_path']}")
        print(f"  FIX_TYPE: {item['type']}")
        print(f"  FIX_NAME: {item['file']}")
        print(f"  FIX_SCORE: {item['score']}")

        enrich_fields = [f for f in item["fields_to_fix"]
                        if f.get("action") in ("enrich",)]
        fill_fields = [f for f in item["fields_to_fix"]
                      if f.get("action") == "fill"]
        struct_fixes = [f for f in item["fields_to_fix"]
                       if f.get("action") == "fix_structure"]

        if enrich_fields:
            ef_str = "; ".join(
                f"{f['field']}: {f['current_len']}→{f['target_len']}字"
                for f in enrich_fields
            )
            print(f"  FIX_ENRICH: {ef_str}")
        if fill_fields:
            ff_str = "; ".join(f["field"] for f in fill_fields)
            print(f"  FIX_FILL: {ff_str} (空字段)")
        if struct_fixes:
            sf_str = "; ".join(
                f"{f['field']}({f.get('category','')})"
                for f in struct_fixes
            )
            print(f"  FIX_STRUCTURE: {sf_str}")

        print(f"  FIX_SOURCE_DIR: {src_dir}")
        print(f"  ---")

    # 聚合修复指令
    print("\n  📋 聚合修复指令:")
    print(f"  AGENT_FIX: book_dir={book_dir} book_id={book_id} "
          f"chapter={chapter} threshold={threshold}")
    print(f"  AGENT_FIX_TYPES: {', '.join(f'{t}({c})' for t, c in sorted(type_fix_count.items()))}")
    print(f"  AGENT_FIX_COUNT: {len(fix_manifest)}")

    print(f"\n  📊 审查完成: 评分{score:.0%} (阈值{threshold:.0%})")
    print(f"  🔧 需要修复 {len(fix_manifest)} 个文件")
    print(f"  💡 建议: 解读上述FIX指令 → 委托子Agent修复 → "
          f"重新渲染(pipeline_v2.py phase-a)")

    return False


def apply_fixes_and_rerender(book_dir: str, book_id: str, chapter: str) -> bool:
    """Agent修复后：重新渲染 + 重新审查"""
    data_dir = os.path.join(book_dir, ".dag", f"第{chapter}章", "data")

    print("=" * 60)
    print(f"📋 Agent修复确认: 第{chapter}章")
    print("=" * 60)

    print("\n▶ 检查YAML文件时间...")
    yaml_files = sorted(f for f in os.listdir(data_dir) if f.endswith('.yaml'))
    for yf in yaml_files:
        yp = os.path.join(data_dir, yf)
        mtime = os.path.getmtime(yp)
        print(f"  {yf}: {datetime.fromtimestamp(mtime).strftime('%H:%M:%S')}")

    # 获取书名
    print("\n▶ 重新渲染模板...")
    python = sys.executable
    book_name = "?"
    state_path = os.path.join(book_dir, ".dag", f"{book_id}_ch{chapter}.json")
    if os.path.isfile(state_path):
        try:
            with open(state_path) as f:
                sd = json.load(f)
            book_name = sd.get("book_name", "?")
        except Exception:
            pass

    ok = run_script(TEMPLATE_ENGINE, [
        'render-chapter', '--data-dir', data_dir, '--output-dir', book_dir,
        '--book-id', book_id, '--book-name', book_name, '-c', chapter,
    ])
    if not ok:
        print("  ❌ 重新渲染失败")
        return False
    print("  ✅ 重新渲染完成")

    # 质量门
    print("\n▶ 重新运行质量门...")
    run_script(VALIDATE_MERMAID, ['--book-dir', book_dir])
    run_script(WIKILINK_DEEP_FIXER, [book_dir])
    run_script(WIKILINK_FIXER, [book_dir])

    # 重新审查
    print("\n▶ 重新审查...")
    r = subprocess.run(
        [python, QUALITY_REVIEWER, "chapter",
         "--book-dir", book_dir, "--book-id", book_id,
         "-c", chapter, "--json"],
        capture_output=True, text=True
    )
    if r.stdout:
        try:
            result = json.loads(r.stdout)
            score = result.get("score", 0.0)
            print(f"  📊 修复后评分: {score:.0%}")
            type_scores = result.get("type_scores", {})
            for ptype, ts in sorted(type_scores.items()):
                if ts.get("items", 0) > 0:
                    print(f"    {ptype:12s}: {ts['score']:.0%}")
            print(f"  {'✅ 修复后质量达标' if r.returncode == 0 else '⚠️ 修复后仍低于阈值'}")
        except Exception:
            print(f"  无法解析JSON: {r.stdout[:500]}")

    print(f"\n✅ 修复确认完成")
    return True
