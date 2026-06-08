# YAML 生成指南 — Agent 写数据文件规范

## Schema 要求

所有 YAML 数据文件必须严格遵循 `{name, file, fm, bd}` 四字段结构。

### 字段说明

```yaml
- name: "名称"                    # 条目名称，人类可读
  file: "概念中文名"              # 短名/文件名（无 .md 无路径）
  fm:                            # 元数据（frontmatter）
    source_chapter: "1"          # 字符串，非数字
    source_from: "第1章 1.2.2"    # 来源定位
    confidence: 0.95             # 必须匹配节点类型的允许值！
    confidence_note: "精准释义逐字匹配出处原文"  # 必填！
  bd:                            # 内容数据（必须是字典，不是 | 块字符串）
    term_definition: "..."       # 模板字段在 bd 内部
    ...
```

### 节点类型 vs 置信度对照表

| 类型 | 文件名 | 置信度 | file 字段命名规则 | 说明 |
|:-----|:-------|:------:|:-----------------|:-----|
| concept | concepts.yaml | **0.95** | 概念中文名（如 `电磁兼容`） | 固定值，仅此可接受 |
| ke | kes.yaml | **0.85** | KE 中文名（如 `系统电磁兼容性`） | 允许值 `{0.85}` |
| entity | entities.yaml | **0.85** | 实体名（如 `CISPR`） | 允许值 `{0.85}` |
| kp | kps.yaml | **0.85** | KP 中文名（如 `EMC_EMI_EMD基本概念与定义`） | 允许值 `{0.85}`。**禁止**用 `第N章-知识点N` |
| sp | sps.yaml | **0.75** | SP 中文名 | 允许值 `{0.75}` |
| scene | scenes.yaml | **0.65** | 场景中文名 | 允许值 `{0.65}` |
| exercise | exercises.yaml | **0.65** | `第N章-习题N`（标准化格式） | 允许值 `{0.65}`（非 0.85！） |
| solution | solutions.yaml | **0.65** | `第N章-习题N-解答` | 允许值 `{0.65}` |

**重要**：
- 置信度必须精确匹配允许值中的某个值。0.95 ≠ 0.98，0.85 ≠ 0.95。
- KP 的 `file` 字段必须使用知识点名称（如 `EMC基本概念`），**禁止**使用 `第1章-知识点1` 格式。
- **`source_from` 字段禁止包含 `"第N章 "` 前缀**。模板自动拼接 `第{{source_chapter}}章 §{{source_from}}`，若 source_from 已含 `"第2章 "` 则渲染为 `第2章 §第2章 2.2`（重复）。正确值：`"2.2"`、`"2.2.1 电磁干扰三要素"`。
- 违反了上述规则的，`build_kb_files.py` 会逐文件检查 FrontMatter，不符合直接跳过该文件。
### 常见结构错误

| 错误模式 | 现象 | 修复 |
|:---------|:-----|:-----|
| 顶层无 name/file/fm/bd | build_kb_files 读不到数据 | 包装为 `{name, file, fm, bd}` 四字段 |
| confidence 值错误（如 exercise=0.85） | build 说"不符合允许值"，0 文件产出 | 修改 confidence 为允许值列表中的值 |
| kps.yaml 的 bd 字段在顶层 | build 说"数据为空"或 0 文件 | 把 solved_problem/learning_objectives 等移到 bd 下 |
| exercises.yaml 扁平结构（无 fm/bd） | build 说"数据未找到" | 添加 fm (含 source_chapter+confidence) + bd |
| fm 缺失 confidence 字段 | 构造时 KeyError 或 0 文件 | 补 confidence + confidence_note |
| bd 是 `|` 块字符串 | 所有 `{{字段}}` 占位符不替换 | bd 必须是字典，公式/图在字典内部用 `|` 块 |
| source_chapter 是数字 1 而非字符串 "1" | schema 校验失败 | 加引号 `"1"` |

### Agent 写 YAML 的正确方式（delegate_task）

Python 脚本中使用 `yaml.dump`：

