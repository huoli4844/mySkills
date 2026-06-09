#!/usr/bin/env python3
"""
kb-qa 知识库搜索引擎 — 支持 domain-wiki 格式的 KB 搜索。

domain-wiki 目录格式（带编号前缀）：
  30_核心概念/  40_知识要素/  50_知识点/
  60_技能点/    70_应用场景/  80_实体/  90_习题/

自动适配三种 KB 结构：
  - domain-wiki（40_知识要素/ 格式）
  - emc-textbook-wiki（知识要素/ 格式）
  - 平面（所有 .md 在同层）

用法：
  # 搜索指定 KB 目录
  python3 kb_search.py /path/to/kb "关键词"

  # 限制只搜索特定类型
  python3 kb_search.py /path/to/kb "关键词" --types concept,ke

  # 输出 JSON 供程序消费
  python3 kb_search.py /path/to/kb "关键词" --format json --max-results 10
"""
import argparse, json, os, re, sys
from pathlib import Path
from typing import Optional
from collections import OrderedDict


# ============================================================
# domain-wiki 目录映射表
# ============================================================

DOMAIN_WIKI_MAP = {
    # 逻辑名 -> (标签显示名, 匹配目录前缀列表)
    'kp':      ('知识点',     ['50_知识点', '知识点']),
    'concept': ('核心概念',   ['30_核心概念', '概念']),
    'ke':      ('知识要素',   ['40_知识要素', '知识要素']),
    'sp':      ('技能点',     ['60_技能点', '技能点']),
    'scene':   ('应用场景',   ['70_应用场景', '场景']),
    'entity':  ('实体',       ['80_实体', '实体']),
    'exercise':('习题',       ['90_习题', '习题解答', '习题']),
}

# domain-wiki 搜索优先级（从高到低）
SEARCH_PRIORITY = ['kp', 'concept', 'ke', 'sp', 'scene', 'entity', 'exercise']

# KB 嵌套搜索路径
NESTED_PATHS = [
    '电磁兼容领域/*',   # 领域/书籍子目录
    '01_领域/*',        # 替代领域目录名
    '',                 # 根目录直接搜索
]


def detect_kb_structure(kb_dir: str) -> dict:
    """扫描 KB 目录，检测结构类型并返回目录映射"""
    kb_path = Path(kb_dir).expanduser().resolve()
    if not kb_path.is_dir():
        return {"type": "invalid", "dirs": {}, "book_dirs": []}

    # 1. 检测可用的实际目录（支持多级嵌套）
    actual_dirs = {}
    # 搜索路径候选：根目录、子目录、领域/*、领域/*/子目录
    search_roots = [kb_path]
    for sub in kb_path.iterdir():
        if sub.is_dir():
            search_roots.append(sub)
            # 再深一层（电磁兼容领域/{书籍名}）
            for sub2 in sub.iterdir():
                if sub2.is_dir():
                    search_roots.append(sub2)

    for root in search_roots:
        for logical, (label, prefixes) in DOMAIN_WIKI_MAP.items():
            if logical in actual_dirs:
                continue
            for prefix in prefixes:
                p = root / prefix
                if p.is_dir():
                    actual_dirs[logical] = str(p)
                    break

    # 2. 搜索嵌套结构（domain-wiki 常见布局）
    book_dirs = []
    for subdir in kb_path.iterdir():
        if subdir.is_dir():
            # 检查子目录下是否有 30_核心概念 等
            for logical, (label, prefixes) in DOMAIN_WIKI_MAP.items():
                for prefix in prefixes:
                    if (subdir / prefix).is_dir():
                        book_dirs.append(str(subdir))
                        break
                if book_dirs and book_dirs[-1] == str(subdir):
                    break

    # 3. 检测 20_正文 目录
    body_dirs = []
    if (kb_path / '20_正文').is_dir():
        body_dirs.append(str(kb_path / '20_正文'))
    for bd in book_dirs:
        if (Path(bd) / '20_正文').is_dir():
            body_dirs.append(str(Path(bd) / '20_正文'))

    # 4. 判断结构类型
    if actual_dirs:
        struct_type = 'domain-wiki'
    elif book_dirs:
        struct_type = 'nested-domain-wiki'
    elif body_dirs:
        struct_type = 'body-only'
    else:
        struct_type = 'flat'

    return {
        "type": struct_type,
        "dirs": actual_dirs,
        "book_dirs": book_dirs,
        "body_dirs": body_dirs,
        "root": str(kb_path),
    }


