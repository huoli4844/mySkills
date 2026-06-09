#!/usr/bin/env python3
"""template_engine.py — YAML → .md 渲染引擎（v2.0）

从 domain_book_schema.json 读取字段映射，从模板 .md 读取输出格式。
纯代码引擎，无硬编码字段名，领域无关、书籍无关。

用法:
  # 渲染单个类型
  python3 template_engine.py render --type concept \\
    --data .dag/第N章/data/concepts.yaml \\
    --output 30_核心概念 \\
    --book-id 01_书籍ID --book-name "书籍名称" -c N

  # 按顺序渲染一个章节的全部L1类型（concept→ke→entity→kp→sp→scene→exercise→solution）
  python3 template_engine.py render-chapter \\
    --data-dir .dag/第N章/data \\
    --output-dir . \\
    --book-id 01_书籍ID --book-name "书籍名称" -c N

设计原则：
  - 不读取任何`.py`中的字段定义，全部从 schema.json + 模板 .md 驱动
  - 模板中写了什么 {{xxx}}，就从 YAML 的对应字段取值
  - 字段名映射通过 schema.json 的 template_var 字段
  - 所有自动填充字段（book_id/book_name/chapter_num 等）由代码注入，不依赖 YAML
"""

import argparse
import json
import os
import re
import sys
from typing import Any, Optional

try:
    import yaml as _yaml
except ImportError:
    _yaml = None


# ── 路径 ──
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(SCRIPT_DIR)
SCHEMA_PATH = os.path.join(SKILL_DIR, "schemas", "domain_book_schema.json")
TEMPLATES_DIR = os.path.join(SKILL_DIR, "assets", "templates")

# 节点类型 → 输出目录映射（知识库目录约定）
DIR_MAP = {
    'concept':    '30_核心概念',
    'ke':         '40_知识要素',
    'entity':     '80_实体',
    'kp':         '50_知识点',
    'sp':         '60_技能点',
    'scene':      '70_应用场景',
    'exercise':   '90_习题',
    'solution':   '90_习题/解答',
}

# 习题/解答特殊处理（filename 不同）
EXERCISE_FILENAME_MAP = {
    'exercise': lambda item, ch: f"{item['name']}.md" if item['name'].startswith(f'第{ch}章') else f"第{ch}章-{item['name']}.md",
    'solution': lambda item, ch: f"{item['name']}.md" if item['name'].startswith(f'第{ch}章') else f"第{ch}章-{item['name']}-解答.md",
}


# ════════════════════════════════════════════════════════════
# Schema 加载
# ════════════════════════════════════════════════════════════

def load_schema() -> dict:
    if not os.path.exists(SCHEMA_PATH):
        raise FileNotFoundError(f"schema 文件不存在: {SCHEMA_PATH}")
    with open(SCHEMA_PATH) as f:
        return json.load(f)


def load_template(template_name: str) -> str:
    """加载模板 .md 文件"""
    tpl_path = os.path.join(TEMPLATES_DIR, template_name)
    if not os.path.exists(tpl_path):
        raise FileNotFoundError(f"模板文件不存在: {tpl_path}")
    with open(tpl_path, encoding='utf-8') as f:
        return f.read()


# ════════════════════════════════════════════════════════════
# 核心渲染逻辑
# ════════════════════════════════════════════════════════════

def render_item(item: dict, type_name: str, schema: dict,
                book_id: str, book_name: str, chapter_num: str) -> Optional[str]:
    """将单个 YAML item 渲染为 .md 文本。返回 None 表示失败。"""
    node_schema = schema['node_types'].get(type_name)
    if not node_schema:
        print(f"❌ 未知节点类型: {type_name}", file=sys.stderr)
        return None

    # 加载模板
    template_name = node_schema['template']
    template_content = load_template(template_name)

    # 构建替换表：{{xxx}} → 值
    replacements = {}

    # 1. 从 YAML fm 字段
    fm = item.get('fm', {})
    for fm_name, fm_def in node_schema['frontmatter'].items():
        if fm_name in fm:
            val = fm[fm_name]
        else:
            # 自动填充字段
            val = _auto_fill_value(fm_name, item, book_id, book_name, chapter_num, type_name)
        replacements[fm_name] = val if val is not None else ''

    # 2. 从 YAML bd 字段
    bd = item.get('bd', {})
    for bd_name, bd_def in node_schema['bd'].items():
        val = bd.get(bd_name, '')
        if val is None:
            val = ''
        # 处理 list 类型
        if isinstance(val, list):
            val = '\n'.join(f'- {v}' for v in val) if val else ''
        replacements[bd_name] = val

    # 3. name 特殊处理（item 顶层）
    if 'name' not in replacements or not replacements.get('name'):
        replacements['name'] = item.get('name', '')

    # 特殊字段后处理：mermaid 类字段自动包裹
    MERMAID_FIELDS = {'core_concept_map', 'structure_diagram', 'principle_diagram', 'workflow_diagram',
                      'solution_flowchart', 'application_scenario'}
    for key in MERMAID_FIELDS:
        if key in replacements and replacements[key]:
            replacements[key] = _auto_wrap_mermaid(str(replacements[key]))

    # 执行替换
    result = template_content
    for key, val in replacements.items():
        result = result.replace('{{' + key + '}}', str(val))

    # 检查未替换的占位符
    remaining = set(re.findall(r'\{\{(\w+)\}\}', result))
    if remaining:
        # 尝试用自动填充兜底
        for key in list(remaining):
            val = _auto_fill_value(key, item, book_id, book_name, chapter_num, type_name)
            if val is not None and val != '':
                result = result.replace('{{' + key + '}}', str(val))
                remaining.discard(key)
        if remaining:
            print(f"  ⚠️ 未替换的占位符: {', '.join(sorted(remaining))}", file=sys.stderr)

    # 剥离 HTML 注释（包括 @prompt 写作指导）
    result = re.sub(r'<!--.*?-->', '', result, flags=re.DOTALL)

    return result


