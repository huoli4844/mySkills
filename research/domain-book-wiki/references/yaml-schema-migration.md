# YAML Schema Migration Guide

## Problem

Existing `.dag/第N章/data/*.yaml` files were created with **v50.0 template** schema.
The current pipeline (`yaml_pre_validate.py` + template files) expects **v50.7+ schema**.

When running `pipeline batch`, yaml_pre_validate blocks with:

```
ERROR: bd.solved_problem: 必填字段 'solved_problem' 为空或占位符
WARN: 不识别字段名: additional_explanations, core_concept_map_source, ...
WARN: bd 中缺失字段 'confidence', 'confidence_note', 'entity_type', 'upstream_downstream'
```

## Schema Changes (v50.0 → v50.7+)

### Removed fields (in old YAML, not in new template)
- `additional_explanations` → delete or migrate to `solution_detail`
- `core_concept_map_source` → delete
- `definition_source` → delete (use `source_from` in frontmatter)
- `figure_references` → delete
- `formula_references` → delete
- `references` → delete

### New required fields (missing in old YAML)
- `solved_problem` (concepts) — describe what problem this concept solves
- `upstream_downstream` (all types) — knowledge graph relationship
- `entity_type` (entities) — entity type classification
- `confidence` / `confidence_note` — now required in bd body (not just frontmatter)

## Fix Options

### Option A: Relax validation (fast, 5 min)
In `yaml_pre_validate.py`, change `solved_problem` from ERROR to WARN
for concept types. This lets pipeline pass while keeping other checks.

### Option B: Migration script (thorough, 1-2 hr)
Create `scripts/migrate_yaml_schema.py` that:
1. Walks `.dag/*/data/*.yaml`
2. Removes old fields (`additional_explanations` etc.)
3. Adds empty new fields (`solved_problem: ""`, `upstream_downstream: ""`)
4. Validates output with yaml_pre_validate
5. Runs `pipeline batch --no-cache` to verify

## Verification

After migration:
```bash
pipeline batch -w $BOOK_DIR --book-id $BOOK_ID --no-cache 2>&1 | grep -E "质量闸门|done|failed"
```

All chapters should pass through quality gates. Remaining failures
would be genuine content issues (not schema format issues).
