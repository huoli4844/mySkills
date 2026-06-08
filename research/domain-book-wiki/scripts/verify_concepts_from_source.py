#!/usr/bin/env python3
"""
verify-concepts-from-source.py — 核心概念定义出处验证脚本（硬约束过滤）

三步骤中的第三步：将 Agent 生成的候选概念定义在正文中精确检索，
匹配不到的自动删除，只保留可在正文中找到的定义。

用法：
  python3 verify-concepts-from-source.py <concepts.json> --source-dir <20_正文/> [--output <filtered.json>]
  python3 verify-concepts-from-source.py <concepts.json> --source-dir <20_正文/> --in-place

输入 JSON 格式（与 template_assembler.py 兼容）：
  {
    "template": "concept_template.md",
    "output_dir": "...",
    "book_id": "...",
    "book_name": "...",
    "chapter_num": "...",
    "items": [
      {
        "name": "传导耦合",
        "definition": "传导耦合是指通过导体传输的电磁干扰。...",
        "source_chapter": "第2章",
        ...
      }
    ]
  }

输出：过滤后的 JSON（移除了所有定义不可检索的概念项）
"""

from __future__ import annotations


import argparse
import json
import os
import re
import sys

from dag_constants import PipelineError
from log_utils import get_logger

log = get_logger(__name__)



def normalize(text: str) -> str:
    """标准化文本用于模糊匹配：去标点、去空格、去图片标记、去公式"""
    text = re.sub(r"!\[.*?\]\(.*?\)", "", text)  # 去图片
    text = re.sub(r"\$\$.*?\$\$", "", text, flags=re.DOTALL)  # 去块公式 $$...$$
    text = re.sub(r"\$[^$\n]+\$", "", text)  # 去行内公式 $...$
    text = re.sub(
        r"[\s，。、；：\u201c\u201d\u2018\u2019！（）：？•·\[\]{}\u3010\u3011\u300a\u300b\u300c\u300d\u300e\u300f—…\-\n\r\t]",
        "",
        text,
    )
    return text


def _has_formula(text: str) -> bool:
    """检查文本是否含公式标记"""
    return bool(re.search(r"\$[^$]+\$|\\\[|\\\(|\\begin\{", text))


def _strip_formulas(text: str) -> str:
    """将公式替换为 [公式] 占位符"""
    text = re.sub(r"\$\$.*?\$\$", "[公式]", text, flags=re.DOTALL)
    text = re.sub(r"\$[^$\n]+\$", "[公式]", text)
    return text


def find_definition_in_sources(definition: str, source_dir: str, source_chapter: str = "", max_files: int = 5) -> dict:
    """
    在正文文件中搜索定义文本。

    返回：
        {
            "found": True/False,
            "in_file": "第2章.md" or None,
            "match_type": "exact" / "fuzzy" / None,
            "reason": "说明"
        }
    """
    if not definition or not source_dir:
        return {"found": False, "in_file": None, "match_type": None, "reason": "定义为空或无源目录"}

    # 收集候选文件
    source_files = []
    if os.path.isdir(source_dir):
        for f in sorted(os.listdir(source_dir)):
            if f.endswith(".md") and os.path.isfile(os.path.join(source_dir, f)):
                source_files.append(f)

    # 如果指定了章节，优先匹配
    if source_chapter:
        ch_num = re.sub(r"[^0-9]", "", source_chapter)
        chapter_files = [f for f in source_files if ch_num in f]
        if chapter_files:
            source_files = chapter_files + [f for f in source_files if f not in chapter_files]

    # 限制搜索文件数
    source_files = source_files[:max_files]

    # 标准化定义文本
    defn_clean = normalize(definition[:150])

    for sf in source_files:
        sf_path = os.path.join(source_dir, sf)
        try:
            with open(sf_path, encoding="utf-8") as f:
                src_text = f.read()

            # 1. 精确匹配（原文本片段）
            short_defn = definition[:80].replace("\n", " ")
            if short_defn in src_text:
                return {
                    "found": True,
                    "in_file": sf,
                    "match_type": "exact",
                    "reason": f"精确匹配: {short_defn[:50]}...",
                }

            # 1b. v40.0: 公式跳窗匹配（若定义含公式，替换为 [公式] 后搜索）
            if _has_formula(definition[:80]):
                formula_defn = _strip_formulas(definition[:100]).replace("\n", " ")
                formula_src = _strip_formulas(src_text)
                if formula_defn in formula_src:
                    return {"found": True, "in_file": sf, "match_type": "formula", "reason": "公式跳窗匹配"}

            # 2. 模糊匹配（去标点后）
            src_clean = normalize(src_text)
            if defn_clean in src_clean:
                return {"found": True, "in_file": sf, "match_type": "fuzzy", "reason": "模糊匹配（去标点后一致）"}

            # 3. v40.0: 前40字去标点匹配（给公式留出空间，阈值从80降到40）
            head40 = normalize(definition[:50])
            if head40 in src_clean:
                return {"found": True, "in_file": sf, "match_type": "fuzzy", "reason": "前50字去标点+去公式匹配"}

        except Exception as e:
            log.debug(f"定义匹配失败: {e}")
            continue

    return {
        "found": False,
        "in_file": None,
        "match_type": None,
        "reason": f"在 {len(source_files)} 个正文文件中均未找到",
    }


