# Quality Review Metrics (v3.0)

## Three-Tier Check System

quality_reviewer.py — T1: 结构完整性 / T2: 内容深度 / T3: 交叉验证

## T1 Checks

| Check | What it catches | Severity |
|-------|----------------|----------|
| fm_missing | FM缺少source_chapter/confidence | error |
| yaml_no_name | YAML缺少顶层name字段 | error |
| placeholder_residue | {{xxx}}未替换残留 | error |
| prompt_leak | @prompt泄漏到渲染输出 | error |
| mermaid_syntax | Mermaid标签未用引号包裹 | warning |
| bd_extra_fields | bd多出模板没用到的字段 | info |

## T2 Checks

| Check | What it catches | Severity |
|-------|----------------|----------|
| field_empty | bd字段为空或填"无"/"(无)"/"待补充" | error |
| field_too_short | bd字段低于FIELD_DEPTH阈值 | warning |
| mermaid_missing | concept的core_concept_map非图结构 | warning |
| bloom_missing | KP/SP缺少bloom_level | warning |
| term_english_missing | KE缺少term_english | info |
| solution_shallow | solution的principle_steps < 100字 | warning |

## Scoring

files = unique files with issues
penalty = min(errors/files * 0.15, 0.7) + min(warnings/files * 0.04, 0.25)
score = max(0, 1 - penalty)

| Score | Meaning |
|-------|---------|
| 95-100% | Excellent |
| 85-95% | Good (minor depth warnings) |
| 70-85% | Fair (multiple shallow fields) |
| < 70% | Needs review |

## CLI

python3 quality_reviewer.py book --book-dir /path --book-id 01_书ID
python3 quality_reviewer.py chapter --book-dir /path --book-id 01_书ID -c 3 --threshold 0.5
python3 pipeline_v2.py review --book-dir /path --book-id 01_书ID
