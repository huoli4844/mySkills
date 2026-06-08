# Mermaid Unicode 渲染失败排查指南

## 症状

Mermaid 图完全不显示（空白或报错），但 `%%{init}` 语法检查通过、括号平衡。同一文件中其他 Mermaid 图正常显示。

## 常见根因

### 1. Unicode 组合字符（最常见）

节点标签 `[...]` 中的 Unicode 组合字符（U+0300-U+036F）会导致 Mermaid 渲染引擎崩溃：

```
❌  B-->D[电场切向连续: n̂×(E₁-E₂)=0]
```
- `n̂` = `n` (U+006E) + 组合音调符 (U+0302) — **导致整个图不显示**
- `×` (U+00D7), `·` (U+00B7), `₁₂` (U+2081/2082 下标) — 多数 Mermaid 版本不支持

**修复**：替换为纯 ASCII：

```
✅  B-->D[电场切向连续: nx(E1-E2)=0]
```

中文/CJK 字符（U+4E00+）不受影响，可正常使用。

### 2. YAML 双引号字符串行接续符残留

YAML 中 `"..."` 双引号字符串使用 `\` 行接续拆分长行：

```yaml
core_concept_map: "flowchart TD\n    B-->E[磁场切向:\
      \ n̂×(H₁-H₂)=J_s]"
```

`\` 在 YAML 行尾是续行符（被移除），但 `\ `（反斜杠+空格）在行首是 YAML 转义序列（映射为一个空格）。**如果 YAML 写错了**，反斜杠可能泄露到实际字符串中，变成 `\  `（反斜杠+空格）出现在 Mermaid 节点标签里。

**检测方法**：
```python
import yaml
with open('concepts.yaml') as f:
    data = yaml.safe_load(f)
for item in data:
    mermaid = item.get('bd', {}).get('core_concept_map', '')
    if '\\' in mermaid:
        print(f"残留反斜杠: {item['name']}")
```

### 3. `%%{init}` 括号不匹配

```yaml
%%{init: {'theme': 'base', 'themeVariables': {'fontSize': '12px'}}}
```

正确：3 开 `{` + 3 闭 `}`。如果模板或数据生成时花括号数量不一致，Mermaid 解析 `%%{init}` 会失败，后续所有图语法都不识别。

### 4. classDef/class 链式语法（已修复的老问题）

```mermaid
flowchart TD
    A[节点]-->B[节点2]
    classDef root fill:#1a73e8; class A root;  # ← Mermaid 不支持
```

Mermaid **不支持**在流程图定义行中用 `;` 链式拼接 classDef/class 语句。见已知修复 #27。

## 批量检测脚本

```python
import re, yaml

with open('data/concepts.yaml') as f:
    data = yaml.safe_load(f)

for item in data:
    mermaid = item.get('bd', {}).get('core_concept_map', '')
    if not mermaid:
        continue
    
    issues = []
    # 组合字符检测
    for c in mermaid:
        if 0x0300 <= ord(c) <= 0x036F:
            issues.append(f'组合字符 U+{ord(c):04X}')
            break
    
    # 数学符号检测  
    for c in mermaid:
        if ord(c) in (0x00D7, 0x00B7, 0x00F7):
            issues.append(f'数学符号 U+{ord(c):04X}')
            break
    
    # 下标检测
    for c in mermaid:
        if 0x2080 <= ord(c) <= 0x2089:
            issues.append(f'下标 U+{ord(c):04X}')
            break
    
    # 反斜杠残留检测
    if '\\' in mermaid:
        issues.append('残留反斜杠')
    
    # classDef 检测
    if 'classDef' in mermaid:
        issues.append('包含 classDef')
    
    if issues:
        print(f"❌ {item['name']}: {', '.join(issues)}")
    else:
        print(f"✅ {item['name']}")
```

## 修复原则

- Mermaid 节点标签 `[text]`、`{text}`、`(text)` 中的文本只应包含：**中文 + ASCII 字母数字 + 常见标点**（空格、冒号、逗号、句号、括号）
- 数学公式（`×`, `·`, `ρ`, `₁`, `n̂` 等）应放到 LaTeX 块 `$$...$$` 中，不要在 Mermaid 标签里使用
- 精确符号（如 `n̂` 表示法向量）建议简写为 `n` 或 `n^^`，公式中再用 `$\hat{n}$` 精确表示
