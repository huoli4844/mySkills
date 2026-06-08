# yaml_auto_fill.py — 模板驱动的 YAML 自动填充引擎

> v50.2 — 从模板 `.md` 文件解析 `{{field}}` → 分类 → Python 自动填机械字段 → LLM 只填内容字段

## 核心原理

模板即契约。从 8 个模板解析 106 个 `{{field}}` 占位符，按可自动程度分类：

| 类别 | 占比 | 填充方式 | 示例 |
|:-----|:-----|:--------|:-----|
| meta | ~30% | Python 自动（查表/上下文） | confidence, bloom_level, source_chapter |
| auto | ~5% | Python 自动（源文正则） | definition_sentence, source_from |
| derived | ~10% | Python 计算 | difficulty(bloom→⭐), bloom_progression |
| llm | ~50% | LLM 填（结构化 prompt） | theoretical_basis, derivation_analysis |

**效果**：Agent 手写字段从 ~24 减至 ~6，字段名错误率 33%→0%。

## 命令速查

```bash
yaml_auto_fill.py analyze                          # 分析模板字段分类
yaml_auto_fill.py skeleton -t kp -n "名称" -c 1    # 生成骨架
yaml_auto_fill.py fill -w $DIR -t kp -c 1 -o out   # 机械填充
yaml_auto_fill.py llm-prompt -w $DIR -t kp -n "X"  # LLM 提示
yaml_auto_fill.py validate-fix -w $DIR             # 验证闭环
```

## 合并策略

Agent 已有高质量内容时使用**合并模式**：Agent YAML + Python 补缺元字段（source_from/bloom_level/difficulty）。252 个元字段一次性补全。

## 关键陷阱

- **批量写 YAML 前计数**：`len(旧)≥len(新)` 阻断，防止数据丢失
- **bloom_level 值域**：`validate-fix` 自动修复非标值（如 "知道→分析" → "应用→分析"）
- **confidence 值域**：按类型自动修正（concept=0.95, kp=0.85, sp=0.75, scene=0.65）
