---
name: book-build
description: "教材写作管线：大纲驱动 → delegate_task 并行创作 → batch_fix 公式编号 → 质量审计 → git 提交。提供写作大纲解析、内容差距分析、P0/P1 分阶段补充、公式编号批量修复、全章质量审计等工具。适用场景：基于多本参考书进行的中文专业教材（特别是电磁兼容/EMC领域）的结构化编写。"
version: 3.2.0
author: Hermes Agent
license: MIT
platforms: [macos, linux]
metadata:
  hermes:
    tags: [textbook, emc, outline-driven, academic-writing]
    related_skills: [github-repo-management, file2md]
---

# book-build（教材写作管线）

## Overview

**大纲驱动，写作大纲供料，严格遵循结构，专业级学术写作。** 管线由脚本控制流程、Agent 负责创作判断。脚本不做创造，Agent 不做机械重复。

**核心原则：借鉴手法，不照搬内容。** 参考教材是学习写作手法的老师，不是摘抄内容的仓库。融合多本教材内容用自己的语言重新组织，禁止段落级复制粘贴。

```
setup_project.py      ① 创建项目目录 + 配置
       ↓
generate_outlines.py  ② 提纲docx → Agent 生成写作大纲（可人工调整）
       ↓
validate_outlines.py  ③ 大纲 QC
       ↓
generate_task_list.py ④ 从大纲生成写作任务列表
       ↓
auto_write.py         ⑤ 按任务列表自动 → delegate_task 逐章创作
       ↓
batch_fix_numbers     ⑥ 批量修复公式编号
       ↓
quality_audit.py      ⑦ 统一质量审计 + 修复
```

**全自动执行（核心偏好）**：执行时不问"要不要/是否继续"，直接做。

## When to Use

- 用户要求**新建**教材项目 → `setup_project.py`
- 需要从提纲+参考书**生成写作大纲** → `generate_outlines.py` + Agent
- 需要**检查写作大纲**完整性 → `validate_outlines.py`
- 需要从大纲**编排写作任务** → `generate_task_list.py`
- 需要**自动逐章写作** → `auto_write.py`
- 需要**补充/扩充**已有章节内容 → delegate_task
- 需要**批量修复**公式编号 → `batch_fix_formula_numbers.py`
- 需要**质量审计** → `quality_audit.py`

## Design

### 三层配置架构

| 层 | 内容 | 存放位置 |
|:---|:-----|:---------|
| **技能层** | 操作流程、陷阱清单、公式格式铁律 | SKILL.md + references/ |
| **项目层** | 教材名、参考书路径（仅此而已） | `book-build.yaml` |
| **章节层** | 每章内容结构、建议体量、素材来源 | `写作大纲/writing-guide-chX.md` |

### 配置哲学（硬核教训，不要违背）

`book-build.yaml` **只放项目信息**（教材名 + 参考书路径）。不要往里面塞任何"写作风格规范"、"内容密度底线"、"公式推导标准"等。这些归 SKILL.md（通用规则）和写作大纲（章节特异性规则）管。

**错误示范（已被纠正）：**
- ❌ `writing_style` 任何字段都不该在 yaml 里
- ❌ `density_baseline` 该在写作大纲里
- ❌ `knowledge_base` 由 `source_books[].path` 覆盖

**正确做法：**
- ✅ `book-build.yaml` = 教材名 + 参考书路径（18行足矣）
- ✅ 写作规范 → SKILL.md 或 references/
- ✅ 每章密度底线 → 写作大纲中定义

### 脚本与 Agent 分工
- **脚本**管流程编排、文件操作、统计检查
- **Agent**管内容创作、质量判断、调整决策

## Workflow

### ① 创建项目

```bash
python3 scripts/setup_project.py /path/to/教材 \
  --name "电磁兼容教材" --outline 教材提纲.docx
```

完成后编辑 `book-build.yaml`，填入参考教材路径。

### 生成写作大纲（关键环节）

**两阶段流程：**

**第一阶段：脚本生成骨架（`generate_outlines.py`）**

从提纲 docx 解析章节结构，创建 `output/写作大纲/writing-guide-chX.md`，包含全部 15 个板块的空白模板。同时输出 `output/outline_tasks.json` 供第二阶段使用。

**第二阶段：Agent 填充完整内容**

