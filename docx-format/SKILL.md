---
name: docx-format
description: Word文档(docx)智能格式化技能。自动识别标题层级（第X章/X.X/X.X.X）、转换Unicode文本公式和图片公式为可编辑OMML、识别图/表题注并应用Caption样式。适用于中文教材、技术文档的批量格式化场景。当用户需要对docx文件进行标题规范化、公式可编辑化、题注标注等格式化操作时触发此技能。
agent_created: true
---

# docx-format — Word文档智能格式化

将未格式化的docx文档一键转换为标题规范、公式可编辑、题注标准化的Word文档。

## 适用场景

- 中文教材、技术书籍的docx源文件格式化
- 从PDF转docx后的文档结构修复
- 需要将Unicode文本公式和图片公式转为Word可编辑OMML格式
- 需要将"图X-X"/"表X-X"文本转为标准Caption题注

## 触发条件

当用户提出以下意图时触发：
- "格式化这个docx"、"整理这个Word文档"
- "把标题变成样式"、"识别章节标题"
- "公式变成可编辑的"、"图片公式转OMML"
- "题注标注"、"图/表编号转Caption"
- 涉及docx文档的标题、公式、题注三大格式化需求

## 核心功能

### 1. 标题识别与样式应用

| 模式 | 正则 | 样式 |
|------|------|------|
| `第X章` | `^第\s*\d+\s*章\s+\S` | Heading1 |
| `X.X` | `^\d+\.\d+\s+\S` | Heading2 |
| `X.X.X` | `^\d+\.\d+\.\d+\s+\S` | Heading3 |

- 自动跳过目录条目（含"……"或"第X章...(页码)"格式）
- 在`styles.xml`中定义Heading1/2/3样式（SimHei字体，居中/左对齐）
- 支持通过`--heading1/2/3`参数自定义正则模式

### 2. Unicode文本公式 → OMML

检测段落中的Unicode下标/上标字符，将整个run转为`m:oMath`元素：

- 下标：₀₁₂₃₄₅₆₇₈₉ₐₑₒₓₙₘ → `m:sSub`
- 上标：⁰¹²³⁴⁵⁶⁷⁸⁹ⁿ → `m:sSup`
- 同时存在 → `m:sSubSup`

**注意**：标题和题注段落也执行公式转换（不因标题/题注处理而跳过）。

### 3. 题注识别与Caption样式

- 图题注：`图X-X 描述` → Caption样式（Figure SEQ域代码）
- 表题注：`表X-X 描述` → Caption样式（Table SEQ域代码）

**智能过滤**（`is_true_caption`）：
- 描述以"给出/示出/是/中，/所示/表示/描述/列出/说明/为"开头的不是题注
- 题注内容占段落<60%且段落>120字符的不是题注（避免误判正文引用）

### 4. 图片公式OCR → OMML（可选）

使用pix2tex(LaTeX-OCR)本地模型识别图片公式：

1. 检测条件：`w:drawing` + `wp:inline` + 高度3~30pt（排除装饰图标和普通图片）
2. 通过`document.xml.rels`映射rId→图片文件路径
3. pix2tex识别图片 → LaTeX字符串
4. `latex_to_omml.py`将LaTeX转为OMML `m:oMath`元素
5. 替换原`w:drawing`为`m:oMath`

**依赖**：`pip install pix2tex`（不安装则自动跳过OCR）
**注意**：PyTorch 2.6+需要patch `torch.load`的`weights_only`参数。

## 使用方式

### 方式一：脚本直接执行

```bash
# 基本用法（含OCR）
python3 scripts/format_docx.py input.docx output.docx

# 跳过OCR（更快）
python3 scripts/format_docx.py input.docx output.docx --no-ocr

# 自定义标题模式
python3 scripts/format_docx.py input.docx output.docx \
  --heading1 '^Chapter\s+\d+' \
  --heading2 '^\d+\.\d+' \
  --heading3 '^\d+\.\d+\.\d+'

# 自定义题注模式
python3 scripts/format_docx.py input.docx output.docx \
  --fig-pattern '^Fig\.\s*(\d+-\d+)\s*(.*)' \
  --tab-pattern '^Table\s*(\d+-\d+)\s*(.*)'

# 指定工作目录（便于调试）
python3 scripts/format_docx.py input.docx output.docx --work-dir /tmp/my_work
```

