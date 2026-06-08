# DAG 流程分析与优化建议

## 一、当前完整流程全景

以第13章为例，当前处理一个章节的完整路径：

### Phase 0: 准备（人工/Agent 手动操作）

```
源文 file2md → 20_正文/第13章.md
         ↓
Agent 通读源文，确定本章的概念/KE/实体/KP/SP/Scene 清单
         ↓
创建 .dag/第13章/data/ 目录
```

**问题：没有模板参与的"内容规划"步骤。** Agent 凭印象决定本章要写什么类型、各类型几个条目。模板、schema、源文三者的交集没有被显式计算出来。

### Phase 1: 写 YAML（纯手工，无模板驱动）

```
Agent 逐个写 YAML 文件：
  1. concepts.yaml  — 凭对 schema 的记忆写字段
  2. kes.yaml       — 凭对 KE 模板的记忆写字段
  3. entities.yaml  — 同上
  4. kps.yaml       — 同上
  5. sps.yaml       — 同上
  6. scenes.yaml    — 同上
  7. exercises.yaml — 简单，2字段
  8. solutions.yaml — 骨架
```

**核心问题：Agent 写 YAML 的"待填字段清单"是由 Agent 自己的记忆决定的，不是由模板决定的。**

当前可用的辅助手段：
- `yaml_writer.py prompt --type xxx` — 看 @prompt，但**没有强制使用**
- `yaml_writer.py self-instruct --type xxx -c N --book-dir` — 自指导，也**没有强制使用**
- `yaml_writer.py skeleton --type xxx` — 生成骨架，但骨架不包含@prompt

### Phase 2: pipeline phase-a（自动校验 + 渲染）

```
Step 1: 校验 YAML
  - 遍历 .dag/第N章/data/*.yaml
  - 对每个 item 用 _validate_item_basic() 检查：
    - name 必填
    - fm 必填字段存在性（按 schema.json 的 fm 定义）
    - bd 必填字段存在性（按 schema.json 的 bd 定义）
    - 无多余字段（不在 schema 中的字段报错）
    - confidence 值在 allowed 列表中
  - ⚠️ 只检查字段存在性，不检查：
    - 内容是否为空字符串
    - 内容是否只是占位符（"待补充"、"无"等）
    - min_chars 约束
    - formula_check 约束
    - 模板 {{xxx}} 覆盖率（schema 有但模板没用的字段 vs 模板有但 schema 没的字段）

Step 2: 模板渲染
  - 读 schema → 读模板 → 构建 replacements dict
  - 对每个 {{xxx}} 做 str.replace
  - _auto_wrap_mermaid() 包裹 raw graph TD
  - 剥离 <!-- @prompt --> 注释
  - 输出到目标目录
  - ⚠️ 对未替换的 {{xxx}} 只打印 warning，不阻断
```

### Phase 3: 质量检查（手动/事后）

```
读取已渲染文件 → 检查：
  - @prompt 泄漏
  - {{xxx}} 残留
  - Mermaid 语法（括号引用、单行图）
  - 内容行数
→ 发现问题 → 修 YAML → 重渲染 → 再检查
```

---

## 二、关键差距分析

### 差距 1：模板是"渲染格式"而非"内容契约"

当前模板的角色：**最终的 .md 输出格式。**
模板应有的角色：**告诉 DAG 系统"这个类型需要写哪些字段、每个字段怎么写"。**

后果：
- Agent 写 YAML 时不知道模板有 26 个 bd 字段（可能漏写）。
- 即使漏写了，pipeline phase-a 的校验只查 schema 不查模板，可能通过校验但输出含 `{{xxx}}`。
- schema.json 中的字段列表和模板中的 `{{xxx}}` 列表可能不一致（没有交叉验证）。

**修复方向**：DAG 入口处增加 "模板-字段映射" 校验——用正则从模板提取所有 `{{xxx}}`，对比 schema 的 bd 字段，两边不一致时阻断。

### 差距 2：Agent 写 YAML 的工作流是"自由发挥"而非"填空"

