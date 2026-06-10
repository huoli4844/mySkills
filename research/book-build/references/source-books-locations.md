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

> 匹配度和策略因章节而异，需根据关键词搜索判断。
