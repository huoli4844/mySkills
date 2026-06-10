#!/usr/bin/env python3
"""
generate_outlines.py — 从提纲文档 + 参考书目生成每章写作大纲。

流程：
  1. 读取项目配置（教材名、提纲文件、参考书路径）
  2. 解析提纲文件，提取纲目结构（各章名称和L1节）
  3. 对每章，用 delegate_task 委托 Agent：
     a. 读取参考书对应章节内容
     b. 分析各教材的写作手法和内容侧重
     c. 生成写作大纲（含子节结构、建议体量、素材来源）
  4. 将大纲写入 output/写作大纲/writing-guide-chX.md

用法：
  python3 scripts/generate_outlines.py --project /path/to/教材
  python3 scripts/generate_outlines.py --project /path/to/教材 --chapter 3   # 只生成第3章
"""

import os
import re
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Optional


CHAPTER_TEMPLATE = """# 第{ch}章 {title} 写作指南

> ⚠️ **质量宣言**：以下所有板块必须全部填充，不得有`[具体说明]`、`[要素X]`等占位符。
> 填充完成后运行 `ls -la` 确认文件≥35KB，`grep -c "具体说明"` 结果为0。
> **大纲有多厚，章节就有多厚**——这是控制章节体量的关键杠杆。

## ⚠️ 格式规范（创作前必读）

创作时请严格遵守以下格式，避免写完后大量返工。

### 公式写法
- **行内公式**：用单 `$` 包裹，如 `$E = mc^2$`
- **块级公式**：用 `$$` 包围，编号 `\\tag{{章-序号}}` **独占一行**，放在闭合 `$$` **之前**
  ```markdown
  $$
  IL = 20 \\log(U_1/U_2)
  \\tag{{7-4}}
  $$
  ```
- **核心公式必须给出推导过程**：按"物理原理→建模假设→数学代入→导出结果→参数解释"五步展开。推导不少于4步，每一步配文字说明。例如分贝换算公式（dBm↔dBuV），需要从功率定义出发经至少三步代数推导得到最终快捷公式。
- **辅助公式直接给出**：中间步骤、已知公式变体等不自创编号。
- **引用块内公式**：每行加 `>` 前缀
  ```markdown
  > $$
  > IL = 20 \\log(U_1/U_2)
  > \\tag{{7-4}}
  > $$
  ```

### Mermaid 图写法
- **只能用** `graph TD`（竖向）或 `graph LR`（横向）
- **禁止使用**：`timeline`、`mindmap`、`%%{{init}}%%`、`<-->`（双向箭头）、`subgraph`（跨边界连接）
- **禁止在标签中使用**：emoji（`🔄` `⚠️` etc）、星号（`⭐`）、特殊 Unicode
- 节点标签用双引号包裹：`A["标签文字"]`
- **换行用 `<br>`**（不是 `\n`）：`A["第一行<br>第二行"]` ✅
- **简单连接**用 `A --> B`，虚线用 `A -.-> B`

### 图注与表题写法（学术规范）
- **图注在图的下方**：用斜体 `*图章-序号：标题*`，放在Mermaid图或图片的**下一行**
  ```markdown
  ```mermaid
  graph TD
      A --> B
  ```
  *图7-1 滤波器原理示意图*
  ```
- **表题在表的上方**：用粗体 `**表章-序号：标题**`，放在Markdown表格的**上一行**
  ```markdown
  **表7-1 滤波器类型对比**
  | 类型 | 特点 |
  |:-----|:-----|
  | 低通 | 通过低频 |
  ```
- 表格必须带对齐标记：`|:--|:--:|--:|`

### 禁止写入的内容
- ❌ `## 本章写作说明`、`12条军规落实检查`、`全章核心公式总结`
- ❌ Bloom 分类标签（`**记忆层**`、`**理解层**`）

---

## 各教材章节对应关系

| 本章拟定节号 | 路宏敏 | 张亮 | 柯金良 | 梁振光 |
|:------------|:-------|:-----|:-------|:-------|
| {ch}.1 [标题] | 对应路宏敏第几章哪节 | 对应张亮第几章哪节 | 对应柯金良第几章哪节 | 对应梁振光第几章哪节 |
| {ch}.2 [标题] |  |  |  |  |

## 各教材写作手法对比表

| 对比维度 | 路宏敏 | 张亮 | 柯金良 | 梁振光 |
|:---------|:-------|:-----|:-------|:-------|
| **核心手法** |  |  |  |  |
| **开篇方式** |  |  |  |  |
| **案例运用** |  |  |  |  |
| **术语处理** |  |  |  |  |
| **历史脉络** |  |  |  |  |
| **理论深度** |  |  |  |  |
| **结构复杂度** |  |  |  |  |
| **可读性** |  |  |  |  |
| **适用读者** |  |  |  |  |

## 各书最值得借鉴的3个手法

### 路宏敏
1. **[手法名]**：[具体说明，为什么好，如何借鉴]
2. **[手法名]**：[具体说明]
3. **[手法名]**：[具体说明]

### 张亮
1. **[手法名]**：[具体说明，为什么好，如何借鉴]
2. **[手法名]**：[具体说明]
3. **[手法名]**：[具体说明]

### 柯金良
1. **[手法名]**：[具体说明，为什么好，如何借鉴]
2. **[手法名]**：[具体说明]
3. **[手法名]**：[具体说明]

### 梁振光
1. **[手法名]**：[具体说明，为什么好，如何借鉴]
2. **[手法名]**：[具体说明]
3. **[手法名]**：[具体说明]

## 各教材共同盲区（发挥空间）

| 盲区 | 具体表现 | 我们的发挥空间 |
|:-----|:---------|:-------------|
| **[盲区1]** | 各教材都漏了什么 | 我们可以补充什么、放在哪节 |
| **[盲区2]** | 各教材都漏了什么 | 我们可以补充什么、放在哪节 |

> 盲区应包含两类：①技术性盲区（缺数学模型、缺对比表、缺可视化等具体内容缺失）
> ②教学性盲区（前沿缺失、职业导向、费效比分析等 pedagogical 提升空间）

## 本章定位

本章是全书的总纲与导引，肩负四大使命：
1. **建立学习动机**：[通过什么案例建立学习动机]
2. **奠定概念基础**：[精确定义哪些核心概念]
3. **绘制学科全景**：[介绍哪些内容，帮助读者建立什么认知]
4. **指引学习路径**：[说明与前后章的关系]

**读者画像**：[目标读者群体、前修课程基础]
**本章篇幅**：控制在XX~XX页（含图表），约占全书X%~X%。

## 学习目标与内容覆盖映射

每一条学习目标必须能被正文内容覆盖。请在填写结构建议表后，逐条确认：

| # | 学习目标 | 对应的正文节号 | 落实情况 |
|:-:|:---------|:--------------|:--------:|
| 1 | [目标1内容] | §X.X, §X.X | 必填 |
| 2 | [目标2内容] | §X.X, §X.X | 必填 |
| 3 | [目标3内容] | §X.X, §X.X | 必填 |
| 4 | [目标4内容] | §X.X, §X.X | 必填 |
| 5 | [目标5内容] | §X.X, §X.X | 必填 |

> 每一条学习目标必须至少对应一个章节。如果某目标没有对应的正文内容，则需补充对应章节或修改学习目标。

## ⚠️ 写作原则：借鉴手法，不照搬内容

参考教材是学习写作手法的**老师**，不是摘抄内容的**仓库**。

**正确做法**：
- ✅ 阅读各教材对应章节，理解其**写作逻辑**（为什么先讲这个再讲那个、用什么案例引出概念）
- ✅ 参考其**数据、标准号、定义原文**（这些是事实性知识，可以引用并注明出处）
- ✅ 将多本教材的内容**融合提炼**，用自己的语言重新组织

**错误做法**：
- ❌ 从某一本教材中直接复制段落甚至整节内容
- ❌ 仅把多本教材的内容"拼接"在一起，没有自己的分析视角
- ❌ 案例从参考教材中摘抄（案例必须来自公开报道的真实事件）

**检验标准**：写成的内容应该看起来像"一位教授理解了多本书后自己写的"，而不是"从多本书里剪贴出来的"。

## 结构建议

| 大纲节号 | 标题 | 建议体量 | 主导手法 | 主要素材来源 |
|:--------|:----|:--------:|:---------|:------------|
| {ch}.1 | [标题] | KB | [写作手法概述] | [参考教材哪些节] |
| {ch}.2 | [标题] | KB | [写作手法概述] | [参考教材哪些节] |
| {ch}.3 | [标题] | KB | [写作手法概述] | [参考教材哪些节] |
| **总计** |  | **KB** |  |  |

## 章末必含板块（以下内容必须在章末出现，缺一不可）

| 板块 | 要求 | 位置 |
|:-----|:-----|:-----|
| **本章总结** | Mermaid知识结构图 + 6~9个核心要点表（含公式编号引用） | 习题之前 |
| **习题** | 基础题(3~5题)+进阶题(3~4题)+思考题(2~3题)，共8~12题 | 参考文献之前 |
| **参考文献** | 至少10篇，含参考教材+IEC/CISPR/GB标准+公开报告 | 深入阅读之前 |
| **深入阅读** | 3~6本，每本附100字以内推荐理由 | 全文末尾 |

## 技术深度专项要求

以下技术内容**必须**在正文中出现，缺一不可：

| 技术项 | 第1章要求 | 后续各章要求 |
|:-------|:---------|:------------|
| **电尺寸概念** | 定义+公式$k=l/\lambda$+工程判据($\lambda/10$) | 在屏蔽/接地/滤波各章复用 |
| **窄带/宽带分类** | Giri分类法+百分比带宽公式+四类划分 | 在测量章复用 |
| **术语体系** | 至少10条核心术语（EMC/EMI/EMD/EMS/三要素/分贝/兼容裕度等） | 持续扩展 |
| **案例技术参数** | 每个案例至少含3个具体技术参数（频率/电压/距离/金额/数量等） | 每章保持 |
| **兼容电平图** | 发射限值/抗扰度限值/兼容电平的层次关系 | 在标准章深化 |

## 每节写作指南（创作时逐节填写）

### 第{ch}.1节 [标题]

**子节规划**：[本节应包含哪些子节，如"定义→三要素→数学模型→术语体系→设计方法"]

**写作手法**：[用什么手法写这节，如"日常现象引入→概念辨析→数学模型"]

**必须包含的要素**（3~8条，每一条都是一个知识点）：
- [要素1]：[一句话说明，含参考教材出处]
- [要素2]：[一句话说明，含参考教材出处]
- [要素3]：[一句话说明，含参考教材出处]

**建议的设问过渡**（不少于2句）：
- [前一段]→[后一段]之间："[过渡语句]"
- [前一段]→[后一段]之间："[过渡语句]"

**案例建议**（不少于2个）：
- [案例名]（用在哪个知识点后，从哪本书参考，含关键技术参数）

### 第{ch}.2节 [标题]

**写作手法**：[如"历史叙事法→时间线可视化"]

**必须包含的要素**：
- [要素1]：[一句话说明]
- [要素2]：[一句话说明]

**建议的设问过渡**：
- [前一段]→[后一段]之间："[过渡语句]"

**案例建议**：[这节应该用哪些案例]

### 量化底线（每节至少满足以下指标）

| 指标 | 每节最低要求 | 全章最低要求 |
|:----|:-----------|:-----------|
| **案例** | 每节至少2个（1生活化+1工程） | 全章至少8个 |
| **公式** | 每节至少1个编号公式 | 全章至少8个 |
| **必含要素** | 全部列入（见每节指南） | 全部落实 |
| **设问过渡** | 每节至少2句 | 全章至少8句 |

> **案例要求**：每个案例不少于150字，结构为"背景→技术分析→后果→启示"。必须来自公开报道真实事件，含公司名/时间/具体参数值（频率、电压、距离、金额等）。禁止从参考教材摘抄案例。
>
> **公式要求**：核心公式必须给出不少于4步的推导过程（物理原理→建模假设→数学代入→导出结果→参数解释）。辅助公式直接给出不自创编号。

### 扩展指引（Agent 填充每节时参考）

Agent 为每节补充以下三个维度，**大纲有多厚，章节就有多厚**——这是控制章节体量的关键杠杆。

**必含要素清单**：读者从这节必须掌握的知识点（3-8条）。例如"电磁骚扰与电磁干扰的因果关系辨析、三要素乘积模型 E_int(f)=S(f)*C(f)"。

**设问过渡**：本节末尾到下一节的衔接语句（1-2句，可直接用在正文中）。例如"从上面的辨析可以看出，EMI是EMD通过耦合途径作用于敏感设备的结果——由此引出三要素框架。"

**案例建议**：本节可用的真实案例（来自公开报道，非教材摘抄）。标注案例用在哪个知识点后面，含关键技术参数。每节至少1个案例。

### 章末板块填充指引（Agent 完善大纲时填充）

填充"本章总结"、"习题"、"参考文献"、"深入阅读"四个章末板块的内容：

**本章总结**：Mermaid知识结构图（展示各L1节间关系）+ 6~9个核心要点表格（每个要点含关键内容、对应公式编号、对应章节）。

**习题**：基础题(3~5题，概念理解) + 进阶题(3~4题，计算分析) + 思考题(2~3题，综合开放)。每题标注所属节号。

**参考文献**：至少10篇，含参考教材、IEC/CISPR/GB标准、公开报告、学术论文。

**深入阅读**：3~6本，每本附50~100字推荐理由，说明适合什么阶段读者阅读。

Agent 为每节补充以下三个维度，**大纲有多厚，章节就有多厚**——这是控制章节体量的关键杠杆。

**必含要素清单**：读者从这节必须掌握的知识点（3-8条）。例如"电磁骚扰与电磁干扰的因果关系辨析、三要素乘积模型 E_int(f)=S(f)*C(f)"。

**设问过渡**：本节末尾到下一节的衔接语句（1-2句，可直接用在正文中）。例如"从上面的辨析可以看出，EMI是EMD通过耦合途径作用于敏感设备的结果——由此引出三要素框架。"

**案例建议**：本节可用的真实案例（来自公开报道，非教材摘抄）。标注案例用在哪个知识点后面，含关键技术参数。每节至少1个案例。

### 填充示例（以第1章第1节为例）

```
### 第1.1节 电磁兼容定义内涵

**写作手法**：日常现象引入→EMD/EMI辨析→术语深度→三要素框架→数学模型

**必须包含的要素**：
- EMD与EMI的因果关系辨析，含GB/T 4365定义引用
- EMD与EMI多维度对比表（本质、因果角色、消除方式等8个维度）
- 电磁干扰三要素（骚扰源、耦合途径、敏感设备）
- 三要素乘积模型 E_int(f) = S(f)·C(f)
- 三类EMC设计策略（抑制源、切断途径、提高抗扰度）

**建议的设问过渡**：
- 日常案例→EMD定义之间："这些都是每一个人在日常生活中都曾遇到过的小'麻烦'，但它们背后指向的其实是同一个工程问题——电磁干扰。"
- EMD/EMI辨析→三要素之间："从上面的辨析可以看出，EMI是EMD通过耦合途径作用于敏感设备的结果。由此引出了电磁兼容分析中最核心、最基本的框架——电磁干扰三要素。"

**案例建议**：
- 阿波罗12号雷击事件（用在EMI概念后，NASA报告MSC-01855重新叙述）
- 谢菲尔德号驱逐舰（用在三要素模型后，系统级EMC设计缺陷视角）
- 手机干扰音箱（用在三要素模型前，生活化场景引入）
```

## 图表清单

| 编号 | 类型 | 内容说明 | 建议位置 | 参考来源 |
|:----|:-----|:---------|:---------|:--------|
| 图{ch}.1 | 示意图/流程图/Mermaid | [图的内容] | [放在哪节] | [参考哪本书的图或自主原创] |
| 图{ch}.2 |  |  |  |  |
| 表{ch}.1 | 表格 |  |  |  |

## 5.1 重点素材清单

### 图片/图表素材
| 素材 | 参考来源 | 优先级 | 说明 |
|:----|:---------|:------|:-----|
| [素材名] | [参考教材哪节] | ★★★★★ | [用于哪节、如何加工] |

### 案例素材
| 案例 | 参考来源 | 优先级 | 说明 |
|:----|:---------|:------|:-----|
| [案例名] | [公开报道来源，非教材] | ★★★★★ | [用在哪个知识点后] |

### 标准/法规素材
| 素材 | 参考来源 | 优先级 | 说明 |
|:----|:---------|:------|:-----|
| [标准号] | [标准名称] | ★★★☆☆ | [用于哪节] |

## 5.2 12条军规落实检查（Agent自查用，不写入教材正文）

> ⚠️ 以下军规是 Agent 写完本章后自查自纠用的，**不是教材正文内容**。

| 军规 | 落实要求 | 本章落实情况 |
|:----|:---------|:------------|
| ① 真实案例驱动 | 至少3个震撼案例 | |
| ② 章首设"本章导读" | 说明内容、目标、与前修课程关系 | |
| ③ 术语加粗+解释 | 首次出现的术语加粗并给出定义 | |
| ④ 每节末设小结 | 3~5个要点+2~3个思考题 | |
| ⑤ 每节至少1张图或表 | 图表覆盖所有节 | |
| ⑥ 全章末综合思考题 | 5~8题，含简答、分析、拓展 | |
| ⑦ 区分选读/必读 | 用*标注选读或注明"拓展阅读" | |
| ⑧ 篇幅控制 | 不超过全书10% | |
| ⑨ 章末参考文献 | 列出引用和推荐阅读 | |
| ⑩ 关键概念给出英文 | 首次出现时给出英文全称和缩写 | |
| ⑪ 公式标准编号 | 使用 \\tag{{章-序号}} 格式 | |
| ⑫ 前后章衔接 | 章首明确与上章/下章关系 | |

## 5.3 待改进/补充方向

1. **[改进方向1]**：[具体说明]
2. **[改进方向2]**：[具体说明]

## 5.4 与前后章的衔接要点

| 衔接方向 | 衔接内容 | 具体措施 |
|:---------|:---------|:---------|
| **与前修课程衔接** | [依赖哪些前修课程] | [在哪些位置标注回顾] |
| **与第X章衔接** | [本章为第X章做什么铺垫] | [在哪些位置标注"详见第X章"] |
"""


