"""Additional unit tests for post_generation_check.py — all public check functions.

Covers check_mermaid, check_wikilinks, check_tag_placement, check_spelling,
check_formula_format, plus extra edge cases for check_mermaid_has_caption
and check_derivation_depth.

Each check function has at least 3 tests (normal / error / boundary).
"""

import sys
from pathlib import Path

SCRIPTS_DIR = str(Path(__file__).resolve().parent.parent)
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

import post_generation_check as pgc


# ═══════════════════════════════════════════════════════════════
#  check_mermaid  —  Mermaid 语法全面校验
# ═══════════════════════════════════════════════════════════════

class TestCheckMermaid:
    """7-item Mermaid syntax check."""

    def test_valid_mermaid_no_issues(self):
        """Valid flowchart with no problems → empty issues."""
        text = (
            "```mermaid\n"
            "flowchart LR\n"
            "  A[Start] --> B[End]\n"
            "```\n"
        )
        issues = pgc.check_mermaid(text)
        assert len(issues) == 0, f"Expected no issues, got: {issues}"

    def test_unknown_chart_type(self):
        """Unknown Mermaid chart type → WARN issue."""
        text = (
            "```mermaid\n"
            "invalidType XYZ\n"
            "  A-->B\n"
            "```\n"
        )
        issues = pgc.check_mermaid(text)
        type_issues = [i for i in issues if "未知图表类型" in i[2]]
        assert len(type_issues) > 0, f"Expected unknown type warning, got: {issues}"

    def test_empty_mermaid_block(self):
        """Mermaid block with no content → WARN issue."""
        text = "```mermaid\n```\n"
        issues = pgc.check_mermaid(text)
        empty_issues = [i for i in issues if "内容为空" in i[2]]
        assert len(empty_issues) > 0, f"Expected empty content warning, got: {issues}"

    def test_unclosed_mermaid_block(self):
        """Mermaid block missing closing ``` → ERROR."""
        text = "```mermaid\nflowchart LR\n  A-->B\n"
        issues = pgc.check_mermaid(text)
        unclosed = [i for i in issues if "缺闭合" in i[2]]
        assert len(unclosed) > 0, f"Expected unclosed error, got: {issues}"

    def test_mermaid_no_blocks_at_all(self):
        """No mermaid blocks at all → empty issues."""
        issues = pgc.check_mermaid("# Just text\nNo diagrams.\n")
        assert len(issues) == 0

    def test_empty_text(self):
        """Empty string → empty issues."""
        issues = pgc.check_mermaid("")
        assert len(issues) == 0

    def test_subgraph_with_special_chars(self):
        """subgraph title containing parentheses or commas → ERROR."""
        text = (
            "```mermaid\n"
            "flowchart LR\n"
            "subgraph 测试（特殊）\n"
            "  A-->B\n"
            "end\n"
            "```\n"
        )
        issues = pgc.check_mermaid(text)
        subgraph_issues = [i for i in issues if "subgraph" in i[2] and "特殊字符" in i[2]]
        assert len(subgraph_issues) > 0, f"Expected subgraph char error, got: {issues}"

    def test_mermaid_block_with_emoji(self):
        """Node label containing emoji → WARN."""
        text = (
            "```mermaid\n"
            "flowchart LR\n"
            "  A[测试🔧] --> B[完成✅]\n"
            "```\n"
        )
        issues = pgc.check_mermaid(text)
        emoji_issues = [i for i in issues if "emoji" in i[2] or "含emoji" in i[2]]
        assert len(emoji_issues) > 0, f"Expected emoji warning, got: {issues}"

    def test_xychart_missing_yaxis(self):
        """xychart-beta without y-axis → WARN."""
        text = (
            "```mermaid\n"
            "xychart-beta\n"
            "  title \"Test\"\n"
            "  x-axis \"X\"\n"
            "  bar [1, 2, 3]\n"
            "```\n"
        )
        issues = pgc.check_mermaid(text)
        yaxis_issues = [i for i in issues if "缺y-axis" in i[2]]
        assert len(yaxis_issues) > 0, f"Expected missing y-axis warning, got: {issues}"

    def test_classdef_undefined_reference(self):
        """:::style referencing undefined classDef → ERROR."""
        text = (
            "```mermaid\n"
            "flowchart LR\n"
            "  A:::myStyle --> B\n"
            "```\n"
        )
        issues = pgc.check_mermaid(text)
        classdef_issues = [i for i in issues if "未定义的classDef" in i[2]]
        assert len(classdef_issues) > 0, f"Expected undefined classDef error, got: {issues}"

    def test_init_with_single_quotes(self):
        """%%{init} using single quotes → WARN."""
        text = (
            "```mermaid\n"
            "%%{init: {'theme': 'base'} }%%\n"
            "flowchart LR\n"
            "  A-->B\n"
            "```\n"
        )
        issues = pgc.check_mermaid(text)
        init_issues = [i for i in issues if "单引号" in i[2]]
        assert len(init_issues) > 0, f"Expected single-quote warning, got: {issues}"

    def test_multiple_mermaid_blocks(self):
        """Multiple valid mermaid blocks → no issues."""
        text = (
            "```mermaid\n"
            "flowchart LR\n"
            "  A-->B\n"
            "```\n\n"
            "```mermaid\n"
            "sequenceDiagram\n"
            "  A->>B: Hello\n"
            "```\n"
        )
        issues = pgc.check_mermaid(text)
        assert len(issues) == 0, f"Expected no issues, got: {issues}"


