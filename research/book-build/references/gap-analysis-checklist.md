# 三书内容差距分析检查清单（Phase 0.6）

> 路径通过 `book_config.py` 从 `config.yaml` 加载，无需硬编码。

## Step 1：定位三本书的对应内容

```bash
# 通过 book_config.py 搜索关键词
python3 -c "
from book_config import Config
c = Config()
import subprocess, sys
kw = sys.argv[1] if len(sys.argv) > 1 else '关键词'
for b in c.source_books:
    r = subprocess.run(['grep', '-n', kw, b['path']], capture_output=True, text=True, timeout=10)
    print(f'=== {b[\"author\"]} ({b[\"display_name\"]}) ===')
    for l in r.stdout.strip().split(chr(10))[:10]:
        print(l)
" "关键词"
```

注意：章号可能不匹配，需通过关键词搜索而非机械按章号定位。

## Step 2：逐书阅读

阅读顺序：书A（最详尽优先）→ 书B（工程案例最多）→ 书C（结构最清晰）

每本书重点读：章首（前30%）、核心技术节（全部）、章末（后20%）。

## Step 3：编制定量对比表

| 维度 | 当前章 | 书A | 书B | 书C |
|:-----|:------:|:---:|:---:|:---:|
| 公式数 | | | | |
| 例题数 | | | | |
| Mermaid图 | | | | |
| 对比表 | | | | |
| 习题数 | | | | |

## Step 4：三类素材标记

| 标记 | 含义 | 处理方式 |
|:----:|:-----|:---------|
| ✅ 已使用 | 当前章已包含 | 无需操作 |
| ⬜ 可补充 | 三书有、当前章没有、且能自然融入 | 估算补充量→按优先级加入 |
| ❌ 超范围 | 需要额外物理理论，超出典型教材深度 | 记录但不纳入 |

## Step 5：估算补充量

每个可补充项标注：来源书/节号、融入位置、估算行数、优先级（高/中/低）。

## Step 6：确认内容天花板

如果三本书中该主题的最大章节体量×1.5后仍低于目标，且无额外理论可展开，说明天花板已到。

天花板到达后的替代策略：
1. 加深案例（经过→分析→启示三段式）
2. 加对比表（跨维度对比）
3. 加工程经验值（"导线电感≈1μH/m"类实战经验）
4. 加Mermaid图（文字决策树转图）
