# Wikilink 批量修复技术

**版本**: v50.4 | **触发条件**: 知识库构建完成后 wikilink 断裂率 >10%

## 问题识别

Knowledge base 构建完成后需独立运行 wikilink 检查——`quality_score.py` 的 errors 计数不直接反映 wikilink 完整性。需额外扫描：

```bash
# 1. 收集所有 .md 文件名
python3.12 -c "
import glob, os
files = set()
for d in ['10_总揽','20_正文','30_核心概念','40_知识要素','50_知识点','60_技能点','70_应用场景','80_实体','90_习题','90_习题/解答']:
    for f in glob.glob(f'{d}/*.md'):
        files.add(os.path.basename(f).replace('.md',''))
"

# 2. 扫描所有 [[wikilink]] 并交叉验证
```

## 三层修复流程

### L1: Fuzzy Match 构建映射

```python
from difflib import get_close_matches

# 提取断裂目标（按引用次数降序）
# 对每个断裂目标跑 fuzzy-match:
matches = get_close_matches(broken_target, existing_files, n=3, cutoff=0.4)
# 人工校验：选 closest semantic match，不自动接受 random best
```

### L2: Python Batch Replace

```python
import glob, re

mapping = {
    r'\[\[电磁兼容预测基本原理\]\]': r'[[EMC数值方法选型指南]]',
    r'\[\[电磁兼容三要素\]\]': r'[[电磁兼容三要素分析法]]',
    # ... 30-40 条映射覆盖 top ~80% 断裂
}

for md_file in glob.glob('*/*.md') + glob.glob('*/*/*.md'):
    with open(md_file) as f:
        content = f.read()
    orig = content
    for old, new in mapping.items():
        content = re.sub(old, new, content)
    if content != orig:
        with open(md_file, 'w') as f:
            f.write(content)
```

### L3: 尾部清理

L2 后剩余断裂多为低频（1-2x）域名引用或场景名，逐个人工判断：
- 有明确对应文件 → 补映射再跑一次
- 无对应文件但可合并到其他链接 → 移除链接文本，保留描述
- 引用不存在且无合理替代 → 标记为 `[[需创建]]`

## 关键原则

1. **优先修高频**：top 10 断裂目标通常覆盖 50%+ 的断裂数
2. **语义优先于字符串匹配**：fuzzy-match 给候选列表，但最终选择基于语义——不自动接受 score 最高的
3. **禁止 `replace_all=true`**：用 Python batch script 而非 patch 工具，确保每个替换发生在其所在的完整文件中
4. **验证闭环**：修复后重跑 wikilink check，目标 <15% 断裂率

## EMC 实战数据

| 阶段 | 总链接 | 断裂 | 断裂率 | 唯一断裂目标 |
|:-----|:------|:-----|:------|:-----------|
| 修复前 | 1123 | 354 | 31.5% | 162 |
| L2 第1轮 | 1123 | 163 | 14.5% | 135 |
| L2 第2轮 | 1136 | 129 | 11.4% | 121 |

**核心映射**（top 20 覆盖 124/354 = 35%）：

| 断裂目标 | 引用次数 | → 替换为 |
|:--------|:-------:|:--------|
| 电磁兼容预测基本原理 | 47 | EMC数值方法选型指南 |
| 电磁兼容三要素 | 14 | 电磁兼容三要素分析法 |
| 电磁辐射基本模型 | 13 | 发射机模型 |
| 传导耦合模型 | 10 | 传导干扰 |
| 麦克斯韦方程与电磁场基本原理 | 8 | 麦克斯韦 |
| 静电放电 | 7 | 静电放电模拟器 |
| 瞬态电磁场 | 7 | 瞬态干扰特性对比与防护方法 |
| 电磁兼容标准 | 6 | 电磁兼容测量标准选择方法 |
| 浪涌 | 6 | 雷击浪涌 |
| 雷电防护 | 6 | 雷电防护体系 |
| 频率指配算法 | 6 | 频率指配优化算法选择与应用 |
| 频率指配模型 | 6 | 频率指配约束条件建模 |
| 电磁屏蔽 | 6 | 电场屏蔽 |
| 共模干扰和差模干扰 | 5 | 差模与共模辐射 |
| 变压器耦合 | 5 | 变压器耦合隔离 |
| 插入损耗 | 5 | EMI滤波技术原理与应用 |
| 战时电磁频谱管理 | 4 | 战时电磁频谱管理计划编制 |
| 辐射发射测量 | 4 | 辐射发射测量操作流程 |
| 滤波技术概述 | 4 | EMI滤波技术原理与应用 |
| 电磁兼容基本概念 | 4 | 电磁兼容定义 |
