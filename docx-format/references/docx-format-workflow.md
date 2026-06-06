# docx-format 工作流详细参考

## 1. docx文件结构

docx本质是ZIP包，核心结构：

```
docx (ZIP)
├── [Content_Types].xml    ← 内容类型定义（必须在ZIP根目录！）
├── _rels/
│   └── .rels              ← 全局关系（必须在ZIP根目录！）
├── docProps/
│   ├── app.xml
│   └── core.xml
└── word/
    ├── document.xml       ← 主文档内容
    ├── document.xml.rels  ← 文档关系（图片rId映射等）
    ├── styles.xml         ← 样式定义
    ├── numberings.xml     ← 编号定义
    ├── settings.xml       ← 文档设置
    ├── headers/
    ├── footers/
    ├── theme/
    └── media/             ← 图片资源
        ├── image1.jpeg
        └── image2.png
```

## 2. XML命名空间

```python
W  = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'      # Word
M  = '{http://schemas.openxmlformats.org/officeDocument/2006/math}'       # Math (OMML)
R_NS = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'  # 关系
WP = '{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}'  # Drawing
A  = '{http://schemas.openxmlformats.org/drawingml/2006/main}'            # Drawing ML
XML_NS = '{http://www.w3.org/XML/1998/namespace}'                         # XML
```

## 3. 标题处理细节

### 检测逻辑

```python
# 优先级：H1 > H3 > H2（H3必须在H2之前检查，因为X.X.X也匹配X.X）
if re.match(r'^第\s*\d+\s*章\s+\S', text):
    h_level = 'Heading1'
elif re.match(r'^\d+\.\d+\.\d+\s+\S', text):
    h_level = 'Heading3'
elif re.match(r'^\d+\.\d+\s+\S', text) and not re.match(r'^\d+\.\d+\.\d+', text):
    h_level = 'Heading2'
```

### 样式应用

```xml
<!-- 修改前 -->
<w:p>
  <w:pPr>
    <w:pStyle w:val="Normal"/>
    <w:outlineLvl w:val="0"/>
  </w:pPr>
  <w:r><w:t>第1章 电磁兼容概述</w:t></w:r>
</w:p>

<!-- 修改后 -->
<w:p>
  <w:pPr>
    <w:pStyle w:val="Heading1"/>
    <!-- outlineLvl已移除 -->
  </w:pPr>
  <w:r><w:t>第1章 电磁兼容概述</w:t></w:r>
</w:p>
```

关键：必须移除`w:outlineLvl`，否则Word可能忽略pStyle的标题级别。

### styles.xml定义要求

Word不会自动创建样式定义——如果styles.xml中没有对应styleId，即使段落引用了该样式也不会生效。必须在styles.xml中手动创建：

```xml
<w:style w:type="paragraph" w:styleId="Heading1">
  <w:name w:val="heading 1"/>
  <w:basedOn w:val="Normal"/>
  <w:next w:val="Normal"/>
  <w:qFormat/>
  <w:pPr>
    <w:keepNext/>
    <w:keepLines/>
    <w:spacing w:before="340" w:after="340"/>
    <w:jc w:val="center"/>
    <w:outlineLvl w:val="0"/>
  </w:pPr>
  <w:rPr>
    <w:b/><w:bCs/>
    <w:rFonts w:ascii="SimHei" w:hAnsi="SimHei" w:eastAsia="SimHei"/>
    <w:sz w:val="32"/><w:szCs w:val="32"/>
  </w:rPr>
</w:style>
```

## 4. Unicode公式转换

### 字符映射表

| 下标字符 | 映射 | 上标字符 | 映射 |
|---------|------|---------|------|
| ₀₁₂₃₄₅₆₇₈₉ | 0123456789 | ⁰¹²³⁴⁵⁶⁷⁸⁹ | 0123456789 |
| ₐₑₒₓₙₘ | aeonxm | ⁿ | n |

### OMML结构

```
U_dBV → <m:oMath>
           <m:sSub>
             <m:e><m:r><m:t>U</m:t></m:r></m:e>
             <m:sub><m:r><m:t>dBV</m:t></m:r></m:sub>
           </m:sSub>
         </m:oMath>
```

### 处理边界

- 公式run必须包含Unicode下标/上标字符才触发转换
- 标题和题注段落不跳过公式检测（v5修复的关键bug）
- `run_text.rstrip()`去除尾部空白避免公式结构错乱

## 5. 题注处理

### Caption段落结构

