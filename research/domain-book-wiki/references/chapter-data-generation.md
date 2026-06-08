# 新章数据生成指南

## 全流程（源文件 → 数据 → 构建）

```
Phase 1: 源文件转换（零 AI 数据，使用 source-prepare 技能）
  .doc/.docx 源文件
    │
    ├── docx-format（标题格式化）
    ├── file2md（→ .md + assets/，保留完整文件名如 第1章 电磁兼容概述.md）
    ├── [可选] container_extract → merge_source
    ├── 复制到 20_正文/（保留完整文件名，勿截断为 第N章.md）+ assets/
    │
    └── preflight.py -w $BOOK_DIR  ← Phase 1 闸门

Phase 1.5: 章节结构预处理（纯脚本，零 AI）
  20_正文/第N章.md
    │
    ├── pipeline auto（自动触发 chapter_toc phase）
    │   └── preprocess_toc.py → .dag/第N章/chapter_toc.json
    │
    └── chapter_toc 标记 done

Phase 2: AI 知识加工（基于自适应容器，逐概念精读）
  核心原则：容器层级由脚本自适应探测（不硬编码 ###），所有内容（图/公式/表/KE）按容器归属。
  Agent 不再一次读全文，改为：

  Step A: 读 chapter_toc.json（~100 行结构化标题索引）
    消耗: ~2K tokens
    产出: 掌握全章节的 `containers[]` 列表、每容器行号范围、`container_level`

  Step B: 对每个容器（或 auto_split 子容器），逐个处理:
    1. read_file(20_正文/第N章.md, offset=line, limit=line_end-line)
       → 只读该容器所属的精准节段（通常 30-200 行）
       → 消耗: ~2K tokens
    2. Agent 在该段中:
       - `$$...$$` → formula_references（容器内公式）
       - `图X-X` → figure_references（容器内插图）
       - `表X-X` → additional_explanations（容器内表格）
       - `XX是指/称为...` → definition_sentence（容器内定义句）
       - `XX定理/XX参数/XX方法` → 知识要素候选（后续 kes.yaml）
    3. [v36.1] **核心概念过滤** — 详见下方 [核心概念过滤标准（附案例）](#核心概念过滤标准附案例)。
       简记：只有同时满足三条才写入 concepts.yaml：篇幅≥50行 + 支撑材料≥3个 + 有展开结构。
       不符合条件的候选 → 不抽为概念，内容归入所属父概念或 KE
    4. 写入 concepts.yaml（追加，只当前概念）
    4. 立即 build: pipeline done concepts
    5. 交叉校验:
       search_files("图X-X", path="30_核心概念/")
       → 检查该图号是否已被已建概念引用
       → 如果发现共享，移除当前概念中的引用
    6. 总消耗/概念: ~12K tokens

  按顺序: concepts.yaml → kes.yaml + entities.yaml → kps.yaml → sps.yaml → scenes.yaml
    │
    ├── validate_chapter_data.py --chapter N --fix
    └── pipeline auto -c N
```

## 核心概念过滤标准（附案例）

### 三条量化标准

一个 `###` 容器只有**同时满足**以下三条才写入 `concepts.yaml`：

| # | 标准 | 阈值 | 理由 |
|:-:|:-----|:----:|:-----|
| 1 | **篇幅** | ≥ 50 行 | 核心概念需要长篇讲解才能让学生掌握 |
| 2 | **支撑材料** | ≥ 3 个 | 公式 + 图 + 表的合计数量，代表概念的"教学密度" |
| 3 | **展开结构** | 有子标题或多段落 | 非一句话定义，有分点详述 |

不满足的候选 → **不写入 concepts.yaml**，内容归入所属父概念或 KE。

### 第3章案例（电磁兼容预测）

#### ✅ 通过（核心概念）

| 候选 | 行数 | 支撑 | 结构 | 原因 |
|:-----|:----:|:----:|:----:|:-----|
| 远场天线模型 | 289 | 72图 | 4子节 | 长篇讲解天线方向图模型，子节详述有意/无意辐射区 |
| 谐波发射模型 | 214 | 12图+19表 | 6子节 | 表格+配图+分段讲解各次谐波 |
| 多导体传输线理论 | 304 | 119图 | 3子节 | 父容器，包含电报方程等子内容 |
| BLT方程 | 258 | 184图 | 3子节 | 父容器，含平行双线/一般形式/算例 |

