# v49.0 质量审计报告

> 审计日期: 2026-06-05
> **状态: ✅ 全部问题在 v50.0 已修复**（见下文各条标注）
> 审计范围: EMC 知识库

## 八项需求逐条评估

| # | 需求 | 状态 | 证据 |
|:--|:--|:--|:--|
| 1 | 所属领域/层级解读/认知阶段/概念图谱折叠 | ✅ | 全部节点有 Bloom 层级 + Mermaid + 解析 + domain |
| 2 | 场景可一键跳转关联知识点 | ✅ | Scene `## 二、知识与技能应用` 含 wikilink |
| 3 | 知识点含举例/解释/原理/技能要求/技能目标 | ✅ | 19/19 KP 有技能要求+技能目标，Mermaid 推导+详解 |
| 4 | 技能点配套 1-2 实例 | ✅ | 11/13 SP 含"典型实操案例"(2个案例) |
| 5 | 场景各节点一句话描述+整体解答 | ⚠️ | 10/10 有节点描述；**1/10 有方案详解** |
| 6 | 概念/知识点标注"解决的问题" | ✅ | 34/34 概念 + 19/19 KP 有 `### 0. 解决的问题` |
| 7 | 技能点聚焦实操说明方法 | ✅ | Mermaid 操作流程图 + 六步流程 + Bloom 对齐 |
| 8 | 场景展示解题全流程 | ⚠️ | 10/10 有 Mermaid 工作流图；**1/10 有详细方案** |

## v49 工具问题

### 1. yaml_pre_validate.py schema 与实际 YAML 脱节 (P0) ✅ v50.0 已修复

**修复方案 (v50.0)**: `dag_constants.py` 新增 `REQUIRED_BD_FIELDS` 作为唯一权威 schema。`yaml_pre_validate.py` 通过 `_TYPE_TO_BD_KEY` 映射 + `from dag_constants import REQUIRED_BD_FIELDS` 消费同一源头。`build_kb_files.py` 同步从 dag_constants 导入。

### 2. exercise/solution 类型无法识别 (P0) ✅ v50.0 已修复

**修复方案**: `_detect_type()` 的 `type_map` 已包含 `exercises→exercise` 和 `solutions→solution`。`solutions_part*.yaml` 通过 `"solutions" in name.lower()` 子串匹配正确识别。

### 3. 概念学习目标渲染为 Python list repr (P1) ✅ v49.1 已修复

### 4. 概念 frontmatter 中 book_name 全空 (P1) ✅ v49.1 已修复

### 5. entity_type/domain/classification 无意义泄露 (P2) ✅ v49.1 已修复

### 6. 场景"方案详解"缺失 (P2) ✅ 本 session 修复

## v50 修复方向

1. 统一 schema 来源：`dag_constants.py NODE_CONFIG` 作为唯一权威 schema
2. `yaml_pre_validate.py` 和 `build_kb_files.py._REQUIRED_BD_FIELDS` 从同一处读取
3. 补充 exercise/solution 类型
4. 修复概念学习目标 list 渲染
5. 从 book_overview frontmatter 自动填入 book_name
6. 清理无效 frontmatter 字段（entity_type/domain/classification 仅限于实体模板）
