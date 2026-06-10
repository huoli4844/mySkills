"""Smoke tests for renumber.py — backup, detect_chapter, and renumber."""

import sys
import os
from pathlib import Path

# Ensure book-build scripts are importable
SCRIPTS_DIR = str(Path(__file__).resolve().parent.parent)
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

import renumber


class TestDetectChapter:
    """Test detect_chapter() — infers chapter number from filename or tags."""

    def test_from_filename_chinese(self, temp_dir):
        """第N章-xxx.md → chapter=N"""
        path = str(temp_dir["paths"]["ch3"])
        content = temp_dir["file_contents"]["ch3"]
        ch = renumber.detect_chapter(path, content)
        assert ch == "3", f"Expected '3', got '{ch}'"

    def test_from_filename_english(self, temp_dir):
        """ChN-xxx.md → chapter=N"""
        root = temp_dir["root"]
        f = root / "Ch5-test.md"
        f.write_text("some content")
        ch = renumber.detect_chapter(str(f), "some content")
        assert ch == "5", f"Expected '5', got '{ch}'"

    def test_from_existing_tags(self, temp_dir):
        """Fallback to first existing tag if filename has no chapter hint."""
        root = temp_dir["root"]
        f = root / "notes.md"
        content = "$$\n\\tag{7-3}\n$$\n"
        f.write_text(content)
        ch = renumber.detect_chapter(str(f), content)
        assert ch == "7", f"Expected '7', got '{ch}'"

    def test_default_when_no_hint(self, temp_dir):
        """No filename hint and no tags → default '1'."""
        root = temp_dir["root"]
        f = root / "misc.md"
        f.write_text("no formulas")
        ch = renumber.detect_chapter(str(f), "no formulas")
        assert ch == "1", f"Expected '1', got '{ch}'"

    def test_empty_file(self, temp_dir):
        """Empty file → detects chapter from filename even with empty content."""
        path = str(temp_dir["paths"]["empty"])
        content = temp_dir["file_contents"]["empty"]
        ch = renumber.detect_chapter(path, content)
        # Filename is "第6章-空.md" so chapter 6
        assert ch == "6"


class TestBackup:
    """Test backup() — creates .bak copy."""

    def test_backup_created(self, temp_dir):
        """backup() creates .bak file with same content."""
        path = temp_dir["paths"]["ch3"]
        bak = renumber.backup(str(path))
        bak_path = Path(bak)
        assert bak_path.exists(), f"Backup {bak} not created"
        assert bak_path.read_text() == path.read_text()

    def test_backup_idempotent(self, temp_dir):
        """backup() does NOT overwrite existing .bak."""
        path = temp_dir["paths"]["ch3"]
        first = renumber.backup(str(path))
        second = renumber.backup(str(path))
        assert first == second


class TestRenumber:
    """Test renumber() — full renumber pipeline."""

    def test_renumber_basic(self, temp_dir):
        """Basic renumber: formulas get sequential tags."""
        path = temp_dir["paths"]["ch3"]
        # Dry run first — shouldn't modify
        result = renumber.renumber(str(path), dry_run=True)
        assert result is True, "Dry run should succeed"

    def test_renumber_produces_tags(self, temp_dir):
        """After renumber, all $$ blocks have \\\\tag{3-N}."""
        import re
        path = temp_dir["paths"]["ch3"]
        original_content = path.read_text()
        renumber.renumber(str(path))
        result = path.read_text()
        # The file content has \tag{3-1} (single backslash)
        tags = re.findall(r"\\tag\{3-(\d+)\}", result)
        # Should have 2 formulas → 2 tags
        assert len(tags) == 2, f"Expected 2 tags, got {len(tags)}"
        # Verify sequential: extract just the formula numbers
        nums = [int(n) for n in tags]
        assert nums == [1, 2], f"Expected [1,2], got {nums}"
        # Restore for other tests
        path.write_text(original_content)

    def test_renumber_inline_blocks(self, temp_dir):
        """Single-line $$inline$$ formulas get converted to multi-line."""
        import re
        path = temp_dir["paths"]["inline_formulas"]
        renumber.renumber(str(path), chapter="13")
        result = path.read_text()
        # The file content has \tag{13-1} (single backslash)
        tags = re.findall(r"\\tag\{13-\d+\}", result)
        # The inline file has 1 inline formula
        assert len(tags) == 1, f"Expected 1 tag, got {len(tags)}"
        # Verify it's now multi-line (has newlines after $$)
        assert "$$\n" in result

    def test_renumber_empty_file(self, temp_dir):
        """Empty file → no crash."""
        path = temp_dir["paths"]["empty"]
        renumber.renumber(str(path))
        # Should not crash, file stays empty
        assert path.read_text() == ""

    def test_renumber_no_formulas(self, temp_dir):
        """File with no $$ formulas → no tags added."""
        import re
        path = temp_dir["paths"]["plain"]
        renumber.renumber(str(path))
        result = path.read_text()
        tags = re.findall(r"\\\\tag\{\d+-\d+\}", result)
        assert len(tags) == 0

    def test_renumber_orphan_tags(self, temp_dir):
        """Orphan \\\\tag{} outside $$ blocks gets moved inside."""
        import re
        path = temp_dir["paths"]["ch4"]
        renumber.renumber(str(path))
        result = path.read_text()
        # All tags should be inside $$ blocks
        # Split by $$ to check
        segments = result.split("$$")
        for i, seg in enumerate(segments):
            tags = re.findall(r"\\\\tag\{\d+-\d+\}", seg)
            if tags:
                # Odd-indexed segments are outside $$ blocks
                # (0=outside, 1=inside, 2=outside, ...)
                if i % 2 == 0 and seg.strip():
                    # Outside-formula text should have no tags
                    assert not tags, f"Found tag outside $$ block in segment {i}: {tags}"


class TestFixOrphanTags:
    """Test fix_orphan_tags() specifically."""

    def test_orphan_moved_inside(self, temp_dir):
        """A \\\\tag{} line before a $$ block gets moved inside."""
        lines = [
            "some text",
            "\\tag{4-1}",
            "$$",
            "E = mc^2",
            "$$",
        ]
        result = renumber.fix_orphan_tags(lines)
        joined = "\n".join(result)
        # The tag should now be between the $$ delimiters
        assert "$$\n\\tag{4-1}\n$$" in joined, f"Tag not inside $$: {joined}"


class TestConvertInlineBlocks:
    """Test convert_inline_blocks() specifically."""

    def test_inline_conversion(self):
        """Single-line $$...$$ gets expanded to multi-line."""
        text = "inline $$formula$$ here"
        result = renumber.convert_inline_blocks(text)
        assert "$$\n" in result
        assert "\\tag{XX-XX}\n$$" in result

    def test_no_inline(self):
        """Text with no $$...$$ is unchanged."""
        text = "no formulas here"
        result = renumber.convert_inline_blocks(text)
        assert result == text
