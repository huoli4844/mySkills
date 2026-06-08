# WMF 公式验证方案

## 问题

教材源文的公式全部以 WMF/EMF 图片形式嵌入（1,133 个 WMF 图片），Agent 通过视觉解读后手写 ASCII 数学式填入 `mathematical_model` 字段。公式内容无法自动化文本交叉验证。

## 已知差异案例

| 公式 | 概念文件内容 | Word 源文 (WMF) | 差异 |
|:-----|:------------|:---------------|:-----|
| (2-36) | `$$VN = -dΦ/dt = -d/dt∫∫B·dS$$` | WMF image-178 | 用户指出不一致，具体符号差异待确认 |

## 修复步骤（需 API key）

1. 安装 `formula-extract` 技能
2. 对所有 `20_正文/assets/*.wmf` 运行 OCR→LaTeX:
   ```bash
   for f in 20_正文/assets/*.wmf; do
     formula-extract "$f" --output-latex 2>/dev/null
   done > wmf_formulas.txt
   ```
3. 与 `.dag/第N章/data/concepts.yaml` 中的 `mathematical_model` 字段做逐条符号级对比
4. 标记差异项，人工确认正确版本后修正 YAML 和 .md 文件

## 无 API key 时的降级方案

- Agent 精读上下文文本（正文中 WMF 前后的文字描述），从自然语言描述中重建公式
- 交叉引用标准教科书（法拉第定律、库仑定律等常见物理公式的标准形式）
- 用 WMF 文件大小分类：>800 字节说明含复杂积分/矩阵，需特别谨慎
