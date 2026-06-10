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


def build_prompt(project_root: str, chapter: int, guide_content: str, cfg: dict) -> str:
    """构建写作 prompt"""
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
    
    prompt = f"""# 教材写作任务：第{chapter}章

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
    return prompt


def auto_write_chapter(project_root: str, chapter: int, task: dict):
    """为单章执行写作"""
    print(f"\n{'='*60}")
    print(f"✍️  开始写第{chapter}章: {task.get('title', '')}")
    print(f"{'='*60}")
    
    # 加载大纲
    guide = load_writing_guide(project_root, chapter)
    cfg = read_config(project_root)
    
    # 检查是否已有内容
    if check_existing_chapter(project_root, chapter):
        print(f"  ⚠️  第{chapter}章已有内容（>5KB），跳过（用 --force 覆盖）")
        return False
    
    # 构建 prompt
    prompt = build_prompt(project_root, chapter, guide, cfg)
    
    # 输出 prompt 到文件，供 Agent 或人类使用
    prompt_dir = Path(project_root) / ".hermes"
    prompt_dir.mkdir(exist_ok=True)
    prompt_path = prompt_dir / f"write_ch{chapter}.prompt.md"
    prompt_path.write_text(prompt, encoding='utf-8')
    
    print(f"  📝 写作指令已生成: {prompt_path}")
    print(f"  📖 使用写作大纲: output/写作大纲/writing-guide-ch{chapter}.md")
    print(f"  🎯 目标: 完成第{chapter}章创作")
    print(f"\n  将 prompt 文件内容复制给 Agent 后执行:")
    print(f"  -> 读取 {prompt_path}")
    print(f"  -> 按照大纲要求创作第{chapter}章")
    print(f"  -> 保存到 output/ 目录")
    print(f"  -> 运行 batch_fix_formula_numbers.py 修复公式编号")
    
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
        auto_write_chapter(str(project_root), args.chapter, target[0])
    
    elif args.all:
        # 遍历全部 pending 或 in_progress
        for task in tasks:
            if task.get("status") in ("pending", "in_progress"):
                task["status"] = "in_progress"
                save_tasks(str(project_root), tasks)
                wrote = auto_write_chapter(str(project_root), task["chapter"], task)
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
                auto_write_chapter(str(project_root), task["chapter"], task)
                break
        else:
            print("✅ 所有章节已完成，没有待写任务")


if __name__ == "__main__":
    main()
