# Harness Engineering (驾驭工程) 诊断

> v50.0 — 6 维度系统评估 + 10 项改进路线图 + 7 项已实现

## 当前能力矩阵

| 维度 | 状态 | 已实现 | 未实现 |
|:-----|:----:|:------|:------|
| 预测性 | ⚠️ | DAG 依赖链强制 + yaml_pre_validate 秒级校验 + check_file_naming | Agent 手写 YAML 是最大变量 |
| 可观测性 | ✅ | quality_score.json + yaml_pre_validate + L2/L3/L4 索引覆盖率 | 无构建仪表盘 |
| 防御深度 | ✅ | content-check + preflight + build staging(逐文件) + WorkspacePaths 校验 | 无事务回滚 |
| 故障隔离 | ✅ | 原子逐文件构建 + PipelineLock + 自动标准化命名 | — |
| 可维护性 | ✅ | content_check_rules 拆为 rules/ + 模板精简 + SKILL.md 69行 | — |
| 确定性 | ✅ | SHA256缓存 + YAML预校验 + 习题命名标准化 + 目录前缀修正 | 无产物diff校验 |

## v50.0 已实现

| # | 能力 | 效果 |
|:--|:-----|:-----|
| 1 | `yaml_pre_validate.py` + `REQUIRED_BD_FIELDS` 集中化 | schema 统一消除 350+ 假阳性 |
| 2 | `build staging` 逐文件移动 | 逐章构建不再覆写其他章 |
| 3 | `quality_score.py` | wikilink 权重修正 + L2/L3/L4 索引覆盖率 |
| 4 | `WorkspacePaths` `_is_valid_book` 校验 | 杜绝 domain 目录误传入重名 |
| 5 | `check_file_naming` + 构建自动标准化 | 习题命名统一 `第N章-习题N` |
| 6 | 习题↔解答自动互链 | `exercise_link` + `related_answer` 自动生成 |
| 7 | pipeline validate 集成跨章一致性 | 第 12/13 步调用 check_cross_chapter_consistency |
| 5 | `REQUIRED_BD_FIELDS` 集中化 (dag_constants) | v50.0 | 消除KE/Entity/KP/SP/Scene 350+ 假阳性 |
| 6 | `content_check_rules.py` → `rules/` 拆分 | v50.0 | 1327→291行入口 + 5×200行 |
| 7 | 死代码清理 | v50.0 | 62→48 .py 文件 |
| 8 | 跨章一致性 → `pipeline validate` 第12步 | v50.0 | 同名概念冲突可阻断 |
| 9 | 习题/解答文件命名自动标准化 + 互链 | v50.0 | build 时自动修正，pre-validate 发出 warning |
| 10 | 死代码清理 + build_*.py 薄包装器删除 | v50.0 | 62→48 .py 文件 |

## 剩余路线图

| # | 项目 | 收益 |
|:--|:-----|:-----|
| 1 | ~~quality_score wikilink 路径修复~~ ✅ v50.0 已完成 | — |
| 2 | 核心构建链路加集成测试 | 防回归 |
| 3 | yaml_auto_gen.py 自动提取定义句/公式/图引用 | 缩小 Agent 变量 |
| 4 | 构建仪表盘/渐进式日志 | 可观测性 |
| 5 | 事务回滚（跨章） | 故障隔离 |
