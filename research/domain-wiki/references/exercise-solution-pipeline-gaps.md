# 习题/解答 Pipeline 空白缺陷分析（v35.7 修复版）

## 原始缺陷（v35.6 前）

### 数据缺失链路

```
第N章 .docx ✅ → Phase 1 未执行 ❌ → 20_正文/ 无 .md → exercises 检测失败 → solutions 跳过
```

### 3 个设计漏洞

1. **exercises 自动检测失败 → 静默 done**
   - `_auto_detect_and_build_exercises` 返回 False
   - `pipeline_auto` else 分支标记 `status=done`（而非 blocked）
   - 后续 solutions 的 DAG 依赖检查只看 status，不看文件数
   - → exercises 和 solutions 都跳过，无任何警告

2. **solutions 阶段只做"组装已有数据"，不做"生成答案"**
   - `solutions` 调用 `build_kb_files.py --type solution`
   - 需要 `.dag/第N章/data/solutions.yaml` 作为输入
   - Pipeline 从不生成这个 YAML — Agent 必须手动写
   - 无 solutions.yaml → 直接 return False

3. **Phase 1 缺失无闸门检测**
   - `.docx` 存在但 `.md` 不存在 → exercises 只打印警告就跳过
   - 不阻断 pipeline，不提示需要先运行 file2md

## v35.7 修复方案

### 修复 1：exercises 失败 → blocked
```
pipeline_auto exercises 段:
  if not success:
    → s["phases"][ph]["status"] = "blocked"  (原 done)
    → 检查 .docx 存在但 .md 缺失 → 提示"请先运行 file2md"
    → all_passed = False; continue  (不进入后续 phases)
```

### 修复 2：solutions 失败 → blocked
```
pipeline_auto solutions 段:
  if not success and _phase_count(wr, "exercises") > 0:
    → s["phases"][ph]["status"] = "blocked"
```

### 修复 3：solutions.yaml 缺失时自动回退
```
_auto_build_solutions:
  1. 尝试 build_kb_files.py --type solution（需 solutions.yaml）
  2. 失败 → 直接从 90_习题/*.md 提取题目内容
  3. 用 template_assembler_core.assemble_md() 生成骨架解答:
     - confidence: 0.5
     - answer: "（待填充参考答案）"
     - exam_point_analysis: "（待Agent分析考点）"
     - strict: False  # 不阻断写入
```

### 修复 4：comprehensive-content-check 全局配对检查
```
check_exercise_solution_pairing(wiki_root):
  遍历 90_习题/ 下所有习题 .md
  → 在 90_习题/解答/ 中查找对应解答
  → 缺失 → FAIL 级别阻断
```

### 修复 5：中文骨架占位符检测
```
has_placeholder() 扩展检测:
  原: {{placeholder}} 模式
  新增:
    - （待填充***）
    - （待Agent***）
    - （待补充***）
    - （暂无***）
```
这些模式在骨架解答的"参考答案"和"考点分析"段出现时，`comprehensive-content-check` 以 FAIL 级别标记。

## 设计规则（硬编码）

| # | 规则 | 实现位置 |
|---|------|---------|
| 1 | **仅源文末尾有习题时生成** | `_auto_detect_and_build_exercises` — 检测 `20_正文/` 末尾"思考题/习题"块 |
| 2 | **有习题则必须有解答** | `pipeline_auto` + `check_exercise_solution_pairing` — blocked + FAIL 双闸门 |
| 3 | **解答可增量填充** | 骨架解答 confidence=0.5，Agent 后续替换内容 |
| 4 | **无习题 → 不生成空壳** | 源文无习题内容时 exercises 标记为 done（0 文件），solutions 不触发 |
