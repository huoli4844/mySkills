"""Tests for generate_outlines.py — CHAPTER_TEMPLATE, _chinese_to_arabic,
outline_exists, generate_chapter_outline, and parse_outline_structure."""

import sys
import os
from pathlib import Path

SCRIPTS_DIR = str(Path(__file__).resolve().parent.parent)
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from generate_outlines import (
    CHAPTER_TEMPLATE,
    CHAPTER_NUM_MAP,
    _chinese_to_arabic,
    parse_outline_structure,
    outline_exists,
    generate_chapter_outline,
)


# =============================================================
# CHAPTER_TEMPLATE
# =============================================================
class TestChapterTemplate:
    """Verify CHAPTER_TEMPLATE formatting."""

    def test_format_contains_chapter_number(self):
        """格式化后的模板应包含章号。"""
        result = CHAPTER_TEMPLATE.format(ch=3, title="搭接技术")
        assert "# 第3章 搭接技术 写作指南" in result

    def test_format_contains_title(self):
        """格式化后的模板应包含章节标题（含中文）。"""
        result = CHAPTER_TEMPLATE.format(ch=7, title="电磁屏蔽")
        assert "# 第7章 电磁屏蔽 写作指南" in result

    def test_format_contains_structure_table(self):
        """格式化后的模板应包含结构建议表格的节号占位符。"""
        result = CHAPTER_TEMPLATE.format(ch=3, title="测试")
        # 格式化的模板中 {ch} 应已被替换
        assert "3.1" in result or "3." in result
        assert "{ch}" not in result

    def test_format_contains_mermaid_section(self):
        """格式化后的模板应包含写作手法对比表、Mermaid 规范等核心板块。"""
        result = CHAPTER_TEMPLATE.format(ch=1, title="绪论")
        # 核心板块
        assert "## 各教材章节对应关系" in result
        assert "## 各教材写作手法对比表" in result
        assert "### 公式写法" in result
        assert "### Mermaid 图写法" in result
        assert "## 图表清单" in result
        assert "## 每节写作指南（创作时逐节填写）" in result

    def test_format_chapter_9(self):
        """格式化第9章也应正确。"""
        result = CHAPTER_TEMPLATE.format(ch=9, title="滤波技术")
        assert "# 第9章 滤波技术 写作指南" in result
        assert "9." in result


# =============================================================
# CHAPTER_NUM_MAP
# =============================================================
class TestChapterNumMap:
    """Verify chapter numeral map completeness."""

    def test_has_one_to_fifteen(self):
        """映射表应包含一~十五。"""
        assert len(CHAPTER_NUM_MAP) == 15
        assert CHAPTER_NUM_MAP['一'] == 1
        assert CHAPTER_NUM_MAP['五'] == 5
        assert CHAPTER_NUM_MAP['十'] == 10
        assert CHAPTER_NUM_MAP['十一'] == 11
        assert CHAPTER_NUM_MAP['十五'] == 15


# =============================================================
# _chinese_to_arabic
# =============================================================
class TestChineseToArabic:
    """Test Chinese numeral → Arabic number conversion."""

    def test_single_digit(self):
        assert _chinese_to_arabic("一") == 1
        assert _chinese_to_arabic("三") == 3
        assert _chinese_to_arabic("五") == 5
        assert _chinese_to_arabic("九") == 9
        assert _chinese_to_arabic("十") == 10

    def test_compound(self):
        assert _chinese_to_arabic("十一") == 11
        assert _chinese_to_arabic("十二") == 12
        assert _chinese_to_arabic("十五") == 15

    def test_in_text(self):
        """函数在段落文本中查找中文章节号。"""
        assert _chinese_to_arabic("第三章 搭接技术") == 3
        assert _chinese_to_arabic("第十一章 测试") == 11

    def test_no_match(self):
        """找不到中文字符时返回 None。"""
        assert _chinese_to_arabic("hello world") is None
        assert _chinese_to_arabic("第3章 测试") is None  # 阿拉伯数字不匹配
        assert _chinese_to_arabic("") is None

    def test_longer_matches_first(self):
        """较长中文数字（如'十一'）优先于较短匹配（如'十'）。"""
        # '十一' 包含 '十'，但排序确保长匹配优先
        assert _chinese_to_arabic("十一") == 11, "应匹配 '十一'=11 而不是 '十'=10"
        assert _chinese_to_arabic("十二") == 12
        assert _chinese_to_arabic("十三") == 13


