# 质量体系全面审计报告 (v34.0)

> 2024-05-28 — 对 domain-book-wiki 技能全部 9 个检查器的端到端审计

## 一、检查器清单（9 个）

| # | 检查器 | 覆盖维度 | Pipeline 自动? | 出错阻断? |
|---|--------|---------|:---:|:---:|
| C1 | `preflight.py` | 模板/YAML结构/DIR/模块/Phase1源文件/教学链 | ✅ | ✅ |
| C2 | `schema.py` | YAML bd-as-string/必填键 | ❌→✅(v34) | ✅ |
| C3 | `validate_chapter_data.py` | YAML bd字段完整性 | ❌ | — |
| C4 | `validate_phase_output` | FM/置信度/占位符/type/**子节填充** | ✅ | ✅ |
| C5 | `comprehensive-content-check` | 内容深度/公式/Mermaid/图片/占位符 | ✅ | ✅(v34) |
| C6 | `verify-concepts.py` | 概念非空/标记词/出处 | ✅ | ✅(v34) |
| C7 | `verify-concepts-from-source.py` | 定义原文可检索（硬约束） | ✅ | ✅ |
| C8 | `verify_completeness.py` | wikilink/孤立文件/YAML↔文件 | ✅(v34) | — |
| C9 | `validate-mermaid-syntax.py` | HTML tag/引号/括号/subgraph | ✅(v34) | ✅(v34) |

## 二、v34.0 修复的阻断断裂

### 修复前（v33.0 阻断链条）
```
C5 content-check → ❌ FAIL 不阻断（仅打印）
C9 mermaid-check → ❌ exit(1) 被丢弃
C6 verify-concepts → ❌ exit(1) 被丢弃
C2/C3 schema → ❌ 不自动跑
```
只有 C7（概念溯源硬约束）在 L1 闸门中真正阻断。

### 修复后（v34.0）
```
C5 → ✅ FAIL → blocked
C6/C9 → ✅ returncode → critical
C2 → ✅ pipeline_init Phase 0 自动跑
C8 → ✅ pipeline_validate 交叉验证
```

## 三、图谱能力运用报告

### v34.0 状态：14 项能力中仅 4 项接入 pipeline
- `build()`, `check_graph_quality()`, `check_l1_connectivity()`, `check_path_integrity()`（仅 L1）
- 7 项核心分析能力完全闲置：`check_similar_names`, `degree_centrality`, `check_bridge_gaps`, `validate`, `suggest_build_order`, `trace`, `impact`

### L2 层：仅做 SQL 查询，不是图分析
- 仅检查 wikilink 节点存在性和 L2 覆盖率 ≥80%
- 缺：全书知识链完整性、核心概念识别、跨章一致性

### L3 层：跨书引用仅计数
- `_check_cross_book_refs` 只统计跨书边数，始终 pass
- 缺：跨书概念对齐、重复检测、知识孤岛检测、领域链覆盖

### L4 层：仅检查空心概念
- 缺：全库健康度、跨领域桥接、知识盲区

## 四、v35.0 四级图谱能力全接入

| 层级 | 新增检查 | 调用的 KGraph 方法 | 级别 |
|:---:|:--------|:------------------|:----:|
| L1 | 孤儿KE | `check_graph_quality()` | critical |
| L1 | 过载节点 | `check_graph_quality()` | warning |
| L1 | 相似节点名 | `check_similar_names(0.85)` | warning |
| L2 | 全书知识链 | `check_path_integrity()` | warning |
| L2 | 核心概念 | `degree_centrality()` | warning |
| L2 | 跨章一致性 | `check_similar_names(0.9)` | warning |
| L3 | 跨书对齐 | `check_similar_names(0.88)` + 跨书过滤 | warning |
| L3 | 知识孤岛 | 跨书边比例 <5% | warning |
| L3 | 领域链 | `check_path_integrity()` | warning |
| L4 | 健康度 | `validate()` + `check_graph_quality()` | warning |
| L4 | 跨领域桥接 | 跨领域边统计 | warning |
| L4 | 知识盲区 | `check_path_integrity()` | warning |
