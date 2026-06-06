# v31 端到端审计 — 发现的关键 bug（2026-05-28）

在实际 workspace（`~/Desktop/测试-全书/电磁兼容基础`）上运行 `pipeline init → auto → validate` 完整链路后发现的 bug。

## Bug 1: `argparse` 误删

**症状**：所有 pipeline 命令（init, status, auto, validate）报 `NameError: name 'argparse' is not defined`

**根因**：清理"未用 import"时误删 `import argparse`，但 dag_controller.py 的 `main()` 函数使用 `argparse.ArgumentParser()` 构建 CLI。

**修复**：`import os, sys, json, re, argparse, subprocess, glob` — 加回 argparse。

## Bug 2: `kp` 从 DAG_DEPENDS 缺失

**症状**：`pipeline init` 报 `KeyError: 'kp'`

**根因**：编辑 `DAG_DEPENDS` 时误删 `"kp":["concepts","ke"]`，但 `kp` 仍在 `DAG_ORDER` 中。`pipeline init` 遍历 `DAG_ORDER` 取值时触发 KeyError。

**修复**：在 `DAG_DEPENDS` 中补回 `"kp":["concepts","ke"]`。

**防御性检查**：
```bash
python3 -c "from dag_utils import DAG_ORDER, DAG_DEPENDS; assert set(DAG_ORDER)==set(DAG_DEPENDS.keys())"
```

## Bug 3: pipeline auto 不传 book-id 给子进程

**症状**：`pipeline auto` 调用 `build_kb_files.py` 时输出 `❌ BOOK_ID 未设置！`，静默失败但 pipeline 标记 done（因旧文件残留）。

**根因**：`_auto_build_kb_phase()` 和 `pipeline_next()` 的 subprocess.run 参数列表中缺少 `--book-id`/`--book-name`。`build_kb_files.py` 的 `main()` 已增加 BOOK_ID 非空校验，缺参数直接 exit(1)。

**修复**：从 state 对象 `s["book_id"]` 和 `s.get("book_name","")` 提取值，传入 subprocess.run 参数。

## Bug 4: 20_正文/ 缺失导致 exercises 检测失败

**症状**：`pipeline auto` 的 exercises 阶段报 `章节文件不存在`

**根因**：工作区有 8 个 `.docx` 文件但未运行 `file2md` 或 `source-prepare` 预处理。

**修复**：先运行预处理生成 `20_正文/第N章.md`，再跑 pipeline。

## 数据覆盖缺口

| 章节 | 正文 | Concepts | KE | KP | SP | Scene |
|:-----|:----:|:--------:|:--:|:--:|:--:|:-----:|
| 第1章 | ❌ | 8 | 7 | 0 | 0 | 0 |
| 第2章 | ❌ | 9 | 13 | 7 | 2 | 1 |
| 第3章 | ❌ | 7 | 11 | 5 | 2 | 1 |
| 第4-8章 | ❌ | 0 | 0 | 0 | 0 | 0 |

第1章缺少 KP/SP/Scene，第4-8章完全无数据。需 Agent 按 `references/chapter-data-generation.md` 补全。

## 73 个断链

已生成的 21 个 .md 文件中有 73 个 wikilink 指向不存在的目标文件。需 `pipeline fix fix` 自动修复或补全缺失的数据后再重建。
