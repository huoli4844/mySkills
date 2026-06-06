---
name: source-prepare
description: 集成管线：将 .doc/.docx/.pdf 教材源文件转换为知识库可用的 MD + LaTeX 公式素材。.docx 内含 OLE 对象时，用 container_extract.py 零成本提取公式。自动检测文件类型，串联 formula-extract → docx-format → file2md → merge_source。
version: "1.5.0"
tags: [preprocessing, pipeline, textbook, docx, pdf, formula, md]
author: Hermes Agent
platforms: [macos]
related_skills: [formula-extract, docx-format, file2md, emc-textbook-wiki, domain-book-wiki]
---

# source-prepare — 知识库源文件预处理管线

将任意格式的教材源文件（.doc/.docx/.pdf）转换为 **emc-textbook-wiki 可用的 MD 出处文件** + **LaTeX 公式素材**。

## 管线架构

```
输入文件
  │
  ├── .doc ──→ ① formula-extract 提取公式 → _formulas/ (LaTeX + summary.json)
  │             ② textutil .doc → .docx
  │             ③ docx-format 格式化 (标题/题注)
  │             ④ file2md → MD + assets/
  │
  ├── .docx ──→ ① docx-format 格式化
  │             ② file2md → MD + assets/
  │
  └── .pdf  ──→ ① file2md (Docling) → MD + assets/
               ↓
        Ready for emc-textbook-wiki Step 3 (出处提取)
```

## 关键路径

### .doc 文件（旧版 Word + MathType OLE 公式）

这是最复杂的路径。`.doc` 格式的 OLE 公式无法被 pandoc 识别。

**处理策略**（双线并行）：

**线 A — 出处 MD**（供 Step 3 使用）：
```
.doc → textutil → .docx → docx-format → file2md → MD
                                   ↓
                             标题样式 · 图题注 · 表题注
```
- MD 中公式显示为 `EMBED Equation.3` 占位符（旧 OLE 对象无法转换）
- 正文文字、标题层级、图片引用、表格等完全保留

**线 B — 公式素材**（供 Step 5 知识要素使用）：
```
.doc → formula-extract/convert_all.py → latex/ (311个 .tex + summary.json)
                                       → omml/ (311个 .omml.xml)
```
- **311 个公式全部成功转换为可编辑 LaTeX**（经实测验证）
- 在 Step 5 创建知识要素时，从 `_formulas/summary.json` 中按需检索 LaTeX

### .docx 文件（新版 Word，推荐）

```text
.docx → docx-format → file2md → MD + assets/
                          ↓
                Pandoc OMML→LaTeX 自动转换
```
- 公式自动转为 `$...$` LaTeX，保真度最高
- 标题层级 / 题注 / 图片 / 表格全部保留
- **这是最优路径**

#### 如果 .docx 来自旧版 .doc 另存为（公式为 WMF 图片）

很多客户提供的 .docx 是由旧版 .doc（含 MathType 公式）直接另存为 .docx 而来。此时：
- docx 内无 OMML 公式
- docx 的 `word/media/` 下有大量 WMF 图片
- **但** `word/embeddings/` 下保存了原始的 OLE 对象（`oleObject*.bin` 文件）

**检测方法**：
```bash
python3 -c "
import zipfile
with zipfile.ZipFile('第2章.docx') as z:
    bins = [n for n in z.namelist() if 'embeddings' in n and n.endswith('.bin')]
    print(f'OLE 对象数: {len(bins)}')
"
```

**重要发现**：每个 `oleObject*.bin` 文件本身是一个 **OLE2 复合文档**（以 `d0cf11e0` 魔数开头），内部包含 `Equation Native` 流（MathType MTEF 二进制数据）。这些数据可以用 `mtef_to_latex.rb` 解析为 LaTeX。

**从 .docx 的内嵌 OLE 对象提取公式的工作流**（使用 `scripts/container_extract.py`）：

```bash
# 1. 一行命令提取 311 个 LaTeX 公式（零 API 成本）
python3 ~/.hermes/skills/research/source-prepare/scripts/container_extract.py \
  第2章.docx -o /tmp/formula_output

# 2. merge_source 将 LaTeX 替换回 MD
python3 ~/.hermes/skills/research/source-prepare/scripts/merge_source.py \
  --md formatted.md \
  --formulas /tmp/formula_output/latex/summary.json \
  --assets assets \
  -o 第2章-电磁兼容的电磁原理.md
```

