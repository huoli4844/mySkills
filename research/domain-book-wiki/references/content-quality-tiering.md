# Content Quality Tiering Methodology

## Problem

Pipeline depth checks (`check_kp_depth`, `check_sp_depth`, `check_scene_depth`) catch obvious gaps (missing formulas, no tool names, no quantitative params) but **cannot detect skeleton files** — files where every section exists but is filled with "无" (placeholder). After mechanical fixes bring FAIL counts to 0, a second layer of assessment is needed.

## Three-Indicator Tiering

For each generated `.md` file, count:

| Indicator | Measurement | Red Flag |
|:----------|:------------|:---------|
| **Line count** | `wc -l` | < 120 lines for Scene, < 150 for SP, < 180 for KP |
| **"无" density** | `grep -c '^无$'` | ≥ 8 "无" markers → skeleton; ≥ 13 → empty shell |
| **Wikilink count** | `grep -c '\[\['` | < 3 links → disconnected orphan node |
| **Mermaid count** | `grep -c '\`\`\`mermaid'` | 0 → no visual explanation (critical for Scene) |
| **Wikilink breakage** | `quality_score.py --book-dir . --all` → `wikilink_broken/wikilink_total` | > 30% → navigation broken |

## Tiering Rubric

### A-tier (Gold Standard)
- Lines: KP ≥ 250, SP/Scene ≥ 170
- "无" markers: ≤ 3
- Has: quantitative case study with specific numbers, real tool names (Keysight/R&S/Ansys), pitfall comparison table
- Wikilinks: ≥ 10 connected to concepts/KEs

### B-tier (Passable)
- Lines: KP 180-249, SP/Scene 130-169
- "无" markers: 4-7
- Structure complete, some sections thin but serviceable
- Has at least one Mermaid diagram with explanation

### C-tier (Weak — needs Agent content fill)
- Lines: KP 160-179, SP/Scene 100-129
- "无" markers: 8-12
- Missing: self-check answers, Bloom matrix, pitfall comparison
- Skeleton is there but lacks substance

### D-tier (Empty Shell — REDO)
- Lines: < baseline threshold
- "无" markers: ≥ 13
- Most sections are "无" — file exists only structurally
- Needs complete Agent content fill from source

## EMC Knowledge Base Audit Results (v50.3 baseline)

| Node Type | A-tier | B-tier | C-tier | D-tier | Total |
|:----------|:------:|:------:|:------:|:------:|:-----:|
| KP | 6 | 8 | 3 | 2 | 19 |
| SP | 0 | 5 | 4 | 4 | 13 |
| Scene | 0 | 3 | 5 | 2 | 10 |
| Concept | 0 | 25 | 0 | 0 | 25 |
| KE | — | 62 | — | — | 62 |

### D-tier Files (Redo Priority)

**KP** (2):
- `PCB电磁兼容设计流程.md` — Bloom解读="无", Bloom矩阵="无", 技能要求="无"
- `元器件EMC选型策略.md` — same pattern, shallow across the board

**SP** (4 — ≥13 "无" markers):
- `EMC仿真网格剖分技巧.md` (14 "无")
- `判断近场与远场区域.md` (14 "无")  
- `抗扰度测量实施方法.md` (13 "无")
- `辐射发射测量操作流程.md` (13 "无")

**Scene** (2 — 10 "无" markers, 0 Mermaid):
- `电子产品电磁兼容认证测量.md`
- `舰船平台系统级电磁兼容现场测量.md`

### Wikilink Health

- Total: 680 wikilinks across all nodes
- Broken: 286 (42%) — primary quality blocker for navigation
- Root cause: cross-chapter wikilinks not resolving; redirect pages missing for KE/concept references

## Usage

```bash
# Quick tiering scan
for f in 50_知识点/*.md; do
  wu=$(grep -c '^无$' "$f")
  lines=$(wc -l < "$f")
  links=$(grep -c '\[\[' "$f")
  echo "$lines lines | $wu wu | $links links | $f"
done | sort -t'|' -k2 -rn  # sort by "无" count descending
```

Always run tiering after `pipeline batch` completes — before declaring a chapter done.
