# domain-wiki v2.0 架构重构说明

## 背景

v52.5 之前版本的核心问题：
- 15个validator文件（~5108行），各自维护字段列表
- 10个文件独立定义confidence值，互不一致
- 4个字段名权威源，改一个不影响其他
- Agent写YAML靠文字提示，没有类型约束
- 每章至少3-5次手动修复才能通过pipeline

## 解决方案：三域隔离

```
schemas/domain_book_schema.json  ← 数据域（唯一真相源）
scripts/yaml_writer.py           ← Agent工具域（类型安全）
scripts/template_engine.py       ← 渲染域（纯代码）
scripts/pipeline_v2.py           ← 编排域（两阶段）
```

### 数据域（唯一真相源）

`schemas/domain_book_schema.json` 定义8个节点类型的全部字段：

```json
{
  "concept": {
    "template": "concept_template.md",
    "confidence": {"allowed": [0.95], "default": 0.95},
    "frontmatter": {
      "source_chapter": {"type": "string", "required": true},
      "confidence": {"type": "number", "required": true, "allowed": [0.95]}
    },
    "bd": {
      "term_english": {"type": "string", "required": true},
      "mathematical_model": {"type": "string", "required": false}
    }
  }
}
```

代码不硬编码任何字段名，全部从 schema 动态读取。

### Agent工具域（类型安全）

`yaml_writer.py` 从 schema 动态生成 Pydantic 模型，Agent写YAML时：

```python
# 内部自动生成
class ConceptBD(BaseModel):
    term_english: str = Field(..., min_length=1)
    mathematical_model: Optional[str] = None

class ConceptYAML(BaseModel):
    name: str
    file: str
    fm: ConceptFM
    bd: ConceptBD
    @model_validator
    def check_confidence(self):
        # 从 schema 读取 allowed
```

写字段名/confidence超范围 → 写入前报错，不产生脏数据。

### 渲染域（纯代码）

`template_engine.py` 工作原理：

1. 读 schema.json → 知道哪些是 bd 字段、哪些是 auto_fill 字段
2. 读模板 .md → 知道输出格式
3. 对每个 YAML item：取 fm + auto_fill + bd 值 → 替换模板 {{xxx}}
4. 写入 .md 文件

不包含任何校验逻辑，纯渲染。

### 编排域（两阶段）

`pipeline_v2.py`:

- **Phase A（纯代码）**: 校验YAML → 模板渲染（所有字段从schema读）
- **Phase B（Agent评估）**: 输出已有数据概况 → 建议Agent判断是否需要KP/SP/Scene

## 组件关系

```
yaml_writer.py ──read──▶ schema.json ◀──read── template_engine.py
       │                                        │
       ▼                                        ▼
   Validated YAML                         Rendered .md files
       │                                        │
       └──────────▶ pipeline_v2.py ◀────────────┘
                        │
            ┌───────────┴───────────┐
            ▼                       ▼
       Phase A                 Phase B
   （校验→渲染）             （Agent评估）
```

## 与旧版对比

| 操作 | 旧版(v52.5) | 新版(v2.0) |
|:-----|:-----------|:-----------|
| 查看可用类型 | `schema_loader.py list` | `yaml_writer.py list` |
| 生成YAML骨架 | `schema_loader.py extract concept --yaml` | `yaml_writer.py skeleton --type concept` |
| 写YAML | 手动写，文字提示字段名 | `yaml_writer.py write --type concept --items '[...]'` |
| 校验YAML | `schema.py validate` | `yaml_writer.py validate --yaml-path xxx.yaml` |
| 构建章节 | `dag_controller.py pipeline auto -c N` | `pipeline_v2.py phase-a -c N` |

## 遗留说明

旧版文件（dag_controller.py / build_kb_files.py / schema_loader.py / schema.py / 等15个validator）保留在 scripts/ 目录中供参考。新构建请使用 v2.0 工具链。

旧版通过 `domain-wiki-v52.5-legacy` git tag 可回溯。