**输出验证**：310 个 WMF → LaTeX 替换，57 个块级公式转为 Typora 格式。详见 `references/docx-embedded-ole-extraction.md`。

#### 如果公式是图片（客户提供的 .docx 中公式为截图）

```bash
# 启用 OCR 模式，将图片公式转为可编辑 LaTeX
python3 ~/.hermes/skills/research/source-prepare/scripts/prepare_source.py \
  book-with-image-formulas.docx \
  -o /path/wiki/出处 --split --ocr
```

**处理流程**：
```
.docx（公式为图片）
     ↓
docx-format（pix2tex OCR）
     ├── 检测 w:drawing + height 3~30pt 的图片（判断是否为公式）
     ├── 加载 LaTeX-OCR 模型识别图片内容
     ├── 转换为 LaTeX 字符串
     └── latex_to_omml.py → OMML 替换原图片
     ↓
file2md（pandoc OMML→$...$ LaTeX）
     ↓
MD 中公式为可编辑 LaTeX
```

**依赖**：
```bash
pip install pix2tex      # LaTeX-OCR 模型（首次加载约 30 秒）
```

**局限**：
- pix2tex 侧重印刷体公式识别，手写体效果下降
- 仅识别高度 3~30pt 的 inline 图片（排除装饰图标和正文插图）
- 模型首次加载约需 30 秒
- **不识别 WMF 格式**（旧版 .doc 另存为 .docx 时产生的 WMF 图片公式），详见下方「融合模式」

### 融合模式：.doc + .docx 对处理（推荐用于 WMF 图片公式）

当你有**一对同源文件**（`.doc` + `.docx`，例如教材的旧版 Word 和 新版 Word 保存），并且 `.docx` 中的公式是 **WMF 图片**（不可编辑），可以使用融合模式：用 `.doc` 的 formula-extract 提取 LaTeX 公式，注入到 `.docx` 的正文 MD 中。

**三步工作流：**

```bash
# 1. 处理 .doc → 获得 311 个 LaTeX 公式
python3 ~/.hermes/skills/research/source-prepare/scripts/prepare_source.py \
  book.doc -o /path/wiki/出处

# 2. 处理 .docx → 获得正文 MD + 图片 assets
python3 ~/.hermes/skills/research/source-prepare/scripts/prepare_source.py \
  book.docx -o /path/wiki/出处_docx

# 3. 融合 → 完整出处 MD（公式可编辑 + 插图保留）
python3 ~/.hermes/skills/research/source-prepare/scripts/merge_source.py \
  --md 出处_docx/formatted.md \
  --formulas 出处/_formulas/latex/summary.json \
  --assets 出处_docx/assets \
  -o 第2章-电磁兼容的电磁原理.md
```

**输出**：
```
output/
├── 第2章-电磁兼容的电磁原理.md    ← 全文 MD（公式为 LaTeX + 插图 ![]()）
└── assets/                        ← 非公式图片（插图/照片/表格）
    ├── 图2-1-空间场的计算.emf
    ├── 图2-5-基本电振子的等效.emf
    └── ...
```

**处理流程**：
```
.docx 正文 MD（file2md 输出）        .doc formula-extract LaTeX
│  ![](assets/image-001.wmf)   →       $\\nabla\\times\\vec{H}=j\\omega\\varepsilon\\vec{E}+\\vec{J}$
│  ![](assets/image-260.wmf)   →       $\\omega$（行内）
│  ![](assets/图2-1-xxx.emf)  保留     ← 非 WMF 插图，保留原样
│
↓ merge_source.py（按序替换 310 个 WMF → LaTeX）
↓ fix_formulas（清理 \\wideparen、空分母等问题）
↓
$$ \\nabla\\times\\vec{H}=j\\omega\\varepsilon\\vec{E}+\\vec{J} $$
式中，$\\omega$ 为源的角频率...
![图2-1-空间场的计算](assets/图2-1-空间场的计算.emf)
```

**已知问题**（merge_source 会自动修复）：
- `\wideparen{n}` → `\hat{n}`（非标 yhmath 命令，5+ 处）
- `\frac{Z_{12}}{}` → `Z_{12}`（空分母，~10 处）
- `\left\uf048` / `\right\uf049` → `\left(` / `\right)`（Unicode 损坏）
- `$$ formula $$` → Typora 兼容三行格式（53 处自动转换）

### .pdf 文件

```
.pdf → file2md (Docling) → MD + assets/
```
- Docling 结构化解析，保留布局/表格/标题
- **公式局限**：PDF 中的图片公式无法转为 LaTeX，公式显示为图片占位符
- 推荐优先找对应的 .docx 源文件

