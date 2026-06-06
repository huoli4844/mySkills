# 数据架构演进取向

## 最终架构（v31）

```
工作区/.dag/
  第1章/data/
    concepts.yaml       ← 每章独立，多章并行不冲突
    kes.yaml
    kps.yaml
    ...
  第2章/data/
    concepts.yaml
    ...
  01_电磁兼容基础_ch1.json   ← pipeline 状态文件
  backups/                   ← 构建快照
```

## 设计原理

1. **数据归工作区，不归技能目录** — `~/.hermes/skills/domain-book-wiki/scripts/data/` 只做回退拷贝，不在构建时写入
2. **每章独立** — 消除 `_filter_by_chapter`，目录结构即过滤条件。多人并行写不同章互不覆盖
3. **优先级**：工作区 `.dag/第N章/data/` → 技能目录 `scripts/data/第N章/` → 扁平回退 `scripts/data/`

## 加载代码

```python
# build_kb_files.py _load_items
if output_dir and chapter:
    ch_data = os.path.join(output_dir, ".dag", f"第{chapter}章", "data", yaml_name)
    if os.path.exists(ch_data): return yaml.safe_load(open(ch_data)) or []
# fallback to skill data/ directory
```

## 演进历程

| 版本 | 方案 | 问题 |
|:-----|:-----|:-----|
| v25 | `scripts/data/concepts.yaml`（所有内容混合） | 多书构建时相互覆盖 |
| v30 | 工作区 `.dag/data/concepts.yaml`（每书独立） | 每章仍需 `_filter_by_chapter` |
| v31 | 工作区 `.dag/第N章/data/concepts.yaml`（每章独立） | ✅ 当前方案 |
