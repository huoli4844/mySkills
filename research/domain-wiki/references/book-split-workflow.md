# 整书按章节拆分工作流

> 适用于 raw/ 目录下每个书籍都是一个带 `# 第N章` 标题的整书 .md 文件。
> 技能脚本：`scripts/split_book_to_chapters.py`

## 标准化做法

```bash
# 一次性完成：创建目录 + 复制图片 + 拆分章节
cd /path/to/knowledge_base
python3.11 scripts/split_book_to_chapters.py prepare \
  --raw-dir raw/书名/ \
  -w 领域目录/书名/ \
  --split

# 或分步：
# Step 1: 创建目录 + 复制图片
python3.11 scripts/split_book_to_chapters.py prepare \
  --raw-dir raw/书名/ \
  -w 领域目录/书名/

# Step 2: 单独拆分
python3.11 scripts/split_book_to_chapters.py split raw/书名/书名.md \
  -w 领域目录/书名/ \
  --force
```

## `discover_chapter_ranges` 的处理策略

### 章节标题匹配（三项模式）

| 模式 | 正则 | 示例 |
|------|------|------|
| `## 第N章 ...` | `^(?:#{1,2})\s*(第\s*\d+\s*章\s*.*?)` | `## 第 1 章 EMC基础知识` |
| `# 第N章`（无标题） | 同上 | `# 第2章` |
| 无 `#` 前缀 | `^(第\s*\d+\s*章\s*.*?)` | `第6章 电缆及连接器的设计` |

三种模式覆盖了中文教材的常见章节标题格式。

### TOC 条目识别

`TOC_ENTRY_PATTERN = r"第\s*\d+\s*章.*……\s*\d+\s*$"` 匹配带页码标记 `……N` 的目录条目。

**去重策略**（`by_number` 字典）：
- 同一章节号出现多次时，**内容版本（无 …… 页码）覆盖 TOC 版本（有 …… 页码）**
- 内容版本之间保留最后出现的
- TOC 条目之间保留最后出现的

### 章节名补全

内容章节标题通常只有 `# 第N章`（无章节名），从 TOC 条目的 `# 第 N 章 xxxx ……页码` 中提取完整名称补全。

```python
# 示例：内容标题 "# 第5章" → 从 TOC "第 5 章 干扰滤波 …… 108" → "第5章 干扰滤波"
```

### 自动创建第 1 章

当第一个内容章节不是第 1 章时，自动从目录块之后到第一个内容章节之前的内容创建 `第1章 概述`。章节名优先从 TOC 标题获取，兜底用 `"第1章 概述"`。

### 页码伪影清理

`normalize_filename` 自动清理尾部 `……N` 页码标记和孤立行末数字：
- `第 3 章 接地设计 67` → `第3章 接地设计`
- `第 1 章 EMC基础知识 …… 3` → `第1章 EMC基础知识`

### 极小条目的过滤

`< 15 行` 且带 TOC 页码标记的章节被跳过（纯目录子节列表，非正文内容）。

## 性能：逐行扫描，不读入整个文件

`discover_chapter_ranges()` 使用 `for i, line in enumerate(f)` 逐行遍历文件，不调用 `readlines()`。

章节检测、TOC 标记检测（`## 目录`）、行号统计全部在一次遍历中完成。

只有 `split_book()` 需要 `readlines()` 来切片提取各章节内容（`all_lines[start:end]`），这是必需的随机访问。

## 常见陷阱

1. **TOC 条目被当作章节内容** — `by_number` 去重机制确保内容版本优先于 TOC 版本
2. **章节标题无 `#` 前缀** — `CHAPTER_BARE_PATTERN` 兜底匹配
3. **章节文件名含页码伪影** — `normalize_filename` 自动清理 `……N` 和尾部数字
4. **大文件内存占用** — 逐行扫描避免读入整个文件；`split_book()` 的 `readlines()` 是唯一的单次批量读取
