# MD→DOCX 转换指南（v6 — MathML→OMML 管线）

## 目标

教材 Markdown（专为 Obsidian 编写，含 `$$` LaTeX 公式、`\tag` 编号、````mermaid` 图、pipe table）→ Word docx，其中：
- **公式必须是 OMML（可双击编辑的 Word 原生方程）**，不能是静态文本或图片
- **表格必须是原生 Word 表格**（可用样式）
- **Mermaid 图** → 源码+说明文字（Word 不支持渲染）
- **零 Markdown 语法残留**：`**`/`####`/`---`/`- ` 等必须全部转换为 Word 原生格式

## 转换引擎：`scripts/md_to_docx.py`

v6 版本改用两层管线处理公式：

```
Markdown → parse_blocks() → 逐块处理:
  ├─ #/##/###/####/#####/###### → doc.add_heading(content, level=min(n,3))
  ├─ --- 分隔线                  → w:pBdr 底部边框段落
  ├─ - /*/+ 无序列表              → 缩进段落 + • 前缀
  ├─ 1. /1) 有序列表              → 缩进段落 + 编号前缀
  ├─ 普通段落                     → process_markdown_text() 处理行内标记
  ├─ $$ 块公式                   → convert_formula() → oMath 插入  [UPDATED]
  ├─ 管道表格                     → doc.add_table() (python-docx Table API)
  ├─ ```mermaid                  → "📊 Mermaid 图" + 等宽源码段落
  ├─ 其他 ```code                → 等宽字体段落
  └─ 空行                        → 跳过
```

## 公式管线（v6 重大变更）

### 旧方案（已弃用）：手写 LaTeX 解析器

`scripts/latex_to_omml.py` 用递归下降法解析 LaTeX，对以下命令支持不完整：
- `\xrightarrow{文字}` — 降级为 `文字 \to`，丢失箭头语义
- `\begin{aligned}` — 矩阵结构不正确
- `\left(` / `\right)` — 括号大小丢失
- `\text{中文/μV}` — 特殊 Unicode 字符可能渲染异常

**不推荐继续使用。** 保留仅用于向后兼容和简单公式场景。

### 新方案（推荐）：LaTeX → latex2mathml → MathML → OMML

```
$$ LaTeX公式 $$
     │
     ▼
latex2mathml (成熟库，处理所有 LaTeX 边缘情况)
     │
     ▼
     MathML XML (标准化结构)
     │
     ▼
mathml_to_omml.py (本技能新增：MathML tag → OMML tag 一对一映射)
     │
     ▼
  <m:oMath> 元素（可双击编辑）
```

**优势：**
- latex2mathml 处理了 `\xrightarrow`、`\begin{aligned}`、`\left/right`、`\text{中文μV}`、`\boxed` 等全部边缘情况
- MathML 是有规整 XML 结构的标准化格式，MathML→OMML 是一对一标签映射（约 80 行核心代码），远易于手写 LaTeX 解析器（781 行）
- 新增命令只要 latex2mathml 支持就自动生效，无需修改转换代码

**已知限制：**
- `\\usepackage` 等非公式 LaTeX 不支持（latex2mathml 只处理数学模式）
- 部分罕见 MathML 标签（如 `mmultiscripts`、`menclose`、`merror`）尚无映射，出现时降级为纯文本

### 关键依赖

| 组件 | 来源 | 用途 |
|:-----|:-----|:-----|
| `mathml_to_omml.py` | **本技能新增** | MathML→OMML 转换器 |
| `latex2mathml` | `pip install latex2mathml` | LaTeX→MathML 成熟库 |
| `python-docx` | pip | docx 文档构建 |
| `lxml` | pip | XML/OMML 元素操作 |

`latex2mathml` 必须安装：`uv pip install latex2mathml` 或 `pip install latex2mathml`。

### 使用方式

```python
from mathml_to_omml import convert_formula

# 一键转换（推荐）
oMath = convert_formula(r'P = \frac{U^2}{R} \quad (50\Omega)')
# oMath 是 <m:oMath> lxml 元素
paragraph._element.append(oMath)
```

### 行内标记处理（`process_markdown_text()`）

