---
name: book-build
description: "Use when writing a professional textbook from an outline and a domain-wiki knowledge base. Strictly follows the outline structure, queries kb-qa for content, outputs Obsidian Markdown or Word .docx."
version: 2.1.1
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

## When to Use

- 用户提供教材大纲（.docx / .md / 纯文本），要求按大纲逐章编写
- 用户指定一个 domain-wiki 格式的知识库目录作为内容来源
- 用户输出要求为 .md（Obsidian）或 .docx（含可编辑 OMML 公式）

**前置条件**：知识库已用 file2md 转换完成，至少包含 20_正文/ 或 概念/KE/KP 目录。

## Design

教材编写是一个四层递进的知识转化过程：

**L1 — 素材层：** KB 搜索（kb_search.py）从知识库召回概念/知识点/知识要素等内容片段。每一节的素材来自多个源文件。

**L2 — 结构层：** 大纲解析确定章节树；内容类型判别（6种模式）选择写作结构；写作指令生成器（gen_prompt.py）综合大纲定位+素材+写作规则，生成每节的提示词。

**L3 — 写作层：** Agent 按提示词写出正文，遵守 13 条军规。每章必须经过"三书研读→写作指南→动笔"的 Phase 0.5 流程。

**L4 — 校验层：** 每章写完后经过 6 要素检查 + 13 维度自审评分 + 体量铁律验证。

**13 条写作军规**（完整版加载 `references/volume-standards.md`）：

| # | 军规 | 来源 |
|:-:|:-----|:-----|
| 1 | **详实案例驱动** — 13个案例，每个有具体时间/地点/数字/分析 | 路宏敏 |
| 2 | **历史极致细节** — 具体日期+组织全称(含英文)+里程碑 | 路宏敏 |
| 3 | **系统清晰结构** — 内容提要+7条学习目标+对比表 | 梁振光 |
| 4 | **四阶段演进脉络** — 萌芽→形成→体系化→21世纪，双线 | 路宏敏 |
| 5 | **从现象到概念** — 日常引入→正式定义→深度案例 | 张亮 |
| 6 | **工程实用导向** — 每内容配工程场景和具体措施 | 张亮 |
| 7 | **大篇幅讲细讲透** — 每子节≥40KB | 用户 |
| 8 | **含数字实例** — 每节≥1个具体数字计算 | 通例 |
| 9 | **多标准并列定义** — 同时引用GB/T+IEC+IEEE+GJB | 梁振光+路宏敏 |
| 10 | **概念对比表** — 易混淆概念用多维对比表 | 梁振光 |
| 11 | **三级案例结构** — 经过+分析+启示三段式 | 用户+路宏敏 |
| 12 | **教学设问过渡** — 节间加设问/因果/转折过渡 | 通例 |
| 13 | **公式全编号** — 每个 `$$` 显示公式都必须有 `\tag{N-M}` 编号 | 用户 |

## Workflow

```
Phase 0:   大纲解析 → 章节分层树 (/tmp/outline.json)
Phase 0.5: 三书研读 → 写作指南生成 (output/writing-guide-ch{N}.md)
Phase 1:   kb-qa 检索 → 素材包
Phase 2:   内容类型判别 → 6种模式选一
Phase 3:   学术写作 → 遵守13条军规
Phase 4:   格式输出 → .md 或 .docx
Phase 4.5: 清理临时文件 + 图号核验 + 公式全编号检查
Phase 5:   质量核验 → 6要素 + 13维度自审
Phase 6:   版本提交 → git 每个功能单独commit
```

**Phase 0：大纲解析**

```bash
python3 scripts/parse_outline.py 大纲.docx -o /tmp/outline.json
```

支持 .docx、.md、/dev/stdin 三种输入。输出 JSON 含章/节/子节三级树。

**Phase 0.5：三书研读 → 写作指南 → 动笔**（铁律——不读三书不落笔）

每章写前必须执行以下5步流程：

```bash
# ── 标准入口 ──
# Step 1: 找到三本书对应内容并通读
# Step 2: 填写三书手法对比表
# Step 3: 标注三书共同盲区
# Step 4: 生成 writing-guide-ch{N}.md
# Step 5: 严格按指南写作
```