```python
import yaml, os

items = [{
    "name": "概念名称",
    "file": "概念名称",
    "fm": {
        "source_chapter": "1",
        "source_from": "第1章 1.2.2",
        "confidence": 0.95,
        "confidence_note": "精准释义逐字匹配出处原文"
    },
    "bd": {
        "term_english": "EMC",
        "term_definition": "...",
        "definition_sentence": "从源文逐字复制的定义句",
        # ... 其他模板字段
    }
}]

out_dir = "/path/to/.dag/第1章/data/"
with open(os.path.join(out_dir, "concepts.yaml"), 'w') as f:
    yaml.dump(items, f, allow_unicode=True, default_flow_style=False,
              sort_keys=False, indent=2, width=120)
```

### 写完后必做校验

1. **yaml.safe_load 能解析**：`python3 -c "import yaml; yaml.safe_load(open('file.yaml'))"`
2. **计数检查**：确保没覆盖条目
3. **字段名匹配模板**：对照 [template-yaml-field-map.md](template-yaml-field-map.md) 核对 bd 字段名和等级

## 内容深度要求（减少"无"）

Agent 写每个 YAML 条目时，**必须从源文精读提取内容**填充模板字段。每条目的 bd 字段数与要求见 [template-yaml-field-map.md](template-yaml-field-map.md)（节点类型总表）。

### 核心原则

| 等级 | 要求 | 适用字段举例 |
|:-----|:-----|:------------|
| 🟢 必填 | 从源文逐字提取，不得为"无" | `definition_sentence`(concept), `term_definition`(concept/entity), `answer`(solution), `question`(exercise) |
| 🟡 应填 | 从源文归纳，最多1个节可为"无" | `structure`, `application_scenarios`, `typical_systems`, `related_concepts_relations`, `engineering_practices`, `common_misconceptions`, `solved_problem`, `learning_objectives` |
| 🔴 条件填 | 源文有时填，无则"无" | `mathematical_model`, `formula_references`, `core_concept_map`, `figure_references` |

### 数学模型的强制要求（重要陷阱）

对于 `mathematical_model` 和 `formula_references` 字段：
1. **写前必须扫描源文**：搜索对应容器/节段的 `$$...$$` 及行内 `$...$` 公式。如果源文含公式，**必须**提取。
2. **禁止直接填"无"**：除非确认源文对应节段确实没有任何数学表达式（如纯分类介绍的文本段）。即使是框架性概念（如"电磁干扰三要素"），源文也往往有对应的数学模型。
3. **提取模板**：Agent 必须从源文中复制公式。格式示例：
   ```
   $$E(t,f,r,\theta) = S(t,f,r,\theta) \cdot C(t,f,r,\theta) \cdot R(t,f,r,\theta)$$
   *(来源：第2章 §2.2.1 电磁干扰三要素)*
   ```
4. **公式来源必须精确**：每公式/公式组下方必须标注精确来源定位，**禁止**使用模糊文字如"来源：第N章正文"。格式：
   - 有公式编号：`*(来源：第N章 §X.X 式(2-XX))*`
   - 无公式编号：`*(来源：第N章 §X.X 节标题)*`
5. **Figure 引用**：如果公式以图片形式存在（WMF/EMF），在 `figure_references` 中记录图片编号，在 `mathematical_model` 中用 LaTeX 重写公式并标注 `*(图X-X 公式重写)*`。
6. **典型陷阱案例**：
   - ❌ `电磁干扰三要素` → `mathematical_model: 无`（源文有 S·C·R 乘积模型 ✅）
   - ❌ `公式下方 > 来源：第2章正文` → 过于模糊，应为 `*(来源：第2章 §2.2.1 式(2-XX))*`
   - ❌ `屏蔽效能` → `mathematical_model: 无`（源文有 SE=R+A+B ✅）

### 各节点类型要求速览

