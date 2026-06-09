#!/usr/bin/env python3
"""yaml_writer.py — Agent写YAML的CLI入口（v2.1 模块化）

用法:
  python3 yaml_writer.py list
  python3 yaml_writer.py skeleton --type concept
  python3 yaml_writer.py write --type concept --yaml-path path/to/concepts.yaml --items '[...]'
  python3 yaml_writer.py validate --yaml-path path/to/concepts.yaml
  python3 yaml_writer.py self-instruct --type concept -c N --book-dir /path
  python3 yaml_writer.py prompt --type concept
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from yaml_schema import load_schema, write_yaml, validate_yaml_file  # noqa: E402


# ════════════════════════════════════════════════════════════
# CLI 命令
# ════════════════════════════════════════════════════════════

def cmd_list():
    schema = load_schema()
    print(f"节点类型 ({len(schema['node_types'])} 个):")
    print(f"{'类型名':12s} {'模板':28s} {'confidence':18s} {'前部':6s} {'bd':6s}")
    print("-" * 75)
    for t, n in sorted(schema['node_types'].items()):
        conf = str(n['confidence']['allowed'])
        print(f"{t:12s} {n['template']:28s} {conf:18s} {len(n['frontmatter']):>4d}  {len(n['bd']):>4d}")


def cmd_skeleton(type_name: str):
    schema = load_schema()
    if type_name not in schema['node_types']:
        print(f"❌ 未知节点类型: {type_name}")
        return
    node = schema['node_types'][type_name]
    conf_allowed = node['confidence']['allowed']
    conf_default = node['confidence']['default']

    print(f"# {type_name} YAML 骨架")
    print(f"# 模板: {node['template']}")
    print(f"# confidence: {conf_allowed} (默认 {conf_default})")
    print(f"# bd字段: {len(node['bd'])} 个\n")

    print(f"- name: 示例名称")
    print(f"  file: 示例名称")
    print(f"  fm:")
    for fm_name, fm_def in sorted(node['frontmatter'].items()):
        if fm_name == 'confidence':
            print(f"    confidence: {conf_default}")
        elif fm_def.get('auto_fill'):
            print(f"    #{fm_name}: （自动填充）")
        else:
            print(f"    {fm_name}: ")
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


def cmd_self_instruct(type_name: str, chapter_num: str, book_dir: str = None):
    """为Agent生成字段工作台"""
    import re as _re
    from yaml_signals import (  # noqa: E402
        _parse_source_sections, _extract_formulas, _extract_domain_signals,
        _match_field_to_source, _find_section_title, _output_dir, _load_source_section,
    )

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

    prompts = {}
    for m in _re.finditer(r'<!--\s*@prompt\s+(.*?)-->[\s\S]{0,200}?\{\{(\w+)\}\}', tpl_content):
        prompts[m.group(2)] = m.group(1).strip()

    source_sections = {}
    source_formulas = []
    domain_signals = {}
    if book_dir and chapter_num:
        raw = _load_source_section(book_dir, chapter_num)
        if raw:
            source_sections = _parse_source_sections(raw)
            source_formulas = _extract_formulas(raw)
            domain_signals = _extract_domain_signals(source_sections)

    bd_schema = node['bd']
    required_count = sum(1 for d in bd_schema.values() if d.get('required', True))
    optional_count = sum(1 for d in bd_schema.values() if not d.get('required', True))

    lines: list[str] = []
    lines.append("# ════════════════════════════════════════════════")
    lines.append(f"# 📋 {type_name} 字段工作台")
    lines.append(f"# 模板: {node['template']} → 输出: {_output_dir(type_name)}")
    lines.append(f"# 字段总量: {len(bd_schema)} (必填 {required_count} + 可选 {optional_count})")
    lines.append(f"# 置信度: {node['confidence']['allowed']}")
    lines.append(f"# 章节: 第{chapter_num}章")
    lines.append("# ════════════════════════════════════════════════")

    lines.append("")
    lines.append("⚠️ 顶层 file 字段规则：值为该类型节点的名称（如概念名/技能点名），")
    lines.append('   不含 .md 后缀。禁止使用 source_from 的值（源章节文件名含 .md），')
    lines.append("   否则生成文件名会变成 xxx.md.md。file 不设时默认用 name 字段。")

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

    lines.append("")
    lines.append("## 二、字段工作台")
    lines.append("")

    idx = 0
    for bd_name, bd_def in sorted(bd_schema.items()):
        idx += 1
        required = bd_def.get('required', True)
        ftype = bd_def.get('type', 'string')
        cons = bd_def.get('constraints', {})
        constraints_parts = []
        if 'min_chars' in cons:
            constraints_parts.append(f"≥{cons['min_chars']}字")
        if cons.get('formula_check'):
            constraints_parts.append('公式需$$包裹')
        if 'max_chars' in cons:
            constraints_parts.append(f"≤{cons['max_chars']}字")

        section_title = _find_section_title(tpl_content, bd_name)
        matched_snippets = _match_field_to_source(bd_name, section_title, source_sections, prompts.get(bd_name, ''), domain_signals)

        required_mark = '🔴' if required else '🟡'
        required_label = '必填' if required else '可选'
        lines.append(f"{'─'*60}")
        lines.append(f"{required_mark} {idx}/{len(bd_schema)} {bd_name} [{required_label}/{ftype}]")
        lines.append(f"    模板位置: {section_title}")
        if constraints_parts:
            lines.append(f"    schema约束: {'，'.join(constraints_parts)}")
        prompt_text = prompts.get(bd_name, '')
        if prompt_text:
            lines.append(f"    @prompt: {prompt_text}")
        else:
            lines.append(f"    @prompt: （无特殊要求，按字段名含义自然书写）")
        if matched_snippets:
            for sn in matched_snippets[:2]:
                lines.append(f"    源文: 「{sn}」")
        if bd_name == 'mathematical_model' and source_formulas:
            lines.append(f"    源文公式提示:")
            for ln, fm in source_formulas[:3]:
                fm_short = fm[:80] + ('...' if len(fm) > 80 else '')
                lines.append(f"      L{ln}: {fm_short}")

    print("\n".join(lines))


def cmd_prompt(type_name: str, field_name: str = None):
    """查看模板中的 @prompt 指令"""
    SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    schema = load_schema()
    if type_name not in schema['node_types']:
        print(f"❌ 未知节点类型: {type_name}")
        return
    import re as _re
    node = schema['node_types'][type_name]
    tpl_path = os.path.join(SKILL_DIR, 'assets', 'templates', node['template'])
    if not os.path.exists(tpl_path):
        print(f"❌ 模板文件不存在: {tpl_path}")
        return
    with open(tpl_path, encoding='utf-8') as f:
        tpl = f.read()
    prompts = {}
    for m in _re.finditer(r'<!--\s*@prompt\s+(.*?)-->[\s\S]{0,200}?\{\{(\w+)\}\}', tpl):
        prompts[m.group(2)] = m.group(1).strip()
    if field_name:
        if field_name in prompts:
            print(prompts[field_name])
        else:
            print(f"❌ 字段 {field_name} 无 @prompt")
        return
    print(f"📋 {type_name} @prompt 概览 ({len(prompts)} 个字段):\n")
    for fname, pt in sorted(prompts.items()):
        print(f"  {fname:30s} {pt[:60]}..." if len(pt) > 60 else f"  {fname:30s} {pt}")


def cmd_validate_dir(data_dir: str):
    """批量验证整个目录的YAML"""
    if not os.path.isdir(data_dir):
        print(f"❌ 目录不存在: {data_dir}")
        return
    yaml_files = sorted(f for f in os.listdir(data_dir) if f.endswith(('.yaml', '.yml')))
    if not yaml_files:
        print(f"📂 空目录: {data_dir}")
        return
    all_pass = True
    for yf in yaml_files:
        yp = os.path.join(data_dir, yf)
        ok = validate_yaml_file(yp)
        if not ok:
            all_pass = False
    if all_pass:
        print(f"\n✅ 全部 {len(yaml_files)} 个文件通过")
    else:
        print(f"\n⚠️  部分文件未通过")


def main():
    p = argparse.ArgumentParser(description="YAML 写入工具 (v2.1 模块化)")
    sp = p.add_subparsers(dest="cmd")

    sp.add_parser("list", help="列出所有节点类型")

    sk = sp.add_parser("skeleton", help="生成YAML骨架")
    sk.add_argument("--type", required=True)

    wr = sp.add_parser("write", help="校验并写入YAML")
    wr.add_argument("--type", required=True)
    wr.add_argument("--yaml-path", required=True)
    wr.add_argument("--items", required=True)

    vl = sp.add_parser("validate", help="校验YAML文件")
    vl.add_argument("--yaml-path", required=True)
    vl.add_argument("--type")

    vd = sp.add_parser("validate-dir", help="批量校验目录")
    vd.add_argument("--dir", required=True)

    si = sp.add_parser("self-instruct", help="生成字段工作台")
    si.add_argument("--type", required=True)
    si.add_argument("-c", "--chapter")
    si.add_argument("--book-dir")

    pm = sp.add_parser("prompt", help="查看@prompt指令")
    pm.add_argument("--type", required=True)
    pm.add_argument("--field")

    a = p.parse_args()
    if not a.cmd:
        p.print_help()
        return

    try:
        if a.cmd == "list":
            cmd_list()
        elif a.cmd == "skeleton":
            cmd_skeleton(a.type)
        elif a.cmd == "write":
            success = write_yaml(a.type, a.yaml_path, a.items)
            sys.exit(0 if success else 1)
        elif a.cmd == "validate":
            ok = validate_yaml_file(a.yaml_path, a.type)
            sys.exit(0 if ok else 1)
        elif a.cmd == "validate-dir":
            cmd_validate_dir(a.dir)
        elif a.cmd == "self-instruct":
            cmd_self_instruct(a.type, a.chapter or "", a.book_dir)
        elif a.cmd == "prompt":
            cmd_prompt(a.type, a.field)
    except Exception as e:
        print(f"❌ 错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
