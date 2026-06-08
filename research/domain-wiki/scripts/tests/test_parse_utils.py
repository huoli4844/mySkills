"""parse_utils 单元测试 — v38.0"""



import pytest
from parse_utils import (
    extract_section,
    find_placeholders,
    has_placeholder,
    parse_frontmatter,
    safe_filename,
    section_has_real_content,
    split_fm_body,
)

pytestmark = pytest.mark.unit



class TestParseFrontmatter:
    def test_basic_yaml(self):
        content = "---\nname: test\ntype: concept\n---\nbody"
        result = parse_frontmatter(content)
        assert result["name"] == "test"
        assert result["type"] == "concept"

    def test_numeric_values(self):
        content = "---\nconfidence: 0.95\nchapter_num: 3\n---\nbody"
        result = parse_frontmatter(content)
        assert result["confidence"] == 0.95
        assert result["chapter_num"] == 3

    def test_quoted_strings(self):
        content = '---\nname: "quoted name"\ntags: ["a", "b"]\n---\nbody'
        result = parse_frontmatter(content)
        assert result["name"] == "quoted name"
        assert isinstance(result["tags"], list)

    def test_empty_content(self):
        result = parse_frontmatter("")
        assert result == {}

    def test_no_frontmatter(self):
        result = parse_frontmatter("just body text")
        assert result == {}

    def test_colon_in_value(self):
        content = "---\nsource: 第3章: 概述\n---\nbody"
        result = parse_frontmatter(content)
        assert "第3章" in str(result.get("source", ""))


class TestSplitFmBody:
    def test_basic_split(self):
        content = "---\nname: test\n---\nbody text here"
        fm, body = split_fm_body(content)
        assert "name: test" in fm
        assert "body text here" in body

    def test_no_frontmatter(self):
        fm, body = split_fm_body("just body")
        assert fm == ""
        assert "just body" in body


class TestHasPlaceholder:
    def test_curly_brace_placeholder(self):
        assert has_placeholder("text {{name}} more") is True

    def test_chinese_placeholder(self):
        assert has_placeholder("（待补充）") is True

    def test_no_placeholder(self):
        assert has_placeholder("clean text") is False

    def test_empty_string(self):
        assert has_placeholder("") is False


class TestFindPlaceholders:
    def test_finds_multiple(self):
        text = "{{name}} and {{type}} and {{confidence}}"
        result = find_placeholders(text)
        assert len(result) >= 2

    def test_no_placeholders(self):
        result = find_placeholders("no placeholders here")
        assert len(result) == 0


class TestSafeFilename:
    def test_removes_special_chars(self):
        result = safe_filename("test/file:name")
        assert "/" not in result
        assert ":" not in result

    def test_preserves_chinese(self):
        result = safe_filename("核心概念-概念A")
        assert "核心概念" in result
        assert "概念A" in result

    def test_empty_input(self):
        result = safe_filename("")
        assert isinstance(result, str)


class TestExtractSection:
    def test_basic_extraction(self):
        body = "### 定义\n这是定义内容\n### 应用\n这是应用"
        result = extract_section(body, "定义")
        assert "这是定义内容" in result

    def test_section_not_found(self):
        body = "### 其他\n内容"
        result = extract_section(body, "定义")
        assert result == ""


class TestSectionHasRealContent:
    def test_real_content(self):
        body = "### 定义\n这是一段真实的定义内容，超过十个字符。\n### 应用\n内容"
        assert section_has_real_content(body, "定义") is True

    def test_empty_section(self):
        body = "### 定义\n\n### 应用\n内容"
        assert section_has_real_content(body, "定义") is False

    def test_wu_is_valid(self):
        """v35.2: '无' 是合法填充值"""
        body = "### 定义\n无\n### 应用\n内容"
        # "无" 被视为无内容
        assert section_has_real_content(body, "定义") is False
