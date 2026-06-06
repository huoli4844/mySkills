# v50.0 工程修复记录

> 记录本次会话中修复的关键工程化 bug，供后续 session 查阅。

## 1. build staging 目录覆写 bug (P0) 🔥

**症状**: 逐章构建时 `os.rename(.build_tmp/90_习题, 90_习题)` 用临时目录**替换**整个 `90_习题/`，导致其他章的习题全部消失。

**根因**: `build_kb_files.py` staging 提交逻辑使用 `os.rename(out_dir, real_dir)` — 目录级替换，非逐文件合并。

**修复**: 改为逐文件移动:
```python
for fname in os.listdir(out_dir):
    src = os.path.join(out_dir, fname)
    dst = os.path.join(real_dir, fname)
    os.rename(src, dst)
shutil.rmtree(out_dir)
```

## 2. yaml_pre_validate schema 脱节 (P0) 🔥

**症状**: 第 6 章报 255 错误，其中 90%+ 是假阳性。

**根因**: `yaml_pre_validate.check_required_fields()` 硬编码的字段名（如 `skill_description`）与 `build_kb_files._REQUIRED_BD_FIELDS` 的字段名（如 `solved_problem`）完全不同。

**修复**: 在 `dag_constants.py` 中新增 `REQUIRED_BD_FIELDS` 常量，作为唯一权威来源。`yaml_pre_validate` 和 `build_kb_files` 从同一处读取。255 → 57 错误（全部真实内容缺口）。

## 3. 缺失字段 {{placeholder}} 残留 (P1)

**症状**: 知识点文件出现 `{{skill_requirements}}` 字面量，学生看到未渲染的占位符。

**根因**: `build_kb_files` 对必填字段缺失时的处理逻辑: `bd[ph] = "{{" + ph + "}}"` — 保留占位符作为标记。

**修复**: v50.0: 缺失字段统一填"无"，不再保留 `{{}}`。

## 4. _strip_wu_sections 导致结构不一致 (P1)

**症状**: 同类型节点文件结构不一致 — 内容为"无"的节被删除，有的文件有某个节、有的没有。

**根因**: `fill_template()` 末尾调用 `_strip_wu_sections()` 删除内容恰好为"无"的 ### / #### 子节。

**修复**: 移除 `_strip_wu_sections` 调用，保留空节确保结构一致。同时在 `fill_template()` 返回前新增 `re.sub(r'<!--.*?-->', '', result, flags=re.DOTALL)` 剥离 HTML 注释。

## 5. quality_score wikilink 假阳性 (P1)

**症状**: 所有章节显示 398 wikilink 断链（实为 164 条 L2 索引引用未被扫描）。

**根因**: `all_files` 只扫描 6 个节点目录（30_核心概念 ~ 80_实体），遗漏 `10_总揽/` 和 `90_习题/解答/`。

**修复**: 扩展扫描范围到 8 个目录 + 递归子目录。398 → 234（剩余全部是真实内容缺口）。

## 6. quality_score 评分负分 (P1)

**症状**: wikilink 断链率 27%，乘数 10 导致 link_score 为负。

**修复**: wikilink 权重 30%→20%，惩罚乘数 10→3。

## 7. WorkspacePaths 错误传入 domain 目录 (P1)

**症状**: 创建 `电磁兼容领域/电磁兼容领域/0001_电磁兼容基础教材` 嵌套重复目录。

**修复**: `WorkspacePaths.__init__` 新增 `_is_valid_book` 校验（检查 `book_dir/20_正文/` 是否存在），传入 domain 时自动回退修正。

## 8. setdefault 不覆盖 YAML 旧值 (P1)

**症状**: `bd.setdefault("exercise_link", ...)` 不生效 — YAML 已有旧值时 setdefault 不起作用。

**修复**: 改为 `bd["exercise_link"] = ...` 强制覆盖。

## 9. 目录前缀文档错误 (P2)

**症状**: `chapter-data-generation.md` 中 KE→`30_知识要素/`（实为 `40_`）、KP→`40_知识点/`（实为 `50_`）等全部偏移 10。

**修复**: 6/6 前缀全部修正 + 新增习题/解答目录前缀。

## 10. 技能代码清理 (P2)

- 删除 7 个死代码文件 (62→48 .py)
- 合并 template_assembler_core → template_assembler
- 删除 dag_pipeline re-export 层
- 拆分 WorkspacePaths 到独立文件
- content_check_rules.py 1327 行 → 291 行入口 + rules/ (5 文件)
- 删除 6 个 build_*.py 薄包装器