读取 `output/outline_tasks.json`，对每个 `pending` 任务执行 `delegate_task`。**每一章的填充是一个独立委托任务**，因为各章参考书内容不同。

Agent 需填充全部 15 个板块，重点关注**每节写作指南**（写作手法/必含要素/设问过渡/案例建议）。填充标准见本章**写作大纲标准**节。

### ③ 大纲 QC

```bash
python3 scripts/validate_outlines.py --project /path/to/教材
```

### ④ 生成任务列表

```bash
python3 scripts/generate_task_list.py --project /path/to/教材 --force-init
python3 scripts/generate_task_list.py --project /path/to/教材 --status
python3 scripts/generate_task_list.py --project /path/to/教材 --mark-done 3
```

### ⑤ 自动写作

```bash
# 生成下一条写作任务
python3 scripts/auto_write.py --project /path/to/教材

# 遍历全部待写
python3 scripts/auto_write.py --project /path/to/教材 --all

# 覆盖已有章节
python3 scripts/auto_write.py --project /path/to/教材 --chapter 3 --force
```

`auto_write.py` 输出结构化 JSON 到 `.hermes/tasks/write_chX.json`，格式：

```json
{"goal": "为教材项目创作第X章完整内容",
 "context": "...写作大纲+参考书路径+写作规范...",
 "chapter": X,
 "guide_path": "output/写作大纲/writing-guide-chX.md",
 "output_path": "output/第X章-标题.md"}
```

Agent 读取该 JSON 后直接提交给 `delegate_task`：

```
delegate_task(
  goal=task.goal,
  context=task.context,
  toolsets=["terminal", "file"]
)
```

创作完成后运行 `batch_fix_formula_numbers.py` 修复编号。

### ⑥ 统一修复公式编号

```bash
python3 scripts/batch_fix_formula_numbers.py /path/教材/output/第*.md
```

### ⑦ 质量审计

```bash
# 全量（检查公式编号、$$配对、Mermaid语法、禁止内容）
python3 scripts/quality_audit.py --project /path/to/教材

# 单章
python3 scripts/quality_audit.py --project /path/to/教材 --chapter 7

# 快速（仅检查公式和$$）
python3 scripts/quality_audit.py --project /path/to/教材 --quick
```

审计覆盖范围：公式编号连续性、$$配对、内容统计（表格/图/例题）、Mermaid 语法校验（`---config---` 兼容性、subgraph括号、round node顺序、timeline书名号）、禁止内容检查（写作说明/军规/公式总结/Bloom标签）。

### 补充已有章节

```bash
# P0（结构性缺失）：patch 少量框架
# P1（内容质量提升）：delegate_task 深度补充

# 差距分析
python3 scripts/outline_vs_chapter_audit.py \
  --project /path/to/教材 --output /path/to/教材/output
```

## 写作大纲质量标准

Agent 完善写作大纲时，每个大纲必须达到以下标准才能算完成。**达不到这些标准的大纲，写出的章节质量必然不合格。**

### 量化硬指标

| 指标 | 每章要求 | 检查方式 |
|:-----|:--------|:---------|
| 总大小 | **≥35KB** | `ls -la output/写作大纲/writing-guide-chX.md` |
| 板块数 | **全部18个板块非空** | 目视检查，无`[具体说明]`、`[要素X]`等占位符 |
| 各教材写作手法对比表 | **9维度×4教材 = 36格** | 每格应有实质内容 |
| 各书最值得借鉴手法 | **4书×3条 = 12条** | 每条应有手法名+说明+借鉴方式 |
| 各教材共同盲区 | **≥8条** | 每条含具体表现+发挥空间 |
| 每节写作指南 | **每节≥5条必含要素、≥2句设问过渡、≥2个案例** | 逐节检查 |
| 结构建议表 | 每节标注体量(KB)+手法+素材来源 | 检查所有字段已填 |
| 图表清单 | **≥8项** | 含编号+类型+内容+位置+来源 |
| 素材清单 | **按图片/案例/标准分类** | 每类≥5项，标注优先级 |

### 质量核查步骤

完善大纲后，运行以下检查：

