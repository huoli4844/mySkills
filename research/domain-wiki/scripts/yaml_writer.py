#!/usr/bin/env python3
"""yaml_writer.py — Agent写YAML的pydantic工具（v2.0）

从 domain_book_schema.json 读取字段定义，动态生成Pydantic模型。
Agent 通过此工具写YAML，字段名/类型/required/confidence 全部在写入前校验。
写错当场报错，不产生错误数据。

用法:
  # 1. 查看所有可用类型及字段数
  python3 yaml_writer.py list

  # 2. 生成骨架（Agent写YAML前置动作）
  python3 yaml_writer.py skeleton --type concept

  # 3. 写YAML文件（带全量校验）
  python3 yaml_writer.py write --type concept --yaml-path path/to/concepts.yaml \\
    --items '[{"name":"xxx","fm":{"source_chapter":"4","confidence":0.95},"bd":{"term_english":"","term_definition":"..."}}]'

  # 4. 验证已有YAML文件
  python3 yaml_writer.py validate --yaml-path path/to/concepts.yaml

  # 5. 批量验证整个data目录
  python3 yaml_writer.py validate-dir --dir .dag/第4章/data/

设计原则：
  - 不硬编码任何字段名，全部从 schema.json 动态读取
  - 领域无关、书籍无关
  - Agent 用此工具生成的数据 100% 符合schema定义
"""

import argparse
import json
import os
import sys
from typing import Any, Optional

try:
    import yaml as _yaml
except ImportError:
    _yaml = None

# ── 路径 ──
SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
SCHEMA_PATH = os.path.join(os.path.dirname(SKILL_DIR), "schemas", "domain_book_schema.json")


# ════════════════════════════════════════════════════════════
# Schema 加载
# ════════════════════════════════════════════════════════════

def load_schema() -> dict:
    """加载 domain_book_schema.json"""
    if not os.path.exists(SCHEMA_PATH):
        raise FileNotFoundError(f"schema 文件不存在: {SCHEMA_PATH}")
    with open(SCHEMA_PATH) as f:
        return json.load(f)


# ════════════════════════════════════════════════════════════
# Pydantic 模型（动态生成）
# ════════════════════════════════════════════════════════════

try:
    from pydantic import BaseModel, Field, field_validator, model_validator
    from pydantic import ValidationError as PydanticValidationError

    HAS_PYDANTIC = True
except ImportError:
    HAS_PYDANTIC = False
    BaseModel = object  # fallback


def _make_pydantic_models(type_name: str, schema: dict) -> tuple:
    """为指定节点类型动态生成 Pydantic 模型。

    Returns:
        (FrontMatterModel, BDModel, FullModel) 三元组
    """
    if not HAS_PYDANTIC:
        return None, None, None

    node_schema = schema['node_types'].get(type_name)
    if not node_schema:
        raise ValueError(f"未知节点类型: {type_name}")

    # ── FrontMatter 模型 ──
    fm_fields = {}
    for fm_name, fm_def in sorted(node_schema['frontmatter'].items()):
        field_type = str if fm_def['type'] == 'string' else (
            float if fm_def['type'] == 'number' else list
        )
        kwargs = {}
        if not fm_def.get('required', True):
            kwargs['default'] = None

        # confidence 特殊处理
        if fm_name == 'confidence':
            allowed = node_schema['confidence']['allowed']
            kwargs['default'] = node_schema['confidence']['default']
            kwargs['ge'] = 0.5
            kwargs['le'] = 1.0

        fm_fields[fm_name] = (Optional[field_type], Field(**kwargs)) if not fm_def.get('required', True) else (field_type, Field(**kwargs))

    FrontMatter = type('FrontMatter', (BaseModel,), {
        '__annotations__': {k: v[0] for k, v in fm_fields.items()},
        **{k: v[1] for k, v in fm_fields.items()},
    })

    # ── BD 模型 ──
    bd_fields = {}
    for bd_name, bd_def in sorted(node_schema['bd'].items()):
        field_type = str if bd_def['type'] in ('string', 'string|mermaid', 'mermaid') else (
            list if 'list' in bd_def['type'] else str
        )
        kwargs = {}
        if not bd_def.get('required', True):
            kwargs['default'] = None

        # min_chars 约束
        constraints = bd_def.get('constraints', {})
        if 'min_chars' in constraints:
            kwargs['min_length'] = constraints['min_chars']

        bd_fields[bd_name] = (Optional[field_type], Field(**kwargs)) if not bd_def.get('required', True) else (field_type, Field(**kwargs))

    BDModel = type('BDModel', (BaseModel,), {
        '__annotations__': {k: v[0] for k, v in bd_fields.items()},
        **{k: v[1] for k, v in bd_fields.items()},
    })

    # ── 完整模型 ──
    class FullYAML(BaseModel):
        name: str = Field(..., min_length=1)
        file: str = Field(..., min_length=1)
        fm: FrontMatter
        bd: BDModel

        @model_validator(mode='after')
        def check_confidence(self):
            allowed = node_schema['confidence']['allowed']
            if self.fm.confidence not in allowed:
                raise ValueError(f"confidence={self.fm.confidence} 不属于允许值 {allowed}（类型: {type_name}）")
            return self

    return FrontMatter, BDModel, FullYAML


# ════════════════════════════════════════════════════════════
# 校验函数（无 pydantic 时用模板字段遍历）
# ════════════════════════════════════════════════════════════

