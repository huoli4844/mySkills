# Content Supplementation Workflow（章节内容补充）

**当已有章节正文，需要补充特定素材时的操作流程。**

## Trigger Conditions

Use this workflow when:
1. A pre-existing chapter needs specific new content from a reference textbook
2. A writing guide identifies gaps in the current chapter
3. A single textbook has unique content not covered in the primary source
4. Content needs to be inserted without disrupting existing structure or numbering

## Workflow

### Step 1: Read the Writing Guide (if exists) — or the Task Description

```bash
# If it exists, read the chapter's writing guide to identify what to add
# Guides are in output/写作大纲/writing-guide-ch{N}.md
read_file path="output/写作大纲/writing-guide-ch{N}.md" limit=200
```

If the writing guide does NOT exist, the user's task description IS the authoritative guide. Extract:
- **What specific content to add** ("柯金良6类频谱分类法", "雷电二次效应", etc.)
- **Which book/source to extract from** (e.g., "柯金良书中搜索对应内容")
- **Target chapter and section locations**

The task description's content item list (e.g., "第3章新增: 柯金良6类频谱分类法、雷电二次效应...") serves the same role as a writing guide — it tells you exactly what to find, where from, and where to insert.

### Step 2: Locate and Search the Reference Textbook

**First, locate the reference textbook files.** Reference books may be stored outside the project directory, in locations like `~/Desktop/电磁兼容/处理后/`, `~/Desktop/0601-待整理/`, or `~/Desktop/电磁兼容知识库/raw/`. Search multiple locations:

```bash
# Search common locations for the reference book
search_files pattern="*电磁兼容概论*柯金良*" path="~/Desktop" target=files
search_files pattern="*优先级3*" path="~/Desktop/电磁兼容" target=files
```

Look for `.md` files (parsed in `处理后/` directories) or `.docx`/`.pdf` (raw sources). Prefer the `处理后/` markdown version — it's text-searchable and directly readable.

If the book is not in the expected location, check alternative project directories the user may have created.

**Then, search the reference textbook for specific content sections.** Use `search_files` with the reference book's own section numbering system:

```bash
# Search by section number (e.g., Ke Jinliang §2.8, §2.9)
search_files pattern="2\.8 骚扰源的特性分析|2\.9 骚扰源的模型" path="<path_to_book.md>" context=0

# Search by section heading
search_files pattern="## 2.2 雷电及其二次效应|公共场所" path="<path_to_book.md>" context=0

# Search combined keywords from the user's requirements
search_files pattern="频谱分类|窄带|宽带|双指数|振铃波|传输线" path="<path_to_book.md>" context=3
```

Key search strategies:
- **By section number** — The user's requirements reference specific sections (e.g., "柯金良6类频谱分类法" → §2.8, "雷电二次效应" → §2.2). Start with the exact section heading.
- **By directory table of contents** — Read the first 100-200 lines of the reference book's markdown to see its table of contents (has all section numbers and names).
- **By combined keywords** — For content that spans sections, search by topic keywords with `context=3` to find the right location.
- **By cross-reference** — The user may specify both a topic name (e.g., "公共场所骚扰源") and a book source. Search both the topic and the source mention.

After finding section locations, read the relevant sections:

```bash
# Find the starting line and read the section
search_files pattern="^## 2\.5 公共场所" path="<path_to_book.md>" context=0
# → gives line number, then:
read_file path="<path_to_book.md>" offset=<line> limit=80
```

**Large-file navigation pitfall**: The reference book may be 20,000+ lines. NEVER `read_file` the whole file — always locate sections via `search_files` first, then `read_file` with precise offset/limit.

### Step 3: Read the Existing Chapter

Read the current chapter to understand:
- What content already exists (avoid duplication)
- The exact insertion point (look for existing section breaks, adjacent content)
- The numbering state (last formula tag, last figure number, last example number)

```bash
# Read target area of existing chapter
read_file path="output/第{N}章-*.md" offset=<target_line> limit=<needed_lines>
```

### Step 4: Apply Targeted Patch

Use `patch` with `mode='replace'` and a **unique** old_string:

```python
# DO NOT rewrite the whole file
# Instead, find a unique anchor string at the insertion point
# and use old_string + new_string to splice in new content

patch(
    mode='replace',
    path='output/第{N}章-*.md',
    old_string='<UNIQUE line(s) from existing file>',
    new_string='<UNIQUE lines + NEW CONTENT + continuation>'
)
```

**Key rules for successful patches:**
- `old_string` must be **unique** in the file — include surrounding context to guarantee uniqueness
- Preserve all existing content in `new_string` — the patch replaces the matched `old_string` with the full `new_string`
- Use `replace_all=True` only when you explicitly want multi-site replacement
- Never remove existing content unless the user explicitly directs you

### Step 5: Verify Content Was Inserted

```bash
# Read the target area to confirm insertion
read_file path="output/第{N}章-*.md" offset=<target_line> limit=10

# Check that adjacent content wasn't accidentally modified
```

