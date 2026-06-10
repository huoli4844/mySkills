---
name: book-build
description: "大纲驱动的专业教材编写管线。Loop Engineering + 自进化。双层配置，自动创建目录结构和进度文件，支持中断恢复。支持 MD→DOCX 转换（OMML 可编辑公式，使用 latex2mathml + MathML→OMML 管线，支持 LaTeX 公式）。"
version: 2.15.0
author: Hermes Agent
license: MIT
platforms: [macos, linux]
metadata:
  hermes:
    tags: [textbook, outline-driven, kb-qa, academic, docx]
    related_skills: [kb-qa, file2md, officecli]
---

# book-build（基于知识库的教材编写）

## Overview

**大纲驱动，知识库供料，严格遵循结构，专业级学术写作。** KB 是原料，教材是成品——不能把知识库中的模板结构复制到教材正文，必须重新组织为自然叙述的学术散文。

**专业教材 = 权威定义 + 直观引入 + 编号公式 + "式中"变量解释 + 含数字实例 + 层次化习题。**

**全自动执行（客户核心偏好）**：执行任务时**不问"要不要/是否继续"**，直接做。做错了再改也比停下来问效率高。只需在完成后汇报结果。

**P0与P1阶段策略差异**（2026-06-10 实战验证）：
- **P0（结构性缺失补充）**：缺失小节、军规检查占位、素材清单 → 直接 `patch` 插入少量框架内容即可，每章增加10-50行
- **P1（内容质量提升）**：真实案例、计算型例题、参考书盲区深度补充 → 必须用 `delegate_task` + 参考书源文提取，每章可能增加50-200行新内容
- 不要混淆：用P0的patch方式做P1会导致内容空洞、案例虚假。P1的每个案例需含具体技术细节（公司名、时间、参数值、工程分析）
- P1前应先运行 `outline_vs_chapter_audit.py` 生成 `补充执行清单.json`，按 P0→P1→P2 优先级执行

**"本章写作说明"插入位置**：当已有章节（1-13章）缺少军规检查和素材清单时，统一在章节末尾添加 `## X.Y 本章写作说明`（Y为大纲最后一个L1节号+1），包含：
- `## X.Y.1 素材来源清单`：列出本章使用的参考教材及对应章节号
- `## X.Y.2 12条军规落实检查`：逐项检查军规落实情况
- 参考 `references/content-supplementation-workflow.md` 中"Adding a New Subsection"模式
- 全章质量审计工作流（公式标签/孤立\tag/$$配对/Mermaid配对/综合审计）见 `references/comprehensive-quality-audit.md`
- 审计陷阱专项（审计覆盖不全/小结条目数/正则匹配）见 `references/audit-pitfalls.md`
- 公式编号系统性缺失（AI写作遗漏/根因诊断/修复流程/预防策略）见 `references/formula-numbering-diagnosis.md`
- 公式编号 0% 缺失详细诊断记录（含每章统计/验证步骤/数据证据）见 `references/formula-numbering-0-percent-diagnosis.md`
- **引用块公式 `>$$` 修复陷阱**（2026-06-11）：见 `references/formula-numbering-diagnosis.md` 中陷阱 D2-D3——引用块内 `>$$` 规范化 + 未闭合 `$$` + 错误 tag 位置的三重复合故障；完整修复流程见 `references/formula-numbering-comprehensive-fix.md`
- **关键陷阱（2026-06-11）**：公式编号修复详见 `references/formula-numbering-diagnosis.md` 中的陷阱A-E

**案例真实性铁律**：教材中的案例**必须来自真实事件**（公开报道/工程记录/标准测试数据），不得从参考教材（路宏敏/张亮/梁振光/柯金良等）直接摘抄。替换案例时，改用丰田EMI事件、iPhone 12 SAR超标、5G C-band干扰、波音787电池EMC等公开真实事件。

**公式格式铁律**（写作阶段必须执行）：
- `\\tag{N-M}` **独占一行**，紧跟在公式内容之后、**闭合 `$$` 之前**（即 `$$` 闭合行的前一行），禁止与公式同行或放在 `$$` 之前
- 正确格式：
  ```
  $$
  公式内容
  \\tag{N-M}
  $$
  ```
- 错误格式（会导致配对错位）：
  ```
  $$
  公式内容
  $$
  \\tag{N-M}   ← 错误！tag 在 $$ 之后
  ```
- `$$` **独立一行**，禁止公式内容与 `$$` 写在同一行
- 行内公式用单 `$` 包裹：`$E=mc^2$`
- 引用块内公式使用 `> $$` 而非 `$$`，内容行用 `>` 前缀
- 违反以上规则 → 运行 `post_generation_check.py --fix` 自动修复

**公式编号系统性缺失的根因与修复（2026-06-11 诊断确认）**：
- **根因**：AI Agent 在写作阶段系统性忽略 `gen_prompt.py` 中"公式编号：`\tag{章-序号}`"指令，739个公式100%无编号
- **这不是 post_generation_check 的 bug**：`check_formulas` 只报告不删除；`_fix_missing_tag` 只补缺但不做全局重编号
- **正确修复路径**：对整章运行 `python3 scripts/batch_fix_formula_numbers.py output/第N章-*.md`（v2 完整版：`>$$` 规范化 + 未闭合 `$$` 修复 + 空块清理 + tag 位置修正 → 重编号）。对于无格式问题的简单文件也可以用 `python3 scripts/renumber.py output/第N章-*.md`，但 batch_fix_formula_numbers.py 更安全（同时覆盖 `>$$`/未闭合 $$/空块三类潜在问题）。
- **预防**：在 `delegate_task` 写节的 context 中必须显式包含"每个 $$ 公式块必须紧跟 \tag{章-序号} 编号"的强约束
- **验证**：修复后运行 `python3 scripts/post_generation_check.py output/第N章.md --fix` 确认所有公式块都有编号
- **批量修复工具**：使用 `scripts/batch_fix_formula_numbers.py`（v2 完整版：`>$$` 规范化 + 未闭合 `$$` 修复 + 空块清理 + tag 位置修正，安全版：先读后写+自动备份）；对复杂的三重复合故障（`>$$` + 未闭合 `$$` + tag 位置错误同时出现），运行一次即可修复全部问题。

