# Domain-Wiki vs Domain-Book-Wiki 身份验证指南

## 验证方法

```bash
# 唯一可靠的区分方法：检查 @prompt 数量
grep -c '@prompt' ~/.hermes/skills/research/domain-wiki/assets/templates/concept_template.md
# domain-wiki (ACTIVE):  24
# domain-book-wiki (BACKUP): 0

# 快速检查使用哪种 pipeline：
ls ~/.hermes/skills/research/domain-wiki/scripts/pipeline_v2.py       # ACTIVE skill
ls ~/.hermes/skills/research/domain-book-wiki/scripts/dag_controller.py # BACKUP
```

## 如果改错了怎么办

1. `git log --oneline -5` 确认错误的提交
2. `git revert --no-edit <commit_hash>` 逐条撤销
3. `git push`
4. 切到正确的 skill 目录重新编辑

## 历史

- 提交 `8c3cd15` 创建 domain-book-wiki 作为 v52.x 历史备份，commit message 明确标注"仅作历史参考"
- 提交 `b204470` 移除了旧的 domain-book-wiki，随后 `8c3cd15` 重新恢复
- Agent 在 2026-06-09 错误修改了 domain-book-wiki（提交 d16480a, 9622516），随后 revert
- 用户原话："你已经搞了几次啦"