CHAPTER_NUM_MAP = {
    '一': 1, '二': 2, '三': 3, '四': 4, '五': 5,
    '六': 6, '七': 7, '八': 8, '九': 9, '十': 10,
    '十一': 11, '十二': 12, '十三': 13, '十四': 14, '十五': 15,
}


def _chinese_to_arabic(text: str) -> Optional[int]:
    """将中文章节号转为阿拉伯数字，如 '一'→1, '十一'→11"""
    for cn, num in sorted(CHAPTER_NUM_MAP.items(), key=lambda x: -len(x[0])):
        if cn in text:
            return num
    return None


def parse_outline_structure(docx_path: str) -> List[dict]:
    """解析提纲 docx 文件，提取各章名称和L1节结构。"""
    if not os.path.exists(docx_path):
        print(f"❌ 提纲文件不存在: {docx_path}")
        return []
    
    try:
        import docx
        doc = docx.Document(docx_path)
        chapters = []
        current_ch = None
        
        for para in doc.paragraphs:
            text = para.text.strip()
            if not text:
                continue
            # 匹配 "第X章"（支持中文和阿拉伯数字）
            ch_num = _chinese_to_arabic(text)
            m_arabic = re.match(r'第(\d+)章\s+(.+)', text)
            if ch_num is not None and '章' in text:
                if current_ch:
                    chapters.append(current_ch)
                title = re.sub(r'第[一二三四五六七八九十]+章\s*', '', text)
                title = re.sub(r'第\d+章\s*', '', title)
                current_ch = {"chapter": ch_num, "title": title.strip(), "sections": []}
                continue
            if m_arabic:
                if current_ch:
                    chapters.append(current_ch)
                current_ch = {"chapter": int(m_arabic.group(1)), "title": m_arabic.group(2).strip(), "sections": []}
                continue
            
            # 匹配 L1 节 "X.Y"
            if current_ch:
                m = re.search(r'(\d+\.\d+)\s+(.+)', text)
                if m:
                    sec_num = m.group(1)
                    if sec_num.startswith(f"{current_ch['chapter']}."):
                        current_ch["sections"].append({"num": sec_num, "title": m.group(2).strip()})
        
        if current_ch:
            chapters.append(current_ch)
        
        if chapters:
            return chapters
    except ImportError:
        print("⚠️  python-docx 未安装，尝试用 pandoc 转换...")
    
    return []