def _auto_wrap_mermaid(value: str) -> str:
    """自动为 mermaid 类字段添加代码块包裹（如果还不含）"""
    if not value or value.strip() == '':
        return value  # 空内容留空
    stripped = value.strip()
    # 检查是否已有代码块包裹或 init 配置
    if stripped.startswith('```') or stripped.startswith('%%init'):
        return value  # 已有 fences 或 init 配置，不重复包裹
    # 如果是 raw mermaid 内容，用完整包裹
    if any(stripped.startswith(prefix) for prefix in ('graph ', 'pie ', 'flowchart ', 'sequenceDiagram', 'classDiagram', 'stateDiagram', 'mindmap', 'gantt', 'journey', 'gitGraph', 'erDiagram', 'timeline', 'xychart')):
        return f"```mermaid\n{stripped}\n```"
    # 难以判断，则原样输出
    return value


def _auto_fill_value(field_name: str, item: dict,
                     book_id: str, book_name: str, chapter_num: str,
                     type_name: str) -> Any:
    """为自动填充字段生成值"""
    defaults = {
        'book_id': book_id,
        'book_name': book_name,
        'chapter_num': chapter_num,
        'name': item.get('name', ''),
        'type': type_name,
        'type_tag': NODE_TAG_MAP.get(type_name, [type_name]),
        'template_version': 'v7.0',
        'cssclass': 'knowledge-base',
        'bloom_level': item.get('fm', {}).get('bloom_level', ''),
        'entity_type': item.get('fm', {}).get('entity_type', ''),
        'bloom_progression_analysis': '',
        'exercise_link': _gen_exercise_link(item, type_name, chapter_num),
        'exercise_name': _gen_exercise_link(item, type_name, chapter_num),
        'source_chapter': chapter_num,
        'source_from': '',
    }
    if field_name in defaults:
        return defaults[field_name]
    if field_name == 'aliases':
        return item.get('fm', {}).get('aliases', [])
    if field_name == 'tags':
        tags = [book_id, type_name]
        extra_tags = item.get('fm', {}).get('tags', [])
        if isinstance(extra_tags, list):
            tags.extend(extra_tags)
        return tags
    return ''


NODE_TAG_MAP = {
    'concept': ['核心概念'],
    'ke': ['知识要素'],
    'entity': ['实体'],
    'kp': ['知识点'],
    'sp': ['技能点'],
    'scene': ['应用场景'],
    'exercise': ['习题'],
    'solution': ['习题解答'],
}


def _gen_exercise_link(item: dict, type_name: str, chapter_num: str) -> str:
    """从solution item的名称生成对应的习题链接名"""
    name = item.get('name', '')
    base_name = name.replace('-解答', '').replace(f'第{chapter_num}章-', f'第{chapter_num}章-')
    return f"第{chapter_num}章-{base_name}" if not base_name.startswith(f'第{chapter_num}章') else base_name


# ════════════════════════════════════════════════════════════
# 输出文件名生成
# ════════════════════════════════════════════════════════════

def get_output_filename(item: dict, type_name: str, chapter_num: str) -> str:
    """根据item和类型生成输出文件名"""
    # exercise/solution 有特殊命名
    if type_name in EXERCISE_FILENAME_MAP:
        return EXERCISE_FILENAME_MAP[type_name](item, chapter_num)

    # 其他类型使用 file 字段
    file_base = item.get('file', item.get('name', 'unnamed'))
    # 防御性去除已有 .md 后缀，防止 Agent 误将 source_from 值（含 .md）写入 file 字段导致 .md.md
    if file_base.endswith('.md'):
        file_base = file_base[:-3]
    return f"{file_base}.md"


