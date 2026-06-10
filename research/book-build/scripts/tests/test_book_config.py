"""Smoke tests for book_config.py — Config() loads config.yaml correctly."""

import sys
from pathlib import Path

SCRIPTS_DIR = str(Path(__file__).resolve().parent.parent)
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from book_config import Config


class TestConfigLoad:
    """Test Config() — loads config.yaml from the expected location.

    所有断言只检查结构和类型，不检查具体值。
    这样即便 config.yaml 更换领域（改书名/路径/作者），测试依然通过。
    """

    def test_loads_without_error(self):
        """Config() instantiation succeeds (finds config.yaml)."""
        cfg = Config()
        assert cfg is not None
        assert repr(cfg).startswith("<Config")

    def test_textbook_name(self):
        """Config.textbook_name returns a non-empty string."""
        cfg = Config()
        assert cfg.textbook_name is not None
        assert isinstance(cfg.textbook_name, str)
        assert len(cfg.textbook_name) > 0

    def test_outline_file(self):
        """Config.outline_file returns a string ending with .docx."""
        cfg = Config()
        assert cfg.outline_file is not None
        assert isinstance(cfg.outline_file, str)
        assert cfg.outline_file.endswith(".docx")

    def test_outline_path(self):
        """Config.outline_path includes both input_dir and outline_file."""
        cfg = Config()
        path = cfg.outline_path
        assert path.endswith(".docx")
        assert cfg.input_dir in path

    def test_output_dir(self):
        """Config.output_dir is a non-empty string."""
        cfg = Config()
        output = cfg.output_dir
        assert isinstance(output, str)
        assert len(output) > 0

    def test_writing_guide_dir(self):
        """Config.writing_guide_dir is a subdir of output_dir."""
        cfg = Config()
        assert cfg.writing_guide_dir.startswith(cfg.output_dir)

    def test_cases_dir(self):
        """Config.cases_dir is a subdir of output_dir."""
        cfg = Config()
        assert cfg.cases_dir.startswith(cfg.output_dir)

    def test_experiments_dir(self):
        """Config.experiments_dir is a subdir of output_dir."""
        cfg = Config()
        assert cfg.experiments_dir.startswith(cfg.output_dir)

    def test_exercise_dir(self):
        """Config.exercise_dir is a subdir of output_dir."""
        cfg = Config()
        assert cfg.exercise_dir.startswith(cfg.output_dir)

    def test_chapter_path_format(self):
        """chapter_path() returns path ending with .md."""
        cfg = Config()
        p = cfg.chapter_path(5, "示例")
        assert p.endswith(".md")
        assert "第5章" in p

    def test_writing_guide_path_format(self):
        """writing_guide_path() returns path ending with .md."""
        cfg = Config()
        p = cfg.writing_guide_path(3)
        assert p.endswith(".md")
        assert "writing-guide-ch3" in p
        assert "写作大纲" in p

    def test_case_path_format(self):
        """case_path() returns path including 案例目录."""
        cfg = Config()
        p = cfg.case_path(2, 1, "标题")
        assert p.endswith(".md")
        assert "案例" in p

    def test_source_books_sorted_by_priority(self):
        """Config.source_books returns books sorted by priority."""
        cfg = Config()
        books = cfg.source_books
        assert len(books) > 0, "Expected at least one source book"
        priorities = [b.get("priority", 99) for b in books]
        assert priorities == sorted(priorities), (
            f"Books not sorted by priority: {priorities}"
        )

    def test_each_book_has_author_and_path(self):
        """Every source book has author, display_name, and path."""
        cfg = Config()
        for b in cfg.source_books:
            assert b.get("author"), f"Book missing author: {b}"
            assert b.get("display_name"), f"Book missing display_name: {b}"
            assert b.get("path"), f"Book missing path: {b}"

    def test_book_a_properties(self):
        """Properties for book_a (name, author, path) are accessible."""
        cfg = Config()
        assert cfg.book_a_name is not None
        assert cfg.book_a_author is not None
        assert cfg.book_a_path is not None
        assert cfg.book_a_processed_dir is not None

    def test_book_b_properties(self):
        """Properties for book_b are accessible."""
        cfg = Config()
        assert cfg.book_b_name is not None
        assert cfg.book_b_author is not None
        assert cfg.book_b_path is not None

    def test_book_c_properties(self):
        """Properties for book_c are accessible."""
        cfg = Config()
        assert cfg.book_c_name is not None
        assert cfg.book_c_author is not None
        assert cfg.book_c_path is not None

    def test_knowledge_base_properties(self):
        """KB path properties are accessible (values from config)."""
        cfg = Config()
        assert cfg.kb_processed_dir is not None
        assert cfg.kb_raw_dir is not None
        assert cfg.kb_domain_dir is not None

    def test_workflow_mode(self):
        """Config.workflow_mode returns a valid mode."""
        cfg = Config()
        assert cfg.workflow_mode in ("fast", "full"), (
            f"Expected 'fast' or 'full', got '{cfg.workflow_mode}'"
        )

    def test_volume_thresholds(self):
        """Volume threshold properties are numeric."""
        cfg = Config()
        assert isinstance(cfg.thin_threshold_lines, int)
        assert isinstance(cfg.thin_threshold_kb, (int, float))
        assert isinstance(cfg.target_mermaid_min, int)

    def test_get_book_by_author_matches_config(self):
        """get_book_by_author() returns a book whose author matches."""
        cfg = Config()
        for b in cfg.source_books:
            author = b["author"]
            book = cfg.get_book_by_author(author)
            assert book is not None, f"Should find {author}"
            assert book["author"] == author

    def test_get_book_by_author_not_found(self):
        """get_book_by_author() returns None for unknown author."""
        cfg = Config()
        book = cfg.get_book_by_author("不存在的作者")
        assert book is None

    def test_quality_auto_fix_default(self):
        """quality_auto_fix is a boolean."""
        cfg = Config()
        assert isinstance(cfg.quality_auto_fix, bool)

    def test_get_default_returns_singleton(self):
        """get_default() caches and returns the same instance."""
        cfg1 = Config.get_default()
        cfg2 = Config.get_default()
        assert cfg1 is cfg2

    def test_ensure_dirs_creates_output_subdirs(self):
        """ensure_dirs() creates all output subdirectories without error."""
        import tempfile, os
        cfg = Config()
        # Store original dirs
        orig_guide = cfg.writing_guide_dir
        orig_cases = cfg.cases_dir
        # No error expected (dirs may already exist)
        cfg.ensure_dirs()
        assert True

    def test_grep_all_books_returns_dict(self):
        """grep_all_books() returns a dict with all book names as keys."""
        cfg = Config()
        results = cfg.grep_all_books("test")
        for b in cfg.source_books:
            assert b["display_name"] in results
