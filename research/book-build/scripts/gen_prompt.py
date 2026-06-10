#!/usr/bin/env python3
"""
写作指令生成器 — 对大纲中的每一节，生成 Agent 写作用的结构化提示词。

核心原则：KB 内容是原料，教材是成品，不能直接搬运。每节需重新组织。

用法：
  # 对某节生成写作指令并保存到文件
  python3 scripts/gen_prompt.py \\
    --outline /tmp/教材大纲.json \\
    --kb-dir /Users/.../电磁兼容知识库 \\
    --chapter 3 --section 3.1 \\
    -o /tmp/prompt_3.1.md

  # 输出到 stdout（给子 Agent 传 context）
  python3 scripts/gen_prompt.py \\
    --outline /tmp/教材大纲.json \\
    --kb-dir /Users/.../电磁兼容知识库 \\
    --chapter 3 --section 3.1

输出内容（5个板块）：
  ① 本章在全书的定位（前章/后章/依赖关系）
  ② 本节信息（标题、内容类型、子节、推荐写作结构）
  ③ KB素材（按类型分组：概念/知识要素/知识点/技能点/场景）
  ④ 写作规则（6要素必须/可选/禁止）
  ⑤ 段落过渡指导 + 公式编号约定 + 章节结尾模板

内容类型（6种）：
  - 历史叙事型：分阶段 + 双线（国际/国内）+ 对照表
  - 概念解构型：直观引入 → 多标准定义 → 分解 → 对比表
  - 原理推导型：物理原理 → 建模 → 推导 → 式中解释 → 例题
  - 系统组成型：框图 + 逐项详述
  - 分类枚举型：分类表 + 每类详述
  - 工程案例型：问题 → 方案 → 实施 → 验证

依赖：
  - kb-qa/scripts/kb_search.py（搜索知识库）
  - scripts/detect_content_type.py（判断内容类型）
  - scripts/book_config.py（加载 config.yaml 领域配置）
"""
import argparse, json, os, sys, textwrap
from pathlib import Path

# === 知识点领域相关的检测前缀 ===
DOMAIN_WIKI_PREFIXES = ['30_核心概念', '40_知识要素', '50_知识点',
                        '60_技能点', '70_应用场景', '80_实体', '90_习题']

# 硬编码的依赖关系（可根据大纲动态生成）
CHAPTER_DEPENDS = {
    1: [],           # 绪论，独立
    2: [1],          # 概述依赖绪论
    3: [1, 2],       # 骚扰源依赖前面
    4: [1, 2],       # 耦合途径
    5: [1, 2, 3, 4],
    6: [1, 2, 3, 4, 5],
    7: [1, 2, 3, 4, 5, 6],
    8: [1, 2, 3, 4, 5, 6, 7],
    9: [1, 2, 3, 4, 5, 6, 7, 8],
    10: [1, 2, 3, 4, 5, 6, 7, 8, 9],
    11: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
    12: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11],
    13: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
}

SIX_ELEMENTS = {
    'authoritative_definition': {
        'label': '权威定义',
        'rule': '引用国家标准/国际标准的定义，多个权威并列后归纳共同点',
        'required': '概念解构型',
        'forbidden': '只给一个定义就完事',
    },
    'intuitive_intro': {
        'label': '直观引入',
        'rule': '公式之前必须给出物理直观或日常类比，至少1-2句话',
        'required': '原理推导型',
        'forbidden': '公式直接出现没有引出',
    },
    'numbered_formula': {
        'label': '有编号的公式',
        'rule': '每个公式必须有 \\tag{章-序号} 编号',
        'required': '原理推导型',
        'forbidden': '公式无编号',
    },
    'variable_explanation': {
        'label': '"式中"变量解释',
        'rule': '每个公式后紧接"式中"段落，解释每个符号的含义和单位',
        'required': '含公式的所有类型',
        'forbidden': '公式后无变量解释',
    },
    'concrete_example': {
        'label': '含数字的实例',
        'rule': '必须有具体数字的实例（如"某系统参数为X，代入计算得Y"）',
        'required': '所有类型',
        'forbidden': '"已知A=B求C"这种抽象表述',
    },
    'layered_exercises': {
        'label': '层次化习题',
        'rule': 'L1概念+L2公式应用+L3综合分析+L4故障诊断，每章至少4题',
        'required': '每章末尾',
        'forbidden': '只有概念题或只有计算题',
    },
}


