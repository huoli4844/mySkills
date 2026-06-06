---
name: formula-extract
description: 从 EMF/WMF/PNG 矢量/位图或 .doc 文件中提取数学公式，输出 LaTeX + OMML
tags: [formula, latex, omml, math, mtef, doc]
related_skills: [source-prepare]
---

# formula-extract 技能

从 EMF/WMF/PNG 等矢量/位图文件或旧版 Word .doc（MTEF 公式）中提取**可编辑数学公式**，输出 Markdown 和 Word 同时可用的格式。

## 核心特点

- **零本地重型依赖**：不依赖 LibreOffice、ImageMagick
- **在线 LLM 驱动公式识别**：使用 kimi-k2.6 / GPT-4o 等多模态大模型，识别准确率远超传统 OCR
- **MTEF 原生解析（推荐）**：直接解析 .doc 中的 MathType Native 数据，零网络依赖，311 公式/秒级处理
- **双格式输出**：
  - LaTeX（`$...$` / `$$...$$`）→ Markdown 直接可用
  - OMML → 可直接嵌入 Word docx 的 `<m:oMath>`

## 文件结构

```
formula-extract/
├── SKILL.md                          # 本文档
└── scripts/
    ├── extract_formula.py            # 主脚本: 在线 LLM 公式识别 (EMF/WMF/PNG)
    ├── extract_docx_previews.py      # 辅助脚本: 从 docx 提取 PNG 预览
    ├── mtef_to_latex.rb              # MTEF 原生解析器: .doc → LaTeX
    └── convert_all.py                # 整合脚本: .doc → LaTeX + OMML
```

## 依赖安装

### 在线 LLM 方案

```bash
pip install lxml Pillow requests olefile
```

### MTEF 原生解析方案（推荐用于原始 .doc）

```bash
# 1. Python 依赖
pip install lxml olefile

# 2. Ruby 依赖（mathtype gem，含 MTEF v3/v5 解析器）
git clone https://github.com/siefkenj/mathtype /tmp/mathtype
cd /tmp/mathtype && gem build mathtype.gemspec && gem install --user-install bindata

# 3. 创建 ole/storage 桩（⚡必做：rubygems 上不存在 ole-storage 包）
mkdir -p /tmp/mathtype/stubs/ole
cat > /tmp/mathtype/stubs/ole/storage.rb << 'RUBY'
# Stub for ole/storage — mtef_to_latex.rb reads .bin directly, no OLE parsing needed
module Ole; class Storage; def self.open(path, mode); end; end; end
RUBY
```

> `latex_to_omml.py` 来自 `docx-format` 技能，确保该技能在同一工作空间。
>
> ⚠ `formula-extract` 在 `mlops/` 子目录下时，`convert_all.py` 会自动向上多跳一级查找 `docx-format`。

## API 密钥配置

**必须**: LLM API 密钥（公式识别）
**可选**: ConvertAPI 密钥（仅在无法获取 PNG 预览时使用）

### 1. Moonshot / OpenAI（公式识别）— 必须

**Moonshot (kimi-k2.6)：**
- 注册：https://platform.moonshot.cn/
- 设置环境变量：
  ```bash
  export MOONSHOT_API_KEY="sk-xxxxxxxx"
  ```

**OpenAI (GPT-4o)：**
- 设置环境变量：
  ```bash
  export OPENAI_API_KEY="sk-xxxxxxxx"
  ```

### 2. ConvertAPI（可选备用）

只有当你的 EMF/WMF **没有对应的 PNG 预览** 时才需要：
- 注册：https://www.convertapi.com/
- 免费额度：每天 1500 秒转换时间 + 250 MB
- 设置环境变量：
  ```bash
  export CONVERTAPI_SECRET="your-secret-here"
  ```

> 推荐优先使用「从 docx 提取 PNG 预览」或「同目录手动转换」，完全不需要 ConvertAPI。

## 用法

### 方案 A：MTEF 原生解析（推荐用于原始 .doc）

如果你的源文件是**旧版 Word .doc**（含 MathType 公式），这是**最准确、零网络依赖**的方案。直接从 .doc 的 OLE 对象中提取 MathType Native 数据，解析 MTEF 二进制格式，输出 LaTeX + OMML。

