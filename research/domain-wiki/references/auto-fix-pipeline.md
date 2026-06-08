# 构建后自动修复管道（post_build_fix.py）

## 概述

`post_build_fix.py` 在 `build_kb_files.py` 完成后运行，自动修复生成文件中的常见格式和质量问题，实现「发现问题→自动修复→再次验证」的闭环。

## 用法

```bash
# 方式1：构建时自动触发（推荐）
python3 scripts/build_kb_files.py --type concept --chapter 2 \
  --output-base <wiki_root> --auto-fix --source-dir <出处目录>

# 方式2：独立运行（全部修复）
python3 scripts/post_build_fix.py <wiki_root> --source-dir <出处目录>

# 方式3：独立运行（仅修复公式）
python3 scripts/post_build_fix.py <wiki_root> --fix-only formula

# 方式4：独立运行（仅修复图引用）
python3 scripts/post_build_fix.py <wiki_root> --fix-only figure --source-dir <出处目录>
```

## 三项修复

### 1. fix_block_formulas

**检测**：`$$formula$$` 写在同一行
**修复**：拆为 `$$\nformula\n$$` 独占三行格式
**实测**：电磁兼容知识库第1-2章修复 77 处/17 文件（真实知识库）

**注意**：只修复块级 `$$...$$`，行内 `$...$` 保持不变。匹配使用正则为：
```python
re.compile(r'(?<!\$)\$\$(?!\$)([^\n]*?[^\s\n])\$\$(?!\$)', re.MULTILINE)
```

### 2. fix_figure_references

**检测**：`> 图X-X 说明文字` 文本引用（非 Markdown 图片语法）
**修复**：三步走——
  a. 从 `--source-dir` 指定的出处章节 .md 构建「图号→图片文件」映射表
  b. 从出处 `assets/` 复制匹配的图片到知识库 `assets/`
  c. 替换为 `![alt](assets/文件)` Markdown 图片链接

**图映射构建算法**：在出处章节 .md 中查找两种模式：
```
模式1: ![图2-1-说明](assets/图2-1-说明.emf)  → fig_key="图2-1", fig_file="图2-1-说明.emf"
模式2: 图2-1 说明（单独一行） → 辅助匹配
```
模糊匹配支持前缀匹配：`图2-1` → `图2-1-空间场的计算.emf`

**实测**：电磁兼容知识库修复 17 处/8 文件，复制 25 张命名图片

**限制**：
- 需要 `--source-dir` 指向出处章节 .md 目录
- 如果出处 assets 中缺少对应图片文件（如无名 image-NNN.wmf 而非命名 图X-X-说明.xxx），保持文本引用不变

### 3. fix_mermaid_sources

**检测**：frontmatter 中 `core_concept_map_source` 为 "无"
**修复**：从同文件的 `source_from` 字段推导出处引用并填入

## 集成管道

```text
build_kb_files.py --auto-fix
       ↓
  build_{type}()   →  生成 .md 文件
       ↓
  post_build_fix():           ← 自动触发
    ├── fix_block_formulas()     # 修复公式格式
    ├── fix_figure_references()  # 修复图片引用+复制图片
    ├── fix_mermaid_sources()    # 补全图源出处
    └── generate_report()        # 输出修复日志
       ↓
  comprehensive-content-check.py  # 验证修复效果
    └── 0 FAIL, 0 WARN → PASS
```

## 与 comprehensive-content-check.py 的关系

| 阶段 | 脚本 | 职责 |
|:----|:-----|:-----|
| 检测 | comprehensive-content-check.py | 发现问题（公式格式/图片缺失/图解析缺失） |
| 修复 | post_build_fix.py | 自动修复可修复项 |
| 验证 | comprehensive-content-check.py | 重新检查确认 0 FAIL |

## 已知陷阱

1. **目录名不匹配**：`target_dirs` 过滤使用中文短名（`概念`）和编号名（`30_核心概念`）两种格式。如果知识库使用其他命名约定，需更新 `target_dirs`。
2. **图映射缺失**：`fix_figure_references` 依赖出处章节 .md 中存在 `![图X-X-说明]` 模式的命名图片引用。如果章节只有 `![](image-NNN.wmf)` 无名引用，无法建立映射，修复跳过。
3. **source-dir 相对路径**：`--source-dir` 指定的是包含章节 .md 文件和 `assets/` 子目录的目录。脚本自动在 `{source_dir}/` 下找 `assets/` 子目录。

## 调试

```bash
# 单独测试公式匹配
python3 -c "
import re
test = r'$$\nabla \times \mathbf{H} = j\omega\varepsilon\mathbf{E} + \mathbf{J}$$'
pattern = re.compile(r'(?<!\$)\$\$(?!\$)([^\n]*?[^\s\n])\$\$(?!\$)', re.MULTILINE)
matches = list(pattern.finditer(test))
print(f'匹配数: {len(matches)}')

# 测试修复后
from post_build_fix import fix_block_formulas_in_text
result, count = fix_block_formulas_in_text(test)
print(f'修复: {count} 处')
"

# 单独测试图映射
python3 -c "
from post_build_fix import build_figure_map_from_source
fig_map = build_figure_map_from_source('~/Desktop/电磁兼容/出处/')
print(f'图映射: {len(fig_map)} 条')
for k, v in sorted(fig_map.items())[:5]:
    print(f'  {k} → {v}')
"
```
