# .doc + .docx 融合处理陷阱与实测记录

本文件记录 `merge_source.py` 处理 .doc + .docx 同源文件对时的实测发现。

## 实测环境

- 源文件：`第2章-电磁兼容的电磁原理.doc`（3.3 MB, 38 页, OLE2 + MathType）
- 同源文件：`第2章 电磁兼容的电磁原理.docx`（1.3 MB, 另存为产生）
- formula-extract 提取：311 个公式 eqn_0~eqn_310
- file2md DOCX 输出：310 个 WMF 图片引用（image-000.wmf ~ image-309.wmf）
- 非公式图片：16 个（EMF 格式插图 + PNG 照片）

## 数据匹配

| 指标 | 数值 |
|------|------|
| formula-extract 提取公式 | 311 |
| MD 中 WMF 引用 (image-xxx.wmf) | 310 |
| 融合替换成功 | 310（1:1 顺序映射） |
| 未使用的公式 (eqn_310) | 1（可能在页眉/页脚） |

**WMF → LaTeX 顺序映射规则**：MD 中 `![](assets/image-xxx.wmf)` 按**文本出现顺序**依次对应 formula-extract 的 `eqn_0` ~ `eqn_N`。两个序列都来自文档对象池的遍历顺序，保持一致性。

## 公式兼容性问题及修复

### 1. `\wideparen{n}` — 非标 LaTeX 命令

- **来源**：yhmath 宏包，表示法向单位矢量的宽弧记号
- **出现**：边界条件公式中 5+ 处
- **症状**：KaTeX/GitHub 渲染器报错"Unknown command"
- **修复**：→ `\hat{n}`（标准 LaTeX）

### 2. 空分母 `\frac{num}{}`

- **来源**：formula-extract MTEF→LaTeX 转换中，分母为空的分式结构
- **典型例子**：`\frac{Z_{12}}{}U_1`、`\frac{W_0}{}`、`\frac{e^{-jkR}}{}`
- **原因**：MathType 中的分式可能缺少分母，MTEF 解析后生成空分母
- **症状**：KaTeX 报错"Fraction with empty denominator"
- **修复**：→ 裸 `num`（去掉空分式结构）

### 3. `\left\uf048` / `\right\uf049` — Unicode 损坏

- **来源**：formula-extract MTEF 解析中的 Unicode Private Use Area 字符残留
- **症状**：不可见字符导致 LaTeX 解析器卡死
- **修复**：替换为 `\left(` 和 `\right)`

### 4. `\text{、}` — CJK 标点在数学模式中

- **来源**：原文档中中文逗号「、」出现在公式变量间（如 ε、μ 之间）
- **症状**：不报错，但 `\text{、}` 渲染为西文逗号而非中文顿号
- **当前状态**：不修复（不影响渲染，语义可接受）

### 5. 积分下标过长

- **来源**：formula-extract 将积分变量的整个表达式放入 `\int_{...}` 下标
- **例子**：`\int_{\vec{M}(\vec{r}')\frac{e^{-jkR}}{}} d\upsilon`
- **修复难度**：高（需理解公式语义，无法自动修复）
- **建议**：在 Step 5 创建知识要素时，从 `_formulas/summary.json` 中手动修正

## WMF 图片归类规则

`merge_source.py` 使用正则 `!\[\]\(assets/image-\d+\.wmf\)` 匹配公式 WMF。
文件名以**图号开头**的 WMF（如 `图2-2-垂直振子及其镜像.wmf`）被判定为**插图**，保留原样。

| 模式 | 判定 | 处理 |
|------|------|------|
| `image-xxx.wmf` | 公式 | 替换为 LaTeX |
| `图X-X-xxx.wmf` | 插图 | 保留为图片 |
| `图X-X-xxx.emf` | 插图 | 保留为图片 |
| `image-xxx.emf` | 插图（可能含公式标签） | 保留为图片 |

## 输出验证清单

融合后需验证：

```bash
# 1. 无 wideparen 残留
grep 'wideparen' 输出.md

# 2. 无空分母
python3 -c "import re; c=open('输出.md').read(); print(len(re.findall(r'\\\\frac\{[^}]*\}\{\}', c)))"

# 3. WMF 引用数量合理（保留的是插图，非公式）
grep -c '\.wmf)' 输出.md

# 4. 公式数量可接受
grep -c '^\$\$' 输出.md
```

## Typora 兼容性

| 问题 | 原因 | 修复 |
|:----|:-----|:-----|
| `$$ formula $$` 不渲染 | Typora 要求块级公式三行格式 | `fix_formulas()` Fix 4：`$$\\nformula\\n$$` |
| `\wideparen` 报错 | yhmath 宏包，非标命令 | `fix_formulas()` Fix 1：`\hat{n}` |
| `\frac{}{}` 报错 | MTEF 解析产生空分母 | `fix_formulas()` Fix 2：移除空分式 |
| 需在 Typora 偏好设置中启用 | 内联公式默认关闭 | 偏好设置 → Markdown → 内联公式（勾选） |