def outline_exists(guides_dir: str, chapter: int) -> bool:
    """检查某章大纲是否已存在"""
    path = Path(guides_dir) / f"writing-guide-ch{chapter}.md"
    return path.exists() and path.stat().st_size > 100


def generate_chapter_outline(chapter: int, title: str, sections: List[dict], 
                             source_books: List[dict], output_dir: str):
    """为单章生成写作大纲文件"""
    guides_dir = Path(output_dir) / "写作大纲"
    guides_dir.mkdir(parents=True, exist_ok=True)
    out_path = guides_dir / f"writing-guide-ch{chapter}.md"
    
    content = CHAPTER_TEMPLATE.format(ch=chapter, title=title)
    
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"  📝 已创建: writing-guide-ch{chapter}.md")
    return str(out_path)



def main():
    parser = argparse.ArgumentParser(description="从提纲+参考书生成每章写作大纲")
    parser.add_argument("--project", required=True, help="项目根目录")
    parser.add_argument("--chapter", type=int, default=None, help="只生成指定章节（可选）")
    parser.add_argument("--force", action="store_true", help="强制重新生成已有大纲")
    args = parser.parse_args()
    
    project_root = Path(args.project).expanduser().resolve()
    
    # 读取项目配置
    cfg_data = {}
    cfg_path = project_root / "book-build.yaml"
    if cfg_path.exists():
        import yaml
        with open(cfg_path, 'r', encoding='utf-8') as f:
            cfg_data = yaml.safe_load(f) or {}
    
    textbook_cfg = cfg_data.get("textbook", {})
    outline_file = textbook_cfg.get("outline_file", "教材提纲.docx")
    outline_docx = str(project_root / "input" / outline_file)
    source_book_list = cfg_data.get("source_books", []) or []
    
    if not os.path.exists(outline_docx):
        print(f"❌ 提纲文件不存在: {outline_docx}")
        sys.exit(1)
    
    if not source_book_list:
        print("⚠️  book-build.yaml 中未配置 source_books，大纲将只包含结构骨架")
    
    # 解析提纲结构
    print(f"📖 解析提纲文件: {outline_docx}")
    chapters = parse_outline_structure(outline_docx)
    
    if not chapters:
        print("❌ 无法解析提纲文件")
        sys.exit(1)
    
    print(f"✅ 解析出 {len(chapters)} 章")
    chapters.sort(key=lambda c: c["chapter"])
    
    if args.chapter:
        chapters = [c for c in chapters if c["chapter"] == args.chapter]
        if not chapters:
            print(f"❌ 未找到第{args.chapter}章")
            sys.exit(1)
    
    output_dir = str(project_root / "output")
    existing = 0
    created = 0
    
    for ch_info in chapters:
        ch = ch_info["chapter"]
        title = ch_info["title"]
        sections = ch_info.get("sections", [])
        
        guides_path = Path(output_dir) / "写作大纲"
        if (guides_path / f"writing-guide-ch{ch}.md").exists() and not args.force:
            existing += 1
            continue
        
        path = generate_chapter_outline(ch, title, sections, source_book_list, output_dir)
        created += 1
    
    print("\n--- 完成 ---")
    print(f"总章节: {len(chapters)}")
    print(f"新建: {created}  跳过（已存在）: {existing}")
    
    if created > 0:
        print("\n⚠️  大纲已生成基本骨架，建议：")
        print(f"   1. 运行 validate_outlines.py 检查完整性")
        print(f"   2. 人工调整后，运行 generate_task_list.py 生成写作任务")
        
        # 输出结构化任务清单供 Agent 消费
        outline_tasks = []
        for ch_info in chapters:
            ch = ch_info["chapter"]
            title = ch_info["title"]
            sections = ch_info.get("sections", [])
            
            book_refs = []
            for b in source_book_list:
                book_refs.append({
                    "author": b.get("author", "?"),
                    "display_name": b.get("display_name", "?"),
                    "path": b.get("path", "")
                })
            
            outline_tasks.append({
                "type": "complete_writing_guide",
                "chapter": ch,
                "title": title,
                "guide_path": f"output/写作大纲/writing-guide-ch{ch}.md",
                "outline_sections": sections,
                "source_books": book_refs,
                "status": "pending"
            })
        
        tasks_path = project_root / "output" / "outline_tasks.json"
        with open(tasks_path, 'w', encoding='utf-8') as f:
            json.dump(outline_tasks, f, ensure_ascii=False, indent=2)
        print(f"\n📋 已输出结构化任务: {tasks_path}")
        print(f"   Agent 读取该文件后，对每个 pending 任务：")
        print(f"   1. delegate_task → 分析参考书内容")
        print(f"   2. 完善 writing-guide-chX.md（写作手法、体量目标、素材来源）")
        print(f"   3. 标记 status 为 completed")


if __name__ == "__main__":
    main()
