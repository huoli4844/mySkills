# Quality Gate Architecture

## Overview

The domain-wiki pipeline has multiple quality gates at different phases. Each gate catches a specific class of issue. They are designed to catch problems EARLY — at the YAML level, before build — to avoid wasting time on failed builds.

```
Agent writes YAML → Phase 0.5 (yaml_pre_validate) → Phase 1 (build_kb_files) → Phase 2 (validate_phase_output) → Phase 3 (cleanup/fix)
                                                                                                              ↻ (auto-fix loop)
```

## Gate 1: yaml_pre_validate (Phase 0.5)

**When**: After Agent writes YAML, before build_kb_files.

**Usage**: 
```bash
# Per-file check
python3.12 yaml_pre_validate.py .dag/第N章/data/concepts.yaml

# Full chapter (with source-level checks)
python3.12 yaml_pre_validate.py --book-dir $BOOK_DIR -c N -v
```

**Checks** (in order):

| Check | What it catches | Severity |
|:------|:----------------|:---------|
| `check_schema` | Missing name/file/fm/bd, wrong field types | warning |
| `check_confidence` | confidence not matching node type's required value | warning |
| `check_required_fields` | Critical bd fields empty (definition_sentence etc.) | warning |
| `check_bloom` | Bloom level out of range for node type | warning |
| `check_definition_sentence` | Missing marker words (是指/称为/即) | warning |
| `check_name_format` | Non-standard naming patterns | warning |
| `check_mathematical_model` | Theory-concept (name contains 理论/模型/原理) has no formula | warning |
| `check_file_naming` | Exercise/solution file naming violations | warning |
| `check_source_from_format` **(v52.2)** | source_from contains redundant "第N章 " prefix (template adds it) | warning |
| `check_source_mathematical_model` **(v52.2)** | Source section has `$$...$$` formulas but YAML mathematical_model is "无" | warning |
| `check_bd_coverage` **(v52.2)** | bd has too few meaningful fields (< threshold per node type) | warning |
| `check_template_field_names` | bd field names not matching template {{xxx}} placeholders | warning |

**Coverage thresholds** (`check_bd_coverage`):

| Node Type | bd fields | Min filled | Min % |
|:----------|:---------:|:----------:|:-----:|
| concept | ~33 | ≥25 | 76% |
| ke | ~19 | ≥14 | 74% |
| entity | ~17 | ≥13 | 76% |
| kp | ~42 | ≥32 | 76% |
| sp | ~32 | ≥20 | 63% |
| scene | ~28 | ≥14 | 50% |
| exercise | ~5 | ≥4 | 80% |
| solution | ~18 | ≥14 | 78% |

## Gate 2: validate_phase_output (after build)

**When**: After build_kb_files generates .md files for a phase.

**What it checks**: FrontMatter validity, confidence values again, HTML comment leaks, wikilink syntax, file count.

**Blocking**: Critical issues set phase to "blocked" (stops pipeline). Warnings pass through.

## Gate 3: Pipeline Full Validate (manual / auto)

**When**: After all L1 phases are done.

**Usage**: `pipeline validate` or integrated into `pipeline auto`.

**13 checks** (via `dag_pipeline_run.py pipeline_validate`):
1. Phase completion status
2. FrontMatter + confidence + no placeholder leaks
3. wikilink cross-validation (broken links auto-fixed)
4. Exercise-solution 1:1 mapping
5. Mermaid syntax
6. Concept definition verification (from source)
7. Stray file detection
8. Level quality gate (L1 done → L2 ready)
9. Directory registry consistency
10. Content depth quality (A/B/C/D tiering)
11. Render-level validation (validate_render.py)
12. Cross-chapter consistency
13. Knowledge link audit (link_audit.py)

## Gate 4: link_audit (v52.0+)

**When**: After all L1 phases done, before L2 index generation. Activated per-chapter in `pipeline auto` and globally in `pipeline validate`.

**What it checks**: 
- Orphan detection (nodes with 0 incoming wikilinks)
- Asymmetric backlinks (A→B but B↛A)
- Cross-chapter citation analysis → L2 hub nodes

**Fix mode**: `run_link_audit(wiki_root, auto_fix=True)` auto-adds missing backlinks.

## Common Failure Patterns

### Pattern A: YAML structure wrong → 0 files built
**Symptom**: Phase says "done (0 文件)" but YAML has data.
**Root causes** (check in this order):
1. Missing `name`/`file`/`fm`/`bd` structure → Gate 1 `check_schema`
2. Wrong confidence value → Gate 1 `check_confidence`  
3. bd fields at top level instead of inside bd → Gate 1 `check_schema`
4. Flat structure (no fm/bd) for exercises/solutions → Gate 1 `check_schema`

### Pattern B: Source has formula but YAML says "无"
**Symptom**: mathematical_model shows "无" but source section has `$$...$$`.
**Root cause**: Agent didn't scan source before writing YAML.
**Catch**: Gate 1 `check_source_mathematical_model` (requires `--book-dir` + `-c`).

### Pattern C: Template fields covered < 70%
**Symptom**: Generated .md files have 10+ "无" sections.
**Root cause**: Agent only filled core bd fields, skipped the rest.
**Catch**: Gate 1 `check_bd_coverage`.

### Pattern D: SP/Scene not generated
**Symptom**: Phase says "done (0 文件)", no files in 60_技能点 or 70_应用场景.
**Root cause**: sps.yaml / scenes.yaml was empty `[]` or didn't exist.
**Prevention**: Every chapter must have ≥1 SP + ≥1 Scene. Even intro chapters.

### Pattern E: source_from duplicates chapter prefix
**Symptom**: Render shows "> 来源：第2章 §第2章 2.2 节" (redundant).
**Root cause**: YAML source_from contains "第2章 " which template also adds.
**Catch**: Gate 1 `check_source_from_format`.
**Fix**: Strip "第N章 " prefix from source_from values.

## Adding a New Check

1. Write function in `yaml_pre_validate.py` (follow existing pattern: `def check_X(items, node_type) -> list[dict]`)
2. Add `all_results.extend(check_X(...))` in `validate_file()`
3. Add to this document
4. If it requires source file access, add `wr` and `ch` parameters