### 方式二：Agent执行流程

当Agent接收到docx格式化请求时，按以下步骤操作：

1. **确认需求**：向用户确认三项功能是否都需要（标题/公式/题注），是否需要OCR
2. **检查依赖**：确认`lxml`和`Pillow`已安装，OCR需确认`pix2tex`
3. **执行脚本**：运行`format_docx.py`，传入用户指定的docx路径
4. **验证结果**：解压输出docx，检查关键文件（`[Content_Types].xml`、`_rels/.rels`、`word/document.xml`）是否完整
5. **交付文件**：将格式化后的docx文件提供给用户

### Python API调用

```python
from format_docx import format_docx

cnt = format_docx(
    input_path='input.docx',
    output_path='output.docx',
    do_ocr=True,
    h1_pattern=None,  # 使用默认
    fig_pattern=None,  # 使用默认
    work_dir=None,     # 自动创建临时目录
)
print(f"处理结果: {cnt}")
```

## 技术架构

```
输入docx → 解包(unzip) → 修改XML → 重新打包(zip)
                │
                ├── styles.xml: 添加Heading1/2/3、Caption样式定义
                │
                ├── document.xml (Pass 1):
                │   ├── 标题识别 → pStyle设置
                │   ├── 题注识别 → Caption段落构建
                │   └── Unicode公式 → m:oMath替换
                │
                └── document.xml (Pass 2, 可选):
                    ├── 检测图片公式(inline drawing, h=3~30pt)
                    ├── pix2tex OCR → LaTeX
                    └── latex_to_omml → m:oMath替换drawing
```

## 脚本文件说明

| 文件 | 用途 |
|------|------|
| `scripts/format_docx.py` | 主格式化脚本（解包→处理→打包完整流程） |
| `scripts/latex_to_omml.py` | LaTeX→OMML递归下降转换器 |

## 关键注意事项

1. **打包必须从docx根目录开始**：`[Content_Types].xml`和`_rels/.rels`必须在ZIP根目录，否则Word打开后显示乱码
2. **styles.xml必须定义样式**：仅引用不存在的样式ID不会生效，必须在styles.xml中创建完整定义
3. **OCR模型首次加载较慢**：pix2tex模型约需30秒加载，后续识别很快
4. **图片公式判断标准**：高度3~30pt是经验值，可按文档实际情况调整
5. **题注误判防护**：`is_true_caption`的比率检测（60%/120字符阈值）可根据文档特点微调
6. **工作目录不会自动清理**：便于调试，用户可手动删除

## 依赖安装

```bash
# 基本依赖（必需）
pip install lxml Pillow

# 图片公式OCR（可选）
pip install pix2tex

# LaTeX-OCR模型会自动下载到 ~/.pix2tex
```

## 排错指南

| 问题 | 原因 | 解决 |
|------|------|------|
| 输出docx乱码/打不开 | 打包时漏掉了`[Content_Types].xml`或`_rels/.rels` | 确保从解包根目录（而非word/子目录）打包 |
| 标题样式不生效 | styles.xml中未定义对应样式 | 检查`add_styles()`是否正确添加 |
| 公式显示异常 | Unicode字符映射错误或OMML结构有误 | 检查`SUB_MAP`/`SUP_MAP`映射 |
| 图片公式未识别 | 高度阈值不匹配 | 调整`h_pt < 3 or h_pt > 30`的范围 |
| OCR结果不准确 | pix2tex模型限制 | 可改用Mathpix API等商业OCR服务 |
| LaTeX→OMML转换失败 | 不支持的LaTeX命令 | 在`latex_to_omml.py`的`_handle_command`中添加支持 |
