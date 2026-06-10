# Changelog

## 2.11.0 (2026-06-10)
- **md_to_docx.py**: 新增 Markdown→Word 转换工具，支持 single（单文件）和 dir（目录合并）两种模式，依赖 pandoc
- **死字段清理**: 从 project-config-template.yaml 清除未在代码中引用的 `path_processed` 字段
- **.bak 文件过滤**: collect_md_files() 增加 _bak/.bak 与 README.md 过滤

## 2.10.0 (2026-06-10)
- **4本书实战验证**：柯金良《电磁兼容概论》完整融入14章，验证了动态source_books机制在多书场景下的正确性
- **fix_common_issues.py**：新增共性批量修复脚本，处理Mermaid emoji替换(10处)、补图注(20处)、推导深度报告(86→0处)
- **14份写作指南全量重写**：从3列固定表改为动态N列表格，每本教材的分析深度和引用次数均衡（543次柯金良引用，分布14章）
- **14章内容优化**：按新写作指南注入柯金良素材，每章增补5~15KB（如第1章+13KB、第10章+10KB），全章质量校验通过
- **pitfall新增**：公式链无推导文字(86处实战)、blockquote孤立tag、\tag{0-X}章号前缀错误、processed_dir/raw_dir混淆、柯金良章节定位差异

## 2.9.0 (2026-06-10)
- **上下文预算管理层（L5）**：Design 新增第五层，每章写完后释放上下文，下一章仅加载写作指南+当前章素材+全书修正日志，防止上下文膨胀导致质量下降
- **修正自进化机制**：新增 `book-build-corrections.yaml`，自动记录每次修正操作（含 applicable_to 适用范围字段），下一章 Phase 2 写作指南生成时自动注入修正经验。Phase 6 检查是否重犯之前修正过的问题
- **Phase 3 并行搜索**：差距分析时用 delegate_task 并行 grep 所有参考教材，而非串行一本本读
- **Loop Engineering 理念表扩充为 5 项**：新增「自进化 (Self-Evolution)」组件
- **零硬编码原则新增**：`corrections.yaml` 的索引和数据获取通过 book_config.py 动态适配

## 2.8.0 (2026-06-10)
- **Loop Engineering 理念框架**：从"写提示词"到"设计验收标准"，在 Design 后新增概念层说明
- **自动反馈钩子**：每次 write_file 后自动触发 post_generation_check.py --fix，失败循环重试最多5次，不依赖 Agent 记忆
- **硬闸门系统**：4 道强制阻断闸门（体量闸门→自动差距分析、编号审计闸门→锁定提交、Mermaid渲染闸门、差距分析循环闸门），含 Mermaid 流程图
- **防漂移指南针机制**：每轮写作前（含中断恢复）强制重读 writing-guide-chN.md，解决长时间写作的目标漂移
- **Phase 3 自动触发差距分析**：post_generation_check.py 自动测量体量，低于偏薄阈值自动进入差距分析循环，无需等用户反馈
- **差距分析新增循环补充步骤（第7步）**：补充后再次测量，达标或确认内容天花板后停止
- **Phase 编号体系重整**：Phase 0/0.5/0.6/1~2/4.5 统一映射为 Phase 1-9，43 处引用全部更新，零残留

## 2.7.0 (2026-06-10)
- **双层配置架构**: config.yaml 只存技能默认值（工作流/体量/子目录名）,
  book-build.yaml 存项目配置（教材名/参考教材/知识库路径）
- **project-config-template.yaml**: 新增项目配置模板文件
- **setup() 幂等**: 先盘点已有内容，只补缺失不删已有。原样保留已有章节/案例/实验
- **task_tracker.py**: 新增任务进度管理，在项目根目录创建 book-build-progress.yaml
  支持 init_from_outline / mark_in_progress/completed / next_pending / 中断恢复
- **冰点法则（零硬编码设计原则）**: 不写路径/数量/具体值到文档和测试
- **去除"三本书"假设**: source_books 改为 list，所有文档/表格/测试动态适配
- **去除 book_a/b/c 固定属性**: book_a_author/book_a_path 等全部移除，通过
  source_books 列表遍历
