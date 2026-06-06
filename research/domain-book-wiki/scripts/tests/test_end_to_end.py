"""端到端集成测试：验证 pipeline 从零到产出的全流程。

不依赖真实知识库数据，使用临时工作区和最小 YAML 输入。
标记为 integration 以免在无 uv/pyyaml 的环境中误跑。
"""

import json
import os

import pytest
from dag_constants import DIR
from dag_pipeline_ops import pipeline_init
from dag_state import WorkspacePaths


@pytest.mark.integration
class TestEndToEndPipeline:
    """从零创建临时工作区 → pipeline init → 写 YAML → build → 验证输出"""

    def _write_source_file(self, src_dir: str, chapter: int) -> str:
        """创建最小测试用章节源文件"""
        fname = f"第{chapter}章 测试章节.md"
        content = f"""# 第{chapter}章 测试章节

## 概述

本章介绍测试概念。

## {chapter}.1 测试概念的定义

**测试概念**是指一个用于验证pipeline功能的最小化理论单元。它是知识库的基本构建块。

## {chapter}.2 测试概念的影响因素

测试概念的主要影响因素包括：
- 因素A
- 因素B
- 因素C

## {chapter}.3 测试概念的分析方法

测试概念的分析方法主要包括：

### 方法一：定性分析

通过逻辑推理判断。

### 方法二：定量计算

通过数学公式计算。

## {chapter}.4 测试概念的应用

测试概念广泛应用于自动化测试领域。

### 应用场景1

场景描述。

### 应用场景2

场景描述。

## 小结

本章介绍了测试概念的核心内容。

## 习题

1. 什么是测试概念？
2. 测试概念的影响因素有哪些？
3. 简述测试概念的分析方法。
"""
        path = os.path.join(src_dir, fname)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return path

    def _write_concept_yaml(self, data_dir: str) -> str:
        """创建最小测试用概念 YAML"""
        items = [
            {
                "name": "测试概念",
                "file": "测试概念",
                "fm": {
                    "source_chapter": "1",
                    "source_from": "§1.1",
                    "confidence": 0.95,
                    "confidence_note": "测试用最小概念",
                },
                "bd": {
                    "term_definition": "用于验证pipeline功能的最小化理论单元。",
                    "definition_sentence": "测试概念是指一个用于验证pipeline功能的最小化理论单元。",
                    "learning_objectives": "知道→理解：掌握测试概念的定义和影响因素。",
                    "prerequisite_knowledge": "无",
                    "term_english": "Test Concept",
                    "domain": "测试领域",
                    "classification": "测试分类",
                    "core_concept_map": "无",
                    "core_concept_map_analysis": "无",
                    "structure": "测试概念由定义、影响因素和分析方法构成。",
                    "mathematical_model": "无",
                    "application_scenarios": "- 自动化测试\n- 知识库构建",
                    "engineering_practices": "- 在知识库构建中用于验证pipeline流程。\n- 在自动化测试中作为最小可验证单元。",
                    "common_misconceptions": "- 误区：概念必须复杂。事实：最小化概念也能独立成篇。",
                    "related_concepts_relations": "- [[测试概念]] 是知识库的基本构建块",
                    "related_knowledge_elements": "无",
                    "related_directory": "无",
                    "upstream_downstream": "无",
                    "evolution": "无",
                    "confusion_compare": "无",
                    "value": "测试用最小概念具有验证价值。",
                    "typical_systems": "无",
                    "key_parameters": "无",
                    "features": "最小化、可验证、独立性",
                    "tech_classification": "无",
                },
            }
        ]
        os.makedirs(data_dir, exist_ok=True)
        path = os.path.join(data_dir, "concepts.yaml")
        with open(path, "w", encoding="utf-8") as f:
            import yaml

            yaml.dump(items, f, allow_unicode=True, default_flow_style=False)
        return path

    def test_full_pipeline(self, tmp_path):
        """创建临时工作区 → pipeline init → 写 YAML → build → 验证输出"""
        wr = str(tmp_path)
        book_id = "01_testbook"
        ch = "1"

        # ── Phase 1: 创建源文件 ──
        src_dir = os.path.join(wr, DIR["SOURCE"])
        os.makedirs(src_dir, exist_ok=True)
        self._write_source_file(src_dir, int(ch))

        # ── Phase 1.5: pipeline init ──
        args_type = type("Args", (), {
            "wiki_root": wr,
            "book_id": book_id,
            "chapter": ch,
            "book_name": "测试教材",
            "force": False,
        })
        pipeline_init(args_type())

        # 验证 state 文件已创建
        state_path = os.path.join(wr, ".dag", f"{book_id}_ch{ch}.json")
        assert os.path.exists(state_path), f"state file not created: {state_path}"
        with open(state_path) as f:
            state = json.load(f)
        assert state["book_id"] == book_id
        assert state["chapter"] == ch
        assert "phases" in state

        # ── Phase 1.5: preprocess_toc（CLI 模式）──
        import subprocess
        import sys

        toc_dir = os.path.join(wr, ".dag", f"第{ch}章")
        os.makedirs(toc_dir, exist_ok=True)
        toc_path = os.path.join(toc_dir, "chapter_toc.json")
        ms = sorted(
            f for f in os.listdir(src_dir)
            if f.startswith(f"第{ch}章") and f.endswith(".md")
        )
        assert ms, "no source file found"
        src_path = os.path.join(src_dir, ms[0])
        ppt_script = os.path.join(os.path.dirname(__file__), "..", "preprocess_toc.py")
        subprocess.run(
            [sys.executable, ppt_script, src_path, "-o", toc_path],
            capture_output=True, text=True, timeout=30, check=True,
        )
        assert os.path.exists(toc_path), "chapter_toc.json not created"

        # ── Phase 2: 写 YAML → .dag/第1章/data/ ──
        data_dir = os.path.join(wr, ".dag", f"第{ch}章", "data")
        self._write_concept_yaml(data_dir)
        assert os.path.exists(os.path.join(data_dir, "concepts.yaml"))

        # ── Phase 2: build concepts（CLI 模式）──
        kb_script = os.path.join(os.path.dirname(__file__), "..", "build_kb_files.py")
        build_result = subprocess.run(
            [sys.executable, kb_script,
             "--type", "concept",
             "--output-dir", wr,
             "--book-id", book_id,
             "--source-dir", src_dir,
             "--chapter", ch],
            capture_output=True, text=True, timeout=60,
        )
        if build_result.returncode != 0:
            print("STDOUT:", build_result.stdout[-500:])
            print("STDERR:", build_result.stderr[-500:])
        assert build_result.returncode == 0, f"build failed: {build_result.stderr[-300:]}"

        wp = WorkspacePaths(wr)
        concept_dir = wp.content_dir("concepts")
        md_files = [f for f in os.listdir(concept_dir) if f.endswith(".md")]
        assert len(md_files) >= 1, f"no concept md files in {concept_dir}"
        concept_path = os.path.join(concept_dir, "测试概念.md")
        assert os.path.exists(concept_path), "测试概念.md not created"
        with open(concept_path) as f:
            content = f.read()
        assert "测试概念" in content
        assert "## 学习目标" in content
        assert "一、基础信息" in content
        assert "二、核心内容" in content
        assert "三、应用与关联" in content
        assert "## 关联目录" in content

        # ── Phase 2: content-check ──
        from content_check_rules import check_file_full

        results = check_file_full(concept_path, "concept", wr)
        assert results is not None
        fails = sum(1 for r in results if r[0] == "FAIL")
        # 允许少量 WARN，不允许 FAIL（最小化 YAML 可能触发字段字数告警）
        assert fails == 0, f"content-check: {fails} FAIL(s): {[r for r in results if r[0] == 'FAIL'][:3]}"

        # ── 最终验证：产出文件结构 ──
        dirs_to_check = [
            ("30_核心概念", wp.content_dir("concepts")),
            ("40_知识要素", wp.content_dir("ke")),
        ]
        for label, d in dirs_to_check:
            assert os.path.isdir(d) or not os.path.exists(d), f"{label} dir issue: {d}"

        print(f"\n✅ 端到端测试通过: {len(md_files)} 概念文件生成, 0 FAIL")
