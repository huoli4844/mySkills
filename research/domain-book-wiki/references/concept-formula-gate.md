# 核心概念公式质量闸门 (v50.2)

> 核心概念必须引用源文公式。源文无公式支撑的概念应降级为 KE。

## 审计流程

```bash
# 1. 扫描全部概念，检查 mathematical_model 和 theoretical_basis 是否含 $$ LaTeX
python3.12 -c "
import yaml, re
for ch in '12345678':
    with open(f'.dag/第{ch}章/data/concepts.yaml') as f: items = yaml.safe_load(f)
    for item in items:
        mm = str(item['bd'].get('mathematical_model',''))
        tb = str(item['bd'].get('theoretical_basis',''))
        has = '$$' in mm + tb
        print(f'第{ch}章 {item[\"name\"]}: {\"✅\" if has else \"❌\"} 公式')
"
```

## 分类处理

| 概念状态 | 处理 | 原因 |
|:--------|:-----|:-----|
| 有 `$$` LaTeX 公式 | 保留 | 合格 |
| 内容≤1字（空壳） | **降级为 KE** | 从未被 Agent 填充，源文未将其作为独立核心概念讲授 |
| 有内容（100-300字）但无公式 | **降级为 KE** | 源文无公式支撑，不满足核心概念标准 |
| 有内容但公式在 WMF/EMF 图片中 | **保留**，标记需 `formula-extract` | 概念本身合格，公式需从图片提取 |
| 有 ASCII 公式（如 `dB=10lg(P1/P0)`） | **转换为 `$$` LaTeX** | 已有数学内容，格式转换即可 |

## 降级操作

```python
# 从 concepts.yaml 移除，添加到 kes.yaml
import yaml

with open('.dag/第N章/data/concepts.yaml') as f: concepts = yaml.safe_load(f)
with open('.dag/第N章/data/kes.yaml') as f: kes = yaml.safe_load(f)

kept, removed = [], []
for item in concepts:
    if item['name'] in ['干扰源分类', ...]:  # 待降级列表
        ke_entry = {
            'name': item['name'],
            'file': item.get('file', item['name']),
            'fm': {
                'source_chapter': ch,
                'confidence': 0.85,
                'confidence_note': '从核心概念降级(源文无公式支撑)',
            },
            'bd': {
                'term_definition': '（降级自核心概念，详见20_正文源文）',
                'definition_sentence': item.get('bd',{}).get('definition_sentence','无'),
            },
        }
        kes.append(ke_entry)
        removed.append(item['name'])
    else:
        kept.append(item)

with open('.dag/第N章/data/concepts.yaml','w') as f: yaml.dump(kept, f, ...)
with open('.dag/第N章/data/kes.yaml','w') as f: yaml.dump(kes, f, ...)

# 删除旧 .md
os.remove('30_核心概念/干扰源分类.md')
```

## ASCII→`$$` 转换

源文 .md 中的 ASCII 数学表达式直接包装为 `$$` LaTeX：

```python
def ascii_to_latex(mm_text):
    lines = mm_text.split('\n')
    result = []
    for line in lines:
        if re.search(r'[=≈×÷∫∂∇√αβγδεθλμπ]', line):
            result.append(f'$${line.strip()}$$')
    return '\n\n'.join(result)
```

## 实战数据（EMC 教材）

| 指标 | 修复前 | 修复后 |
|:-----|:------|:------|
| 概念总数 | 34 | 25 |
| 概念有公式 | 11 (32%) | 25 (100%) |
| 降级为 KE | — | 9 个 |
| 空壳概念 | 9 个 | 0 |