def _validate_item_basic(item: dict, type_name: str, schema: dict) -> list[str]:
    """基础校验（不使用 pydantic 时的降级方案）"""
    errors = []
    node_schema = schema['node_types'][type_name]

    # 检查 name
    if 'name' not in item or not item['name']:
        errors.append("缺少 name 字段")

    # 检查 fm
    fm = item.get('fm', {})
    for fm_name, fm_def in node_schema['frontmatter'].items():
        if fm_def.get('required', True) and fm_name not in fm:
            errors.append(f"fm 缺少必填字段: {fm_name}")

    # confidence 校验
    conf = fm.get('confidence')
    if conf is not None:
        allowed = node_schema['confidence']['allowed']
        if conf not in allowed:
            errors.append(f"confidence={conf} 不属于允许值 {allowed}")

    # 检查 bd 字段
    bd = item.get('bd', {})
    bd_schema = node_schema['bd']
    for bd_name, bd_def in bd_schema.items():
        if bd_def.get('required', True) and bd_name not in bd:
            errors.append(f"bd 缺少必填字段: {bd_name}")

    # 检查多余字段
    known_fm = set(node_schema['frontmatter'].keys())
    if fm:
        extra_fm = set(fm.keys()) - known_fm
        for ef in extra_fm:
            errors.append(f"fm 多余字段: {ef} (不在schema中)")

    bd_fields_schema = set(bd_schema.keys())
    if bd:
        extra_bd = set(bd.keys()) - bd_fields_schema
        for eb in extra_bd:
            errors.append(f"bd 多余字段: {eb} (不在schema中)")

    return errors


# ════════════════════════════════════════════════════════════
# CLI 命令
# ════════════════════════════════════════════════════════════

def cmd_list():
    """列出所有可用节点类型"""
    schema = load_schema()
    print(f"节点类型 ({len(schema['node_types'])} 个):")
    print(f"{'类型名':12s} {'模板':28s} {'confidence':18s} {'前部':6s} {'bd':6s}")
    print("-" * 75)
    for t, n in sorted(schema['node_types'].items()):
        conf = str(n['confidence']['allowed'])
        print(f"{t:12s} {n['template']:28s} {conf:18s} {len(n['frontmatter']):>4d}  {len(n['bd']):>4d}")


def cmd_skeleton(type_name: str):
    """生成YAML骨架（不带值的字段名模板）"""
    schema = load_schema()
    if type_name not in schema['node_types']:
        print(f"❌ 未知节点类型: {type_name}")
        print(f"   可用类型: {', '.join(sorted(schema['node_types'].keys()))}")
        return

    node = schema['node_types'][type_name]
    conf_allowed = node['confidence']['allowed']
    conf_default = node['confidence']['default']

    print(f"# {type_name} YAML 骨架 (yaml_writer v2)")
    print(f"# 模板: {node['template']}")
    print(f"# confidence: {conf_allowed} (默认 {conf_default})")
    print(f"# bd字段: {len(node['bd'])} 个")
    print()

    print(f"- name: 示例名称")
    print(f"  file: 示例名称")
    print(f"  fm:")
    for fm_name, fm_def in sorted(node['frontmatter'].items()):
        if fm_name == 'confidence':
            print(f"    confidence: {conf_default}")
        elif fm_def.get('auto_fill'):
            print(f"    #{fm_name}: （自动填充）")
        else:
            placeholder = "" if fm_def.get('required', True) else ""
            print(f"    {fm_name}: {placeholder}")
    print(f"  bd:")
    for bd_name, bd_def in sorted(node['bd'].items()):
        placeholder = "''" if bd_def['type'] == 'string' else '[]'
        if not bd_def.get('required', True):
            print(f"    {bd_name}: 无  # optional")
        else:
            constraints = bd_def.get('constraints', {})
            note = ""
            if 'min_chars' in constraints:
                note = f"  # ≥{constraints['min_chars']}字"
            if constraints.get('formula_check'):
                note += "  # 用$$包裹公式" if note else "  # 用$$包裹公式"
            print(f"    {bd_name}: {placeholder}{note}")


def cmd_write(type_name: str, yaml_path: str, items_json: str):
    """校验并写入YAML文件"""
    schema = load_schema()
    if type_name not in schema['node_types']:
        print(f"❌ 未知节点类型: {type_name}")
        sys.exit(1)

    try:
        items = json.loads(items_json)
    except json.JSONDecodeError as e:
        print(f"❌ items JSON 解析失败: {e}")
        sys.exit(1)

    if not isinstance(items, list):
        print(f"❌ items 必须是 JSON 数组")
        sys.exit(1)

    # 校验每个 item
    all_errors = []
    for idx, item in enumerate(items):
        if HAS_PYDANTIC:
            _, _, FullYAML = _make_pydantic_models(type_name, schema)
            try:
                FullYAML(**item)
            except PydanticValidationError as e:
                for err in e.errors():
                    loc = " -> ".join(str(l) for l in err['loc'])
                    all_errors.append(f"第{idx+1}项 [{loc}]: {err['msg']}")
        else:
            errors = _validate_item_basic(item, type_name, schema)
            for err in errors:
                all_errors.append(f"第{idx+1}项: {err}")

    if all_errors:
        print(f"❌ 发现 {len(all_errors)} 个错误，YAML 未写入:")
        for e in all_errors:
            print(f"  • {e}")
        sys.exit(1)

    # 写入
    os.makedirs(os.path.dirname(yaml_path), exist_ok=True)
    with open(yaml_path, 'w', encoding='utf-8') as f:
        if _yaml:
            _yaml.dump(items, f, allow_unicode=True, default_flow_style=False, sort_keys=False, width=4096)
        else:
            # fallback: write as JSON (YAML is better but JSON is valid YAML subset)
            json.dump(items, f, ensure_ascii=False, indent=2)

    print(f"✅ 已写入 {len(items)} 项 → {yaml_path}")


def cmd_validate(type_name: str, yaml_path: str):
    """校验已有YAML文件""" if False else None