```bash
# 1. 大小检查
ls -la output/写作大纲/writing-guide-chX.md   # 应≥35KB

# 2. 占位符检查
grep -c '\[具体说明\]' output/写作大纲/writing-guide-chX.md  # 应为0
grep -c '\[要素' output/写作大纲/writing-guide-chX.md       # 应为0

# 3. 板块完整性
grep -c '^## ' output/写作大纲/writing-guide-chX.md  # 应有15个以上##板块

# 4. 案例建议
grep -c '案例建议' output/写作大纲/writing-guide-chX.md  # 应≥4节
```

### 如果质量不达标

- 缺分析深度 → 重新读取参考教材，补充写作手法对比
- 有占位符 → 逐项替换为实际内容
- 体量不足 → 补充案例建议、设问过渡、必含要素

每章开头：

```markdown
# 第X章 章节名称
## 内容提要
...段落...
通过本章学习，读者应达成以下学习目标：
1. 能......（不要加 Bloom 标签）
2. 能......
```

**关键要求：每一条学习目标必须被正文覆盖。** 写作大纲中需填写"学习目标与内容覆盖映射表"，逐条确认每条目标的对应节号。`quality_audit.py` 会自动检查学习目标关键词是否在正文中出现，超半数缺失会报"可能未被覆盖"。

**禁止**：`**记忆层**` Bloom 标签、`## 学习目标`（统一为 `## 内容提要`）

## 写作大纲标准（15板块结构）

每份写作大纲必须包含以下 15 个板块。**大纲的厚度决定章节的厚度**——无每节写作指南的大纲产出约40KB/章，有则可达100KB+。

| # | 板块 | 填充内容 | 作用 |
|:-:|:-----|:---------|:-----|
| ① | **格式规范** | 公式/Mermaid/表格写法 + 禁止内容 | 创作前必读，避免返工 |
| ② | **各教材章节对应关系** | 4列参考书对应表 | 确定每节素材来源 |
| ③ | **各教材写作手法对比表** | 9维度固定框架对比 | 学习各书写作技法 |
| ④ | **各书最值得借鉴的3个手法** | 每书3条+借鉴方式 | 明确可复用的技法 |
| ⑤ | **各教材共同盲区** | 技术盲区+教学盲区表 | 确定发挥空间 |
| ⑥ | **本章定位** | 四大使命+读者画像+篇幅 | 章节创作导向 |
| ⑦ | **写作原则** | 借鉴手法不照搬内容 | 红线约束 |
| ⑧ | **结构建议表** | 每节体量/手法/素材 | 控制章节体量 |
| ⑨ | **每节写作指南 ⭐** | 写作手法+必含要素+设问过渡+案例建议 | **核心**：直接约束章节深度 |
| ⑩ | **图表清单** | 编号/类型/内容/位置/来源 | 配图规划 |
| ⑪ | **重点素材清单** | 图片/案例/标准三类+优先级 | 素材规划 |
| ⑫ | **12条军规检查** | 12项自查（Agent用，不写入正文） | 质量自检 |
| ⑬ | **待改进方向** | 后续可补充的方向 | 迭代规划 |
| ⑭ | **衔接要点** | 表格，≥5个衔接方向 | 确保章节连贯 |
| ⑮ | **填充示例** | 第1.1节完整示例 | Agent参考格式 |

### 每节写作指南（④）的填充标准

Agent 为每节填充 4 个维度：

**写作手法**：叙事逻辑链，如"日常现象引入→EMD/EMI辨析→三要素框架→数学模型"。这定义了该节的行文脉络。

**必须包含的要素**：读者必须掌握的 3-8 条知识点，每条含参考教材出处。例如"EMD与EMI因果关系辨析（GB/T 4365定义，路宏敏§1.2.1）"。**要素越多，章节体量越大。**

**建议的设问过渡**：段落之间的衔接语句，可直接用在正文中。例如"从上面的辨析可以看出，EMI是EMD通过耦合途径作用于敏感设备的结果。由此引出了电磁兼容分析中最核心、最基本的框架——电磁干扰三要素。" **过渡越流畅，章节可读性越高。**

**案例建议**：公开真实事件（非教材摘抄），标注用在哪个知识点后。例如"阿波罗12号雷击事件（用在EMI概念后，NASA报告MSC-01855重新叙述）"。

### ⚠️ 量化底线（2026-06-12 实战验证）

**写作大纲的密度直接决定章节的体量。** 验证数据：

