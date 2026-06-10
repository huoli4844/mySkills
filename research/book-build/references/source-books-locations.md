# 参考教材源文件位置

> 本文件的命令通过 `book_config.py` 动态加载配置，不假设数量。

## 查看当前配置的参考教材

```bash
python3 -c "from book_config import Config; c=Config()
for i, b in enumerate(c.source_books, 1):
    print(f'参考教材{i}: {b[\"author\"]}《{b[\"display_name\"]}》→ {b[\"path\"]}')"
```

## 快速查找某主题

```bash
python3 -c "
from book_config import Config
c = Config()
results = c.grep_all_books('关键词')
for name, lines in results.items():
    print(f'=== {name} ===')
    for l in lines: print(l)
"
```

## 各书对照表

| 编号 | 作者 | 书名 | 匹配度 | 参考策略 |
|:----:|:-----|:-----|:------:|:---------|
| 1 | (从 config 读取) | | 高/中/低 | 直接使用/辅助参考/仅借鉴手法 |
| 2 | (同上) | | | |
| … | | | | |

## 非标准配置的补充参考书

| 书名 | 出版信息 | 路径 | 体量 | 适用章节 |
|:-----|:---------|:-----|:----:|:--------|
| 何金良《电磁兼容概论》 | 科学出版社，2010 | `~/Desktop/电磁兼容/处理后/电磁兼容概论_柯金良/优先级3-电磁兼容概论-柯金良.md` | 20797行 / 1.2MB | 第3章（骚扰源分类）、第4章（电磁屏蔽）、第6章（滤波技术） |

> 何金良章节对应的用户项目中：第6章（滤波）→ 第7章-滤波技术.md；第4章（屏蔽）→ 第8章-屏蔽技术.md。搜索用 `第 6 章` 或 `第 4 章` 章节标题定位。
