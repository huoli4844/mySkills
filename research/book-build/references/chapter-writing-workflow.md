# 每章写作前：参考教材研读与写作指南生成工作流

## 核心理念

**不读参考教材不落笔。** 每一章动手写之前，必须先读取配置的参考教材（`config.yaml` → `source_books`）中对应的章节原文，分析各书的写作手法，形成该章的**写作指南文件**，然后严格按照指南动笔。

```bash
# 查看当前配置了多少本参考教材
python3 -c "from book_config import Config; c=Config()
print(f'共 {len(c.source_books)} 本参考教材:')
for i, b in enumerate(c.source_books, 1):
    print(f'  {i}. {b[\"author\"]}《{b[\"display_name\"]}》(priority={b[\"priority\"]})')"
```

## 为什么要这样做？

| 原因 | 说明 |
|:-----|:------|
| 吸收真正的教材感 | 参考教材是已出版的正规书，段落节奏、公式融入方式、案例写法经过编辑审定 |
| 避免千篇一律 | 每章内容不同，各书的表现手法也不同，单纯通用提示词无法体现差异 |
| 获取领域真实素材 | 参考教材中有大量具体的工程数据、历史事件、标准号，通用知识库无法替代 |
| 避免自我重复 | 不参照原文，Agent 容易每章用同一模板重复写作 |

## 工作流：五步法

```
Step 1: 源文研读
  → 找到各参考教材对应章节的 .md 文件（章号可能不匹配，用关键词搜索）
  → 逐本通读全文（至少前30%和核心节的全部）
  → 记录：每本书的章首手法、核心节手法、独特数据、最值得借鉴的3个手法

Step 2: 手法分析
  → 填写各书写作手法对比表（8维度：章首引入/概念定义/公式/案例/表格/历史/工程实用/独特亮点）
  → 标注每本书最值得借鉴的3-5个手法
  → 标注各书共同盲区（发挥空间，至少3个）

Step 3: 生成写作指南（写作大纲/writing-guide-ch{N}.md）
  → 用 templates/writing-guide-template.md 模板
  → 包含：研读分析+结构建议+每节指南+素材清单+图量规划+12条军规检查清单

Step 4: 自动进入 Step 5（除非 config.yaml 中 phase_0_5_auto: false）
  → 向用户报告写作指南已生成（不打断不等待确认）

Step 5: 按指南写作
  → 写作过程中随时回看指南
  → 完稿后对照指南逐项检查「没有遗漏任何要素」
  → 立即运行 python3 scripts/post_generation_check.py --fix
```

> **注意**：config.yaml 中 `phase_0_5_auto: true`（默认）时跳过用户确认，直接动笔。

---

## Step 1：源文研读

### 1.1 获取各参考教材章节文件路径

```bash
# 通过 book_config.py 动态获取
python3 -c "from book_config import Config; c=Config()
for i, b in enumerate(c.source_books, 1):
    print(f'教材{i} [{b[\"author\"]}]: {b[\"path\"]}')"
```

### 1.2 读什么

**每本书重点读三部分：**

| 部分 | 为什么要读 |
|:-----|:-----------|
| **章首部分（前2-3节）** | 看各书如何开门见山、如何引出主题、如何定义概念 |
| **中间核心节（深度技术节）** | 看细节深度——公式如何融入、案例如何展开、表格如何使用 |
| **章末部分（总结+习题）** | 看每本书如何收尾、习题的层次分布 |

### 1.3 注意：章节号可能不匹配

各参考书的第N章**主题可能与目标教材的第N章完全不同**。

判断方法：
```bash
# 用 wc -c 看文件大小 + head 看章首 → 快速判断主题
python3 -c "from book_config import Config; c=Config()
import os
for b in c.source_books:
    sz = os.path.getsize(b['path']) if os.path.exists(b['path']) else 0
    print(f'{b[\"author\"]}: {sz} 字节')"
```

当章号不匹配时的标准搜索法：
```bash
# 在参考教材路径中搜索关键词
python3 -c "
from book_config import Config
c = Config()
import subprocess, sys
kw = sys.argv[1] if len(sys.argv) > 1 else '关键词'
for b in c.source_books:
    r = subprocess.run(['grep', '-l', kw, b['path_processed'] + '*.md'],
                       capture_output=True, text=True, timeout=10, shell=True)
    if r.stdout.strip():
        print(f'{b[\"author\"]}: 匹配章节→ {r.stdout.strip()}')"
"关键词"

# 记录每本书的匹配度和参考策略
# 格式示例：
# | 书名 | 对应章节 | 匹配度 | 参考策略 |
# |:-----|:--------|:-----:|:---------|
# | ... | ... | 高/中/低 | 直接使用/辅助参考/仅借鉴手法 |
```

### 1.4 读的时候注意什么

每个段落问自己三个问题：

1. **"这段在教什么？"** — 识别写作意图（定义/举例/推导/对比/总结）
2. **"为什么这样写？"** — 分析手法选择（为什么用表格而不是文字？为什么先现象后定义？）
3. **"这里有什么独特数据？"** — 提取亮点数据（时间/地点/标准号/具体数值/历史事件全称）

### 1.5 记录模板

读完每本书后，动态遍历记录：

