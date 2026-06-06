# docx 嵌入 OLE 对象 → LaTeX 公式提取

## 问题背景

客户提供的 `.docx` 文件由旧版 `.doc`（含 MathType 公式，1.0 版 Word 97-2003）另存而来。此时：
- docx 内无 OMML 公式（`<m:oMath>` 元素）
- `word/media/` 下有大量 WMF 图片（公式的渲染产物）
- `word/embeddings/` 下保存了原始 OLE 对象（`oleObject*.bin` 文件）
- docx 头 350+ 的 OLE 对象引用，305+ 的 WMF 媒体文件

## 关键技术发现

每个 `oleObject*.bin` 文件本身是一个 **OLE2 复合文档**（以 `d0cf11e0` 魔数开头），内部包含 `Equation Native` 流（MathType MTEF 二进制数据）。可以用 `mtef_to_latex.rb` 解析为 LaTeX。

**OLE2 魔数比较坑**：Python 的 `data[:8] == b'\\xd0\\xcf\\x11\\xe0\\xa1\\xb1\\x1a\\xe1'` 必须用完整的 8 字节，不可只比较前 4 字节 `b'\\xd0\\xcf\\x11\\xe0'`（虽然 8 字节 vs 4 字节的 `==` 总是 False）。

## adapter 脚本

`scripts/container_extract.py` — 从 .docx 的嵌入 OLE 对象中提取 MathType 公式。

```bash
python3 scripts/container_extract.py 第2章.docx -o ./formula_output
```

内部流程：
1. 遍历 docx zip 的 `word/embeddings/oleObject*.bin`
2. 用 `olefile` 打开每个 bin（它是 OLE2 容器）
3. 读取 `Equation Native` 流（含 28 字节 OLE 头的完整数据）
4. 写入 `eqn_bins/eqn_N.bin`
5. 调用 `mtef_to_latex.rb` 批量转换

输出：
```
formula_output/
  ├── eqn_bins/       ← Equation Native 原始数据 (.bin)
  ├── latex/
  │   ├── eqn_0.tex   ← LaTeX 文件
  │   ├── eqn_1.tex
  │   └── summary.json ← 索引
  └── omml/           ← OMML (.omml.xml)
```

## 与 merge_source 配合

```bash
python3 scripts/container_extract.py 第2章.docx -o /tmp/f
python3 scripts/merge_source.py \\
  --md formatted.md \\
  --formulas /tmp/f/latex/summary.json \\
  --assets assets \\
  -o 第2章-电磁兼容的电磁原理.md
```

merge_source 输出示例：310 个 WMF 全部替换为 LaTeX，57 个块级公式转为 Typora 兼容三行格式。

## MTEF→LaTeX 已知伪影

merge_source 的 `fix_formulas()` 自动修复：
- `\\wideparen{n}` → `\\hat{n}`（非标 yhmath 命令）
- `\\frac{Z_{12}}{}` → `Z_{12}`（空分母）
- `\\left\\uf048` / `\\right\\uf049` → `\\left(` / `\\right)`（Unicode 损坏）
- `$$ formula $$` 单行 → Typora 三行格式

## 局限性

- 仅适用于 `.docx` 在 `word/embeddings/` 下有 `oleObject*.bin` 的情况
- 要求 mathtype gem 已安装（`/tmp/mathtype/lib`）
- 要求 `olefile` Python 包
- 每个 oleObject*.bin 必须是 OLE2 容器（`d0cf11e0` 魔数），含 `Equation Native` 流
- textutil .docx→.doc 反向转换不保留 OLE 对象（实测验证：textutil 输出的 .doc 无 Equation Native 流，仅 4 个顶层流）
