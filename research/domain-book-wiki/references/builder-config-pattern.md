# BUILDER_CONFIG Pattern（配置表驱动构建模式）

将 N 个几乎相同的 Builder 函数替换为 1 个参数化函数 + 1 个配置字典。

## 问题

```python
# ❌ 6 个函数，每个 ~50 行，共 ~300 行
def build_ke(output_dir, chapter):    # create dir → load items → filter → assemble
def build_kp(output_dir, chapter):    # 同上，仅 4 个参数不同
def build_sp(output_dir, chapter):    # 同上
def build_entity(output_dir, chapter): # 同上
def build_scene(output_dir, chapter):  # 同上
def build_concept(output_dir, chapter): # 同上
```

## 解决方案

```python
# ✅ 1 个配置表 + 1 个函数，~140 行
BUILDER_CONFIG = {
    "ke":      {"data": "kes.yaml", "dir": DIR["KE"], "template": "concept_template.md",
                 "quality_key": "concept/ke", "type": "knowledge-element", "tag": ["知识要素"], "extra_fm": []},
    "kp":      {"data": "kps.yaml", "dir": DIR["KP"], "template": "knowledge_template.md",
                 "type": "knowledge", "tag": ["知识点"], "extra_fm_from_fm": ["bloom_level"]},
    "sp":      {"data": "sps.yaml", "dir": DIR["SP"], "template": "skill_template.md", ...},
    "scene":   {"data": "scenes.yaml", "template": "scenario_template.md", ...},
    "concept": {"data": "concepts.yaml", "template": "concept_template.md", ...},
    "entity":  {"data": "entities.yaml", "template": "concept_template.md",
                 "quality_key": "concept/entity", ...},
    "exercise": {"data": "exercises.yaml", "template": "eval_template.md",
                 "quality_key": "eval/exercise", ...},
    "solution": {"data": "solutions.yaml", "template": "eval_template.md",
                 "quality_key": "eval/solution", ...},
}

def build_type(output_dir, chapter, *, type_name, graph_check=False, auto_fix=False, source_dir=None):
    cfg = BUILDER_CONFIG[type_name]
    items = _load_items(cfg["data"])
    items = _filter_by_chapter(items, chapter)
    if graph_check: _graph_precheck(type_name, output_dir, items)
    
    target_dir = os.path.join(output_dir, cfg["dir"])
    os.makedirs(target_dir, exist_ok=True)
    
    for it in items:
        bd = dict(it.get("bd", {}))
        fm = dict(it.get("fm", {}))
        # ... unified assemble_md call ...
    
    if graph_check: _graph_postcheck(type_name, output_dir)
```

## 配置字段说明

| 字段 | 说明 | 示例 |
|:-----|:-----|:-----|
| `data` | YAML/JSON 数据文件名 | `"kes.yaml"` |
| `dir` | DIR 注册表键，输出子目录 | `DIR["KE"]` |
| `template` | 模板文件名 | `"concept_template.md"` |
| `quality_key` | 质量检查子类型键 | `"concept/ke"` |
| `type` | frontmatter type 值 | `"knowledge-element"` |
| `tag` | frontmatter type_tags 值 | `["知识要素"]` |
| `extra_fm` | 静态额外 frontmatter 字段 | `{"aliases": []}` |
| `extra_fm_from_fm` | 从 item.fm 复制到 frontmatter 的键 | `["bloom_level"]` |
| `extra_fm_from_bd` | 从 item.bd 复制到 frontmatter 的键 | `["entity_type"]` |
| `extra_bd_from_fm` | 从 item.fm 复制到 body 的键 | `["source_chapter"]` |

## 收益

- **300 行 → 140 行**（-53%）
- 新增类型只需 3 行配置
- 消除 copy-paste drift
- CLI `--type choices` 自动从 BUILDER_CONFIG.keys() 推导

## 适用条件

满足以下 **所有** 条件时适合使用此模式：
1. N ≥ 3 个函数结构相同
2. 每个函数 30+ 行
3. 仅有 4-8 个参数不同
4. 未来可能增加新类型
