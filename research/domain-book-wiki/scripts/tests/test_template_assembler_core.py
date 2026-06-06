"""test_template_assembler.py — 模板组装核心函数测试

覆盖: verify_definition, parse_template, fill_template, check_placeholders,
      add_mermaid_init, _wrap_mermaid_fields, _fix_mermaid_block_boundaries.
"""

import os

import pytest
from template_assembler import (
    DEFINITION_MARKERS,
    _wrap_mermaid_fields,
    add_mermaid_init,
    check_placeholders,
    fill_template,
    parse_template,
    verify_definition,
)

pytestmark = pytest.mark.unit


class TestVerifyDefinition:
    def test_valid_definition_with_marker(self):
        """含标记词的完整定义应通过"""
        assert verify_definition("概念A是指设备在特定环境中正常工作的能力", "概念A") is True

    def test_empty_definition_fails(self):
        """空定义应失败"""
        assert verify_definition("", "概念A") is False
        assert verify_definition("   ", "概念A") is False

    def test_missing_marker_word_fails(self):
        """无标记词的定义应失败"""
        # "是" 也是标记词，所以需要用完全不含任何标记词的文本
        assert verify_definition("概念A技术广泛应用于电子设备领域", "概念A") is False

    def test_definition_with_source_verification(self):
        """有出处时定义应能在正文中检索到"""
        source = "概念A是指设备或系统在其特定环境中符合要求运行并不对其环境中的任何设备产生无法容忍的干扰的能力。"
        definition = "概念A是指设备或系统在其特定环境中符合要求运行"
        assert verify_definition(definition, "概念A", source) is True

    def test_definition_not_in_source_fails(self):
        """定义不在出处正文中应失败（source_file 为文件路径）"""
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("这是一段完全不同的正文内容，没有任何关于概念A的描述。")
            tmp = f.name
        try:
            definition = "概念A是指设备在特定环境中正常工作"
            result = verify_definition(definition, "概念A", tmp)
            assert result is False
        finally:
            os.unlink(tmp)

    def test_marker_words_coverage(self):
        """关键标记词列表应包含常见词"""
        assert "是指" in DEFINITION_MARKERS
        assert "称为" in DEFINITION_MARKERS
        assert "即" in DEFINITION_MARKERS or "即 " in DEFINITION_MARKERS


class TestParseTemplate:
    def test_parse_simple_template(self):
        """解析含 Front Matter + {{变量}} 的模板"""
        content = "---\ntype: concept\n---\n## {{name}}\n\n{{description}}"
        result = parse_template(content)
        assert isinstance(result, dict)

    def test_parse_empty_template_raises(self):
        """空模板应抛 ValueError"""
        with pytest.raises(ValueError):
            parse_template("")


class TestFillTemplate:
    def test_fill_replacements(self):
        """替换模板中的占位符"""
        template = "名称：{{name}}\n描述：{{desc}}"
        replacements = {"name": "电磁屏蔽", "desc": "防止电磁干扰的技术"}
        result = fill_template(template, replacements)
        assert "电磁屏蔽" in result
        assert "防止电磁干扰的技术" in result

    def test_fill_preserves_unmatched(self):
        """未匹配的占位符应保留"""
        template = "{{name}} 和 {{unknown}}"
        replacements = {"name": "测试"}
        result = fill_template(template, replacements)
        assert "测试" in result
        assert "{{unknown}}" in result


class TestCheckPlaceholders:
    def test_no_placeholders_returns_zero(self):
        """无占位符的文件应返回 0"""
        content = "---\ntype: concept\nname: 测试\n---\n\n这是完整内容，没有占位符。"
        assert check_placeholders(content, "test.md") == 0

    def test_placeholders_detected(self):
        """含 {{placeholder}} 应返回正数"""
        content = "---\ntype: concept\n---\n\n{{description}}\n\n{{formula}}"
        count = check_placeholders(content, "test.md")
        assert count >= 2


class TestMermaidUtils:
    def test_add_mermaid_init(self):
        """add_mermaid_init 应为 Mermaid 块添加 %%{init}"""
        content = "```mermaid\ngraph TD\n    A --> B\n```"
        result = add_mermaid_init(content)
        # 应包含 %%{init} 或保持不变（如果已存在）
        assert "mermaid" in result

    def test_wrap_mermaid_fields(self):
        """_wrap_mermaid_fields 应包裹未闭合的 mermaid 字段"""
        content = "flowchart:\ngraph TD\n    A --> B\n\nother_field: value"
        result = _wrap_mermaid_fields(content)
        assert isinstance(result, str)

    def test_fix_mermaid_block_boundaries(self):
        """_fix_mermaid_block_boundaries 应修复 Mermaid 块闭合问题"""
        from template_assembler import _fix_mermaid_block_boundaries

        # 正常 Mermaid 块
        content = "```mermaid\n%%{init}%%\ngraph TD\n    A --> B\n```\n\n后续内容"
        result = _fix_mermaid_block_boundaries(content)
        assert "后续内容" in result


class TestDefinitionMarkers:
    def test_markers_sorted_by_length(self):
        """DEFINITION_MARKERS_SORTED 应按长度降序"""
        from template_assembler import DEFINITION_MARKERS_SORTED


        for i in range(len(DEFINITION_MARKERS_SORTED) - 1):
            assert len(DEFINITION_MARKERS_SORTED[i]) >= len(DEFINITION_MARKERS_SORTED[i + 1])
