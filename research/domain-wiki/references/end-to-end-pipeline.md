# 知识库构建全流程（工程 vs 内容分工明细）

> v50.7 — 每步标记 `🖥️ 脚本` 或 `🤖 Agent`

## 概览

```
Phase 0: 环境预检       🖥️
Phase 1: 源文件转换      🖥️
Phase 1.5: TOC 预处理   🖥️
Phase 2: YAML 数据生成   🤖（写内容）+ 🖥️（机械填充+字段校验）
Phase 3-7: 文件构建     🖥️
Phase 8: 习题解答        🖥️ + 🤖
Phase 9: 质量验证       🖥️（格式）+ 🤖（内容二审）
Phase 10: 索引生成      🖥️
Phase 11: 全书构建      🖥️（编排）+ 🤖（修复循环）
```

---

## Phase 0: 环境预检 `🖥️ 脚本`

| 步骤 | 脚本 | 说明 |
|:-----|:-----|:------|
| 0.1 | `preflight.py` | 检查工作区目录结构是否完整，20_正文/ 是否存在，.dag/ 下是否有 YAML（防止覆盖） |
| 0.2 | `pipeline init` | 初始化 `.dag/{book_id}_ch{N}.json` 状态文件，创建全部输出目录 |

**输入**：教材目录路径、book_id、章节号
**输出**：状态文件、输出目录树
**耗时**：< 1秒
**失败处理**：目录不完整 → 拒绝启动

---

## Phase 1: 源文件转换 `🖥️ 脚本`

| 步骤 | 脚本 | 说明 |
|:-----|:-----|:------|
| 1.1 | `file2md.py` | .docx 转 .md，保留标题层级、图片(WMF/EMF/PNG)、表格、公式图片 |
| 1.2 | `docx-format` | 可选：修复标题编号样式 |
| 1.3 | `container_extract.py` | 可选：从 Word OLE 对象提取公式→LaTeX |
| 1.4 | `merge_source.py` | 可选：将公式 LaTeX 合并回 .md |
| 1.5 | `cp` | 复制 .md 到 `20_正文/`，保留完整文件名如 `第1章 电磁兼容概述.md` |

**输入**：.docx 源文件
**输出**：`20_正文/第N章 标题.md` + `20_正文/assets/`（图片）
**耗时**：每章 1-3 分钟（取决于 OLE 提取）
**失败处理**：file2md 失败 → `preflight` 阻断

---

## Phase 1.5: TOC 预处理 `🖥️ 脚本`

| 步骤 | 脚本 | 说明 |
|:-----|:-----|:------|
| 1.5.1 | `preprocess_toc.py` | 扫描 `20_正文/第N章.md`，提取 ### 标题结构，统计每容器行数、支撑材料数(图+公式+表) |

**输出**：`.dag/第N章/chapter_toc.json`
```json
{
  "containers": [
    {"text": "远场天线模型", "line": 100, "line_end": 389,
     "line_count": 289, "support_count": 72, "child_count": 4,
     "level": 3}
  ]
}
```

**耗时**：< 1 秒

---

## Phase 2: YAML 数据生成 `🤖 Agent` + `🖥️ 脚本`

**这是最关键的阶段**，严格按"脚本做工程、Agent 做内容"分工。

### 2.0 骨架生成 `🖥️ 脚本`

| 步骤 | 说明 |
|:-----|:------|
| `yaml_auto_fill.py skeleton -t concept -n "名称" -c 1` | 从模板文件提取 `{{xxx}}` 占位符 → 生成完整 YAML 骨架（所有字段预填"待补充"） |
| `yaml_auto_fill.py fill -w $DIR -t concept -c 1` | 机械填充 meta/auto/derived 字段：confidence, bloom_level, source_chapter, source_from, difficulty 等（共 ~48% 的字段） |

**效果**：Agent 不需要手写 metadata 字段，只需填充剩余的 ~52% 内容字段。

### 2.1 容器判断 → 核心概念/KE/实体 `🤖 Agent`

| 步骤 | 执行者 | 说明 |
|:-----|:-------|:------|
| 读 `chapter_toc.json` | 🤖 Agent | 掌握全章容器列表、每容器的行号范围、支撑材料数 |
| 逐容器精读源文（30-200 行） | 🤖 Agent | `read_file("20_正文/第N章.md", offset=line, limit=length)` |
| 三标准过滤 | 🤖 Agent | 判断：篇幅≥50行？支撑≥3？有展开结构？**注意：这三个是必要条件，不是充分条件。真正决定"是否值得抽成概念"需语义理解** |
| 不符合条件的内容 | 🤖 Agent → 降级 | 归入父概念以 KE 形式收录，或作为源文保留不抽取 |
| 写入 YAML | 🤖 Agent + 🖥️ | Agent 填充内容字段；Python 通过 `yaml_auto_fill.py skeleton` 补元字段 |
| **字段名校验** | 🖥️ `yaml_pre_validate.py` | **v50.7 新增**：自动比对 `bd` 键名 vs 模板 `{{xxx}}` → 报告不识别字段和缺失字段 |