def search_kb(kb_dir: str, query: str, max_results: int = 5,
              type_filter: Optional[list[str]] = None) -> list[dict]:
    """
    在 domain-wiki 知识库中搜索与 query 最匹配的内容。
    
    返回按分数降序排列的结果，每项包含：
      path, score, match_type, keyword, logical_type, label_name, content_preview
    """
    kb_path = Path(kb_dir).expanduser().resolve()
    struct = detect_kb_structure(str(kb_path))
    
    if struct['type'] == 'invalid':
        print(f"❌ KB 目录不存在: {kb_path}", file=sys.stderr)
        return []

    # 提取关键词
    keywords = _extract_keywords(query)
    if not keywords:
        keywords = [query]

    seen = set()
    results = []

    # === 策略1：domain-wiki 子目录搜索（优先级从高到低）===
    dirs_to_search = []
    for logical in SEARCH_PRIORITY:
        if type_filter and logical not in type_filter:
            continue
        if logical in struct['dirs']:
            dirs_to_search.append((logical, struct['dirs'][logical]))

    for logical, dir_path in dirs_to_search:
        label = DOMAIN_WIKI_MAP[logical][0] if logical in DOMAIN_WIKI_MAP else logical
        dir_p = Path(dir_path)
        if not dir_p.is_dir():
            continue
        for f in sorted(dir_p.iterdir()):
            if not f.name.endswith('.md') or f.name in seen:
                continue
            fstr = str(f)
            score = _score_file(f, keywords)
            if score > 0:
                seen.add(f.name)
                preview = _get_preview(f)
                results.append({
                    "path": fstr,
                    "score": score,
                    "match_type": "domain-wiki",
                    "keyword": keywords[0],
                    "logical_type": logical,
                    "label": label,
                    "filename": f.name,
                    "content_preview": preview,
                })

    # === 策略2：嵌套书籍子目录搜索（电磁兼容领域/{book}/30_核心概念/）===
    if not type_filter or 'kp' in type_filter or 'concept' in type_filter:
        for bd in struct.get('book_dirs', []):
            book_path = Path(bd)
            for logical in SEARCH_PRIORITY:
                if type_filter and logical not in type_filter:
                    continue
                prefixes = [p for _, prefixes in DOMAIN_WIKI_MAP.values() for p in prefixes[:1]]
                for prefix in [DOMAIN_WIKI_MAP.get((k,)) for k in [logical]]:
                    # Actually let me just search all subdirs
                    pass
            # 搜索 book_dir 下所有子目录的 .md 文件
            for subdir in book_path.iterdir():
                if not subdir.is_dir():
                    continue
                for f in subdir.glob('*.md'):
                    if f.name in seen:
                        continue
                    fstr = str(f)
                    score = _score_file(f, keywords)
                    if score > 0:
                        seen.add(f.name)
                        # 判断类型
                        logical = 'other'
                        for l, (label, prefixes) in DOMAIN_WIKI_MAP.items():
                            for p in prefixes:
                                if p in fstr:
                                    logical = l
                                    break
                            if logical != 'other':
                                break
                        preview = _get_preview(f)
                        results.append({
                            "path": fstr,
                            "score": score,
                            "match_type": "nested",
                            "keyword": keywords[0],
                            "logical_type": logical,
                            "label": DOMAIN_WIKI_MAP.get(logical, ['其他'])[0],
                            "filename": f.name,
                            "content_preview": preview,
                        })

    # === 策略3：20_正文 降级搜索 ===
    if len(results) < max_results:
        for bd in struct.get('body_dirs', []):
            body_path = Path(bd)
            for f in body_path.glob('*.md'):
                if f.name in seen:
                    continue
                fstr = str(f)
                score = _score_file(f, keywords) * 0.7  # 正文降权
                if score > 0:
                    seen.add(f.name)
                    preview = _get_preview(f)
                    results.append({
                        "path": fstr,
                        "score": score,
                        "match_type": "body-text",
                        "keyword": keywords[0],
                        "logical_type": "body",
                        "label": "正文",
                        "filename": f.name,
                        "content_preview": preview,
                    })

    # === 去重+排序 ===
    unique = OrderedDict()
    for r in sorted(results, key=lambda x: -x['score']):
        key = r['path']
        if key not in unique:
            unique[key] = r

    return list(unique.values())[:max_results]


def _extract_keywords(query: str) -> list[str]:
    """从查询字符串提取关键词"""
    cleaned = re.sub(r'^[\d.]+\s*', '', query)
    cleaned = re.sub(r'^\d+\.\d+\.\d+\s*', '', cleaned)
    cleaned = re.sub(r'^第[一二三四五六七八九十\d]+[章节部分]\s*', '', cleaned)
    parts = re.split(r'[与和、,，；;]', cleaned)
    keywords = [p.strip() for p in parts if len(p.strip()) >= 2]
    if cleaned.strip() and cleaned.strip() not in keywords:
        keywords.insert(0, cleaned.strip())
    return keywords


