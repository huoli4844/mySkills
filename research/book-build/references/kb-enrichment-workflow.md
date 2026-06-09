# KB Enrichment Workflow（知识库素材扩展工作流）

## Purpose

Before writing any chapter section, enrich your writing material by searching the KB for multiple related terms. Do NOT rely on a single search — each related keyword may reveal different KB pages.

## Workflow

### Step 1: Extract all key terms from the chapter outline

For each section heading, extract 2-5 search terms:

```
Example for Ch9:
  9.1.1 电磁兼容预测的概念 → "电磁兼容预测", "EMC预测"
  9.2.1 四级筛选 → "四级筛选", "幅度筛选", "频率筛选"
  9.3.3 场线耦合 → "场线耦合", "Taylor模型", "传输线耦合"
```

### Step 2: Search the KB for each term

```bash
python3 <skill_dir>/kb_search.py /path/to/kb "电磁兼容预测" --max-results 10 --format material
python3 <skill_dir>/kb_search.py /path/to/kb "四级筛选" --max-results 5 --format material
python3 <skill_dir>/kb_search.py /path/to/kb "场线耦合" --max-results 5 --format material
```

Where `<skill_dir>` is the kb-qa skill's script directory (`/Users/huoli4844/.hermes/skills/research/kb-qa/scripts/kb_search.py`).

### Step 3: Categorize retrieved results

Note for each:
- **Node type**: 概念 (0.95, authoritative) / 知识点 (comprehensive) / 知识要素 (formulas) / 正文 (raw source)
- **Score**: Higher = better match

### Step 4: Read best-matching pages

Use read_file on the best-matched pages. 概念/ pages provide authoritative definitions; 知识点/ pages provide comprehensive topic coverage; 正文/ chapters provide direct source depth.

### Step 5: Identify coverage gaps

Use the kb-qa coverage table:

| Type | Status |
|:-----|:-------|
| 核心概念 | ✅ (3项) |
| 知识要素 | ✅ (1项) |
| 知识点 | ✅ (2项) |

If an important concept is ❌, note it but do NOT create KB pages mid-writing.

### Step 6: Integrate into writing

- **概念/ pages**: Quote definitions verbatim (strip YAML frontmatter + wikilinks)
- **知识要素/ pages**: Use formulas as reference, verify LaTeX syntax
- **知识点/ pages**: Use comprehensive overviews to ensure no sub-topic missed
- **正文/ chapters**: Use as direct source for depth and technical detail

## Real Example: Chapter 9 电磁兼容预测

| Search term | Best match | Writing value |
|:------------|:-----------|:--------------|
| `电磁兼容预测` | 概念/电磁兼容性预测.md (0.95) | Authoritative definition + M=P-S equation |
| `四级筛选` | 技能点/EMC四级筛选预测技能.md | Operational flow with threshold values |
| `场线耦合` | 正文/第10章.md | Taylor model derivation |
| `仿真软件` | 路宏敏第12章 (正文) | Software comparison table |

## When to USE

- Always when the KB has domain-wiki structure (概念/KE/KP/正文 directories)
- Before each chapter to ensure full content coverage

## When NOT to use

- kb_search.py is READ-ONLY — does not modify the KB
- Do NOT create KB pages as part of enrichment (that's kb-qa Phase C-D)