| 类型 | bd 字段数 | 最少非"无" | 关键必填字段 |
|:-----|:---------:|:----------:|:-------------|
| concept | 33 | ≥30 | definition_sentence, term_definition, term_english |
| ke | 19 | ≥16 | definition, definition_sentence, source |
| entity | 17 | ≥14 | entity_type, term_definition, definition_sentence |
| kp | 42 | ≥36 | solved_problem, learning_objectives, theoretical_basis |
| sp | 32 | ≥26 | core_operation, skill_objectives |
| scene | 28 | ≥22 | scenario_description, node_descriptions |
| exercise | 5 | ≥4 | question |
| solution | 18 | ≥14 | answer, principle_steps, characteristics, exam_points, common_mistakes, solving_tips, difficulty_1/2 |

**完整字段映射、每字段的等级和填充要求** → [template-yaml-field-map.md](template-yaml-field-map.md)

### KP file 命名特殊规则

KP 的 `file` 字段**禁止**使用 `第N章-知识点N` 格式。必须用知识点中文名（如 `EMC_EMI_EMD基本概念与定义`）。

### Solution 内容深度

Solution（eval_template.md）有 18 个 bd 字段，至少填 14 个：
- ✅ `answer`: 基于源文内容的详细解答
- ✅ `principle_steps`: 解题原理的流程化拆解
- ✅ `characteristics`: 题目涉及的技术特点归纳
- ✅ `exam_points`: 核心考点分析
- ✅ `common_mistakes`: 常见错误
- ✅ `solving_tips`: 解题技巧
- ✅ `difficulty_N_title/content`: 难点解析（至少 2 组）
- ✅ `related_concepts`: 关联知识点
- 练习题部分（图表图等源自源文内容判断是否确实需要）

**禁止**：所有字段均为"待后续AI Agent深度填充"或仅 answer 字段有内容。

### 技能点(SP)和应用场景(Scene)的强制生成

**SP 和 Scene 不可跳过**。DAG 流程要求每章至少 1 个 SP 和 1 个 Scene：

| 章类型 | SP 示例 | Scene 示例 |
|:-------|:--------|:-----------|
| 绪论章 | EMC术语辨析与应用 | EMC初步评估 |
| 技术章 | 分贝制换算、链路预算 | 传导/辐射发射测试 |
| 理论章 | 屏蔽效能估算 | 屏蔽体设计验证 |

**判断逻辑**：只要该章包含足够支撑一个完整操作流程的内容，就必须生成 SP/Scene。
**例外**：仅当该章确实无任何工程操作内容时才允许 SP=0（目前无此类章节）。
## 管道自动工作流（pipeline auto）

完整流程：

1. **chapter_toc**: `preprocess_toc.py` → 自动执行（或 `pipeline done chapter_toc`）
2. **Agent 写 YAML**: 写入 `.dag/第N章/data/{concepts,kes,entities,kps,sps,scenes,exercises,solutions}.yaml`
3. **pipeline auto**: 自动构建 → 检查 → 验证 → 标记 done。注意：**exercises/solutions 由 template_writers.py 自动生成**（非 build_kb_files.py），如果 template_assembler.py 缺少 `__main__` 入口则会静默产生 0 文件。
4. **修复循环**: pipeline auto 可能因 confidence/结构问题失败 → 手动修正 YAML → 回滚失败阶段 → 重新 pipeline auto
5. **indexes**: l2_indices → l3_indices → l4_indices

### pipeline auto 的依赖链

```
chapter_toc → concepts → ke → entities → kp → sp → scene → exercises → solutions → l2/l3/l4
```

如果某阶段需要上游完成才能进行。如果上游阶段 FAIL，必须 `pipeline rollback <phase>` 重置后修复 YAML 再重跑。

### 手动构建（build_kb_files.py）

当 pipeline auto 因 confidence 或其他校验失败时，手动构建参数：

```bash
python3.12 build_kb_files.py --type exercise --chapter 1 \
  --book-id "01_工程电磁兼容" \
  --output-dir "/path/to/book_dir"
```

需要同时提供 `--book-id` 和 `--output-dir`（指向书籍根目录 wr）。之后用 `pipeline done <phase>` 同步状态。

### 回滚阶段

当阶段验证失败需要重新构建时：

```bash
python3.12 dag_controller.py pipeline rollback <phase> \
  -w $BOOK_DIR --book-id 01_xxx -c 1
```

回滚会自动重置该阶段及所有下游依赖阶段。
