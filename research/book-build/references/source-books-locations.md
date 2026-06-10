# 参考教材源文件位置

> 本文件中的路径和书名均为示例。实际使用前修改 `config.yaml` → `source_books` 即可。

## 当前配置的三书

```bash
python3 -c "from book_config import Config; c=Config()
for b in c.source_books:
    print(f'{b[\"author\"]}: {b[\"display_name\"]} ({b[\"path\"]})')"
```

## 快速查找某主题

```bash
# 通过 book_config.py 的快捷方法搜索
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

| 角色 | 作者 | 匹配度 | 参考策略 |
|:----|:-----|:------:|:---------|
| 书A (主骨架) | {book_a_author} | 高 | 直接使用 |
| 书B (补充) | {book_b_author} | 中 | 辅助参考 |
| 书C (辅助) | {book_c_author} | 中低 | 仅借鉴手法 |

> 不同章节各书的匹配度不同，需根据关键词搜索判断。详见 `chapter-writing-workflow.md` Step 1.3。
