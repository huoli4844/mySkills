#!/usr/bin/env python3
"""
auto_write.py — 自动按任务列表逐章写作。

流程：
  1. 读取 writing_tasks.json 找到第一个 pending 章节
  2. 读取对应的写作大纲（output/写作大纲/writing-guide-chX.md）
  3. 读取 book-build.yaml 获取参考书路径
  4. 通过 delegate_task（跨进程信号）或直接输出指令供 Agent 执行
  5. 创作完成后标记为 completed

用法：
  python3 scripts/auto_write.py --project /path/to/教材          # 写下一章
  python3 scripts/auto_write.py --project /path/to/教材 --all    # 遍历全部待写
  python3 scripts/auto_write.py --project /path/to/教材 --chapter 3  # 指定章
"""

import os
import re
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict


def load_tasks(project_root: str) -> List[Dict]:
    tasks_path = Path(project_root) / "writing_tasks.json"
    if not tasks_path.exists():
        print(f"❌ 任务列表不存在: {tasks_path}")
        print("   请先运行 generate_task_list.py --project ... --force-init")
        sys.exit(1)
    with open(tasks_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_tasks(project_root: str, tasks: List[Dict]):
    tasks_path = Path(project_root) / "writing_tasks.json"
    with open(tasks_path, 'w', encoding='utf-8') as f:
        json.dump(tasks, f, ensure_ascii=False, indent=2)


def load_writing_guide(project_root: str, chapter: int) -> str:
    guide_path = Path(project_root) / "output" / "写作大纲" / f"writing-guide-ch{chapter}.md"
    if not guide_path.exists():
        print(f"❌ 写作大纲不存在: {guide_path}")
        sys.exit(1)
    return guide_path.read_text(encoding='utf-8')


def read_config(project_root: str) -> dict:
    cfg_path = Path(project_root) / "book-build.yaml"
    cfg = {}
    if cfg_path.exists():
        import yaml
        with open(cfg_path, 'r', encoding='utf-8') as f:
            cfg = yaml.safe_load(f) or {}
    return cfg


def check_existing_chapter(project_root: str, chapter: int) -> bool:
    """检查该章是否已有内容（>5KB 认为已写）"""
    output_dir = Path(project_root) / "output"
    for f in output_dir.glob(f"第{chapter}章-*.md"):
        if f.stat().st_size > 5120:  # 5KB
            return True
    return False


def build_prompt(project_root: str, chapter: int, guide_content: str, cfg: dict) -> dict:
    """构建写作 prompt，返回结构化 dict 供 delegate_task"""
    # 获取参考书路径
    books = cfg.get("source_books", [])
    book_info = "\n".join(
        f"  - {b.get('display_name', '?')}（{b.get('author', '?')}）: {b.get('path', '?')}"
        for b in books
    )
    
    # 获取已有章节大小（供参考）
    output_dir = Path(project_root) / "output"
    existing = ""
    for f in sorted(output_dir.glob("第*.md")):
        m = re.search(r'第(\d+)章', f.name)
        if m:
            ch = int(m.group(1))
            size_kb = f.stat().st_size / 1024
            existing += f"  第{ch}章: {size_kb:.0f}KB\n"
    
    # 构建 agent_goal 和 context
    goal = f"为教材项目创作第{chapter}章完整内容"
    
    context = f"""# 教材写作任务：第{chapter}章

## 项目信息
- 项目路径: {project_root}
- 参考教材:
{book_info}

## 已有章节体量参考
{existing}

## 写作大纲
请严格按照以下写作大纲创作第{chapter}章内容：

```
{guide_content}
```

## 写作规范
1. 公式必须编号：每个 $$ 块内的公式用 \\\\tag{{{chapter}-XX}} 编号，编号连续
2. 格式：\\\\tag{{}} 独占一行，放在 $$ 闭合之前
3. 引用块内公式使用 > $$ > 公式 > \\\\tag{{}} > $$
4. 案例必须来自公开真实事件，不得从参考教材摘抄
5. 每章开头为 ## 内容提要 + 学习目标（不要 Bloom 分类标签）
6. 禁止添加 ## 本章写作说明、## 12条军规落实检查、## ★ 全章核心公式总结

## 输出要求
- 输出完整的第{chapter}章 Markdown 文件内容
- 文件保存到: {output_dir}/第{chapter}章-标题.md
- 包含：编号公式、表格、Mermaid 图、例题、习题、参考文献
"""
    
    return {
        "goal": goal,
        "context": context,
        "chapter": chapter,
        "guide_path": str(Path(project_root) / "output" / "写作大纲" / f"writing-guide-ch{chapter}.md"),
        "output_path": str(output_dir / f"第{chapter}章-标题.md")
    }


def auto_write_chapter(project_root: str, chapter: int, task: dict, force: bool = False):
    """为单章生成 delegate_task-ready 任务"""
    print(f"\n{'='*60}")
    print(f"✍️  第{chapter}章: {task.get('title', '')}")
    print(f"{'='*60}")
    
    guide = load_writing_guide(project_root, chapter)
    cfg = read_config(project_root)
    
    if check_existing_chapter(project_root, chapter):
        if force:
            print(f"  ⚠️  第{chapter}章已有内容，--force 覆盖")
        else:
            print(f"  ⏭️  第{chapter}章已有内容（用 --force 覆盖）")
            return False
    
    task_data = build_prompt(project_root, chapter, guide, cfg)
    
    # 输出结构化任务文件
    task_dir = Path(project_root) / ".hermes" / "tasks"
    task_dir.mkdir(parents=True, exist_ok=True)
    task_path = task_dir / f"write_ch{chapter}.json"
    with open(task_path, 'w', encoding='utf-8') as f:
        json.dump(task_data, f, ensure_ascii=False, indent=2)
    
    print(f"  📝 任务文件: {task_path}")
    print(f"\n  将该任务提交给 delegate_task:")
    print(f"  -> goal:     {task_data['goal']}")
    print(f"  -> context:  包含写作大纲、参考书路径、写作规范")
    print(f"  -> toolsets: terminal, file")
    print(f"\n  或读取 .hermes/tasks/write_ch{chapter}.json 获取完整任务数据")
    
    return True


def main():
    parser = argparse.ArgumentParser(description="自动按任务列表逐章写作")
    parser.add_argument("--project", required=True, help="项目根目录")
    parser.add_argument("--chapter", type=int, default=None, help="指定章节（可选）")
    parser.add_argument("--all", action="store_true", help="遍历全部待写章节")
    parser.add_argument("--force", action="store_true", help="覆盖已有内容")
    args = parser.parse_args()
    
    project_root = Path(args.project).expanduser().resolve()
    tasks = load_tasks(str(project_root))
    
    if args.chapter:
        # 写指定章节（不管状态）
        target = [t for t in tasks if t["chapter"] == args.chapter]
        if not target:
            print(f"❌ 未找到第{args.chapter}章")
            sys.exit(1)
        auto_write_chapter(str(project_root), args.chapter, target[0], args.force)
    
    elif args.all:
        # 遍历全部 pending 或 in_progress
        for task in tasks:
            if task.get("status") in ("pending", "in_progress"):
                task["status"] = "in_progress"
                save_tasks(str(project_root), tasks)
                wrote = auto_write_chapter(str(project_root), task["chapter"], task, args.force)
                if wrote:
                    task["status"] = "completed"
                    task["completed_at"] = datetime.now().isoformat()
                    save_tasks(str(project_root), tasks)
                    print(f"  ✅ 第{task['chapter']}章 标记为已完成")
                else:
                    print(f"  ⏭️  第{task['chapter']}章 跳过")
        print(f"\n✅ 全部完成")
    
    else:
        # 写第一个 pending
        for task in tasks:
            if task.get("status") == "pending":
                auto_write_chapter(str(project_root), task["chapter"], task, args.force)
                break
        else:
            print("✅ 所有章节已完成，没有待写任务")


if __name__ == "__main__":
    main()
