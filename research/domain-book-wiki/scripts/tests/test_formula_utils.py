"""test_formula_utils.py — formula_utils 状态机测试

测试 find_formula_blocks 和 has_citation_after 的各种场景，
包括代码块内的 $$ 跳过、多个公式块、边界条件。
"""



import pytest
from formula_utils import FormulaBlock, find_formula_blocks, has_citation_after

pytestmark = pytest.mark.unit

# ── find_formula_blocks ───────────────────────────────────


class TestFindFormulaBlocks:
    def test_no_formulas(self):
        """无公式文本应返回空列表"""
        lines = ["普通文本", "没有公式", "只有文字"]
        assert find_formula_blocks(lines) == []

    def test_single_block(self):
        """单个 $$ 公式块"""
        lines = ["文本", "$$", "E = mc^2", "$$", "后续"]
        blocks = find_formula_blocks(lines)
        assert len(blocks) == 1
        assert blocks[0] == FormulaBlock(start_line=1, end_line=3)

    def test_multiple_blocks(self):
        """多个 $$ 公式块"""
        lines = ["$$", "A", "$$", "", "$$", "B", "$$"]
        blocks = find_formula_blocks(lines)
        assert len(blocks) == 2
        assert blocks[0] == FormulaBlock(start_line=0, end_line=2)
        assert blocks[1] == FormulaBlock(start_line=4, end_line=6)

    def test_skip_mermaid_code_block(self):
        """Mermaid 代码块内的 $$ 应被跳过"""
        lines = [
            "```mermaid",
            "flowchart TD",
            '    A --> B["V=(U+S)(U-S)^{-1}"]',
            "```",
            "",
            "$$",
            "P = I \\cdot R",
            "$$",
        ]
        blocks = find_formula_blocks(lines)
        assert len(blocks) == 1
        assert blocks[0] == FormulaBlock(start_line=5, end_line=7)

    def test_skip_generic_code_block(self):
        """通用代码块内的 $$ 应被跳过"""
        lines = [
            "```python",
            'x = "$$"',
            "```",
            "$$",
            "real formula",
            "$$",
        ]
        blocks = find_formula_blocks(lines)
        assert len(blocks) == 1
        assert blocks[0] == FormulaBlock(start_line=3, end_line=5)

    def test_code_block_then_formula_then_code_block(self):
        """交替出现的代码块和公式"""
        lines = [
            "```",
            "$$",  # 代码块内，跳过
            "```",
            "$$",  # 真实公式 opening
            "F=ma",
            "$$",  # 真实公式 closing
            "```mermaid",
            "$$",  # 代码块内，跳过
            "```",
        ]
        blocks = find_formula_blocks(lines)
        assert len(blocks) == 1
        assert blocks[0] == FormulaBlock(start_line=3, end_line=5)

    def test_empty_lines(self):
        """空行列表应返回空列表"""
        assert find_formula_blocks([]) == []

    def test_unclosed_formula(self):
        """未关闭的 $$ 不应产生块"""
        lines = ["$$", "E = mc^2", "没有 closing"]
        assert find_formula_blocks(lines) == []

    def test_inline_text_around_delimiters(self):
        """$$ 行有其他文字时不算（stripped != '$$'）"""
        lines = ["文本 $$ E=mc^2 $$", "正常文字"]
        assert find_formula_blocks(lines) == []


# ── has_citation_after ────────────────────────────────────


class TestHasCitationAfter:
    def test_citation_immediately_after(self):
        """closing $$ 后紧跟来源标注"""
        lines = ["$$", "E=mc^2", "$$", "> 来源：教材", "后续"]
        assert has_citation_after(lines, 2) is True

    def test_citation_with_blank_line(self):
        """closing $$ 后空一行再有来源标注"""
        lines = ["$$", "E=mc^2", "$$", "", "> 来源：教材"]
        assert has_citation_after(lines, 2) is True

    def test_no_citation(self):
        """无来源标注应返回 False"""
        lines = ["$$", "E=mc^2", "$$", "", "普通段落"]
        assert has_citation_after(lines, 2) is False

    def test_citation_half_width_colon(self):
        """半角冒号的来源标注也应被识别"""
        lines = ["$$", "E=mc^2", "$$", "> 来源: 教材"]
        assert has_citation_after(lines, 2) is True

    def test_stops_at_next_formula(self):
        """遇到下一个 $$ 应停止搜索"""
        lines = ["$$", "A", "$$", "$$", "B", "$$", "> 来源：远处"]
        # end_line=2, 下一个 $$ 在 line 3，应停止
        assert has_citation_after(lines, 2) is False

    def test_stops_at_non_quote_content(self):
        """遇到非引用、非空行应停止"""
        lines = ["$$", "A", "$$", "新段落内容", "> 来源：太远"]
        # end_line=2, line 3 是非空非 > 行，停止
        assert has_citation_after(lines, 2) is False

    def test_end_of_file(self):
        """closing $$ 在文件末尾应返回 False"""
        lines = ["$$", "A", "$$"]
        assert has_citation_after(lines, 2) is False

    def test_custom_window(self):
        """自定义窗口大小"""
        lines = ["$$", "A", "$$", "", "", "", "", "> 来源：远处"]
        # 默认 window=20 应能找到
        assert has_citation_after(lines, 2, window=20) is True
        # window=2 不够远，line 3 是空行（通过），line 4 也是空行（通过）
        # 但空行以 '' strip 后是 ''，不触发 break
        # 空行不匹配 break 条件，继续搜索
        # 实际上空行不会 break，所以只要 window 能到 line 7 就能找到
        assert has_citation_after(lines, 2, window=3) is False


# ── 集成场景 ───────────────────────────────────────────────


class TestIntegrationScenarios:
    def test_mermaid_then_formula_with_citation(self):
        """Mermaid 块后的真实公式有来源 → 全部 cited"""
        lines = [
            "```mermaid",
            "flowchart TD",
            '    A["$$"]',
            "```",
            "",
            "$$",
            "P = I \\cdot R",
            "$$",
            "> 来源：正文",
        ]
        blocks = find_formula_blocks(lines)
        assert len(blocks) == 1
        assert has_citation_after(lines, blocks[0].end_line) is True

    def test_multiple_formulas_mixed_citations(self):
        """多个公式块，部分有来源部分无"""
        lines = [
            "$$",
            "A",
            "$$",
            "> 来源：教材",
            "",
            "$$",
            "B",
            "$$",
            "没有来源",
        ]
        blocks = find_formula_blocks(lines)
        assert len(blocks) == 2
        assert has_citation_after(lines, blocks[0].end_line) is True
        assert has_citation_after(lines, blocks[1].end_line) is False
