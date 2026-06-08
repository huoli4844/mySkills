# Preflight Workflow (v52.4)

写入 YAML 数据文件后、pipeline auto 前的预验证闸门。

## 使用场景

每次写入或修改 `.*/第N章/data/*.yaml` 后，在执行 `pipeline auto` 前运行。

## 命令

```bash
dag_controller.py pipeline preflight -w $BOOK_DIR --book-id XXX -c N
```

## 检查项

1. **文件存在性** — 8个必须的 YAML 数据文件是否存在
2. **YAML 语法** — 能否被 `yaml.safe_load` 解析
3. **格式** — 是否为 YAML list（`- name:` 开头）
4. **字段名匹配** — 每个条目的 `bd:` 字段名 vs 模板 `{{xxx}}` 的差集
   - `missing`（模板有但YAML无）→ 必须补充，否则 `{{xxx}}` 残留
   - `extra`（YAML有但模板无）→ 不阻断但建议清理
5. **置信度** — 每个 `fm.confidence` 是否在 `CONFIDENCE_LEVELS` 允许范围内
6. **习题-解答配对** — exercises.yaml 与 solutions.yaml 条目数是否一致

## 输出格式

```
✅ concepts.yaml      (核心概念, 6项)
⚠️ entities.yaml      (实体, 3项)
    ⚠️ [隔离变压器] 多余 1 字段: entity_type    ← 可忽略（非阻断）
✅ exercises.yaml     (习题, 11项)
⚠️ kes.yaml           (知识要素, 5项)
    ⚠️ [接地技术基础] 缺 5 字段: xxx, yyy      ← 必须修复
✅ 习题-解答配对: 11 = 11 ✓
```

## 典型调试路径

### 问题1：`name`/`source_chapter`/`source_from` 被报告为缺失

这些是**自动填充字段**——不应该出现在 `bd:` 中，因为它们由 `build_kb_files.py` 从 `fm:` 自动填充。确认它们在 `_AUTO_FILL_FIELDS` 集合中（schema_loader.py 第41行）。如果预验证仍报告缺失，说明 schema_loader 的 `_AUTO_FILL_FIELDS` 需要更新。

### 问题2：`classification`/`references`/`structure` 被报告为多余

这些字段只存在于旧版模板。检查 `assets/templates/<type>.md` 中是否真的包含 `{{classification}}` 等。如果不在模板正文中，从 YAML `bd:` 中移除。

### 问题3：confidence 超出允许值

检查 `tac_constants.py` 中的 `CONFIDENCE_LEVELS` 表。例如 concept 只允许 `{0.95}`，使用 `0.90` 会阻断 build。修改 YAML `fm.confidence` 为允许值。

## 与 pipeline auto 的关系

preflight 不修改状态文件，不改变 pipeline 状态，不写任何文件。它只读检查。发现的问题可以并行修复，修复后直接跑 `pipeline auto`，不需要再次 preflight。

## 可支持性与扩展

要增加预验证检查项，在 `dag_controller.py` 的 `_run_preflight()` 函数中添加逻辑。注意保持非阻断原则——只报告不中断。