# 重新实现 validate
def cmd_validate_file(yaml_path: str, explicit_type: str = None):
    """校验已有YAML文件"""
    schema = load_schema()

    # 自动识别类型
    if explicit_type:
        type_name = explicit_type
    else:
        fname = os.path.basename(yaml_path).replace('.yaml', '').replace('.yml', '')
        type_map = {
            'concepts': 'concept',
            'kes': 'ke',
            'entities': 'entity',
            'kps': 'kp',
            'sps': 'sp',
            'scenes': 'scene',
            'exercises': 'exercise',
            'solutions': 'solution',
        }
        type_name = type_map.get(fname)
    if not type_name:
        print(f"❌ 无法自动识别类型，文件名 {fname} 不在映射中: concept/ke/entity/kp/sp/scene/exercise/solution")
        return

    if not os.path.exists(yaml_path):
        print(f"❌ 文件不存在: {yaml_path}")
        return

    with open(yaml_path) as f:
        if _yaml:
            items = _yaml.safe_load(f)
        else:
            items = json.load(f)

    if not isinstance(items, list):
        print(f"❌ 格式错误: 期望 YAML list，得到 {type(items).__name__}")
        return

    all_errors = []
    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            all_errors.append(f"第{idx+1}项: 不是字典")
            continue
        errors = _validate_item_basic(item, type_name, schema)
        for err in errors:
            all_errors.append(f"第{idx+1}项 [{item.get('name','?')}]: {err}")

    if all_errors:
        print(f"❌ {yaml_path}: {len(all_errors)} 个错误:")
        for e in all_errors:
            print(f"  • {e}")
    else:
        print(f"✅ {yaml_path}: {len(items)} 项，全部通过")


def cmd_self_instruct(type_name: str, chapter_num: str, book_dir: str = None):
    """为Agent生成字段工作台：源文片段 + @prompt规格 + schema约束，按字段并排展示"""
    import re as _re
    schema = load_schema()
    SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    if type_name not in schema['node_types']:
        print(f"❌ 未知节点类型: {type_name}")
        return

    node = schema['node_types'][type_name]
    tpl_path = os.path.join(SKILL_DIR, 'assets', 'templates', node['template'])
    if not os.path.exists(tpl_path):
        print(f"❌ 模板文件不存在: {tpl_path}")
        return

    with open(tpl_path, encoding='utf-8') as f:
        tpl_content = f.read()

    # 1. 提取 @prompt
    prompts = {}
    for m in _re.finditer(
        r'<!--\s*@prompt\s+(.*?)-->[\s\S]{0,200}?\{\{(\w+)\}\}',
        tpl_content
    ):
        prompts[m.group(2)] = m.group(1).strip()

    # 2. 加载源文，解析为按标题分段的字典
    source_sections = {}  # {heading_text: content_text}
    source_formulas = []  # [(line_num, formula)]
    if book_dir and chapter_num:
        raw = _load_source_section(book_dir, chapter_num)
        if raw:
            source_sections = _parse_source_sections(raw)
            source_formulas = _extract_formulas(raw)

    # 3. 收集 schema 约束 + 匹配源文
    bd_schema = node['bd']
    required_count = sum(1 for d in bd_schema.values() if d.get('required', True))
    optional_count = sum(1 for d in bd_schema.values() if not d.get('required', True))

    field_entries = []
    bd_fields_sorted = sorted(bd_schema.items())

    for bd_name, bd_def in bd_fields_sorted:
        required = bd_def.get('required', True)
        ftype = bd_def.get('type', 'string')
        cons = bd_def.get('constraints', {})
        constraints_parts = []
        if 'min_chars' in cons:
            constraints_parts.append(f"≥{cons['min_chars']}字")
        if cons.get('formula_check'):
            constraints_parts.append('公式需$$包裹(formula_check)')
        if 'max_chars' in cons:
            constraints_parts.append(f"≤{cons['max_chars']}字")

        # 找模板节标题
        section_title = _find_section_title(tpl_content, bd_name)

        # 匹配源文片段
        matched_snippets = _match_field_to_source(bd_name, section_title, source_sections, prompts.get(bd_name, ''))

        # 公式检测
        formula_hint = ''
        if bd_name == 'mathematical_model' and source_formulas:
            formula_hint = f"\n  源文检测到 {len(source_formulas)} 个公式，以下可用:"
            for ln, fm in source_formulas[:3]:
                fm_short = fm[:80] + ('...' if len(fm) > 80 else '')
                formula_hint += f"\n    L{ln}: {fm_short}"

        field_entries.append({
            'name': bd_name,
            'required': required,
            'type': ftype,
            'constraints': '，'.join(constraints_parts) if constraints_parts else '无',
            'prompt': prompts.get(bd_name, ''),
            'section_title': section_title,
            'snippets': matched_snippets,
            'formula_hint': formula_hint,
        })

    # 4. 输出
    lines = []
    lines.append("# ════════════════════════════════════════════════")
    lines.append(f"# 📋 {type_name} 字段工作台")
    lines.append(f"# 模板: {node['template']} → 输出: {_output_dir(type_name)}")
    lines.append(f"# 字段总量: {len(bd_schema)} (必填 {required_count} + 可选 {optional_count})")
    lines.append(f"# 置信度: {node['confidence']['allowed']}")
    lines.append(f"# 章节: 第{chapter_num}章")
    lines.append("# ════════════════════════════════════════════════")

    # 源文结构总览
    if source_sections:
        lines.append("")
        lines.append("## 一、源文章节结构")
        for h, text in source_sections.items():
            text_preview = text[:80].replace('\n', ' ').strip()
            lines.append(f"  {h}")
            lines.append(f"    {text_preview}...")
        if source_formulas:
            lines.append(f"\n  源文公式: {len(source_formulas)} 个")
            for ln, fm in source_formulas[:5]:
                fm_short = fm[:60] + ('...' if len(fm) > 60 else '')
                lines.append(f"    L{ln}: {fm_short}")

    # 字段工作台
    lines.append("")
    lines.append("## 二、字段工作台")
    lines.append("")

    idx = 0
    for fe in field_entries:
        idx += 1
        required_mark = '🔴' if fe['required'] else '🟡'
        required_label = '必填' if fe['required'] else '可选'
        lines.append(f"{'─'*60}")
        lines.append(f"{required_mark} {idx}/{len(bd_schema)} {fe['name']} [{required_label}/{fe['type']}]")
        lines.append(f"    模板位置: {fe['section_title']}")

        if fe['constraints'] and fe['constraints'] != '无':
            lines.append(f"    schema约束: {fe['constraints']}")

        if fe['prompt']:
            lines.append(f"    @prompt: {fe['prompt']}")
        else:
            lines.append(f"    @prompt: （无特殊要求，按字段名含义自然书写）")

        if fe['snippets']:
            for sn in fe['snippets'][:2]:  # max 2 snippets
                lines.append(f"    源文: 「{sn}」")

        if fe['formula_hint']:
            lines.append(f"    {fe['formula_hint']}")

        lines.append("")

    # 总结与提醒
    lines.append(f"{'='*60}")
    lines.append(f"📊 共 {len(bd_schema)} 个 bd 字段需要填写")
    lines.append(f"   必填 {required_count} 个 — 必须逐字段填写，不可跳过")
    lines.append(f"   可选 {optional_count} 个 — 有实际内容就写，否则填「无」")
    lines.append("")
    lines.append("⚠️ 重要提醒:")
    lines.append(f"  - confidence 必须 ∈ {node['confidence']['allowed']}")
    lines.append("  - 字段名必须与上面列出的完全一致，不可自创")
    lines.append("  - 所有字段放在 bd: {} 下，非顶层")
    lines.append("  - core_concept_map 写 raw graph TD 内容即可（引擎自动加 fence）")
    lines.append("  - 列表字段用 YAML 列表格式 `[item1, item2]`")
    lines.append(f"  - 完成写入后用 yaml_writer.py validate 确认")
    lines.append(f"{'='*60}")

    print('\n'.join(lines))