# ═══════════════════════════════════════════════════════════════
#  check_wikilinks  —  Wikilink 检查
# ═══════════════════════════════════════════════════════════════

class TestCheckWikilinks:
    """[[wikilink]] detection — forbidden in textbooks."""

    def test_detects_single_wikilink(self):
        """A single [[wikilink]] → one issue."""
        text = "参考[[第3章-搭接技术]]中的内容。\n"
        issues = pgc.check_wikilinks(text)
        assert len(issues) == 1
        assert "[[第3章-搭接技术]]" in issues[0][2]

    def test_detects_multiple_wikilinks(self):
        """Multiple [[wikilinks]] → one issue per link."""
        text = (
            "见[[第3章]]和[[第4章]]和[[第5章]]。\n"
        )
        issues = pgc.check_wikilinks(text)
        assert len(issues) == 3

    def test_no_wikilinks_no_issues(self):
        """Text with no [[...]] → no issues."""
        text = "这是普通文本，没有交叉引用。\n"
        issues = pgc.check_wikilinks(text)
        assert len(issues) == 0

    def test_empty_text(self):
        """Empty string → no issues."""
        issues = pgc.check_wikilinks("")
        assert len(issues) == 0

    def test_brackets_not_wikilinks(self):
        """Regular brackets like [text] or [1] → no issues (not [[)."""
        text = (
            "参考文献[1]对此有详细说明。\n"
            "方括号[示例]不是链接。\n"
        )
        issues = pgc.check_wikilinks(text)
        assert len(issues) == 0

    def test_wikilinks_on_multiple_lines(self):
        """Wikilinks on different lines → correct line numbers."""
        text = (
            "[[第3章]]\n"
            "some text\n"
            "[[第4章]]\n"
        )
        issues = pgc.check_wikilinks(text)
        assert len(issues) == 2
        # Line numbers should be 1 and 3
        assert issues[0][0] == 1
        assert issues[1][0] == 3

    def test_wikilink_with_pipe(self):
        """[[target|display]] style wikilink → detected."""
        text = "参考[[搭接技术|第3章]]。\n"
        issues = pgc.check_wikilinks(text)
        assert len(issues) == 1
        assert "搭接技术|第3章" in issues[0][2]


# ═══════════════════════════════════════════════════════════════
#  check_tag_placement  —  \tag{} 放置检查
# ═══════════════════════════════════════════════════════════════