```xml
<w:p>
  <w:pPr><w:pStyle w:val="Caption"/></w:pPr>
  <w:r><w:t>图</w:t></w:r>
  <w:r><w:fldChar w:fldCharType="begin"/></w:r>
  <w:r><w:instrText xml:space="preserve"> SEQ Figure \* ARABIC </w:instrText></w:r>
  <w:r><w:fldChar w:fldCharType="separate"/></w:r>
  <w:r><w:t>5-24</w:t></w:r>
  <w:r><w:fldChar w:fldCharType="end"/></w:r>
  <w:r><w:t xml:space="preserve">　描述文字</w:t></w:r>
</w:p>
```

### is_true_caption过滤逻辑

两级过滤：

1. **非题注起始词**：描述以"给出/示出/是/中，/所示/表示/描述/列出/说明/为/中给/中示"开头 → 排除
2. **比率检测**：
   - `caption_len / para_len >= 0.6` → 是题注（题注占段落大部分）
   - `para_len <= 120` → 是题注（短段落更可能是题注）
   - 否则 → 不是题注（正文中的引用"如图5-24所示"）

### 为什么要保留原pPr属性

`build_caption`保留原段落的缩进、对齐等属性（除pStyle和outlineLvl），确保题注外观一致。

## 6. 图片公式OCR

### 检测条件

```python
# 必须同时满足：
1. w:drawing 存在
2. wp:inline 存在（非anchor浮动图）
3. extent.cy / 12700 在 3~30pt 之间
4. blip的rId在document.xml.rels中有对应media文件
5. 段落中尚未有m:oMath元素（避免重复处理）
```

### rId映射链

```
document.xml → w:drawing → wp:inline → a:blip r:embed="rId7"
                                              ↓
document.xml.rels → <Relationship Id="rId7" Target="media/image42.jpeg"/>
                                              ↓
word/media/image42.jpeg → 实际图片文件
```

### pix2tex使用注意事项

1. **PyTorch 2.6+兼容**：需要patch `torch.load`的`weights_only`参数
   ```python
   import torch
   original_load = torch.load
   def patched_load(*args, **kwargs):
       if 'weights_only' not in kwargs:
           kwargs['weights_only'] = False
       return original_load(*args, **kwargs)
   torch.load = patched_load
   ```

2. **去重优化**：同一图片可能被多次引用，用`seen_images`字典缓存OCR结果

3. **替换逻辑**：将`w:drawing`的父`w:r`整体替换为`m:oMath`（保持段落结构完整）

## 7. LaTeX→OMML转换器

`latex_to_omml.py`实现了递归下降解析器，支持：

| 类别 | 示例 | OMML元素 |
|------|------|---------|
| 上下标 | `x^2`, `x_1` | `m:sSup`, `m:sSub` |
| 分数 | `\frac{a}{b}` | `m:f` |
| 根号 | `\sqrt{x}`, `\sqrt[3]{x}` | `m:rad` |
| 希腊字母 | `\alpha`, `\beta` | Unicode字符 |
| 大运算符 | `\sum`, `\int` | Unicode字符 |
| 函数 | `\sin`, `\ln` | 正体`m:r` |
| 重音 | `\bar{x}`, `\hat{x}` | `m:acc` |
| 矩阵 | `\begin{pmatrix}` | `m:m` + `m:d` |
| 字体 | `\mathrm{x}`, `\mathbf{x}` | `m:rPr/m:sty` |

扩展方法：在`_handle_command`方法中添加新的cmd分支即可。

## 8. 打包关键规则

**最常见的bug**：打包时只打包了`word/`子目录，漏掉了ZIP根目录的`[Content_Types].xml`和`_rels/.rels`，导致Word无法识别文件。

正确的打包流程：

```python
# ✅ 正确：从docx根目录打包
pack_docx('unpacked_docx_root/', 'output.docx')

# ❌ 错误：从word/子目录打包
pack_docx('unpacked_docx_root/word/', 'output.docx')  # 丢失关键文件！
```

验证方法：

```python
with zipfile.ZipFile('output.docx', 'r') as zf:
    names = zf.namelist()
    assert '[Content_Types].xml' in names
    assert '_rels/.rels' in names
    assert 'word/document.xml' in names
```

## 9. 性能参考

基于9MB、980文件的中文教材docx实测：

| 步骤 | 耗时 |
|------|------|
| 解包 | <1s |
| styles.xml修改 | <1s |
| Pass1（标题+题注+Unicode公式） | 3-5s |
| pix2tex模型加载 | 30s（首次） |
| Pass2（132个图片公式OCR+替换） | 60-90s |
| 打包 | 2-3s |
| **总计（含OCR）** | ~2分钟 |
| **总计（--no-ocr）** | ~10秒 |
