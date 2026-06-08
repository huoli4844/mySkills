# 质量审查 + Agent驱动修复流程 (v2.0)

> 核心设计原则：**质量审查的输出是给Agent消费的，不是给人看的。** Agent必须能从结构化输出中解析出"哪个文件、哪个字段、缺多少字、从哪里找源文"，然后自动委托修复。

## 架构

```
┌──────────────────────────────────────────────────────────┐
│ quality_reviewer.py (v2.0)     ← 审查引擎                │
│  ├── T1: 结构完整性（YAML字段/{{xxx}}/@prompt/Mermaid）  │
│  ├── T2: 内容深度（字段填充率/最小长度/bloom_level）     │
│  └── T3: 交叉验证（wikilink/跨类型引用）                 │
│                                                          │
│  输出模式:                                                │
│    默认 → format_report() 人类可读                        │
│    --json → build_json_output() 结构化JSON供Agent消费    │
│    fix-manifest → build_fix_manifest() 文件级修复指令    │
└──────────────────────────────────────────────────────────┘
         │
         ▼ (--json 输出样例)
┌──────────────────────────────────────────────────────────┐
│ JSON fix_manifest 结构:                                   │
│ [                                                         │
│   {                                                        │
│     "file": "电容性耦合",                                   │
│     "type": "concept",                                     │
│     "score": 0.84,                                         │
│     "yaml_path": ".dag/第3章/data/concepts.yaml",          │
│     "fields_to_fix": [                                     │
│       {"field":"term_definition",          "action":"enrich", "current_len":31, "target_len":80}, │
│       {"field":"application_scenarios",    "action":"enrich", "current_len":43, "target_len":50}, │
│       {"field":"learning_objectives",      "action":"enrich", "current_len":55, "target_len":80}, │
│     ]                                                      │
│   }, ...                                                   │
│ ]                                                          │
└──────────────────────────────────────────────────────────┘
         │
         ▼ (Agent解读fix_manifest)
┌──────────────────────────────────────────────────────────┐
│ Agent 驱动修复循环:                                        │
│                                                          │
│  Step 1: 解析JSON fix_manifest                            │
│  Step 2: 对每个低分文件，委托子Agent修复                   │
│          传给子Agent: YAML路径 + 源文目录 + 具体字段问题  │
│  Step 3: 子Agent读取源文，重写YAML对应字段                │
│  Step 4: pipeline_v2 review-fix --re-render --apply       │
│          重新渲染 + 质量门 + 重新审查                     │
│  Step 5: 如果仍有低分文件，回到Step 2                    │
└──────────────────────────────────────────────────────────┘
```

## 关键设计决策

### 为什么输出JSON而非文本报告？

质量审查的输出不是给人看的报告——Agent需要从结构化输出中直接知道：
- **文件级**：哪个YAML文件分数低
- **字段级**：哪个字段不够深（当前字数 vs 目标字数）
- **修复指令**：enrich（扩充）还是 fill（填充）
- **上下文**：YAML路径、源文目录

Agent 收到以下指令即可精确委托修复：
```
FIX_FILE: /path/to/.dag/第3章/data/concepts.yaml
FIX_TYPE: concept
FIX_NAME: 电容性耦合
FIX_ENRICH: term_definition: 31→80字; learning_objectives: 55→80字
FIX_FILL: engineering_practices (空字段)
FIX_SOURCE_DIR: /path/to/20_正文
```

### 为什么 `--threshold` 和 `--fix-threshold` 分离

两个阈值服务于不同目的：

| 参数 | 作用 | 默认值 | 说明 |
|:----|:-----|:-------|:-----|
| `--threshold` | exit阻断阈值 | 0.5 | 全书评分低于此则pipeline exit 1。用于CI门禁 |
| `--fix-threshold` | 修复清单阈值 | 0.8 | 文件评分低于此则列入fix_manifest。用于内容精益 |