def _parse_source_sections(raw_text: str) -> dict:
    """将源文按 ##/### 标题解析为 {标题: 内容} 字典"""
    import re as _re
    sections = {}
    lines = raw_text.split('\n')
    current_heading = None
    current_content = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith('## ') or stripped.startswith('### '):
            if current_heading:
                sections[current_heading] = '\n'.join(current_content).strip()
            current_heading = stripped
            current_content = []
        elif current_heading:
            current_content.append(line)
    if current_heading:
        sections[current_heading] = '\n'.join(current_content).strip()

    return sections


def _extract_formulas(raw_text: str) -> list:
    """从源文提取所有 $$..$$ 公式，返回 [(行号, 公式文本)]"""
    import re as _re
    formulas = []
    lines = raw_text.split('\n')
    in_formula = False
    formula_lines = []
    for i, line in enumerate(lines, 1):
        if '$$' in line:
            if in_formula:
                formula_lines.append(line.replace('$$', '').strip())
                formulas.append((i - len(formula_lines) + 1, '\n'.join(formula_lines).strip()))
                formula_lines = []
                in_formula = False
            else:
                in_formula = True
                remainder = line.replace('$$', '').strip()
                if remainder:
                    formula_lines.append(remainder)
        elif in_formula:
            formula_lines.append(line.strip())
    return formulas


# 模板节标题 → 源文查询关键词映射
_TEMPLATE_SECTION_KEYWORDS = {
    '术语定义': ['术语', '定义', '定义', '概念', '含义', '是指'],
    '精确释义': ['是指', '定义', '含义', '释义'],
    '核心概念图谱': ['图', '结构', '概念', '关系'],
    '图谱解析': ['图', '所示', '如下'],
    '数学模型': ['公式', '方程', '$$', '式', '模型', 'Maxwell', '麦克斯韦'],
    '工作原理': ['原理', '构成', '要素', '组成', '结构', '包括'],
    '关键参数': ['参数', '指标', '系数', '电平', '限值', 'dB'],
    '物理含义特征': ['特征', '特性', '含义', '特点', '性质'],
    '学习目标': ['学习', '目标', '掌握', '了解'],
    '前置知识': ['基础', '前提', '先修', '预备'],
    '解决的问题': ['解决', '问题', '目的', '作用'],
    '应用场景': ['应用', '场景', '案例', '工程', '领域'],
    '典型系统': ['系统', '设备', '仪器', '工具', '软件'],
    '使用价值': ['价值', '重要', '意义', '作用', '关键'],
    '工程实践': ['工程', '实践', '应用', '测量', '测试'],
    '常见误区': ['误区', '误解', '注意', '不要', '避免'],
    '技术分类': ['分类', '类型', '分为', '种'],
    '与相关概念的关系': ['关系', '关联', '联系', '相关', '区别'],
    '相近概念辨析': ['区别', '辨析', ' vs ', '对比', '比较', '不同'],
    '发展演进': ['发展', '历史', '演进', '演变', '阶段', '最早'],
    '关联知识要素': ['知识', '要素', '相关'],
    '上下游关系': ['上游', '下游', '输入', '输出', '前后'],
    '自学检验': ['自测', '问题', '思考', '检验', '题'],
}

