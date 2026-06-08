"""yaml_gen.py 单元测试 — 字段提取/类型匹配/验证/交互式生成"""

import os
import tempfile

import pytest
from yaml_gen import (
    ALL_TYPES,
    COMMON_FRONTMATTER_FIELDS,
    QUALITY_KEY_MAP,
    TEMPLATE_FILE_MAP,
    _detect_type_from_path,
    _type_label,
    build_reverse_index,
    extract_template_vars,
    load_field_registry,
    parse_field_mapping,
)

pytestmark = pytest.mark.unit

# ── 常量和映射验证 ──────────────────────────────────────────


class TestConstants:
    """验证常量和映射表的完整性"""

    def test_all_types_in_quality_key_map(self):
        """ALL_TYPES 中的每个类型都应有 quality_key 映射"""
        for t in ALL_TYPES:
            assert t in QUALITY_KEY_MAP, f"{t} 缺少 quality_key 映射"

    def test_all_types_in_template_file_map(self):
        """ALL_TYPES 中的每个类型都应有模板文件映射"""
        for t in ALL_TYPES:
            assert t in TEMPLATE_FILE_MAP, f"{t} 缺少模板文件映射"

    def test_template_files_exist(self):
        """映射的模板文件应当存在于磁盘"""
        skill_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        templates_dir = os.path.join(skill_dir, "assets", "templates")
        if not os.path.exists(templates_dir):
            pytest.skip("templates dir not found")

        unique_files = set(TEMPLATE_FILE_MAP.values())
        for fname in unique_files:
            path = os.path.join(templates_dir, fname)
            assert os.path.exists(path), f"模板文件缺失: {fname}"

    def test_common_fields_not_empty(self):
        """COMMON_FRONTMATTER_FIELDS 应包含基本字段"""
        assert "name" in COMMON_FRONTMATTER_FIELDS
        assert "book_id" in COMMON_FRONTMATTER_FIELDS
        assert len(COMMON_FRONTMATTER_FIELDS) >= 10

    def test_type_label_all(self):
        """_type_label 应支持所有类型"""
        for t in ALL_TYPES:
            label = _type_label(t)
            assert isinstance(label, str) and len(label) > 0


# ── 模板解析 ────────────────────────────────────────────────


class TestExtractTemplateVars:
    """extract_template_vars 函数测试"""

    def test_extract_from_existing_template(self):
        """从实际模板文件提取变量"""
        skill_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        template_path = os.path.join(
            skill_dir, "assets", "templates", "concept_template.md"
        )
        if not os.path.exists(template_path):
            pytest.skip("concept_template.md not found")

        vars_list = extract_template_vars(template_path)
        assert len(vars_list) > 10
        assert "name" in vars_list
        assert "term_definition" in vars_list
        # 变量应唯一
        assert len(vars_list) == len(set(vars_list))

    def test_extract_from_missing_file(self):
        """缺失文件返回空列表"""
        result = extract_template_vars("/nonexistent/template.md")
        assert result == []

    def test_extract_from_temp_template(self):
        """从临时模板提取变量"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False
        ) as f:
            f.write("---\nname: {{name}}\ntype: {{type}}\n---\n\n{{body_field}}\n{{another_field}}\n")
            f.flush()
            path = f.name

        try:
            vars_list = extract_template_vars(path)
            assert "name" in vars_list
            assert "type" in vars_list
            assert "body_field" in vars_list
            assert "another_field" in vars_list
            assert len(vars_list) == 4
        finally:
            os.unlink(path)

    def test_duplicate_vars_deduplicated(self):
        """重复变量应去重"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False
        ) as f:
            f.write("{{name}} {{name}} {{name}}\n{{other}}\n{{name}}\n")
            f.flush()
            path = f.name

        try:
            vars_list = extract_template_vars(path)
            assert vars_list == ["name", "other"]
        finally:
            os.unlink(path)


# ── yaml-field-mapping.md 解析 ──────────────────────────────