#### ❌ 否决（KE）

| 候选 | 行数 | 原因 |
|:-----|:----:|:------|
| 干扰裕度 | **1行**(L70) | 一句话定义"IM称为干扰裕度"，无图无公式 |
| 传输损耗 | 零散出现9次 | 无独立 `###` 容器，嵌入"简单预测"节内作为参数讨论 |
| 天线方向图模型 | **0次**出现 | Agent 凭空编造，正文中无此独立章节 |

### 第4章案例（电磁兼容工程方法）

#### ✅ 通过（8 个核心概念）

| 概念 | 行数 | 图 | 支撑 | 节 |
|:-----|:----:|:--:|:----:|:---|
| 纵向扼流圈 | 80 | 104 | 104 | 4.1 接地 |
| 电场屏蔽 | 70 | 55 | 55 | 4.3 屏蔽 |
| 磁场屏蔽 | 108 | 54 | 54 | 4.3 屏蔽 |
| 金属平板屏蔽效能的计算 | 238 | 106+12表 | 118 | 4.3 屏蔽 |
| 非实心型屏蔽体屏效计算 | 94 | 44 | 44 | 4.3 屏蔽 |
| 薄膜屏蔽 | 88 | 6 | 6 | 4.3 屏蔽 |
| 反射滤波器 | 110 | 56 | 56 | 4.4 滤波 |
| 电源线滤波器 | 58 | 96 | 96 | 4.4 滤波 |

#### ❌ 否决（KE）

| 候选 | 行数 | 原因 |
|:-----|:----:|:------|
| 接地的含义和分类 | 10 | 定义级内容，几句话能说清 |
| 单点接地 | 12 | 篇幅仅12行，不够展开 |
| 浮地 | 14 | 同上 |
| 防雷接地 | 4 | 极短小节 |
| 搭接的方法和原则 | 2 | 组织性标题，非教学内容 |
| 滤波器的分类 | 10 | 纯列举分类，无展开讲解 |

### 边界案例

| 候选 | 行数 | 支撑 | 结论 | 说明 |
|:-----|:----:|:----:|:----:|:-----|
| 地阻抗干扰 | 40 | 32图 | ❌ KE | 篇幅差10行，可考虑将父容器扩展后纳入 |
| 多层屏蔽体屏蔽效能计算 | 36 | 26图 | ❌ KE | 同上 |
| 通风孔的屏蔽 | 34 | 18图 | ❌ KE | 同上 |

边界案例的处理：如果父容器合并多个短节后总篇幅 ≥ 50 行，可作为一个综合概念抽取。否则保持 KE。

### 快速验证命令（v36.5 自适应容器版）

```bash
# 对指定章节跑过滤（v36.5 支持 auto_split 容器）
# ⚠️ 将 SRCFILE/TOCFILE 替换为实际路径
SRCFILE="$WIKI_ROOT/20_正文/第N章 电磁兼容概述.md"
TOCFILE="$WIKI_ROOT/.dag/第N章/chapter_toc.json"
python3 -c "
import json, re
src = open('$SRCFILE').read()
toc = json.load(open('$TOCFILE'))
containers = toc.get('containers', toc.get('leaf_nodes', []))
for n in containers:
    if n.get('auto_split'):
        for sub in n['split_into']:
            lc = sub['line_end'] - sub['line'] + 1
            sup = sub.get('support_count', 0)
            tag = '✅' if lc>=50 and sup>=3 else '❌'
            print(f'{tag} L{sub[\"line\"]:>4} {lc:>3}行 sup={sup} {n[\"text\"][:30]}[{sub[\"sub_id\"]}]')
    else:
        lc = n['line_end'] - n['line'] + 1
        sup = n.get('support_count', 0)
        sub_count = n.get('child_count', 0)
        tag = '✅' if lc>=50 and sup>=3 and sub_count>=1 else '❌'
        print(f'{tag} L{n[\"line\"]:>4} {lc:>3}行 sup={sup} {n[\"text\"][:40]}')
"
```

## 源文预处理（完整版）

### Step 1: docx-format（修复标题样式）

```bash
# ⚠️ 跨平台临时目录：macOS/Linux 用 $TMPDIR，Windows 用 %TEMP%
TMP="${TMPDIR:-/tmp}"
python3 ~/.hermes/skills/docx-format/scripts/format_docx.py \
  "第N章 xxx.docx" "$TMP/chN_formatted.docx" --no-ocr
```