当前 Agent 写 YAML 的流程：
```
通读源文 → 决定写哪个概念 → 凭记忆写字段 → 挨个填内容
```

应有的流程：
```
跑 self-instruct → 拿到：
  ① 模板声明了哪些字段（{{xxx}} 列表）
  ② 每个字段在模板的哪个节（章节标题）
  ③ 每个字段的 @prompt（写作指导）
  ④ schema 约束（min_chars, formula_check）
  ⑤ 源文上下文（source section）
  → 生成待填字段清单 → 逐字段填空
```

**当前 self-instruct 的输出缺少一项关键信息：模板中的 `{{xxx}}` 完整列表。** Agent 拿到 self-instruct 后仍然不知道"这个类型总共有 26 个字段，你已经写了几个、漏了几个"。

**修复方向**：self-instruct 首部加一个 `[x/26]` 完成度进度条。

### 差距 3：校验和渲染之间缺少"内容深度闸门"

Pipeline phase-a step 1 只校验字段存在性，不校验内容质量。一个 `bd: {theoretical_basis: "无"}` 不会阻断——它会通过校验、通过渲染、输出到文件，然后等到 Phase 3 手动检查才被发现。

但 schema.json 实际上已经定义了 `min_chars` 和 `formula_check` 约束——只是 pipeline_v2.py 的 `_validate_item_basic()` 没有使用它们。

**修复方向**：pipeline_v2.py 的校验函数增加内容深度检查——如果字段有 min_chars 约束但内容太短 → warning（或可配置为 error）。如果字段有 formula_check 但没有 $$ → warning。

### 差距 4：解答生成 = 骨架 + 等待 Agent

当前 solutions 永远只生成骨架（`"待Agent填充"`），没有自动化任何内容。即使源文已经明确描述了某些习题的答案，pipeline 也不尝试提取。

**修复方向**：在 `_auto_generate_solutions()` 中增加从源文段落匹配答案片段的逻辑（基于关键词相似度），至少填充 `answer` 和 `principle_steps` 两个字段。

### 差距 5：Pipeline 不生成"写作进度报告"

```
当前：phase-a → 输出 "✅ [concept] 2 files" → 结束
应有：phase-a → 输出 "✅ [concept] 2 files (2/26 bd fields missing: xxx, yyy)"
```

Agent 写完 YAML 后无法快速知道：哪些字段写了、哪些漏了、哪些太短。

**修复方向**：pipeline_v2.py 在渲染完成后，对每类型做覆盖率报告——统计字段填充率、空值率、`{{xxx}}` 残留率。

### 差距 6：跨章节知识一致性检查

当前 pipeline 完全按章节隔离运行。但第13章的内容可能引用第3章的传导耦合概念（习题8明确要求跨章节分析）。pipeline 不检查跨章节的 wikilink 是否正确，也不检查同名概念的定义是否一致。

---

## 三、优化方案（按优先级排列）

### P0 — 立刻做，阻断核心缺陷

#### 优化 1：模板字段覆盖率校验（DAG 入口）

在 `pipeline_v2.py` 的 Step 1（YAML 校验）中增加：

```python
def check_template_coverage(yaml_path, type_name, schema):
    """检查 YAML 中的 bd 字段是否覆盖了模板中所有的 {{xxx}}"""
    # 1. 从 schema 读模板文件名
    template_file = schema['node_types'][type_name]['template']
    # 2. 从模板文件提取所有 {{xxx}}
    template_vars = set(re.findall(r'\{\{(\w+)\}\}', template_content))
    # 3. 去除非 bd 的特殊字段（name, book_id 等自动填充字段）
    template_vars -= AUTO_FILL_VARS
    # 4. 检查 YAML 中已有的 bd 字段
    existing_bd = set(yaml_item.get('bd', {}).keys())
    missing = template_vars - existing_bd
    # 5. 输出覆盖率
    coverage = len(existing_bd & template_vars) / len(template_vars) * 100
    return missing, coverage
```