class TestParseFieldMapping:
    """parse_field_mapping 函数测试"""

    def test_parse_returns_dict(self):
        """解析应返回 dict"""
        skill_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        md_path = os.path.join(skill_dir, "references", "yaml-field-mapping.md")
        if not os.path.exists(md_path):
            pytest.skip("yaml-field-mapping.md not found")

        sections = parse_field_mapping(md_path)
        assert isinstance(sections, dict)
        assert len(sections) > 5

    def test_frontmatter_section_exists(self):
        """FrontMatter 公共字段节应存在"""
        skill_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        md_path = os.path.join(skill_dir, "references", "yaml-field-mapping.md")
        if not os.path.exists(md_path):
            pytest.skip("yaml-field-mapping.md not found")

        sections = parse_field_mapping(md_path)
        frontmatter_key = "FrontMatter 公共字段（所有类型通用）"
        assert frontmatter_key in sections
        assert "name" in sections[frontmatter_key]

    def test_concept_section_with_required(self):
        """概念类节应包含必填字段标记"""
        skill_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        md_path = os.path.join(skill_dir, "references", "yaml-field-mapping.md")
        if not os.path.exists(md_path):
            pytest.skip("yaml-field-mapping.md not found")

        sections = parse_field_mapping(md_path)
        concept_key = "概念类 (concept_template.md, quality_key=concept)"
        assert concept_key in sections
        assert "term_english" in sections[concept_key]
        assert sections[concept_key]["term_english"].startswith("[required] ")

    def test_skill_section_no_required_column(self):
        """技能点节为3列表格（无必填列）"""
        skill_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        md_path = os.path.join(skill_dir, "references", "yaml-field-mapping.md")
        if not os.path.exists(md_path):
            pytest.skip("yaml-field-mapping.md not found")

        sections = parse_field_mapping(md_path)
        skill_key = "技能点 (skill_template.md, quality_key=skill)"
        assert skill_key in sections
        assert "skill_objectives" in sections[skill_key]
        # 3列表格不应有 [required] 前缀
        desc = sections[skill_key]["skill_objectives"]
        assert not desc.startswith("[required] ")

    def test_missing_file(self):
        """缺失文件返回空 dict"""
        result = parse_field_mapping("/nonexistent/mapping.md")
        assert result == {}


class TestLoadFieldRegistry:
    """load_field_registry 函数测试"""

    def test_returns_four_tuples(self):
        """返回4元组"""
        skill_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        md_path = os.path.join(skill_dir, "references", "yaml-field-mapping.md")
        if not os.path.exists(md_path):
            pytest.skip("yaml-field-mapping.md not found")

        result = load_field_registry()
        assert len(result) == 4
        sections, required_map, desc_map, type_fields_map = result
        assert isinstance(sections, dict)
        assert isinstance(required_map, dict)
        assert isinstance(desc_map, dict)
        assert isinstance(type_fields_map, dict)

    def test_type_fields_map_has_all_types(self):
        """type_fields_map 应包含所有类型"""
        skill_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        md_path = os.path.join(skill_dir, "references", "yaml-field-mapping.md")
        if not os.path.exists(md_path):
            pytest.skip("yaml-field-mapping.md not found")

        _, _, _, type_fields_map = load_field_registry()
        for t in ALL_TYPES:
            assert t in type_fields_map, f"{t} 不在 type_fields_map 中"
            assert len(type_fields_map[t]) > 0, f"{t} 字段列表为空"

    def test_required_map_has_values(self):
        """required_map 应包含必填字段"""
        skill_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        md_path = os.path.join(skill_dir, "references", "yaml-field-mapping.md")
        if not os.path.exists(md_path):
            pytest.skip("yaml-field-mapping.md not found")

        _, required_map, _, _ = load_field_registry()
        assert required_map.get("term_definition") is True
        assert required_map.get("principle_steps") is True

    def test_desc_map_has_values(self):
        """desc_map 应包含字段说明"""
        skill_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        md_path = os.path.join(skill_dir, "references", "yaml-field-mapping.md")
        if not os.path.exists(md_path):
            pytest.skip("yaml-field-mapping.md not found")

        _, _, desc_map, _ = load_field_registry()
        assert "英文术语" in desc_map.get("term_english", "")
        assert "名称" in desc_map.get("name", "")


# ── 反向索引 ────────────────────────────────────────────────


class TestBuildReverseIndex:
    """build_reverse_index 函数测试"""

    def test_specific_field_maps_to_type(self):
        """特定字段应映射到其所属类型"""
        type_fields_map = {
            "concept": ["term_definition", "domain"],
            "skill": ["skill_objectives", "core_operation"],
        }
        reverse = build_reverse_index(type_fields_map)
        assert "concept" in reverse["term_definition"]
        assert "skill" in reverse["skill_objectives"]

    def test_common_fields_in_all_types(self):
        """公共字段应出现在所有类型中"""
        type_fields_map = {
            "concept": ["field_a"],
            "skill": ["field_b"],
        }
        reverse = build_reverse_index(type_fields_map)
        for cf in COMMON_FRONTMATTER_FIELDS:
            assert cf in reverse
            for t in ALL_TYPES:
                assert t in reverse[cf]


# ── 类型检测 ────────────────────────────────────────────────


