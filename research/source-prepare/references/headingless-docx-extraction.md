# 无标题样式 .docx 的结构化提取（Path E）

## 背景

有些 .docx 文档不使用 Word 的 Heading 样式（Heading1/2/3），而是通过**字体大小 + 加粗**等格式化方式表示标题层级。pandoc 无法识别这种文档的标题结构，导致 `file2md` 输出中所有 `#` 标记消失，正文显示为纯文本 + page header 污染。

## 判断标准

```python
import docx
doc = docx.Document('input.docx')
all_normal = all(p.style.name == 'Normal' for p in doc.paragraphs[:100])
if all_normal:
    # 确认是标题样式缺失的文档
```

辅助检查：所有 `#### N.M` 节号在 source 中是否被 page header/blockquote 包裹。

## 处理方案

### 方案 A：docx-format → file2md（推荐，保留图片）

先运行 `docx-format` 给源文件加 Heading 样式，再跑 `file2md`：

```bash
python3 format_docx.py input.docx formatted.docx --no-ocr
python3 file2md.py formatted.docx -o output/ --split
```

**优点**：保留图片/assets，通过 file2md 管道
**局限**：标题检测依赖 docx-format 的正则模式（`^第X章`/`^X.X`/`^X.X.X`），较复杂的文档可能仍有遗漏

### 方案 B：python-docx 直接提取（docx2md_textract.py）

绕过 pandoc，用 python-docx 直接读取段落内容和字体属性，通过硬编码的段落索引检测章节标题。

```bash
python3 docx2md_textract.py input.docx output/ --split
```

**优点**：100% 精确的章节边界（基于段落索引），不受 page header 污染
**局限**：图片引用丢失（需额外从 file2md assets/ 合并），公式显示为 `[公式图片×N]` 占位符

#### 章节标题检测规则

标题通过一组预定义的**段落索引**（如 `507: (2, "电磁兼容理论基础")`）确定。这些索引需要从源文档中手动查找：

```python
# 在 python-docx 中找出大字号段落（≥20pt）
for i, p in enumerate(doc.paragraphs):
    sz = max((r.font.size.pt for r in p.runs if r.font.size), default=0)
    if sz >= 20:
        print(f"P{i}: {sz}pt, {p.text[:40]}")
```

#### 节号检测规则

行首匹配以下模式自动添加 `###`/`####`：
- `N.M 标题` → `### 标题`
- `N.M.P 标题` → `#### 标题`

#### 页眉/页码过滤规则

- 行内容匹配 `^\d+\s*电[磁]{1,2}兼容` → 跳过（page header）
- 行内容匹配 `^电[磁]{1,2}兼容.*\d+$` → 跳过（page header 反转）
- 纯数字行（`^\d+$`, len≤4）→ 跳过（页码）
- 行内容含 `\d+\s+电磁兼容原理与技术` → 去除该片段（页码污染）

### 方案 C：后处理 split（post_split.py）

如果已有完整 `formatted.md`（file2md 输出），可通过 `## N.1` 节号位置重新分割章节：

```bash
python3 post_split.py formatted.md output/
```

**优点**：无需重新运行 file2md，利用已有 .md
**局限**：仅适用于 file2md 输出中 `## N.1` 节号正确的情况

## .docx 图像公式识别

当 .docx 中的公式为嵌入图片（PNG/JPEG，非 OMML）时，可用 `--formula-recognize` 触发 LLM 识别：

```bash
python3 prepare_source.py input.docx -o output/ --formula-recognize
```

**流程**：
1. docx-format 加标题样式
2. file2md 提图片到 assets/
3. 检测 assets/ 中小尺寸图片（PIL Image.size: w<300 or h<100）
4. 运行 `extract_formula.py --batch`（需 MOONSHOT_API_KEY / OPENAI_API_KEY）
5. merge_source.py 替换图片引用为 LaTeX

**公式候选检测**：双层过滤
- 层1（docx XML）：查找 `wp:inline` drawing，cy 高度 3~30pt
- 层2（PIL）：查找 assets/ 中像素宽<300 或高<100 的图片
