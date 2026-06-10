#!/usr/bin/env python3
"""
generate_task_list.py — 从写作大纲生成写作任务列表。
读取各章写作大纲，解析出每节的目标体量和素材来源，
输出结构化任务清单，供 Agent 按顺序创作。

用法：
  python3 generate_task_list.py --project /path/to/教材 [--output tasks.json]
  python3 generate_task_list.py --project /path/to/教材 --status   # 查看进度
  python3 generate_task_list.py --project /path/to/教材 --mark-done 3  # 标记第3章完成
"""

import os
import re
import sys
import json
import argparse
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime


TASKS_FILE = "writing_tasks.json"


def load_or_init_tasks(project_root: str, guides_dir: str) -> List[Dict]:
    """加载已有任务列表，或从写作大纲初始化"""
    tasks_path = Path(project_root) / TASKS_FILE
    if tasks_path.exists():
        with open(tasks_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []


def parse_outline_tasks(guides_dir: str) -> List[Dict]:
    """从写作大纲解析创作任务"""
    guides_path = Path(guides_dir)
    tasks = []
    
    for fpath in sorted(guides_path.glob("writing-guide-ch*.md")):
        m = re.search(r'ch(\d+)', fpath.stem)
        if not m:
            continue
        ch = int(m.group(1))
        
        with open(fpath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 提取 L1 节
        l1_sections = re.findall(r'^###\s+(\d+\.\d+)\s+(.+)', content, re.MULTILINE)
        # 提取 L2 子节
        l2_sections = re.findall(r'^####\s+([\d.]+)\s+(.+)', content, re.MULTILINE)
        
        # 从大纲表格中提取目标体量
        targets = {}
        for line in content.split('\n'):
            if '|' not in line or 'KB' not in line:
                continue
            cols = [c.strip() for c in line.split('|')]
            if len(cols) >= 4 and re.match(r'^\d+\.\d+$', cols[1]):
                sec = cols[1]
                target_kb = re.search(r'(\d+(?:\.\d+)?)\s*KB', line)
                if target_kb:
                    targets[sec] = float(target_kb.group(1))
        
        task = {
            "chapter": ch,
            "title": "",
            "l1_sections": [f"{s[0]} {s[1][:60]}" for s in l1_sections],
            "l2_sections": [f"{s[0]} {s[1][:60]}" for s in l2_sections],
            "target_kb_per_section": targets,
            "status": "pending",
            "created_at": datetime.now().isoformat(),
        }
        
        # 从文件第一行找章标题
        for line in content.split('\n')[:5]:
            t = re.search(r'第' + str(ch) + r'章\s+(.+)', line)
            if t:
                task["title"] = t.group(1).strip()
                break
        
        tasks.append(task)
    
    return tasks


def show_status(tasks: List[Dict]):
    """显示任务进度"""
    print(f"\n{'章':>4} {'标题':30s} {'L1节':>4} {'L2节':>4} {'状态':10s}")
    print("-" * 60)
    
    counts = {"pending": 0, "in_progress": 0, "completed": 0}
    for t in tasks:
        status = t.get("status", "pending")
        counts[status] = counts.get(status, 0) + 1
        ch = t["chapter"]
        title = t.get("title", "")[:28]
        n1 = len(t.get("l1_sections", []))
        n2 = len(t.get("l2_sections", []))
        status_char = {"pending": "⏳", "in_progress": "✍️", "completed": "✅"}.get(status, "⏳")
        target = t.get("target_kb_per_section", {})
        target_info = f"~{sum(target.values()):.0f}KB" if target else ""
        print(f" 第{ch:>2}章 {title:28s} {n1:>3}节 {n2:>3}节 {status_char} {target_info:>8s}")
    
    total = len(tasks)
    done = counts.get("completed", 0)
    pct = done / total * 100 if total > 0 else 0
    print(f"\n 进度: {done}/{total} ({pct:.0f}%)")
    print(f" 待写: {counts.get('pending', 0)}  进行中: {counts.get('in_progress', 0)}  已完成: {done}")


def main():
    parser = argparse.ArgumentParser(description="从写作大纲生成写作任务列表")
    parser.add_argument("--project", required=True, help="项目根目录")
    parser.add_argument("--output", default=None, help="输出JSON路径（默认：project/writing_tasks.json）")
    parser.add_argument("--status", action="store_true", help="查看进度")
    parser.add_argument("--mark-done", type=int, default=None, help="标记某章已完成")
    parser.add_argument("--mark-progress", type=int, default=None, help="标记某章进行中")
    parser.add_argument("--force-init", action="store_true", help="重新从大纲初始化任务列表")
    args = parser.parse_args()
    
    project_root = Path(args.project).expanduser().resolve()
    guides_dir = str(project_root / "output" / "写作大纲")
    
    if not (project_root / "output" / "写作大纲").exists():
        print(f"❌ 写作大纲目录不存在: {guides_dir}")
        print("   请先运行 setup_project.py 创建项目，并将写作大纲放入 output/写作大纲/")
        sys.exit(1)
    
    # 加载或初始化
    if args.force_init or not (project_root / TASKS_FILE).exists():
        tasks = parse_outline_tasks(guides_dir)
        tasks_path = project_root / TASKS_FILE
        with open(tasks_path, 'w', encoding='utf-8') as f:
            json.dump(tasks, f, ensure_ascii=False, indent=2)
        print(f"✅ 已从 {len(tasks)} 章写作大纲生成任务列表: {tasks_path}")
    else:
        tasks = load_or_init_tasks(str(project_root), guides_dir)
    
    # 修改状态
    if args.mark_done:
        for t in tasks:
            if t["chapter"] == args.mark_done:
                t["status"] = "completed"
                t["completed_at"] = datetime.now().isoformat()
        with open(project_root / TASKS_FILE, 'w', encoding='utf-8') as f:
            json.dump(tasks, f, ensure_ascii=False, indent=2)
        print(f"✅ 第{args.mark_done}章 标记为已完成")
    
    if args.mark_progress:
        for t in tasks:
            if t["chapter"] == args.mark_progress:
                t["status"] = "in_progress"
        with open(project_root / TASKS_FILE, 'w', encoding='utf-8') as f:
            json.dump(tasks, f, ensure_ascii=False, indent=2)
        print(f"✍️  第{args.mark_progress}章 标记为进行中")
    
    # 显示状态
    if args.status or not any([args.mark_done, args.mark_progress, args.force_init]):
        show_status(tasks)
    
    # 输出JSON
    if args.output:
        out_path = Path(args.output)
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(tasks, f, ensure_ascii=False, indent=2)
        print(f"📝 已输出: {out_path}")


if __name__ == "__main__":
    main()
