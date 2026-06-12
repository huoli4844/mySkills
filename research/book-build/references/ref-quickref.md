# 参考文件快查表

## 按场景速查

| 你正在做 | 需要加载 |
|:---------|:---------|
| **写大纲** | `templates/chapter-writing-guide-template.md` + `references/outline-writing-standards.md` |
| **修改大纲** | 同上 + `references/gap-fill-workflow.md` |
| **写章节正文** | `references/professor-level-writing-guide.md` + `references/chapter-writing-rules.md` + `references/parallel-section-writing.md` |
| **审章节正文** | `references/chapter-writing-prep.md` + `references/chapter-writing-endmatter.md` |
| **质量审计** | `scripts/quality_audit.py --quick` 或 `--full` |
| **公式编号修复** | `scripts/batch_fix_formula_numbers.py` |
| **Mermaid修复** | `references/mermaid-compatibility-guide.md` |
| **领域初始化** | `scripts/domain_init.py --project /path/to/教材` |
| **体量检查** | `references/volume-standards.md` |
| **深度优化** | `references/chapter-writing-depth.md` |
| **差距分析** | `scripts/outline_vs_chapter_audit.py` + `references/content-supplementation-workflow.md` |
| **排查问题** | 先看 `references/INDEX.md` L3 背景层 |

## 核心文件清单（按重要性降序）

```
  L1·必读
  ├─ references/professor-level-writing-guide.md    教学法（每次写正文必读）
  ├─ references/mermaid-compatibility-guide.md       Mermaid规则（每次写图必读）
  ├─ references/chapter-writing-delegation.md        delegate约束（每次委托前读）
  └─ references/domain-agnostic-architecture.md      架构说明（新项目初始化时读）

  L2·按需
  ├─ templates/chapter-writing-guide-template.md     写作大纲模板
  ├─ references/outline-writing-standards.md         大纲质量标准
  ├─ references/chapter-writing-rules.md             12条军规
  ├─ references/chapter-writing-prep.md              章前准备
  ├─ references/chapter-writing-endmatter.md         章末模板
  ├─ references/chapter-writing-style-fusion.md      风格融合
  ├─ references/parallel-section-writing.md          并行分节写作
  ├─ references/content-supplementation-workflow.md  内容补充
  ├─ references/gap-fill-workflow.md                 查疑补漏
  └─ references/comprehensive-quality-audit.md       质量审计

  L3·背景
  └─ 详见 references/INDEX.md
```

## 快速规则速查

| 规则 | 一句话 |
|:-----|:-------|
| 公式格式 | `$$` → `\tag{章-序号}` 独占行 → `$$` |
| Mermaid | 仅 `graph TD/LR`，禁 emoji/`%%{init}%%`/subgraph |
| 图注/表题 | 图注在下方 `*图X-X：标题*`，表题在上方 `**表X-X：标题**` |
| 12条军规 | Agent 自查工具，**不是教材正文** |
| 案例来源 | 公开真实事件，**禁止从参考书摘抄** |
| 写作原则 | **借鉴手法，不照搬内容** |
| book-build.yaml | 最小化（只放教材名+参考书路径） |
