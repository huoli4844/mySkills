# Mermaid Troubleshooting Guide for Obsidian

## Quick Reference: Error → Root Cause → Fix

| Error Signal | Root Cause | Fix |
|:-------------|:-----------|:-----|
| `Lexical error on line X. Unrecognized text.` | `subgraph` title contains parentheses `()`, brackets `（）`, em dash `—`, or comma `,` | Remove special chars from subgraph title. Split into multiple `graph LR` blocks instead of one subgraph. |
| Blank/white chart, no error shown | (a) `xychart-beta` with multi-series data (Obsidian Mermaid version too old for v10.6+ features) | Replace with `graph LR` or `flowchart TD` blocks. xychart-beta is unreliable in Obsidian. |
| Same | (b) Emoji `✅❌⚠️🔽➡️` in node labels | Replace with plain text ("达标/不达标/注意/下降"). |
| Same | (c) `%%{init}` uses single quotes `'...'` instead of double quotes `"..."` | Change to `%%{init: {"key": "value"}}%%`. |
| Same | (d) `%%{init}` line placed mid-diagram instead of first line | Move `%%{init...}%%` to the FIRST LINE of the mermaid block. |
| `undefined class` / node has no style | `:::classname` referenced but no `classDef classname ...` declared | Add `classDef classname fill:#xxx,color:#xxx` for every `:::` usage. |
| Chart renders but is cut off / tiny | No `%%{init}` for max width | Add `%%{init: {"flowchart": {"useMaxWidth": false}}}%%` as first line. |
| Mindmap shows blank | (a) More than 1 root node | Mindmap must have exactly one root. |
| Same | (b) Too many nodes (>30) | Split into multiple mindmaps. |
| `flowchart` nodes duplicated / wrong branching | Node label contains `,` or `()` without quote wrapping `["..."]` | Wrap in quotes: `A["label with, comma"]`. |

## The Most Reliable Diagram Type for Obsidian

**`graph LR` or `graph TD`** with small, simple node counts (≤10 per block).

Why it works:
- Supported since the earliest Mermaid versions bundled with Obsidian
- No dependency on xychart-beta (v10.6+) or block-beta (v11+)
- No subgraph title lexical pitfalls
- Style declarations work reliably

**When you need a before/after multi-series comparison:**
- Do NOT use xychart-beta — it does not render multi-series in Obsidian
- Do NOT use subgraph with special characters in the name
- DO use 3-4 individual `graph LR` blocks, one per comparison group
- Each block: 1→2→3 progression nodes + 1 limit/reference node
- Use `style` with fill colors (red→orange→green→blue dashed) for visual encoding

## Debugging Flowchart

```
Is the Mermaid diagram blank?
├── Yes → Check for emoji: run `post_generation_check.py --fix`
│         Check for xychart-beta: replace with graph/flowchart
│         Check %%{init} syntax: single quotes? missing }%%?
│
├── No, but Lexical error →
│   Is subgraph title the line? Contains ()—,? → Remove them
│   Is %%{init} the line? Missing %%. → Fix
│
├── No, but undefined class →
│   Add classDef for all ::: references
│
└── Renders but ugly →
    Add %%{init: {"flowchart": {"useMaxWidth": false}}}%%
    Wrap unquoted node labels with ["..."]
```

## Testing Protocol

After fixing a non-rendering Mermaid diagram:

1. Open the .md file in Obsidian
2. Switch to Reading mode (not Source/Live Preview)
3. Confirm the diagram is visible
4. If still blank, right-click → "Copy" → paste into https://mermaid.live/edit to isolate Obsidian-specific vs syntax bug

## Tool Integration

The `post_generation_check.py --fix` script in this skill can:
- ✅ Detect and auto-remove `bar-group-group` and other illegal xychart-beta keywords
- ✅ Detect emoji in node labels (warns only)
- ✅ Detect subgraph titles with special characters (warns only)
- ✅ Detect missing classDef definitions
- ✅ Detect %%{init} format issues
- ✅ Run all checks on every Mermaid block in the file
