"""Tests for batch_fix_formula_numbers.py — backup, process_file, helpers."""

import sys
import os
from pathlib import Path
import re

SCRIPTS_DIR = str(Path(__file__).resolve().parent.parent)
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

import batch_fix_formula_numbers as bff


def _write_file(root: Path, basename: str, content: str) -> str:
    """Write a temp file and return its path."""
    p = root / basename
    p.write_text(content, encoding='utf-8')
    return str(p)


class TestBackup:
    """Test backup() — creates .bak copy."""

    def test_backup_created(self, temp_dir):
        root = temp_dir["root"]
        path = _write_file(root, "test.md", "hello world")
        bff.backup(path)
        bak_path = path + '.bak'
        assert os.path.exists(bak_path)
        assert Path(bak_path).read_text() == "hello world"

    def test_backup_not_overwrite(self, temp_dir):
        root = temp_dir["root"]
        path = _write_file(root, "test.md", "hello world")
        bff.backup(path)
        Path(path).write_text("modified", encoding='utf-8')
        bff.backup(path)
        assert Path(path + '.bak').read_text() == "hello world"


class TestProcessFile:
    """Test process_file() — formula numbering pipeline."""

    def test_process_file_basic(self, temp_dir):
        root = temp_dir["root"]
        path = _write_file(root, "第3章-搭接技术.md",
            "## 3.1 搭接\n\n$$\nZ = R + j\\omega L\n$$\n\n$$\nI = \\frac{V}{Z}\n$$\n")
        n_tags, was_unclosed = bff.process_file(path)
        assert n_tags == 2
        assert was_unclosed is False
        result = Path(path).read_text(encoding='utf-8')
        assert r'\tag{3-1}' in result
        assert r'\tag{3-2}' in result

    def test_process_file_empty(self, temp_dir):
        root = temp_dir["root"]
        path = _write_file(root, "第6章-空.md", "")
        n_tags, was_unclosed = bff.process_file(path)
        assert n_tags == 0

    def test_process_file_no_formulas(self, temp_dir):
        root = temp_dir["root"]
        path = _write_file(root, "第7章-说明.md", "# 第7章\n\n本章无公式。\n")
        n_tags, was_unclosed = bff.process_file(path)
        assert n_tags == 0
        result = Path(path).read_text(encoding='utf-8')
        assert '\\tag' not in result

    def test_process_file_orphan_tags(self, temp_dir):
        root = temp_dir["root"]
        path = _write_file(root, "第4章-屏蔽.md",
            "$$\nE = \\frac{Q}{4\\pi\\epsilon r^2}\n$$\n\\tag{4-1}\n$$\nB = \\mu H\n$$\n")
        bff.process_file(path)
        result = Path(path).read_text(encoding='utf-8')
        tags = re.findall(r'\\tag\{4-(\d+)\}', result)
        assert len(tags) <= 2


class TestDollarBoundary:
    """Test is_dollar_boundary and plumbing helpers."""

    def test_is_dollar_boundary(self):
        assert bff.is_dollar_boundary('$$') is True
        assert bff.is_dollar_boundary('> $$') is True
        assert bff.is_dollar_boundary('$$ ') is False
        assert bff.is_dollar_boundary('text') is False


class TestCleanupEmpty:
    """Test cleanup_empty_consecutive_dollars."""

    def test_empty_blocks_removed(self):
        result = bff.cleanup_empty_consecutive_dollars(["$$", "$$"])
        assert result == []

    def test_text_preserved(self):
        result = bff.cleanup_empty_consecutive_dollars(["text", "$$", "math", "$$"])
        assert result == ["text", "$$", "math", "$$"]

    def test_adjacent_empty_removed(self):
        result = bff.cleanup_empty_consecutive_dollars(["a", "$$", "$$", "b"])
        assert result == ["a", "b"]

    def test_blockquote_empty_removed(self):
        result = bff.cleanup_empty_consecutive_dollars(["> $$", "> $$"])
        assert result == []


class TestFindUnclosed:
    """Test find_unclosed_dollar."""

    def test_no_unclosed(self):
        has, pos = bff.find_unclosed_dollar(["$$", "math", "$$"])
        assert has is False

    def test_unclosed(self):
        has, pos = bff.find_unclosed_dollar(["$$", "math"])
        assert has is True
        assert pos == 0

    def test_blockquote_unclosed(self):
        has, pos = bff.find_unclosed_dollar(["> $$", "math"])
        assert has is True
