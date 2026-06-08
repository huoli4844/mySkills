# YAML 多行字符串转义：`\n` 字面量污染问题

## 症状

`build_kb_files.py --type concept` 生成的概念 `.md` 文件中，多行字段（`additional_explanations`、`structure`、`mathematical_model` 等）显示为字面量 `\n\n` 而非真实段落分隔：

```markdown
### 4. 补充说明

远场天线模型是天线电磁兼容预测的基础模型。\n\n**有意辐射区增益**：在设计频率和极化下...
```

Obsidian 中看到的是 `\n\n` 字样，不是换行。

## 根因

`yaml.dump()` 对含真实换行符 `\n` 的字符串使用双引号（double-quoted）样式：

```yaml
# yaml.dump 输出的格式（双引号）
additional_explanations: "第一段。\n\n第二段。\n\n**粗体标题**：..."
```

模板组装器 `assemble_md()` 读取此 YAML 后，`{{additional_explanations}}` 的值是 Python 字符串 `"第一段。\n\n第二段。\n\n**粗体标题**：..."`。直接写入 MD 时，`\n` 被当作两个字符（反斜杠+n），不是换行。

## 修复方案

### 方案 A：编写时使用 YAML literal block scalar（推荐）

```python
import yaml

class LiteralStr(str):
    """标记为 YAML literal block scalar 的字符串"""
    pass

def literal_str_representer(dumper, data):
    return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')

yaml.add_representer(LiteralStr, literal_str_representer)

# 对多行字段使用 LiteralStr 包装
bd = {
    "additional_explanations": LiteralStr("第一段。\n\n**标题**：..."),
    "structure": LiteralStr("1. 要素一\n2. 要素二"),
    # 单行字段保持普通 str
    "formula_references": "无",
}
```

输出：
```yaml
additional_explanations: |-
  第一段。
  
  **标题**：...
structure: |-
  1. 要素一
  2. 要素二
```

### 方案 B：写完后正则替换（快速修复）

```python
import re

with open("concepts.yaml", "r") as f:
    content = f.read()

# 匹配双引号包裹的多行字符串，转换为 | block
def convert_to_block(m):
    key = m.group(1)
    value = m.group(2)
    if '\\n' in value:
        unescaped = value.replace('\\n', '\n')
        indented = '\n  '.join(unescaped.split('\n'))
        return f'{key}: |-\n  {indented}'
    return m.group(0)

# 注意：此正则仅处理简单情况，复杂嵌套需要更健壮的方案
content = re.sub(
    r'^(\w+): "((?:[^"\\]|\\[^n])*\\n(?:[^"\\]|\\[^n])*)"',
    convert_to_block, content, flags=re.M
)

with open("concepts.yaml", "w") as f:
    f.write(content)
```

### 方案 C：写入时不使用 yaml.dump，直接手写 YAML

对多行字段显式使用 `|` 缩进块：

```python
concept_yaml = f"""\
- name: 远场天线模型
  file: 远场天线模型
  fm:
    source_chapter: "3"
    ...
  bd:
    ...
    additional_explanations: |
      远场天线模型是天线电磁兼容预测的基础模型。

      **有意辐射区增益**：在设计频率和极化下...

      **非有意辐射区**：对于高增益天线...
    structure: |
      1. **钥匙型平面方向图**
      2. **有意辐射区模型**
      ...
    formula_references: 无
"""
```

**注意**：手写 YAML 时 `|` 块内的内容缩进 2 格，空行也需保持缩进。

### 方案 D：模板组装器侧后处理（全局修复）

在 `assemble_md()` 或 `_wrap_mermaid_fields()` 之后添加：

```python
# 将字面量 \n 替换为真实换行（但排除公式块、代码块、Mermaid 块内的）
import re

def fix_literal_newlines(md_content):
    """将 MD 正文中的字面量 \\n 替换为真实换行"""
    # 保护代码块和 Mermaid 块
    blocks = []
    def save_block(m):
        blocks.append(m.group(0))
        return f'%%BLOCK_{len(blocks)-1}%%'
    
    protected = re.sub(r'```.*?```', save_block, md_content, flags=re.DOTALL)
    protected = re.sub(r'\$\$.*?\$\$', save_block, protected, flags=re.DOTALL)
    
    # 在非保护区域替换
    fixed = protected.replace('\\n', '\n')
    
    # 恢复保护块
    for i, block in enumerate(blocks):
        fixed = fixed.replace(f'%%BLOCK_{i}%%', block)
    
    return fixed
```

## 验证

```bash
# 检查生成的概念文件中是否仍有字面量 \n
grep -l '\\\\n\\\\n' 30_核心概念/*.md
# 应返回空
```

## 相关 pitfall

SKILL.md pitfall #36
