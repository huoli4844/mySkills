# Docling 安装与故障修复

## 标准安装

```bash
pip install docling
```

## 已知故障：tqdm 损坏

**症状**：导入 Docling 时报 `ValueError: Unable to compare versions for tqdm>=4.27: need=4.27 found=None`

**原因**：tqdm 的 dist-info 目录损坏（缺少 METADATA/RECORD 文件），导致 `tqdm.__version__` 为 `None`，transformers（Docling 的依赖）无法做版本比较。

**修复**：
```bash
# 1. 删除损坏的 dist-info
rm -rf /opt/miniconda3/lib/python3.9/site-packages/tqdm-4.67.1.dist-info/
rm -rf /opt/miniconda3/lib/python3.9/site-packages/tqdm*

# 2. 重新安装
pip install tqdm

# 3. 验证
python3 -c "import tqdm; print(tqdm.__version__)"   # 应输出版本号，不是 None
```

## 验证安装

```bash
python3 -c "from docling.document_converter import DocumentConverter; print('OK')"
```

## PDF 公式提取能力

Docling 仅能提取 PDF 中**以特殊字体渲染的文本公式**并转为 LaTeX `$$...$$`。
对于**渲染为嵌入图片的公式**（本教材电子对抗原理与技术的主要情况），Docling 无法提取为 LaTeX。
