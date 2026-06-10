---
name: book-build
description: "Use when writing a professional textbook from an outline and a domain-wiki knowledge base. Strictly follows the outline structure, queries kb-qa for content, outputs Obsidian Markdown or Word .docx."
version: 2.6.0
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

## Setup（首次使用）

```bash
# 1. 创建项目目录
mkdir ~/Desktop/我的教材

# 2. 初始化项目（创建 book-build.yaml + input/ + output/ 及子目录）
python3 scripts/book_config.py --project ~/Desktop/我的教材 --setup

# 3. 编辑项目配置
#    vim ~/Desktop/我的教材/book-build.yaml
#    填入教材名、参考教材路径等

# 4. 把提纲文件放入 input/
#    cp 教材提纲.docx ~/Desktop/我的教材/input/

# 5. 启动写作
#    每次加载项目: cfg = Config(project_root="~/Desktop/我的教材")
```

- 用户提供教材大纲（.docx / .md / 纯文本），要求按大纲逐章编写
- 用户指定一个 domain-wiki 格式的知识库目录作为内容来源
- 用户输出要求为 .md（Obsidian）或 .docx（含可编辑 OMML 公式）

**前置条件**：知识库已用 file2md 转换完成，至少包含 20_正文/ 或 概念/KE/KP 目录。

## Design

教材编写是一个四层递进的知识转化过程：

**L1 — 素材层：** KB 搜索（kb_search.py）从知识库召回概念/知识点/知识要素等内容片段。每一节的素材来自多个源文件。

**L2 — 结构层：** 大纲解析确定章节树；内容类型判别（6种模式）选择写作结构；写作指令生成器（gen_prompt.py）综合大纲定位+素材+写作规则，生成每节的提示词。

**L3 — 写作层：** Agent 按提示词写出正文，遵守 13 条军规。每章必须经过"教材研读→写作指南→动笔"的 Phase 0.5 流程。写作指南存放在 `写作大纲/` 子目录下。

**L4 — 校验层：** 每章写完后经过 6 要素检查 + 13 维度自审评分 + 体量铁律验证。

**工作流模式**（`config.yaml` → `workflow.default_mode`）：
- **`fast`**（默认）：Phase 0（大纲解析）→ Phase 3（写作）→ Phase 4.5（质量检查）→ Phase 6（提交）。跳过教材研读（Phase 0.5）和内容差距分析（Phase 0.6）。
- **`full`**：保留完整的 11 Phase 管线。每章写前必须执行教材研读，写完后执行完整审计。

**配置层次**（双层覆盖）：
- **技能默认值**：`~/.hermes/skills/research/book-build/config.yaml`（工作流/体量/子目录模板）
- **项目配置**：`{project_root}/book-build.yaml`（教材名/参考教材路径/知识库路径）
- 项目配置覆盖技能默认值。`scripts/book_config.py(project_root=...)` 自动合并。

**零硬编码设计原则（冰点法则）**：
1. **不写路径** — 所有路径从 `config.yaml` → `book_config.py` 动态读取
2. **不写数量** — 不假设 `source_books` 有几本、`subdirs` 有几个。所有代码/文档/测试通过 `len(c.source_books)` 或遍历动态适配
3. **不写具体值到文档** — reference 文件和 SKILL.md 正文只讲方法论。示例用 `{book_a_author}` 等占位符，不出现领域特有术语
4. **不写具体值到测试** — 测试只断言结构（`isinstance`/`endswith`/`is not None`），不断言 config.yaml 中定义的具体文本/路径/数字
5. **不写领域词到通用方法** — 方法名和文档用"参考教材"而非"三书/路宏敏"