### Step 2: file2md（→ .md + assets/）

```bash
python3 ~/.hermes/skills/mlops/file2md/scripts/file2md.py \
  "$TMP/chN_formatted.docx" -o "$TMP/chN_md" --split
```

### Step 3: [可选] OLE 公式提取

```bash
python3 ~/.hermes/skills/research/source-prepare/scripts/container_extract.py \
  "第N章 xxx.docx" -o "$TMP/chN_formulas"

# 仅当 summary.json 中 success > 0 时走此步
python3 ~/.hermes/skills/research/source-prepare/scripts/merge_source.py \
  --md "$TMP/chN_md/第N章"*.md \
  --formulas "$TMP/chN_formulas/latex/summary.json" \
  --assets "$TMP/chN_md/assets" \
  -o "$TMP/chN_merged.md"
```

### Step 4: 复制到 wiki 目录

```bash
WIKI_ROOT="~/Desktop/知识库/01_领域/01_资料库/01_电磁兼容基础"
cp "$TMP/chN_md/第N章"*.md "$WIKI_ROOT/20_正文/"
cp -n "$TMP/chN_md/assets/"* "$WIKI_ROOT/20_正文/assets/" 2>/dev/null
```

## 数据格式：YAML 精确定义

### 概念（concepts.yaml）

⚠️ **`bd` 必须是 YAML 字典，不是 `|` 字面块字符串！**

```yaml
- name: 概念名称                    # 中文全名
  file: 概念名称                     # 短名，无扩展名，无路径
  fm:
    source_chapter: "3"             # 字符串，非数字
    source_from: 第3章 X.X.X
    confidence: 0.95                # 概念固定 0.95
    confidence_note: 精准释义逐字匹配出处原文  # 必填！
  bd:                               # ← 必须是字典
    term_english: English Name
    term_definition: 一句话定义
    source: 出处原文引用
    definition_sentence: 完整定义的精准释义
    definition_source: 来源：第3章 X.X.X
    core_concept_map: |             # Mermaid 在字典内部用 | 块
      flowchart TD
          A[节点1] --> B[节点2]
    core_concept_map_source: 无
    core_concept_map_analysis: 图解析说明
    additional_explanations: 补充说明
    formula_references: |           # 公式在字典内部用 | 块
      $$E = \frac{1}{2} m v^2$$
    figure_references: 无
    structure: 结构说明
    mathematical_model: 无
    tech_classification: 无
    application_scenarios: 无
    typical_systems: 无
    related_concepts_relations: 无
    confusion_compare: 无
    evolution: 无
    engineering_practices: 无
    common_misconceptions: 无
    references: 无
    related_knowledge_elements: 无
```

**`bd` 不能是 `|` 块字符串**的原因：`assemble_md()` 做 `{{field}}` 替换时，期望每个字段是独立字符串。如果 `bd` 整个是 `|` 块，所有 `{{formula_references}}`、`{{core_concept_map}}` 等占位符不会被替换，生成的内容全空。

#### ⚠️ `definition_sentence` 的精确匹配要求（频繁踩坑）

C7 quality gate 要求 `definition_sentence` 同时满足两个条件，否则 `blocked`：

**条件 1 — 源文可检索**：前 120 字符必须是 `20_正文/` 中的 **连续原文子串**
  - ✅ 正确：复制单段完整句 `"传导耦合是指通过导体传输的电磁干扰。当电磁干扰源的波长远大于敏感源的线度时..."`（取自 line 360 连续文本）
  - ❌ 错误：拼接两段 `"电磁屏蔽技术是...。传统单一材料..."`（两段中间隔了其他文字和新行）
  - ❌ 错误：改写或概括 `"传导耦合是通过导体传递干扰信号的耦合方式"`（不是原文）

**条件 2 — 定义标记词**：前 120 字符必须包含 `是指`/`称为`/`即`/`是` 之一
  - ✅ `"电磁散射的实质是电磁波在媒质不均匀处产生的二次或多次辐射。"`（含 `是`）
  - ❌ `"在两种媒质的分界面上，电磁场必须满足一定的边界条件。"`（无标记词）