正则优先级：`$$(跨行)` > `$` > `**` > `*` > `` ` `` > `[text](url)` > 纯文本。

```python
pattern = r'(\$\$[\s\S]*?\$\$|\$[^$]+\$|\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`|\[([^\]]+)\]\(([^)]+)\))'
```

| 标记 | 处理方式 |
|:-----|:---------|
| `$$...$$` | → 居中 OMML 块公式（mathml_to_omml.convert_formula） |
| `$...$` | → 行内 OMML 公式 |
| `**...**` | → run.bold = True |
| `*...*` | → run.italic = True |
| `` `...` `` | → Couier New + 灰色背景 |
| `[...](...)` | → 嵌入图片（如文件存在） |

**关键修复**：`$$` 跨越多行时必须用 `[\s\S]*?` 而非 `[^$]+`，否则多行公式不匹配。

### 公式预处理（MathML 管线已无必要）

**2026-06-10 更新**：`clean_latex()` 函数已从 `md_to_docx.py` 中移除。MathML 管线（`latex2mathml` + `mathml_to_omml.py`）原生处理公式中的所有 LaTeX 命令，不再需要手动预处理：

- `\\tag{N-M}` ✅ → latex2mathml 保留，OMML 自动忽略
- `\\xrightarrow{文字}` ✅ → 正确渲染为箭头 accent（不是降级文本）
- `\\begin{aligned}` ✅ → 自动转为 eqnArray 多行结构
- `\\displaystyle` / `\\limits` ✅ → latex2mathml 原生支持
- `\\left(` / `\\right)` ✅ → fence 括号自动伸缩
- `\\text{中文/μV}` ✅ → 正体文本
- `\\boxed{}` ✅ → 边框方盒

**如果使用旧管线（不推荐）**：必须手动执行 `clean_latex()` 预处理：移除 `\\tag` 行、`\\xrightarrow{a}`→`a \\to`、移除 `\\displaystyle`/`\\limits`。

## 表格处理

Markdown pipe table → `parse_blocks()` 识别连续 `|` 行 → `add_table()`：

1. 第1行 = 表头（粗体+居中对齐）
2. 第2行 = 对齐分隔符（`:---`=左对齐, `:---:`=居中, `---:`=右对齐）
3. 第3行起 = 数据行（含行内公式处理）

每个表格单元格的内容经过 `process_inline_math()`，所以单元格中的 `$...$` 也会被转为 OMML。

## Mermaid 处理

Word 不支持 Mermaid 渲染。策略：提取首行描述 + 以等宽字体展示源码。

```
📊 Mermaid 图
示意图: graph LR | A[label] --> B[label]
源码:
graph LR
    A[label] --> B[label]
```

## 标题处理（v5 关键修复）

| 原始 Markdown | 处理方式 | Word 样式 |
|:--------------|:---------|:----------|
| `# 标题` | Heading 1 | 一级标题 |
| `## 标题` | Heading 2 | 二级标题 |
| `### 标题` | Heading 3 | 三级标题 |
| `#### 标题` | → `min(4,3)=3` Heading 3（加粗） | 三级标题 |
| `##### 标题` | → `min(5,3)=3` Heading 3 | 三级标题 |
| `###### 标题` | → `min(6,3)=3` Heading 3 | 三级标题 |

## 已知限制

| 限制 | 说明 |
|:-----|:------|
| Mermaid 不渲染 | Word 无 Mermaid 引擎，无法直接渲染 |
| `\\text{}` 不处理嵌套 | 教材中无嵌套情况 |
| 图片嵌入 | 仅查找 `![alt](path)` 中的路径，标准 docx 插入 |
| 无序列表嵌套 | 不检测嵌套层级，全部一级缩进 |

## 故障排查

| 症状 | 根因 | 修复 |
|:-----|:-----|:-----|
| docx 打不开/损坏 | `oMath` XML 结构错误 | 检查 `mathml_to_omml.latex_to_omml()` 返回值是否含非法字符，确认 `latex2mathml` 已安装 |
| 公式显示为空白 | `latex2mathml` 遇到不识别的 LaTeX 命令 | 在 `mathml_to_omml.py` 的 `_mml_convert()` 中添加标签映射，或提交 issue 给 latex2mathml |
| 公式部分缺失 | `latex2mathml` 输出含 XML 非法字符（`&`） | 确认 `_latex_to_mathml()` 中的 `re.sub` 已修复 `&`→`&amp;` |
| `**` 等 Markdown 符号残留 | `process_markdown_text()` 正则未匹配 | 检查 `pattern` 的顺序和 `[\\s\\S]*?` 的使用 |
| `####` 显示为原文 | `heading_level()` 正则限制 `#{1,3}` | 改为 `#{1,6}` + `min(len,3)` 映射 |
| `---` 显示为原文 | 未识别横线 | 在 `add_paragraph_text()` 中提前检查并转为边框段落 |
| 列表符号 `-`/`1.` 残留 | 未识别列表 | 在 `add_paragraph_text()` 中正则匹配 `^[-*+] ` 和 `^\\d+[.)] ` |
| 表格横跨多页 | python-docx 默认不设跨页断行 | 需手动设置 `tblPr` 的 `cantSplit` 属性 |
| `\\begin{aligned}` 对齐( `&` )丢失 | `&` 在 MathML 中被转为 `<mi>&amp;</mi>`，MathML→OMML 时简化为不可见元素 | eqnArray 已正确处理行结构；对齐点降级不影响可读性 |

## 迭代历史

| 版本 | 引擎 | 公式 | Mermaid | Markdown 残留 | 结论 |
|:-----|:-----|:-----|:--------|:--------------|:-----|
| v1 | pandoc | ❌ raw tex | ❌ 源码 | ❌ 大量 | 放弃 pandoc 路线 |
| v2 | pandoc+预处理 | ❌ 仍失败 | ❌ 源码 | ❌ | 预处理不足以修复 |
| v3 | python-docx | ✅ OMML | ✅ 源码说明 | ❌ `**` 残留 | 核心换引擎成功 |
| v4 | python-docx+正则 | ✅ 40个 | ✅ | ✅ 0 `**` | 正则修复跨行匹配 |
| v5 | python-docx+全标记 | ✅ 40个 | ✅ | ✅ 全部处理 | 新增列表/横线/`####` |
| **v6** | **python-docx+mathml_to_omml** | **✅ 40个OMML(全部正确)** | **✅** | **✅** | **公式管线重写：手写LaTeX解析器→latex2mathml→MathML→OMML。`\\xrightarrow`正确箭头accent，`\\begin{aligned}` eqnArray多行，`clean_latex()`移除** |