## 依赖安装

```bash
# 基础
pip install lxml olefile

# docx-format 依赖
pip install lxml Pillow

# file2md 依赖
brew install pandoc
pip install docling

# formula-extract 依赖（仅 .doc 需要）
git clone https://github.com/siefkenj/mathtype /tmp/mathtype
cd /tmp/mathtype && gem build mathtype.gemspec && gem install --user-install bindata
mkdir -p /tmp/mathtype/stubs/ole
cat > /tmp/mathtype/stubs/ole/storage.rb << 'RUBY'
module Ole; class Storage; def self.open(path, mode); end; end; end
RUBY
```

> macOS 自带 `textutil`，无需额外安装。

## 使用方式

### 一键处理

```bash
python3 scripts/prepare_source.py \
  "/path/to/第2章电磁兼容的电磁原理.doc" \
  -o /path/to/wiki/出处 \
  --split
```

### 参数说明

| 参数 | 说明 |
|:----|:----|
| `input` | 输入文件（.doc / .docx / .pdf），必需 |
| `-o / --output` | 输出目录，默认输入文件同目录 |
| `--split` | 按章节分割输出（file2md --split 模式） |
| `--no-ocr` | 禁用 PDF OCR（纯文本 PDF 加速） |
| `--ocr` | **启用图片公式 OCR**（pix2tex），将 .docx 中的图片公式转为可编辑 LaTeX。需安装 `pip install pix2tex` |\n| `--formula-recognize` | **启用 LLM 图片公式识别**（formula-extract），将 .docx 中的图片公式通过多模态 LLM（kimi-k2.6/GPT-4o）转为 LaTeX。需配置 `MOONSHOT_API_KEY` 或 `OPENAI_API_KEY` 环境变量。流程：docx-format → file2md → 检测 assets/ 中小尺寸图片 → extract_formula.py --batch → merge_source.py 替换 |
| `--formulas-dir` | 公式提取输出目录（默认 `{output}/_formulas/`） |
| `--skip-formulas` | 跳过公式提取（仅 .doc 模式） |

### 输出结构

```
输出目录/
├── 文件名.md                    ← 出处 MD（供 emc-textbook-wiki Step 3）
├── assets/                      ← 图片
│   ├── 图2-1-xxx.png
│   └── ...
└── _formulas/                   ← 公式素材（仅 .doc，供 Step 5）
    ├── latex/
    │   ├── eqn_0.tex            ← 311个 .tex 文件
    │   ├── eqn_1.tex
    │   ├── ...
    │   └── summary.json         ← 索引：name + latex + version
    └── omml/
        ├── eqn_0.omml.xml       ← 311个 OMML 文件
        ├── ...
        └── summary.json
```

**使用 --split 时**：

```
输出目录/
├── 文件名.md                    ← 完整文件
├── 第2章-电磁兼容的电磁原理.md    ← 按章节分割（每章一个文件）
├── assets/
└── _formulas/
```

## 管线详解

### Step 1: 文件类型检测

```python
def detect_type(path):
    ext = Path(path).suffix.lower()
    with open(path, 'rb') as f:
        header = f.read(8)
    if ext == '.doc':
        return 'doc'   # OLE2 / CFB
    elif ext == '.docx':
        return 'docx'  # ZIP + XML
    elif ext == '.pdf':
        return 'pdf'   # PDF
```

### Step 2.1: formula-extract（仅 .doc）

```bash
python3 ~/.hermes/skills/mlops/formula-extract/scripts/convert_all.py \
  "input.doc" \
  "_formulas/"
```

内部流程：
1. `olefile` 遍历 OLE ObjectPool → 提取 311 个 Equation Native 流
2. `ruby mathtype gem` 解析 MTEF v3/v5 二进制 → snapshot Hash
3. `mtef_to_latex.rb` 递归转换为 LaTeX
4. `latex_to_omml.py` 将 LaTeX 转为 OMML XML

实测结果：311/311 公式全部成功。

### Step 2.2: textutil 转换（仅 .doc）

```bash
textutil -convert docx "input.doc" -output "converted.docx"
```

macOS 原生工具，保留正文、图片、表格、布局。公式变为 OLE 占位符。

### Step 2.3: docx-format 格式化

```bash
python3 ~/.hermes/skills/docx-format/scripts/format_docx.py \
  "input.docx" "formatted.docx" --no-ocr
```