**特殊注意事项**：
- **引号字符必须完全一致**：源文用中文弯引号 `\u201c...\u201d`（如 `"低频"`），YAML 中必须用相同 Unicode 字符，不能用 ASCII 直引号 `"`（U+0022）。YAML 字符串中无法直接用转义写中文弯引号，建议用 raw string 或 Python unicode escape `\u201c` / `\u201d`。
- **不能跨段落**：源文件中段落之间的空白行、图片引用标记等都会打断连续检索。即使两个句子分别存在，中间有其他内容时也不能拼接。
- **首句优先原则**：优先使用源文中的首句（含有 `是` 的句子），长度不够时可追加同段的后续句。

### 知识要素（kes.yaml）

```yaml
- name: 知识要素名称
  file: 知识要素名称
  fm:
    source_chapter: "3"
    source_from: 第3章 X.X.X
    confidence: 0.85
    confidence_note: 基于正文内容归纳生成
  bd:
    definition: 一句话定义
    classification: 分类列表
    structure: |
      **核心公式**：
      $$IM = P_I - S_I$$
    key_parameters: 关键参数
    features: 特征描述
    application_scenarios: 应用场景
    value: 工程价值
    upstream_downstream: 无
    related_knowledge_elements: 无
    references: 无
    source: 出处原文
    domain: 电磁兼容
```

### Agent 写 YAML 的两种方式

❌ **不要** 用 `patch` / `write_file` 手搓 YAML 字符串。反斜杠转义、YAML 缩进、`|` 块边界的细微错误极难排查。

✅ **用 Python 写** — 代理可以在 `delegate_task` 中使用 `terminal("python3 -c \"...\"")` 或写一个临时 `.py` 脚本，调用 `yaml.dump()`：
```python
import yaml
items = [{"name": "...", "bd": {...}}, ...]
# 追加到现有文件
with open("path.yaml", "r") as f:
    existing = yaml.safe_load(f) or []
existing.extend(items)
with open("path.yaml", "w") as f:
    yaml.dump(existing, f, allow_unicode=True, default_flow_style=False,
              sort_keys=False, indent=2, width=120)
```
用 `patch` 追加 YAML 的替代方案：读取 YAML 文件 → `yaml.safe_load` → 修改 Python dict → `yaml.dump` 写回。

⚠️ **注意**：`yaml.dump` 输出的对齐、换行、缩进与手写不同，但只要 `yaml.safe_load` 能解析回来就是正确的。

## 并行生成策略：Agent 输出质量要求

| 代理 | 文件 | 条目上限 | 置信度 |
|:----|:-----|:--------:|:------:|
| 概念 | concepts.yaml | **max 9** | 0.95 |
| 知识要素 | kes.yaml | **max 13** | 0.85 |
| KP+SP+Scene | kps.yaml+sps.yaml+scenes.yaml | KP≤7, SP≤2, Scene≤1 | 0.85/0.75/0.65 |

### Agent prompt 的硬约束

`delegate_task` 的 `context` 中必须明确：

1. **YAML `bd` 必须是字典** — 不是 `|` 块字符串。每个模板字段独立一行，公式/图字段内部再用 `|` 块
2. **`fm` 必须包含 `confidence_note`** — 概念"精准释义逐字匹配出处原文"，其他"基于正文内容归纳生成"
3. **`file` 是短名** — 纯中文，无 `.md`，无路径
4. **`source_chapter` 是字符串 `"3"`** — 不是数字
5. **概念 ≤ 9 个** — 只提取最核心的，子主题归入 KE
6. **输出正确 YAML 示例** — 在 context 中嵌入一个完整条目作为范文
7. **模板字段名必须精确匹配** — Agent 提示词中的 bd 字段名必须与模板 `{{变量}}` 完全一致。⚠ 先用 `grep -o '{{[^}]*}}' assets/templates/<type>.md | sort -u` 获取正确字段名，不要凭记忆猜测。SP/Scene 字段名极易写错（如 `skill_description` 应为 `skill_objectives`，`scene_type` 应为 `scenario_type`）。完整对照表见 `references/yaml-field-mapping.md`。

### 常见错误表

