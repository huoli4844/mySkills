---
name: book-build
description: "Use when writing a professional textbook from an outline and a domain-wiki knowledge base. Strictly follows the outline structure, queries kb-qa for content, outputs Obsidian Markdown or Word .docx."
version: 2.2.0
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

**核心原则**：教材是学术作品，不是知识库的复制品。KB是原料，教材是成品——必须重新组织为自然叙述的学术散文，不能把知识库中的模板结构（YAML frontmatter、`精准释义：`格式等）复制到正文中。

**13 条写作军规**（完整版加载 `references/volume-standards.md`）：

| # | 军规 | 来源 |
|:-:|:-----|:-----|
| 1 | **详实案例驱动** — 13个案例，每个有具体时间/地点/数字/分析 | 路宏敏 |
| 2 | **历史极致细节** — 具体日期+组织全称(含英文)+里程碑 | 路宏敏 |
| 3 | **系统清晰结构** — 内容提要+7条学习目标+对比表 | 梁振光 |
| 4 | **四阶段演进脉络** — 萌芽→形成→体系化→21世纪，双线 | 路宏敏 |
| 5 | **从现象到概念** — 日常引入→正式定义→深度案例 | 张亮 |
| 6 | **工程实用导向** — 每内容配工程场景和具体措施 | 张亮 |
| 7 | **每章≥80KB正文 / ≥100KB总量** — 对标路宏敏各章100KB/1500行的水平。初次写完若仅30~50KB，执行Phanse 0.6差距分析后扩充 | 用户 |
| 8 | **含数字实例** — 每节≥1个具体数字计算 | 通例 |
| 9 | **多标准并列定义** — 同时引用GB/T+IEC+IEEE+GJB | 梁振光+路宏敏 |
| 10 | **概念对比表** — 易混淆概念用多维对比表 | 梁振光 |
| 11 | **三级案例结构** — 经过+分析+启示三段式 | 用户+路宏敏 |
| 12 | **教学设问过渡** — 节间加设问/因果/转折过渡 | 通例 |
| 13 | **公式全编号** — 每个 `$$` 显示公式都必须有 `\\tag{N-M}` 编号 | 用户 |
| 14 | **不添加wikilink** — 教材正文中不加 `[[wikilink]]` 导航或交叉引用（除非用户明确要求），保持学术读物的纯净性 | 用户 |

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

**三书对标分析表**（推荐格式——量化三书可用素材）：

| 维度 | 书A（如柯金良第X章） | 书B（如路宏敏第X章） | 本教材定位 |
|:----|:-------------------|:-------------------|:----------|
| **核心内容** | 一句话概括该章 | 一句话概括该章 | 融合两者+大纲 |
| **结构优势** | A独有的组织方式 | B独有的组织方式 | 以A为主干+B补充 |
| **体量对标** | XX KB | XX KB | 目标XX~XX KB |

**三书定位**（Role Assignment）：

| 书 | 角色 | 对应教材节段 |
|:---|:-----|:------------|
| 书A | **主骨架** | §X.X~§X.X（理论/概念部分） |
| 书B | **补充**/细节 | §X.X（扩展/案例/软件部分） |
| 书C | **辅助**/交叉参考 | §X.X（边缘/关联部分） |

这个对标分析表直接决定每节的素材来源分配——主骨架书提供70%以上基础内容，补充书提供案例/扩展内容。

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

写作前，先用 kb_search.py 对每一节的关键词在知识库中做多轮搜索，获取权威定义、公式和案例素材。详见 `references/kb-enrichment-workflow.md`。

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

### 六维编号审计（铁律——写完后必须逐项执行）

每章生成后、提交git前，**必须**逐项检查以下全部六个编号系统。任何一个出问题都不能提交。

