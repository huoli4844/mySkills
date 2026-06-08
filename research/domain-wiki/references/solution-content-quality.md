# 解答内容质量增强设计

## 问题

习题解答文件中包含通用模板文字（如"该习题考查教材第X章核心内容"、"解答基于教材第X章的相关内容"），无实际教学价值。

## 挑战

| 问题 | 说明 |
|:-----|:------|
| 不同章节的模板文字不同 | Ch2: "该习题考查教材第2章..."；Ch3: "解答基于教材第3章..."——固定正则模式总会有遗漏 |
| 占位符题目 | YAML 中 `question: "第3章习题1"` → 无领域关键词 → 源文搜索找不到相关段落 |
| 源文格式 | 正文 .md 包含 YAML frontmatter，混合在段落中 |

## 方案 v51.7

### 1. 质量评分检测 (替代固定正则)

```python
# post_build_fix.py — _detect_boilerplate()
维度一：长度 < 60 字 → too_short
维度二：模板词密度 > 40%（该习题/解答/基于/教材/核心等 15 词）→ high_boilerplate_density  
维度三：不含领域术语且 < 200 字 → no_domain_terms
任一维度触发 → 判为模板，触发替换
```

**优势**：不依赖特定短语模式，Ch2 "该习题考查教材第2章..." 和 Ch3 "解答基于教材第3章..." 统一检出。

### 2. 章节标题回退关键词

```python
# post_build_fix.py — _extract_keywords()
if not keywords or re.match(r"^\d+章", q_clean):
    chapter = extract_chapter_number(question)     # "第3章习题1" → "3"
    ch_title = discover_chapters(wiki_root)[chapter]  # → "第3章 电磁兼容预测"
    ch_kw = strip_chapter_prefix(ch_title)          # → "电磁兼容预测"
    keywords += ch_kw.split()
    # 对齐 kw_map
    for q_sub, mapped in kw_map.items():
        if q_sub in ch_kw:
            keywords += mapped
```

**优势**：占位符题目也能提取到"电磁兼容预测"、"EMC"等领域关键词。

### 3. 跳过源文 YAML frontmatter

`_load_source_text()` 加载 `20_正文/第N章 xxx.md` 时用 `re.sub(r"^---\n.*?\n---\n", "", content, flags=re.DOTALL)` 剥离 YAML 头，防止 `{"title": "...", "parser": "file2md"}` 等元数据泄露到解答内容中。

## 配置依赖

| 文件 | 用途 | 跨领域 |
|:-----|:------|:--------|
| `config/knowledge_keywords.yaml` | 题目关键词→源文搜索词映射 | ✅ 换领域改此文件 |
| `config/book_info.yaml` | 章节名到描述的映射 | ✅ 换书改此文件 |
| `20_正文/第N章 xxx.md` | 源文本内容（由 file2md 生成） | ✅ 自动发现 |