**项目目录结构**（config.yaml → project）：
```
{project.root}/
├── input/                       ← 教材提纲 docx 存放目录
│   └── 教材提纲.docx
└── output/                      ← 所有输出
    ├── 第N章-标题.md             ← 各章正文（直接放在 output/）
    ├── 写作大纲/                 ← 每章的写作指南（Phase 0.5 产出）
    │   └── writing-guide-chN.md
    ├── 案例/                     ← 独立案例文件（Phase 7 产出）
    │   └── 案例X-Y_标题.md
    ├── 实验/                     ← 独立实验文件（Phase 7 产出）
    │   └── 实验XX_名称.md
    └── 习题解答/                 ← 全书完成后统一处理的习题解答
        └── 第N章-习题解答.md
```

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
Phase 0.5: 教材研读 → 写作指南生成 (output/写作大纲/writing-guide-ch{N}.md)
Phase 1:   kb-qa 检索 → 素材包
Phase 2:   内容类型判别 → 6种模式选一
Phase 3:   学术写作 → 遵守13条军规
Phase 4:   格式输出 → .md 或 .docx
Phase 4.5: 清理临时文件 + 图号核验 + 公式全编号检查
Phase 5:   质量核验 → 6要素 + 13维度自审
Phase 6:   版本提交 → git 每个功能单独commit
Phase 7:   案例/实验扩展 — 按模板用delegate_task并行重写，写完后clean→renumber→audit三步修复
```

**Phase 0：大纲解析**

```bash
python3 scripts/parse_outline.py 大纲.docx -o /tmp/outline.json
```

支持 .docx、.md、/dev/stdin 三种输入。输出 JSON 含章/节/子节三级树。

**Phase 0.5：教材研读 → 写作指南 → 动笔**（铁律——不读参考教材不落笔）

每章写前必须执行以下5步流程：

```bash
# ── 标准入口 ──
# Step 1: 找到各教材对应内容并通读
# Step 2: 填写各教材手法对比表
# Step 3: 标注各教材共同盲区
# Step 4: 生成 writing-guide-ch{N}.md → output/写作大纲/
# Step 5: 严格按指南写作
```

**Step 1：研读参考教材** — 每本至少读章首(前30%)+核心节(全部)+章末(后20%)

```bash
# 通过 book_config.py 获取各教材路径后，grep 搜索对应关键词
# 路径在 config.yaml → source_books 中定义
python3 -c "from scripts.book_config import Config; c=Config()
for b in c.source_books:
    print(f'{b[\"author\"]}: {b[\"path\"]}')"

# 示例：搜索关键词
python3 -c "
from scripts.book_config import Config
c = Config()
import subprocess, sys
for b in c.source_books:
    r = subprocess.run(['grep', '-n', sys.argv[1], b['path']], capture_output=True, text=True, timeout=10)
    print(f'=== {b[\"author\"]} ===')
    print('\n'.join(r.stdout.strip().split(chr(10))[:5]))