处理项目：
- 标题层级识别：`第X章` → Heading1，`X.X` → Heading2，`X.X.X` → Heading3
- 图题注 / 表题注 → Caption 样式
- 图片公式 OCR（可选，需 pix2tex）

### Step 2.4: file2md 转换

```bash
python3 ~/.hermes/skills/mlops/file2md/scripts/file2md.py \
  "formatted.docx" -o "输出目录" --split
```

Pandoc 驱动的 DOCX→MD 高保真转换：
- 标题层级保留为 `#/##/###`
- 图片提取到 `assets/`，用题注命名
- 表格转为 pipe table

## 与 emc-textbook-wiki / domain-book-wiki 的衔接

| 消费方 Step | 本管线的产出 | 用途 |
|:----------------------|:------------|:-----|
| domain-book-wiki Step 2 | **`00_正文/第N章.md`** + `assets/` | 作为出处源文件，按章节分割 |
| emc-textbook-wiki Step 3 (出处) | **`文件名.md`** + `assets/` | 同上 |
| **Step 5 (知识要素)** | **`_formulas/latex/summary.json`** | 公式素材检索，LaTeX 可直接嵌入知识要素 |
| Step 6~8 (知识点/技能点/场景) | — | 公式素材可从 _formulas 引用 |

### 当 prepare_source.py 无法处理 .docx 时（0标题、0OMML、全图片公式）

如果 .docx 不使用 Word 标题样式（所有段落 style='Normal'/NormalIndent），pandoc 无法检测标题层级，导致 `file2md --split` 输出异常：
- 输出 MD 中所有标题消失（显示为纯文本而非 `##`）
- 页眉页码污染正文（如 `22   电磁兼容原理与技术`）
- 公式为图片占位符 `[公式图片×N]`

**处理方案**：放弃 source-prepare 管线，用 python-docx 直接提取（详见 domain-book-wiki SKILL.md 的 Path E）。核心步骤：
1. 用 python-docx 逐段落检测字体大小（≥20pt → 章节标题）
2. 用节号模式 `N.M` 补全 `###` 标题标记
3. 跳过页眉页脚行
4. 输出到 `00_正文/第N章.md`

> 💡 `.docx` 中的嵌入 OLE 对象（`word/embeddings/oleObject*.bin`）可提取为 LaTeX。详见 `references/docx-embedded-ole-extraction.md`。

### Step 3 集成命令

```bash
# 管线产出在 出处/ 目录后，emc-textbook-wiki 直接使用
ls 出处/第2章-电磁兼容的电磁原理.md
```

### Step 5 公式素材使用

当创建知识要素需要公式时，从 `_formulas/latex/summary.json` 中检索：

```python
import json
with open('出处/_formulas/latex/summary.json') as f:
    formulas = json.load(f)
# 按内容关键词搜索对应公式
# 例如：检索 "nabla" 找旋度方程
```

## OLE 提取失败（非 MathType 对象的处理）

当 .docx 来自旧版 .doc 的另存为，OLE 对象可能不含 MathType Equation Native 流（而是 Visio 图表、Excel 工作表等嵌入对象）。症状：
- `container_extract.py` 输出 "无 Equation Native 流"（689/689 错误）
- OLE 对象魔数为 `d0cf11e0`（OLE2 容器）但内部流非 Equation Native

**处理方案**：
- 直接使用 file2md 输出（WMF 图片公式作为 `![](assets/image-NNN.wmf)` 占位符）
- 放弃 merge_source 融合步骤
- 生成 YAML 数据时，根据源文上下文手动编写 LaTeX 公式
- WMF 图片在 macOS/Typora 中不显示，需在生成 YAML 时手动补充公式内容

## 已知限制

| 限制 | 说明 |
|:----|:------|
| **.doc 公式不直接出现在 MD 中** | textutil 转换将 OLE 公式变为 `EMBED Equation.3` 占位符。公式 LaTeX 仅保存在 `_formulas/` 供 Step 5 使用 |
| **.doc 标题变为粗体** | textutil 转换不保留 Word 标题样式，`第N章` 变为 `**第N章**` 粗体文本而非 `##` 标题。`--split` 在此模式下可能无法自动分割章节 |
| **.doc 不能直接 .md** | 必须经 .doc → .docx → .md 两步 |
| **.docx 保留公式但 .doc 不行** | 如果有 .docx 源文件，公式保真度最高 |
| **.pdf 公式为图片** | Docling 无法将图片公式转为 LaTeX |
| **.docx 公式为图片** | 客户提供的 .docx 中公式可能是截图（非可编辑 OMML） | 使用 `--ocr` 参数启用 pix2tex OCR 识别图片公式 |
| **Typora 不显示块级公式** | `$$ formula $$` 单行格式 Typora 不识别 | `merge_source.py` 的 `fix_formulas()` 自动转换为 `$$\nformula\n$$` 三行格式 |
| **题注编号重置** | docx-format 的 Caption SEQ 域代码使题注编号从 1 开始独立编号，不保留原始编号 |
| docx 嵌入 OLE 对象提取 |  | scripts/container_extract.py 提取 → merge_source 替换。详见 references/docx-embedded-ole-extraction.md |

