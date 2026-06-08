# 解答内容深度规范 (v35.9)

解答骨架仅提供结构性占位符，Agent 必须填充完整内容后方可标记 done。
质量检查 `check_solution_mandatory_diagrams` **仅覆盖流程图和知识闭环图的必填检查**（5.1/5.2），
**不检查二/三/四段的文字段落密度**。Agent 需自觉确保各段充实。

## 各段最低要求

| 段 | 子节 | 最低字数 | 要求 |
|---|---|---|---|
| 二、核心解答 | 2.1 实现原理 | ≥400 字 | 分步骤详析，含公式和物理意义，逐层展开 |
| | 2.2 主要特点 | ≥4 维度 | 表格 + 每维度 2-3 句文字说明 |
| 三、考点与易错点 | 3.1 核心考点 | ≥4 个考点 | 每个考点 1-2 句，标注考查重点 |
| | 3.2 常见错误 | ≥3 条 | 每条 50-80 字，含错误描述 + 正确纠正 |
| | 3.3 解题技巧 | ≥3 条 | 可操作的答题策略 |
| 四、难点深度解析 | 4.1-4.3 | 每个 ≥200 字 | 独立标题 + 深度内容（物理本质/数学推导/工程联系）|
| 五、可视化解题逻辑 | 5.1 流程图 | 完整 Mermaid | 6 步节点链（质量检查 FAIL 级阻断空图）|
| | 5.1 分步说明 | 6 步 | 每步 1-2 句 |
| | 5.2 知识闭环图 | 完整 Mermaid | 4 节点闭环（质量检查 FAIL 级阻断非 Mermaid 语法）|
| | 知识闭环图解析 | ≥200 字 | 从顶层概念出发，逐步描述每个节点的逻辑关系、分支路径、闭环反馈机制、关联知识要素、工程意义总结 |
| 六、关联资源 | 6.1 核心知识点 | ≥3 个 wikilink | 关联的概念/知识点/知识要素 |
| | 6.2 引用出处 | ≥1 个来源 | 教材章节 + 权威参考文献 |

## 批量生成策略

当需要生成 5+ 个解答文件时，子代理（delegate_task）的 600s 超时窗口不足。
改用脚本直调 `assemble_md`：

```python
# $TMP/gen_solutions.py
import sys; sys.path.insert(0, '/Users/.../scripts')
from template_assembler_core import assemble_md

for exercise in exercises:
    bd = { ... 27 fields with full content ... }
    assemble_md(template_name="eval_template.md", front_matter_updates=fm, quality_key="eval/solution",
                body_replacements=bd, output_dir=sol_dir,
                filename=f"{name}.md", strict=False)
```

然后用 `terminal` 执行：`python3 $TMP/gen_solutions.py`
