---
name: file2md
description: "高保真文档解析：PDF/DOCX → Markdown。最大限度还原原始文件的内容、格式、目录、图片、公式、表格、段落结构。DOCX 使用 pandoc 原生转换，PDF 使用 Docling 结构化理解。"
version: 3.3.1
author: Hermes Agent
license: MIT
platforms: [macos, linux]
metadata:
  hermes:
    tags: [docx, pdf, extraction, formula, table, image, markdown]
    category: document-conversion
    related_skills: [docx-parser, docx-format, source-prepare]
---

# file2md — 高保真文档转 Markdown v3.3.0

将 PDF/DOCX 文件最大限度还原为 Markdown，保留目录结构、正文段落、数学公式（LaTeX）、表格、图片、列表等全部内容。

## 核心目标

**最大限度精确还原**原始文件的：
- ✅ 标题层级与目录结构
- ✅ 正文段落与文本格式（加粗/斜体/下划线）
- ✅ 数学公式（LaTeX `$...$` / `$$...$$`）
- ✅ 表格（Markdown pipe table）
- ✅ 图片（提取到 `assets/` 目录，MD 中引用相对路径）
- ✅ 列表（有序/无序）、引用块、脚注
- ✅ 原始阅读顺序

## 架构

```
file2md.py  (主入口 + CLI + 共享工具)
  │
  ├── .docx → docx2md.py ── pandoc ──→ Markdown + assets/图片
  │           (LaTeX修复/后处理)    (OMML→LaTeX，全量提取)
  │
  └── .pdf  → pdf2md.py  ── Docling ─→ Markdown + assets/图片
              (图片提取/后处理)    (结构化理解，布局/表格/图片)
```

按需导入：处理 DOCX 时不会加载 PDF 模块，反之亦然。

## 用法

```bash
# 自动检测文件类型
python3 scripts/file2md.py input.docx -o output/
python3 scripts/file2md.py input.pdf -o output/

# 输出到输入文件同目录
python3 scripts/file2md.py input.docx

# 禁用 OCR（纯文本 PDF，加速解析）
python3 scripts/file2md.py input.pdf -o output/ --no-ocr

# 按章节分割输出（检测"第N章"标题，每章一个文件）
python3 scripts/file2md.py input.docx -o output/ --split
python3 scripts/file2md.py input.pdf -o output/ --split
```

### 参数说明

| 参数 | 必需 | 说明 |
|:-----|:----:|:-----|
| `input` | ✅ | 输入文件路径（.pdf 或 .docx） |
| `-o / --output` | ❌ | 输出目录（默认：输入文件同目录） |
| `--engine` | ❌ | PDF 引擎：`docling`（默认，唯一） |
| `--no-ocr` | ❌ | 禁用 OCR（加速纯文本 PDF 解析） |
| `--split` | ❌ | 按章节分割输出多文件（检测`第N章`标题边界） |

### H1 标题不含章号前缀

file2md 忠实还原 docx 中的 H1 标题文本。如果原始文档的 H1 仅为"电磁兼容预测"（不含"第3章"前缀），输出 MD 的 H1 也如此。

**影响**：构建知识库时需要统一的 `# 第N章 标题` 格式。如果在 `20_正文/` 中使用 file2md 的输出，需在 Phase 1 完成后手动添加章号前缀，否则：
- `preprocess_toc.py` 产出的 `headings_tree[0].text` 不含章号
- 同一本书的各章节 H1 格式不一致

**修复**：`sed -i '' 's/^# /# 第X章 /' 文件.md` 或用 Python 正则替换。然后重新运行 `preprocess_toc.py`。

**注意**：file2md 生成的 frontmatter 中 `"title"` 字段通过文档解析可能已包含完整信息（如 `"第3章 电磁兼容预测"`），但 H1 正文不一定同步。frontmatter 的 title 依赖于文件名的解析，不一定可靠。

### 输出结构

**单文件模式（默认）：**

```
output/
├── 文件名.md                    # 转换后的 Markdown（完整）
└── assets/                      # 提取的图片
    ├── 图3.1.1-比幅测向原理.png  # 有题注：用题注命名
    ├── 图3.2.3-全向比幅系统.png  # 有题注：用题注命名
    ├── image-005.png             # 无题注：保持序号命名
    └── ...
```

**按章分割模式（`--split`）：**

```
output/
├── 文件名.md                    # 完整文件（仍会生成）
├── 第3章-测向与定位技术.md       # 分割后的章节文件
├── 第4章-信号截获技术.md
└── assets/                      # 共用的图片目录
    └── ...
```

## 依赖安装

