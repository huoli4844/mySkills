# TOC Detection Design (v2 — Final Approach)

## History

The TOC detection went through 3 iterations during the 2026-06-09 session processing a 21K-line book:

| Iteration | Approach | Problem |
|-----------|----------|---------|
| v1 | Filter TOC block (##目录→first content chapter) | Missing chapters that only exist in TOC |
| v2 | Keep all chapters, drop <100 line TOC entries | Still too aggressive for TOC-only chapters |
| v3 (final) | Keep ALL chapters, skip only <15 line entries | ✅ All 20 chapters present, continuous numbering |

## Final Design

```
CHAPTER_PATTERN (## 第N章) + CHAPTER_BARE_PATTERN (第N章 w/o #)
  → chapter_starts[]
  → by_number dict (last-wins, content overrides TOC)
  → toc_titles dict (collect full names from TOC)
  → fill missing content chapter names from TOC titles
  → auto-create Ch1 from preamble if first content ch > 1
  → build ranges
  → split_book() writes each, skipping <15 line TOC entries
```

## Key Design Decisions

1. **Keep TOC-only chapters.** They represent the book's intended chapter structure even if the content header doesn't use `# 第N章` format.
2. **Content chapter wins over TOC** when both exist (by_number last-wins with content-vs-TOC priority).
3. **Fill missing titles from TOC.** Content chapters with just `# 第2章` (no title) get their name from the TOC entry.
4. **Skip only <15 line TOC entries.** These are the sub-section TOC listings within TOC-only chapters like `第8章 隔离变压器` (9 lines).
5. **Normalize filenames** — strip `……页码` artifacts, trailing spaces, bare page numbers (like `接地设计 67`→`接地设计`).
6. **Single-pass line-by-line scan** — `discover_chapter_ranges()` no longer uses `readlines()`. It iterates with `for i, line in enumerate(f)` to handle very large files without memory pressure.

## Book-Specific Quirks This Handles

- `# 第2章` (no title text) → title filled from TOC
- `第6章 电缆及连接器的设计 ……141` (no `#` prefix) → captured by BARE_PATTERN
- ` ` (trailing spaces in filenames) → stripped
- `…… 3` / `67` page number artifacts in titles → cleaned

All handling is pattern-based, not book-specific. No hardcoded chapter numbers or book names.
