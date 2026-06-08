"""yaml_schema.py — Schema加载 + Pydantic模型 + 校验函数

从 domain_book_schema.json 动态生成 Pydantic 模型。领域无关。
供 yaml_writer.py 的 write/validate 命令使用。
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any, Optional

try:
    import yaml as _yaml
except ImportError:
    _yaml = None

try:
    from pydantic import BaseModel, Field, model_validator
    from pydantic import ValidationError as PydanticValidationError
    HAS_PYDANTIC = True
except ImportError:
    HAS_PYDANTIC = False
    BaseModel = object

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SCHEMA_PATH = os.path.join(os.path.dirname(SCRIPT_DIR), "schemas", "domain_book_schema.json")


def load_schema() -> dict:
    """加载 domain_book_schema.json"""
    if not os.path.exists(SCHEMA_PATH):
        raise FileNotFoundError(f"schema 文件不存在: {SCHEMA_PATH}")
    with open(SCHEMA_PATH) as f:
        return json.load(f)


def _make_pydantic_models(type_name: str, schema: dict) -> tuple:
    """为指定节点类型动态生成 Pydantic 模型"""
    if not HAS_PYDANTIC:
        return None, None, None

    node_schema = schema['node_types'].get(type_name)
    if not node_schema:
        raise ValueError(f"未知节点类型: {type_name}")

    fm_fields = {}
    for fm_name, fm_def in sorted(node_schema['frontmatter'].items()):
        field_type = str if fm_def['type'] == 'string' else (float if fm_def['type'] == 'number' else list)
        kwargs: dict[str, Any] = {}
        if not fm_def.get('required', True):
            kwargs['default'] = None
        if fm_name == 'confidence':
            kwargs['default'] = node_schema['confidence']['default']
            kwargs['ge'] = 0.5
            kwargs['le'] = 1.0

        ftype = Optional[field_type] if not fm_def.get('required', True) else field_type
        fm_fields[fm_name] = (ftype, Field(**kwargs))

    FrontMatter = type('FrontMatter', (BaseModel,), {
        '__annotations__': {k: v[0] for k, v in fm_fields.items()},
        **{k: v[1] for k, v in fm_fields.items()},
    })

    bd_fields = {}
    for bd_name, bd_def in sorted(node_schema['bd'].items()):
        field_type = str if bd_def['type'] in ('string', 'string|mermaid', 'mermaid') else (list if 'list' in bd_def['type'] else str)
        kwargs = {}
        if not bd_def.get('required', True):
            kwargs['default'] = None
        if 'min_chars' in bd_def.get('constraints', {}):
            kwargs['min_length'] = bd_def['constraints']['min_chars']
        ftype = Optional[field_type] if not bd_def.get('required', True) else field_type
        bd_fields[bd_name] = (ftype, Field(**kwargs))

    BDModel = type('BDModel', (BaseModel,), {
        '__annotations__': {k: v[0] for k, v in bd_fields.items()},
        **{k: v[1] for k, v in bd_fields.items()},
    })

    class FullYAML(BaseModel):
        name: str = Field(..., min_length=1)
        file: str = Field(..., min_length=1)
        fm: FrontMatter
        bd: BDModel

        @model_validator(mode='after')
        def check_confidence(self):
            allowed = node_schema['confidence']['allowed']
            if self.fm.confidence not in allowed:
                raise ValueError(f"confidence={self.fm.confidence} 不属于允许值 {allowed}")
            return self

    return FrontMatter, BDModel, FullYAML


def _validate_item_basic(item: dict, type_name: str, schema: dict) -> list[str]:
    """基础校验（无 pydantic 时的降级方案）"""
    errors = []
    node_schema = schema['node_types'][type_name]
    if 'name' not in item or not item['name']:
        errors.append("缺少 name 字段")

    fm = item.get('fm', {})
    for fm_name, fm_def in node_schema['frontmatter'].items():
        if fm_def.get('required', True) and fm_name not in fm:
            errors.append(f"fm 缺少必填字段: {fm_name}")
    conf = fm.get('confidence')
    if conf is not None:
        allowed = node_schema['confidence']['allowed']
        if conf not in allowed:
            errors.append(f"confidence={conf} 不属于允许值 {allowed}")

    bd = item.get('bd', {})
    for bd_name, bd_def in node_schema['bd'].items():
        if bd_def.get('required', True) and bd_name not in bd:
            errors.append(f"bd 缺少必填字段: {bd_name}")

    known_fm = set(node_schema['frontmatter'].keys())
    if fm:
        extra_fm = set(fm.keys()) - known_fm
        for ef in extra_fm:
            errors.append(f"fm 多余字段: {ef}")
    if bd:
        bd_schema_set = set(node_schema['bd'].keys())
        extra_bd = set(bd.keys()) - bd_schema_set
        for eb in extra_bd:
            errors.append(f"bd 多余字段: {eb}")
    return errors


def validate_yaml_file(yaml_path: str, explicit_type: str = None) -> bool:
    """校验一个YAML文件，返回是否通过"""
    schema = load_schema()
    if explicit_type:
        type_name = explicit_type
    else:
        fname = os.path.basename(yaml_path).replace('.yaml', '').replace('.yml', '')
        type_map = {
            'concepts': 'concept', 'kes': 'ke', 'entities': 'entity',
            'kps': 'kp', 'sps': 'sp', 'scenes': 'scene',
            'exercises': 'exercise', 'solutions': 'solution',
        }
        type_name = type_map.get(fname)
    if not type_name:
        print(f"❌ 无法自动识别类型: {yaml_path}")
        return False
    if not os.path.exists(yaml_path):
        print(f"❌ 文件不存在: {yaml_path}")
        return False

    with open(yaml_path) as f:
        items = _yaml.safe_load(f) if _yaml else json.load(f)
    if not isinstance(items, list):
        print(f"❌ 格式错误: 期望 YAML list")
        return False

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
        return False
    print(f"✅ {yaml_path}: {len(items)} 项，全部通过")
    return True


def write_yaml(type_name: str, yaml_path: str, items_json: str) -> bool:
    """校验并写入YAML文件"""
    schema = load_schema()
    if type_name not in schema['node_types']:
        print(f"❌ 未知节点类型: {type_name}")
        return False
    try:
        items = json.loads(items_json)
    except json.JSONDecodeError as e:
        print(f"❌ items JSON 解析失败: {e}")
        return False
    if not isinstance(items, list):
        print(f"❌ items 必须是 JSON 数组")
        return False

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
            for err in _validate_item_basic(item, type_name, schema):
                all_errors.append(f"第{idx+1}项: {err}")

    if all_errors:
        print(f"❌ 发现 {len(all_errors)} 个错误，YAML 未写入:")
        for e in all_errors:
            print(f"  • {e}")
        return False

    os.makedirs(os.path.dirname(yaml_path), exist_ok=True)
    with open(yaml_path, 'w', encoding='utf-8') as f:
        if _yaml:
            _yaml.dump(items, f, allow_unicode=True, default_flow_style=False, sort_keys=False, width=4096)
        else:
            json.dump(items, f, ensure_ascii=False, indent=2)
    print(f"✅ 已写入 {len(items)} 项 → {yaml_path}")
    return True
