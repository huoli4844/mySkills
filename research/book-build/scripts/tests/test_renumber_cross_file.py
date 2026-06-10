"""Smoke tests for renumber_cross_file.py — collect_files() and analyze()."""

import sys
from pathlib import Path

SCRIPTS_DIR = str(Path(__file__).resolve().parent.parent)
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

import renumber_cross_file as rcf


class TestCollectFiles:
    """Test collect_files() — gathers files matching chapter patterns."""

    def test_collects_main_chapter(self, temp_dir):
        """Finds 第8章-*.md files for chapter 8."""
        root = str(temp_dir["root"])
        files = rcf.collect_files(root, 8)
        # Should find at least 第8章-正文.md
        names = [Path(f).name for f in files]
        assert "第8章-正文.md" in names, f"Expected 第8章-正文.md in {names}"

    def test_collects_case_files(self, temp_dir):
        """Finds 案例8-*.md files for chapter 8."""
        root = str(temp_dir["root"])
        files = rcf.collect_files(root, 8)
        names = [Path(f).name for f in files]
        assert "案例8-案例1.md" in names, f"Expected 案例8-案例1.md in {names}"

    def test_collects_lab_files(self, temp_dir):
        """Finds 实验8_*.md files for chapter 8."""
        root = str(temp_dir["root"])
        files = rcf.collect_files(root, 8)
        names = [Path(f).name for f in files]
        assert "实验8_实验1.md" in names, f"Expected 实验8_实验1.md in {names}"

    def test_no_files_for_unmatched_chapter(self, temp_dir):
        """Returns empty list for chapter with no files."""
        root = str(temp_dir["root"])
        files = rcf.collect_files(root, 99)
        assert len(files) == 0, f"Expected empty list, got {files}"

    def test_files_sorted_and_unique(self, temp_dir):
        """Returns sorted, deduplicated list."""
        root = str(temp_dir["root"])
        files = rcf.collect_files(root, 8)
        assert len(files) == len(set(files)), "Results should be unique"
        names = [Path(f).name for f in files]
        assert names == sorted(names), f"Results should be sorted: {names}"


class TestAnalyze:
    """Test analyze() — counts formulas, figures, examples, tables."""

    def test_analyze_counts_formulas(self, temp_dir):
        """analyze() counts all formula tags across files."""
        root = temp_dir["root"]
        files = sorted([
            str(root / "第8章-正文.md"),
            str(root / "案例8-案例1.md"),
            str(root / "实验8_实验1.md"),
        ])
        result = rcf.analyze(files, 8)
        assert len(result["formula"]) == 3, f"Expected 3 formulas (one per file), got {len(result['formula'])}"

    def test_analyze_counts_figures(self, temp_dir):
        """analyze() counts *图N-X captions across files."""
        root = temp_dir["root"]
        files = sorted([
            str(root / "第8章-正文.md"),
            str(root / "案例8-案例1.md"),
        ])
        result = rcf.analyze(files, 8)
        assert len(result["fig"]) == 2, f"Expected 2 figures, got {len(result['fig'])}"

    def test_analyze_counts_examples(self, temp_dir):
        """analyze() counts **例N-X across files."""
        root = temp_dir["root"]
        files = sorted([
            str(root / "第8章-正文.md"),
            str(root / "实验8_实验1.md"),
        ])
        result = rcf.analyze(files, 8)
        assert len(result["example"]) == 2, f"Expected 2 examples, got {len(result['example'])}"

    def test_analyze_counts_tables(self, temp_dir):
        """analyze() counts **表N-X across files."""
        root = temp_dir["root"]
        files = [str(root / "第8章-正文.md")]
        result = rcf.analyze(files, 8)
        assert len(result["table"]) == 1, f"Expected 1 table, got {len(result['table'])}"

    def test_analyze_no_duplicates(self, temp_dir):
        """analyze() reports no duplicates when all numbers are unique."""
        root = temp_dir["root"]
        files = sorted([
            str(root / "第8章-正文.md"),
            str(root / "案例8-案例1.md"),
            str(root / "实验8_实验1.md"),
        ])
        result = rcf.analyze(files, 8)
        assert len(result["dup_formula"]) == 0, f"Should detect no dupes: {result['dup_formula']}"

    def test_analyze_empty_file_list(self, temp_dir):
        """Empty file list → empty counts."""
        result = rcf.analyze([], 8)
        assert len(result["formula"]) == 0
        assert len(result["fig"]) == 0
        assert len(result["example"]) == 0
        assert len(result["table"]) == 0
        assert len(result["files"]) == 0
