# 内容差距分析检查清单（Phase 0.6）

> 参考教材数量从 `config.yaml` → `source_books` 动态读取。

## Step 1：定位各书对应内容

```bash
python3 -c "
from book_config import Config
c = Config()
import subprocess, sys
kw = sys.argv[1] if len(sys.argv) > 1 else '关键词'
for b in c.source_books:
    r = subprocess.run(['grep', '-n', kw, b['path']], capture_output=True, text=True, timeout=10)
    print(f'=== {b[\"author\"]}《{b[\"display_name\"]}》 ===')
    for l in r.stdout.strip().split(chr(10))[:10]:
        print(l)
" "关键词"
```

注意：章号可能不匹配，通过关键词搜索而非按章号定位。

## Step 2：逐书阅读

按 priority 升序阅读（最高优先级的书最先读）。

每本书重点读：章首（前30%）、核心技术节（全部）、章末（后20%）。

## Step 3：编制定量对比表

动态对比：对每本参考书各开一列：

| 维度 | 当前章 | 书1 | 书2 | 书3 | … |
|:-----|:------:|:---:|:---:|:---:|:-:|
| 公式数 | | | | | |
| 例题数 | | | | | |
| Mermaid图 | | | | | |
| 对比表 | | | | | |
| 习题数 | | | | | |

（列数 = config 中 source_books 的数量）

## Step 4：三类素材标记

| 标记 | 含义 | 处理方式 |
|:----:|:-----|:---------|
| ✅ 已使用 | 当前章已包含 | 无需操作 |
| ⬜ 可补充 | 参考书有、当前章没有、可自然融入 | 估算补充量→按优先级加入 |
| ❌ 超范围 | 需要额外理论，超出典型教材深度 | 记录但不纳入 |

## Step 5：估算补充量

每项标注：来源书、融入位置、估算行数、优先级（高/中/低）。

## Step 6：确认内容天花板

如果所有参考书中该主题的最大章节体量×1.5后仍低于目标，且无额外理论可展开，说明天花板已到。

替代策略：
1. 加深案例（经过→分析→启示三段式）
2. 加对比表（跨维度对比）
3. 加工程经验值（领域常见经验值）
4. 加Mermaid图（文字决策树转图）