**一键转换：**

```bash
cd /Users/huoli4844/.hermes/skills/mlops/formula-extract/scripts
python3 convert_all.py \
  "/path/to/第2章电磁兼容的电磁原理.doc" \
  ./formula_output

# 输出:
#   ./formula_output/latex/        # 311 个 .tex 文件 + summary.json
#   ./formula_output/omml/         # 311 个 .omml.xml 文件 + summary.json
```

**summary.json 格式：**

```json
{
  "total": 311,
  "success": 311,
  "errors": 0,
  "formulas": [
    {"name": "eqn_0", "latex": "\\nabla\\times\\vec{H}=j\\omega\\varepsilon\\vec{E}+\\vec{J}", "version": 3},
    ...
  ]
}
```

**技术原理：**

```
.doc (OLE2)
  └─ ObjectPool/.../Equation Native 流
        ├─ 28 bytes OLE 头
        └─ MTEF v3/v5 数据
              ├─ CHAR 记录 (Unicode + embellishments)
              ├─ TMPL 记录 (分数、根号、积分、上下标...)
              ├─ LINE/PILE/MATRIX 记录
              └─ END 记录
                    ↓
              Ruby mathtype gem 解析为 snapshot Hash
                    ↓
              mtef_to_latex.rb 递归转换为 LaTeX
                    ↓
              latex_to_omml.py 转为 OMML
```

**支持的结构：**

| MTEF 记录 | LaTeX 输出 | 示例 |
|-----------|-----------|------|
| CHAR + embRARROW | `\vec{}` | H⃗ → `\vec{H}` |
| tmSUB | `_{}` | H₂ → `H_{2}` |
| tmSUP | `^{}` | I^jωt → `I^{j\omega t}` |
| tmFRACT | `\frac{}{}` | 1/2 → `\frac{1}{2}` |
| tmPAREN | `\left( \right)` | (a/b) → `\left( \frac{a}{b} \right)` |
| tmROOT | `\sqrt{}` / `\sqrt[]{}` | √x → `\sqrt{x}` |
| tmINTEG | `\int` | ∫f(x)dx → `\int f(x)dx` |
| tmSUM | `\sum` | Σ → `\sum` |
| tmVEC | `\vec{}` | 矢量箭头 |
| tmHAT | `\hat{}` | Ĥ → `\hat{H}` |
| tmBOX | `\boxed{}` | 方框 |

### 方案 B：在线 LLM 识别（用于 EMF/WMF/PNG 图片）

##### 单文件处理（EMF/WMF 自动转换）

```bash
cd /Users/huoli4844/.hermes/skills/mlops/formula-extract/scripts

# 使用默认的 Moonshot/kimi-k2.6
python3 extract_formula.py \
  "/Users/huoli4844/Desktop/电磁兼容/出处/assets/图2-27-漏感产生的反电动势.wmf"

# 输出保存在 ./formula_output/
#   - 图2-27-漏感产生的反电动势.latex.md
#   - 图2-27-漏感产生的反电动势.omml.xml
```

#### 已有 PNG，直接识别

```bash
python3 extract_formula.py formula.png --no-convert
```

#### 使用 OpenAI GPT-4o

```bash
python3 extract_formula.py formula.png \
  --provider openai \
  --model gpt-4o
```

#### 方式一：从原始 docx 提取 PNG 预览（推荐，零 ConvertAPI）

如果你的 EMF/WMF 是从 Word docx 中提取的，原始 docx 里通常同时存了 PNG/JPEG 预览：

```bash
# 批量从多个章节 docx 中提取所有 PNG 预览
python3 extract_docx_previews.py "/path/to/书籍目录" \
  --batch -o ./assets/ --report

# 输出:
#   ./assets/第3章 电磁兼容预测/
#     image1.png   ← 对应 image1.emf 的预览
#     image2.png   ← 对应 image2.wmf 的预览
#   ./assets/mapping.json  ← emf→png 映射表
```

提取后，直接把 PNG 给主脚本识别：
```bash
python3 extract_formula.py ./assets/第3章\ 电磁兼容预测/ --batch --no-convert
```

