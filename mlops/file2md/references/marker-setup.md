# Marker (marker-pdf) 安装与配置

> Marker = VikParuchuri/marker — 高精度 PDF→Markdown 转换工具，基于深度学习布局分析。
> 与 Docling 相比，在布局还原、特殊字体识别上通常表现更好。

## 依赖要求

- **Python ≥ 3.10**（必需 — surya-ocr 使用 `X | Y` 联合类型语法，Python 3.9 报错）
- macOS 或 Linux

## 安装步骤

### 1. 创建 Python 3.11 环境（如果系统 Python 是 3.9）

```bash
# 使用 conda（已有 py311 环境可直接使用）
conda create -n py311 python=3.11 -y
conda activate py311
```

### 2. 安装 marker-pdf

```bash
pip install marker-pdf
pip install psutil          # Marker 运行时依赖，可能不会被自动拉取
```

### 3. 验证安装

```bash
# 查看帮助
python3 -m marker --help

# 测试转换
python3 -m marker input.pdf output.md
```

## 典型用法

```bash
# 单文件转换
marker input.pdf output.md

# 批量转换目录（自动找到所有 PDF）
marker /path/to/pdf_dir/ /path/to/output_dir/

# 指定语言（中文文档）
marker input.pdf output.md --langs zh
```

## 已知陷阱

### 陷阱 1：Python 3.9 不兼容

```
TypeError: unsupported operand type(s) for |: '_GenericAlias' and 'NoneType'
```

**原因**：surya-ocr（Marker 的依赖）在 schema 定义中使用 Python 3.10+ 语法。
**解决**：使用 Python 3.10+ 环境（conda py311 或 brew python3.11/3.12）。

### 陷阱 2：psutil 未自动安装

```
ModuleNotFoundError: No module named 'psutil'
```

**原因**：marker-pdf 依赖 psutil 但 pip 依赖解析可能跳过。
**解决**：`pip install psutil`。

### 陷阱 3：Marker 未集成到 file2md 的 --engine 参数

file2md 当前 PDF 引擎仅支持 `docling`（默认）。使用 Marker 需单独调用：

```bash
# 不通过 file2md，直接调用
/opt/miniconda3/envs/py311/bin/marker input.pdf output_dir/
```
