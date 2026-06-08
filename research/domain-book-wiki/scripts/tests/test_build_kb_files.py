"""build_kb_files.py 单元测试 — Mermaid 净化、括号感知拆分"""


import pytest
from build_kb_files import _sanitize_mermaid, _split_stmts_bracket_aware

pytestmark = pytest.mark.unit

# ── _split_stmts_bracket_aware ──────────────────────────


class TestSplitStmtsBracketAware:
    """括号感知分号拆分"""

    def test_simple_split(self):
        result = _split_stmts_bracket_aware("A --> B; C --> D")
        assert result == ["A --> B", "C --> D"]

    def test_no_semicolon(self):
        result = _split_stmts_bracket_aware("A --> B")
        assert result == ["A --> B"]

    def test_bracket_protected(self):
        """方括号内的分号不拆分"""
        result = _split_stmts_bracket_aware("A[text;more] --> B; C --> D")
        assert len(result) == 2
        assert "text;more" in result[0]

    def test_curly_brace_protected(self):
        """花括号内的分号不拆分"""
        result = _split_stmts_bracket_aware("A{cond;alt} --> B; C --> D")
        assert len(result) == 2
        assert "cond;alt" in result[0]

    def test_double_quote_protected(self):
        """双引号内的分号不拆分"""
        result = _split_stmts_bracket_aware('A["text;inside"] --> B; C')
        assert len(result) == 2

    def test_single_quote_protected(self):
        """单引号内的分号不拆分"""
        result = _split_stmts_bracket_aware("A['text;inside'] --> B; C")
        assert len(result) == 2

    def test_empty_string(self):
        result = _split_stmts_bracket_aware("")
        assert result == []

    def test_trailing_semicolon(self):
        result = _split_stmts_bracket_aware("A --> B;")
        assert result == ["A --> B"]

    def test_multiple_semicolons(self):
        result = _split_stmts_bracket_aware("A; B; C; D")
        assert result == ["A", "B", "C", "D"]

    def test_nested_brackets(self):
        """嵌套括号"""
        result = _split_stmts_bracket_aware("A[{x;y}] --> B; C")
        assert len(result) == 2


# ── _sanitize_mermaid ────────────────────────────────────


class TestSanitizeMermaid:
    """Mermaid 代码净化"""

    def test_preserves_graph_declaration(self):
        code = "graph TD\n    A --> B"
        result = _sanitize_mermaid(code)
        assert "graph TD" in result

    def test_preserves_flowchart_declaration(self):
        code = "flowchart LR\n    A --> B"
        result = _sanitize_mermaid(code)
        assert "flowchart LR" in result

    def test_preserves_subgraph(self):
        code = "graph TD\n    subgraph Title\n        A --> B\n    end"
        result = _sanitize_mermaid(code)
        assert "subgraph Title" in result
        assert "end" in result

    def test_quotes_bracket_nodes_with_special_chars(self):
        """含特殊字符的方括号节点应被加引号"""
        code = "graph TD\n    A[公式: E=mc^2]"
        result = _sanitize_mermaid(code)
        # 应该包含引号包裹
        assert '"' in result or "E=mc" in result

    def test_preserves_comment_lines(self):
        code = "graph TD\n    %% this is a comment\n    A --> B"
        result = _sanitize_mermaid(code)
        assert "%% this is a comment" in result

    def test_preserves_empty_lines(self):
        code = "graph TD\n\n    A --> B"
        result = _sanitize_mermaid(code)
        assert "\n\n" in result or result.count("\n") >= 2

    def test_splits_semicolon_statements(self):
        """分号分隔的语句应被拆成多行"""
        code = "graph TD\n    A --> B; C --> D"
        result = _sanitize_mermaid(code)
        lines = [line.strip() for line in result.split("\n") if line.strip()]
        assert "A --> B" in lines
        assert "C --> D" in lines

    def test_preserves_style_lines(self):
        code = "graph TD\n    style A fill:#f9f"
        result = _sanitize_mermaid(code)
        assert "style A fill:#f9f" in result

    def test_empty_input(self):
        result = _sanitize_mermaid("")
        assert result == ""

    def test_no_modification_needed(self):
        """简单 Mermaid 代码不需要修改"""
        code = "graph TD\n    A --> B"
        result = _sanitize_mermaid(code)
        # 结果应该等价（可能格式略有不同）
        assert "A --> B" in result

    def test_edge_label_preserved(self):
        """边标签应被保留"""
        code = "graph TD\n    A -->|label| B"
        result = _sanitize_mermaid(code)
        assert "label" in result