## 标题修复（docx-format 后处理）

当 source-prepare 处理 .docx 后，`## 2.1 基本电磁原理` 可能变为纯文本 `2.1 基本电磁原理`。使用以下脚本修复：

```python
import re

with open('output.md', 'r', encoding='utf-8') as f:
    content = f.read()

lines = content.split('\n')
fixed = []
for line in lines:
    stripped = line.strip()
    # Match "2.1" or "2.1.1" patterns at line start
    m = re.match(r'^(\d+)\.(\d+)(?:\.(\d+))?\s+(.+)$', stripped)
    if m and not stripped.startswith('#') and not line.startswith('!['):
        sub = m.group(3)
        if sub:  # 2.1.1 → ###
            fixed.append(f"### {stripped}")
        else:    # 2.1 → ##
            fixed.append(f"## {stripped}")
    else:
        fixed.append(line)

with open('output.md', 'w', encoding='utf-8') as f:
    f.write('\n'.join(fixed))
```

**何时需要**：运行 `prepare_source.py` 后，检查输出 MD 中是否有 `2.1 基本` 等裸编号行。如发现则运行修复。

| 问题 | 原因 | 解决 |
|:----|:------|:-----|
| .doc 转 .docx 失败 | textutil 不支持该格式 | 确认是 OLE2 CFB 格式 .doc |
| formula-extract 报 Ruby 错误 | ole/storage 桩未创建 | 运行依赖安装中的 `mkdir -p /tmp/mathtype/stubs/ole && ...` |
| file2md 0 标题/0 公式 | 源 docx 中无对应结构 | .doc 经 textutil 会丢失公式，属正常 |
| file2md --split 不分章 | 标题格式不符 | file2md 按 `第N章` 分割，确认标题含该模式 |
| **处理后标题标记丢失**（`2.1` 无 `##` 前缀） | docx-format 转换标题样式后，pandoc 无法识别为 heading | 后处理用 Python 正则修复：识别行首 `\\d+\\.\\d+` 等模式，添加 `##`/`###` 前缀。示例见下方「标题修复」|
| 图片缺失 | assets/ 目录未随 MD 一起拷贝 | 拷贝 MD 时需同时拷贝 assets/ 目录 |
| Typora 中公式以纯文本显示 | `$$ formula $$` 单行格式 | fusion_output.md 已自动转换为三行格式；若手动编辑过公式块，确认 `$$` 独占一行 |
| Typora 中行内公式显示为 `$...$` | 内联公式未在 Typora 偏好设置中启用 | Typora → 偏好设置 → Markdown → 内联公式（勾选） |

## 版本历史

| 版本 | 日期 | 说明 |
|:-----|:-----|:------|
| v1.4.0 | 2026-05-27 | 新增 `--formula-recognize` 参数：检测 .docx 中的图片公式，通过 formular-extract `extract_formula.py`（LLM 多模态识别）转为 LaTeX，并由 `merge_source.py` 替换 MD 中的图片引用。`step_formula_recognition()` 使用 docx 中 drawing 高度检测（3~30pt）+ PIL 图片尺寸过滤公式候选。合并时 `merge_source.py` 支持 `![image](assets/image-NNN.png)` 模式（不限于 .wmf）。 |\n| v1.3.1 | 2026-05-27 | 修复 `detect_file_type()` 在传入字符串参数时的 `AttributeError`（Path.exists 不兼容 str），增加 `isinstance(path, str)` 自动转换 |
| v1.3.0 | 2026-05-26 | 新增 .docx 嵌入 OLE 对象（oleObject*.bin）提取技术文档：每个 bin 本身是 OLE2 容器，内部含 Equation Native 流，可用 mtef_to_latex.rb 解析为 LaTeX。详见 references/docx-embedded-ole-extraction.md。 |
| v1.2.0 | 2026-05-26 | 初始版本 |
