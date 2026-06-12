#!/usr/bin/env python3
"""
init_project.py — 教材项目初始化 + 写作大纲生成 + QC验证 + 任务清单创建。
合并原 setup_project.py + generate_outlines.py + validate_outlines.py + generate_task_list.py。

用法：
  python3 scripts/init_project.py /path/to/教材 --name "电磁兼容教材" --outline 教材提纲.docx
  python3 scripts/init_project.py /path/to/教材 --chapter 1      # 只生成指定章
  python3 scripts/init_project.py /path/to/教材 --skip-setup     # 跳过项目创建（已初始化）
  python3 scripts/init_project.py /path/to/教材 --status         # 查看任务进度
  python3 scripts/init_project.py /path/to/教材 --mark-done 3   # 标记第3章完成
"""

import os
import re
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Tuple

# ============================================================
# 常量定义
# ============================================================

DEFAULT_GITIGNORE = """# OS
.DS_Store

# IDE
.idea/
*.swp
*.swo

# Hermes temp
.hermes-tmp.*

# Backup
*.bak
*.bak2
*.orig

# Temp scripts
output/fix_*.py

# Audit artifacts (regenerated each run)
output/补充与完善分析报告.md
output/补充执行清单.json
"""

DEFAULT_YAML = """# =============================================================================
# book-build 项目配置
# =============================================================================

# --- 教材信息 ---
textbook:
  name: "{name}"
  outline_file: "{outline}"

# --- 参考教材配置 ---
# 按 priority 排序，数字越小优先级越高
# path: 参考教材处理后的 Markdown 文件路径
source_books:
  # - display_name: "工程电磁兼容（第3版）"
  #   author: "路宏敏"
  #   priority: 1
  #   path: "/path/to/参考书.md"
"""

CHAPTER_NUM_MAP = {
    '一': 1, '二': 2, '三': 3, '四': 4, '五': 5,
    '六': 6, '七': 7, '八': 8, '九': 9, '十': 10,
    '十一': 11, '十二': 12, '十三': 13, '十四': 14, '十五': 15,
}

TASKS_FILE = "writing_tasks.json"
SKILL_DIR = Path(__file__).resolve().parent.parent


# ============================================================
# Phase 1a — 项目创建（原 setup_project.py）
# ============================================================

def setup_project(root: Path, textbook_name: str, outline_file: str) -> bool:
    """创建项目目录结构和默认配置。幂等（已存在的不覆盖）。"""
    if root.exists() and any(root.iterdir()):
        print(f"  ⚠️  目录已存在且不为空: {root}")
        print("     继续执行将创建缺失的子目录，不会覆盖已有文件。")

    dirs = [root, root / "input", root / "output",
            root / "output" / "写作大纲", root / "output" / "实验",
            root / "output" / "案例", root / "output" / "习题解答"]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)

    yaml_path = root / "book-build.yaml"
    if not yaml_path.exists():
        yaml_path.write_text(DEFAULT_YAML.format(name=textbook_name, outline=outline_file), encoding="utf-8")

    gitignore_path = root / ".gitignore"
    if not gitignore_path.exists():
        gitignore_path.write_text(DEFAULT_GITIGNORE, encoding="utf-8")

    outline_path = root / "input" / outline_file
    if not outline_path.exists():
        print(f"\n  ⚠️  请将提纲文件放入: {outline_path}")
        return False
    return True


# ============================================================
# Phase 1b — 大纲生成（原 generate_outlines.py）
# ============================================================

def _chinese_to_arabic(text: str) -> Optional[int]:
    for cn, num in sorted(CHAPTER_NUM_MAP.items(), key=lambda x: -len(x[0])):
        if cn in text:
            return num
    return None


def parse_outline_docx(docx_path: str) -> List[dict]:
    """解析提纲 docx 文件，提取各章名称和L1节结构。"""
    if not os.path.exists(docx_path):
        return []
    try:
        import docx
        doc = docx.Document(docx_path)
        chapters = []
        current_ch = None
        for para in doc.paragraphs:
            text = para.text.strip()
            if not text:
                continue
            ch_num = _chinese_to_arabic(text)
            m_arabic = re.match(r'第(\d+)章\s+(.+)', text)
            if (ch_num is not None and '章' in text) or m_arabic:
                if current_ch:
                    chapters.append(current_ch)
                num = ch_num if ch_num else int(m_arabic.group(1))
                title = re.sub(r'第[一二三四五六七八九十]+章\s*', '', text)
                title = re.sub(r'第\d+章\s*', '', title) if m_arabic else title
                current_ch = {"chapter": num, "title": title.strip(), "sections": []}
                continue
            if current_ch:
                m = re.search(r'(\d+\.\d+)\s+(.+)', text)
                if m:
                    sec_num = m.group(1)
                    if sec_num.startswith(f"{current_ch['chapter']}."):
                        current_ch["sections"].append({"num": sec_num, "title": m.group(2).strip()})
        if current_ch:
            chapters.append(current_ch)
        return chapters
    except ImportError:
        return []