**输出**：按 DAG 顺序逐个写入：
1. `concepts.yaml` — 核心概念（≤9 个/章，confidence=0.95）
2. `kes.yaml` — 知识要素（≤13 个/章，confidence=0.85）
3. `entities.yaml` — 实体（设备/组织/标准，confidence=0.85）

### 2.2 定义句设置 `🤖 Agent`

| 条件 | 操作 |
|:-----|:------|
| 源文含 "是指/称为/即/就是" 标记词 | Agent 逐字复制含标记词的连续句子（≤120 字符） |
| 引号字符必须完全一致 | 中文弯引号 `\u201c\u201d` 不能写成 ASCII `"` |
| 不能跨段落拼接 | 必须是单段连续正文子串 |

### 2.3 概念图/公式/图引用 `🤖 Agent`

| 字段 | 角色 | 说明 |
|:-----|:-----|:------|
| `core_concept_map` | 🤖 Agent | 手写 Mermaid 流程图展示概念内部结构 |
| `mathematical_model` | 🤖 Agent | 从源文提取或视觉解读 WMF 图片 → LaTeX |
| `formula_references` | 🤖 Agent | 列出本概念相关的公式编号 |
| `figure_references` | 🤖 Agent | 列出本概念相关的图号（注意：不能跨概念共享） |

### 2.4 知识点(KP) / 技能点(SP) / 场景(Scene) 生成 `🤖 Agent`

按 DAG 顺序：concepts → ke → kp → sp → scene

| 类型 | 核心判断 | 关键字段 |
|:-----|:---------|:---------|
| KP | 整合 1+ 概念的可教学单元 | `theoretical_basis`, `key_details`, `derivation_analysis`, `application_scenarios` |
| SP | 知识→动手能力的方法 | `core_operation`, `operation_flow_analysis`, `typical_practical_cases` |
| Scene | 多知识综合解决真实问题 | `scene_elements`, `node_descriptions`, `solution_detail`, `boundary_conditions` |

### 2.5 习题检测与解答骨架 `🖥️ 脚本 + 🤖`

| 步骤 | 执行者 | 说明 |
|:-----|:-------|:------|
| 习题自动检测 | 🖥️ `extract_exercises_from_text()` | 从 20_正文/ 扫描 "习题/思考题" 节段 → 自动生成 `exercises.yaml` |
| 解答自动配对 | 🖥️ `verify_exercise_solution_mapping()` | 1:1 配对，自动生成 `solutions.yaml` 骨架 |
| 解答内容填充 | 🤖 Agent | 填充答案详解、解题流程图、知识闭环分析 |

---

## Phase 3-7: 文件构建 `🖥️ 脚本`（全自动，零 Agent）

| 步骤 | 脚本 | 说明 |
|:-----|:-----|:------|
| `build_kb_files.py --type concept` | 🖥️ | 读 `concepts.yaml` → `fill_template()` 替换 `{{xxx}}` → 原子写入 `30_核心概念/名称.md` |
| `build_kb_files.py --type ke` | 🖥️ | 同上 → `40_知识要素/` |
| `build_kb_files.py --type kp` | 🖥️ | 同上 → `50_知识点/` |
| `build_kb_files.py --type sp` | 🖥️ | 同上 → `60_技能点/` |
| `build_kb_files.py --type scene` | 🖥️ | 同上 → `70_应用场景/` |
| `build_kb_files.py --type exercise` | 🖥️ | 同上 → `90_习题/` |
| `build_kb_files.py --type solution` | 🖥️ | 同上 → `90_习题/解答/` |

**关键工程机制**：
- `load_template()` → `parse_template()` → `fill_template()`（`template_assembler.py` + `template_writers.py`）
- 原子写入：`tempfile.mkstemp()` → `os.replace()`（防断电数据损坏）
- 缺失字段统一填"无"（不保留 `{{placeholder}}`）
- HTML 注释剥离（`<!-- Agent提示 -->` 不输出到文件）

---

## Phase 8: 质量验证 `🖥️ 脚本（格式）+ 🤖 Agent（内容）`

### 8.0 构建后自动修复 `🖥️ 脚本`

| 步骤 | 脚本 | 说明 |
|:-----|:-----|:------|
| `post_build_fix.py` | 🖥️ | 自动修复公式独占三行、图引用路径、Mermaid init 配置 |

### 8.1 四重质量闸门 `🖥️ 脚本`

| 闸门 | 脚本 | 检查项 |
|:-----|:-----|:-------|
| L1: 格式 | `yaml_pre_validate.py` | schema/confidence/bloom_level/定义句标记词/字段名匹配 |
| L2: 内容 | `content_check_rules.py` | 公式格式/Mermaid 语法/wikilink 断裂/字段字数阈值 |
| L3: 渲染 | `validate_render.py` | Mermaid 可解析/LaTeX 括号平衡/图引用可解析 |
| L4: 综合 | `quality_score.py` | 0-100 评分 + L2/L3/L4 索引覆盖率 |

任意闸门 FAIL → `blocked`（状态文件中 `status: blocked`）