" "关键词"
```

**Step 2：填写各教材手法对比表**（向用户汇报）

从8个维度对比：章首引入 / 概念定义深度 / 公式数量与使用 / 案例类型 / 表格使用 / 历史叙事 / 工程实用导向 / 独特亮点。

**各教材对标分析表**（推荐格式——量化可用素材，列数 = 实际配置的教材数）：

| 维度 | 教材1 | 教材2 | ... | 本教材定位 |
|:----|:------|:------|:---|:----------|
| **核心内容** | 概括 | 概括 | | 融合+大纲 |
| **结构优势** | 独有的组织方式 | 独有的组织方式 | | 主骨架+补充 |
| **体量对标** | XX KB | XX KB | | 目标XX KB |

**各教材定位**（Role Assignment —— 行数 = 实际配置的教材数）：

| 教材 | 角色 | 对应教材节段 |
|:----|:-----|:------------|
| （按 priority 最高者） | **主骨架** | §X.X~§X.X（理论/概念部分） |
| （次高者） | **补充**/细节 | §X.X（扩展/案例/软件部分） |
| （其余） | **辅助**/交叉参考 | §X.X（边缘/关联部分） |

这个对标分析表直接决定每节的素材来源分配——主骨架书提供70%以上基础内容，补充书提供案例/扩展内容。

**Step 3：标注发挥空间**

分析各教材都有但写得不透的内容，形成3-5个发挥空间。

**Step 4：生成写作指南** — 文件 `output/写作大纲/writing-guide-ch{N}.md`

用模板 `templates/writing-guide-template.md`，至少包含：
- 研读分析（各教材对应关系 + 8维度手法对比 + 发挥空间）
- 结构建议（每节字数 + 主导手法 + 素材来源）
- 每节写作指南（引入方式 + 要素 + 设问 + 案例建议）
- 素材清单（从各教材提取的具体数据/标准号/案例）
- **图量规划**（≥6~8张Mermaid，标注每张图号/位置/类型）
- 12条军规落实检查

完成后向用户汇报：`第N章写作指南已生成 → output/写作大纲/writing-guide-ch{N}.md`
汇报时列出各教材手法对比表和发挥空间。**如 config.yaml 中 `phase_0_5_auto: true`（默认），跳过用户确认直接进入 Step 5 动笔。**

第6章实战示例：详见 `output/写作大纲/writing-guide-ch6.md`（含完整的8维度对比+7Mermaid图规划+14条军规检查清单），可直接作为后续章节写作指南的参考模板。

**Step 5：按指南写作**

写作中随时回看指南。每写一节前先读该节指南。完稿后对照指南逐项检查「没有遗漏任何要素」。

**Phase 0.6：内容差距分析 —— 当章写完后感觉"单薄"时**

当用户反馈某章体量不足时，执行内容差距分析：

1. **搜索各教材的对应主题**：用 grep 命令在教材中获取所有相关内容
2. **逐书阅读完整章节**：按 priority 读（最高优先级的书最先）
3. **编制定量对比表**：按公式/例题/Mermaid图/对比表/习题六个维度对比当前输出 vs 各教材
4. **标记三类素材**：✅已使用 / ⬜可补充 / ❌超范围
5. **估算补充量**：每项增加的行数/字节数→排列优先顺序
6. **确认内容天花板**——不是所有章都能达到104KB（第4章体量）。有些主题的核心公式就3-4个，补充方向：案例深度→对比表→工程经验值→Mermaid图

详见 `references/gap-analysis-checklist.md`。第5章实战示例：`output/第5章-搭接技术.md` 经本分析补充了8项，从40KB扩展到63KB/5张Mermaid图/32条公式。

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

**7 项 Mermaid 语法校验**（修复前只查闭合的漏洞，现完整覆盖）：

| # | 检查项 | 检测内容 | 是否自动修复 |
|:-:|:-------|:---------|:-----------:|
| 1 | **图表类型合法性** | 首行关键字是否在已知类型白名单中 | 否 |
| 2 | **xychart-beta 关键字白名单** | 仅允许 `title`/`x-axis`/`y-axis`/`bar`/`line`，禁止 `bar-group-group` 等非法关键字 | ✅ 自动移除 |
| 3 | **flowchart 节点引号** | 标签含逗号/括号时必须用 `["label"]` 包裹 | 否 |
| 4 | **subgraph 标题特殊字符** | subgraph 标题中禁止括号/破折号/逗号（Obsidian 词法崩溃根因） | 否 |
| 5 | **emoji 禁令** | 节点标签中不得含 emoji（Obsidian渲染崩溃根因） | 否 |
| 6 | **`%%{init}` 格式** | 必须双引号JSON + 闭合 `}%%` | 否 |
| 7 | **classDef 定义覆盖** | 所有 `:::xxx` 引用必须有对应 `classDef` | 否 |

本脚本执行8类检查：
1. 公式LaTeX语法（花括号平衡、\\left/\\right对称、无空\\frac）
2. 公式全编号（每个$$块必须有\\tag，编号连续无重复无跳跃）
3. **Mermaid图语法校验（7项，详见上表）**
4. **Mermaid有图必有说明检查**（每个```mermaid后3行内须有*图N-X：描述*图注）
5. **Wikilink检查（教材禁止[[...]]交叉引用）**
6. **推导深度启发式检查**（连续3个公式前无推导词→告警）
7. 常见拼写错误检查
8. **自动修复管线**：缺编号→补编号、编号跳跃→重新编号、重复→去重、Mermaid非法关键字移除

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

