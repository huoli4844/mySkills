---
name: domain-book-wiki
template_version: v1.0
domain: research
description: 知识库构建编排系统 — 教材源文→结构化YAML数据→模板引擎→Obsidian知识库。含schema_loader.py字段管理、pipeline preflight预验证闸门
version: v52.4
triggers:
  - "生成知识库"
  - "domain-wiki"
  - "知识库构建"
  - "dag pipeline"
  - "schema_loader"
  - "preflight"
---

# domain-book-wiki — 知识库构建编排系统

教材源文 → 知识库（结构化 YAML 数据 → 模板引擎 → Obsidian/Markdown 输出）

## 核心工作流（v52.4+）

### 推荐流程（每章一次通过）

```bash
# 1. 初始化
dag_controller.py pipeline init -w $BOOK_DIR --book-id XXX -c N

# 2. 写入 YAML 数据到 .dag/第N章/data/
#    用 schema_loader 获取正确字段名：
python3 scripts/schema_loader.py extract concept --yaml

# 3. 预验证（先查问题再跑auto）
dag_controller.py pipeline preflight -w $BOOK_DIR --book-id XXX -c N

# 4. 一次性修复所有问题 → 单次auto通过
dag_controller.py pipeline auto -w $BOOK_DIR --book-id XXX -c N
```

### 旧流程（避免）
```bash
# ❌ 直接auto → 第3阶段发现问题 → 回来修 → 重跑 → ...
dag_controller.py pipeline auto ...  # 第一次：3/12 通过，平均3-4次手动干预
```

## 新命令速查（v52.4）

| 命令 | 用途 |
|:-----|:------|
| `pipeline preflight -w $DIR -c N` | 验证全部8个YAML文件后再跑auto |
| `schema_loader.py list` | 列出8种类型及模板字段数 |
| `schema_loader.py extract concept` | 提取概念模板的bd字段名列表 |
| `schema_loader.py extract concept --yaml` | 生成YAML骨架（含全部正确字段名） |
| `schema_loader.py validate <yaml_path>` | 验证单个YAML的bd字段vs模板 |
| `schema_loader.py verify type f1 f2` | 快速验证字段名合法性 |

## 架构

```
dag_controller.py           CLI入口（preflight + SKILL_DIR）
dag_pipeline_run.py         auto编排（数据变更自动检测 + 字段校验）
phase_validator.py          阶段输出验证（置信度/占位符/FrontMatter）
schema_loader.py [NEW]      模板字段名唯一权威源（替代4处分散列表）
build_kb_files.py           YAML → .md 渲染引擎
template_assembler.py       模板引擎（__main__已恢复）
post_build_fix.py           自动修复（双反斜杠/公式/wikilink）
```

## 字段名管理

### 背景（v52.4之前的问题）
技能有4个分散的字段名权威源（模板`{{xxx}}`、REQUIRED_BD_FIELDS、CONFIDENCE_LEVELS、字段校验），写 YAML 时用错字段名→模板`{{xxx}}`不替换→build后残留→质量D级。

### 解决
`schema_loader.py` 从 `assets/templates/*.md` 自动提取 `{{xxx}}` 占位符。自动过滤 `name`/`source_chapter`/`source_from`/`bloom_level` 等自动填充字段。Agent 写 YAML 前需用 `extract --yaml` 生成骨架。

### 症状
- build 生成的 `.md` 中出现 `{{xxx}}` 原样残留
- pipeline auto 输出 `[字段校验/类型/名称] 缺N字段: ...`
- preflight 输出 `⚠️ [名称] 缺N字段: field1, field2`

## 关键陷阱（v52.4 新增）

### B6. Confidence 值必须匹配 CONFIDENCE_LEVELS

`tac_constants.CONFIDENCE_LEVELS` 严格校验每类节点的 confidence 值：

| 类型 | 允许值 | 含义 |
|:-----|:-------|:-----|
| concept | `{0.95}` | 精准释义逐字匹配出处 |
| ke / entity | `{0.85}` | 基于正文归纳 |
| kp | `{0.85}` | 基于正文归纳 |
| sp | `{0.75}` | 操作步骤来自原文 |
| scene / exercise | `{0.65}` | 基于教材案例 |
| solution | `{0.65, 0.85}` | 骨架0.65 / Agent填充0.85 |

写错 confidence 直接阻断 build。用错值（concept=0.85 / sp=0.80）导致 build_kb_files.py 输出"OK 完成: 0 个文件"。

### B7. Preflight 先于 pipeline auto 执行

缺失字段（missing）→ 必须补充，否则 {{xxx}} 残留阻断build → **阻断级**
多余字段（extra）→ 不会阻断build，但不清理会干扰后续校验
置信度超出允许值 → **阻断级**

### B8. 自动填充字段无需写入 bd

