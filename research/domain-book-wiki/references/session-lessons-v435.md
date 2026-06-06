# v43.5 会话经验教训

## CP-01: KP/SP/Scene 严禁跳过

❌ **错误做法**: Agent 根据章节类型（如概述章）自行判断不创建 KP/SP/Scene YAML
✅ **正确做法**: Agent 必须为**每一章**创建完整的 6 个 YAML（concepts/kes/entities/kps/sps/scenes）。即使概述章内容较浅，也要从已有概念和 KE 中整合出至少 1 个知识点/技能点/场景

**触发信号**: 用户质问"技能是怎么判断是不是要 KP/SP/Scene 的?" —— pipeline auto 不会跳过，是 Agent 没写 YAML

## CP-02: 习题和解答必须分开放

❌ **错误**: 习题文件内含骨架解答（「参见教材相关章节」「无」）
✅ **正确**: 
- 习题文件（`90_习题/`）使用 `exercise_template.md`——仅含题目 + wikilink
- 解答文件（`90_习题/解答/`）使用 `eval_template.md`——每个字段都有实质内容
- 修改涉及三处：`pipeline_auto.py`、`template_assembler.py`、`dag_constants.py`

## CP-03: YAML 内容质量底线

❌ **错误**: "了解""无""误区""滤波设计"等单薄占位符
✅ **正确**: 每个字段至少 80-300 字，含具体数据（频率/dB/器件型号/尺寸/费用）。概念文件 ≥8KB，KE ≥2KB，解答 ≥5KB

## CP-04: Bloom 字段不在 bd 中显示"无"

❌ **错误**: 模板用 `{{bloom_level}}` 但值在 fm 中，bd 里没注入
✅ **正确**: KP/SP/Scene 的 `bd_extra_keys_from_item_fm` 必须含 `["bloom_level"]`

## CP-05: definition_sentence 必须逐字匹配源文

❌ **错误**: 自己重新组织语句与源文不完全一致（多/少标点、漏「如表1-4所示」）
✅ **正确**: 直接从源文复制粘贴，标点符号一个不能差。用 `read_file` 验证

## CP-06: YAML 数据存在 .dag/ 下会丢

❌ **风险**: pipeline init/rollback 会清 `.dag/` 目录，YAML 随之丢失
✅ **Workaround**: 重置前确保 YAML 已备份。长期应迁移到独立 `data/` 目录

## CP-07: 六个 confidence 值各不相同

| 类型 | concept | ke | entity | kp | sp | scene | solution |
|:-----|:------:|:--:|:------:|:--:|:--:|:-----:|:--------:|
| confidence | 0.95 | 0.85 | 0.85 | 0.85 | 0.75 | 0.65 | 0.85 |

## CP-08: 习题模板有两处硬编码

修改习题模板时必须同时改三处：
1. `pipeline_auto.py` 第 66 行 — 自动检测习题的 template 参数
2. `template_assembler.py` 第 423 行 — ASSEMBLER_CONFIG 的 exercise 条目
3. `dag_constants.py` BUILDER_CONFIG — `build_kb_files.py` 的配置
