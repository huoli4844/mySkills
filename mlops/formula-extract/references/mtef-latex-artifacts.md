# MTEF → LaTeX 转换已知伪影

`mtef_to_latex.rb` + Ruby mathtype gem 的 MTEF v3/v5 解析在 311 公式验证中 100% 成功转换，但输出的 LaTeX 存在一些已知伪影。这些伪影不是 Bug，是 MTEF 二进制格式的固有局限。

## 伪影清单

### 1. `\wideparen{n}` — 非标命令

- **来源**：yhmath 宏包的宽弧记号，用于法向单位矢量
- **出现场景**：边界条件公式（`\hat{n}×(\vec{E}_1-\vec{E}_2)=0`）
- **症状**：KaTeX/GitHub 报 "Unknown command"
- **修复**：→ `\hat{n}`（标准 LaTeX）

### 2. 空分母 `\frac{num}{}`

- **来源**：MathType 中的分式可能缺少分母（如 `Z_12/` 被解析为 `\frac{Z_{12}}{}`）
- **典型例子**：`\frac{W_{0}}{}`、`\frac{e^{-jkR}}{}`、`\frac{Z_{12}}{}U_1`
- **症状**：KaTeX 报 "Fraction with empty denominator"
- **修复**：→ 裸 `num`（移除空分式）

### 3. `\left\uf048` / `\right\uf049` — Unicode 损坏

- **来源**：MTEF 解析中 Unicode Private Use Area 字符（U+F048/U+F049）残留
- **症状**：不可见字符导致 LaTeX 解析器卡死或报错
- **修复**：→ `\left(` / `\right)`

### 4. 积分下标包含整个被积式

- **来源**：MTEF 的 INTEG 记录将积分变量作为下标解析
- **典型例子**：`\int_{\vec{J}\Phi d\upsilon}`（正确应为 `\int \vec{J} \Phi d\upsilon`）
- **症状**：积分符号的下标位置显示整个表达式
- **修复**：需人工理解公式语义后修正

### 5. 多余的 `\text{、}` 在中文逗号处

- **来源**：原文档变量列表中用中文顿号分隔（如 ε、μ）
- **输出**：`$\varepsilon\text{、}\mu$`
- **症状**：不报错，但渲染效果略古怪
- **修复**：对显示无实质影响，可忽略

### 6. 遗漏的空格和括号

- **来源**：MTEF 格式不保存人类可读的空格和括号
- **例子**：`\frac{1}{2}[\vec{E}\times\vec{H}^{*}]` 缺少部分括号
- **症状**：语义正确但可读性下降
- **修复**：对渲染无影响

## 自动修复方案

推荐使用 `source-prepare` 的 `merge_source.py` 脚本（其 `fix_formulas()` 函数自动修复问题 1-3）：

```bash
# 集成到 source-prepare 的融合管线
python3 ~/.hermes/skills/research/source-prepare/scripts/merge_source.py \
  --md ... --formulas ... -o 输出.md
```

或单独修复 formula-extract 的输出：

```python
import re

with open('eqn_0.tex') as f:
    latex = f.read()

# Fix 1
latex = re.sub(r'\\wideparen\{([^}]*)\}', r'\\hat{\1}', latex)
# Fix 2
latex = re.sub(r'\\frac\{([^}]*)\}\{\}', r'\1', latex)
# Fix 3
latex = latex.replace('\\left\uF048', '\\left(')
latex = latex.replace('\\right\uF049', '\\right)')

print(latex)
```

## 影响范围

| 伪影 | 发生频率 (311 公式中) | 严重程度 |
|:----|:--------------------:|:--------:|
| `\wideparen` | ~5 处 | 高（报错） |
| 空分母 `\frac{}{}` | ~10 处 | 高（报错） |
| Unicode 损坏 | ~2 处 | 高（解析卡死） |
| 积分下标 | ~15 处 | 中（语义正确但显示异常） |
| `\text{、}` | ~10 处 | 低（不影响渲染） |
