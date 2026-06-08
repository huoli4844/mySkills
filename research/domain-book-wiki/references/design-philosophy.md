# 设计哲学：领域无关、书籍无关的知识库构建框架

## 核心理念

这个框架不是"EMC知识库构建工具"——它是**任意学科、任意书籍**的知识库生成框架。
模板 `.md` 文件定义输出长什么样，代码负责渲染，Agent 负责提取内容。

```
输入（任意学科/任意书籍）：
  正文 .md 文件
    ↓ Agent 结构化提取
  YAML 数据文件
    ↓ schema.json 校验 + template_engine 渲染
输出（严格按模板结构）：
  .md 知识库文件
```

## 三域隔离

| 域 | 职责 | 领域绑定 | 
|:---|:-----|:--------|
| 模板 `.md` | 输出格式标准 | **模板可换** — 换学科只需换模板目录 |
| Schema `schema.json` | 字段映射规则 | **领域无关** — 从模板自动生成字段映射 |
| 代码 `template_engine.py` | 纯渲染引擎 | **完全无关** — 不出现任何具体字段名 |

代码中不应出现任何具体的：
- 字段名（都从 schema.json 读）
- confidence 值（都从 schema.json 读）
- 模板文件名（从类型名映射，映射表在 template_engine.py 头部）
- 章节/书籍/领域路径（作为参数传入）

## 数据流

```
正文（.md）
    ↓ Agent 理解 + 提取
YAML（.dag/第N章/data/*.yaml）
    ↓ yaml_writer.py 校验
已校验的 YAML
    ↓ template_engine.py 渲染
已填充的 .md
```

Agent 的职责：
1. 从正文中提取概念、KE、实体 → 写 YAML → 校验 → Agent 评估是否需要 KP/SP/Scene
2. 读已输出的概念/KE/KP 内容 → 写习题解答

代码的职责（全部在 template_engine.py）：
1. 从 schema.json 读字段映射
2. 从模板 .md 读输出格式
3. 替换 {{xxx}} → 值
4. 输出 .md 文件

## 常见反模式

- **代码里硬编码字段名** → 换模板字段就崩 → 正确：从 schema.json 读
- **模板和校验耦合** → 改模板显示格式导致字段规则变动 → 正确：模板只管显示，schema 管规则
- **Agent 直接写 .md 文件** → 跳过模板引擎 → 正确：Agent 只写 YAML，代码渲染
- **pipeline 做太多事** → 结构提取+语义判断+校验混在一起 → 正确：Phase A 纯代码，Phase C Agent
