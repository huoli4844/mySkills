# delegate_task 写 YAML 的标准工作流

> 适用场景：需要子代理为某章节写全部 8 种 YAML 数据文件。
> 核心原则：模板 @prompt 是**原料**不是指令，必须用 `build-prompt` 加工成结构化提示词后注入 context。

## 标准 context 模板

```yaml
SKILL: /Users/huoli4844/.hermes/skills/research/domain-wiki
BOOK: /path/to/book/书籍名
CH: N
SRC: $BOOK/20_正文/第N章 章节名.md
DATA_DIR: $BOOK/.dag/第N章/data/

*** CRITICAL WORKFLOW — FOLLOW EXACTLY ***
Step 1: cd $SKILL && python3 scripts/yaml_writer.py build-prompt --type TYPE -c N
→ READ the output. It contains per-field writing requirements from template @prompt.
Step 2: Read the source file SRC for content
Step 3: Write YAML to DATA_DIR/TYPE.yaml with format: - name: / file: / fm: / bd:
Step 4: cd $SKILL && python3 scripts/yaml_writer.py validate --yaml-path $YAML --type TYPE
Step 5: Fix ALL errors until PASS
Step 6: cd $SKILL && python3 scripts/pipeline_v2.py run --book-dir $BOOK -c N --book-id ID --book-name NAME
```

## 为什么必须用 build-prompt

对比两个命令的输出差异：

| 命令 | 输出内容 | 用于 | 效果 |
|:-----|:---------|:-----|:-----|
| `skeleton --type concept` | 字段名清单（26个名字） | 看有哪些字段 | 子代理不知道每个字段怎么写 |
| `prompt --type concept` | @prompt原料文本 | 人工参考 | 原料未经加工，子代理不会自动使用 |
| `self-instruct --type concept -c N` | 字段工作台（@prompt+源文+约束） | 亲自填写 | 输出太长，不适合直接塞 context |
| `build-prompt --type concept -c N` | 结构化提示词（写作总则+逐字段要求+字数+格式+输出模板+校验指令） | **delegate_task context 注入** | 子代理拿到即可按指导写作 |

**关键教训（2026-06-09）：** 只给子代理 `skeleton`（字段名清单）时，子代理凭自己理解写内容，导致：
- `term_definition` 只有 10-30 字（要求≥80字）
- `mathematical_model` 用纯文本而非 `$$...$$`
- `core_concept_map` 缺失
- `common_misconceptions` 无格式

注入 `build-prompt` 输出后，同样的子代理能写出 26 字段全部充实的内容。

## 子代理 context 的完整结构

```
基本信息: SKILL路径, BOOK路径, 章节号, 源文路径, 数据目录路径

关键指令:
  Step 1: cd $SKILL && python3 scripts/yaml_writer.py build-prompt --type TYPE -c N
  Step 2: 读源文
  Step 3: 写YAML
  Step 4: validate校验
  Step 5: 修复至PASS

最小要求:
  concept≥3, ke≥2, entity≥1, kp≥1, sp≥1, scene≥1, exercise≥2, solution≥2

fm必填字段:
  source_chapter: "N"
  source_from: "第N章 标题"
  confidence_note: "系统自动填充"
  confidence: 0.95(concept)/0.85(ke/entity/kp)/0.75(sp)/0.65(scene/exercise/solution)
```

## 注意事项

1. **不要只用 `skeleton`** — 它只输出字段名，不含任何写作指导。子代理无指导写出的内容质量差。
2. **不要用 `self-instruct` 输出塞 context** — 它输出包含全部源文，太长。`build-prompt` 更紧凑。
3. **`build-prompt` 是每章运行一次** — 它不依赖源文内容，只依赖模板 @prompt，所以不同章输出相同。
4. **写完后必须 `validate`** — pydantic 校验会检测字段缺失、confidence 范围、字段类型等。
5. **通过后必须 `pipeline_v2.py run`** — 才会渲染到 .md 文件并更新索引。
