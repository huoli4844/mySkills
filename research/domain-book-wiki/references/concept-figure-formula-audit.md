# Concept Figure & Formula Audit Guide

## When to Use
When asked about concept quality (figure/formula references) or when fixing cross-concept data consistency issues.

## Audit Approach: Always Scan ALL Chapters

When someone asks about one chapter's concept quality, **audit all chapters** first. Most concept quality issues are systemic, not chapter-specific. The same Agent mistake patterns repeat across all chapters.

```python
# Quick audit script pattern:
import yaml, re
from collections import defaultdict
issues = []
for ch in ["第1章", "第2章", "第3章"]:
    with open(f"data/{ch}/concepts.yaml") as f:
        data = yaml.safe_load(f) or []
    for item in data:
        bd = item.get("bd", {})
        fr = bd.get("formula_references","")
        fig = bd.get("figure_references","")
        if fr and fr != "无" and not re.search(r'\$\$', fr):
            issues.append(f"TEXT_FORMULA {ch}/{item['name']}")
        if re.findall(r'表\d+[-–]\d+', fig):
            issues.append(f"TABLE_IN_FIGURE {ch}/{item['name']}")
```

## 4 Checks to Run

### Check 1: formula_references text-only (no $$)
Regex: `formula_references` value is non-empty, not "无", but contains no `$$`
Fix: Replace with actual `$$...$$` LaTeX or change to "无". Move cross-references to `additional_explanations`.

### Check 2: figure_references contains table references
Regex: `表\d+[-–]\d+` found in `figure_references`
Fix: Remove table references. Move table descriptions to `additional_explanations`.

### Check 3: Same figure referenced by 2+ concepts (shared figure)
Algorithm: Collect all `图X-X` from all concepts' `figure_references`. Flag any `图X-X` appearing in ≥2 concepts.
Legitimate exception: Figures that explicitly illustrate multiple sibling concepts (e.g. 图1-2 shows "多种电磁耦合" → valid for both 辐射耦合 and 传导耦合).
Fix: Remove from the less-specific concept. Rule: figure must be **exclusively** for explaining this concept.

### Check 4: Same figure referenced by parent AND child/sub-concept
Flag pattern: Concept A (parent) and Concept B (sub-concept of A) both reference 图X-X.
Example: 电磁辐射 (parent) and 基本电振子 (sub-concept) both referenced 图2-7、图2-8.
Fix: Only the sub-concept (closest match) keeps the figure reference. The parent should not include its sub-concepts' exclusive figures.

## Validation Commands

```bash
# YAML-level pre-build check
python3 -c "
import yaml, re
for ch in ['第1章','第2章','第3章']:
    with open(f'data/{ch}/concepts.yaml') as f:
        for item in yaml.safe_load(f) or []:
            bd=item.get('bd',{})
            fr=bd.get('formula_references','')
            fig=bd.get('figure_references','')
            if fr and fr!='无' and not re.search(r'\$\$',fr):
                print(f'FAIL TEXT_FORMULA: {ch}/{item[\"name\"]}')
            if '表' in fig:
                print(f'FAIL TABLE_IN_FIG: {ch}/{item[\"name\"]}')
"

# Post-build check (via comprehensive-content-check)
python3 scripts/comprehensive-content-check.py -w $BOOK_DIR

# Shared figure detection (via dag_quality)
python3 -c "
from dag_quality import check_shared_figures
shared = check_shared_figures('/path/to/wiki', '01_book')
for fig, concepts in shared.items():
    print(f'SHARED: {fig} by {concepts}')
"
```

## Origin
Pattern discovered during v36.0 audit of 24 concepts across 3 chapters. 4 shared figures, 1 text-formula, 1 table-in-figure found and fixed.
