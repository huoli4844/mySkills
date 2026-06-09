# Changelog

# Changelog

## 2.3.0 (2026-06-10)
- **Mermaid语法校验全面升级**：`post_generation_check.py` 检查 Mermaid 图内语法而非仅检查闭合标签
- **新增6项Mermaid检查**：图表类型合法性、xychart-beta关键字白名单（`block_lines[1:]`首行跳过防误报）、flowchart节点引号要求、emoji禁令、`%%{init}`格式规范、classDef定义覆盖
- **新增Mermaid自动修复**：`_fix_mermaid_issues()` 自动移除 `bar-group-group` 等非法关键字，集成到 `--fix` 管线
- **SKILL.md文档增强**：Phase 4.5 新增6项Mermaid校验表格，pitfalls.md 新增 #32 xychart-beta 陷阱
- **修复误报**：xychart-beta 首行 `xychart-beta` 不再被错判为非法关键字

## 2.1.0 (2026-06-09)
- **新增 `post_generation_check.py`** — 自动质量检查脚本：公式语法/全编号/Mermaid闭合/拼写，支持 `--fix` 自动修复
- **新增 `clean_formula_numbers.py`** — 当编号严重混乱时，删除所有原编号后从头重排（使用前必须备份）
- **新增 `fix_tag_placement.py`** — 将误放在 `$$` 外部的 `\tag{}` 移回公式块内部
- **Phase 0.5 重构**：从简单标注扩展为5步标准化流程（研读→手法对比→发挥空间→写作指南→动笔），新增向用户展示对比表+获确认后才能动笔的要求
- **Phase 4.5 升级**：从零散shell命令替换为统一的 `post_generation_check.py --fix` 调用，新增审计报告模板
- **Pitfall 9**: 写作指南须经用户确认后方可动笔
- **Pitfall 10**: `\tag` 与 `$$` 边界问题——自动修复脚本可能将tag放在 $$ 外部
- **Pitfall 11**: `clean_formula_numbers.py` 使用前必须备份
- **Bug fix**: `_fix_missing_tag` 函数将 `\tag` 插入在 `$$` 之后而非之前，确保在公式块内部
- **新增 `references/gap-analysis-checklist.md`** — Phase 0.6 三书内容差距分析模板

## 2.0.0 (2026-06-09)
- **重大重构**：SKILL.md 从 2012 行/80KB → 168 行/8.6KB（减量89%）
- 重构为 `skill-authoring` 标准格式：Overview→When to Use→Design→Workflow→Commands→Pitfalls→Reference Index
- 详细写作规范、完整陷阱列表移至 references/
- 新增 13 条军规（公式全编号规则）
- 新增 `references/pitfalls.md` 完整陷阱列表

## 1.9.0 (2026-06-09)
- 12条军规→13条：新增「公式全编号」规则
- `volume-standards.md` 新增 0f 公式全编号检查项
- 综合核验清单新增 0d 公式全编号项

## 1.8.0 (2026-06-08)
- 图号检查 + 学习目标审查 + 数学推导标准
- 新增 L3 六步推导结构标准
- 新增综合核验清单（0a-0e）

## 1.7.0 (2026-06-08)
- Phase 4.5 清理+图号核验环节
- Mermaid ≥6 张标准
- 体量铁律 5~10×

## 1.6.0 (2026-06-08)
- 12条军规完整版
- 三书融合写作法（张亮引入→梁振光结构→路宏敏细节）
- 写作禁止清单

## 1.0.0 (2026-06-06)
- 初始版本：Phase 0-6 工作流
- 三本教材研读方法论
- 6要素质量检查