这个校验确保 Agent 没漏写模板要求的字段。

#### 优化 2：内容深度约束校验

在 `pipeline_v2.py` 的 `_validate_item_basic()` 中增加：

```python
# 对每个 bd 字段检查 schema 的 constraints
for bd_name, bd_def in bd_schema.items():
    constraints = bd_def.get('constraints', {})
    value = str(bd.get(bd_name, ''))
    min_chars = constraints.get('min_chars', 0)
    if min_chars > 0 and len(value) < min_chars:
        errors.append(f"{bd_name} 内容过短 ({len(value)}字 < 要求{min_chars}字)")
    if constraints.get('formula_check') and '$$' not in value:
        errors.append(f"{bd_name} 需要 $$ 包裹公式，但未找到")
```

#### 优化 3：Agent 写 YAML 前插入强制指令

在 `yaml_writer.py write` 命令中新增 `--use-self-instruct` 参数，或在 write 之前自动跑 self-instruct：

```bash
# 改前：
yaml_writer.py write --type concept --yaml-path ... --items '[...]'

# 改后（加 show-first）：
yaml_writer.py write --type concept --yaml-path ... --items '[...]' --show-prompt
# 默认先输出 @prompt + schema 约束，Agent 看完后再接受 items
```

### P1 — 提升质量，大幅减少修复循环

#### 优化 4：self-instruct 增加字段覆盖率进度

在当前 `cmd_self_instruct()` 的输出首部增加一条：

```
📊 字段覆盖：template 声明 26 个 bd 字段 (必填 23 + 可选 3)
   已完成: 0/26 (0%)
```

Agent 写 YAML 前先看覆盖率，写完后重新跑 `self-instruct` 确认覆盖率。

#### 优化 5：pipeline 渲染后输出覆盖率报告

在 `template_engine.py` 的 `cmd_render_chapter()` 末尾增加统计：

```python
# 对每类型统计
stats = {
    'total_fields': len(all_template_vars),
    'filled_fields': len(filled_vars),
    'empty_fields': [f for f in all_template_vars if rendered_value(f) in ('无', '')],
    'placeholder_residue': remaining_placeholders,
}
```

输出格式：
```
📊 [concept] 覆盖率: 24/26 (92%)
   ❌ 未填: core_concept_map (可选), related_knowledge_elements (可选)
   ⚠️  内容为空: 无
```

### P2 — 自动化增强

#### 优化 6：自动习题答案提取

在 `_auto_generate_solutions()` 中增加源文关键词匹配——对已知答案明确在源文中的习题（如"电磁兼容三要素是什么"），自动提取答案段落。

#### 优化 7：跨章节一致性检查

增加独立脚本 `check_cross_chapter.py`，扫描所有 chapter 的概念/KE/实体，检查：
- 同名概念的定义是否一致（余弦相似度+阈值）
- wikilink 目标文件是否存在
- 跨章节引用的方向是否对称

---

## 四、关键设计原则（优化后）

```
模板（{{xxx}} + @prompt）
    │
    ▼
self-instruct（解析模板 → 提取字段清单 + @prompt + schema约束 + 源文语境）
    │
    ▼
Agent 收到标准化工作台：
  ┌─────────────────────────────────┐
  │ 📋 类型: concept               │
  │ 📊 字段覆盖率: 待填: 26个       │
  │ 📌 term_definition: ≥50字       │
  │    从源文摘抄 - 以下源文片段:   │
  │    [20_正文/第13章.md: L15-35]  │
  │ 📌 mathematical_model: 需$$公式  │
  │    源文相关公式: [L120-125]     │
  │ ...                            │
  └─────────────────────────────────┘
    │
    ▼
Agent 填空式写作（字段名锁定、格式锁定、约束锁定）
    │
    ▼
pydantic 校验（字段名、类型、confidence）
    │
    ▼
pipeline phase-a（模板覆盖率校验 + 内容深度校验 + 渲染）
    │
    ▼
覆盖率报告 → Agent 补充 → 再渲染
```