典型用法：
```bash
# pipeline内部调用：
quality_reviewer.py chapter \
  --threshold 0.01 \        # 从不exit阻断
  --fix-threshold 0.9       # 高质量目标
```

### 为什么fix_manifest基于文件级评分

类型级均分掩盖局部问题。例如：
- concept 类型评分 0.85（看起来不错）
- 但其中某些文件只有 0.70（概念定义太短）

所以 `build_fix_manifest()` 不检查类型级阈值，直接检查每个文件的 `file_scores`。

## CLI 用法全览

### quality_reviewer.py

```bash
# 单章审查 + JSON输出（含fix_manifest）
quality_reviewer.py chapter \
  --book-dir /path --book-id 01_ID -c 3 \
  --json --fix-threshold 0.9

# 全书审查 JSON
quality_reviewer.py book \
  --book-dir /path --book-id 01_ID --json

# 生成修复清单（Agent消费）
quality_reviewer.py fix-manifest \
  --book-dir /path --book-id 01_ID -c 3 \
  --threshold 0.9 --json --output fix.json

# 生成修复指令到stdout（FIX_FILE/FIX_FIELDS格式）
quality_reviewer.py fix-manifest \
  --book-dir /path --book-id 01_ID -c 3 \
  --threshold 0.9
```

### pipeline_v2.py

```bash
# 单章审查 + JSON
pipeline_v2.py review --book-dir . --book-id 01_ID -c 3 \
  --json --fix-threshold 0.9

# 审查+修复指令输出
pipeline_v2.py review-fix --book-dir . --book-id 01_ID -c 3 \
  --threshold 0.9

# 修复清单保存到文件
pipeline_v2.py review-fix --book-dir . --book-id 01_ID -c 3 \
  --threshold 0.9 --output fix.json

# Agent修复后重新渲染+审查
pipeline_v2.py review-fix --book-dir . --book-id 01_ID -c 3 \
  --re-render --apply

# 自动按序处理（含quality_review/auto_fix阶段）
pipeline_v2.py run --book-dir . --book-id 01_ID -c 3 --book-name "书名"
```

## DAG阶段集成

dag_state.py 新增两个阶段：

| 阶段 | index | 依赖 | 说明 |
|:----|:-----|:------|:------|
| quality_review | 9 | 全部Phase A产出 | 运行质量审查，生成fix_manifest。成功即标记done |
| auto_fix | 10 | quality_review | 如果quality_review发现低分文件，此阶段标记为pending等待Agent操作。Agent修复后手动标记为done |

run命令输出示例：
```
▶ 执行阶段: quality_review
  审查: score=0.95, 13个文件需修复
  写入状态: quality_review=done, auto_fix=pending

▶ 执行阶段: auto_fix
  等待Agent修复YAML
  指令: 解读FIX指令 → 委托子Agent → pipeline_v2.py review-fix --re-render --apply
```

## Agent 委托修复子任务模板

当 Agent（Hermes）从 review-fix 输出解析到修复清单后，按类型批量委托：

```
对于每个低分的 concept 文件：
  委托子Agent：
    goal: "修复YAML文件中的字段"
    context: |
      YAML路径: {yaml_path}
      文件: {file} ({type})
      源文路径: {source_dir}/第{chapter}章.md
      
      需要修复的字段:
        - term_definition: 当前31字 → 目标80字 (扩充)
        - learning_objectives: 当前55字 → 目标80字 (扩充)
      
      请读取源文对应段落，重写YAML对应字段。
      用 yaml.dump() 写入，保持原有结构不变。
    工具: [terminal, file]
```

典型子Agent修复指令产出：
- 读取现有 YAML → 定位到待修字段
- 读取源文 → 找到相关段落
- 重写字段（扩充或填充）
- 写入YAML（yaml.dump, allow_unicode=True, default_flow_style=False）
- 验证YAML语法（yaml.safe_load）
