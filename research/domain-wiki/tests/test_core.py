"""domain-wiki 轻量测试套件

运行方式:
  python3 -m pytest tests/ -v
  或
  python3 tests/test_core.py -v
"""

import json
import os
import sys
import tempfile
import unittest

# 添加 scripts 到路径
SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(SCRIPT_DIR, "scripts")
sys.path.insert(0, SCRIPT_DIR)
sys.path.insert(0, SCRIPTS_DIR)


class TestDagState(unittest.TestCase):
    """dag_state.py 单元测试"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.bdir = os.path.join(self.tmpdir, "book")
        os.makedirs(os.path.join(self.bdir, ".dag"), exist_ok=True)
        # 导入
        import dag_state as ds
        self.ds = ds

    def test_default_state(self):
        state = self.ds.ChapterState(self.bdir, "test_book", "1")
        self.assertEqual(state.book_id, "test_book")
        self.assertEqual(state.chapter, "1")
        self.assertEqual(state.get_status("concepts"), "pending")

    def test_set_status(self):
        state = self.ds.ChapterState(self.bdir, "test_book", "1")
        state.set_status("concepts", "done", files=5)
        state.save()

        # 重新加载
        state2 = self.ds.ChapterState(self.bdir, "test_book", "1")
        self.assertEqual(state2.get_status("concepts"), "done")
        self.assertEqual(state2.get_phase_count("concepts"), 5)

    def test_can_run_deps(self):
        state = self.ds.ChapterState(self.bdir, "test_book", "1")
        # chapter_toc has no deps, should be runnable
        can, reason = state.can_run("chapter_toc")
        self.assertTrue(can)

        # concepts depends on chapter_toc
        can, reason = state.can_run("concepts")
        self.assertFalse(can)

    def test_next_pending(self):
        state = self.ds.ChapterState(self.bdir, "test_book", "1")
        self.assertEqual(state.next_pending(), "chapter_toc")

        state.set_status("chapter_toc", "done")
        state.set_status("concepts", "done")
        self.assertEqual(state.next_pending(), "ke")

    def test_all_done(self):
        state = self.ds.ChapterState(self.bdir, "test_book", "1")
        self.assertFalse(state.all_done())

        for p in self.ds.PHASES:
            state.set_status(p["name"], "done")
        self.assertTrue(state.all_done())


class TestKGraphBasic(unittest.TestCase):
    """KGraph 基础测试——使用实际书籍目录（如果存在）"""

    @classmethod
    def setUpClass(cls):
        cls.real_book = os.path.expanduser(
            "~/Desktop/电磁兼容知识库/电磁兼容领域/工程电磁兼容第3版_路宏敏"
        )
        if not os.path.isdir(os.path.join(cls.real_book, "30_核心概念")):
            cls.real_book = None

    def test_import(self):
        from kg_builder import KGraph
        self.assertTrue(hasattr(KGraph, "build"))

    def test_empty_build(self):
        from kg_builder import KGraph
        with tempfile.TemporaryDirectory() as td:
            kg = KGraph(td, book_dir=td)
            stats = kg.build()
            self.assertEqual(stats["nodes"], 0)
            self.assertEqual(stats["edges"], 0)

    def _skip_if_no_real_book(self):
        if not self.real_book:
            self.skipTest("真实书籍目录不存在")

    def test_real_build(self):
        self._skip_if_no_real_book()
        from kg_builder import KGraph
        kb_root = os.path.dirname(os.path.dirname(self.real_book))
        kg = KGraph(kb_root, book_dir=self.real_book)
        stats = kg.build()
        self.assertGreater(stats["nodes"], 0, "应该从书籍目录找到节点")
        self.assertIn("type_counts", stats)

    def test_quality_check(self):
        self._skip_if_no_real_book()
        from kg_builder import KGraph
        kb_root = os.path.dirname(os.path.dirname(self.real_book))
        kg = KGraph(kb_root, book_dir=self.real_book)
        kg.build()
        q = kg.check_graph_quality()
        self.assertIn("summary", q)
        self.assertIn("issues", q)


class TestPipelineCommands(unittest.TestCase):
    """pipeline_v2.py CLI 参数解析测试"""

    def test_phase_a_help(self):
        import subprocess
        pipe = os.path.join(SCRIPTS_DIR, "pipeline_v2.py")
        r = subprocess.run([sys.executable, pipe, "--help"], capture_output=True, text=True)
        self.assertIn("phase-a", r.stdout)
        self.assertIn("run", r.stdout)
        self.assertIn("build-indices", r.stdout)

    def test_dag_state_import(self):
        """确保 dag_state.py 导入无报错"""
        import subprocess
        pipe = os.path.join(SCRIPTS_DIR, "dag_state.py")
        r = subprocess.run([sys.executable, "-c", "import sys; sys.path.insert(0,'scripts'); from dag_state import ChapterState, PipelineError; print('OK')"],
                           capture_output=True, text=True, cwd=os.path.dirname(SCRIPTS_DIR))
        self.assertIn("OK", r.stdout)


class TestDomainAgnostic(unittest.TestCase):
    """领域无关性验证测试"""

    def test_verify_script_runs(self):
        """验证领域无关检查脚本可以运行"""
        import subprocess
        script = os.path.join(SCRIPTS_DIR, "verify_domain_agnostic.sh")
        if os.path.isfile(script):
            r = subprocess.run(["bash", script], capture_output=True, text=True)
            # 脚本应正常完成（即使有失败，exit code 1 也是预期行为）
            print(f"  verify_domain_agnostic.sh: exit={r.returncode}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