### Step 6: Handle Numbering Disruptions

When inserting content with new formulas, figures, examples, or tables:

```bash
# 1. Use temporary tags (e.g., \tag{99-99}, **例99-99**)
# 2. After ALL insertions are complete, run renumbering
python3 scripts/renumber.py output/第{N}章-*.md

# 3. Verify numbering
python3 scripts/post_generation_check.py output/第{N}章-*.md
```

### Step 7: Quality Verification (using the skill's scripts)

The verification scripts (`post_generation_check.py`, `fix_common_issues.py`) live in the `book-build` skill's scripts directory at `~/.hermes/skills/research/book-build/scripts/`. Run them from the project directory:

```bash
# Run quality check with auto-fix
python3 ~/.hermes/skills/research/book-build/scripts/post_generation_check.py output/第{N}章-*.md --fix --verbose

# Run common issue fixes
python3 ~/.hermes/skills/research/book-build/scripts/fix_common_issues.py output/第{N}章-*.md
```

**IMPORTANT — do not skip this step.** The user expects these scripts to be run as the final validation. If they don't exist at the relative path (`scripts/post_generation_check.py`), use the absolute path from the skill directory.

If both scripts cannot be found or produce errors, write a standalone validation script that at minimum checks:
- All Ke Jinliang content was inserted (search for unique keywords)
- No duplicate equation tags
- Brace balance in LaTeX math blocks
- File line count increase

## Common Insertion Patterns

### Adding a New Subsection

```
#### （3）New Subsection Title

New subsection content...
```

Insert after the last existing subsection, before the next major section heading.

### Adding a New Table

Insert near the related text, with proper table numbering (use temporary number first, renumber later).

### Adding a New Example

```
**例 N-99**：Example title

...
```

Note: Examples are numbered per-chapter. Use a temporary number (N-99) during insertion, then renumber globally.

### Adding Inline Formulas

```latex
$$
k = \frac{l}{\lambda} = \frac{l f}{v} \tag{N-M}
$$
```

## Pitfalls

1. **Writing guide may not exist** — The user may ask for writing guides that haven't been generated yet (`writing-guide-ch3.md`, `writing-guide-ch4.md`). When they don't exist, fall back to the user's explicit instructions in the task description as the authoritative guide for what content to add.

2. **Not checking insertion area first** — Always read the 10-20 lines around the intended insertion point to capture exact text formatting (table pipes, list markers, blank lines).

3. **old_string not unique** — The patch tool requires unique matches. Include 3-5 surrounding lines of context in `old_string` for uniqueness, especially for table rows or repeated section markers like `---`.

4. **Accidentally deleting content** — The patch replaces `old_string` with `new_string`. If `new_string` doesn't include the `old_string` text, the matched content is deleted. Always carry existing text into `new_string` unless you intend deletion.

5. **Numbering cascade** — Inserting new formulas, examples, figures, or tables mid-chapter causes all subsequent numbering to shift. Run renumbering after ALL insertions complete, not after each one.

6. **Running renumbering resets text references** — After renumbering, text references like `式(7-5)` or `见例7-3` may point to wrong numbers if they contain the old numbers frozen in text. These must be manually updated or handled by the cross-ref fix script.

7. **Content from multiple textbooks** — When adding content from multiple reference textbooks, add them in priority order. Higher-priority books' content should be placed earlier in the subsection where possible.

8. **`post_generation_check.py --fix` 创建孤立 `\tag` 行（blockquote 上下文中）** — 当 `\tag` 位于 `> $$` 块引用块的 `$$` 内部时（如插入的柯金良等引用内容），`--fix` 的 `_fix_missing_tag` 可能解析错误，在 `$$` 块外部额外插入 `\tag{6-N}` 等孤立行。这些行不在任何 `$$` 块内，会导致渲染失败。修复方法：手动删除所有孤立的 `\tag{6-N}` 行（即不在任何 `$$` 块内部的行），而不是运行 `renumber.py`（重排脚本可能同样受 blockquote 上下文影响）。验证：`grep -n '^\\\\tag{' output/第N章.md | head -20` 应只显示在 `$$` 块内部的行。

9. **`patch` tool partial-read warning** — The `patch` tool issues a warning: "file was last read with offset/limit pagination (partial view). Re-read the whole file before overwriting it." This is advisory — the patch still applies successfully. But to avoid confusion, do a full `read_file` (without `offset`/`limit` restrictions if the file is <100K chars) before the first patch on each file, so the tool's internal cache has the full view.

9. **Scripts in skill directory vs. project directory** — `post_generation_check.py --fix` and `fix_common_issues.py` are in `~/.hermes/skills/research/book-build/scripts/`, not in the project root. Running `python3 scripts/post_generation_check.py` from the project directory will fail with "No such file or directory". Use the absolute path or symlink the scripts into the project root before running them.

10. **Validation after insertion** — After all insertions are complete, the user explicitly expects validation scripts to be run. Never skip this step. If the scripts fail, write a custom validation as fallback rather than reporting nothing.