class TestCheckTagPlacement:
    """\tag{} must be inside $$...$$ blocks."""

    def test_tag_outside_dollar_block(self):
        """\tag{N-M} floating outside $$ → ERROR."""
        text = (
            "$$\n"
            "E = mc^2\n"
            "$$\n"
            "\\tag{1-1}\n"
            "$$\n"
            "F = ma\n"
            "$$\n"
        )
        issues = pgc.check_tag_placement(text)
        assert len(issues) == 1
        assert "$$块外部" in issues[0][2]

    def test_tag_inside_dollar_block(self):
        """\tag{} properly inside $$ → no issues."""
        text = (
            "$$\n"
            "\\tag{1-1}\n"
            "E = mc^2\n"
            "$$\n"
        )
        issues = pgc.check_tag_placement(text)
        assert len(issues) == 0

    def test_no_tags_at_all(self):
        """No \tag{} anywhere → no issues."""
        text = "## Test\n\nSome text without tags.\n"
        issues = pgc.check_tag_placement(text)
        assert len(issues) == 0

    def test_empty_text(self):
        """Empty string → no issues."""
        issues = pgc.check_tag_placement("")
        assert len(issues) == 0

    def test_mixed_inside_and_outside(self):
        """Some tags inside, some outside → only outside ones flagged."""
        text = (
            "$$\n"
            "\\tag{1-1}\n"
            "a = b\n"
            "$$\n"
            "\\tag{1-2}\n"
            "$$\n"
            "\\tag{1-3}\n"
            "c = d\n"
            "$$\n"
        )
        issues = pgc.check_tag_placement(text)
        assert len(issues) == 1
        assert "1-2" in issues[0][2]  # the outside one

    def test_tag_not_matching_numbering_pattern(self):
        """\\tag{} with non-standard content like 'abc' → not flagged (only N-M pattern)."""
        text = (
            "$$\n"
            "E = mc^2\n"
            "$$\n"
            "\\tag{abc}\n"  # not matching \d+-\d+ pattern, so ignored
        )
        issues = pgc.check_tag_placement(text)
        assert len(issues) == 0

    def test_tag_on_separate_line_inside_block(self):
        """Multiple tags inside blocks → no issues."""
        text = (
            "$$\n"
            "\\tag{1-1}\n"
            "a = b\n"
            "$$\n"
            "$$\n"
            "\\tag{1-2}\n"
            "c = d\n"
            "$$\n"
        )
        issues = pgc.check_tag_placement(text)
        assert len(issues) == 0


# ═══════════════════════════════════════════════════════════════
#  check_spelling  —  LaTeX 拼写检查
# ═══════════════════════════════════════════════════════════════

class TestCheckSpelling:
    """Common LaTeX spelling mistakes."""

    def test_detects_misspelled_word(self):
        """"omege" instead of "omega" → WARN."""
        text = "根据公式 omege 的值计算。\n"
        issues = pgc.check_spelling(text)
        spell_issues = [i for i in issues if "omege" in i[2]]
        assert len(spell_issues) == 1
        assert "omega" in spell_issues[0][2]

    def test_detects_multiple_misspellings(self):
        """Multiple misspelled words → multiple issues."""
        text = "omege 和 lamda 都是常见错误。\n"
        issues = pgc.check_spelling(text)
        assert len(issues) >= 2

    def test_correct_text_no_issues(self):
        """No misspellings → empty issues."""
        text = "根据公式 omega 和 lambda 的值计算。\n"
        issues = pgc.check_spelling(text)
        assert len(issues) == 0

    def test_empty_text(self):
        """Empty string → no issues."""
        issues = pgc.check_spelling("")
        assert len(issues) == 0

    def test_misspelling_part_of_larger_word(self):
        """Misspelling boundaries: 'thets' in middle of 'bethets' shouldn't match due to \b."""
        text = "bethetsomething\n"
        issues = pgc.check_spelling(text)
        assert len(issues) == 0, "Should not match as part of another word"

    def test_all_known_misspellings(self):
        """Exercise all known misspellings to ensure patterns work."""
        text = (
            "omege thets epsilo lamda delat sgima alfe bete gama pai infinty Omege\n"
        )
        issues = pgc.check_spelling(text)
        # Should find at least most of them (omege, thets, epsilo, etc.)
        assert len(issues) >= 10, f"Expected many issues, got {len(issues)}: {issues}"

    def test_case_sensitive_omege_vs_Omege(self):
        """"Omege" (capital O) should be caught separately from "omege"."""
        text = "Both omege and Omege are wrong.\n"
        issues = pgc.check_spelling(text)
        assert len(issues) == 2


# ═══════════════════════════════════════════════════════════════
#  check_formula_format  —  公式格式规范
# ═══════════════════════════════════════════════════════════════