def _score_file(f: Path, keywords: list[str]) -> float:
    """对单个文件评分（0=不匹配，最高20）"""
    fname = f.name.replace('.md', '')
    score = 0.0
    
    try:
        text = f.read_text('utf-8', errors='ignore')
    except Exception:
        return 0.0

    first_line = text.strip().split('\n')[0] if text.strip() else ''

    for kw in keywords:
        kw_lower = kw.lower()
        
        # 文件名精确匹配（最高分）
        if kw_lower == fname.lower():
            score += 10.0
        elif kw_lower in fname.lower():
            score += 7.0
        
        # H1/H2 标题匹配
        if kw_lower in first_line.lower():
            score += 8.0
        
        # 内容匹配
        count = text.lower().count(kw_lower)
        if count > 0:
            score += min(count * 0.5, 5.0)

    return score


def _get_preview(f: Path, max_chars: int = 300) -> str:
    """获取文件内容预览"""
    try:
        text = f.read_text('utf-8', errors='ignore')
        # 剥离 YAML frontmatter
        body = re.sub(r'^---\n.*?\n---\n', '', text, flags=re.DOTALL)
        body = body.strip()
        if len(body) <= max_chars:
            return body
        return body[:max_chars] + '...'
    except Exception:
        return '<读取失败>'


def format_material_pack(section_title: str, results: list[dict]) -> str:
    """输出供 Agent 写作使用的素材包"""
    lines = []
    lines.append(f"## 写作素材包：{section_title}")
    lines.append("")

    if not results:
        lines.append("> ⚠️ KB 中未找到任何相关内容。将基于通用领域知识写作。")
        lines.append("")
        return "\n".join(lines)

    # 按类型分组
    by_type = OrderedDict()
    for logical in SEARCH_PRIORITY:
        label = DOMAIN_WIKI_MAP[logical][0] if logical in DOMAIN_WIKI_MAP else logical
        by_type[logical] = []
    by_type['other'] = []
    by_type['body'] = []

    for r in results:
        t = r.get('logical_type', 'other')
        if t not in by_type:
            by_type[t] = []
        by_type[t].append(r)

    for logical, items in by_type.items():
        if not items:
            continue
        label = items[0].get('label', '其他')
        lines.append(f"### {label}（{len(items)}项）")
        lines.append("")
        for item in items:
            fname = item.get('filename', '?')
            score = item.get('score', 0)
            match = item.get('match_type', '')
            lines.append(f"- **{fname}** [评分 {score}, {match}]")
            lines.append(f"  `{item['path']}`")
            preview = item.get('content_preview', '')
            if preview:
                lines.append(f"  ```\n  {preview[:200]}\n  ```")
            lines.append("")

    # 覆盖评估
    lines.append("### 覆盖评估")
    lines.append("")
    lines.append("| 类型 | 状态 |")
    lines.append("|:-----|:-----|")
    for logical in SEARCH_PRIORITY:
        label = DOMAIN_WIKI_MAP[logical][0] if logical in DOMAIN_WIKI_MAP else logical
        found = len(by_type.get(logical, []))
        mark = '✅' if found > 0 else '❌'
        lines.append(f"| {label} | {mark} ({found}项) |")
    
    lines.append("")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description='kb-qa 知识库搜索（domain-wiki 格式）')
    parser.add_argument('kb_dir', help='知识库根目录')
    parser.add_argument('query', help='搜索关键词')
    parser.add_argument('--max-results', type=int, default=5)
    parser.add_argument('--types', help='限定类型: concept,ke,kp,sp,scene,entity,exercise（逗号分隔）')
    parser.add_argument('--format', choices=['text', 'json', 'material'], default='material',
                        help='输出格式: text=列表, json=程序可消费, material=写作素材包')
    args = parser.parse_args()

    type_filter = args.types.split(',') if args.types else None
    results = search_kb(args.kb_dir, args.query, args.max_results, type_filter)

    # 结构诊断
    struct = detect_kb_structure(args.kb_dir)
    
    if args.format == 'json':
        print(json.dumps({
            "query": args.query,
            "kb_dir": args.kb_dir,
            "kb_structure": struct['type'],
            "total": len(results),
            "results": [
                {
                    "path": r['path'],
                    "score": r['score'],
                    "type": r['logical_type'],
                    "label": r['label'],
                    "filename": r['filename'],
                    "match_type": r['match_type'],
                    "preview": r['content_preview'][:200],
                }
                for r in results
            ],
        }, ensure_ascii=False, indent=2))
    elif args.format == 'material':
        print(format_material_pack(args.query, results))
    else:
        print(f"📋 查询: {args.query}")
        print(f"📁 KB: {args.kb_dir}（结构: {struct['type']}）")
        print(f"📎 匹配: {len(results)} 项")
        print()
        for r in results:
            print(f"  [{r['label']:6s}] {r['filename']:30s} 评分 {r['score']:.0f}")


if __name__ == '__main__':
    main()
