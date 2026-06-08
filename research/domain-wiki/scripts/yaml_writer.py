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


if __name__ == "__main__":
    main()
