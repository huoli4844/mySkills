# TOC Detection Design (`split_book_to_chapters.py`)

## Problem

Books often have a Table of Contents (TOC) section before the actual content.
TOC entries look like chapter headings but contain no substantive content — only
page references. Without detection, `split_book` creates empty/thin chapter files
from TOC entries.

## Design (v2.0+)

Three-layer filtering:

### Layer 1: Chapter heading matching

Two regex patterns handle different heading formats:

```python
CHAPTER_PATTERN    = r"^(?:#{1,2})\s*(第\s*\d+\s*章\s*.*?)$"    # ## 第 1章 xxx
CHAPTER_BARE_PATTERN = r"^(第\s*\d+\s*章\s*.*?)$"                # 第6章 xxx (no #)
```

Key fix (`.` not `.+`): `# 第2章` has zero characters after `章`, so `.+`
(requires >=1 char) fails. `.*` allows empty text.

### Layer 2: TOC block detection

The TOC block is identified as:
- **Start**: `## 目录` heading line
- **End**: First non-TOC chapter heading with ≥100 lines of content span

All chapter entries whose `start` falls within this range are filtered out.

### Layer 3: Content span check

Even without TOC detection, chapters with content span < 100 lines that match
TOC page-number pattern are skipped in `split_book()`.

## Edge Cases

| Book | Issue | Fix |
|------|-------|-----|
| `# 第2章` (no title text) | `.++` required >=1 char after `章` | `.*` allows zero |
| `第6章 xxx` (no `#` prefix) | Only CHAPTER_PATTERN checked | Add CHAPTER_BARE_PATTERN |
| `第3章 接地设计 67` (no page num marker) | Layer-2-only check misses it | Block detection catches all in TOC range |
| Content vs TOC same chapter number | TOC header then content header same number | `by_number[ch_num] = (start, text)` keeps LAST |
