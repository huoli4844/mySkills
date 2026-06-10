# 公式编号系统性缺失 — 根因诊断与修复（2026-06-11）

## 问题现象

教材生成后，`post_generation_check.py` 报告所有公式"缺 \tag 编号"。

## 根因分析

### 不在质量检查脚本

| 脚本 | 行为 | 是否删除编号 |
|------|------|-------------|
| `post_generation_check.py` `check_formulas` | 只报告"缺\tag编号" | ❌ 不删除 |
| `_fix_missing_tag` | 在 `$$` 闭合前插入缺失编号 | ❌ 只补缺 |
| `_fix_duplicate_tags` | 重新连续编号 | ❌ 不删除已有编号 |
| `renumber.py` Step 3 | **删除**所有 `\\tag{N-M}` | ✅ 删除旧编号 |
| `renumber.py` Step 4 | 按出现顺序重新编号 | ✅ 重建编号 |

### AI 写作阶段遗漏

- `gen_prompt.py` 第五节明确写了"公式编号：`\\tag{章-序号}`"
- 但 13 章 739 个公式中 **0 个有编号**
- 这是 AI Agent 系统性忽略指令，非脚本 bug

## 正确的修复流程

### 方法1：renumber.py（推荐）

```bash
# 重排指定章节的公式编号
python3 scripts/renumber.py output/第N章-标题.md

# 预览模式（不改文件）
python3 scripts/renumber.py output/第N章-标题.md --dry-run

# 指定章号（自动检测失败时）
python3 scripts/renumber.py output/第N章-标题.md --chapter N
```

流程：备份 → 修复孤立tag → 转inline为block → 清除旧编号 → 按出现顺序编号 N-1, N-2, ...

### 方法2：post_generation_check.py --fix

```bash
python3 scripts/post_generation_check.py output/第N章.md --fix
```

注意：`--fix` 中的 `_fix_missing_tag` 只补缺失，不做全局重编号。如果已有编号但不连续，需要用 `renumber.py`。

## 预防策略

在 `delegate_task` 写节的 context 中必须显式包含：

```
⚠️ 公式编号铁律：每个 $$...$$ 块内必须有 \tag{章-序号} 编号。
\tag{} 独占一行，放在 $$ 闭合之前。
没有编号的公式 = 不合格的输出。
```

## 验证

```bash
# 检查是否有 \tag
grep -c '\\tag{' 第N章.md
# 应该 = 公式块数（$$...$$ 对的数量）

# 运行质量检查
python3 scripts/post_generation_check.py output/第N章.md
# 应显示"所有公式语法正确，编号连续无问题"
```

## 相关文件

- `scripts/renumber.py` — 公式编号统一重排（合并 fix_formula_numbers + clean_formula_numbers + fix_tag_placement）
- `scripts/post_generation_check.py` — 质量检查 + 自动修复
- `scripts/gen_prompt.py` — 写作指令生成器（含公式编号指令）
- `references/pitfalls.md` — 陷阱列表 #38-39
