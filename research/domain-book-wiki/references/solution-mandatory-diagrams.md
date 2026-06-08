# 解答必填图检查（v35.8）

## 设计规则

解答文件的两个核心部分必须填充实际内容：

| 字段 | 要求 | 质量检查 |
|------|------|---------|
| `problem_solving_flowchart`（解题思路） | 必填，通常为 Mermaid `graph TD` 流程图 | 不能为 `"无"` 或占位符 |
| `knowledge_closed_loop`（知识闭环） | **必填，必须用 Mermaid 图** | 必须包含 `graph`/`flowchart`/`sequenceDiagram` 等声明 |

## 质量闸门

`check_solution_mandatory_diagrams()` 在 `comprehensive-content-check.py` 中：
- **FAIL**: 解题思路为空/"无"/含占位符
- **FAIL**: 知识闭环为空/"无"/含占位符
- **FAIL**: 知识闭环内容不含有效 Mermaid 语法关键字

## 骨架生成器默认图

当 solutions.yaml 缺失时，`_auto_build_solutions` 生成：

**解题思路 (graph TD)**：
```
审题: [题目前20字]... → 回顾相关概念 → 建立分析模型
  → 推导关键结论 → 验证与工程应用 → 总结答题
```

**知识闭环 (graph LR)**：
```
第N章核心概念 → 分析模型 → [习题短名]: 解决方案
  → 工程应用 -.-> 第N章核心概念
```

Agent 填充解答时必须替换或细化这些骨架图。

## 禁忌

1. Mermaid 节点标签中禁止使用 `→`（U+2192）— 与箭头语法 `-->` 冲突。用 `>` 替代。
2. 不能把知识闭环写成纯文本 — 必须用 Mermaid 图展示概念→应用闭环。
3. 不能留 `"无"` 在解题思路或知识闭环位置 — 必填图检查会 FAIL。
