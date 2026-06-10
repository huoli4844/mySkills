"""Smoke tests for task_tracker.py — 任务进度管理。"""

import sys
from pathlib import Path

SCRIPTS_DIR = str(Path(__file__).resolve().parent.parent)
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from task_tracker import TaskTracker


def _make_chapters(n: int, start: int = 1):
    return [{"number": i, "title": f"第{i}章"} for i in range(start, start + n)]


class TestTaskTracker:
    """TaskTracker 进度管理全流程测试。"""

    def test_init_empty_project(self, tmp_path):
        """全新项目，进度文件不存在。"""
        tt = TaskTracker(str(tmp_path))
        assert tt.total == 0
        assert tt.current_chapter is None
        assert tt.status() == "未初始化"
        assert tt.has_progress() is False

    def test_init_from_outline(self, tmp_path):
        """从大纲初始化 12 章。"""
        tt = TaskTracker(str(tmp_path))
        tt.init_from_outline(_make_chapters(12))
        assert tt.total == 12
        assert tt.has_progress() is True
        assert tt.current_chapter["number"] == 1
        assert tt.current_chapter["status"] == "pending"
        assert tt.completed_count == 0

    def test_progress_file_created(self, tmp_path):
        """初始化后进度文件存在。"""
        tt = TaskTracker(str(tmp_path))
        tt.init_from_outline(_make_chapters(5))
        progress_path = tmp_path / "book-build-progress.yaml"
        assert progress_path.exists()

    def test_mark_in_progress(self, tmp_path):
        """标记进行中。"""
        tt = TaskTracker(str(tmp_path))
        tt.init_from_outline(_make_chapters(5))
        tt.mark_in_progress(3)
        assert tt.current_chapter["number"] == 3
        assert tt.current_chapter["status"] == "in_progress"

    def test_mark_completed(self, tmp_path):
        """完成一章后自动移到下一章。"""
        tt = TaskTracker(str(tmp_path))
        tt.init_from_outline(_make_chapters(5))
        tt.mark_completed(1)
        assert tt.completed_count == 1
        assert tt.current_chapter["number"] == 2
        assert tt.current_chapter["status"] == "pending"

    def test_mark_completed_moves_to_next_pending(self, tmp_path):
        """完成多章后指向第一个未完成的。"""
        tt = TaskTracker(str(tmp_path))
        tt.init_from_outline(_make_chapters(5))
        tt.mark_completed(1)
        tt.mark_completed(3)
        # 第2章还是 pending，应指向 2
        assert tt.current_chapter["number"] == 2

    def test_all_completed(self, tmp_path):
        """全部完成后的状态。"""
        tt = TaskTracker(str(tmp_path))
        tt.init_from_outline(_make_chapters(3))
        tt.mark_completed(1)
        tt.mark_completed(2)
        tt.mark_completed(3)
        assert tt.completed_count == 3
        assert tt.status() == "全部完成（3章）"
        assert tt.next_pending() is None

    def test_resume_session(self, tmp_path):
        """模拟中断后恢复：重新加载进度文件。"""
        tt1 = TaskTracker(str(tmp_path))
        tt1.init_from_outline(_make_chapters(6))
        tt1.mark_in_progress(3)

        # 模拟新会话
        tt2 = TaskTracker(str(tmp_path))
        assert tt2.has_progress() is True
        assert tt2.current_chapter["number"] == 3
        assert tt2.current_chapter["status"] == "in_progress"

    def test_summary(self, tmp_path):
        """summary() 返回正确的统计。"""
        tt = TaskTracker(str(tmp_path))
        tt.init_from_outline(_make_chapters(4))
        tt.mark_completed(1)
        tt.mark_in_progress(2)
        s = tt.summary()
        assert s["total"] == 4
        assert s["completed"] == 1
        assert s["in_progress"] == 1
        assert s["pending"] == 2

    def test_next_pending(self, tmp_path):
        """next_pending 找到第一个待处理的。"""
        tt = TaskTracker(str(tmp_path))
        tt.init_from_outline(_make_chapters(4))
        tt.mark_completed(1)
        n = tt.next_pending()
        assert n is not None
        assert n["number"] == 2

    def test_mark_skipped(self, tmp_path):
        """跳过某章不影响其他。"""
        tt = TaskTracker(str(tmp_path))
        tt.init_from_outline(_make_chapters(4))
        tt.mark_skipped(2)
        s = tt.summary()
        assert s["pending"] == 3  # skipped 不计入 pending

    def test_init_from_outline_preserves_completed(self, tmp_path):
        """已有完成记录的章，重新 init 时保持 completed 状态。"""
        tt1 = TaskTracker(str(tmp_path))
        tt1.init_from_outline(_make_chapters(5))
        tt1.mark_completed(1)

        # 模拟第二次 init（比如重新解析大纲）
        tt2 = TaskTracker(str(tmp_path))
        tt2.init_from_outline(_make_chapters(5))
        assert tt2.completed_count == 1  # 第1章保留已完成
        assert tt2.current_chapter["number"] == 2  # 从第2章开始

    def test_empty_outline(self, tmp_path):
        """空大纲不报错。"""
        tt = TaskTracker(str(tmp_path))
        tt.init_from_outline([])
        assert tt.total == 0
        assert tt.current_chapter is None