# 字段名 → 关键词的逆向映射（由 section_title 映射而来）
_FIELD_KEYWORDS = {
    'term_definition': ['定义', '术语', '是指', '称为'],
    'term_english': [],
    'definition_sentence': ['是指', '定义为'],
    'mathematical_model': ['公式', '方程', '$$', '模型'],
    'structure': ['构成', '组成', '要素', '步骤', '流程', '①', '②', '③'],
    'key_parameters': ['参数', '指标', 'dB', '电平', '限值'],
    'features': ['特征', '特点', '特性', '包括', '可分为'],
    'solved_problem': ['解决', '问题', '困难', '复杂', '效率'],
    'application_scenarios': ['应用', '场景', '领域', '工程'],
    'engineering_practices': ['工程', '实践', '实际', '建议', '注意', '应该'],
    'common_misconceptions': ['误区', '误解', '注意', '不要', '避免'],
    'evolution': ['发展', '历史', '最早', '提出', '阶段', '演进'],
    'prerequisite_knowledge': ['基础', '先修', '前提', '需要', '掌握'],
    'learning_objectives': ['掌握', '理解', '了解', '学习', '目标'],
    'self_check_questions': ['问题', '思考', '自测', '检验'],
    'related_concepts_relations': ['关系', '关联', '概念', '联系'],
    'confusion_compare': ['区别', '比较', '不同', '对比'],
    'value': ['价值', '重要', '意义', '关键'],
    'typical_systems': ['系统', '工具', '软件', '仪器'],
    'upstream_downstream': [],
    'core_concept_map': ['图', '结构', '概念', '关系'],
    'core_concept_map_analysis': [],
    'tech_classification': ['分类', '分为', '类型'],
    'domain': [],
    'classification': ['分类'],
    'related_knowledge_elements': [],
    'aliases': [],
    'tags': [],
}

# 补充：从字段名到关键词的通用规则
for field_name in list(_FIELD_KEYWORDS.keys()):
    if not _FIELD_KEYWORDS[field_name]:
        # 从字段名拆分: "related_concepts_relations" → ["related", "concepts", "relations"]
        parts = field_name.split('_')
        _FIELD_KEYWORDS[field_name] = parts


# ── 语义级源文匹配引擎 ──

# 信号词：指示特定类型内容的标记词（EMC领域全覆盖）
# 每条信号词都可能出现在@prompt或源文中，用于句子的多维评分
_SIGNAL_WORDS = {
    'definition': [
        '是指', '定义为', '称为', '定义为', '表示', '指',
        '是…的', '所谓', '即', '指的是', '指的是',
        '定义', '概念', '含义', '术语', '释义',
        '就是', '就是指', '表示的是',
    ],
    'formula': [
        '$$', '公式', '方程', '等式', '表达式',
        '关系式', '本构关系', '边界条件', '麦克斯韦',
        'Maxwell', '旋度', '散度', '梯度',
        '微分', '积分', '差分', '代数',
        'FDTD', 'MoM', 'FEM', 'TLM', '数值分析',
    ],
    'number': [
        # 单位
        'dB', 'dBm', 'dBuV', 'dBuV/m', 'dBA', 'dBμV',
        'Hz', 'kHz', 'MHz', 'GHz', 'THz',
        'V', 'mV', 'μV', 'kV',
        'A', 'mA', 'μA', 'kA',
        'W', 'mW', 'μW', 'kW',
        'Ω', 'mΩ', 'μΩ', 'kΩ',
        'F', 'pF', 'nF', 'μF',
        'H', 'nH', 'μH', 'mH',
        'm', 'mm', 'cm', 'μm', 'nm',
        's', 'ms', 'μs', 'ns', 'ps',
        'V/m', 'A/m', 'T', 'mT', 'μT',
        'Np', '°',
        # 参数名
        '频率', '功率', '电压', '电流', '阻抗',
        '场强', '功率密度', '灵敏度', '限值',
        '裕量', '电平', '幅度', '波长',
        '步长', '网格', '分辨率',
        # 数值模式
        '\\d+',  # 任意数字 — 在代码中特殊处理
    ],
    'example': [
        '例如', '如', '案例', '实例', '示例',
        '如图', '如表', '如下', '见图',
        '例如说', '举例', '举个例子',
        '某', '以一个', '下面以',
        '案例一', '案例二', '应用案例',
        '实测', '试验', '测试案例',
        '表13-', '图12-', '式12-',  # 图表引用
        '场景', '应用背景', '实际工程',
    ],
    'structure': [
        '①', '②', '③', '④', '⑤',
        '步骤', '流程', '阶段', '要素',
        '首先', '其次', '然后', '最后',
        '第一步', '第二步', '第三步',
        'Step1', 'Step2', '步骤1',
        '包括', '包含', '由…组成', '分为',
        '构成', '组成', '结构',
        '系统组成', '系统构成', '组成部分',
    ],
    'negation': [
        '不要', '避免', '注意', '误区', '错误',
        '不能', '不得', '不可', '不应该',
        '注意', '需要注意的是', '值得关注',
        '误区', '常见误解', '容易混淆',
        '不能认为', '不能简单', '并非',
        '区别', '不同', '差异', 'vs', '对比',
        '容易', '可能引起', '风险',
        '困难', '复杂度', '挑战',
        '但是', '然而', '不过', '需要注意的是',
    ],
    'evolution': [
        '最早', '提出', '20世纪', '发展', 
        '199', '200', '196', '197', '198',  # 年份
        '自', '以来', '历经', '阶段',
        '历史', '演进', '演变', '过程',
        '传统', '早期', '以前', '最初',
        '近年来', '当前', '目前', '当今',
        '趋势', '方向', '前景',
        '未来', '下一步', '发展方向',
    ],
    'application': [
        '应用', '场景', '实际', '工程',
        '产品', '系统', '设计', '开发',
        '测试', '诊断', '整改',
        '解决', '实现', '完成',
        '应用于', '适用于', '可用于',
        '在…中', '在…方面',
        '车载', '机载', '舰载', '星载',
        '通信', '雷达', '天线', 'PCB',
        '工业', '医疗', '汽车', '航空航天',
    ],
    'cause_effect': [
        '因为', '所以', '因此', '从而',
        '导致', '引起', '造成', '产生',
        '由于', '源于', '基于',
        '目的', '目标', '为了',
        '作用', '功能', '用途',
        '原因', '根源', '机理',
        '结果', '后果', '效果',
        '提高', '降低', '增强', '抑制',
    ],
}