class TestDetectTypeFromPath:
    """_detect_type_from_path 函数测试"""

    def test_concepts_file(self):
        assert _detect_type_from_path("concepts.yaml") == "concept"
        assert _detect_type_from_path("/path/to/concepts.yaml") == "concept"

    def test_knowledge_file(self):
        assert _detect_type_from_path("knowledge.yaml") == "knowledge"

    def test_skills_file(self):
        assert _detect_type_from_path("skills.yaml") == "skill"

    def test_scenarios_file(self):
        assert _detect_type_from_path("scenarios.yaml") == "scenario"

    def test_exercises_file(self):
        assert _detect_type_from_path("exercises.yaml") == "exercise"

    def test_solutions_file(self):
        assert _detect_type_from_path("solutions.yaml") == "solution"

    def test_unknown_file(self):
        assert _detect_type_from_path("unknown_file.yaml") is None
        assert _detect_type_from_path("random.yaml") is None

    def test_with_path_prefix(self):
        assert (
            _detect_type_from_path(".dag/第1章/data/concepts.yaml") == "concept"
        )


# ── CLI 集成测试 ────────────────────────────────────────────


class TestCLIExtract:
    """extract 子命令测试"""

    def test_extract_concept_exits_ok(self):
        """extract concept 应正常退出"""
        import subprocess
        import sys

        script = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "..", "yaml_gen.py"
        )
        result = subprocess.run(
            [sys.executable, script, "extract", "concept"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0
        assert "- name:" in result.stdout  # v44.2: 容器结构
        assert "fm:" in result.stdout
        assert "bd:" in result.stdout
        assert "term_definition:" in result.stdout

    def test_extract_all_exits_ok(self):
        """extract all 应正常退出"""
        import subprocess
        import sys

        script = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "..", "yaml_gen.py"
        )
        result = subprocess.run(
            [sys.executable, script, "extract", "all"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0
        assert "概念类" in result.stdout
        assert "知识点类" in result.stdout
        assert "技能点类" in result.stdout

    def test_extract_invalid_type_errors(self):
        """无效类型应报错"""
        import subprocess
        import sys

        script = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "..", "yaml_gen.py"
        )
        result = subprocess.run(
            [sys.executable, script, "extract", "invalid_type"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode != 0


class TestCLIMatch:
    """match 子命令测试"""

    def test_match_skill_fields(self):
        """技能点字段应匹配 skill"""
        import subprocess
        import sys

        script = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "..", "yaml_gen.py"
        )
        result = subprocess.run(
            [sys.executable, script, "match", "skill_objectives,core_operation"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0
        assert "skill" in result.stdout

    def test_match_solution_fields(self):
        """解答字段应匹配 solution"""
        import subprocess
        import sys

        script = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "..", "yaml_gen.py"
        )
        result = subprocess.run(
            [sys.executable, script, "match", "principle_steps,characteristics"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0
        assert "solution" in result.stdout

    def test_match_unknown_fields_warns(self):
        """未知字段应警告"""
        import subprocess
        import sys

        script = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "..", "yaml_gen.py"
        )
        result = subprocess.run(
            [sys.executable, script, "match", "nonexistent_field_xyz"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0
        assert "未识别" in result.stdout


class TestCLIValidate:
    """validate 子命令测试"""

    def test_validate_valid_yaml(self):
        """验证合法的 YAML"""
        import subprocess
        import sys

        script = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "..", "yaml_gen.py"
        )
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", prefix="concepts_", delete=False
        ) as f:
            f.write(
                "items:\n"
                "  - name: test\n"
                "    term_english: eng\n"
                "    term_definition: def\n"
                "    definition_sentence: sent\n"
                "    definition_source: src\n"
                "    domain: d\n"
                "    classification: c\n"
                "    core_concept_map: m\n"
                "    core_concept_map_analysis: a\n"
                "    structure: s\n"
                "    application_scenarios: app\n"
                "    engineering_practices: engp\n"
                "    common_misconceptions: misc\n"
                "    related_concepts_relations: rel\n"
                "    related_knowledge_elements: ke\n"
                "    learning_objectives: obj\n"
                "    prerequisite_knowledge: pre\n"
                "    self_check_questions: q\n"
            )
            path = f.name

        try:
            result = subprocess.run(
                [sys.executable, script, "validate", path],
                capture_output=True,
                text=True,
                timeout=30,
            )
            assert result.returncode == 0
            assert "有效" in result.stdout
        finally:
            os.unlink(path)

    def test_validate_missing_file(self):
        """验证缺失文件应报错"""
        import subprocess
        import sys

        script = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "..", "yaml_gen.py"
        )
        result = subprocess.run(
            [sys.executable, script, "validate", "/nonexistent/file.yaml"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode != 0

    def test_validate_no_items_key(self):
        """无 items 键应报错"""
        import subprocess
        import sys

        script = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "..", "yaml_gen.py"
        )
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", prefix="concepts_", delete=False
        ) as f:
            f.write("other: value\n")
            path = f.name

        try:
            result = subprocess.run(
                [sys.executable, script, "validate", path],
                capture_output=True,
                text=True,
                timeout=30,
            )
            assert result.returncode != 0
        finally:
            os.unlink(path)
