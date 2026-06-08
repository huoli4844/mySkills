"""tests/test_review.py — 质量审查模块测试"""
import subprocess
import sys
import json
import os

SCRIPT_DIR = os.path.join(os.path.dirname(__file__), "..", "scripts")
sys.path.insert(0, SCRIPT_DIR)


def test_check_item_pass():
    """check-item 应通过高质量YAML项"""
    item = json.dumps({
        "name": "测试概念",
        "fm": {"source_chapter": "3", "confidence": 0.95},
        "bd": {
            "term_definition": "A" * 80,
            "learning_objectives": "B" * 80,
            "prerequisite_knowledge": "C" * 30,
            "core_concept_map": "graph TD; A-->B",
            "working_principle": "D" * 80,
            "application_scenarios": "E" * 50,
        },
    }, ensure_ascii=False)
    r = subprocess.run(
        [sys.executable, os.path.join(SCRIPT_DIR, "quality_reviewer.py"),
         "check-item", "--type", "concept", "--threshold", "0.8",
         "--item", item],
        capture_output=True, text=True
    )
    data = json.loads(r.stdout)
    assert data["pass"], f"应通过但实际分数={data['score']}"
    print(f"  ✅ test_check_item_pass: score={data['score']:.0%}")


def test_check_item_fail():
    """check-item 应拦截短字段"""
    item = json.dumps({
        "name": "短字段概念",
        "fm": {"source_chapter": "3", "confidence": 0.95},
        "bd": {"term_definition": "短", "learning_objectives": "短"},
    }, ensure_ascii=False)
    r = subprocess.run(
        [sys.executable, os.path.join(SCRIPT_DIR, "quality_reviewer.py"),
         "check-item", "--type", "concept", "--threshold", "0.9",
         "--item", item],
        capture_output=True, text=True
    )
    data = json.loads(r.stdout)
    assert not data["pass"], f"应拦截但实际通过 score={data['score']}"
    assert any(i["field"] == "term_definition" for i in data["issues"]), "应检测到term_definition太短"
    print(f"  ✅ test_check_item_fail: score={data['score']:.0%} (拦截正确)")


def test_imports():
    """检查新模块可导入"""
    errs = []
    for mod in ["review_field_depth", "review_format", "yaml_schema", "yaml_signals", "pipeline_fix"]:
        try:
            __import__(mod)
        except ImportError as e:
            errs.append(f"{mod}: {e}")
    assert not errs, f"导入失败: {errs}"
    print(f"  ✅ test_imports: 全部模块导入成功")


def test_dag_state():
    """检查 dag_state 14 阶段"""
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
    from dag_state import PHASES
    names = [p["name"] for p in PHASES]
    assert "quality_review" in names, "缺少 quality_review 阶段"
    assert "auto_fix" in names, "缺少 auto_fix 阶段"
    assert len(PHASES) == 14, f"应为14阶段, 实际{len(PHASES)}"
    print(f"  ✅ test_dag_state: {len(PHASES)} 阶段")


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("✅ 全部通过")
