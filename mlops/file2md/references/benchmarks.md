# file2md 实测基准对比

> 实测环境：macOS 26.5, Apple Silicon (arm64)
> 测试文件：《创业者手册-构建AI原生创业公司-中文》（Anthropic 出品，中文翻译版，42页，1.3MB PDF，对应 DOCX 18KB）

---

## 基准 1：DOCX → MD — Pandoc 原始输出 vs file2md

**测试文件**：`教学系统架构图问题分析.docx`（18KB，含表格/加粗/列表/编号）

| 维度 | Pandoc 原始 | file2md (pandoc + 后处理) |
|:-----|:-----------:|:--------------------------:|
| 文件大小 | 7,223 字节 | 7,750 字节 |
| 行数 | 143 行 | 148 行 |
| 元数据 frontmatter | ❌ 无 | ✅ YAML (title, sha256, date) |
| 表格 | ❌ 纯文本网格 | ✅ pipe table (带对齐) |
| 编号列表 | ⚠️ 保留 a.b.c 原文 | ✅ 转标准 1.2.3 有序列表 |
| 加粗/斜体 | ✅ | ✅ |
| 页脚标记 | ⚠️ `\|` 转义符残留 | ⚠️ `/|` 类似残留 |

**结论**：file2md 完胜。本质上 file2md 的 DOCX 路径 = pandoc + 后处理管道（表格式修复、编号格式规范化、元数据注入），所以保留了 pandoc 全部优点，修复了其输出格式问题。

---

## 基准 2：PDF → MD — File2md (Docling) vs Marker (marker-pdf)

**测试文件**：《创业者手册-构建AI原生创业公司-中文.pdf》（42页，1.3MB，中文正文+表格+图片）

| 维度 | file2md (Docling) | Marker (marker-pdf) |
|:-----|:-----------------:|:-------------------:|
| 处理时间 | ✅ ~6 分钟 (349s) | ❌ ~11 分钟 (649s) |
| 首次模型下载 | ✅ 已有缓存 | ❌ ~1.9GB (4个模型) |
| 文件大小 | 73 KB / 841 行 | 74 KB / 751 行 |
| 元数据 | ✅ YAML frontmatter | ❌ 无 |
| 标题层级 | ✅ 干净无重复 (77 个) | ❌ 重复（页码标题 + 内容标题双重出现） |
| 图片提取 | ✅ 12 张 (assets/image-NNN.png) | ⚠️ 9 张 (_page_N_Picture_N.jpeg) |
| 表格 | ✅ pipe table | ✅ pipe table |
| 封面页 | ⚠️ 少量乱码 | ✅ 略好 |
| 正文质量 | ✅ 可读 | ✅ 可读 |

**结论**：总体 file2md 更优。Marker 唯一的优势是封面页表格稍好，但代价是首次下载 ~2GB 模型、处理时间近 file2md 的两倍、标题层级有重复、提取图片更少。

---

## 推荐策略

| 文件类型 | 推荐工具 | 理由 |
|:---------|:--------:|:-----|
| **DOCX** | file2md | = pandoc + 后处理管道，质量最优 |
| **PDF（一般）** | file2md (Docling) | 速度快，标题干净，元数据完整 |
| **PDF（布局复杂）** | 两者均可，首选 file2md | Marker 布局精度略高但代价太大 |

> **注意**：Marker 尚未集成到 file2md 的 `--engine` 参数中，需单独调用：
> ```bash
> /opt/miniconda3/envs/py311/bin/marker /path/to/pdf_dir/ --output_dir /path/to/output/
> ```
