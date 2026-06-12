# Reference Index — 分层目录

## 分层规则

| 层 | 说明 | 何时加载 |
|:---|:-----|:---------|
| **L1 — 必备** | Agent 每次加载技能时都应读取 | 自动（写入 SKILL.md 正文） |
| **L2 — 按需** | 特定场景下才需要 | 根据 ref-quickref.md 按场景选择 |
| **L3 — 背景** | 仅排查问题时需要 | 问题发生时按需查看 |

---

## L1 必备（SKILL.md 正文已覆盖）

- `professor-level-writing-guide.md` — 9大教授级教学法
- `outline-writing-standards.md` — 写作大纲质量标准 + 15板块 + 体量基准
- `mermaid-compatibility-guide.md` — Mermaid 语法约束
- `chapter-writing-delegation.md` — 章节写作委托约束
- `domain-agnostic-architecture.md` — 领域无关架构设计

这些内容已在 SKILL.md 中以浓缩形式出现。

---

## L2 按需（根据场景选择加载）

### 场景 A：创作写作大纲
```
references/outline-writing-standards.md
templates/chapter-writing-guide-template.md
```

### 场景 B：审核/修改写作大纲
```
references/outline-writing-standards.md
references/content-supplementation-workflow.md
references/gap-fill-workflow.md
```

### 场景 C：写章节正文
```
references/professor-level-writing-guide.md
references/chapter-writing-prep.md
references/chapter-writing-style-fusion.md
references/chapter-writing-style-fusion-2.md
references/chapter-writing-rules.md（12条军规）
references/chapter-writing-endmatter.md
references/parallel-section-writing.md
```

### 场景 D：质量审计
```
references/comprehensive-quality-audit.md
references/audit-script-landscape.md
scripts/quality_audit.py --help
scripts/post_generation_check.py --help
```

### 场景 E：修复公式编号
```
references/formula-numbering-diagnosis.md
references/formula-numbering-comprehensive-fix.md
scripts/batch_fix_formula_numbers.py --help
```

### 场景 F：修复 Mermaid
```
references/mermaid-compatibility-guide.md
scripts/post_gen_check/mermaid.py
```

### 场景 G：检查体量
```
references/volume-standards.md
references/pipeline-comparison-baseline.md
```

### 场景 H：内容补充（差距分析后）
```
references/content-supplementation-workflow.md
scripts/outline_vs_chapter_audit.py --help
```

### 场景 I：写作深度提升
```
references/chapter-writing-depth.md
references/derivation-example-107.md
references/formula-derivation-standard.md
```

---

## L3 背景（排查问题时使用）

| 文件名 | 用途 |
|:-------|:-----|
| `six-dimension-audit.md` | 六维审计旧版文档（仅历史参考） |
| `pitfalls.md` | 完整陷阱列表（SKILL.md 已覆盖关键项） |
| `delegate-vs-direct-write.md` | delegate 边界测试数据 |
| `changelog.md` | 版本变更历史 |
| `domain-agnostic-audit.md` | 领域无关审计命令 |
| `pipeline-comparison-baseline.md` | 管线输出质量基线 |
| `gap-analysis-checklist.md` | 差距分析检查表 |
| `audit-pitfalls.md` | 审计陷阱列表 |
| `writing-quickref.md` | 写作快速参考 |
| `content-expansion-workflow.md` | 内容扩展工作流 |
| `textbook-style-guide.md` | 排版规范 |
| `automated-gap-analysis.md` | 自动化差距分析 |
| `six-elements.md` | 六要素旧版文档 |
| `config-philosophy.md` | 配置哲学 |
| `chapter-writing-workflow.md` | 章节写作工作流 |
| `writing-patterns.md` | 写作模式 |
| `experiment-writing-standard.md` | 实验写作标准 |
| `case-writing-template.md` | 案例编写模板 |
| `content-supplementation-from-kejinliang.md` | 柯金良补充素材 |

---

## 脚本索引

| 脚本 | 用途 |
|:-----|:-----|
| `scripts/domain_init.py` | 领域初始化（TOC提取→KG构建→领域注入） |
| `scripts/setup_project.py` | 新建项目目录 |
| `scripts/generate_outlines.py` | 生成写作大纲骨架 |
| `scripts/validate_outlines.py` | 大纲QC |
| `scripts/generate_task_list.py` | 生成写作任务 |
| `scripts/auto_write.py` | 自动写作（delegate_task） |
| `scripts/batch_fix_formula_numbers.py` | 批量修复公式编号 |
| `scripts/quality_audit.py` | 质量审计 |
| `scripts/outline_vs_chapter_audit.py` | 差距分析 |
| `scripts/post_generation_check.py` | 生成后检查 |
| `scripts/check_table_columns.py` | 表格列数检查 |
| `scripts/detect_content_type.py` | 内容类型检测 |
| `scripts/gen_prompt.py` | 生成写作提示 |
| `scripts/task_tracker.py` | 任务进度管理 |