#### 方式二：同目录已有 PNG 预览（自动检测）

如果 `图2-27.wmf` 旁边已经有 `图2-27.png`，主脚本会自动检测到并直接使用，**无需任何配置**：

```bash
python3 extract_formula.py 图2-27-漏感产生的反电动势.wmf
# 输出: [发现] 同目录存在位图预览，直接使用: 图2-27-漏感产生的反电动势.png
```

#### 批量处理目录

```bash
python3 extract_formula.py /path/to/assets/ --batch -o ./output/
```

#### 保留转换后的 PNG

```bash
python3 extract_formula.py input.wmf --keep-png
# 同时输出: output/图2-27.../图2-27....png
```

#### 完整参数

```bash
python3 extract_formula.py <input> \
  -o ./output                    # 输出目录 \
  --provider moonshot            # LLM 提供商: moonshot|openai|custom \
  --model kimi-k2-6              # 模型名称 \
  --api-key sk-xxx               # API 密钥（覆盖环境变量） \
  --convertapi-secret secret     # ConvertAPI 密钥（覆盖环境变量） \
  --no-convert                   # 跳过 EMF/WMF 转换（输入已是图片） \
  --batch                        # 批量处理目录 \
  --keep-png                     # 保留在线转换后的 PNG
```

## 工作流程

### 方案 A：MTEF 原生解析

```
.doc (OLE2)
    │
    └─ [olefile] 提取 Equation Native 流 (311个)
                │
                ↓
        [Ruby mathtype gem] 解析 MTEF v3/v5
                │
                ↓
        Snapshot (Hash: CHAR/TMPL/LINE/PILE...)
                │
                ↓
        [mtef_to_latex.rb] 递归转换为 LaTeX
                │
        ┌───────┴───────┐
        ↓               ↓
   .tex (LaTeX)    [latex_to_omml.py]
   (Markdown)              ↓
                      .omml.xml
                      (Word docx)
```

### 方案 B：在线 LLM 识别

```
输入文件
    │
    ├─ EMF/WMF/EMZ/WMZ ──→ [ConvertAPI 在线转换] ──→ PNG
    │
    └─ PNG/JPG/GIF/BMP ──→ 直接使用
                │
                ↓
        [base64 编码]
                │
                ↓
        [Moonshot / OpenAI 多模态 API]
        提示词: "识别数学公式，只输出纯 LaTeX"
                │
                ↓
        LaTeX 字符串
                │
        ┌───────┴───────┐
        ↓               ↓
   .latex.md       .omml.xml
   (Markdown)      (Word docx)
```

## 输出文件说明

### `.tex` — Markdown 可用

```tex
$\nabla\times\vec{H}=j\omega\varepsilon\vec{E}+\vec{J}$
```

直接在 Markdown 中渲染为数学公式。

### `.omml.xml` — Word 可用

```xml
<ns0:oMath xmlns:ns0="http://schemas.openxmlformats.org/officeDocument/2006/math">
  <ns0:r><ns0:t>∇</ns0:t></ns0:r>
  <ns0:acc>
    <ns0:accPr><ns0:chr ns0:val="⃗"/></ns0:accPr>
    <ns0:e><ns0:r><ns0:t>H</ns0:t></ns0:r></ns0:e>
  </ns0:acc>
  ...
</ns0:oMath>
```

插入 docx 的 `word/document.xml` 中即可在 Word 内编辑。

## 已知问题与修复

### 0. LaTeX 输出伪影（MTEF→LaTeX 转换）

MTEF→LaTeX 转换会产生一些已知伪影：`\wideparen{n}`（非标命令）、空分母 `\frac{}{}`、Unicode 损坏 `\uf048`/`\uf049`、积分下标过长。详见 `references/mtef-latex-artifacts.md`。

推荐在 formula-extract 输出后使用 `fix_formulas()` 自动修复（集成在 `source-prepare/scripts/merge_source.py` 中）。

### 1. `ole/storage` 缺失