def load_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def search_kb_for_section(kb_dir, query, max_results=5):
    """调用 kb_search.py 搜索 KB"""
    kb_search = Path(__file__).parent.parent.parent / 'kb-qa' / 'scripts' / 'kb_search.py'
    if not kb_search.exists():
        # 备选路径
        kb_search = Path(__file__).parent / 'search_kb.py'
    
    import subprocess
    r = subprocess.run(
        [sys.executable, str(kb_search), kb_dir, query,
         '--format', 'json', '--max-results', str(max_results)],
        capture_output=True, text=True, timeout=15
    )
    try:
        return json.loads(r.stdout)
    except:
        return {"results": [], "total": 0}


def detect_content_type(section_title, outline_context=None):
    """判断内容类型（调用 detect_content_type.py 或规则判断）"""
    dct = Path(__file__).parent / 'detect_content_type.py'
    import subprocess
    r = subprocess.run(
        [sys.executable, str(dct), section_title, '--format', 'json'],
        capture_output=True, text=True, timeout=10
    )
    try:
        return json.loads(r.stdout)
    except:
        return {"primary_type": "mixed", "label": "复合型", "suggested_structure": []}


def get_chapter_context(ch_num, outline):
    """获取本章在全书中的上下文"""
    chapters = outline.get('chapters', [])
    ch_idx = None
    for i, c in enumerate(chapters):
        if str(c.get('number', '')) == str(ch_num):
            ch_idx = i
            break
    
    if ch_idx is None:
        return f"第{ch_num}章"
    
    ch = chapters[ch_idx]
    prev = chapters[ch_idx - 1]['title'] if ch_idx > 0 else None
    next_ch = chapters[ch_idx + 1]['title'] if ch_idx < len(chapters) - 1 else None
    depends = CHAPTER_DEPENDS.get(int(ch_num), [])
    
    parts = []
    if prev:
        parts.append(f"前章：{prev}")
    if next_ch:
        parts.append(f"后章：{next_ch}")
    parts.append(f"依赖前章：第{'、'.join(str(d) for d in depends)}章" if depends else "独立章（全书基础）")
    
    return ' | '.join(parts)


def get_element_requirements(content_type):
    """根据内容类型获取 6 要素的必须/可选/禁止列表"""
    mandatory = []
    optional = []
    forbidden = []
    
    primary = content_type.get('primary_type', 'mixed')
    
    for key, elem in SIX_ELEMENTS.items():
        req = elem['required']
        fb = elem['forbidden']
        
        if req == '所有类型':
            mandatory.append(f"✅ **必须** {elem['label']}：{elem['rule']}")
            forbidden.append(f"🚫 **禁止** {fb}")
        elif primary in req or req == primary:
            mandatory.append(f"✅ **必须** {elem['label']}：{elem['rule']}")
            forbidden.append(f"🚫 **禁止** {fb}")
        elif req == '每章末尾':
            optional.append(f"⬜ **章末** {elem['label']}：{elem['rule']}")
        else:
            optional.append(f"⬜ **可选** {elem['label']}：{elem['rule']}")
    
    return mandatory + optional, forbidden


def build_kb_section(kb_data):
    """从 KB 搜索结果构建素材清单"""
    lines = []
    results = kb_data.get('results', [])
    if not results:
        lines.append("> ⚠️ KB 无匹配。将基于通用领域知识写作。")
        lines.append("")
        return '\n'.join(lines)
    
    # 按类型分组
    by_type = {}
    for r in results:
        t = r.get('type', 'other')
        if t not in by_type:
            by_type[t] = []
        by_type[t].append(r)
    
    type_labels = {'kp': '知识点', 'concept': '核心概念', 'ke': '知识要素',
                   'sp': '技能点', 'scene': '应用场景', 'entity': '实体',
                   'exercise': '习题', 'body': '正文'}
    
    for t in ['kp', 'concept', 'ke', 'sp', 'scene', 'entity', 'exercise', 'body']:
        items = by_type.get(t, [])
        if not items:
            continue
        label = type_labels.get(t, t)
        lines.append(f"#### 【{label}】{len(items)}项")
        lines.append("")
        for item in items:
            fname = item.get('filename', '?')
            score = item.get('score', 0)
            preview = item.get('preview', '')
            lines.append(f"- **{fname}** (评分{score})")
            if preview:
                lines.append(f"  ```\n  {preview[:200]}\n  ```")
        lines.append("")
    
    return '\n'.join(lines)


