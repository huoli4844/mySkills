# 两步分析模式 (v46.0 新增)

借鉴 LLM Wiki 的 Two-Step Chain-of-Thought Ingest 模式，对大章（>1000行）
采用"先分析、后生成"的两步策略，提升 YAML 质量。

## When to Use

- 章节 > 1000 行源文
- 章节容器数 > 15（大量候选需要筛选）
- 定义句提取失败率高（反复返工）
- 需要 delegate_task 并行处理多个章节

## 两步流程

### Step 1: Analysis — 生成分析文件

Agent 通读章节 → 输出 `analysis.md` 到 `.dag/第N章/`：

```markdown
<!-- .dag/第N章/analysis.md -->

## 候选概念
| 容器 | 节标题 | 行数 | 支撑点 | 三标准 |
|------|--------|------|--------|--------|
| 1.2.1 | 电磁干扰三要素 | 120行 | 3个公式+2张图 | ✅ 满足 |
| 1.3.2 | 分贝单位 | 35行 | 1个公式 | ❌ 降级为KE |

## 交叉引用机会
- [[电磁干扰三要素]] → 关联到第3章 [[传导耦合途径]]
- [[电磁兼容标准]] → 需新建 Entity [[GJB151B]]

## 定义句候选
### 电磁干扰三要素
原文位置: 第1章 L156-158
候选文本: "电磁干扰是指任何能导致设备或系统性能降级的电磁现象"
验证: ✅ 含标记词"是指"，前120字内

### 分贝单位
原文位置: 第1章 L234
候选文本: "分贝是..."
验证: ❌ 定义句依赖图片引用，需还原
```

### Step 2: Generation — 基于分析写 YAML

Agent 读取 `analysis.md` → 批量写 YAML 到 `.dag/第N章/data/`：

1. 读 `analysis.md` 确认候选概念列表
2. 确认定义句已验证通过
3. 批量写 concepts.yaml → kes.yaml → entities.yaml → kp.yaml → sp.yaml → scene.yaml
4. 写完后 `pipeline auto` 驱动 build → check → validate

## 收益

| 维度 | 传统模式 | 两步模式 |
|------|---------|---------|
| 定义句返工率 | 30-50% | <10% |
| 容器遗漏率 | 5-10% | <2% |
| Agent 交互轮次 | 10-15 轮 | 5-8 轮 |
| 分析结果可审计 | ❌ | ✅ |
| 适合并行处理 | ❌ | ✅ (analysis 作共享上下文) |

## 与 delegate_task 的配合

对于多章并行处理，analysis 文件作为共享上下文：

```python
# 伪代码
for chapter in chapters:
    delegate_task(
        goal=f"分析第{chapter}章并生成 analysis.md",
        context="...chapter source path...",
    )

# 汇总 analysis 文件后
for chapter in chapters:
    delegate_task(
        goal=f"基于 analysis.md 写第{chapter}章的 YAML",
        context=f"analysis 文件在 .dag/第{chapter}章/analysis.md",
    )
```

## 注意事项

- analysis.md 是辅助文件，不影响 pipeline 状态
- 如果分析阶段发现"所有容器都不满足三标准"，不要强行写空的 concepts.yaml
- 定义句验证是分析阶段的核心工作，不要在生成阶段才发现不可检索
