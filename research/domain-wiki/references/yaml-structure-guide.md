# YAML 文件容器结构指南

> ✅ v44.2: `yaml_gen.py extract <type>` 已输出完整容器结构（含 `name/file/fm/bd`），不再输出扁平字段列表。
> 可直接使用 extract 输出作为 YAML 骨架，填入实际内容即可。
>
> **写 YAML 前建议先用 `yaml_gen.py extract <type>` 获取正确容器结构，再参考已有章 `.dag/第N章/data/*.yaml` 确认格式。**

---

## 完整容器结构（所有类型通用）

```yaml
- name: "节点名称"
  file: "节点名称"          # ⚠️ 不可含 .md 后缀，builder 自动追加
  fm:                       # ← fm 固定 4 字段，其他字段放 bd
    source_chapter: '7'     # 来源章号
    source_from: "§7.1"     # 来源节号
    confidence: 0.95        # ⚠️ 见下方速查表
    confidence_note: "..."  # 置信度说明
  bd:                       # ← 模板变量字段，参考 yaml-field-mapping.md
    term_english: "..."
    term_definition: "..."
    definition_sentence: "..."   # ⚠️ 必须能在 20_正文 中逐字检索
    ...
```

## fm 字段清单（固定 4 个）

| 字段 | 必填 | 说明 |
|:-----|:---:|:-----|
| `source_chapter` | ✅ | 章号（如 `'7'`） |
| `source_from` | ✅ | 节号（如 `"§7.1"`） |
| `confidence` | ✅ | 置信度（见速查表） |
| `confidence_note` | ✅ | 置信度说明文字 |

## confidence 速查表（所有 8 种类型）

| 类型 | confidence | quality_key |
|:-----|:---------:|:------------|
| concept | 0.95 | concept |
| ke | 0.85 | concept/ke |
| entity | 0.85 | concept/entity |
| kp | 0.85 | knowledge |
| sp | 0.75 | skill |
| scene | 0.65 | scenario |
| exercise | 0.65 | eval/exercise |
| solution | 0.85 | eval/solution |

## 🚫 常见错误 vs ✅ 正确格式

### 错误 1：扁平格式（已被 v44.2 修复 — 旧版 extract 输出幻觉）

> ⚠️ **v44.2 已修复**：`yaml_gen.py extract` 现在直接输出正确容器结构，Agent 不再需要手动添加 `name/file/fm/bd`。
> 以下错误示例仅保留供历史参考，新项目不会遇到此问题。

```yaml
# ❌ 旧版错误 — 扁平格式
- book_id: "0001"
  chapter_num: "7"
  confidence: 0.95
  term_definition: "..."
  definition_sentence: "..."
```

```yaml
# ✅ 正确 — fm 仅 4 字段，bd 含模板变量
- name: "电磁频谱管理"
  file: "电磁频谱管理"
  fm:
    source_chapter: '7'
    source_from: "§7.1"
    confidence: 0.95
    confidence_note: "教材核心概念"
  bd:
    term_definition: "..."
    definition_sentence: "..."
    ...
```

### 错误 2：fm 塞了太多字段

```yaml
# ❌ 错误 — aliases/tags/domain/type 在 fm 中
fm:
  source_chapter: '7'
  source_from: "§7.1"
  confidence: 0.95
  confidence_note: "..."
  aliases: [...]        # ← 由 builder static_fm_extra 自动填
  tags: [...]           # ← 同上
  domain: "电磁兼容"     # ← 应放在 bd 中
```

```yaml
# ✅ 正确 — fm 严格仅 4 字段
fm:
  source_chapter: '7'
  source_from: "§7.1"
  confidence: 0.95
  confidence_note: "..."
```

### 错误 3：顶层缺 file 字段

```yaml
# ❌ 错误 — builder 报 'file' KeyError
- name: "电磁频谱管理"
  fm: {...}
  bd: {...}
```

```yaml
# ✅ 正确
- name: "电磁频谱管理"
  file: "电磁频谱管理"    # ← 必填
  fm: {...}
  bd: {...}
```

### 错误 4：confidence 值写错

```yaml
# ❌ exercise 用 0.85 → FM 校验阻断
fm:
  confidence: 0.85       # ← exercise 应为 0.65

# ✅ 正确
fm:
  confidence: 0.65       # ← 对照速查表
```

---

**版本**: v44.2  \n**最后更新**: 2026-06-03  \n**v44.2 变更**: extract 输出已改为完整容器结构，不再输出扁平字段列表。同步更新了"错误 1"说明。  \n**建议**: 写 YAML 前用 `yaml_gen.py extract <type>` 获取正确容器结构，再参考已有章 `.dag/第N章/data/*.yaml` 确认格式。