mathtype 库的 `file_parser/ole.rb` 依赖 `ole/storage`，但 rubygems 上 **不存在** `ole-storage` 包。
`mtef_to_latex.rb` **实际上不经过** `OleFileParser`（它直接读取已提取的 .bin 文件），但仍然会因 `require` 失败。

**解决方法**：在 `/tmp/mathtype/stubs/` 下创建桩，并通过 `-I` 参数加入 Ruby 加载路径。

`convert_all.py` 已自动添加 `-I /tmp/mathtype/stubs` 参数。

### 2. 跨技能路径解析

`convert_all.py` 导入 `docx-format/scripts/latex_to_omml.py`。由于 `formula-extract` 在 `mlops/` 子目录下，父级路径需要向上多跳一级。
`convert_all.py` 已自动检测 `mlops/` 层级并修正。

### 3. MATH_UNICODE 重复键

`mtef_to_latex.rb` 的 `MATH_UNICODE` 哈希表包含 100+ 对重复键（`0x221A`、`0x2282` 等）。Ruby 2.6+ 会输出 warning，不影响功能。
如需清除，删除低优先级（第 150-420 行）的重复条目。

## 适用性前置检查

**运行前先确认你的公式存在形式：**

```bash
python3.12 -c "
import zipfile
with zipfile.ZipFile('第N章.docx') as z:
    xml = z.read('word/document.xml').decode()
    omath = xml.count('<m:oMath')
    mtef = xml.count('Equation Native')
    print(f'OMML: {omath}, MTEF: {mtef}')
"
```

| 结果 | 可用方案 |
|:-----|:---------|
| OMML > 0 | 直接提取 OMML → LaTeX（零网络） |
| MTEF > 0 | MTEF 原生解析（零网络，需 .doc 非 .docx） |
| **OMML=0 且 MTEF=0** | **必须 LLM API（Moonshot/OpenAI），无离线路径** |

### 无 API 时的降级方案

当 `.docx` 中公式全为图片（OMLL=0, MTEF=0）且无 API key 时：

1. **不适用 formula-extract** — 所有方案均需要 API
2. **检查 domain-book-wiki 概念 YAML** — 概念创建时可能已将公式文本存入 `mathematical_model` 字段（ASCII 格式）
3. **ASCII→LaTeX 转换**：如果已有 ASCII 公式，直接包装 `$$...$$` 即可在 Obsidian 渲染
4. **降级无公式概念**：源文和概念均无公式的概念应降级为 KE（知识要素）

> 详见 `domain-book-wiki` 技能的 `references/concept-formula-gate.md`

## 常见问题

### Q: 不想用 ConvertAPI？

完全可以不用。三种替代方案：

1. **从原始 docx 提取 PNG 预览**（推荐）：
   ```bash
   python3 extract_docx_previews.py 第3章.docx -o ./assets/
   python3 extract_formula.py ./assets/ --batch --no-convert
   ```

2. **同目录放同名 PNG**：把 `xxx.png` 放在 `xxx.wmf` 旁边，脚本自动检测使用

3. **手动转换**：用在线网站（cloudconvert.com）把 EMF/WMF 拖进去转 PNG，然后用 `--no-convert`

### Q: 公式识别不准确？

- 尝试更换模型：`--model kimi-k2-6` 或 `--model gpt-4o`
- 确保图片清晰、对比度高
- 对于手写公式，识别率会下降

### Q: OMML 转换失败？

某些复杂 LaTeX 结构（如复杂的矩阵、自定义宏）可能无法完美转为 OMML。此时 `.tex` 中的 LaTeX 仍然是准确的，可手动在 Word 的公式编辑器中输入。

## 技术细节

- **EMZ/WMZ 解压**：使用 Python 标准库 `gzip`，纯本地处理
- **图片编码**：`base64` 嵌入 LLM 请求，无需上传图床
- **LaTeX → OMML**：复用 `docx-format` 技能中的 `latex_to_omml.py`，支持上下标、分数、根号、希腊字母、积分、矩阵等常见结构

## 扩展：自定义 LLM 提供商

支持任何 OpenAI-compatible API：

```bash
python3 extract_formula.py formula.png \
  --provider custom \
  --base-url https://api.your-provider.com/v1 \
  --api-key sk-xxx \
  --model your-model-name
```