- **56 个测试**（16 book_config + 13 task_tracker + 27 其他），全部通过

## 2.5.0 (2026-06-10)
- **新增 `check_tag_placement()`**：检测 `\tag{}` 在 `$$` 块外部（孤立标签），杜绝渲染失败
- **SKILL.md**：新增 pitfall #24（子代理写出的 \\tag{} 在 $$ 块外部）和 #25（子代理不写公式的 $$ 包装）
- **新增 `references/case-writing-template.md`**：8大模块案例编写模板（命名规范/公式要求/Mermaid规范/质量审查流程）
- **更新质量审查管线为8项**：公式→Mermaid(7项)→Wikilink→\\tag{}放置→拼写→自动修复→统计

## 2.3.0 (2026-06-10)
- **Mermaid语法校验全面升级**：`post_generation_check.py` 检查 Mermaid 图内语法而非仅检查闭合标签
- **新增6项Mermaid检查**：图表类型合法性、xychart-beta关键字白名单（`block_lines[1:]`首行跳过防误报）、flowchart节点引号要求、emoji禁令、`%%{init}`格式规范、classDef定义覆盖
- **新增Mermaid自动修复**：`_fix_mermaid_issues()` 自动移除 `bar-group-group` 等非法关键字，集成到 `--fix` 管线
- **SKILL.md文档增强**：Phase 4.5 新增6项Mermaid校验表格，pitfalls.md 新增 #32 xychart-beta 陷阱
- **修复误报**：xychart-beta 首行 `xychart-beta` 不再被错判为非法关键字

## 2.1.0 (2026-06-09)
- **新增 `post_generation_check.py`** — 自动质量检查脚本：公式语法/全编号/Mermaid闭合/拼写，支持 `--fix` 自动修复
- **新增 `clean_formula_numbers.py`** — 当编号严重混乱时，删除所有原编号后从头重排（使用前必须备份）
- **新增 `fix_tag_placement.py`** — 将误放在 `$$` 外部的 `\tag{}` 移回公式块内部
- **Phase 0.5 重构**：从简单标注扩展为5步标准化流程（研读→手法对比→发挥空间→写作指南→动笔），新增向用户展示对比表+获确认后才能动笔的要求
- **Phase 4.5 升级**：从零散shell命令替换为统一的 `post_generation_check.py --fix` 调用，新增审计报告模板
- **Pitfall 9**: 写作指南须经用户确认后方可动笔
- **Pitfall 10**: `\tag` 与 `$$` 边界问题——自动修复脚本可能将tag放在 $$ 外部
- **Pitfall 11**: `clean_formula_numbers.py` 使用前必须备份
- **Bug fix**: `_fix_missing_tag` 函数将 `\tag` 插入在 `$$` 之后而非之前，确保在公式块内部
- **新增 `references/gap-analysis-checklist.md`** — Phase 0.6 内容差距分析模板

## 2.0.0 (2026-06-09)
- **重大重构**：SKILL.md 从 2012 行/80KB → 168 行/8.6KB（减量89%）
- 重构为 `skill-authoring` 标准格式：Overview→When to Use→Design→Workflow→Commands→Pitfalls→Reference Index
- 详细写作规范、完整陷阱列表移至 references/
- 新增 13 条军规（公式全编号规则）
- 新增 `references/pitfalls.md` 完整陷阱列表

## 1.9.0 (2026-06-09)
- 12条军规→13条：新增「公式全编号」规则
- `volume-standards.md` 新增 0f 公式全编号检查项
- 综合核验清单新增 0d 公式全编号项

## 1.8.0 (2026-06-08)
- 图号检查 + 学习目标审查 + 数学推导标准
- 新增 L3 六步推导结构标准
- 新增综合核验清单（0a-0e）

## 1.7.0 (2026-06-08)
- Phase 4.5 清理+图号核验环节
- Mermaid ≥6 张标准
- 体量铁律 5~10×

## 1.6.0 (2026-06-08)
- 12条军规完整版
- 多教材融合写作法（张亮引入→梁振光结构→路宏敏细节）
- 写作禁止清单

## 1.0.0 (2026-06-06)
- 初始版本：Phase 0-6 工作流
- 三本教材研读方法论
- 6要素质量检查