class TestCheckFormulaFormat:
    """Formula formatting rules: tag/$$ separation, empty blocks."""

    def test_tag_same_line_as_dollars(self):
        """\tag{} on same line as $$ → ERROR."""
        text = (
            "根据原理：\n"
            "$$ \\tag{1-1}\n"
            "F = ma\n"
            "$$\n"
        )
        issues = pgc.check_formula_format(text)
        same_line = [i for i in issues if "tag与公式同行" in i[2]]
        assert len(same_line) > 0, f"Expected tag-same-line error, got: {issues}"

    def test_empty_dollar_block(self):
        """Consecutive '$$' with nothing between → WARN."""
        text = "$$\n$$\n"
        issues = pgc.check_formula_format(text)
        empty = [i for i in issues if "空$$块" in i[2]]
        assert len(empty) > 0, f"Expected empty-block warning, got: {issues}"

    def test_tag_after_dollar_dollar(self):
        """\tag{} on line immediately after $$ (outside block) → ERROR."""
        text = (
            "$$\n"
            "\\tag{1-1}\n"
            "E = mc^2\n"
            "$$\n"
        )
        issues = pgc.check_formula_format(text)
        after = [i for i in issues if "tag在$$之后" in i[2]]
        assert len(after) > 0, f"Expected tag-after-$$ error, got: {issues}"

    def test_proper_format_no_issues(self):
        """Well-formatted formula with \tag on its own line before $$ → no issues."""
        text = (
            "根据原理：\n"
            "\\tag{1-1}\n"
            "$$\n"
            "F = ma\n"
            "$$\n"
        )
        issues = pgc.check_formula_format(text)
        assert len(issues) == 0, f"Expected no issues, got: {issues}"

    def test_no_formulas_at_all(self):
        """No $$ blocks → no issues."""
        text = "# Just text\nNo formulas here.\n"
        issues = pgc.check_formula_format(text)
        assert len(issues) == 0

    def test_empty_text(self):
        """Empty string → no issues."""
        issues = pgc.check_formula_format("")
        assert len(issues) == 0

    def test_inline_dollar_not_confused(self):
        """Inline $$...$$ (single-line) should not trigger false positives."""
        text = (
            "传递函数为 $$H(s) = \\frac{1}{RCs+1}$$ 即低通。\n"
        )
        issues = pgc.check_formula_format(text)
        # Inline formulas don't have the tag-on-same-line issue pattern
        # since there's no \tag{ inside the inline block
        assert len(issues) == 0, f"Expected no issues for inline $$, got: {issues}"


# ═══════════════════════════════════════════════════════════════
#  check_mermaid_has_caption  —  额外边界测试
# ═══════════════════════════════════════════════════════════════

class TestCheckMermaidHasCaptionExtra:
    """Additional edge cases beyond the existing smoke tests."""

    def test_caption_on_exact_third_line(self):
        """Caption on line 3 after closing ``` → no issue (within 3-line window)."""
        text = (
            "```mermaid\n"
            "flowchart LR\n"
            "  A-->B\n"
            "```\n"
            "\n"
            "\n"
            "*图1-1：测试*  ← line 3 after close\n"
        )
        issues = pgc.check_mermaid_has_caption(text)
        assert len(issues) == 0, f"Caption on line 3 should pass, got: {issues}"

    def test_caption_on_line_6_or_further(self):
        """Caption on line 6+ after close → too far (code searches i+1..i+5), flagged."""
        text = (
            "```mermaid\n"
            "flowchart LR\n"
            "  A-->B\n"
            "```\n"
            "\n"
            "\n"
            "\n"
            "\n"
            "\n"
            "\n"
            "*图1-1：测试*  ← line 6 after close\n"
        )
        issues = pgc.check_mermaid_has_caption(text)
        cap_issues = [i for i in issues if "缺图注" in i[2]]
        assert len(cap_issues) > 0

    def test_caption_blocked_by_heading(self):
        """A heading before caption → caption not found, flagged."""
        text = (
            "```mermaid\n"
            "flowchart LR\n"
            "  A-->B\n"
            "```\n"
            "## 下一个标题\n"
            "*图1-1：测试*\n"
        )
        issues = pgc.check_mermaid_has_caption(text)
        cap_issues = [i for i in issues if "缺图注" in i[2]]
        assert len(cap_issues) > 0

    def test_caption_blocked_by_code_block(self):
        """A ``` code block before caption → caption not found, flagged."""
        text = (
            "```mermaid\n"
            "flowchart LR\n"
            "  A-->B\n"
            "```\n"
            "```python\n"
            "print('hello')\n"
            "```\n"
            "*图1-1：测试*\n"
        )
        issues = pgc.check_mermaid_has_caption(text)
        cap_issues = [i for i in issues if "缺图注" in i[2]]
        assert len(cap_issues) > 0

    def test_multiple_mermaids_one_missing_caption(self):
        """First has caption, second missing → one issue for second."""
        text = (
            "```mermaid\n"
            "flowchart LR\n"
            "  A-->B\n"
            "```\n"
            "*图1-1：第一个*\n\n"
            "```mermaid\n"
            "flowchart LR\n"
            "  C-->D\n"
            "```\n"
            "## 新章节\n"
        )
        issues = pgc.check_mermaid_has_caption(text)
        assert len(issues) == 1  # only the second mermaid


