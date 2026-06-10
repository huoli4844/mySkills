"""task_tracker.py — 教材编写任务进度管理。

在项目根目录创建 book-build-progress.yaml，记录：
  - 总共多少章（从大纲解析得出）
  - 每章的状态（pending/in_progress/completed/skipped）
  - 当前处理到哪一章
  - 上次更新时间

Agent 每次进入时先检查进度文件，从中断处继续。

用法：
    from task_tracker import TaskTracker

    tt = TaskTracker(project_root="/path/to/project")
    tt.init_from_outline([{"number": 1, "title": "绪论"}, ...])

    tt.current_chapter   # → {"number": 1, "title": "绪论", "status": "pending"}
    tt.mark_in_progress(1)
    tt.mark_completed(1)
    tt.next_pending()    # → {"number": 2, ...}

    tt.status()          # → "第2章/共12章 (in_progress)"
"""

import os
import time
from typing import List, Dict, Optional, Any

PROGRESS_FILENAME = "book-build-progress.yaml"


class TaskTracker:
    """教材编写任务进度管理器。"""

    def __init__(self, project_root: str):
        self._project_root = project_root
        self._progress_path = os.path.join(project_root, PROGRESS_FILENAME)
        self._data = self._load()

    # ── 文件读写 ──

    def _load(self) -> dict:
        """加载进度文件，不存在则返回空结构。"""
        if not os.path.exists(self._progress_path):
            return {"chapters": [], "current_index": 0, "last_updated": None}
        import yaml
        with open(self._progress_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {"chapters": [], "current_index": 0, "last_updated": None}

    def _save(self):
        """保存进度文件。"""
        self._data["last_updated"] = time.strftime("%Y-%m-%d %H:%M:%S")
        import yaml
        with open(self._progress_path, "w", encoding="utf-8") as f:
            yaml.dump(self._data, f, allow_unicode=True, default_flow_style=False,
                       sort_keys=False, encoding="utf-8")

    # ── 初始化 ──

    def init_from_outline(self, chapters: List[Dict[str, Any]]):
        """从大纲解析结果初始化进度表。

        chapters 格式: [{"number": 1, "title": "绪论"}, ...]
        如果进度文件已存在且有完成记录，保留已完成状态，只追加新章。
        """
        existing = {c["number"]: c for c in self._data["chapters"] if c.get("status") == "completed"}

        new_list = []
        for ch in chapters:
            num = ch["number"]
            if num in existing:
                # 保留已完成状态
                entry = existing[num]
                entry["title"] = ch.get("title", entry.get("title", ""))
                new_list.append(entry)
            else:
                new_list.append({
                    "number": num,
                    "title": ch.get("title", ""),
                    "status": "pending",
                })

        # 找到第一个未完成的作为 current_index
        current_index = 0
        for i, c in enumerate(new_list):
            if c.get("status") == "pending":
                current_index = i
                break

        self._data["chapters"] = new_list
        self._data["current_index"] = current_index
        self._save()

    def has_progress(self) -> bool:
        """是否已有进度记录（可继续）。"""
        return bool(self._data.get("chapters"))

    # ── 查询 ──

    @property
    def chapters(self) -> List[Dict]:
        return list(self._data.get("chapters", []))

    @property
    def total(self) -> int:
        return len(self._data.get("chapters", []))

    @property
    def current_chapter(self) -> Optional[Dict]:
        """返回当前章信息，若无则返回 None。"""
        idx = self._data.get("current_index", 0)
        chapters = self._data.get("chapters", [])
        if 0 <= idx < len(chapters):
            return dict(chapters[idx])
        return None

    @property
    def completed_count(self) -> int:
        return sum(1 for c in self._data.get("chapters", [])
                   if c.get("status") == "completed")

    def next_pending(self) -> Optional[Dict]:
        """找到下一个 pending 的章节。"""
        for c in self._data.get("chapters", []):
            if c.get("status") == "pending":
                idx = self._data["chapters"].index(c)
                self._data["current_index"] = idx
                self._save()
                return dict(c)
        return None

    # ── 状态变更 ──

    def mark_in_progress(self, chapter_num: int):
        """标记某章为进行中。"""
        for i, c in enumerate(self._data.get("chapters", [])):
            if c["number"] == chapter_num:
                c["status"] = "in_progress"
                self._data["current_index"] = i
                self._save()
                return True
        return False

    def mark_completed(self, chapter_num: int):
        """标记某章为已完成，并自动移到下一章。"""
        for c in self._data.get("chapters", []):
            if c["number"] == chapter_num:
                c["status"] = "completed"
                break
        # current_index 移到下一个未完成的
        next_idx = None
        for i, c in enumerate(self._data.get("chapters", [])):
            if c.get("status") == "pending":
                next_idx = i
                break
        if next_idx is not None:
            self._data["current_index"] = next_idx
        self._save()
        return True

    def mark_skipped(self, chapter_num: int):
        """标记某章为跳过（提纲有但无需编写）。"""
        for c in self._data.get("chapters", []):
            if c["number"] == chapter_num:
                c["status"] = "skipped"
                self._save()
                return True
        return False

    # ── 报告 ──

    def status(self) -> str:
        """返回人类可读的状态摘要。"""
        total = self.total
        if total == 0:
            return "未初始化"
        done = self.completed_count
        if done == total:
            return f"全部完成（{total}章）"
        current = self.current_chapter
        if current:
            ch = current
            return f"第{ch['number']}章「{ch['title']}」/共{total}章 ({ch['status']})"
        return f"{done}/{total} 章完成"

    def summary(self) -> Dict:
        """返回状态数据字典。"""
        chapters = self._data.get("chapters", [])
        return {
            "total": len(chapters),
            "completed": self.completed_count,
            "pending": sum(1 for c in chapters if c.get("status") == "pending"),
            "in_progress": sum(1 for c in chapters if c.get("status") == "in_progress"),
            "current": self.current_chapter,
            "updated": self._data.get("last_updated"),
        }


def main():
    """CLI 入口：查看/管理进度。"""
    import argparse, sys
    parser = argparse.ArgumentParser(description="教材编写进度管理")
    parser.add_argument("--project", "-p", required=True, help="项目根目录")
    parser.add_argument("--status", action="store_true", help="查看进度")
    parser.add_argument("--mark", choices=["in_progress", "completed", "skipped"],
                        help="标记某章状态（配合 --chapter）")
    parser.add_argument("--chapter", type=int, help="章号")
    args = parser.parse_args()

    tt = TaskTracker(args.project)

    if args.status:
        print(tt.status())
        s = tt.summary()
        print(f"总章: {s['total']}  已完成: {s['completed']}  进行中: {s['in_progress']}  待处理: {s['pending']}")
        if tt.current_chapter:
            cc = tt.current_chapter
            print(f"当前: 第{cc['number']}章「{cc['title']}」({cc['status']})")
        return

    if args.mark and args.chapter:
        fn = getattr(tt, f"mark_{args.mark}", None)
        if fn:
            fn(args.chapter)
            print(f"✅ 第{args.chapter}章 → {args.mark}")
        else:
            print(f"❌ 不支持的操作: {args.mark}", file=sys.stderr)
            sys.exit(1)
        return

    parser.print_help()


if __name__ == "__main__":
    main()