**Step 1：研读三书** — 每本至少读章首(前30%)+核心节(全部)+章末(后20%)

```bash
# 路宏敏第6章（接地—第6章）
wc -c /Users/huoli4844/Desktop/电磁兼容/处理后/工程电磁兼容第3版_路宏敏/优先级1-十二五规划教材_工程电磁兼容第3版_路宏敏.md
grep -n "第6章\|接地" /Users/huoli4844/Desktop/电磁兼容/处理后/工程电磁兼容第3版_路宏敏/优先级1-十二五规划教材_工程电磁兼容第3版_路宏敏.md | head -5

# 梁振光第5章（接地及搭接）
wc -c /Users/huoli4844/Desktop/电磁兼容/处理后/电磁兼容原理技术及应用第2版_梁振光/优先级4-十三五_电磁兼容原理技术及应用第2版_梁振光.md
grep -n "接地" /Users/huoli4844/Desktop/电磁兼容/处理后/电磁兼容原理技术及应用第2版_梁振光/优先级4-十三五_电磁兼容原理技术及应用第2版_梁振光.md | head -5

# 张亮第3章（接地与屏蔽）
wc -c /Users/huoli4844/Desktop/电磁兼容/处理后/电磁兼容EMC技术及应用实例详解_张亮/优先级2-电磁兼容EMC技术及应用实例详解-张亮.md
grep -n "接地" /Users/huoli4844/Desktop/电磁兼容/处理后/电磁兼容EMC技术及应用实例详解_张亮/优先级2-电磁兼容EMC技术及应用实例详解-张亮.md | head -5
```

注意：三本书的章号可能与本教材不同（如梁振光的搭接在5.5节），必须通过搜索关键词定位，而非机械按章号读取。详细命令见 `references/source-books-locations.md`。

**Step 2：填写三书手法对比表**（向用户汇报）

从8个维度对比：章首引入 / 概念定义深度 / 公式数量与使用 / 案例类型 / 表格使用 / 历史叙事 / 工程实用导向 / 独特亮点。

**Step 3：标注发挥空间**

分析三本书都有但写得不透的内容，形成3-5个发挥空间。

**Step 4：生成写作指南** — 文件 `output/writing-guide-ch{N}.md`

用模板 `templates/writing-guide-template.md`，至少包含：
- 研读分析（三书对应关系 + 8维度手法对比 + 发挥空间）
- 结构建议（每节字数 + 主导手法 + 素材来源）
- 每节写作指南（引入方式 + 要素 + 设问 + 案例建议）
- 素材清单（从三本书提取的具体数据/标准号/案例）
- **图量规划**（≥6~8张Mermaid，标注每张图号/位置/类型）
- 12条军规落实检查

完成后向用户汇报：`第N章写作指南已生成 → output/writing-guide-ch{N}.md`
汇报时列出三书手法对比表和发挥空间，**必须征得用户确认方向正确**后，再开始动笔。

第6章实战示例：详见 `output/writing-guide-ch6.md`（含完整的8维度对比+7Mermaid图规划+14条军规检查清单），可直接作为后续章节写作指南的参考模板。

**Step 5：按指南写作**

写作中随时回看指南。每写一节前先读该节指南。完稿后对照指南逐项检查「没有遗漏任何要素」。

**Phase 0.6：内容差距分析 —— 当章写完后感觉"单薄"时**

当用户反馈某章体量不足时，执行三书内容差距分析：

1. **搜索三本书的对应主题**：用 grep 命令在三本书中获取所有相关内容
2. **逐书阅读完整章节**：路宏敏优先（最详尽），张亮次之，梁振光最后
3. **编制定量对比表**：按公式/例题/Mermaid图/对比表/习题六个维度对比当前输出 vs 三本书
4. **标记三类素材**：✅已使用 / ⬜可补充 / ❌超范围
5. **估算补充量**：每项增加的行数/字节数→排列优先顺序
6. **确认内容天花板**——不是所有章都能达到104KB（第4章体量）。有些主题的核心公式就3-4个，补充方向：案例深度→对比表→工程经验值→Mermaid图