### 8.2 质量闸门自动修复循环 `🖥️ 编排 + 🤖 修复`（v50.7 新增）

```
pipeline batch --retry 3
  ↓
逐章 pipeline auto
  ↓
┌─ PASS → next chapter ───────────────────────────────────┐
│                                                          │
└─ FAIL → _auto_fix_blocked_phases():                      │
           Step 1: content_check_rules 扫描格式问题 🖥️       │
           Step 2: post_build_fix 机械修复 🖥️                │
           Step 3: retry pipeline auto 🖥️                   │
              ↓ 重试用尽                                     │
           collect_fix_report() → fix_report.json 🖥️        │
              ↓                                             │
           Agent 读报告 → 分析错误日志 → 找源文 → 修 YAML → 重 build 🤖→🖥️ → PASS ──┘
```

### 8.3 内容深度二次审核 `🖥️ 扫描 + 🤖 评审`（v50.7 新增）

| 步骤 | 执行者 | 说明 |
|:-----|:-------|:------|
| `pipeline review -w $DIR --book-id XX` | 🖥️ | 扫描生成的全部 .md，提取关键节段，统计"无"密度+行数+wikilink |
| A/B/C/D 分层 | 🖥️ | `_tier_from_stats()`: wu≥13=D, wu≥8=C, wu≤7+baselines=B, 金标=A |
| 输出 `review_batch.json` | 🖥️ | 含每个文件的 stats + sections 内容片段 |
| D-tier/C-tier 修复 | 🤖 Agent | 精读源文 → 填充 YAML bd 内容字段 → 重 build |

---

## Phase 9: 索引生成 `🖥️ 脚本`（全自动）

| 步骤 | 脚本 | 说明 |
|:-----|:-----|:------|
| L2 单书总揽 | `index_assembler.py` | `10_总揽/book_overview_{book_id}_0.md` |
| L3 领域总控 | `index_assembler.py` | `领域总控/` 跨书统计 |
| L4 知识库总控 | `index_assembler.py` | `知识库总控/` 全库顶层视图 |
| 知识图谱 | `kb_graph.py build` | 从 .md 构建 SQLite 节点+边图 |
| 跨章一致性 | `pipeline_insights.py` | 跨章同名概念冲突检测 |

---

## Phase 10: 全流程一键编排 `🖥️ 脚本`

| 命令 | 说明 |
|:-----|:------|
| `pipeline auto -w $DIR -c N` | 单章全流程：build→check→validate→索引 |
| `pipeline batch -w $BOOK_DIR --retry 3` | **全书批量（v50.7 自动章节发现）**：扫描 20_正文/ → 逐章 pipeline auto |
| `pipeline batch --from-chapter 5` | 断点续传：从第 5 章开始 |
| `pipeline batch --no-cache` | 禁用 SHA256 增量缓存，强制全量重建 |

---

## 分工总表

```
阶段                         脚本    Agent    说明
─────────────────────────────────────────────────────
Phase 0: 环境预检             ✅     —        preflight 检查
Phase 1: 源文件转换           ✅     —        file2md 格式转换
Phase 1.5: TOC 预处理         ✅     —        preprocess_toc 扫描容器
Phase 2: YAML 骨架生成        ✅     —        yaml_auto_fill skeleton/fill
Phase 2: 三标准过滤(概念/KE)   —     ✅       需要语义理解
Phase 2: 定义句提取            —     ✅       需要判断哪句是定义
Phase 2: 概念图/公式/图引用    —     ✅       需要教学质量
Phase 2: KP/SP/Scene 内容     —     ✅       需要教学叙述能力
Phase 2: 字段名校验           ✅     —        yaml_pre_validate 模板比对
Phase 2: 习题自动检测          ✅     —        正则扫描20_正文/
Phase 3-7: 文件构建           ✅     —        build_kb_files 全自动
Phase 8: 格式质量闸门         ✅     —        4 层机械检查
Phase 8: 自动修复循环         ✅     ✅       脚本编排+Agent修复YAML
Phase 8: 内容深度审核          ✅     ✅       脚本扫描+Agent评审D-tier
Phase 9: 索引生成             ✅     —        index_assembler 全自动
Phase 10: 全书编排            ✅     —        pipeline batch 一键
```

## 关键数字

| 指标 | 数值 |
|:-----|:-----|
| 每章典型总耗时（含 Agent 写 YAML） | 15-30 分钟（Agent 写）+ 2 分钟（脚本构建+校验） |
| 每章生成文件数 | 概念≤9 + KE≤13 + 实体≤5 + KP≤7 + SP≤3 + Scene≤2 + 习题≈12 |
| 单文件行数 | 概念 8KB~15KB，KP 8KB~12KB，SP 6KB~10KB，Scene 7KB~12KB |
| 脚本文件 | 48 个 .py，~22K 行 |
| Agent 填充比例 | YAML 内容字段 ~52%，元字段 48% 由 yaml_auto_fill 自动填 |
| 重试机制 | `--retry N` 机械修复；N 次后用尽 → fix_report.json → Agent 手动修复 |