# ════════════════════════════════════════════════════════════
# YAML 数据加载
# ════════════════════════════════════════════════════════════

def load_yaml(yaml_path: str) -> list:
    """加载 YAML 数据文件"""
    if not os.path.exists(yaml_path):
        print(f"⚠️ 文件不存在: {yaml_path}", file=sys.stderr)
        return []

    with open(yaml_path, encoding='utf-8') as f:
        if _yaml:
            data = _yaml.safe_load(f)
        else:
            data = json.load(f)

    if not isinstance(data, list):
        print(f"⚠️ {yaml_path}: 期望 YAML list，得到 {type(data).__name__}", file=sys.stderr)
        return []

    return data


# ════════════════════════════════════════════════════════════
# CLI 命令
# ════════════════════════════════════════════════════════════

def cmd_render(type_name: str, data_path: str, output_dir: str,
               book_id: str, book_name: str, chapter_num: str):
    """渲染单个类型的所有item为.md文件"""
    schema = load_schema()

    if type_name not in schema['node_types']:
        print(f"❌ 未知节点类型: {type_name}")
        print(f"   可用: {', '.join(sorted(schema['node_types'].keys()))}")
        return

    items = load_yaml(data_path)
    if not items:
        print(f"📂 {data_path}: 无数据，跳过")
        return

    os.makedirs(output_dir, exist_ok=True)

    generated = 0
    for item in items:
        # 渲染
        md_content = render_item(item, type_name, schema, book_id, book_name, chapter_num)
        if md_content is None:
            continue

        # 输出文件名
        filename = get_output_filename(item, type_name, chapter_num)
        output_path = os.path.join(output_dir, filename)

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(md_content)
        generated += 1

    print(f"✅ [{type_name}] {data_path} → {output_dir}: {generated} 个文件")


def cmd_render_chapter(data_dir: str, output_base: str,
                       book_id: str, book_name: str, chapter_num: str):
    """按DAG顺序逐类型渲染一章"""
    schema = load_schema()

    # YAML文件名 → 类型名映射
    yaml_map = {
        'concepts.yaml': 'concept',
        'kes.yaml': 'ke',
        'entities.yaml': 'entity',
        'kps.yaml': 'kp',
        'sps.yaml': 'sp',
        'scenes.yaml': 'scene',
        'exercises.yaml': 'exercise',
        'solutions.yaml': 'solution',
    }

    # 按DAG顺序
    dag_order = ['concept', 'ke', 'entity', 'kp', 'sp', 'scene', 'exercise', 'solution']

    for type_name in dag_order:
        yaml_fname = [k for k, v in yaml_map.items() if v == type_name][0]
        yaml_path = os.path.join(data_dir, yaml_fname)

        if not os.path.exists(yaml_path):
            print(f"⏭️ [{type_name}] YAML文件不存在: {yaml_fname}")

            # exercise/solution 特殊处理：自动检测
            if type_name == 'exercise':
                print(f"   尝试自动检测习题...")
                _auto_detect_exercises(output_base, book_id, book_name, chapter_num)
            elif type_name == 'solution':
                print(f"   尝试生成解答骨架...")
                _auto_generate_solutions(output_base, book_id, book_name, chapter_num)
            continue

        output_dir_key = DIR_MAP.get(type_name)
        if not output_dir_key:
            print(f"⚠️ [{type_name}] 无输出目录映射")
            continue

        output_dir = os.path.join(output_base, output_dir_key)
        cmd_render(type_name, yaml_path, output_dir, book_id, book_name, chapter_num)


def _auto_detect_exercises(output_base: str, book_id: str, book_name: str, chapter_num: str):
    """从源文自动检测习题（简化版，不依赖完整pipeline）"""
    source_dir = os.path.join(output_base, '20_正文')
    if not os.path.isdir(source_dir):
        return

    # 查找章节文件
    source_files = sorted(f for f in os.listdir(source_dir) if f.startswith(f'第{chapter_num}章'))
    if not source_files:
        return

    source_path = os.path.join(source_dir, source_files[0])
    with open(source_path, encoding='utf-8') as f:
        content = f.read()

    # 提取习题
    ex_section = re.search(r'## 习题\s*\n(.*?)(?=\n## |\Z)', content, re.DOTALL)
    if not ex_section:
        return

    ex_lines = ex_section.group(1).strip().split('\n')
    exs = []
    for line in ex_lines:
        m = re.match(r'\d+[\.\、]\s*(.*)', line.strip())
        if m:
            exs.append({
                'name': f'习题{len(exs)+1}',
                'fm': {'source_chapter': chapter_num},
                'bd': {'question': m.group(1).strip(), 'related_answer': ''},
            })

    if not exs:
        return

    ex_dir = os.path.join(output_base, '90_习题')
    os.makedirs(ex_dir, exist_ok=True)

    schema = load_schema()
    for ex in exs:
        md = render_item(ex, 'exercise', schema, book_id, book_name, chapter_num)
        if md:
            raw_name = ex['name']
            if raw_name.startswith(f'第{chapter_num}章-'):
                filename = f"{raw_name}.md"
            else:
                filename = f"第{chapter_num}章-{raw_name}.md"
            with open(os.path.join(ex_dir, filename), 'w', encoding='utf-8') as f:
                f.write(md)

    print(f"  ✅ 自动检测到 {len(exs)} 道习题")