详见 `references/gap-analysis-checklist.md`。第5章实战示例：`output/第5章-搭接技术.md` 经本分析补充了8项（射频电阻公式/20种结构/π形滤波器失效分析/经验值讨论等），从40KB扩展到63KB/5张Mermaid图/32条公式。

**Phase 1~2：kb-qa 检索 + 内容类型判别**

```bash
python3 scripts/kb_search.py /知识库 "3.1 电磁骚扰源分类" --format material
python3 scripts/detect_content_type.py "1.1 发展历史"  # → 历史叙事型
```

内容类型：历史叙事型、概念解构型、原理推导型、系统组成型、分类枚举型、工程案例型、复合型。

**Phase 3：学术写作**

核心规则见 `references/chapter-writing-standard.md`。每节必须遵守 6 要素清单：
- [ ] 权威定义（多标准并列）
- [ ] 直观引入（第一段不是公式）
- [ ] 公式有编号 `\tag{N-M}`
- [ ] 公式后有"式中"变量解释
- [ ] 有含数字实例
- [ ] 有层次化习题

**Mermaid 图规范**：每章 ≥6 张；每图有图号+文字说明；使用 `%%{init: {"flowchart": {"useMaxWidth": false}}}%%` 防止 Obsidian 缩放。

**数学推导标准**：一律 L3 逐步推导（从第一性原理出发，无跳步）。六步结构：物理背景→数学建模→代入代换→关键运算→最终形式→物理阐释+数字例题。详见 `references/derivation-example-107.md`。

**Phase 4.5：自动质量检查** — 每章生成后**必须**运行（铁律——跳过本阶段属于质量事故）：

```bash
# 必须在每次write_file输出章节文件后立即执行
python3 scripts/post_generation_check.py output/第N章-*.md --fix --verbose
```

检查内容：
1. **公式LaTeX语法** — 花括号平衡、\left/\right对称、无空\frac、\begin/\end匹配
2. **公式全编号** — 每个`$$`显示公式必须有\tag、编号连续无重复无跳跃
3. **Mermaid图闭合** — 每个```mermaid必须有对应的```结束符
4. **常见LaTeX拼写错误** — omega/theta/epsilon/pi等常见误拼
5. **自动修复**（`--fix`）— 缺编号自动补、重复编号自动重新编号、跳跃自动修复

质量审计报告必须在每章完成后向用户汇报，格式：

```
📋 第N章 质量审计
━━━━━━━━━━━━━━━━━━━
公式:  XX条 (5-1~5-XX)  连续✅
Mermaid图: X张           闭合✅
LaTeX语法:               全部合法✅
例题: X个
━━━━━━━━━━━━━━━━━━━
```

如果审计发现问题，必须先用 `--fix` 修复，然后重新审计确认无误后，才能提交git。

**Phase 5：质量核验**（内容深度 — 已由 Phase 4.5 覆盖语法后，本阶段专注内容质量）

```bash
python3 scripts/verify_chapter.py output/第N章.md --verbose
```

五维检查：结构完整性 / 内容深度 / 数学推导 / 学术规范 / 去AI味。详见 `references/six-elements.md`。

**Phase 6：版本提交**

- 一个功能调整 = 一次 commit
- 提交说明必须有实质内容：`git diff --stat --cached` 后再写

## Key Commands

| 用途 | 命令 |
|:-----|:------|
| 大纲解析 | `python3 scripts/parse_outline.py 大纲.docx -o /tmp/outline.json` |
| KB搜索 | `python3 scripts/kb_search.py /kb \"关键词\" --format material` |
| 内容类型判断 | `python3 scripts/detect_content_type.py \"标题\" --has-formula yes` |
| 写作指令生成 | `python3 scripts/gen_prompt.py --outline /tmp/outline.json --kb-dir /kb --chapter 1 --section 1.1 -o /tmp/prompt.md` |
| 质量核验 | `python3 scripts/verify_chapter.py output/第N章.md` |
| 体量检查 | `wc -c output/第N章.md` |
| 公式全编号检查 | `python3 scripts/post_generation_check.py output/第N章.md --fix --verbose` | 首选：自动检查+修复 |
| 公式编号重排 | `python3 scripts/clean_formula_numbers.py output/第N章.md` | 当编号严重混乱（重复/跳跃/缺失）时使用，从头重排 |

