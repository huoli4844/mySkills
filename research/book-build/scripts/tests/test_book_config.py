"""Smoke tests for book_config.py — Config() loads config.yaml correctly."""

import sys
from pathlib import Path

SCRIPTS_DIR = str(Path(__file__).resolve().parent.parent)
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from book_config import Config


class TestConfigLoad:
    """Test Config() — loads config.yaml from the expected location."""

    def test_loads_without_error(self):
        """Config() instantiation succeeds (finds config.yaml)."""
        cfg = Config()
        assert cfg is not None
        assert repr(cfg).startswith("<Config")

    def test_textbook_name(self):
        """Config.textbook_name returns the name from config.yaml."""
        cfg = Config()
        assert cfg.textbook_name == "电磁兼容", (
            f"Expected '电磁兼容', got '{cfg.textbook_name}'"
        )

    def test_outline_file(self):
        """Config.outline_file returns the outline path."""
        cfg = Config()
        assert cfg.outline_file is not None
        assert cfg.outline_file.endswith(".docx") or isinstance(cfg.outline_file, str)

    def test_output_dir(self):
        """Config.output_dir returns a Path relative to the skill root."""
        cfg = Config()
        output = cfg.output_dir
        assert isinstance(output, Path)
        assert "output" in str(output)

    def test_source_books_sorted_by_priority(self):
        """Config.source_books returns books sorted by priority."""
        cfg = Config()
        books = cfg.source_books
        assert len(books) >= 3, f"Expected at least 3 source books, got {len(books)}"
        priorities = [b.get("priority", 99) for b in books]
        assert priorities == sorted(priorities), (
            f"Books not sorted by priority: {priorities}"
        )

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
        """KB path properties are accessible."""
        cfg = Config()
        assert cfg.kb_processed_dir is not None
        assert cfg.kb_raw_dir is not None
        assert cfg.kb_domain_dir is not None

    def test_workflow_mode(self):
        """Config.workflow_mode returns the default mode."""
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

    def test_get_book_by_author(self):
        """get_book_by_author() returns the matching book."""
        cfg = Config()
        book = cfg.get_book_by_author("路宏敏")
        assert book is not None
        assert book["author"] == "路宏敏"

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
