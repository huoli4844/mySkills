# 全章质量审计工作流

## 审计入口

所有审计统一通过 `quality_audit.py`：

```bash
python3 scripts/quality_audit.py --project /path/to/教材              # 全量审计
python3 scripts/quality_audit.py --project /path/to/教材 --chapter 7  # 单章
python3 scripts/quality_audit.py --project /path/to/教材 --quick      # 快速
```

## 审计覆盖范围

### 公式检查
- `\tag{章-序号}` 章号前缀是否正确
- `\tag` 是否连续无跳跃无重复
- `$$` 是否配对（行级状态机，处理 `>$$` 格式）
- `$$` 内的 `\tag` 是否独占一行（需 `batch_fix_formula_numbers.py` 预修复）

### 军规合规
- 正文是否含第二人称"你"（习题前）
- 是否存在"Step"标记（应为学术表述）
- 小结条目数是否为6条
- 是否存在占位符（[待补充]/[TODO]等）
- 参考文献是否有 [M]/[S] 标识
- `$$` 是否配对（独立检查）

### 写作规范
- 正文是否含禁止内容（本章写作说明/12条军规/全章核心公式总结）
- 学习目标是否被正文覆盖

### 图表质量
- Mermaid 语法：禁止 emoji、timeline、mindmap、%%{init}%%、<-->
- subgraph：标题不含括号，内部无 direction
- 引号配对、圆边节点位置
- 图注在 Mermaid 图下方，表题在表格上方

### 技术深度（第1章）
- 电尺寸概念、窄带/宽带分类、术语体系、兼容电平图

## 修复流程

1. 运行 `quality_audit.py --chapter X` 获取审计结果
2. 公式标签/编号问题 → `batch_fix_formula_numbers.py`
3. Mermaid 问题 → 手动修正源文件
4. 正文违规内容 → 手动删除
5. 学习目标覆盖 → 在写作大纲中补充映射关系
6. 最终运行 `quality_audit.py --chapter X` 验证 0 issues

## 实战教训

### 教训1：审计必须覆盖所有章节
`outline_vs_chapter_audit.py` 只检查大纲-章节差距（结构性缺失），不检查军规符合性。必须同时运行质量审计（检查第二人称/Step标记/小结条目数等格式问题）。

### 教训2：小结条目数必须恰好6条
军规来源：`references/chapter-writing-standard.md` 第4.1节明确规定小结为6条要点。Mermaid图也算在小结范围内（第4/5章小结包含Mermaid图+文字要点），图表不计入6条。

### 教训3：正则必须匹配实际格式
大纲文件的节号使用 `### N.N` 格式，审计正则应同时匹配 `##` 和 `###`。

## 相关脚本

- `quality_audit.py` — 统一质量审计（公式/军规/写作规范/图表/技术深度）
- `batch_fix_formula_numbers.py` — 公式编号批量修复
- `outline_vs_chapter_audit.py` — 大纲-章节差距分析（结构性）
- `post_generation_check.py` — 生成后自动修复（LaTeX语法/缺编号/Mermaid关键字）
- `check_table_columns.py` — 表格列数检查+修复