# 字段 → 内容特征描述（自动匹配信号词的配置）
_FIELD_SIGNAL_PROFILES = {
    'term_definition':  {'primary': 'definition', 'secondary': '', 'min_chars': 30},
    'definition_sentence': {'primary': 'definition', 'secondary': '', 'min_chars': 30},
    'mathematical_model': {'primary': 'formula', 'secondary': '', 'min_chars': 20, 'require_num': True},
    'structure': {'primary': 'structure', 'secondary': 'definition', 'min_chars': 40},
    'key_parameters': {'primary': 'number', 'secondary': '', 'min_chars': 20, 'require_num': True},
    'features': {'primary': 'definition', 'secondary': 'structure', 'min_chars': 20},
    'solved_problem': {'primary': 'cause_effect', 'secondary': 'definition', 'min_chars': 30},
    'application_scenarios': {'primary': 'application', 'secondary': 'example', 'min_chars': 30},
    'engineering_practices': {'primary': 'number', 'secondary': 'example', 'min_chars': 30, 'require_num': True},
    'common_misconceptions': {'primary': 'negation', 'secondary': 'cause_effect', 'min_chars': 20},
    'evolution': {'primary': 'evolution', 'secondary': '', 'min_chars': 30},
    'prerequisite_knowledge': {'primary': 'definition', 'secondary': '', 'min_chars': 20},
    'learning_objectives': {'primary': 'definition', 'secondary': '', 'min_chars': 10},
    'self_check_questions': {'primary': 'definition', 'secondary': '', 'min_chars': 10},
    'related_concepts_relations': {'primary': 'definition', 'secondary': 'cause_effect', 'min_chars': 20},
    'confusion_compare': {'primary': 'negation', 'secondary': 'definition', 'min_chars': 20},
    'value': {'primary': 'cause_effect', 'secondary': 'definition', 'min_chars': 30},
    'typical_systems': {'primary': 'application', 'secondary': '', 'min_chars': 20},
    'core_concept_map': {'primary': 'definition', 'secondary': '', 'min_chars': 10},
    'core_concept_map_analysis': {'primary': 'definition', 'secondary': 'structure', 'min_chars': 20},
    'upstream_downstream': {'primary': 'cause_effect', 'secondary': '', 'min_chars': 20},
}


def _get_prompt_query(prompt_text: str) -> list:
    """从 @prompt 提取关键查询词"""
    import re as _re
    if not prompt_text:
        return []
    # 提取中英文关键词（2字以上中文词，或字母数字词）
    words = []
    # 中文: 2字以上片段
    cn_matches = _re.findall(r'[\u4e00-\u9fff]{2,}', prompt_text)
    words.extend(cn_matches)
    # 英文/数字: 字母数字组合
    en_matches = _re.findall(r'[a-zA-Z][a-zA-Z0-9]{1,}', prompt_text)
    words.extend(en_matches)
    # 去停用词
    stop_words = ['可以', '这个', '不是', '没有', '一个', '用于', '必须', '需要',
                  '应该', '能够', '可能', '已经', '这些', '所有', '不得', '或', '的',
                  '了', '在', '是', '和', '与', '及', '等', '从', '对', '以', '其',
                  'the', 'is', 'and', 'or', 'of', 'to', 'in', 'for', 'with', 'that',
                  'from']
    return [w for w in words if w.lower() not in stop_words and len(w) >= 2]


def _split_sentences(text: str) -> list:
    """将文本拆分为句子列表，每句保留位置信息"""
    import re as _re
    if not text:
        return []
    # 按句号、问号、感叹号、换行后的数字序号拆分
    parts = _re.split(r'(?<=[。！？；；\n])\s*', text)
    sentences = []
    for p in parts:
        p = p.strip()
        if len(p) >= 10:  # 至少10字才认为是一句
            sentences.append(p)
    return sentences


def _score_sentence(sentence: str, keywords: list, bd_name: str, prompt_text: str) -> float:
    """对句子进行多维评分"""
    import re as _re
    score = 0.0

    # 1. 关键词匹配（基础分）
    lower_sent = sentence.lower()
    matched = sum(1 for kw in keywords if kw.lower() in lower_sent)
    score += matched * 1.0
    # 2. 精确匹配加分（整词匹配）
    exact_matched = sum(1 for kw in keywords if len(kw) >= 3 and kw in sentence)
    score += exact_matched * 0.5

    # 3. 信号词匹配（主+次信号）
    profile = _FIELD_SIGNAL_PROFILES.get(bd_name, {})
    primary_signal = profile.get('primary', 'definition')
    secondary_signal = profile.get('secondary', '')

    # 主信号
    signal_words = _SIGNAL_WORDS.get(primary_signal, [])
    signal_hits = sum(1 for sw in signal_words if sw in sentence)
    score += signal_hits * 1.5

    # 次信号（权重减半）
    if secondary_signal:
        sec_words = _SIGNAL_WORDS.get(secondary_signal, [])
        sec_hits = sum(1 for sw in sec_words if sw in sentence)
        score += sec_hits * 0.75

    # 4. 数字密度加分（如果字段需要数值内容）
    if profile.get('require_num'):
        numbers = _re.findall(r'\d+[\.\d]*', sentence)
        num_hits = len(numbers)
        score += num_hits * 0.3
        # 检测单位词
        units = _SIGNAL_WORDS.get('number', [])
        unit_hits = sum(1 for u in units if u in sentence)
        score += unit_hits * 1.0

    # 5. 公式检测特殊加分
    if bd_name == 'mathematical_model' or bd_name == 'mathematical_model':
        if '$$' in sentence:
            score += 5.0  # 公式包含加分极高

    # 6. 长度惩罚：太短（<20字）的句子信息量不够
    if len(sentence) < 20:
        score -= 2.0
    # 太长（>500字）的句子主题可能发散
    if len(sentence) > 500:
        score -= 1.0

    return max(score, 0.0)