```bash
# 统一审计脚本（一次性检查全部编号系统）
python3 -c "
import re
with open('output/第{N}章-*.md','r') as f: text = f.read()
# 1) 公式 tags: 检查连续性 + 章号前缀
tags = re.findall(r'\\\\tag\{(\d+-\d+)\}', text)
for i,t in enumerate(tags):
    ch,num = t.split('-')
    assert int(num)==i+1, f'公式编号不连续: 期待{N}-{i+1}, 实际{t}'
    assert ch==str(N), f'公式章号错误: 期待{N}-X, 实际{t}'
# 2) 图 captions
figs = re.findall(r'\*图(\d+-\d+)', text)
for i,f in enumerate(figs):
    assert f==f'{N}-{i+1}', f'图号错误: 期待{N}-{i+1}, 实际{f}'
# 3) 例题 numbering
exs = re.findall(r'\*\*例(\d+-\d+)', text)
for i,e in enumerate(exs):
    assert e==f'{N}-{i+1}', f'例题号错误: 期待{N}-{i+1}, 实际{e}'
# 4) 表 numbering
tbls = re.findall(r'\*\*表(\d+-\d+)', text)
for i,t in enumerate(tbls):
    assert t==f'{N}-{i+1}', f'表号错误: 期待{N}-{i+1}, 实际{t}'
# 5) 文本引用 vs 实际定义的一致性
refs = set(re.findall(r'式\((\d+-\d+)\)', text))
tag_set = set(tags)
miss = refs - tag_set
assert not miss, f'公式引用指向不存在编号: {miss}'
# 6) 章末总览Mermaid图中的引用——确认摘要图里的例号/公式号也正确
overview = text.split('本章知识结构总览')[0] if '本章知识结构总览' in text else ''
summary_refs = set(re.findall(r'例(\d+-\d+)', overview))
examples = set(e for e in exs)
miss_ex = summary_refs - examples
assert not miss_ex, f'总览图引用不存在的例题: {miss_ex}'
print('✅ 六维编号审计全部通过')
"
```

**六维检查内容明细：**

| # | 检查项 | 检查内容 | 常见失败场景 |
|:-:|:-------|:---------|:------------|
| 1 | **公式章号前缀** | 每个`\tag{7-X}`的章号必须正确 | 从第8章素材抄来却写成`8-X` |
| 2 | **公式编号连续性** | 全部`\tag{}`必须连续无间隔 | 删除中间公式后未重排 |
| 3 | **图编号连续性** | 全部`*图N-X：`必须连续 | 插入新Mermaid图后产生重复号 |
| 4 | **例题编号连续性** | 全部`**例N-X**`必须连续 | 在已有例之间插入新例导致后续偏移 |
| 5 | **表编号连续性** | 全部`**表N-X：**`必须连续 | 插入新表后未重排 |
| 6 | **总览图引用一致** | 章末总览Mermaid中的例号/公式号与实际一致 | 例题重排后摘要图未同步 |

> **重新编号后的链路风暴**：任何编号重排（公式/图/例/表）都会导致以下4类引用失效，必须全部同步更新：
> 1. 文本中的`式(N-X)`、`图N-X`、`见例N-X`等引用
> 2. 章末总览Mermaid图中的引用
> 3. 章末要点列表中的引用
> 4. 习题中的引用（如\"用式N-X计算\"）
>
> 修复策略：重排后立即用 `python3 scripts/fix_all_cross_refs.py output/第N章.md --old N --new N` 统一扫描替换。

**中间插入内容的编号风暴**（新增铁律）：任何在已有章节中间插入新内容（公式/例题/图/表）的行为都会导致后续所有编号偏移。**正确处理流程**：

1. **不要在插入时维护编号**——给新内容赋一个临时编号（如`\tag{7-99}`）
2. **所有插入完成后**，统一运行编号重排脚本
3. **重排后的链路三步闭环**：
   a. 运行顺序重排 → 确认全部连续
   b. 更新文本引用（`式(N-X)`引用匹配新编号）
   c. 更新章末总览Mermaid图 + 要点列表 + 习题引用

