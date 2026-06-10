---
name: book-build
description: "大纲驱动的专业教材编写管线。Loop Engineering + 自进化。双层配置，自动创建目录结构和进度文件，支持中断恢复。支持 MD→DOCX 转换（OMML 可编辑公式）。"
version: 2.11.0
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

### 任务进度自动管理

每次从大纲解析出章节列表后，Agent 会在项目根目录创建 `book-build-progress.yaml`：

```yaml
chapters:
  - number: 1
    title: "绪论"
    status: completed
  - number: 2
    title: "电磁兼容概述"
    status: completed
  - number: 3
    title: "电磁骚扰源"
    status: in_progress
current_index: 2
last_updated: "2026-06-10 14:30:00"
```

**中断恢复**：Agent 每次启动时检查该文件，找到 `status: pending` 的第一章继续。
**手动查看**：`python3 scripts/task_tracker.py --project ~/Desktop/我的教材 --status`
```

[Content truncated due to length limit - using full SKILL.md from skill_view output]
