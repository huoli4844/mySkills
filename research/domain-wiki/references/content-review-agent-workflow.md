# 内容深度 Agent 二次审核工作流

> v50.7: 机械检查 PASS 后的教学质量评审

## 工作流

```
pipeline review -w $BOOK_DIR --book-id XX -c N
    ↓
扫描 30_核心概念/ 50_知识点/ 60_技能点/ 70_应用场景/
提取关键节段 + 统计指标 + A/B/C/D 分层
    ↓
输出 .dag/第N章/review_batch.json
```

## review_batch.json 结构

```json
{
  "book_id": "01_emc",
  "chapter": "4",
  "wiki_root": "/path/to/book",
  "summary": {"total": 18, "A": 2, "B": 8, "C": 5, "D": 3},
  "files": [
    {
      "name": "电场屏蔽",
      "file": "电场屏蔽.md",
      "type": "concept",
      "phase": "concepts",
      "stats": {
        "lines": 84,
        "wu_count": 2,
        "wikilinks": 6,
        "tier": "B"
      },
      "sections": {
        "mathematical_model": "$$SE = R + A + B$$",
        "theoretical_basis": "屏蔽效能由反射损耗R、吸收损耗A和多次反射修正B组成...",
        "theoretical_basis_body": "当电磁波入射到金属屏蔽体时，在空气-金属界面产生反射...",
        "application_scenarios": "无",
        "engineering_practices": "机箱屏蔽设计、电缆屏蔽层接地"
      }
    }
  ]
}
```

## 质量分层定义

| 层级 | 条件 | 含义 | 操作 |
|:-----|:-----|:-----|:-----|
| **A** | wu≤3, lines≥250, wikilinks≥10 | 金标 | 无需操作 |
| **B** | wu≤7, lines≥130 | 达标 | 可选增强 |
| **C** | wu 8-12 | 偏弱 | Agent 精读源文后补充关键节段 |
| **D** | wu≥13 | 空壳 | Agent 从源文完整重填 |

## Agent 评审流程

### Step 1: 读取 review_batch.json

```bash
cat .dag/第N章/review_batch.json
```

关注 `summary.D` 和 `summary.C`。

### Step 2: 对每个 D-tier / C-tier 文件

#### 2a: 阅读 review_batch.json 中该文件的 `sections`

- 哪些节段是"无"或极短？
- 哪几个字段需要补充？

#### 2b: 从源文找到对应概念

```bash
SOURCE_FILE="20_正文/第N章 XXXX.md"
grep -n "概念名称" "$SOURCE_FILE" | head -5
```

#### 2c: 读取源文对应段落（行号范围从 chapter_toc.json 或 grep 定位）

```bash
read_file("$SOURCE_FILE", offset=120, limit=80)
```

#### 2d: 精读后填充 YAML bd 字段

```python
import yaml, os
BOOK_DIR = "/path/to/book"
ch = "N"
yaml_path = os.path.join(BOOK_DIR, f".dag/第{ch}章/data/concepts.yaml")
with open(yaml_path) as f:
    data = yaml.safe_load(f)
for item in data:
    if item["name"] == "电场屏蔽":
        item["bd"]["mathematical_model"] = "$$SE = R + A + B$$"
        item["bd"]["application_scenarios"] = "- 机箱屏蔽\\n- 电缆屏蔽\\n- 窗口屏蔽"
with open(yaml_path, "w") as f:
    yaml.dump(data, f, allow_unicode=True, default_flow_style=False,
              sort_keys=False, indent=2, width=120)
```

### Step 3: 重新构建

```bash
dag_controller.py pipeline auto -w $BOOK_DIR --book-id $BOOK_ID -c N
```

### Step 4: 验证

```bash
dag_controller.py pipeline review -w $BOOK_DIR --book-id $BOOK_ID -c N
# 确认 D-tier 数减少或消失
```