```markdown
## 参考教材研读记录 - 第N章

{% for b in c.source_books %}
### {{ b.author }}《{{ b.display_name }}》
- 文件：{{ b.path }}
- **章首手法**：{观察描述}
- **核心节手法**：{观察描述}
- **独特数据**：{具体的时间/地点/数字/标准号}
- **最值得借鉴的3个手法**：
  1. {手法1}
  2. {手法2}
  3. {手法3}

{% endfor %}
```

> 注：实际写作时由 Agent 对每本参考教材逐书填写，配置有多少本就填写多少组。

---

## Step 2：手法分析

### 2.1 各书写作手法对比表

对比维度对所有参考教材统一适用，列数 = `len(c.source_books)`：

| 对比维度 | 教材1 | 教材2 | 教材3 | … |
|:---------|:------|:------|:------|:-:|
| **章首引入方式** | {观察} | {观察} | {观察} | |
| **概念定义深度** | {观察} | {观察} | {观察} | |
| **公式数量和使用方式** | {观察} | {观察} | {观察} | |
| **案例数量和类型** | {观察} | {观察} | {观察} | |
| **表格使用** | {观察} | {观察} | {观察} | |
| **历史叙事** | {观察} | {观察} | {观察} | |
| **工程实用导向** | {观察} | {观察} | {观察} | |
| **该章独特亮点** | {亮点} | {亮点} | {亮点} | |

### 2.2 共同盲区（发挥空间）

分析各书**都没有写透**的内容——这就是发挥空间：

```markdown
### 各书共同盲区

1. **{盲区1}** — 所有书都{具体问题}，我们可以{具体发挥}
2. **{盲区2}** — 所有书都{具体问题}，我们可以{具体发挥}
3. **{盲区3}** — 所有书都{具体问题}，我们可以{具体发挥}
```

### 2.3 12条写作军规适配

```markdown
### 12条军规的本章适配

1. **详实案例驱动** → 本章使用的案例：{案例A}（来源：教材1）、{案例B}（来源：教材2）
2. **历史极致细节** → 本章可用的历史素材：{具体信息}
...（逐条覆盖）
```

---

### 2.4 每章图量规划

| 项目 | 基准 |
|:-----|:----:|
| 最小图量 | config.yaml 中 `target_mermaid_min`（默认6张） |
| 图号 | 从 `图N-1` 开始按出现顺序递增 |
| 必须转图的内容 | 文字型决策树 / 时间线 / 分类结构 / 因果链 / 流程图 |

**Mermaid图规则**：
- 每张图后必须有文字说明：`*图N-M：图标题*`
- 引言中"如图N-M所示"与图注"*图N-M：*"必须一致
- 图号修正后必须用 `grep '图N-'` 验证无冲突
- 禁止 subgraph 标题含括号/破折号（Obsidian 崩溃）
- 节点标签中禁止 emoji（用"通过/超标"替代）

### 2.5 临时文件管理

```bash
# 各节扩展稿 → 组装后删除
output/section-*.md

# 写作指南 → 保留供后续参考
output/写作大纲/writing-guide-*.md

# 清理命令
rm -f output/section-*.md /tmp/ch*-*.md
```

---

## Step 3：生成写作指南

写作指南存放在 `output/写作大纲/writing-guide-ch{N}.md`，用 `templates/writing-guide-template.md` 模板，至少包含：

- 本章定位
- 结构建议表（每节字数 + 主导手法 + 素材来源）
- 每节逐项写作指南（引入方式 + 必须要素 + 设问过渡 + 案例建议）
- 素材清单（从各参考教材提取的具体数据/标准号/案例）
- 图量规划（≥6~8张Mermaid，标注图号/位置/类型）
- 12条军规落实检查清单

```bash
# 输出路径获取
python3 -c "from book_config import Config; c=Config(); print(c.writing_guide_path(N))"
```

---

## Step 4：按指南写作

### 4.1 写作对照清单

```markdown
写作前：
  □ 已通读所有参考教材对应章节
  □ 已完成各书手法对比表
  □ 已标注共同盲区
  □ 写作指南文件已生成

写作中：
  □ 每写一节前再看该节的指南
  □ 每写完一节检查是否符合分配的素材和手法
  □ 每写完一节检查设问过渡是否到位

写作后：
  □ 对照写作指南逐项检查
  □ 检查总字数是否达到该章目标
  □ 检查13条军规是否全部落实
  □ 运行 post_generation_check.py --fix
```

### 4.2 写作中回看原文

```bash
# 列出所有参考教材路径
python3 -c "from book_config import Config; c=Config()
for i, b in enumerate(c.source_books, 1):
    print(f'教材{i}: {b[\"path\"]}')"

# 用 read_file 打开对应的节
# read_file {某教材路径} --offset {行号} --limit 50
```

---

## 执行入口

```bash
# 1. 查看所有参考教材概览
python3 -c "from book_config import Config; c=Config()
for b in c.source_books:
    import os
    sz = os.path.getsize(b['path']) if os.path.exists(b['path']) else 0
    print(f\"{b['author']}: {b['display_name']} ({sz} 字节)\")"

# 2. 通读各书章首和章末
# （使用 read_file 工具）
```

> **路径工具**：
> - `book_config.py` → `Config()` 加载 `config.yaml`（`project` + `source_books` + `knowledge_base` 三节）
> - 各动态命令中的 `c.source_books` 返回当前配置的所有参考教材，按 priority 排序
> - 修改 `config.yaml` 即可切换/增删参考教材，无需改动本工作流文件
