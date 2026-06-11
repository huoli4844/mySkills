# 审计脚本全景（v3.4.0）

## v3.4.0 变更记录

`comprehensive_audit.py` **已于 v3.4.0 删除**。其 7 项检查（第二人称、Step标记、小结条目数、占位符、参考文献格式、$$配对、公式标签章号）已完全合并到 `quality_audit.py` 的 `check_second_person()`/`check_step_markers()`/`check_summary_count()`/`check_placeholders()`/`check_footnotes_format()`/`check_dollar_pairing()`/`check_tag_chapter_prefix()` 函数中。

以前使用 `comprehensive_audit.py` 的调用全部改为：
```bash
python3 scripts/quality_audit.py --project . --chapter N
```

## 审计脚本职责矩阵

| 脚本 | 行数 | 状态 | 职责 | 调用者 |
|:-----|:----:|:----:|:-----|:-------|
| `quality_audit.py` | 454 | ✅ 主力 | 统一审计入口：公式、Mermaid、内容统计、军规合规、学习目标覆盖、技术深度 | Agent / 命令行 |
| `batch_fix_formula_numbers.py` | 300 | ✅ 主力 | 公式编号批量修复（\tag 章号前缀连续性） | Agent 写作后 |
| `post_generation_check.py` | 812 | ⚠️ 辅助 | 生成后自动修复：公式/Mermaid/wikilink/拼写/推导深度/图注/格式 | 可选 |
| `outline_vs_chapter_audit.py` | 288 | ✅ 独立 | 大纲-正文差距分析（结构性） | P0 补充阶段 |
| `check_table_columns.py` | 121 | ✅ 独立 | 表格对齐行列检查与修复 | 可选 |

## 标准审计流程（v3.4.0）

```
写作完成
  ↓
batch_fix_formula_numbers.py   # 修复公式编号
  ↓
quality_audit.py --project . --chapter N   # 全面审计（含军规合规）
  ↓
[有问题？]
  ├─ 公式问题 → batch_fix 或手动修
  ├─ Mermaid问题 → 手动修
  ├─ 内容问题 → delegate_task 扩充
  └─ 格式问题 → post_generation_check.py --fix
```

## 未来改进方向

1. **quality_audit.py 拆分** — 454行接近红线，建议拆为 `qa_formula.py` + `qa_content.py` + `qa_cli.py`
2. **Gate A（大纲生成前验证）** — 在 generate_outlines.py 中内置检查，防止不合格大纲产出
3. **Gate B（正文生成时即时修复）** — 参考 domain-wiki 的内联检查流程
