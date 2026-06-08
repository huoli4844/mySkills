# Exercises Auto-Generation from Solutions

## When triggered

When `build_kb_files.py --type solution` detects that `exercises.yaml` is missing for the chapter but `solutions.yaml` exists.

## What happens

1. **WARN** logged: `[solution] 第N章有 solutions.yaml 但 exercises.yaml 不存在！`
2. **Auto-generate** `exercises.yaml` from `solutions.yaml`:
   - `file`: solution's file minus `-解答` suffix
   - `name`: same as file
   - `fm.source_chapter`: current chapter
   - `fm.bloom_level`: from solution's bd or fm
   - `fm.confidence`: **0.65** (must match eval/exercise schema — 0.75 will be rejected)
   - `bd.question`: from solution's bd.question (may be a placeholder)
3. **Auto-trigger** `build_kb_files.py --type exercise --chapter N` via subprocess
4. Solutions build continues with its own `solutions.yaml` data

## Data flow

```
solutions.yaml exists
    ↓ (missing exercises.yaml detected)
Auto-generate exercises.yaml
    ↓ (subprocess)
build_kb_files --type exercise reads new exercises.yaml
    → produces N exercise files
    ↓ (back in solution build)
build_kb_files --type solution continues
    → auto-question from exercises.yaml (if questions are real, not placeholders)
```

## Pitfalls

- `confidence: 0.65` not `0.75` — exercise schema only accepts 0.65
- Subprocess must use absolute paths — `os.path.abspath(output_dir)` and full script path
- The auto-generated exercises have placeholder questions if solutions.yaml also has placeholders
- Real question content requires Agent to fill exercises.yaml or solutions.yaml properly
