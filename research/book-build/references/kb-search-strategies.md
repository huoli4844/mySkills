# KB 搜索策略参考

根据知识库目录结构类型，选择不同的搜索策略。

## 策略表

| KB 结构 | 搜索策略 | 关键字 |
|:--------|:---------|:-------|
| **emc-textbook-wiki 格式**（概念/知识要素/知识点/技能点/场景/习题解答 目录） | 按优先级搜索: 知识点/>概念/>知识要素/>技能点/>场景/ | `native-kbqa` |
| **按章分目录**（第1章/第2章/...） | 先搜索目标章节目录，再全文搜索 | `chapter-dirs` |
| **平面目录**（所有 .md 在同层） | 文件名优先 → 内容 grep 全文 | `flat` |
| **PDF/DOCX 原始文件** | 先 file2md 转换 → 再搜索 .md 文件 | `raw-files` |

## 自动检测 KB 结构的方法

```bash
# 1. 是否 emc-textbook-wiki 格式？
ls {KB_DIR}/概念/ 2>/dev/null && echo "has-concept-dir"
ls {KB_DIR}/知识要素/ 2>/dev/null && echo "has-ke-dir"
ls {KB_DIR}/知识点/ 2>/dev/null && echo "has-kp-dir"

# 2. 是否按章分目录？
ls {KB_DIR}/第1章/ 2>/dev/null && echo "chapter-dirs"
ls {KB_DIR}/第01章/ 2>/dev/null && echo "chapter-dirs"

# 3. 平面模式？
find {KB_DIR} -maxdepth 1 -name "*.md" | head -1 | wc -l
```