def _load_outline_template() -> str:
    """加载写作大纲模板"""
    template_path = SKILL_DIR / 'templates' / 'chapter-writing-guide-template.md'
    with open(template_path, 'r', encoding='utf-8') as f:
        return f.read()


OUTLINE_TEMPLATE = _load_outline_template()


def generate_chapter_skeleton(chapter: int, title: str, output_dir: str) -> str:
    """为单章生成写作大纲骨架文件。"""
    guides_dir = Path(output_dir) / "写作大纲"
    guides_dir.mkdir(parents=True, exist_ok=True)
    out_path = guides_dir / f"writing-guide-ch{chapter}.md"

    content = OUTLINE_TEMPLATE.format(ch=chapter, title=title)
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(content)
    return str(out_path)


# ============================================================
# Phase 1c — 大纲QC（原 validate_outlines.py）
# ============================================================

def parse_sections(content: str) -> Tuple[List[str], List[str]]:
    l1 = re.findall(r'^###\s+(\d+\.\d+)\s+(.+)', content, re.MULTILINE)
    l2 = re.findall(r'^####\s+(\d+\.\d+\.\d+)\s+(.+)', content, re.MULTILINE)
    return ([f"{s[0]} {s[1][:40]}" for s in l1],
            [f"{s[0]} {s[1][:40]}" for s in l2])


