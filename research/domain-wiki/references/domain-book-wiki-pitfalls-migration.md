# Domain-Book-Wiki 陷阱迁移记录

## 已从旧技能迁移的修复（v3.0 全量吸收）

| 陷阱 | 旧技能问题 | domain-wiki 修复 | 日期 |
|:----|:----------|:----------------|:----:|
| bare `except Exception:` | 33处裸异常不记录 | 全部改为精确异常类型+print | 2026-06-09 |
| 文件超600行 | 14个超标文件 | kg_builder(677→526)、pipeline_v2(661→512)、phase_a.py新拆 | 2026-06-09 |
| 字段双源不同步 | schema/模板/mapping三处不同 | 模板单一权威+动态提取 | 先天 |
| 索引空壳无检测 | book_overview连通率全0% | graph_analytics 18项检测 | 先天 |
| 管线预验证 | 无preflight直接开跑 | Step 0 Preflight(phase_a.py) | 2026-06-09 |
| 跨章一致性 | 无 | quality_reviewer.check_cross_references | 2026-06-09 |
| 源文溯源验证 | verify_concepts_from_source | 待移植到check-item | P2 |
| 公式提取 | audit_wmf_formulas | 未移植 | P2 |
| 孤立链接审计 | link_audit | quality_gate集成 | P3 |

## 验证过程中发现的domain-wiki自身bug

### 1. pipeline_v2.py run 无限循环（3个根因）
详见 SKILL.md Pitfalls 表末尾的3条入口。

### 2. dag_state.py set_status 静默忽略
旧状态文件缺某些phase时set_status检查`if phase in self._data["phases"]`为False→什么都不做。
save写出不含该phase的状态→next_pending永远返回该phase→无限循环。
**修复**: set_status遇到缺失phase时自动创建默认条目。

### 3. split_book_to_chapters.py 正则 `.+?` 太严格
`CHAPTER_PATTERN = r"^(#{1,2})\s*(第\s*\d+\s*章\s*.+?)(?:\s*$)"`
当章节标题只有`# 第2章`（无标题文本）时，`.+?`需要至少1字符导致匹配失败。
**修复**: `.+?`→`.*?`（2026-06-09，处理21K行新书`电磁兼容EMC技术及应用实例详解_张亮`时发现）

### 4. 新书中 # 第N章 格式不匹配
某些书籍实际内容用`# 第2章`格式（不含`##`且无标题文本），不同于TOC中的长格式。
旧正则的`^#{1,2}`匹配单#，但`.+?`的贪婪性导致整体失败。
**修复**: 同上，改为`.*?`。
