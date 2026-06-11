#!/usr/bin/env python3
"""
domain_injector.py — 用知识图谱的领域信号填充 reference 模板变量。

读取 domain-context.yaml，将 references/ 中的 {{var}} 替换为实际领域词，
写入 output/领域上下文/references/ 目录供 Agent 加载。

用法：
  python3 scripts/domain_injector.py --project /path/to/教材
  python3 scripts/domain_injector.py --project /path/to/教材 --refs-only   # 只生成reference副本
"""

import os
import re
import sys
import yaml
import shutil
import argparse
from pathlib import Path
from typing import Dict, Optional

# project root
SKILL_DIR = Path(__file__).resolve().parent.parent
REFERENCES_DIR = SKILL_DIR / "references"


def load_domain_context(project_root: str) -> Dict:
    """读取已构建的领域上下文"""
    yaml_path = os.path.join(project_root, "output", "领域上下文", "domain-context.yaml")
    if not os.path.exists(yaml_path):
        print(f"⚠️  领域上下文不存在，请先运行 kg_builder.py build")
        print(f"   {yaml_path}")
        return {}
    with open(yaml_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f) or {}


def build_variable_map(ctx: Dict) -> Dict[str, str]:
    """
    从领域上下文构建 {{var}} → 实际值的映射表。
    
    默认值用于领域信号缺失时的回退。
    """
    domain_name = ctx.get("domain_name", "本领域")
    standards = ctx.get("standards_family", [])
    top_terms = [t["term"] for t in ctx.get("top_terms", [])[:5]]
    
    standards_str = "、".join(standards) if standards else "行业"
    
    return {
        "domain_name": domain_name,
        "domain_standards": f"{standards_str}标准",
        "domain_standards_family": standards_str,
        "domain_key_terms": "、".join(top_terms[:3]) if top_terms else f"{domain_name}核心概念",
        "example_cases": f"真实{domain_name}工程案例",
        "standard_refs": f"参考教材、{standards_str}标准、公开报告",
    }


def inject_variables(text: str, var_map: Dict[str, str]) -> str:
    """替换所有 {{var}} 为实际值，未定义的变量保留原样"""
    def replacer(m):
        var_name = m.group(1).strip()
        if var_name in var_map:
            return var_map[var_name]
        # Try partial match
        for key, val in var_map.items():
            if key in var_name:
                return val
        return m.group(0)  # Keep as-is
    
    return re.sub(r'\{\{(\w+)\}\}', replacer, text)


def inject_references(project_root: str, var_map: Dict[str, str], verbose: bool = False) -> int:
    """用领域信号填充 references/ 中的模板，写入项目 output/ 目录"""
    refs_dir = os.path.join(project_root, "output", "领域上下文", "references")
    os.makedirs(refs_dir, exist_ok=True)
    
    count = 0
    for fpath in sorted(REFERENCES_DIR.glob("*.md")):
        content = fpath.read_text(encoding='utf-8')
        
        # 只处理含 {{variable}} 的文件
        if '{{' not in content:
            continue
        
        injected = inject_variables(content, var_map)
        out_path = os.path.join(refs_dir, fpath.name)
        
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(injected)
        
        count += 1
        if verbose:
            vars_found = re.findall(r'\{\{(\w+)\}\}', content)
            print(f"   {fpath.name}: {len(vars_found)} 个变量")
    
    return count


def inject_generate_outlines(project_root: str, var_map: Dict[str, str]):
    """目前 template 变量通过 domain-context.yaml 运行时注入"""
    pass


def main():
    parser = argparse.ArgumentParser(description='领域信号注入器')
    parser.add_argument('--project', required=True, help='项目根目录')
    parser.add_argument('--refs-only', action='store_true', help='只生成 reference 副本')
    parser.add_argument('--verbose', '-v', action='store_true')
    args = parser.parse_args()
    
    ctx = load_domain_context(args.project)
    if not ctx:
        sys.exit(1)
    
    var_map = build_variable_map(ctx)
    
    print(f"\n🔧 领域信号注入")
    print(f"   领域: {var_map['domain_name']}")
    print(f"   标准: {var_map['domain_standards']}")
    print(f"   核心术语: {ctx.get('top_terms', [])[:5]}")
    
    ref_count = inject_references(args.project, var_map, verbose=args.verbose)
    print(f"\n   ✅ 已注入 {ref_count} 个 reference 文件")
    print(f"      到 {args.project}/output/领域上下文/references/")


if __name__ == '__main__':
    main()