| 错误模式 | 后果 | 检测方法 |
|:---------|:-----|:---------|
| `bd: |` 块字符串（概念） | build 成功但 `{{field}}` 全空 | `validate_chapter_data.py` |
| `file` 含扩展名 | build 文件名异常 | `validate_chapter_data.py` |
| `source_chapter: 3` 数字 | yaml.load 读为 int，类型不匹配 | `validate_chapter_data.py` |
| 概念数 > 9 | 内容膨胀，子主题混杂 | `validate_chapter_data.py` 告警 |
| 缺失 `confidence_note` | build 报 KeyError | `validate_chapter_data.py` |
| **definition_sentence 非源文连续文本** | 前 120 字不在 20_正文/ 中可检索 → quality gate blocked | pipeline done 中的 C7 检测 |
| **definition_sentence 缺标记词** | 前 120 字不含 是指/称为/即/是 → quality gate blocked | pipeline done 中的 marker_word 检测 |
| **引号字符不匹配** | 中文弯引号 vs ASCII 直引号导致检索失败 | 手工检查；Python print(repr(text)) 查看 Unicode |
| **bd 字段名不匹配模板** | 占位符不替换 → `{{xxx}}` 残留 | 构建后 grep `{{` 检查，或 `grep -o '{{[^}]*}}' templates/<type>.md` 核对 |

| **bd 字段名不匹配模板** | v52.3 新增 pipeline 字段校验，pipeline auto 检测到新 YAML 时自动警告 | 运行 pipeline auto 时看 `[字段校验/...]` 警告 |
| **Agent 提示词中的字段名必须引用 `references/yaml-field-mapping.md`** | bd 字段名是 YAML ↔ 模板的契约，写错则所有 {{xxx}} 不替换 | 写作前 `grep -o '{{[^}]*}}' assets/templates/<type>.md` 确认 |


## 构建前验证

```bash
# 验证 + 自动修复
python3 scripts/validate_chapter_data.py --chapter 3 --fix

# 无问题后构建
python3 scripts/build_kb_files.py --type concept --chapter 3
python3 scripts/build_kb_files.py --type ke --chapter 3
python3 scripts/build_kb_files.py --type kp --chapter 3
python3 scripts/build_kb_files.py --type sp --chapter 3
python3 scripts/build_kb_files.py --type scene --chapter 3
```

## 关键约束清单

1. YAML `|` 后继行缩进 2 格
2. Mermaid 图禁止 classDef/class
3. wikilink：必须带目录前缀，格式 `[[前缀/文件名|显示名]]`。前缀对照：
   - 核心概念 → `30_核心概念/`
   - 知识要素(KE) → `40_知识要素/`
   - 知识点(KP) → `50_知识点/`
   - 技能点(SP) → `60_技能点/`
   - 应用场景(Scene) → `70_应用场景/`
   - 实体 → `80_实体/`
   - 习题 → `90_习题/`
   - 习题解答 → `90_习题/解答/`
   ⚠ 常见错误：不加前缀的裸 wikilink `[[概念名]]` 在解答/子目录中无法正确解析；误用 `30_知识要素/` 等错误前缀。解决方案 `build_kb_files.py` 中 `related_concepts` 字段不使用裸 wikilink——Agent 写 YAML 时必须写带前缀的完整路径。
4. 概念精准释义用 `> ` blockquote
5. 置信度：概念 0.95、KE 0.85、KP 0.85、SP 0.75、Scene 0.65
6. **`bd` 是字典**，公式/图字段在内部才用 `|` 块
7. **构建前运行 `validate_chapter_data.py --fix`**
8. **手动构建后需 `pipeline done <phase>` 同步状态**：用 `build_kb_files.py` 手动构建后，pipeline 状态不会自动更新。需逐个 `pipeline done concepts / ke / entities / kp / sp / scene` 同步。整书构建优先使用 `pipeline auto`。
9. **骨架解答 confidence 需手动修复**：自动回退生成的骨架解答（solutions.yaml 缺失时）confidence=0.5，但 eval_template.md (quality_key=eval/solution) 允许值仅 {0.65, 0.85}。需手动修改 `90_习题/解答/*.md` 中的 confidence 值，或直接提供 solutions.yaml。
10. **习题/解答 file 命名规范 (v50.0)**：`file` 字段必须使用 `第N章-习题N` 格式（章与习题间有连字符 `-`）。示例：`第3章-习题1`、`第7章-习题12`。解答文件命名：`第N章-习题N-解答`。禁止使用 `第N章习题N-题目描述` 等非标准格式。`build_kb_files.py` 会在构建时自动标准化，`yaml_pre_validate.py` 会对非标准命名发出 warning。
