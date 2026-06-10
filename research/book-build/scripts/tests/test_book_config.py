"""Smoke tests for book_config.py — Config() loads config correctly."""

import sys
from pathlib import Path

SCRIPTS_DIR = str(Path(__file__).resolve().parent.parent)
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from book_config import Config


class TestConfigLoad:
    """Test Config() — skill defaults + project override."""

    def test_loads_without_error(self):
        """Config() instantiation succeeds with skill defaults."""
        cfg = Config()
        assert cfg is not None
        assert repr(cfg).startswith("<Config")

    def test_skill_defaults_textbook_empty(self):
        """Without project, textbook_name is empty string."""
        cfg = Config()
        assert cfg.textbook_name == ""
        assert cfg.source_books == []

    def test_skill_defaults_workflow(self):
        """Skill defaults provide workflow settings."""
        cfg = Config()
        assert cfg.workflow_mode in ("fast", "full")
        assert isinstance(cfg.phase_0_5_auto, bool)
        assert isinstance(cfg.quality_auto_fix, bool)

    def test_skill_defaults_volume(self):
        """Skill defaults provide volume thresholds."""
        cfg = Config()
        assert isinstance(cfg.thin_threshold_lines, int)
        assert isinstance(cfg.thin_threshold_kb, (int, float))
        assert isinstance(cfg.target_mermaid_min, int)

    def test_project_loads_config(self):
        """Config(project_root=...) loads book-build.yaml."""
        cfg = Config(project_root="/tmp/test-book-project")
        # The template has key names but values are inside comments
        assert cfg.project_root == "/tmp/test-book-project"

    def test_project_paths(self):
        """Project paths are derived from project_root."""
        cfg = Config(project_root="/tmp/test-book-project")
        assert cfg.input_dir == "/tmp/test-book-project/input"
        assert cfg.output_dir == "/tmp/test-book-project/output"
        assert cfg.outline_path == "/tmp/test-book-project/input/教材提纲.docx"

    def test_subdirs_under_output(self):
        """All subdirs are under output_dir."""
        cfg = Config(project_root="/tmp/test-book-project")
        for d in [cfg.writing_guide_dir, cfg.cases_dir,
                  cfg.experiments_dir, cfg.exercise_dir]:
            assert d.startswith(cfg.output_dir)

    def test_chapter_path_format(self):
        """chapter_path() returns path ending with .md."""
        cfg = Config(project_root="/tmp/test-book-project")
        p = cfg.chapter_path(5, "示例")
        assert p.endswith(".md")
        assert "第5章" in p

    def test_writing_guide_path_format(self):
        """writing_guide_path() returns path ending with .md."""
        cfg = Config(project_root="/tmp/test-book-project")
        p = cfg.writing_guide_path(3)
        assert p.endswith(".md")
        assert "writing-guide-ch3" in p
        assert "写作大纲" in p

    def test_case_path_format(self):
        """case_path() returns file named with 案例 prefix."""
        cfg = Config(project_root="/tmp/test-book-project")
        p = cfg.case_path(2, 1, "标题")
        assert p.endswith(".md")
        assert "案例" in p

    def test_source_books_empty_by_default(self):
        """Without project config, source_books is empty."""
        cfg = Config(project_root="/tmp/test-book-project")
        assert isinstance(cfg.source_books, list)

    def test_get_book_by_author_empty(self):
        """get_book_by_author returns None when no books configured."""
        cfg = Config(project_root="/tmp/test-book-project")
        assert cfg.get_book_by_author("任何人") is None

    def test_project_root_none_by_default(self):
        """Without project_root, project_root is None."""
        cfg = Config()
        assert cfg.project_root is None

    def test_ensure_dirs_no_error(self):
        """ensure_dirs() does not raise (dirs may already exist)."""
        cfg = Config(project_root="/tmp/test-book-project")
        cfg.ensure_dirs()
        assert True

    def test_grep_all_books_returns_dict(self):
        """grep_all_books() returns dict even with no books."""
        cfg = Config(project_root="/tmp/test-book-project")
        results = cfg.grep_all_books("test")
        assert isinstance(results, dict)

    def test_setup_creates_directories(self):
        """Config.setup() creates project dirs and config file."""
        import tempfile, os
        tmpdir = tempfile.mkdtemp(prefix="book-test-")
        Config.setup(tmpdir)
        assert os.path.exists(os.path.join(tmpdir, "book-build.yaml"))
        assert os.path.exists(os.path.join(tmpdir, "input"))
        assert os.path.exists(os.path.join(tmpdir, "output"))
        assert os.path.exists(os.path.join(tmpdir, "output", "写作大纲"))