def _match_field_to_source(bd_name: str, section_title: str,
                           source_sections: dict, prompt_text: str = '') -> list:
    """语义级源文匹配：从 @prompt + 字段名 + 信号词 综合评分，返回最相关句子"""
    if not source_sections:
        return []

    # 1. 构建查询：字段名关键词 + @prompt 关键词 + 模板节标题关键词
    query_terms = set()

    # 字段名分拆
    for part in bd_name.split('_'):
        if len(part) >= 2:
            query_terms.add(part)

    # 模板节标题 - 提取中文词
    import re as _re
    cn_terms = _re.findall(r'[\u4e00-\u9fff]{2,}', section_title)
    query_terms.update(cn_terms)

    # @prompt 关键词
    if prompt_text:
        prompt_terms = _get_prompt_query(prompt_text)
        query_terms.update(prompt_terms)

    # 2. 按句子评分
    scored = []  # [(score, heading, snippet)]
    used_sentences = set()

    for heading, content in source_sections.items():
        sentences = _split_sentences(content)
        for sent in sentences:
            # 去重
            sent_key = sent[:50]
            if sent_key in used_sentences:
                continue
            used_sentences.add(sent_key)

            score = _score_sentence(sent, list(query_terms), bd_name, prompt_text)
            if score > 0:
                # 短片段优先（精确度更高）
                snippet = sent[:300].replace('\n', ' ').strip()
                scored.append((score, heading, snippet))

    # 3. 字段 especial：mathematical_model 的公式兜底
    if bd_name == 'mathematical_model' or bd_name == 'mathematical_model':
        for heading, content in source_sections.items():
            if '$$' in content:
                # 提取公式附近文本
                for line in content.split('\n'):
                    if '$$' in line or any(kw in line for kw in ['公式', '方程', '模型', 'Maxwell']):
                        snippet = line[:200].replace('\n', ' ').strip()
                        if len(snippet) > 10:
                            score = 10.0  # 公式行高优先级
                            scored.append((score, heading, snippet))

    # 4. 排序去重取前2
    scored.sort(key=lambda x: -x[0])

    result = []
    seen_headings = set()
    for score, heading, snippet in scored:
        result.append(f"[{heading}] {snippet}")
        seen_headings.add(heading)
        if len(result) >= 2:
            break

    # 如果前2来自同一个大节（同一主标题），优先展示不同大节的内容
    if len(result) == 2:
        h1 = result[0].split(']')[0].strip('[').split(' ')[0]  # 主节号
        h2 = result[1].split(']')[0].strip('[').split(' ')[0]
        if h1 == h2 and len(scored) > 2:
            # 找不同主节的结果
            for score, heading, snippet in scored[2:]:
                h3 = heading.split(' ')[0]
                if h3 != h1:
                    result[1] = f"[{heading}] {snippet}"
                    break

    # 5. 如果仍无结果，降级到关键词匹配
    if not result:
        for heading, content in source_sections.items():
            for kw in query_terms:
                if len(kw) >= 3 and kw in heading:
                    snippet = content[:200].replace('\n', ' ').strip()
                    result.append(f"[{heading}] {snippet}")
                    break
            if len(result) >= 2:
                break

    return result[:2]


def _find_section_title(tpl_content: str, field_name: str) -> str:
    """查找模板中某字段所在章节标题"""
    import re as _re
    # Find the {{field_name}} and look backward for nearest ### title
    idx = tpl_content.find('{{' + field_name + '}}')
    if idx == -1:
        return field_name
    before = tpl_content[:idx]
    titles = _re.findall(r'#{2,4}\s+(.+?)\n', before)
    return titles[-1] if titles else field_name


def _output_dir(type_name: str) -> str:
    """返回该类型的输出目录名"""
    dir_map = {
        'concept': '30_核心概念',
        'ke': '40_知识要素',
        'entity': '80_实体',
        'kp': '50_知识点',
        'sp': '60_技能点',
        'scene': '70_应用场景',
        'exercise': '90_习题',
        'solution': '90_习题/解答',
    }
    return dir_map.get(type_name, '?')


def _load_source_section(book_dir: str, chapter_num: str) -> str:
    """从20_正文加载章节源文片段"""
    import glob as _glob
    src_dir = os.path.join(book_dir, '20_正文')
    if not os.path.isdir(src_dir):
        return ''
    files = sorted(_glob.glob(os.path.join(src_dir, f'第{chapter_num}章*.md')))
    if not files:
        return ''
    try:
        with open(files[0], encoding='utf-8') as f:
            content = f.read()
        # Strip YAML frontmatter
        import re as _re
        content = _re.sub(r'^---\n.*?\n---\n', '', content, flags=_re.DOTALL)
        return content.strip()
    except Exception:
        return ''
