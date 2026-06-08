# KG Field Data Flow — Adding a New Frontmatter Field to the Knowledge Graph

When a new field is added to a node type's frontmatter (e.g. `bloom_level`, `difficulty`), it must be wired through **6 spots** in the chain. Missing any one means the field exists in the `.md` file but is invisible to the L2/L3/L4 overview generation.

## The 6-Spot Chain

```
YAML  ──①──→ build_kb_files.py  ──②──→ .md template  ──③──→ kb_graph.py  ──④──→ generate_index_data.py  ──⑤──→ L2/L3/L4 template  ──⑥──→ index-assembler.py
```

### ① YAML Schema (opt-in, recommended)
- `scripts/schemas/<type>.schema.json` — add field to `properties` of `fm`
- **When**: all 4 types (kp/sp/scene/exercise) have Bloom
- **Skip**: if the field is truly optional and schema is permissive

### ② BUILDER_CONFIG → fm_extra_keys_from_item_fm
- `scripts/build_kb_files.py` — add field name to the `fm_extra_keys_from_item_fm` array for each node type that uses it
- This makes the YAML's `fm.field` flow into the generated `.md` frontmatter via `{{field}}` in the template
- **KP**: `scripts/build_kb_files.py` line ~208
- **SP**: line ~224
- **Scene**: line ~256
- **Exercise**: line ~304

### ③ .md Template
- `assets/templates/<type>.md` — add `field: {{field}}` to the frontmatter YAML
- The template-assembler replaces `{{field}}` with the value from BUILDER_CONFIG's extra_fm

### ④ kb_graph.py — KG Database (3 sub-spots!)
When the field should be queryable in the knowledge graph for L2/L3/L4:

**a) SCHEMA_SQL** — add column to `CREATE TABLE nodes`
- `scripts/kb_graph.py` ~line 27-39
- ```sql
  field_name TEXT DEFAULT '',
  ```

**b) _process_file node dict** — extract from frontmatter
- `scripts/kb_graph.py` ~line 698-710
- ```python
  "field_name": str(fm.get("field_name", "") or ""),
  ```

**c) build() INSERT statement** — include in VALUES
- `scripts/kb_graph.py` ~line 365-372
- Add column name to INSERT columns AND corresponding `?`/value in VALUES tuple

> ⚠️ **Critical**: These 3 sub-spots (a, b, c) must always be updated together. Forgetting (c) causes a SQLite column count mismatch error at runtime. Forgetting (a) means the column doesn't exist — but SQLite is permissive: `INSERT` silently drops the extra value. If (b) is missing, the field is always empty string.

### ⑤ generate_index_data.py — _build_graph_section
- `scripts/generate_index_data.py` ~line 280-300 (Section 9 for L2 learning path)
- Query the field with `SELECT n.field_name FROM nodes n WHERE n.type='knowledge' ...`
- Pass into the result dict: `result["field_name_based"] = computed_value`

### ⑥ L2/L3/L4 Template + index-assembler.py
- `assets/templates/book_overview.md` — add `{{field_section}}` placeholder
- `scripts/index-assembler.py` `build_book_overview()` — pass `field_section=data.get("field_section", "（待补充）")` to `fill_template()`
- `scripts/generate_index_data.py` `make_index_json("book_overview", ...)` — pass `field_section=graph_data.get("field_name")` as extra kwarg

## Example: Adding `bloom_level` (v36.0)

| # | Spot | File | Change |
|---|------|------|--------|
| ① | Schema | `schemas/kps.schema.json` | `"bloom_level": { "type": "string" }` (already existed) |
| ② | BUILDER_CONFIG | `build_kb_files.py` | `fm_extra_keys_from_item_fm: ["bloom_level"]` (already existed) |
| ③ | Template | `assets/templates/knowledge_template.md` | `bloom_level: {{bloom_level}}` (already existed) |
| ④a | SCHEMA_SQL | `kb_graph.py` | `bloom_level TEXT DEFAULT ''` |
| ④b | _process_file | `kb_graph.py` | `"bloom_level": str(fm.get("bloom_level", "") or "")` |
| ④c | INSERT | `kb_graph.py` | Include `bloom_level` in column list + VALUES |
| ⑤ | generate_index_data | `generate_index_data.py` | `SELECT n.bloom_level` → Bloom-progressive path algorithm |
| ⑥ | Template + assembler | `book_overview.md` | Section title update + `{{learning_path_v2}}` (template already had it) |

## When to Skip Which Spots

| Scenario | Skip | Reason |
|----------|------|--------|
| Field only needed in rendered `.md`, not in KG analysis | Skip ④-⑥ | KG doesn't need to query it |
| Field only for L2 display, not L3/L4 | Skip ⑥ for L3/L4 templates | Only L2 template uses it |
| Field is computed from other data, not FM | Skip ①-③ | Not a direct FM field |