def generate_prompt(outline_path, kb_dir, chapter_num, section_key,
                     output_path=None, format='text'):
    """生成一节完整的写作指令"""
    outline = load_json(outline_path)
    
    # 定位章节
    section_info = None
    chapter_info = None
    for ch in outline.get('chapters', []):
        if str(ch.get('number', '')) == str(chapter_num):
            chapter_info = ch
            for sec in ch.get('sections', []):
                if str(sec.get('number', '')) == str(section_key) or \
                   sec.get('title', '').startswith(section_key):
                    section_info = sec
                    break
            break
    
    if not section_info:
        return f"❌ 未找到第{chapter_num}章节{section_key}"
    
    section_title = section_info['title']
    full_title = section_title
    
    # 搜索 KB
    kb_data = search_kb_for_section(kb_dir, section_title)
    
    # 判断内容类型
    ctype = detect_content_type(section_title)
    
    # 获取章节上下文
    context = get_chapter_context(chapter_num, outline)
    
    # 获取 6 要素要求
    requirements, forbidden = get_element_requirements(ctype)
    
    # KB 素材
    kb_section = build_kb_section(kb_data)
    
    # ====== 组装提示词 ======
    prompt_parts = []
    
    prompt_parts.append(f"""# 写作指令：第{chapter_num}章 {full_title}

---

## 一、本章在全书的定位

{context}

---

## 二、本节信息

- **标题**：{full_title}
- **内容类型**：{ctype.get('label', '复合型')}
- **子节**：""")
    
    subs = section_info.get('subsections', [])
    if subs:
        for sub in subs:
            prompt_parts.append(f"  - {sub.get('title', sub.get('number', ''))}")
    else:
        prompt_parts.append("  （无子节，为最底层写作单元）")
    
    prompt_parts.append(f"""
- **推荐写作结构**：""")
    
    struct = ctype.get('suggested_structure', [])
    for i, s in enumerate(struct, 1):
        prompt_parts.append(f"  {i}. {s}")
    
    prompt_parts.append(f"""
---

## 三、KB 素材（原料，需重新组织）

以下是从知识库搜索到的相关素材。**注意：不能直接复制到教材中**。
KB 中的模板结构（如"学习目标""前置知识""精准释义"等）必须改写成自然叙述。

{kb_section}

---

## 四、写作规则（6 要素）

### 必须遵守
""")
    
    for r in requirements:
        prompt_parts.append(f"  {r}")
    
    prompt_parts.append(f"""
### 禁止
""")
    for f in forbidden[:5]:
        prompt_parts.append(f"  {f}")
    
    prompt_parts.append(f"""  🚫 不添加大纲不存在的子节
  🚫 不自创"本章小结"，用可选的要点列表自然收尾
  🚫 不直接复制KB的模板结构（"精准释义：……"）
  
---

## 五、段落与过渡

- **段落长度**：自然波动——核心内容300-600字长段，辅助30-80字短段
- **过渡**：交替使用设问、类比、递进、转折、因果，避免"下面""接下来"重复
- **公式编号**：\\tag{{{chapter_num}-序号}}
- **图引用**："如图 X-Y 所示"→描述→图→图题"图 X-Y 标题"

---

## 六、章节结尾

每章最后：
```markdown
## 思考题

1. L1概念题...
2. L2数值计算题（有具体数字）...
3. L3综合分析题...
4. L4故障诊断/工程分析题...
```""")
    
    result = '\n'.join(prompt_parts)
    
    if output_path:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(result)
        print(f"✅ 已输出: {output_path}")
    else:
        print(result)


def main():
    parser = argparse.ArgumentParser(description='生成写作指令')
    parser.add_argument('--outline', required=True, help='大纲JSON路径')
    parser.add_argument('--kb-dir', required=True, help='知识库目录')
    parser.add_argument('--chapter', required=True, help='章号')
    parser.add_argument('--section', required=True, help='节号（如 3.1）')
    parser.add_argument('-o', '--output', help='输出文件路径（默认stdout）')
    args = parser.parse_args()
    
    generate_prompt(args.outline, args.kb_dir, args.chapter, args.section, args.output)


if __name__ == '__main__':
    main()
