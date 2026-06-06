# 陷阱归档（pitfalls-archive.md）

> 已修复的历史陷阱。保留用于回溯和防止回归。
> 活跃陷阱请参见 [pitfalls.md](./pitfalls.md)。

## 52. v34.0 质量体系阻断断裂（审计发现 — 全部已修复）

v34.0 双代理并行审计发现 6 类"检查了但不阻断"的阻断断裂。

### 52.1 内容深度 FAIL 不阻断 pipeline
**症状**：`_run_comprehensive_check_on_phase()` 输出 FAIL，阶段仍标记 done。
**修复**：返回 `(passed, fail_count, lines)` 三元组，pipeline_auto 中 `False` → `blocked`。

### 52.2 subprocess returncode 被丢弃
**症状**：C6/C9 exit(1) 但 pipeline_validate 不检查 returncode。
**修复**：检查 `result.returncode != 0`，计入 `_tracked` → `critical_issues`。

### 52.3 schema.py 不在自动 pipeline
**症状**：bd-as-string bug 只能在生成 .md 后由 C4 发现。
**修复**：pipeline_init 自动跑 schema.py Phase 0 预检。

### 52.4 KE 无溯源验证
**症状**：C7 仅用于 concepts（0.95），KE 定义不可追溯。
**修复**：pipeline_done ke 阶段运行溯源验证（warning 不阻断）。

### 52.5 两套断链检查实现不一致
**症状**：dag 内联 scan_broken_links 与 verify_completeness.py 逻辑不同。
**修复**：pipeline_validate [03/12] 同时运行两者，取最大值。

### 52.6 检查结果无持久化
**症状**：所有检查结果仅打印到终端，无法回溯。
**修复**：`_log_check_result()` → `.dag/check_logs/` JSON 日志。

### 52.7 YAML 字段名不匹配模板（v35.2）
**症状**：Agent 写 YAML 后 build 出的 .md 有大量 `{{xxx}}` 占位符残留。
**修复**：字段名对照表 `references/yaml-field-mapping.md`。

### 52.8 `\s` 正则吞换行符使 Mermaid 闭合错位（v35.2）
**修复**：用 `[ \t]` 替代 `\s`。`_fix_mermaid_block_boundaries()` 最后防线。

### 52.9 Obsidian 不渲染 `flowchart` 关键字（v35.2）
**修复**：优先使用 `graph TD`。

### 52.10 构建后文件不在用户工作区（v35.2）
**修复**：每次 build_kb_files.py 后同步到用户工作区路径。

### 52.11 Mermaid 节点标签中 `→` 与箭头语法冲突（v35.2）
**修复**：将节点标签内 `→` 替换为 `>`。

### 52.12 `_wrap_mermaid_fields` 与模板旧包裹冲突（v35.2）
**修复**：所有模板去掉硬编码 mermaid 包裹，统一交 `_wrap_mermaid_fields`。

### 52.13 template_assembler.py `fname` 变量未定义（v35.2）
**修复**：`prefix='.' + fname + '.'` → `prefix='.' + safe_name + '.'`。

### 52.14 `validate_phase_output` 把"无"当未填充（v35.2）
**修复**：移除 `stripped == "无"` 检查条件。

### 52.15 pipeline auto 跳过习题提取（v35.2）
**修复**：检测到源文有习题但目录为空时先重置状态。

### 52.16 目录布局硬编码（v35.4 审计发现）
**修复**（v35.5）：`detect_layout()` / `load_workspace_config()` 三策略自动检测。

---

**归档版本**: v40.0
**归档日期**: 2026-05-30
**活跃陷阱**: 见 [pitfalls.md](./pitfalls.md)