```bash
# 核心依赖（DOCX 模式必需）
brew install pandoc                    # macOS
# apt install pandoc                   # Linux

# 备选：pypandoc_binary（brew 不可用时，自含 pandoc 二进制）
pip install pypandoc_binary

# PDF 引擎（必需，二选一）
pip install docling                    # Docling — 默认引擎，结构化理解
pip install marker-pdf                 # Marker — 备选引擎，高精度布局还原

# 验证安装
pandoc --version
python3 -c "from docling.document_converter import DocumentConverter; print('Docling OK')"
python3 -c "from marker.convert import convert_single_pdf; print('Marker OK')"
```

### marker-pdf 安装注意事项

`marker-pdf`（依赖 surya-ocr）使用 Python 3.10+ 语法（`X | Y` 联合类型），**系统 Python 3.9 会报错**：

```bash
# ❌ 系统 Python 3.9 安装后运行报错：
# TypeError: unsupported operand type(s) for |: '_GenericAlias' and 'NoneType'

# ✅ 解决：使用 conda py311 环境安装
conda create -n py311 python=3.11 -y
conda activate py311
pip install marker-pdf psutil
```

同时也需要 `psutil`（Marker 运行依赖，但 pip 可能不会自动拉取）。
详见 `references/marker-setup.md`。

### pandoc 发现路径说明

`_find_pandoc()` 按以下优先级搜索 pandoc 可执行文件：

1. `pypandoc.get_pandoc_path()`（`pip install pypandoc_binary` 的缓存路径）
2. `$PATH` 中的 `pandoc`
3. `~/bin/pandoc`
4. `/opt/homebrew/bin/pandoc`
5. `/usr/local/bin/pandoc`
6. `/usr/bin/pandoc`

> **macOS 常见陷阱**：`brew install pandoc` 可能因网络或权限超时。此时 `pip install pypandoc_binary` 是可靠的替代方案，pandoc 二进制从 PyPI 直接分发，支持 arm64 和 x86_64。装完后 file2md 自动发现无需额外配置。

## PDF 公式提取的已知限制

| 公式形态 | Docling | Marker | 说明 |
|:---------|:-------:|:------:|:-----|
| 文本公式 | ✅ → LaTeX | ✅ → LaTeX | 两者均可识别转换 |
| 特殊字体公式 | ⚠️ 部分 | ✅ 更好 | Marker 布局还原精度更高 |
| 图片公式 | ❌ 占位符 | ❌ 同 | 图片公式均无法提取为 LaTeX |

> 对于图片公式占比高的文档，建议优先使用 DOCX 源文件（pandoc 公式保真度最高）。
> Marker 作为 PDF 备选引擎，在布局还原上优于 Docling，但未集成到 file2md 的 `--engine` 参数中，需单独调用。

## 已知限制

### 标题检测缺失（使用格式化而非 Word 标题样式的文档）

某些 .docx 文档使用字体大小/加粗等格式化方式表示标题，而非 Word 的 Heading 样式。
此时 pandoc 无法识别标题层级，输出 MD 中无 `#` 标记。

**推荐方案（最优）**：在 file2md 之前先运行 docx-format 技能：

```bash
# 先用 docx-format 应用 Heading 样式
python3 ~/.hermes/skills/docx-format/scripts/format_docx.py \\
  input.docx output.docx --no-ocr

# 再跑 file2md（pandoc 现在能识别标题样式了）
python3 scripts/file2md.py output.docx -o output/ --split
```

实测效果：原 0 标题文档 → docx-format 后 H1=84, H2=133, H3=330 → file2md 输出每章 12~192 个正确标题。

**备用方案**（当 docx-format 不可用时）：
`docx2md.py` 的 `_postprocess_docx_md()` 函数在第9步新增标题检测，从 blockquote/span 包裹中提取节号。

**`_split_by_chapters()` 页眉过滤增强（v3.3.0）**：
章节检测时过滤页眉行：清理 `![image]`、HTML 标签、末尾页码，跳过仍含 `![image` 的行。

## 参考文件

- `scripts/file2md.py` — 主入口 + 共享工具 v3.2.0
- `scripts/docx2md.py` — DOCX 专用逻辑（pandoc 转换 + LaTeX 修复）
- `scripts/pdf2md.py` — PDF 专用逻辑（Docling 解析 + 图片提取）
- `references/实测发现.md` — 实测发现记录
- `references/benchmarks.md` — 实测基准对比（DOCX: Pandoc vs file2md; PDF: file2md vs Marker）
- `references/pitfalls-and-incidents.md` — 陷阱与事故记录（含 **SmartArt 图未提取** 等重要限制）
- `references/docling-setup.md` — Docling 安装与配置
- `references/marker-setup.md` — Marker（marker-pdf）安装与 Python 版本注意事项
