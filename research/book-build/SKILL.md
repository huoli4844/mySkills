---
name: book-build
description: "Use when writing a professional textbook from an outline and a domain-wiki knowledge base. Strictly follows the outline structure, queries kb-qa for content, outputs Obsidian Markdown or Word .docx."
version: 2.0.0
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

**Phase 0.5：三书研读**

每章写前必须执行四步流程：① 通读三本参考教材对应章节；② 填写三书手法对比表；③ 标注三书共同盲区（发挥空间）；④ 生成该章专用写作指南。详见 `references/chapter-writing-workflow.md`。

**体量铁律**：每章字节数 ≥ 第1章 × (5~10)。写前用 `wc -c` 验算。示例：第1章=83KB → 第2章≥415KB。

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

**Phase 4.5：清理与验证**

```bash
# 清理临时文件
rm -f output/section-*.md /tmp/*.md
# 图号核验
grep -n '图N-' output/第N章.md | grep -v '图N-M'  # 无重复
# 公式全编号检查
python3 -c "import re; c=open('output/第N章.md').read(); eqs=re.findall(r'\$\$[^$]+\$\$',c); tags=re.findall(r'\\\\tag\{',c); assert len(eqs)==len(tags), f'缺失{len(eqs)-len(tags)}个编号'"
```

**Phase 5：质量核验**

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
| 公式全编号 | `python3 -c \"import re; c=open('output/第N章.md').read(); eqs=re.findall(r'\$\$[^$]+\$\$',c); tags=re.findall(r'\\\\tag\{',c); print(f'{len(eqs)}公式/{len(tags)}已编号'); assert len(eqs)==len(tags)\"` |

## Common Pitfalls

1. **添加大纲不存在的章节**（自行加"本章小结"等）→ 大纲之外一律不写
2. **直接复制 KB 模板结构**（"精准释义：…"原文搬进教材）→ KB是原料，教材是成品，必须二次加工
3. **公式漏编号** → 每个 `$$` 显示公式都必须有 `\tag{N-M}`。中间推导步骤、近似公式、换算关系均需编号
4. **观测性 Mermaid 图太小** → 加 `%%{init: {"flowchart": {"useMaxWidth": false}}}%%` 防止 Obsidian 缩放
5. **体量不足** → 每章必须 ≥ 第1章×5 字节。补救策略：加案例→加对比表→加公式推导→加数字例题

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