**Common Pitfalls**

1. **添加大纲不存在的章节**（自行加"本章小结"等）→ 大纲之外一律不写
2. **直接复制 KB 模板结构**（"精准释义：…"原文搬进教材）→ KB是原料，教材是成品，必须二次加工
3. **公式漏编号** → 每个 `$$` 显示公式都必须有 `\tag{N-M}`。中间推导步骤、近似公式、换算关系均需编号。特别注意**例题解答中的中间计算步骤**（如数值代入计算δ/R_DC/R_s）也需要编号——它们虽是例题一部分，仍属"显示公式"
4. **公式 tag 与 $$ 同行** → `\tag{5-1}$$` 导致渲染失败。必须 `\n\tag{5-1}\n$$`（tag独占一行，闭合$$另起一行）
5. **直接覆写原文件** → 改技能/改章节文件前先 cp 备份，改好确认无误再替换正式文件
6. **Mermaid 图太小** → 加 `%%{init: {"flowchart": {"useMaxWidth": false}}}%%` 防止 Obsidian 缩放
7. **插入新图后图号冲突** → 在已有章节中插入新Mermaid图后，必须全局搜索 `图N-` 检查是否产生重复编号。插入→搜索→修正，三步闭环
8. **公式校验脚本误报** → grep `\\\\lef`/`\\\\righ` 会在 `\\\\left`/`\\\\right` 内部匹配子串——这是误报。公式语法检查应优先用 python3 的 `re` 模块而非纯字符串搜索
9. **写作指南不经用户确认直接开写** → 三书研读完成后生成writing-guide-ch{N}.md，**必须向用户展示三书手法对比表和发挥空间**，获确认后方可动笔。否则可能方向偏了白写
10. **自动修复脚本将\\tag放在$$外部** → `post_generation_check.py --fix` 的 `_fix_missing_tag` 曾错误地将 `\\tag{N-M}` 插入在 `$$` 之前而非内部，导致渲染失败。当前版本已修复该bug。如果发现 `\\tag` 行出现在 `$$` 之前，运行 `python3 scripts/fix_tag_placement.py output/第N章.md` 将其移回公式块内部
11. **clean_formula_numbers.py会截断文件** → 当编号严重混乱时使用 `clean_formula_numbers.py`，但该脚本会**删除所有原编号后重排**。使用前必须先 `cp` 备份原文件，确认重排后的公式总量正确再替换正式版本

## Reference Index

| 需要时加载 | 内容 |
|:-----------|:------|
| `references/volume-standards.md` | **体量铁律 + 13条军规逐项勾选清单 + 公式全编号检查** |
| `references/chapter-writing-standard.md` | **三书融合写作法 + 章首/正文/章末完整模板** |
| `references/chapter-writing-workflow.md` | **Phase 0.5 四步研读流程**（必读） |
| `references/textbook-style-guide.md` | 教材学术叙事风格指南（三本已出版教材分析） |
| `references/writing-patterns.md` | 6种内容类型完整写作示例 + 通用模板 |
| `references/six-elements.md` | 教材质量综合检查清单（13项+自审评分表） |
| `references/derivation-example-107.md` | L3逐步推导模板（107推导六步法） |
| `references/mermaid-guide.md` | Mermaid图绘制规范与注意事项 |
| `references/textbook-pipeline.md` | 教材编写管线整合指南 |
| `references/pitfalls.md` | 完整陷阱列表（23+条） |
| `references/changelog.md` | 版本更新历史 |
| `references/source-books-locations.md` | **三本参考教材源文件路径 + 各书对照表 + 关键内容来源对应** |
| `references/gap-analysis-checklist.md` | **Phase 0.6 三书内容差距分析检查清单 + 模板** |