**中间插入内容的编号风暴**（铁律）：任何在已有章节中间插入新内容（公式/例题/图/表）的行为都会导致后续所有编号偏移。**正确处理流程**：

1. **不要在插入时维护编号**——给新内容赋一个临时编号（如`\tag{7-99}`）
2. **所有插入完成后**，统一运行编号重排：`python3 scripts/renumber.py output/第N章.md`
3. **重排后的链路三步闭环**：
   a. 运行顺序重排 → 确认全部连续
   b. 更新文本引用（`式(N-X)`引用匹配新编号）
   c. 更新章末总览Mermaid图 + 要点列表 + 习题引用

```bash
# 编号重排的标准命令（统一入口）
python3 scripts/renumber.py output/第N章-*.md
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
语法平衡:  $$平衡✅  Mermaid平衡✅  \\tag{}在$$内部✅
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
| 大纲解析 | `python3 scripts/parse_outline.py 教材提纲.docx -o /tmp/outline.json` |
| KB搜索 | `python3 scripts/kb_search.py /kb "关键词" --format material` |
| 内容类型判断 | `python3 scripts/detect_content_type.py "标题" --has-formula yes` |
| 写作指令生成 | `python3 scripts/gen_prompt.py --outline /tmp/outline.json --kb-dir /kb --chapter 1 --section 1.1 -o /tmp/prompt.md` |
| 质量核验 | `python3 scripts/verify_chapter.py 第N章.md` |
| 体量检查 | `wc -c 第N章.md` |
| 公式全编号检查+修复 | `python3 scripts/post_generation_check.py 第N章.md --fix --verbose` | 首选：自动检查+修复（支持 --dir 目录模式） |
| 公式编号重排 | `python3 scripts/renumber.py 第N章.md` | 合并 fix_formula_numbers + clean_formula_numbers + fix_tag_placement 的统一入口 |
| 章节组装 | `python3 scripts/assemble_chapter.py 前/ --out 第N章.md --chapter N` | 将多节独立文件按大纲顺序组装为完整章 |
| 跨文件编号重排 | `python3 scripts/renumber_cross_file.py . --chapter N --fix` | 多个案例/实验文件间公式编号连续分配 |
| 目录质量检查 | `python3 scripts/post_generation_check.py . --dir --fix` | 扫描目录下所有 .md 一次性检查 |

> **路径说明**：以上命令均在 `output/` 目录下执行。config.yaml 中的 `project.output_dir` 定义了实际输出目录。子目录结构：`写作大纲/`、`案例/`、`实验/`、`习题解答/`。

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
python3 scripts/renumber.py output/第N章-*.md --chapter N
# 验证
python3 -c "import re, glob; text=''.join(open(f).read() for f in glob.glob('output/第N章-*.md')); tags=re.findall(r'tag\{N-\d+\}',text); ok=all(t==f'tag{{N-{i+1}}}' for i,t in enumerate(tags)); print(f'{\"✅\" if ok else \"❌\"} Tags sequential N-1~N-{len(tags)}')"
```

**Subagent delegation for content writing —— 不要用于写教材正文**：

