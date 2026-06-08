# 质量闸门自动修复 Agent 工作流

> v50.7: 新增结构化错误报告 + Agent 驱动修复循环

## 工作流概览

```
pipeline batch --retry N
  ↓
逐章执行 pipeline auto
  ↓
┌─ 质量闸门 PASS → 下一章 ─────────────────────┐
│                                               │
└─ FAIL → 机械修复（公式/图/占位符）            │
          ↓                                     │
         仍有 FAIL → 重试（最多 N 次）           │
          ↓                                     │
         重试用尽 → 生成 fix_report.json        │
                    ↓                           │
                   Agent 读取报告 → 分析 YAML →   │
                   修正 → 重 build               │
                    ↓                           │
                   PASS → 继续下一章 ────────────┘
```

## fix_report.json 结构

当 `pipeline batch --retry N` 用尽重试后，自动生成 `.dag/第N章/fix_report.json`：

```json
{
  "book_id": "01_emc",
  "chapter": "4",
  "wiki_root": "/path/to/book",
  "error_count": 2,
  "errors": [
    {
      "phase": "concepts",
      "file": "电磁屏蔽.md",
      "fail_count": 1,
      "details": [
        ["FAIL", "definition_sentence 前120字符在20_正文中不可检索"],
        ["FAIL", "mathematical_model 为空但 formula_references 非空"]
      ]
    },
    {
      "phase": "kp",
      "file": "pipeline",
      "block_reason": "KP内容深度不足: 缺数字参数",
      "details": [
        ["BLOCKED", "KP内容深度不足: 缺数字参数"]
      ]
    }
  ]
}
```

## Agent 修复流程（Hermes session 中运行）

当 `pipeline batch` 输出 `"错误报告已生成"` 时，Agent 执行以下步骤：

### Step 1: 读取错误报告

```bash
cat .dag/第N章/fix_report.json
```

### Step 2: 对每个 error 定位源文

从 `fix_report.json` 的 `phase` + `file` 确定：
- **concepts/ke/entities** → YAML 在 `.dag/第N章/data/{phase}.yaml`
- **kp/sp/scene** → YAML 在 `.dag/第N章/data/{phase}s.yaml`
- **exercises/solutions** → YAML 在 `.dag/第N章/data/{phase}.yaml`

相关源文 = `20_正文/第N章 目录.md`

### Step 3: 分析并修复

对每个 error 的 `details`：

| 错误类型 | 修复方法 |
|:---------|:---------|
| `definition_sentence 不可检索` | 从源文对应位置重新逐字复制定义句（含正确的引号字符） |
| `mathematical_model 为空` | 从源文对应容器中找 `$$...$$` 公式，填入 `mathematical_model` |
| `KP内容深度不足` | 精读源文容器，补充具体数字/公式/工具名到 `theoretical_basis`/`key_details` |
| `Mermaid 语法错误` | 检查 `%%{init}` 双引号 + `}%%` 闭合，修复箭头/节点语法 |
| `{{placeholder}} 残留` | 将 `{{field}}` 替换为实际内容或"无" |
| `图引用不存在` | 从源文容器中确认正确的图号，或填"无" |

### Step 4: 修正 YAML

```python
# 读取 → 修正 → 写入（通过 yaml.dump 而非手写）
import yaml
with open(".dag/第4章/data/concepts.yaml") as f:
    data = yaml.safe_load(f)
for item in data:
    if item["name"] == "电磁屏蔽":
        item["bd"]["definition_sentence"] = "正确的定义句（逐字复制）"
        item["bd"]["mathematical_model"] = "$$E = ...$$"
with open(".dag/第4章/data/concepts.yaml", "w") as f:
    yaml.dump(data, f, allow_unicode=True, default_flow_style=False,
              sort_keys=False, indent=2, width=120)
```

### Step 5: 重跑 pipeline auto

```bash
dag_controller.py pipeline auto -w $BOOK_DIR --book-id $BOOK_ID -c N
```

重复 Steps 1-5 直到 PASS 或 max 3 次。

## 与现有 pipeline fix 命令的区别

| 特性 | `pipeline fix`（已有） | `fix_report.json`（新增） |
|:-----|:---------------------|:--------------------------|
| 检测目标 | "无"字段 | 质量闸门 FAIL 的具体原因 |
| 使用时机 | 主动扫描修复 | 质量闸门阻断后的自动诊断 |
| 产出 | fix_queue.json（手动项） | fix_report.json（Agent 消费） |
| 执行者 | 脚本输出队列 | Agent 读取+修复 |
