# Pipeline Auto 命令

`dag_controller.py pipeline auto` — 一键自动化执行所有 DAG 阶段。

## 用法

```bash
# 完整构建第 3 章（L1 + L2 + L3 + L4）
dag_controller.py pipeline auto -w $BOOK_DIR --book-id 01_foo -c 3

# 仅 L1（不生成索引）
dag_controller.py pipeline auto -w $BOOK_DIR --book-id 01_foo -c 3 --l1-only

# 从特定阶段恢复
dag_controller.py pipeline auto -w $BOOK_DIR --book-id 01_foo -c 3 --from kp
```

## DAG_ORDER（v33.0）

按教学认知链顺序：

```
concepts → ke → entities → kp → sp → scene → exercises → solutions → l2 → l3 → l4
```

### 依赖关系

| 阶段 | 依赖 |
|:-----|:-----|
| concepts | —（第一步） |
| ke | concepts |
| entities | concepts |
| kp | concepts, ke, entities |
| sp | kp |
| scene | kp, sp |
| exercises | scene |
| solutions | exercises |
| l2_indices | 全部 L1 |
| l3_indices | l2_indices |
| l4_indices | l3_indices |

## 每阶段内部流程（v33.0）

1. 调用 `build_kb_files.py --type <type>` 从 YAML 生成 .md
2. 运行 `comprehensive-content-check.py` 检查内容深度
3. 运行 `validate_phase_output()` 检查 FrontMatter + **模板子节内容完整性**
4. 通过 → `done` / 失败 → `blocked`

## 输出示例

```
🔄 [concepts] 核心概念: 10-30 个
  🔨 build_kb_files.py --type concept --chapter 1
  ✅ content-check [concepts]: 通过
  ✅ [concepts] → done (8 文件)，验证通过

🔄 [ke] 知识要素: 10-30 个
  ✅ content-check [ke]: 通过
  ✅ [ke] → done (11 文件)，验证通过

🔄 [entities] 实体: 3-10 个
  ✅ [entities] → done (3 文件)，验证通过

🔄 [kp] 知识点: 5-15 个
  ✅ [kp] → done (5 文件)，验证通过

🔄 [sp] 技能点: 3-8 个
  ✅ [sp] → done (2 文件)，验证通过

🔄 [scene] 应用场景: 2-5 个
  ✅ [scene] → done (1 文件)，验证通过

🔄 [exercises] 5-20 道（可 auto-detect）
  ✅ [exercises] → done (12 文件)，验证通过

🔄 [solutions] 解答: 与习题数一致
  ✅ [solutions] → done (12 文件)，验证通过

🎉 全部阶段完成
```

## 阻断行为

- 依赖未满足 → 跳过（等待上游修复）
- 阶段 validation 失败 → `blocked`，停止推进
- 模板子节内容未填充 → `validate_phase_output` 报告空节，阻断
