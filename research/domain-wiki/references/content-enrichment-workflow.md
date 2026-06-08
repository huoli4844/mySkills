# Concept Content Enrichment Workflow

## When to use

Pipeline_v2.py phase-a 生成概念骨架后（评分 60-65%），需要 Agent 填充全部 26 个 bd 字段内容。这个阶段是**全自动的** — 不需要问用户"要不要做"。

## Workflow (one delegate_task per chapter)

```
YAML skeleton (2/26 fields filled)
  ↓ delegate_task
Agent reads source + self-instruct guidance
  ↓ for each concept:
    ① yaml_writer.py self-instruct --type concept -c N --book-dir PATH
       → 获取 @prompt 指引 + 每个字段的源文片段
    ② Fill ALL 26 bd fields:
       - Read corresponding source section
       - term_definition ≥80字, mathematical_model as $$LaTeX$$
       - core_concept_map as Mermaid graph TD (≥8 nodes)
       - classification, domain, features, key_parameters etc.
    ③ quality_reviewer.py check-item --type concept --threshold 0.9
       ├─ pass (score ≥0.9) → write to YAML
       └─ fail → enrich from source → retry check
    ④ After ALL concepts pass, write concepts.yaml
  ↓
pipeline_v2.py phase-a --re-render
```

## Key commands

```bash
python3 scripts/yaml_writer.py self-instruct --type concept -c N --book-dir PATH
python3 scripts/quality_reviewer.py check-item --type concept --threshold 0.9 --item '...'
python3 scripts/pipeline_v2.py phase-a --book-dir PATH -c N --book-id XX --book-name "NAME"
```

## Pitfalls

- **Agent 声称完成但 YAML 没写** → 写后验证 `sum(1 for v in i['bd'].values() if v and v!='无') for i in data`
- **写错路径** → WORKSPACE/.dag vs BOOK/.dag，用绝对路径验证
- **只填了 term_definition** → 必须逐字段迭代所有 26 个 bd 字段