`name`, `source_chapter`, `source_from`, `type_tag`, `type`, `confidence`,
`confidence_note`, `chapter_num`, `bloom_level`, `entity_type`, `aliases`, `tags`,
`book_id`, `book_name`, `exercise_link`, `exercise_name`, `bloom_progression_analysis`

这些字段只写一次（放在`fm:`或`bd:`中），不重复。

### B9. [已知] Solutions 回退骨架生成（eval_template 格式不匹配）

**症状**: `pipeline auto` 的 solutions 阶段输出 `⚠️ build_kb_files.py 返回非零（可能 solutions.yaml 缺失）` → 回退到从习题文件直接生成骨架解答。生成的 .md 含 `{{type_tag}}`, `{{bloom_level}}` 占位符残留。

**根因**: `build_kb_files.py` 处理 `--type solution` 时，期望的 bd 字段结构与 `eval_template.md` 中的 `{{xxx}}` 字段名不完全一致，导致 template_assembler 找不到匹配。现有workaround是回退到 skeleton 生成 + auto-fix，但 `{{type_tag}}` 和 `{{bloom_level}}` 无法自动填充（它们在 frontmatter 中但 skeleton 生成时未提供）。

**当前状态**: 非阻断问题 — 解答骨架可以正常浏览，但 2 个占位符残留影响 Obsidian 渲染。需后续系统修复 `build_kb_files.py` 的 solution 处理逻辑或统一 solutions.yaml 的 bd 字段名为 eval_template.md 的精确 {{xxx}} 集合。

### B10. [新增] Preflight 不覆盖内容深度质量

pipeline preflight 保障**格式正确性**（字段名、confidence、文件存在），但**不检验内容深度质量**。

第8章审计经验：

| 检查项 | preflight 是否覆盖 | 第8章合规率 |
|:-------|:------------------:|:----------:|
| 占位符残留 | ✅ | 100% |
| 字段名匹配 | ✅ | 100% |
| confidence合规 | ✅ | 100% |
| 理论基础深度(≥150字) | ❌ | 0% (4/4 KP不足) |
| Wikilink 引用(≥3条) | ❌ | 0% (4/4 KP无) |
| formula $$ 包裹 | ❌ | 0% (1/1概念用纯文本) |
| bloom_level 在fm中 | ❌ | 0% (4/4 KP缺失) |

**原因**: 内容深度是语义级质量，不可通过文件结构和字段名模式匹配自动检查。

**缓解措施**: 写 YAML 时参照 `references/yaml-content-quality-checklist.md` 逐一核查。已知缺陷追踪表在该文件中维护。

## 快速调试

```bash
# pipeline状态
dag_controller.py pipeline status -w $BOOK_DIR --book-id XXX -c N

# 预验证YAML数据（推荐：先于pipeline auto）
dag_controller.py pipeline preflight -w $BOOK_DIR --book-id XXX -c N

# 字段名排查
python3 scripts/schema_loader.py validate .dag/第N章/data/solutions.yaml

# 确认类型名→模板文件映射
python3 scripts/schema_loader.py list

# 生成YAML骨架供Agent参考
python3 scripts/schema_loader.py extract concept --yaml
```

## 完整验证示例（ch7 实际运行记录）

第7章（搭接技术及其应用，264行，6习题）从零到完全构建的完整流程：

```bash
# 1. init + 写8个YAML文件
dag_controller.py pipeline init -w $BOOK_DIR -c 7
# ← 手动写入 .dag/第7章/data/concepts.yaml 等8文件

# 2. preflight：一次性发现9项问题（全部是extra field，非阻断）
dag_controller.py pipeline preflight -w $BOOK_DIR -c 7
# 返回: "发现9项问题（上述 ⚠️ 标记），请修复后运行 pipeline auto"

# 3. 清理extra field（1次性操作，30秒）
# ← 从concepts.yaml移除5个legacy字段，从scenes.yaml移除1个

# 4. 再次preflight → 全通过
dag_controller.py pipeline preflight -w $BOOK_DIR -c 7
# 返回: "🎉 Preflight 全部通过: 30 项数据，无问题"

# 5. pipeline auto → 9/12阶段一次通过（0中断）
dag_controller.py pipeline auto -w $BOOK_DIR -c 7
# 输出: concepts(4) ke(4) entities(3) kp(3) sp(2) scene(2) exercises(6) solutions(106)
# L2/L3/L4跳过（非最终章）
```

**效果**: 从写YAML到构建完成，**零手动中断、零多次重跑**。

## 版本历史

v52.4a (2026-06-08) — 当前版本
- SKILL.md 从无操作占位符改为完整使用文档
- 新增推荐工作流（preflight先于auto）
- 新增CONFIDENCE_LEVELS速查表
- 新增B9（解答骨架回退已知问题）
- 新增ch7完整验证示例
- schema_loader.py: 模板字段唯一权威源
- pipeline preflight: 预验证闸门
- 自动填充字段过滤：消除假阳性

v52.3 — 字段校验warning
v52.2 — 数据变更自动检测 + template_assembler __main__恢复