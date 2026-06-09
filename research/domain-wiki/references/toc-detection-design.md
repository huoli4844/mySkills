# TOC 块自动检测设计（split_book_to_chapters.py）

## 问题

整书 MD 拆分时，`CHAPTER_PATTERN` 同时匹配 TOC 条目和内容章节标题。TOC 条目被当作内容写入，产生 <100 行的空文件（如 `第1章` 仅 90 行 TOC 目录）。

## 三层过滤（2026-06-09）

### 第一层：by_number 去重

`discover_chapter_ranges()` 用 `OrderedDict` 的 `by_number[ch_num] = (start, text)` 覆盖方式保留最后一次匹配（正文版本），消除 TOC 重复。内容条目在 TOC 条目之后出现，故自动覆盖。

### 第二层：TOC 块边界检测

```python
# 检测 ## 目录 行位置
toc_start = None
for i, line in enumerate(lines):
    if re.match(r"^#{1,2}\s*目录\s*$", line.strip()):
        toc_start = i
        break

# 检测第一个内容章节
first_content_line = None
for start, text in chapter_starts:
    if not is_toc(text) and CHAPTER_NUM_PATTERN.search(text):
        # 估算区间：该章节到下一个章节的行数
        span = next_start - start
        if span >= 100:
            first_content_line = start
            break
```

TOC 块 = [`toc_start`, `first_content_line`)。此区间内的所有章节被过滤。

### 第三层：行数阈值

`split_book()` 中跳过 `total_lines < 15` 的 TOC 条目：极小片段（Pure TOC）。

## 章节名补全

内容章节标题仅含 `第N章`（无章节名）。从 TOC 条目收集完整标题并补全：

```python
toc_titles = {}
for start, text in chapter_starts:
    if TOC_ENTRY_PATTERN.match(text):
        clean = re.sub(r'\s*……\s*\d+\s*$', '', text).strip()
        toc_titles[cn] = clean

for ch_num, (start, text) in by_number.items():
    has_name = bool(re.search(r'章\s+\S', text))
    if not has_name and ch_num in toc_titles:
        by_number[ch_num] = (start, toc_titles[ch_num])
```

## 自动创建第1章

当首个内容章节编号 > 1 时，从目录末尾到第2章之间的前言内容自动创建第1章：

```python
if first_idx > 1:
    ch1_start = toc_start + 1
    if ch1_start < first_start:
        ch1_title = toc_titles.get("1", "第1章 概述")
        by_number["1"] = (ch1_start, ch1_title)
```

## 文件名净化

```python
# 清理页码标记
clean = re.sub(r'\s*……\s*\d*\s*$', '', heading_text)
clean = re.sub(r'\s+\d+\s*$', '', clean)
# 无章节名时不用尾随空格
if ch_name:
    return f"第{ch_num}章 {ch_name}.md"
else:
    return f"第{ch_num}章.md"
```
