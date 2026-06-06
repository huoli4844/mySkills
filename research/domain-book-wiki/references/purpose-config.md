# Purpose 意图配置 (v46.0 新增)

借鉴 LLM Wiki 的 `purpose.md` 概念——
除了 Schema（结构规则），还需要 Purpose（方向意图）。

## 文件位置

书本目录下的 `purpose.yaml`：

```
{书号_书名}/purpose.yaml
```

## 完整配置示例

```yaml
# purpose.yaml — 知识库构建意图配置
version: "1.0"

# ── 构建意图 ──────────────────────────────
intent:
  # 构建目标（指导 Agent 的取舍策略）
  goal: "构建研究生级别的电磁兼容教学知识库"
  # 重点关注领域（影响概念升级优先级）
  focus_areas:
    - 电磁兼容设计方法
    - 实际工程案例
    - EMC 测试与标准
  # 质量侧重（影响闸门严格度）
  quality_emphasis: definition_precision  # definition_precision | cross_reference_completeness | diagram_richness
  # 目标读者
  target_audience: 研究生
  # 输出语言
  output_language: zh-CN

# ── 章节策略 ──────────────────────────────
chapter_strategy:
  # 跳过章节
  skip:
    - 附录A  # 暂不处理
    - 附录B  # 参考书目
  # 优先级调整（高于默认三标准）
  promote:
    - 1.2.1    # 电磁干扰三要素 — 核心概念
    - 5.3.2    # PCB EMC 设计规则 — 升级为概念
  # 降级（低于默认三标准）
  demote:
    - 3.4.1    # 分贝单位 — 降级为 KE

# ── 知识图谱配置 ──────────────────────────
graph:
  # 最小交叉引用数（低于此值标记为孤立）
  min_degree: 2
  # 稀疏社区 cohesion 阈值
  sparse_cohesion_threshold: 0.15
  # 是否启用 Louvain 社区检测
  enable_community_detection: true

# ── 增量构建 ──────────────────────────────
incremental:
  # 是否启用 SHA256 缓存（默认 true）
  enable_cache: true
  # 缓存失效策略: strict（hash 精确匹配）| relaxed（忽略空白变化）
  cache_policy: strict
```

## 最小配置

大部分字段有合理默认值，最小可用配置只需：

```yaml
intent:
  goal: "构建电磁兼容知识库"
```

## Agent 如何使用

Pipeline init 阶段自动读取 `purpose.yaml`：

```python
# dag_pipeline_ops.py pipeline_init 中
purpose = read_purpose_yaml(wr)
if purpose:
    # 将意图注入到构建配置中
    config["focus_areas"] = purpose.get("intent", {}).get("focus_areas", [])
    config["quality_emphasis"] = purpose.get("intent", {}).get("quality_emphasis", "definition_precision")
```

Agent 在写 YAML 时根据 `focus_areas` 调整：
- 匹配 focus_areas 的容器优先升级为概念
- `quality_emphasis: definition_precision` → 更严格的定义句闸门
- `quality_emphasis: cross_reference_completeness` → 更详细的交叉引用节

## 与 SCHEMA.md 的区别

| SCHEMA.md | purpose.yaml |
|-----------|-------------|
| 结构规则（如何组织） | 意图方向（为何构建） |
| 静态约定 | 动态策略 |
| 所有 Agent 共用 | 按构建任务独立 |
| 技术性 | 教学性 |