```bash
# 编号重排的标准三步曲
# Step 1: 重排全部\标签（公式/图/例独立执行）
python3 -c "
import re
# 读取文件
with open('output/第N章-*.md','r') as f: lines = f.readlines()

# 按文件出现顺序逐类重排
# 公式重排示例（提取所有\\tag{N-X}，按位置重排）
tags_found = []
for _,line in enumerate(lines,1):
    for m in re.finditer(r'\\\\tag\{\d+-\d+\}', line):
        tags_found.append((_, m.group()))

# Step 2: 全局替换引用
# Step 3: 检查总览图
"
```

**质量审计报告模板**（铁律——每章完成后必须向用户汇报，使用以下格式）：

```
📋 第N章 质量审计
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
公式编号:  XX个 (N-1~N-XX)  连续✅ | 章号前缀✅
公式引用:  XX个             全部有定义✅
图编号:    XX张 (N-1~N-XX)  连续✅
例题编号:  XX个 (N-1~N-XX)  连续✅
表编号:    XX个 (N-1~N-XX)  连续✅
语法平衡:  $$平衡✅  Mermaid平衡✅
Mermaid emoji: 0处✅
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
体量:  XX行 / XXKB / XX公式 / XX图 / XX例
```

**自动修复**（`--fix`）— 缺编号自动补、重复编号自动重新编号、跳跃自动修复。

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

**Quality baseline — actual benchmark volumes from this project**（写完后对照）:

| 章节 | 行数 | KB | 公式 | 图 | 例 |
|:----|:----:|:--:|:---:|:-:|:-:|
| 第4章 耦合途径（标杆） | ~1800 | 104 | 97 | 6 | 21 |
| 第6章 接地技术 | ~1100 | 60 | 42 | 11 | 6 |
| 第7章 滤波技术 | ~940 | 53 | 34 | 9 | 11 |
| 第8章 屏蔽技术 | ~1336 | 81 | 67 | 6 | 11 |
| 偏薄阈值 | <700 | <35 | — | — | — |

**Intermediate-insertion numbering storm protocol**（新增——任何在已有章节中间插入新内容时强制使用）:

当需要在已有章节中**中间插入**新公式/例题/图时，后续所有编号都会偏移。**正确流程**：

1. 给新内容赋**临时编号**（如`\tag{7-99}`、`**例7-99**`）
2. **全部插入完成后**，统一运行编号重排
3. 重排后的**四步闭环**：
   a. 公式tags顺序重排
   b. 例题编号顺序重排  
   c. 图号顺序重排
   d. 更新章末总览Mermaid中的引用 + 要点列表 + 习题引用

```bash
# 公式重排的标准命令（已验证）
python3 -c "
import re
with open('output/第N章-*.md','r') as f: content = f.read()
tag_pattern = re.compile(r'\\\\tag\{\d+-\d+\}')
matches = [(m.start(), m.end()) for m in tag_pattern.finditer(content)]
new_content = list(content)
offset = 0
for i, (start, end) in enumerate(matches):
    new_tag = f'\\\\tag{{{N}-{i+1}}}'
    adj_start = start + offset
    adj_end = end + offset
    new_content[adj_start:adj_end] = list(new_tag)
    offset += len(new_tag) - (end - start)
with open('output/第N章-*.md','w') as f: f.write(''.join(new_content))
# Verify
tags = re.findall(r'\\\\tag\{\d+-\d+\}', ''.join(new_content))
ok = all(t==f'\\\\tag{{{N}-{i+1}}}' for i,t in enumerate(tags))
print(f'✅ Tags sequential {N}-1~{N}-{len(tags)}' if ok else '❌ FAIL')
"
```

**Subagent delegation for content writing —— 不要用于写教材正文**：