def cmd_validate_dir(data_dir: str):
    """批量校验目录下所有YAML文件"""
    if not os.path.isdir(data_dir):
        print(f"❌ 目录不存在: {data_dir}")
        return

    yaml_files = sorted(f for f in os.listdir(data_dir) if f.endswith(('.yaml', '.yml')))
    if not yaml_files:
        print(f"📂 空目录: {data_dir}")
        return

    total_errors = 0
    for yf in yaml_files:
        yp = os.path.join(data_dir, yf)
        print(f"\n── {yf} ──")
        
        # Capture output from cmd_validate_file
        import io
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            cmd_validate_file(yp)
        finally:
            output = sys.stdout.getvalue()
            sys.stdout = old_stdout
        
        print(output, end='')
        if '❌' in output:
            total_errors += 1

    print(f"\n{'='*50}")
    if total_errors == 0:
        print(f"✅ 全部通过: {len(yaml_files)} 个文件")
    else:
        print(f"❌ {total_errors}/{len(yaml_files)} 个文件有错误")


# ════════════════════════════════════════════════════════════
# cmd_prompt: 从模板提取 @prompt 写作指导
# ════════════════════════════════════════════════════════════

def cmd_prompt(type_name: str, field_name: str = None):
    """从模板文件提取 @prompt 写作指导"""
    import re as _re
    schema = load_schema()
    SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    if type_name not in schema['node_types']:
        print(f"❌ 未知节点类型: {type_name}")
        return

    node = schema['node_types'][type_name]
    tpl_path = os.path.join(SKILL_DIR, 'assets', 'templates', node['template'])
    if not os.path.exists(tpl_path):
        print(f"❌ 模板文件不存在: {tpl_path}")
        return

    with open(tpl_path, encoding='utf-8') as f:
        content = f.read()

    # Extract <!-- @prompt ... --> comments near {{field}} (within 200 chars)
    prompts = {}
    for m in _re.finditer(
        r'<!--\s*@prompt\s+(.*?)-->[\s\S]{0,200}?\{\{(\w+)\}\}',
        content
    ):
        prompts[m.group(2)] = m.group(1).strip()

    if field_name:
        if field_name in prompts:
            print(f"\n{'='*60}")
            print(f"📝 {type_name}.{field_name}")
            print(f"{'='*60}\n")
            print(prompts[field_name])
        else:
            print(f"❌ 字段 '{field_name}' 无 @prompt 指导")
        return

    # Print all fields
    print(f"\n{'='*60}")
    print(f"📋 {type_name.upper()} 字段写作指导（模板: {node['template']}）")
    print(f"{'='*60}")
    for fname in sorted(node['bd'].keys()):
        bd_def = node['bd'][fname]
        required = '必填' if bd_def.get('required') else '可选'
        ftype = bd_def.get('type', 'string')
        auto = '  [自动填充]' if bd_def.get('auto_fill') else ''
        if fname in prompts:
            print(f"\n{'─'*50}")
            print(f"📌 {fname} [{required}/{ftype}]{auto}")
            print(prompts[fname])
        else:
            cons = ''
            c = bd_def.get('constraints', {})
            if 'min_chars' in c:
                cons += f' ≥{c["min_chars"]}字'
            if c.get('formula_check'):
                cons += ' 公式需$$包裹'
            print(f"\n  ⚠️ {fname} [{required}/{ftype}]{auto}{cons}")


# ════════════════════════════════════════════════════════════
# Main
# ════════════════════════════════════════════════════════════

def main():
    p = argparse.ArgumentParser(description="yaml_writer v2 — Agent写YAML的pydantic工具")
    sp = p.add_subparsers(dest="cmd")

    # list
    sp.add_parser("list", help="列出所有节点类型")

    # skeleton
    sk = sp.add_parser("skeleton", help="生成YAML骨架")
    sk.add_argument("--type", required=True, help="节点类型")

    # write
    wr = sp.add_parser("write", help="写YAML文件（带全量校验）")
    wr.add_argument("--type", required=True, help="节点类型")
    wr.add_argument("--yaml-path", required=True, help="输出YAML文件路径")
    wr.add_argument("--items", required=True, help="JSON 数组")

    # validate
    vl = sp.add_parser("validate", help="校验单个YAML文件")
    vl.add_argument("--yaml-path", required=True, help="YAML文件路径")
    vl.add_argument("--type", dest="explicit_type", default=None, help="节点类型（不指定时从文件名自动识别）")

    # validate-dir
    vd = sp.add_parser("validate-dir", help="批量校验整个目录")
    vd.add_argument("--dir", required=True, help="YAML目录路径")

    # prompt
    pr = sp.add_parser("prompt", help="从模板提取@prompt字段写作指导")
    pr.add_argument("--type", required=True, help="节点类型（如 concept/kp/sp 等）")
    pr.add_argument("--field", default=None, help="字段名（可选，不指定时输出全部）")

    # self-instruct
    si = sp.add_parser("self-instruct", help="生成Agent自指导提示词: @prompt + schema约束 + 源文上下文")
    si.add_argument("--type", required=True, help="节点类型")
    si.add_argument("-c", "--chapter", required=True, help="章号")
    si.add_argument("--book-dir", default=None, help="知识库书籍目录（可选，提供后自动加载源文上下文）")

    a = p.parse_args()

    if not a.cmd:
        p.print_help()
        return

    if a.cmd == "list":
        cmd_list()
    elif a.cmd == "skeleton":
        cmd_skeleton(a.type)
    elif a.cmd == "write":
        cmd_write(a.type, a.yaml_path, a.items)
    elif a.cmd == "validate":
        cmd_validate_file(a.yaml_path, getattr(a, 'explicit_type', None))
    elif a.cmd == "validate-dir":
        cmd_validate_dir(a.dir)

    elif a.cmd == "prompt":
        cmd_prompt(a.type, getattr(a, 'field', None))

    elif a.cmd == "self-instruct":
        cmd_self_instruct(a.type, a.chapter, getattr(a, 'book_dir', None))


if __name__ == "__main__":
    main()
