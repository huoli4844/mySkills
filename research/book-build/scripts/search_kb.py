#!/usr/bin/env python3
"""
知识库搜索工具 — 对教材章节标题搜索指定 KB 目录，返回匹配素材。

用法：
  python3 search_kb.py <KB_DIR> "<章节标题>" [--max-results N] [--format json|text]

示例：
  python3 search_kb.py /Users/me/知识库/某领域 "某技术原理"
  python3 search_kb.py /Users/me/知识库 "1.1 研究背景与意义" --max-results 3 --format json
"""
import argparse, json, os, re, sys
from pathlib import Path


def extract_keywords(title: str) -> list[str]:
    """从章节标题提取搜索关键词"""
    cleaned = re.sub(r'^[\d.]+\s*', '', title)
    cleaned = re.sub(r'^第[一二三四五六七八九十\d]+章\s*', '', cleaned)
    parts = re.split(r'[与和、,，]', cleaned)
    keywords = [p.strip() for p in parts if len(p.strip()) >= 2]
    if len(cleaned.strip()) >= 4 and cleaned.strip() not in keywords:
        keywords.insert(0, cleaned.strip())
    return keywords


def search_kb(kb_dir: str, keywords: list[str], max_results: int = 5) -> list[dict]:
    """
    在知识库中搜索与章节最匹配的内容。

    评分策略:
      文件名精确匹配 = 10分
      H1/H2 标题匹配 = 8分
      文件名子串匹配 = 7分
      内容包含关键词 = 5分
    """
    kb_path = Path(kb_dir).expanduser().resolve()
    if not kb_path.is_dir():
        print(f"❌ KB 目录不存在: {kb_path}", file=sys.stderr)
        return []

    results = []
    seen = set()

    for kw in keywords:
        # 方式1: 文件名匹配
        for f in kb_path.rglob(f'*{kw}*.md'):
            fstr = str(f)
            if fstr not in seen:
                seen.add(fstr)
                results.append({"path": fstr, "match_type": "filename", "keyword": kw, "score": 10})

        # 方式2: 内容搜索
        for f in kb_path.rglob('*.md'):
            fstr = str(f)
            if fstr in seen:
                continue
            try:
                text = f.read_text('utf-8', errors='ignore')
                if kw.lower() in text.lower():
                    seen.add(fstr)
                    # 检查是否在标题中
                    first_line = text.strip().split('\n')[0] if text.strip() else ''
                    score = 8 if first_line.startswith('#') else 5
                    # 获取匹配上下文
                    context_lines = []
                    for i, line in enumerate(text.split('\n')):
                        if kw.lower() in line.lower():
                            context_lines.append(f"  L{i+1}: {line.strip()[:120]}")
                    results.append({
                        "path": fstr,
                        "match_type": "title" if score == 8 else "content",
                        "keyword": kw,
                        "score": score,
                        "context": context_lines[:3],
                        "first_line": first_line,
                    })
            except Exception:
                continue

    # 去重+按分数排序（对 path 去重）
    unique = {}
    for r in results:
        p = r["path"]
        if p not in unique or r["score"] > unique[p]["score"]:
            unique[p] = r

    sorted_results = sorted(unique.values(), key=lambda x: -x["score"])
    return sorted_results[:max_results]


def read_kb_content(results: list[dict]) -> list[dict]:
    """读取搜索结果的完整内容，剥离 YAML frontmatter"""
    enriched = []
    for r in results:
        try:
            raw = Path(r["path"]).read_text('utf-8', errors='ignore')
            body = re.sub(r'^---\n.*?\n---\n', '', raw, flags=re.DOTALL)
            enriched.append({
                **r,
                "content": body,
                "content_length": len(body),
                "full_raw": raw,
            })
        except Exception as e:
            enriched.append({**r, "content": f"<读取失败: {e}>", "content_length": 0})
    return enriched


def format_as_material(section_title: str, enriched: list[dict]) -> str:
    """输出写作素材包（Markdown）"""
    lines = []
    lines.append(f"## 写作素材包：{section_title}")
    lines.append("")

    if not enriched:
        lines.append("> ⚠️ KB 中未找到任何相关内容。将基于通用知识写作。")
        lines.append("")
        return "\n".join(lines)

    for i, item in enumerate(enriched, 1):
        lines.append(f"### 来源{i}：{item['path']}")
        lines.append(f"- **匹配方式**：{item['match_type']}（关键词：{item['keyword']}，评分：{item['score']}）")
        lines.append(f"- **内容长度**：{item['content_length']} 字符")
        if item.get('first_line'):
            lines.append(f"- **标题**：{item['first_line'].lstrip('# ')}")
        lines.append("")
        lines.append("```")
        # 只显示前500字符
        preview = item['content'][:500]
        lines.append(preview)
        if item['content_length'] > 500:
            lines.append("... [内容截断] ...")
        lines.append("```")
        lines.append("")

    # 覆盖评估
    lines.append("### 覆盖评估")
    lines.append("")
    lines.append("| 维度 | 状态 |")
    lines.append("|:-----|:-----|")
    types_covered = set()
    for item in enriched:
        p = item['path']
        if re.search(r'/[近]?概念/', p):
            types_covered.add('核心概念')
        elif re.search(r'/知[识]?[识]?要素/', p):
            types_covered.add('公式/方法')
        elif re.search(r'/知[识]?[识]?点/', p):
            types_covered.add('完整知识点')
        elif re.search(r'/技[能]?[能]?点/', p):
            types_covered.add('操作技能')
        elif re.search(r'/场[景]?[景]?/', p):
            types_covered.add('应用案例')

    has_concept = any('核心概念' in t for t in types_covered)
    has_formula = any('公式/方法' in t for t in types_covered)
    has_kp = any('完整知识点' in t for t in types_covered)
    has_example = any('应用案例' in t for t in types_covered)

    lines.append(f"| 核心概念 | {'✅' if has_concept else '❌'} |")
    lines.append(f"| 公式/方法 | {'✅' if has_formula else '❌'} |")
    lines.append(f"| 完整知识点 | {'✅' if has_kp else '❌'} |")
    lines.append(f"| 工程案例 | {'✅' if has_example else '⚠️ 未在KB中找到'} |")
    lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description='知识库搜索：为教材章节搜索 KB 素材')
    parser.add_argument('kb_dir', help='知识库根目录路径')
    parser.add_argument('title', help='章节标题')
    parser.add_argument('--max-results', type=int, default=5, help='最大返回结果数')
    parser.add_argument('--format', choices=['json', 'text'], default='text', help='输出格式')
    args = parser.parse_args()

    keywords = extract_keywords(args.title)
    results = search_kb(args.kb_dir, keywords, args.max_results)
    enriched = read_kb_content(results)

    if args.format == 'json':
        output = {
            "section_title": args.title,
            "keywords": keywords,
            "total_results": len(enriched),
            "kb_directory": args.kb_dir,
            "sources": [
                {
                    "path": r["path"],
                    "score": r["score"],
                    "match_type": r["match_type"],
                    "content_length": r["content_length"],
                }
                for r in enriched
            ],
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        print(f"📋 标题：{args.title}")
        print(f"🔑 关键词：{'、'.join(keywords)}")
        print(f"📁 KB 目录：{args.kb_dir}")
        print(f"📎 匹配结果：{len(enriched)} 项\n")
        print(format_as_material(args.title, enriched))


if __name__ == '__main__':
    main()