实验证明（第8章实战）：delegate_task 写入的教材正文不包含`\tag{}`公式编号、不包含`*图N-X：`图注、不遵循`**例N-X**`格式。subagent无法继承当前会话的写作风格约定。因此：
- 教材正文必须由主Agent直接编写（write_file / patch）
- subagent只能用于：研读三书并输出摘要、收集素材、生成对比表、运行审计脚本
- 如果确实需要subagent写大批内容，必须在context中**显式包含**以下格式约束：
  ```
  约束1: 每个$$显示公式后立即加独占一行的\tag{8-N}
  约束2: 每个Mermaid块后立即加*图8-N：描述*
  约束3: 每个**例8-N**使用双星号加粗
  约束4: 不要使用任何emoji字符
  ```

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
12. **公式章号前缀写错（跨章素材污染）** → 从第N+1章素材复制公式时，`\tag{8-X}`容易被遗忘不改为当前章号。写完后必须扫描 `\tag{` 批量核对章号前缀
13. **在已有示例之间插入新例导致后续编号偏移** → 在例7-1和例7-2之间插入"例7-2"后，原例7-2~7-8全部偏移一位成为7-3~7-9。插入新例后必须：重排例题编号→更新文本引用→更新总览Mermaid→更新要点列表→更新习题引用，五步闭环
14. **章末总览Mermaid图引用滞后** → 例题/公式/图重排后，总览Mermaid图中的引用（如"例7-4/7-8 设计实例"）不会自动更新。必须在任何重排操作后检查该图的每一处引用
15. **单行`$$...$$`混淆状态机审计脚本** → 单行内写`$$\boxed{...}$$`（开闭在同一行）会使状态机审计脚本的`$$`计数漏掉该块，导致后续公式被误判为"tag在$$外"。审计脚本必须用正则`re.finditer(r'\$\$', text)`查找所有`$$`位置而非行状态机
16. **Mermaid图中emoji破坏Obsidian渲染** → `✅❌⚠️🔽➡️` 等emoji出现在Mermaid节点标签中会导致整图不渲染，且不同Obsidian版本表现不一致。Mermaid节点标签中永远使用纯文本替代符号（如"达标/不达标/注意/下降"），不得使用任何Unicode emoji字符。见 `references/mermaid-guide.md`

17. **逐条修复编号 = 引爆炸弹** → 在已有章节中间插入新内容后，如果逐条手动修复编号（把新例7-6改为7-6，再把原7-6改为7-7...），很容易中途出错且总览图引用不同步。**正确做法**：所有新内容用临时编号 → 全部插入完成后 → 运行一次顺序重排脚本扫描全部编号 → 同步更新引用。一步到位，不出错。

18. **子代理(Subagent)输出缺失编号系统** → `delegate_task` 的子代理写出的内容几乎不带 `\tag{}` 编号、`*图N-X：`图注、`式(N-X)`引用。子代理擅长写内容但不擅长维护编号体系。**策略**：子代理写纯内容（正文+公式块+图+Mermaid），编号和引用由母agent在内容合并后统一加。或者子代理的context中必须明确包含编号格式要求。

19. **初次写作体量不足时，不要重写，要扩充** → 写完第一版后发现只有30~50KB（偏薄），正确的做法不是删除重写，而是执行Phase 0.6差距分析找出缺失内容后，用patch在现有框架中插入新内容，最后统一重排编号。经验数据：初次写30~40KB → 插入补充后可到60~100KB。

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
| `references/pitfalls.md` | 完整陷阱列表（35+条） |
| `references/changelog.md` | 版本更新历史 |
| `references/source-books-locations.md` | **三本参考教材源文件路径 + 各书对照表 + 关键内容来源对应** |
| `references/six-dimension-audit.md` | **六维编号审计脚本 + 常见失败场景 + 链路风暴修复** |
| `references/kb-enrichment-workflow.md` | **KB素材扩展工作流** — 写作前多轮搜索KB获取素材，含Ch9实案例 |