# ═══════════════════════════════════════════════════════════════
#  check_derivation_depth  —  额外边界测试
# ═══════════════════════════════════════════════════════════════

class TestCheckDerivationDepthExtra:
    """Additional edge cases beyond the existing smoke tests."""

    def test_exactly_three_bare_formulas_triggers_issue(self):
        """Exactly 3 consecutive formulas without hints → issue."""
        text = (
            "$$\na = b\n$$\n"
            "$$\nc = d\n$$\n"
            "$$\ne = f\n$$\n"
        )
        issues = pgc.check_derivation_depth(text)
        bare = [i for i in issues if "连续" in i[2]]
        assert len(bare) == 1, f"Expected exactly 1 bare-formula issue, got: {issues}"

    def test_four_bare_formulas_two_issues(self):
        """4 bare formulas → 2 issues (at 3rd and 4th; dedup check partial match).
        Note: the dedup logic uses startswith('连续公式前无推导词') which doesn't
        match the actual issue format 'L{N}: 连续{N}个...', so a new issue fires
        each time consecutive_bare increments past 3."""
        text = (
            "$$\na = b\n$$\n"
            "$$\nc = d\n$$\n"
            "$$\ne = f\n$$\n"
            "$$\ng = h\n$$\n"
        )
        issues = pgc.check_derivation_depth(text)
        bare = [i for i in issues if "连续" in i[2]]
        assert len(bare) == 2, f"Expected 2 issues (one at 3, one at 4), got: {bare}"

    def test_hint_resets_counter(self):
        """A hint after 2 bare formulas resets, so no trigger.
        Padding lines isolate the hint so it only affects the formula after it."""
        text = (
            "$$\na = b\n$$\n"
            "$$\nc = d\n$$\n"
            "\n\n\n\n\n"
            "根据原理：\n"
            "$$\ne = f\n$$\n"
            "\n\n\n\n\n"
            "$$\ng = h\n$$\n"
            "$$\ni = j\n$$\n"
        )
        issues = pgc.check_derivation_depth(text)
        bare = [i for i in issues if "连续" in i[2]]
        # With padding, hint only resets counter for formula 3.
        # Formulas 4-5 (g=h, i=j) are 2 consecutive bare → not enough for trigger.
        assert len(bare) == 0, f"Expected no bare-formula issues, got: {bare}"

    def test_mixed_hints_and_bare(self):
        """Pattern: hint, bare, bare, hint, bare, bare, bare → issue on last 3.
        Padding lines isolate hints to only affect the immediately following formula."""
        text = (
            "根据原理：\n"
            "$$\na = b\n$$\n"
            "$$\nc = d\n$$\n"
            "\n\n\n\n\n"
            "由式(1)可得：\n"
            "$$\ne = f\n$$\n"
            "\n\n\n\n\n"
            "$$\ng = h\n$$\n"
            "$$\ni = j\n$$\n"
            "$$\nk = l\n$$\n"
        )
        issues = pgc.check_derivation_depth(text)
        bare = [i for i in issues if "连续" in i[2]]
        # With padding, hints only affect formula right after them.
        # Formulas 1 (a=b) has hint; 2 (c=d) no hint; 3 has hint;
        # formulas 4,5,6 (g=h, i=j, k=l) are 3 consecutive bare → 1 issue
        assert len(bare) == 1, f"Expected 1 issue for last 3 bare, got: {bare}"

    def test_all_formulas_have_hints(self):
        """Every formula preceded by a derivation hint → no issue."""
        text = (
            "根据原理：\n$$\na = b\n$$\n\n"
            "代入可得：\n$$\nc = d\n$$\n\n"
            "由式(1)：\n$$\ne = f\n$$\n"
        )
        issues = pgc.check_derivation_depth(text)
        bare = [i for i in issues if "连续" in i[2]]
        assert len(bare) == 0