实验证明（第8章实战）：delegate_task 写入的教材正文不包含`\tag{}`公式编号、不包含`*图N-X：`图注、不遵循`**例N-X**`格式。subagent无法继承当前会话的写作风格约定。因此：
- 教材正文必须由主Agent直接编写（write_file / patch）
- subagent只能用于：研读参考教材并输出摘要、收集素材、生成对比表、运行审计脚本、按模板扩展案例/实验文件
- 如果确实需要subagent写大批内容（如案例/实验），必须在context中**显式包含**以下格式约束：
  ```
  约束1: 每个$$显示公式后立即加独占一行的\tag{8-N}
  约束2: 每个Mermaid块后立即加*图8-N：描述*
  约束3: 每个**例8-N**使用双星号加粗
  约束4: 不要使用任何emoji字符
  ## Linked Files

  ## Formula Derivation Standard（公式推导铁律）

  **每个显示公式必须从物理原理出发逐步推导，禁止直接贴结果。**

  推导必须遵循**六步结构**（又称"L3逐步推导"——从第一性原理出发，无跳步）：

  | 步骤 | 内容 | 示例（基本方程） |
  |:----|:-----|:----------------|
  | ① **物理原理** | 说明该公式基于的物理定律/原理 | 电磁干扰三要素原理 |
  | ② **建模假设** | 列出简化假设条件 | 远场平面波、各向同性 |
  | ③ **原始方程** | 写出积分律/微分方程/定义式 | $P=G\cdot T$ |
  | ④ **数学代入** | 代入物理量/参数/边界条件 | $G(t,f,\theta)\to P_tG_tA_e$ |
  | ⑤ **导出结果** | 带编号的最终公式 | $L_{bf}=20\lg(4\pi r/\lambda)$ |
  | ⑥ **参数解释** | "式中" 逐变量说明含义和单位 | $r$ 为传播距离（m） |

  **常见推导深度不足场景**（第9章实战教训）：

  | 公式 | 错误写法 | 正确写法 |
  |:-----|:---------|:---------|
  | 基本方程 $M=P-S$ | 直接写"干扰裕度为 $M=P-S$" | 四步：三要素→源模型 $G$ → 传输模型 $T$ → 敏感模型 $S$ → 裕度 $M=P-S$ |
  | 自由空间损耗 $L_{bf}$ | 直接写"$L_{bf}=20\lg(4\pi r/\lambda)$" | Friis方程：功率密度 $S=P_t/(4\pi r^2)$ → 有效面积 $A_e=\lambda^2/(4\pi)$ → $P_r=P_t\lambda^2/(4\pi r)^2$ → 取dB |
  | 接收机灵敏度 $S_{min}$ | 直接写"$S_{min}=-174+NF+10\lg B+SNR_{min}$" | 热噪声 $kT_0=-174\text{dBm/Hz}$ → NF放大 → 带宽积分 → +SNR_min |

  **Phase 4.5/5 新增检查项**：每章完成后，`post_generation_check.py` 会自动运行推导深度启发式检查（检测连续3个公式前无推导词）。如触发告警，**手动抽查5个关键公式**是否包含至少①+⑤+⑥三步。

  ```bash
  # 推导深度检查——手动操作（无法自动化）
  # 1. 从章首抓前5个显示公式
  grep -n '^\$\$' output/第N章.md | head -10
  # 2. 对每个公式，确认其前一段有"推导""原理""根据""由"等推导标记词
  # 3. 若某公式前只有一句"[量]为：" 无任何推导文字 → 标记缺陷
  # 4. 修复：在公式前插入①~⑥推导步骤
  ```

  **去AI味审查**：完全无推导的公式链（公式A→公式B→公式C中间无任何物理说明）是AI写作的典型特征，必须补充推导文字。

1. **添加大纲不存在的章节**（自行加"本章小结"等）→ 大纲之外一律不写
2. **直接复制 KB 模板结构**（"精准释义：…"原文搬进教材）→ KB是原料，教材是成品，必须二次加工
3. **公式漏编号** → 每个 `$$` 显示公式都必须有 `\tag{N-M}`。中间推导步骤、近似公式、换算关系均需编号。特别注意**例题解答中的中间计算步骤**（如数值代入计算δ/R_DC/R_s）也需要编号——它们虽是例题一部分，仍属"显示公式"
4. **公式 tag 与 $$ 同行** → `\tag{5-1}$$` 导致渲染失败。必须 `\n\tag{5-1}\n$$`（tag独占一行，闭合$$另起一行）
5. **直接覆写原文件** → 改技能/改章节文件前先 cp 备份，改好确认无误再替换正式文件
6. **Mermaid 图太小** → 加 `%%{init: {"flowchart": {"useMaxWidth": false}}}%%` 防止 Obsidian 缩放
7. **插入新图后图号冲突** → 在已有章节中插入新Mermaid图后，必须全局搜索 `图N-` 检查是否产生重复编号。插入→搜索→修正，三步闭环
8. **公式校验脚本误报** → grep `\\\\lef`/`\\\\righ` 会在 `\\\\left`/`\\\\right` 内部匹配子串——这是误报。公式语法检查应优先用 python3 的 `re` 模块而非纯字符串搜索
9. **写作指南不经用户确认直接开写** → 教材研读完成后生成writing-guide-ch{N}.md，**默认直接动笔**（config.yaml 中 `phase_0_5_auto: true`）。如需用户确认改为 `false`。
10. **自动修复脚本将\\tag放在$$外部** → `post_generation_check.py --fix` 的 `_fix_missing_tag` 曾错误地将 `\\tag{N-M}` 插入在 `$$` 之前而非内部。当前版本已修复。如果发现 `\\tag` 行出现在 `$$` 之前，运行 `python3 scripts/renumber.py output/第N章.md` 统一修复。
11. **编号重排前未备份** → `renumber.py` 默认自动创建 `.bak` 备份，无需手动 `cp`。如果使用旧版 `fix_*.py` 系列脚本，必须手动备份。
12. **公式章号前缀写错（跨章素材污染）** → 从第N+1章素材复制公式时，`\tag{8-X}`容易被遗忘不改为当前章号。写完后必须扫描 `\tag{` 批量核对章号前缀
13. **在已有示例之间插入新例导致后续编号偏移** → 在例7-1和例7-2之间插入"例7-2"后，原例7-2~7-8全部偏移一位成为7-3~7-9。插入新例后必须：重排例题编号→更新文本引用→更新总览Mermaid→更新要点列表→更新习题引用，五步闭环
14. **章末总览Mermaid图引用滞后** → 例题/公式/图重排后，总览Mermaid图中的引用（如"例7-4/7-8 设计实例"）不会自动更新。必须在任何重排操作后检查该图的每一处引用
15. **单行`$$...$$`混淆状态机审计脚本** → 单行内写`$$\boxed{...}$$`（开闭在同一行）会使状态机审计脚本的`$$`计数漏掉该块，导致后续公式被误判为"tag在$$外"。审计脚本必须用正则`re.finditer(r'\$\$', text)`查找所有`$$`位置而非行状态机
16. **Mermaid图中emoji破坏Obsidian渲染** → `✅❌⚠️🔽➡️` 等emoji出现在Mermaid节点标签中会导致整图不渲染，且不同Obsidian版本表现不一致。Mermaid节点标签中永远使用纯文本替代符号（如"达标/不达标/注意/下降"），不得使用任何Unicode emoji字符。见 `references/mermaid-guide.md`

17. **逐条修复编号 = 引爆炸弹** → 在已有章节中间插入新内容后，如果逐条手动修复编号（把新例7-6改为7-6，再把原7-6改为7-7...），很容易中途出错且总览图引用不同步。**正确做法**：所有新内容用临时编号 → 全部插入完成后 → 运行一次顺序重排脚本扫描全部编号 → 同步更新引用。一步到位，不出错。

18. **子代理(Subagent)输出缺失编号系统** → `delegate_task` 的子代理写出的内容几乎不带 `\tag{}` 编号、`*图N-X：`图注、`式(N-X)`引用。子代理擅长写内容但不擅长维护编号体系。**策略**：子代理写纯内容（正文+公式块+图+Mermaid），编号和引用由母agent在内容合并后统一加。或者子代理的context中必须明确包含编号格式要求。

20. **xychart-beta 的非法关键字导致整图不渲染** → `bar-group-group` 不是合法Mermaid关键字。 `xychart-beta` 仅支持 `title`、`x-axis`、`y-axis`、`bar`、`line` 五个关键字。任何其他关键字（包括 `bar-group-group`）都会导致 Mermaid 解析器抛出错误、整图空白。多系列必须用多个 `bar` 或 `line` 语句分别声明，配合文字说明图例。

21. **Mermaid语法检查缺失（已修复在v2.3.0）** → 旧的 `post_generation_check.py` 只检查Mermaid图块的 `` ``` `` 闭合标签，不校验图内语法。修复后增加了6项检查：图表类型合法性、xychart-beta关键字白名单、flowchart节点引号、emoji禁令、`%%{init}`格式、classDef定义覆盖。

22. **subgraph标题含括号/破折号导致Mermaid整图不渲染** → Obsidian的Mermaid解析器在处理 `subgraph` 标题中的英文括号 `()`、中文括号 `（）`、中文破折号 `—` 时会产生 Lexical error，整张图空白。即使语法在标准Mermaid中有效，Obsidian特定版本的解析器不支持这些字符。修复：① 不修改subgraph名无法修复，因为问题在解析器层；② 将 subgraph 拆分为多个独立的 `graph LR` 或 `flowchart TD` 块，每个块标题用纯文字（无括号/破折号）；③ 用多个图块分别展示不同频率/方案的数据对比。详见 `references/mermaid-guide.md`。

23. **xychart-beta 在 Obsidian 中不支持多系列柱状图** → 即使语法正确（4个 `bar` 或 `line` 系列），Obsidian内置的Mermaid版本对 xychart-beta 的 Render 支持有限，多系列图表渲染为空白。修复：不要用 xychart-beta 做多系列对比，改用 `graph LR` 或 `flowchart TD` 的分组节点/颜色编码方式展示对比数据。

24. **子代理写出的\\tag{}在$$块外部** → `delegate_task` 的子代理写出的公式经常出现 `\\tag{2-XX}` 独占一行但在 `$$` 块外部的情况（孤立标签）。`post_generation_check.py` 的 `check_tag_placement()` 可检测此问题。修复：运行 `python3 scripts/renumber.py output/文件.md`。

25. **子代理不写公式的$$包装** → `delegate_task` 的子代理经常把显示公式写成纯文本 LaTeX。策略：子代理 context 中必须显式包含约束。如果文件已写完发现公式缺 `$$`，需手动补 `$$` 包裹。

26. **配置数量假设** → 不要假设 `source_books` 一定有 3 本、`subdirs` 一定有某个子目录。所有遍历用 `c.source_books` 动态迭代，文档/表格中不出现"书A/书B/书C"固定角色名，测试不断言 `len >= 3`。

## Reference Index

| 需要时加载 | 内容 |
|:-----------|:------|
| `references/case-writing-template.md` | **8大模块案例编写模板** — 工程背景→测试诊断→根因分析(6步推导)→方案设计→验证→经验→拓展→思考题 |
| `references/experiment-writing-standard.md` | **实验编写标准（8章节高质量实验指导书）** — 目的→原理→设备→步骤→数据→分析→思考→注意事项 |
| `references/volume-standards.md` | **体量铁律 + 13条军规逐项勾选清单 + 公式全编号检查** |
| `references/chapter-writing-standard.md` | **三教材融合写作法 + 章首/正文/章末完整模板** |
| `references/chapter-writing-workflow.md` | **Phase 0.5 五步研读流程**（必读） |
| `references/textbook-style-guide.md` | 教材学术叙事风格指南 |
| `references/writing-patterns.md` | 6种内容类型完整写作示例 + 通用模板 |
| `references/six-elements.md` | 教材质量综合检查清单（13项+自审评分表） |
| `references/derivation-example-107.md` | **L3逐步推导模板（107推导六步法）** |
| `references/formula-derivation-standard.md` | **公式推导铁律 + 六步结构详解 + 4个实战实例 + 审计规则** |
| `references/mermaid-guide.md` | Mermaid图绘制规范与注意事项 |
| `references/mermaid-troubleshooting.md` | **Mermaid错误排查速查表（Obsidian版）** — 错误信号→根因→修复方案 |
| `references/pitfalls.md` | 完整陷阱列表（35+条） |
| `references/changelog.md` | 版本更新历史 |
| `references/source-books-locations.md` | 参考教材源文件路径与搜索方法 |
| `references/six-dimension-audit.md` | **六维编号审计脚本 + 常见失败场景 + 链路风暴修复** |
| `references/kb-enrichment-workflow.md` | **KB素材扩展工作流** — 写作前多轮搜索KB获取素材，含Ch9实案例 |