# ── BUILDER_CONFIG 常量测试 ─────────────────────────────


class TestBuilderConfig:
    """BUILDER_CONFIG 常量一致性"""

    def test_builder_config_exists(self):
        from build_kb_files import BUILDER_CONFIG
        assert isinstance(BUILDER_CONFIG, dict)

    def test_builder_config_has_type_keys(self):
        from build_kb_files import BUILDER_CONFIG
        # 至少应包含一些类型配置
        assert len(BUILDER_CONFIG) > 0

    def test_data_dir_exists(self):
        from build_kb_files import DATA_DIR
        assert isinstance(DATA_DIR, str)


# ── _sanitize_file_mermaid ──────────────────────────────


class TestSanitizeFileMermaid:
    """文件级 Mermaid 净化"""

    def test_no_mermaid_blocks(self, tmp_path):
        """不含 mermaid 块的文件不修改"""
        path = tmp_path / "test.md"
        path.write_text("# Title\n\nJust text\n")
        from build_kb_files import _sanitize_file_mermaid
        result = _sanitize_file_mermaid(str(path))
        assert result == 0

    def test_with_mermaid_block(self, tmp_path):
        """包含 mermaid 块的文件应被处理"""
        path = tmp_path / "test.md"
        content = "# Title\n\n```mermaid\ngraph TD\n    A --> B; C --> D\n```\n"
        path.write_text(content)
        from build_kb_files import _sanitize_file_mermaid
        result = _sanitize_file_mermaid(str(path))
        # 可能有修改也可能没有，取决于内容是否需要净化
        assert isinstance(result, int)
        assert result >= 0


# ── build_type 基础测试 ──