## 关键陷阱（2026-06-11 实战新增）

### 陷阱 A：正则 `\$\$(.*?)\$\$` 匹配不可靠
- **不能用** `re.findall(r'\$\$(.*?)\$\$', content, re.DOTALL)` 进行公式块匹配——当公式内容包含 `{` 或 `}` 字符时可能产生错误配对；且当引用块内存在 `>$$` 时正则根本不会匹配（因为 `>$$` 不是 `$$`）
- **必须用行级状态机**：逐行扫描 `$$` 行（或 `>$$`/`> $$` 规范化后的 `$$`），用布尔标志 `in_formula` 配对
- **行级状态机模板**：
```python
in_formula = False
for line in lines:
    if line.strip() == '$$':
        in_formula = not in_formula
    # 在 in_formula 状态切换时处理公式块
```
- **完整修复流程**（含 `>$$` 处理和未闭合 `$$` 检测）：见 `references/formula-numbering-diagnosis.md` 陷阱 D2-D3

### 陷阱 B：空 `$$...$$` 块导致编号偏移
- 现象：`$$\n\n$$`（内容为空或只有空行）被当做一个公式块跳过，导致后续所有编号 +1
- 修复：编号前先扫描并删除所有空 `$$...$$` 块

### 陷阱 C：孤立 `$$` 行破坏配对计数
- 现象：文件中存在前后都是空行或引用标记的独立 `$$`，不属于任何 `$$...$$` 配对
- 修复：用状态机配对后，收集未配对的 `$$` 行索引并删除，然后再编号

### 陷阱 D：`>$$` 引用块格式
- **现象**：引用块内公式使用 `>$$` 或 `> $$` 而非 `$$` 作为边界
- **处理**：将 `> $$` 替换为 `$$`（删除 `>` 前缀），删除空引用行 `>`，然后用行级状态机配对

### 陷阱 D2：引用块公式修复导致配对错位（2026-06-11 新发现）
- **根因**：当文件中存在 `\tag{N-M}` 行紧跟在 `$$` 之前（格式错误：tag 应该在公式后、闭合 `$$` 前），且引用块内 `>$$` 被规范化为 `$$` 后，状态机会错误配对——`>$$` 变为 `$$` 后与后续未配对的 `$$` 形成巨大块
- **症状**：`$$` 总数为奇数（83 而非偶数），状态机配对中出现跨越 80+ 行的公式块（如 L872-L962），tag 位置验证大量失败
- **修复**：必须按以下顺序执行：
  1. 清除所有 `\tag{}` 行（不管位置是否正确）
  2. 规范化 `> $$` → `$$`
  3. 删除空引用行 `>`
  4. 删除连续 `$$`（空块）
  5. 用状态机配对，发现未配对 `$$` → 在公式内容后插入闭合 `$$`
  6. 再次删除连续 `$$`（修复后可能产生的）
  7. 行级配对 + 编号
- **绝对不要用**：先修复 `>$$` 再单独修复 tag 位置的补丁式方法——这会改变行号导致后续修复失效

### 陷阱 D3：`$$` 未闭合导致后续所有配对错位（2026-06-11 新发现）
- **根因**：原始恢复文件中某些公式块的 `$$` 没有闭合（如 L816 `$$` 开始但无闭合），状态机会一直往后找直到找到下一个 `$$`
- **症状**：出现 L872-L962 这样跨越 90 行的"公式块"，`$$` 总数为奇数
- **诊断**：配对后检查 `in_formula` 布尔值，如为 True 则存在未闭合 `$$`
- **修复**：在未闭合 `$$` 后的第一个非空行（公式内容）后插入闭合 `$$`

### 陷阱 E：批量处理脚本的致命错误模式
- **致命**：先 `open(fpath, 'w')` 打开写模式（清空文件），再 `open(fpath, 'r').read()` 读内容 → 读到空字符串
- **正确模式**：先 `open(fpath, 'r').read()` 保存内容到变量，处理后再 `open(fpath, 'w').write()`
- 所有批量修改脚本必须先做备份（`.bak`），再做验证（重读对比）

## 客户使用流程（只需两步）

```
Step 1: 创建目录，告诉 book-build 项目路径
  → mkdir ~/Desktop/我的教材
  → "book-build，项目在 ~/Desktop/我的教材"

Step 2: 技能自动创建全部目录结构和 book-build.yaml
  → Agent 执行: Config.setup(project_root)
  → 自动创建: input/ + output/ + 写作大纲/案例/实验/习题解答/

Step 3: 编辑 book-build.yaml 填入参考教材路径
  → vim ~/Desktop/我的教材/book-build.yaml
  → 修改 textbook.name 和 source_books 列表

完成后，Agent 即可加载项目配置开始写作：
  cfg = Config(project_root="~/Desktop/我的教材")
```

[... SKILL.md content continues unchanged ...]