def filter_concepts_by_source(
    json_path: str, source_dir: str, output_path: str | None = None, in_place: bool = False, verbose: bool = True
) -> dict:
    """
    过滤概念 JSON，移除所有定义不可检索的概念项。

    返回过滤结果统计。
    """
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)

    items = data.get("items", [])
    total = len(items)
    kept = []
    removed = []

    for item in items:
        name = item.get("name", "?")
        definition = item.get("definition", "")
        source_chapter = item.get("source_chapter", data.get("source_chapter", ""))
        source_from = item.get("source_from", "")

        # 始终用 definition 作为匹配文本（source_from 是节号引用，不是正文内容）
        src_to_check = definition if definition else source_from

        result = find_definition_in_sources(src_to_check, source_dir, source_chapter)

        item["_source_verification"] = result

        if result["found"]:
            kept.append(item)
            if verbose:
                log.success(f"  ✅ {name}: {result['reason']}")
        else:
            removed.append(item)
            if verbose:
                log.error(f"  ❌ {name}: {result['reason']}")

    # 更新数据
    data["items"] = kept
    data["_source_verification_summary"] = {
        "total": total,
        "kept": len(kept),
        "removed": len(removed),
        "removed_names": [item.get("name", "?") for item in removed],
    }

    # 输出
    if in_place:
        output_path = json_path

    if output_path:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        if verbose:
            log.info(f"\n📝 过滤结果已保存: {output_path}")

    return {
        "total": total,
        "kept": len(kept),
        "removed": len(removed),
        "removed_names": [item.get("name", "?") for item in removed],
    }


def main():
    parser = argparse.ArgumentParser(
        description="核心概念定义出处验证 — 硬约束过滤\n\n"
        "将 Agent 生成的候选概念定义在正文中精确检索，\n"
        "匹配不到的自动删除，只保留可在正文中找到的定义。"
    )
    parser.add_argument("input", help="概念 JSON 文件路径（items[] 格式）")
    parser.add_argument("--source-dir", "-s", required=True, help="20_正文/ 目录路径")
    parser.add_argument("--output", "-o", help="过滤后 JSON 输出路径（默认不保存）")
    parser.add_argument("--in-place", "-i", action="store_true", help="直接修改输入 JSON 文件（覆盖）")
    parser.add_argument("--quiet", "-q", action="store_true", help="安静模式（只输出统计）")
    parser.add_argument("--json", action="store_true", help="JSON 输出模式（供 ScriptRunner 解析）")

    args = parser.parse_args()

    if not os.path.exists(args.input):
        log.error(f"❌ 输入文件不存在: {args.input}")
        raise PipelineError(f"输入文件不存在: {args.input}")
    if not os.path.isdir(args.source_dir):
        log.error(f"❌ 正文目录不存在: {args.source_dir}")
        raise PipelineError(f"正文目录不存在: {args.source_dir}")

    if not args.quiet:
        log.info("🔍 核心概念定义出处验证")
        log.info(f"   输入: {args.input}")
        log.info(f"   正文: {args.source_dir}")
        log.info("")

    result = filter_concepts_by_source(
        args.input,
        args.source_dir,
        output_path=args.output,
        in_place=args.in_place or False,
        verbose=not args.quiet and not args.json,
    )

    if args.json:
        # v40.0: 结构化 JSON 输出（供 ScriptRunner 解析）
        log.info(f"JSON_OUTPUT:{json.dumps({'total': result['total'], 'verified': result['kept'], 'removed': result['removed'], 'items': [{'name': n} for n in result['removed_names']]}, ensure_ascii=False)}")
    elif not args.quiet:
        log.info(f"\n{'='*50}")
        log.info("  验证结果")
        log.info(f"{'='*50}")
        log.info(f"  总计: {result['total']} 个候选概念")
        log.success(f"  ✅ 保留: {result['kept']} 个（定义可在正文中检索）")
        log.error(f"  ❌ 删除: {result['removed']} 个（定义非正文原句）")
        if result["removed"] > 0:
            log.info("\n  被删除的概念:")
            for name in result["removed_names"]:
                log.info(f"    - {name}")
        log.info("\n  建议: 被删除的概念需要 Agent 重新从正文提取准确的定义")

    # 返回码：全通过=0，有删除=1
    if result["removed"] > 0:
        raise PipelineError(f"Deleted {result['removed']} concepts not found in source")


if __name__ == "__main__":
    try:
        main()
    except PipelineError as e:
        log.error(str(e))
        raise