def _auto_generate_solutions(output_base: str, book_id: str, book_name: str, chapter_num: str):
    """为习题生成解答骨架，读取习题文件中的题目内容"""
    ex_dir = os.path.join(output_base, '90_习题')
    sol_dir = os.path.join(output_base, '90_习题', '解答')

    if not os.path.isdir(ex_dir):
        return

    ex_files = sorted(f for f in os.listdir(ex_dir)
                      if f.endswith('.md') and '解答' not in f and f.startswith(f'第{chapter_num}章'))

    if not ex_files:
        return

    os.makedirs(sol_dir, exist_ok=True)
    schema = load_schema()

    generated = 0
    for exf in ex_files:
        base = exf.replace('.md', '')
        sol_name = f"{base}-解答"

        # 读取习题文件提取题目内容
        question_text = ''
        ex_path = os.path.join(ex_dir, exf)
        if os.path.exists(ex_path):
            with open(ex_path, encoding='utf-8') as f:
                ex_content = f.read()
            q_match = re.search(r'## 题目内容\s*\n(.*?)(?=\n## |\Z)', ex_content, re.DOTALL)
            if q_match:
                question_text = q_match.group(1).strip()[:500]

        item = {
            'name': sol_name,
            'fm': {
                'source_chapter': chapter_num,
                'confidence': 0.65,
                'confidence_note': '自动生成骨架，待Agent填充',
                'exercise_link': base,
                'exercise_name': base,
            },
            'bd': {
                k: '（待Agent填充）' for k in schema['node_types']['solution']['bd'].keys()
            },
        }
        # 如果有问题内容，填入题目原文
        if question_text:
            item['bd']['question'] = question_text

        md = render_item(item, 'solution', schema, book_id, book_name, chapter_num)
        if md:
            out_path = os.path.join(sol_dir, f"{sol_name}.md")
            with open(out_path, 'w', encoding='utf-8') as f:
                f.write(md)
            generated += 1

    print(f"  ✅ 生成了 {generated} 个解答骨架（含题目原文）")


# ════════════════════════════════════════════════════════════
# Main
# ════════════════════════════════════════════════════════════

def main():
    p = argparse.ArgumentParser(description="template_engine v2 — 从schema驱动的模板渲染引擎")
    sp = p.add_subparsers(dest="cmd")

    # list
    sp.add_parser("list", help="列出所有节点类型及模板映射")

    # render
    rn = sp.add_parser("render", help="渲染单个类型的YAML为.md文件")
    rn.add_argument("--type", required=True, help="节点类型")
    rn.add_argument("--data", required=True, help="YAML数据文件路径")
    rn.add_argument("--output", required=True, help="输出目录")
    rn.add_argument("--book-id", required=True)
    rn.add_argument("--book-name", required=True)
    rn.add_argument("-c", "--chapter", required=True)

    # render-chapter
    rc = sp.add_parser("render-chapter", help="按DAG顺序渲染一章全部L1类型")
    rc.add_argument("--data-dir", required=True, help="YAML数据目录（.dag/第N章/data）")
    rc.add_argument("--output-dir", required=True, help="知识库根目录")
    rc.add_argument("--book-id", required=True)
    rc.add_argument("--book-name", required=True)
    rc.add_argument("-c", "--chapter", required=True)

    a = p.parse_args()

    if not a.cmd:
        p.print_help()
        return

    if a.cmd == "list":
        schema = load_schema()
        print(f"{'类型名':12s} {'模板':28s} {'输出目录':16s} {'confidence':18s} {'bd字段':>6s}")
        print("-" * 85)
        for t, n in sorted(schema['node_types'].items()):
            conf = str(n['confidence']['allowed'])
            out_dir = DIR_MAP.get(t, '')
            print(f"{t:12s} {n['template']:28s} {out_dir:16s} {conf:18s} {len(n['bd']):>6d}")

    elif a.cmd == "render":
        cmd_render(a.type, a.data, a.output, a.book_id, a.book_name, a.chapter)

    elif a.cmd == "render-chapter":
        cmd_render_chapter(a.data_dir, a.output_dir, a.book_id, a.book_name, a.chapter)


if __name__ == "__main__":
    main()
