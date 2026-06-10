"""Smoke tests for post_generation_check.py — check_mermaid_has_caption,
check_derivation_depth, and check_formulas."""

import sys
from pathlib import Path

SCRIPTS_DIR = str(Path(__file__).resolve().parent.parent)
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

import post_generation_check as pgc


class TestCheckMermaidHasCaption:
    """Test check_mermaid_has_caption() — '有图必有说明'."""

    def test_detects_missing_caption(self, temp_dir):
        """Mermaid block without *图N-X caption within 3 lines → issue."""
        text = temp_dir["file_contents"]["mermaid_no_cap"]
        issues = pgc.check_mermaid_has_caption(text)
        assert len(issues) > 0, "Should detect missing caption"
        assert "缺图注" in issues[0][2], f"Unexpected issue: {issues[0]}"

    def test_no_issue_with_caption(self, temp_dir):
        """Mermaid block followed by *图N-X caption → no issue."""
        text = temp_dir["file_contents"]["mermaid_with_cap"]
        issues = pgc.check_mermaid_has_caption(text)
        assert len(issues) == 0, f"Should have no issues, got: {issues}"

    def test_no_mermaid_no_issue(self):
        """No mermaid blocks at all → no issues."""
        text = "# Just text\n\nNo diagrams here.\n"
        issues = pgc.check_mermaid_has_caption(text)
        assert len(issues) == 0

    def test_empty_text(self):
        """Empty text → no issues."""
        issues = pgc.check_mermaid_has_caption("")
        assert len(issues) == 0


class TestCheckDerivationDepth:
    """Test check_derivation_depth() — heuristic for derivation hints."""

    def test_detects_bare_formulas(self, temp_dir):
        """3 consecutive formulas without derivation hints → issue."""
        text = temp_dir["file_contents"]["bare_formulas"]
        issues = pgc.check_derivation_depth(text)
        assert len(issues) > 0, "Should detect bare formulas"
        assert "推导词" in issues[0][2], f"Unexpected issue: {issues[0]}"

    def test_no_issue_with_hints(self, temp_dir):
        """Formulas preceded by derivation hints → no issue."""
        text = temp_dir["file_contents"]["derived_formulas"]
        issues = pgc.check_derivation_depth(text)
        # May or may not have issues depending on exact hint count
        # At minimum shouldn't have the '3 bare formulas' issue
        bare_issues = [i for i in issues if "连续" in i[2]]
        assert len(bare_issues) == 0, f"Should have no bare formula issues: {issues}"

    def test_no_formulas_no_issue(self):
        """No formulas at all → no issues."""
        issues = pgc.check_derivation_depth("# No formulas")
        assert len(issues) == 0

    def test_empty_text(self):
        """Empty text → no issues."""
        issues = pgc.check_derivation_depth("")
        assert len(issues) == 0

    def test_less_than_three_formulas(self):
        """1-2 formulas without hints → no '3 consecutive' issue."""
        text = "$$\na = b\n$$\n\n$$\nc = d\n$$\n"
        issues = pgc.check_derivation_depth(text)
        bare = [i for i in issues if "连续" in i[2]]
        assert len(bare) == 0, "Should not flag <3 consecutive formulas"


class TestCheckFormulas:
    """Test check_formulas() — syntax and tag completeness."""

    def test_detects_missing_tags(self, temp_dir):
        """Formula block without \\\\tag{} → issue."""
        text = temp_dir["file_contents"]["missing_tags"]
        # Chapter 12
        issues = pgc.check_formulas(text, 12)
        missing = [i for i in issues if "缺" in i[2] and "tag" in i[2]]
        assert len(missing) > 0, f"Should detect missing tags, got: {issues}"

    def test_balanced_formulas_no_error(self):
        """Properly formatted formulas with tags → no issues."""
        text = "## Test\n\n根据原理：\n$$\n\\tag{1-1}\nF = ma\n$$\n"
        issues = pgc.check_formulas(text, 1)
        errors = [i for i in issues if i[1] == "ERROR"]
        assert len(errors) == 0, f"Should have no errors: {issues}"

    def test_empty_text(self):
        """Empty text → no issues."""
        issues = pgc.check_formulas("", 1)
        assert len(issues) == 0

    def test_no_formulas(self):
        """Text with no $$ blocks → no issues."""
        issues = pgc.check_formulas("# Just text", 1)
        assert len(issues) == 0
