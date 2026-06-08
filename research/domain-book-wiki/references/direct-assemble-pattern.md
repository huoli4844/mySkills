# 数据驱动模式

> v25.8 起所有数据使用 YAML 格式，由 `_load_items()` 统一加载。

## 数据流

```
data/*.yaml (YAML | 字面块零转义 LaTeX + Mermaid)
    │
    ▼
_load_items() → yaml.safe_load()
    │
    ▼
build_kb_files.py builder 函数 → assemble_md() → .md 文件
```

## 关键要点

### YAML 格式

```yaml
- name: 概念名称
  file: 概念文件
  fm:
    source_chapter: "N"
    confidence: 0.95
  bd:
    pure_text: 纯文本内容                             # 直接写
    formula: |                                       # | 字面块
      $$E = \frac{1}{2} mv^2$$                       # \frac 零转义
    mermaid: |                                       # | 字面块
      flowchart TD                                   # 图直接写
          A[节点1] --> B[节点2]
```

### 标准字段自动填充

builder 函数自动添加 `name`、`book_id`、`book_name`、`chapter_num`、`related_directory`，无需在 YAML 中重复。

### 验证

```bash
# 构建
python3 build_kb_files.py --type concept --chapter N

# 验证完整性
python3 comprehensive-content-check.py <wiki_root> -q
```