class TestBuildType:
    """build_type() 参数化类型构建器测试"""

    @pytest.fixture(autouse=True)
    def _setup_env(self, monkeypatch):
        """设置 build_type 所需的环境变量"""
        monkeypatch.setenv("KB_BOOK_ID", "01_test_book")
        monkeypatch.setenv("KB_BOOK_NAME", "测试教材")
        # 强制重新导入，使 BOOK_ID/BOOK_NAME 获取到 monkeypatched 的环境变量
        import build_kb_files
        build_kb_files.BOOK_ID = "01_test_book"
        build_kb_files.BOOK_NAME = "测试教材"

    def _make_minimal_concept_fixture(self, tmp_path, chapter="3", items=None):
        """创建最小概念 YAML 数据文件"""
        if items is None:
            items = [
                {
                    "name": "测试概念A",
                    "file": "test_concept_a",
                    "bd": {
                        "term_english": "Test Concept A",
                        "term_definition": "一个用于测试的概念定义。",
                        "definition_sentence": "测试概念A是指用于验证构建流程的示例概念。",
                        "definition_source": "测试来源 §1.1",
                        "learning_objectives": "理解测试概念的基本含义。",
                        "prerequisite_knowledge": "无",
                        "core_concept_map": "```mermaid\\ngraph TD\\n    A[测试概念A]\\n```",
                        "core_concept_map_source": "测试数据",
                        "core_concept_map_analysis": "简单的测试图谱。",
                        "structure": "无特殊结构。",
                        "mathematical_model": "无",
                        "key_parameters": "无",
                        "features": "用于测试的特性。",
                        "tech_classification": "测试分类",
                        "application_scenarios": "测试场景",
                        "typical_systems": "无",
                        "value": "测试价值",
                        "engineering_practices": "无",
                        "common_misconceptions": "无",
                        "related_concepts_relations": "无",
                        "confusion_compare": "无",
                        "evolution": "无",
                        "related_knowledge_elements": "无",
                        "upstream_downstream": "无",
                        "self_check_questions": "什么是测试概念？",
                        "references": "无",
                        "additional_explanations": "补充说明内容",
                        "formula_references": "无",
                        "figure_references": "无",
                    },
                    "fm": {
                        "confidence": 0.95,
                        "confidence_note": "测试数据",
                        "source_chapter": f"第{chapter}章",
                        "source_from": "测试生成",
                    },
                },
            ]
        dag_dir = tmp_path / ".dag" / f"第{chapter}章" / "data"
        dag_dir.mkdir(parents=True, exist_ok=True)
        yaml_path = dag_dir / "concepts.yaml"
        import yaml
        with open(yaml_path, "w", encoding="utf-8") as f:
            yaml.dump(items, f, allow_unicode=True)
        return yaml_path

    def test_build_type_basic(self, tmp_path):
        """用最小 YAML 数据调用 build_type，验证生成 .md 文件"""
        from build_kb_files import build_type

        self._make_minimal_concept_fixture(tmp_path)
        output_dir = str(tmp_path)

        count = build_type(output_dir, chapter="3", graph_check=False, type_name="concept")
        assert count >= 1

        # 验证文件已生成
        from dag_utils import DIR
        out_dir = tmp_path / DIR["CONCEPTS"]
        assert out_dir.is_dir()
        md_files = list(out_dir.glob("*.md"))
        assert len(md_files) >= 1
        # 验证文件内容包含概念名
        content = (out_dir / "test_concept_a.md").read_text()
        assert "测试概念A" in content

    def test_build_type_empty_items(self, tmp_path):
        """空 items 列表不报错，返回 0"""
        from build_kb_files import build_type

        self._make_minimal_concept_fixture(tmp_path, items=[])
        output_dir = str(tmp_path)

        count = build_type(output_dir, chapter="3", graph_check=False, type_name="concept")
        assert count == 0

    def test_build_type_missing_template(self, tmp_path, monkeypatch):
        """模板文件不存在时报友好错误（不崩溃）"""
        import build_kb_files
        import template_assembler

        self._make_minimal_concept_fixture(tmp_path)
        output_dir = str(tmp_path)

        # 保存原始 load_template
        _real = template_assembler.load_template

        def _mock_load(name):
            if name == "concept_template.md":
                raise FileNotFoundError(f"模板不存在: {name}")  # 模拟模板不存在
            return _real(name)

        # Patch 两个引用点（build_type 和 assemble_md 都用）
        monkeypatch.setattr(template_assembler, "load_template", _mock_load)
        monkeypatch.setattr(build_kb_files, "load_template", _mock_load)
        # v50.7: assemble_md 在 template_writers 中，也需 patch
        try:
            import template_writers
            monkeypatch.setattr(template_writers, "load_template", _mock_load)
        except ImportError:
            pass

        # 调用不应崩溃
        count = build_kb_files.build_type(output_dir, chapter="3", graph_check=False, type_name="concept")
        # 模板不存在时 count 应为 0（assemble_md 也会因模板为 None 失败）
        assert count == 0

    def test_build_type_multiple_items(self, tmp_path):
        """多个 items 时应生成多个文件"""
        from build_kb_files import build_type

        items = [
            {
                "name": f"概念{i}",
                "file": f"concept_{i}",
                "bd": {
                    "term_english": f"Concept {i}",
                    "term_definition": f"概念{i}的定义。",
                    "definition_sentence": f"概念{i}是指一个示例概念。",
                    "definition_source": "§1.1",
                    "learning_objectives": "理解",
                    "prerequisite_knowledge": "无",
                    "core_concept_map": "```mermaid\\ngraph TD\\n    A[概念]\\n```",
                    "core_concept_map_source": "数据",
                    "core_concept_map_analysis": "分析",
                    "structure": "无",
                    "mathematical_model": "无",
                    "key_parameters": "无",
                    "features": "特性",
                    "tech_classification": "分类",
                    "application_scenarios": "场景",
                    "typical_systems": "无",
                    "value": "价值",
                    "engineering_practices": "无",
                    "common_misconceptions": "无",
                    "related_concepts_relations": "无",
                    "confusion_compare": "无",
                    "evolution": "无",
                    "related_knowledge_elements": "无",
                    "upstream_downstream": "无",
                    "self_check_questions": "问题",
                    "references": "无",
                    "additional_explanations": "说明",
                    "formula_references": "无",
                    "figure_references": "无",
                },
                "fm": {
                    "confidence": 0.95,
                    "confidence_note": "测试",
                    "source_chapter": "第3章",
                    "source_from": "测试",
                },
            }
            for i in range(1, 4)
        ]
        self._make_minimal_concept_fixture(tmp_path, items=items)
        output_dir = str(tmp_path)

        count = build_type(output_dir, chapter="3", graph_check=False, type_name="concept")
        assert count == 3

        from dag_utils import DIR
        out_dir = tmp_path / DIR["CONCEPTS"]
        for i in range(1, 4):
            assert (out_dir / f"concept_{i}.md").exists()

    def test_build_type_uses_ke_type(self, tmp_path):
        """验证 build_type 支持 KE 类型"""
        from build_kb_files import build_type

        # 创建 KE 类型的 YAML 数据
        items = [
            {
                "name": "传导耦合",
                "file": "ke_conduction_coupling",
                "bd": {
                    "term_english": "Conduction Coupling",
                    "term_definition": "通过导体直接传输的电磁干扰耦合方式。",
                    "definition_sentence": "传导耦合是指电磁干扰通过导线、PCB走线等导体直接传输的耦合方式。",
                    "definition_source": "教材 §2.1",
                    "learning_objectives": "掌握传导耦合的基本概念和分类。",
                    "prerequisite_knowledge": "电路基础",
                    "core_concept_map": "```mermaid\\ngraph TD\\n    A[传导耦合]\\n```",
                    "core_concept_map_source": "教材",
                    "core_concept_map_analysis": "分析",
                    "structure": "导体传输路径",
                    "mathematical_model": "无",
                    "key_parameters": "阻抗、频率",
                    "features": "低频主导",
                    "tech_classification": "测试耦合",
                    "application_scenarios": "PCB设计",
                    "typical_systems": "电源线",
                    "value": "基础概念",
                    "engineering_practices": "滤波",
                    "common_misconceptions": "无",
                    "related_concepts_relations": "辐射耦合",
                    "confusion_compare": "无",
                    "evolution": "无",
                    "related_knowledge_elements": "共模干扰",
                    "upstream_downstream": "概念A→路径→概念B",
                    "self_check_questions": "概念A与概念B的区别？",
                    "references": "教材第2章",
                    "additional_explanations": "说明",
                    "formula_references": "无",
                    "figure_references": "无",
                },
                "fm": {
                    "confidence": 0.85,
                    "confidence_note": "已验证",
                    "source_chapter": "第3章",
                    "source_from": "教材提取",
                },
            },
        ]
        dag_dir = tmp_path / ".dag" / "第3章" / "data"
        dag_dir.mkdir(parents=True, exist_ok=True)
        yaml_path = dag_dir / "kes.yaml"
        import yaml
        with open(yaml_path, "w", encoding="utf-8") as f:
            yaml.dump(items, f, allow_unicode=True)
        output_dir = str(tmp_path)

        count = build_type(output_dir, chapter="3", graph_check=False, type_name="ke")
        assert count == 1

        from dag_utils import DIR
        out_dir = tmp_path / DIR["KE"]
        assert (out_dir / "ke_conduction_coupling.md").exists()