| 指标 | 无量化底线时 | 有量化底线后 |
|:----|:-----------|:-----------|
| 章节大小 | 34KB（结构好但内容薄） | 42KB（同等结构+内容充实） |
| 案例数 | 2个 | 9个 |
| 公式数 | 4个 | 8个 |

每节的填充必须满足以下底线（在 `generate_outlines.py` 的 CHAPTER_TEMPLATE 中已硬编码）：

- **案例**：每节至少 2 个（1个生活化 + 1个工程案例），全章至少 8 个
- **公式**：每节至少 1 个编号公式，全章至少 8 个
- **必含要素**：全部列入，不得跳过
- **设问过渡**：每节至少 2 句

**验证方法**：创作完成后运行 `quality_audit.py`，审计报告会显示案例数和公式数。低于底线则需补充。

### ⚠️ 常见错误

- ❌ 只填充结构建议表（⑧）就认为大纲完成——这是最大的坑。**⑨每节写作指南才是决定章节质量的关键**
- ❌ 必含要素只写标题不写具体内容——要素需要精确到"含哪个定义、来自哪本书哪节"
- ❌ 案例建议从参考教材中摘抄——必须来自公开真实事件

## ⚠️ 关键澄清

**写作大纲中的以下部分是 Agent 自查工具，不是教材正文，不得写入章节文件：**

| 大纲节 | 用途 |
|:-------|:-----|
| `5.2 12条军规落实检查` | Agent 写完章节后自查自纠的检查清单 |
| `5.1 重点素材清单` | 写作过程中的素材规划，不输出到正文 |
| `5.3 待改进/补充方向` | 后续迭代计划，不输出到正文 |

**教材正文只包含**：叙述性内容、编号公式（`\tag{章-序号}`）、表格、Mermaid 图、例题与习题、参考文献与深入阅读。

- `\tag{N-M}` **独占一行**，在公式内容之后、**闭合 `$$` 之前**
- 正确：`$$\n公式\n\tag{N-M}\n$$`
- 错误：`$$\n公式\n$$\n\tag{N-M}`
- 引用块内公式：`> $$\n> 公式\n> \tag{N-M}\n> $$`
- 违反 → 运行 `batch_fix_formula_numbers.py`

## Common Pitfalls

1. **行级状态机，不用正则** — `\$\$(.*?)\$\$` 对 `>$$` 格式无效。必须用行级状态机
2. **空 `$$...$$` 块** — 编号前先删除
3. **`>$$` 保留 `>` 前缀** — v3 做法，不要替换为 `$$`
4. **先读后写** — 永远 `read()` 再 `write()`，绝不先写后读
5. **Mermaid 圆边节点** — `[("text")]`（对）而非 `[("text)"]`（错）
6. **Mermaid 禁止 emoji** — 节点标签中的 `🔄⚠️🚫📋⭐` 等 emoji 导致渲染器解析失败，用纯文字替代（已在 `references/mermaid-compatibility-guide.md` 中详细说明可用/禁用语法）
7. **Mermaid subgraph 内 direction** — subgraph 内使用 `direction TB/LR` 可能引发渲染问题
8. **Mermaid timeline 中文书名号** — timeline 内容中避免使用 `《》`，可能导致渲染中断
9. **写作说明不写入正文** — 军规检查/核心公式总结是内部工具，不得写入章节文件
10. **book-build.yaml 最小化** — 只放教材名和参考书路径，写作规范在其他地方

## Reference Index

| 需要时加载 | 内容 |
|:-----------|:------|
| `references/formula-numbering-diagnosis.md` | 公式编号根因诊断 + 陷阱 A-E |
| `references/formula-numbering-comprehensive-fix.md` | 综合修复流程 + 诊断决策树 |
| `references/comprehensive-quality-audit.md` | 全章质量审计工作流 |
| `references/content-expansion-workflow.md` | 内容扩充工作流 |
| `references/mermaid-compatibility-guide.md` | Mermaid 兼容性指南（禁止语法+替代方案） |
| `references/mermaid-validation-checklist.md` | Mermaid 语法质量检查清单 |
| `references/mermaid-guide.md` | Mermaid 陷阱与正确写法 |
| `references/derivation-example-107.md` | 公式推导示例 |
| `references/chapter-writing-standard.md` | 章节写作标准 |
