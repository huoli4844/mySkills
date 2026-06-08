# 内联质量检查工作流（inline-before-batch）

> 理念：**写一个过一个** — 生成时就地检查，不把问题留到事后回查。

## 核心理念

```
旧：批量生成全部 YAML → 渲染 → 事后 review-fix → 额外修复轮次
新：逐项生成 → 内联检查 → 通过落盘 → 下一项
```

每个 YAML 项在写入聚合文件前，用 `quality_reviewer.py check-item` 就地检测。问题字段当场从源文补充后重检，通过再提交。批量事后 review-fix 作为安全保障网，不是主要修复手段。

## check-item 命令

```bash
python3 scripts/quality_reviewer.py check-item \
  --type concept            # concept/ke/kp/sp/scene/entity/solution
  --threshold 0.9           # 达标阈值(默认0.8)
  --item '{"name":"...","fm":{...},"bd":{...}}'
```

### 返回值格式

```json
{
  "file": "电容性耦合",
  "type": "concept",
  "score": 0.75,
  "pass": false,
  "issues": [
    {
      "field": "term_definition",
      "severity": "warning",
      "category": "field_too_short",
      "current_len": 31,
      "target_len": 80,
      "action": "enrich"
    }
  ],
  "summary": {"error": 0, "warning": 3, "info": 0, "total": 3}
}
```

exit 0=pass, exit 1=fail

### 检查内容

T1（YAML dict级别，无需渲染）: name/FM必填(source_chapter/confidence)/bloom_level
T2（YAML dict级别，无需渲染）: bd字段深度(FIELD_DEPTH配置)/principle_steps/term_english

### 评分公式

err_penalty = min(errors * 0.25, 0.70)
warn_penalty = min(warnings * 0.06, 0.25)
score = max(0, min(1, 1 - err_penalty - warn_penalty))

| 问题 | 分数 | 0.8通过? |
|------|------|----------|
| 0E 2W | 0.88 | pass |
| 0E 4W | 0.76 | fail |
| 0E 5W | 0.75 | fail |
| 1E 0W | 0.75 | fail |

## Agent 生成流程

```
for each YAML item:
  ① Agent 写 bd 字段内容
  ② check-item --threshold 0.9
     ├─ pass → 追加到 YAML → next
     └─ fail → 逐字段丰富 → 回到 ②
```

## 与 batch review-fix 的关系

内联检查(check-item): 拦截 ~90% 字段深度问题，生成阶段解决
事后审查(review-fix): 安全网，检跨文件引用(T3)/Mermaid/wikilink

第3章实测：13个文件的问题全部可通过内联检查预防。
