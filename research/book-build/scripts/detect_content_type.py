#!/usr/bin/env python3
"""
内容类型检测 — 根据章节标题和 KB 素材判断最适合的写作模式。

用法：
  python3 detect_content_type.py "<章节标题>" [--has-formula yes|no] [--has-example yes|no] [--kbsource concept|kp|none]

示例：
  python3 detect_content_type.py "1.1 某领域的发展历史"
  python3 detect_content_type.py "2.1.4 某原理" --has-formula yes
"""
import argparse, json, re, sys


CONTENT_TYPES = {
    "historical": {
        "label": "历史叙事型",
        "description": "按时间线叙述，一气呵成，无公式",
        "triggers": ["发展历史", "发展历程", "演进", "沿革", "历史", "起源", "背景"],
        "structure": ["引出背景", "时间线叙事（事件A→事件B→事件C）", "总结性收尾"],
    },
    "conceptual": {
        "label": "概念解构型",
        "description": "先给出定义，再分解要素，最后举例",
        "triggers": ["概念", "定义", "含义", "内涵", "基本概念", "术语", "概述", "绪论"],
        "structure": ["一句话定义", "分解要素（要素1/要素2/要素3）", "扩展说明或举例"],
    },
    "derivational": {
        "label": "原理推导型",
        "description": "物理直观引入 → 公式 → 参数解释 → 实例 → 启示",
        "triggers": ["原理", "方程", "公式", "模型", "推导", "关系", "定理", "定律"],
        "structure": ["物理直观/类比引入", "公式推导", "式中变量解释", "实例计算", "分析启示"],
    },
    "system_diagram": {
        "label": "系统组成型",
        "description": "框图描述 → 各部件功能 → 工作流程",
        "triggers": ["组成", "结构", "系统", "框图", "架构", "模块", "部件", "组件"],
        "structure": ["总体框图描述", "各部件功能逐一说明", "信号/工作流程"],
    },
    "enumeration": {
        "label": "分类枚举型",
        "description": "并列子主题，每个 100-300 字，可配表格",
        "triggers": ["分类", "类型", "种类", "特性", "特点", "指标", "参数", "特征"],
        "structure": ["1．主题1 ...", "2．主题2 ...", "3．主题3 ...", "(可选)对比总结表格"],
    },
    "engineering_case": {
        "label": "工程案例型",
        "description": "问题 → 方案 → 实施 → 效果",
        "triggers": ["案例", "应用", "实例", "工程", "实践", "方法", "设计", "实现"],
        "structure": ["问题/需求描述", "方案设计", "实施过程", "效果分析"],
    },
    "mixed": {
        "label": "复合型",
        "description": "以上多种模式的组合",
        "triggers": [],
        "structure": ["根据素材内容灵活组合以上模式"],
    },
}


def detect_content_type(title: str, has_formula: bool = False, has_example: bool = False,
                        kbsource: str = "none") -> dict:
    """
    根据标题和 KB 素材信息判断内容类型。
    
    返回:
    {
        "primary_type": "conceptual",
        "description": "...",
        "reasoning": "标题含'概念'关键词",
        "suggested_structure": [...],
        "suggested_intro": "..."
    }
    """
    title_lower = title.lower()
    scores = {}

    for type_name, type_info in CONTENT_TYPES.items():
        score = 0
        for trigger in type_info["triggers"]:
            if trigger in title:
                # 触发词越长且越靠前，权重越高
                position_bonus = 1.5 if title.find(trigger) < len(title) * 0.3 else 1.0
                score += len(trigger) * 0.5 * position_bonus

        # 公式加分
        if has_formula and type_name == "derivational":
            score += 5
        if has_example and type_name == "engineering_case":
            score += 3

        # KB 素材类型加分
        if kbsource == "concept" and type_name == "conceptual":
            score += 4
        if kbsource == "kp" and type_name == "derivational":
            score += 3

        if score > 0:
            scores[type_name] = score

    if not scores:
        primary = "mixed"
        reasoning = "未检测到明显的类型触发词，使用复合型"
    else:
        primary = max(scores, key=scores.get)
        reasoning = f"触发词评分: {', '.join(f'{k}={v}' for k, v in sorted(scores.items(), key=lambda x: -x[1]))}"

    type_info = CONTENT_TYPES.get(primary, CONTENT_TYPES["mixed"])

    # 建议开头句
    intro_templates = {
        "historical": f"要理解{title}，需要从其历史沿革说起。",
        "conceptual": f"在讨论具体技术之前，首先需要明确{title}的含义。",
        "derivational": f"下面通过数学推导来定量分析{title}。",
        "system_diagram": f"图X.X展示了{title}的系统组成框图。",
        "enumeration": f"从不同维度来看，{title}主要体现在以下几个方面。",
        "engineering_case": f"下面通过一个工程实例来说明{title}的具体应用。",
        "mixed": "",
    }

    return {
        "primary_type": primary,
        "label": type_info["label"],
        "description": type_info["description"],
        "reasoning": reasoning,
        "suggested_structure": type_info["structure"],
        "suggested_intro": intro_templates.get(primary, ""),
    }


def main():
    parser = argparse.ArgumentParser(description='内容类型检测')
    parser.add_argument('title', help='章节标题')
    parser.add_argument('--has-formula', choices=['yes', 'no'], default='no')
    parser.add_argument('--has-example', choices=['yes', 'no'], default='no')
    parser.add_argument('--kbsource', choices=['concept', 'kp', 'ke', 'none'], default='none')
    parser.add_argument('--format', choices=['json', 'text'], default='text')
    args = parser.parse_args()

    result = detect_content_type(
        args.title,
        has_formula=args.has_formula == 'yes',
        has_example=args.has_example == 'yes',
        kbsource=args.kbsource,
    )

    if args.format == 'json':
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"📖 章节：{args.title}")
        print(f"🏷️  类型：{result['label']}（{result['primary_type']}）")
        print(f"📝 判断依据：{result['reasoning']}")
        print()
        print("推荐写作结构：")
        for i, step in enumerate(result['suggested_structure'], 1):
            print(f"  {i}. {step}")
        if result['suggested_intro']:
            print()
            print(f"💡 建议开头：{result['suggested_intro']}")


if __name__ == '__main__':
    main()