def validate_chapter(chapter: int, filepath: str) -> dict:
    """验证单章大纲完整性。"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    size = os.path.getsize(filepath)
    l1_sections, l2_sections = parse_sections(content)
    has_material = any(m in content for m in ['路宏敏', '梁振光', '柯金良', '张亮'])
    has_targets = bool(re.search(r'\|\s*\d+\.\d+\s*\|.*?KB', content))
    has_exercises_spec = '## 习题' in content or '习题' in content
    has_refs = '## 参考文献' in content

    issues = []
    if not l1_sections:
        issues.append("未定义任何 L1 节")
    if not has_material:
        issues.append("未标注素材来源")
    if not has_refs and has_exercises_spec:
        issues.append("缺少参考文献章节")

    return {
        "chapter": chapter, "file": filepath,
        "size_kb": round(size / 1024, 1),
        "l1_count": len(l1_sections), "l2_count": len(l2_sections),
        "has_material": bool(has_material),
        "has_targets": has_targets,
        "issues": issues,
    }


# ============================================================
# Phase 1d — 任务清单（原 generate_task_list.py）
# ============================================================

def load_or_init_tasks(project_root: str, guides_dir: str, force: bool = False) -> List[Dict]:
    tasks_path = Path(project_root) / TASKS_FILE
    if tasks_path.exists() and not force:
        with open(tasks_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return parse_outline_tasks(guides_dir)


def parse_outline_tasks(guides_dir: str) -> List[Dict]:
    guides_path = Path(guides_dir)
    tasks = []
    for fpath in sorted(guides_path.glob("writing-guide-ch*.md")):
        m = re.search(r'ch(\d+)', fpath.stem)
        if not m:
            continue
        ch = int(m.group(1))
        with open(fpath, 'r', encoding='utf-8') as f:
            content = f.read()

        l1_sections = re.findall(r'^###\s+(\d+\.\d+)\s+(.+)', content, re.MULTILINE)
        targets = {}
        for line in content.split('\n'):
            if '|' not in line or 'KB' not in line:
                continue
            cols = [c.strip() for c in line.split('|')]
            if len(cols) >= 4 and re.match(r'^\d+\.\d+$', cols[1]):
                t = re.search(r'(\d+(?:\.\d+)?)\s*KB', line)
                if t:
                    targets[cols[1]] = float(t.group(1))

        task = {
            "chapter": ch, "title": "",
            "l1_sections": [f"{s[0]} {s[1][:60]}" for s in l1_sections],
            "target_kb_per_section": targets,
            "status": "pending",
            "created_at": datetime.now().isoformat(),
        }
        for line in content.split('\n')[:5]:
            t = re.search(r'第' + str(ch) + r'章\s+(.+)', line)
            if t:
                task["title"] = t.group(1).strip()
                break
        tasks.append(task)
    return tasks


def show_status(tasks: List[Dict]):
    c = {"pending": 0, "in_progress": 0, "completed": 0}
    icon = {"pending": "⏳", "in_progress": "✍️", "completed": "✅"}
    for t in tasks:
        c[t.get("status", "pending")] += 1
    done = c.get("completed", 0)
    total = len(tasks)
    pct = done / total * 100 if total > 0 else 0
    print(f"\n  进度: {done}/{total} ({pct:.0f}%)")
    print(f"  待写: {c.get('pending',0)}  进行中: {c.get('in_progress',0)}  已完成: {done}")


# ============================================================
# CLI 入口
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="教材项目初始化管线（四合一）")
    parser.add_argument("project_root", nargs="?", help="新建或已有的项目目录")
    parser.add_argument("--project", help="项目根目录（与位置参数等效）")
    parser.add_argument("--name", default="电磁兼容教材", help="教材名称")
    parser.add_argument("--outline", default="教材提纲.docx", help="提纲文件名")
    parser.add_argument("--chapter", type=int, default=None, help="只生成指定章节大纲")
    parser.add_argument("--skip-setup", action="store_true", help="跳过项目创建（已初始化）")
    parser.add_argument("--force", action="store_true", help="强制重新生成已有大纲")
    parser.add_argument("--status", action="store_true", help="查看任务进度")
    parser.add_argument("--mark-done", type=int, default=None, help="标记某章已完成")
    args = parser.parse_args()

    project_dir = args.project or args.project_root
    if not project_dir:
        print("❌ 请指定项目目录 (--project /path/to/教材)")
        sys.exit(1)

    root = Path(project_dir).expanduser().resolve()
    guides_dir = root / "output" / "写作大纲"

    # --status / --mark-done（不需要完整初始化）
    tasks_path = root / TASKS_FILE
    if args.status or args.mark_done:
        if not tasks_path.exists():
            print("❌ 任务清单不存在，请先初始化项目")
            sys.exit(1)
        tasks = load_or_init_tasks(str(root), str(guides_dir), force=args.status)
        if args.mark_done:
            for t in tasks:
                if t["chapter"] == args.mark_done:
                    t["status"] = "completed"
                    t["completed_at"] = datetime.now().isoformat()
            tasks_path.write_text(json.dumps(tasks, ensure_ascii=False, indent=2))
            print(f"✅ 第{args.mark_done}章 标记为已完成")
        else:
            show_status(tasks)
        return

    # Phase 1a: Setup
    if not args.skip_setup:
        print("📁 Phase 1a: 项目创建")
        if not setup_project(root, args.name, args.outline):
            print("   请放入提纲文件后重新运行")
            sys.exit(1)
        print(f"   ✅ 项目初始化完成: {root}\n")

    # Phase 1b: Generate outlines
    outline_docx = str(root / "input" / args.outline)
    chapters_info = parse_outline_docx(outline_docx)
    if not chapters_info:
        print("❌ 无法解析提纲文件")
        sys.exit(1)

    chapters_info.sort(key=lambda c: c["chapter"])
    if args.chapter:
        chapters_info = [c for c in chapters_info if c["chapter"] == args.chapter]
        if not chapters_info:
            print(f"❌ 未找到第{args.chapter}章")
            sys.exit(1)

    print(f"📖 Phase 1b: 解析到 {len(chapters_info)} 章")

    created = 0
    for ch_info in chapters_info:
        ch = ch_info["chapter"]
        title = ch_info["title"]
        out_path = guides_dir / f"writing-guide-ch{ch}.md"
        if out_path.exists() and not args.force:
            continue
        generate_chapter_skeleton(ch, title, str(root / "output"))
        created += 1
        print(f"  📝 writing-guide-ch{ch}.md")

    # Phase 1c: Validate
    print(f"\n📋 Phase 1c: 大纲QC")
    for ch_info in chapters_info:
        ch = ch_info["chapter"]
        fpath = str(guides_dir / f"writing-guide-ch{ch}.md")
        if not os.path.exists(fpath):
            continue
        result = validate_chapter(ch, fpath)
        status = "⚠️" if result["issues"] else "✅"
        print(f"  第{ch:>2}章 {status} | {result['size_kb']:>5}KB | "
              f"L1={result['l1_count']:>2}节 L2={result['l2_count']:>2}节")
        for issue in result["issues"]:
            print(f"       {issue}")

    # Phase 1d: Task list
    print(f"\n📝 Phase 1d: 任务清单")
    tasks = parse_outline_tasks(str(guides_dir))
    tasks_path = root / TASKS_FILE
    tasks_path.write_text(json.dumps(tasks, ensure_ascii=False, indent=2))
    print(f"   ✅ 已生成: {tasks_path}")

    # Summary
    print(f"\n{'='*50}")
    print(f"✅ 初始化完成：{len(chapters_info)} 章大纲骨架已生成")
    print(f"   下一步: Agent 填充每个 writing-guide-chX.md 的15个板块")
    print(f"   大纲目标体量: ≥68KB/章（填充后）")
    print(f"   建议: 先运行 domain_init.py --project {root} 完成领域注入")


if __name__ == "__main__":
    main()