# =============================================================
# outline_exists
# =============================================================
class TestOutlineExists:
    """Test outline_exists — checks guide file presence and min size."""

    def test_file_not_exists(self, temp_dir):
        root = temp_dir["root"]
        assert outline_exists(str(root), 3) is False

    def test_file_too_small(self, temp_dir):
        root = temp_dir["root"]
        guide = root / "writing-guide-ch3.md"
        guide.write_text("small")  # only 5 bytes, < 100 threshold
        assert outline_exists(str(root), 3) is False

    def test_file_large_enough(self, temp_dir):
        root = temp_dir["root"]
        guide = root / "writing-guide-ch3.md"
        guide.write_text("x" * 200)  # 200 bytes > 100
        assert outline_exists(str(root), 3) is True

    def test_different_chapter(self, temp_dir):
        root = temp_dir["root"]
        guide = root / "writing-guide-ch7.md"
        guide.write_text("x" * 200)
        assert outline_exists(str(root), 7) is True
        assert outline_exists(str(root), 3) is False


# =============================================================
# generate_chapter_outline
# =============================================================
class TestGenerateChapterOutline:
    """Test generate_chapter_outline — writes guide file from template."""

    def test_creates_file(self, temp_dir):
        root = temp_dir["root"]
        output_dir = str(root)
        result = generate_chapter_outline(
            chapter=3,
            title="搭接技术",
            sections=[],
            source_books=[],
            output_dir=output_dir,
        )
        out_path = root / "写作大纲" / "writing-guide-ch3.md"
        assert out_path.exists()
        assert result == str(out_path)

    def test_creates_nested_dir(self, temp_dir):
        """目录不存在时应自动创建。"""
        root = temp_dir["root"]
        output_dir = str(root)
        result = generate_chapter_outline(
            chapter=5,
            title="滤波",
            sections=[],
            source_books=[],
            output_dir=output_dir,
        )
        assert Path(result).exists()

    def test_content_is_template(self, temp_dir):
        """写入的内容应为格式化后的 CHAPTER_TEMPLATE。"""
        root = temp_dir["root"]
        output_dir = str(root)
        generate_chapter_outline(
            chapter=1,
            title="绪论",
            sections=[],
            source_books=[],
            output_dir=output_dir,
        )
        content = (root / "写作大纲" / "writing-guide-ch1.md").read_text(encoding="utf-8")
        assert "# 第1章 绪论 写作指南" in content
        assert content.count("# 第1章") >= 1

    def test_multiple_chapters(self, temp_dir):
        """生成多章时应各自独立。"""
        root = temp_dir["root"]
        output_dir = str(root)
        generate_chapter_outline(1, "绪论", [], [], output_dir)
        generate_chapter_outline(2, "电磁兼容基础", [], [], output_dir)
        ch1 = root / "写作大纲" / "writing-guide-ch1.md"
        ch2 = root / "写作大纲" / "writing-guide-ch2.md"
        assert ch1.exists()
        assert ch2.exists()
        assert "绪论" in ch1.read_text()
        assert "电磁兼容基础" in ch2.read_text()


# =============================================================
# parse_outline_structure
# =============================================================
class TestParseOutlineStructure:
    """Test parse_outline_structure — basic path checks (full parse
    requires a real .docx with python-docx installed)."""

    def test_file_not_found(self):
        """文件不存在时应返回空列表。"""
        result = parse_outline_structure("/nonexistent/path.docx")
        assert result == []
        assert isinstance(result, list)

    def test_empty_path(self):
        """空字符串路径也应返回空列表。"""
        result = parse_outline_structure("")
        assert result == []

    def test_docx_file_behavior(self, temp_dir):
        """测试 .docx 文件存在但无效时的行为：python-docx 已安装则抛
        PackageNotFoundError，否则静默返回 []。"""
        root = temp_dir["root"]
        fake_docx = root / "fake.docx"
        fake_docx.write_text("not a real docx")
        try:
            import docx  # noqa: F401 — check if python-docx is available
            # python-docx 已安装 → 应该抛出 PackageNotFoundError
            import pytest
            with pytest.raises((docx.opc.exceptions.PackageNotFoundError, OSError)):
                parse_outline_structure(str(fake_docx))
        except ImportError:
            # python-docx 未安装 → 静默返回 []
            result = parse_outline_structure(str(fake_docx))
            assert result == []
