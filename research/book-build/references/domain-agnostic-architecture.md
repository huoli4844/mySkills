# 领域无关架构设计（2026-06-16）

## 核心理念

```
SKILL 层 → 100% 领域无关（方法论/流程/约束）
                ↓
book-build.yaml → 客户在这里确定领域
                ↓
setup_project.py → 读取参考书原文 → 提取章节标题
                → 词频统计 → 写入 domain-context.yaml
                ↓
generate_outlines.py → 读取 domain-context.yaml → 填充模板变量
```

## 领域信号提取（从参考书原文）

数据源：minerU 处理过的 .md 文件（非 file2md）
位置：book-build.yaml 中 source_books[].path 指向的路径

minerU 格式特征：
- `## 第X章 标题` — 真正的章节头
- `## X.Y 标题` — 真正的子节头
- `## 前言` / `## 目录` / `## 图书在版编目(CIP)` — 噪声，需过滤
- 文件可能有数百个 `#`/`##` 行，约一半是噪声
- 不同书的格式不一致（有的有"入门篇""提高篇"分层）

提取策略：
1. 按 `##` 分割所有行
2. 过滤噪声行：含 "CIP"/"前言"/"目录"/"内容简介"/"图书在版"/纯数字结尾 等特征
3. 识别章节模式：`## 第X章` → chapter；`## X.Y` → section
4. 去重（目录列表和正文可能重复）
5. 多本书合并 → 词频统计 → top 高频词决定领域判定

## 模板变量机制

CHAPTER_TEMPLATE 中使用 `{{domain_name}}` `{{standards}}` 等占位符。
运行时先读取 domain-context.yaml：
- 存在 → 用领域信号填充变量
- 不存在 → 退化为通用文字，不报错

## 知识点图谱（防止"写偏"）

多本参考书的组织结构不同（A 把"屏蔽"放第4章，B 放第3章），需要跨书的概念共识来兜底。

### 构建方式

```python
# 每本书的 TOC 提取后的合并处理
def build_knowledge_graph(toc_list):
    graph = {
        "domain_name": "电磁兼容",
        "keywords": ["电磁兼容", "干扰", "屏蔽", "接地", "滤波"],
        "core_concepts": [
            {"name": "电磁干扰三要素", "frequency": 4,
             "books": ["路宏敏","张亮","梁振光","柯金良"]},
            {"name": "屏蔽效能", "frequency": 3,
             "books": ["路宏敏","张亮","梁振光"]},
        ],
        "standards_family": "iec",
        "total_concepts": 87,  # 去重后
    }
```

关键词提取规则：
1. 每本书的章节标题 → 去掉编号、修饰词 → 提取名词性短语
2. 跨书合并 → 按出现频次排序
3. 高频（3+ 本）→ 核心概念，必须覆盖
4. 中频（2 本）→ 建议覆盖
5. 低频（1 本）→ 可选

### 用途

| 用途 | 使用阶段 |
|:-----|:---------|
| 确定领域名 + domain-context.yaml | setup_project.py 初始化 |
| 填充 references/ 模板 | setup_project.py 初始化 |
| 填充 writing-guide 的"必含要素" | generate_outlines.py |
| 质量审计：高频概念是否写入 | quality_audit.py（可选扩展） |

### 不做的事

- 不全文语义分析
- 不引入 NLP 库
- 不建 SQLite
- 纯正则提取 + 字符串去重统计

## 执行计划（v3.5.0）

| 顺序 | 步骤 | 提交 |
|:----:|:-----|:-----|
| 1 | references/ + SKILL.md 模板化（替换为 {{var}}） | ① |
| 2 | scripts/ + templates/ 去领域化 | ② |
| 3 | 新增 extract_book_toc.py（借鉴 domain-wiki 章节检测模式） | ③ |
| 4 | 新增 build_knowledge_graph.py（多书 TOC 合并 → 词频统计） | ④ |
| 5 | 增强 setup_project.py（渲染 + 初始化流程） | ⑤ |
| 6 | generate_outlines.py 读取领域上下文 | ⑥ |
| 7 | 验证 + 打 tag book-build-v3.5.0 | ⑦ |

## 不做的

- 不读参考书全文，只读前 200~500 行（覆盖章节标题区）
- 不引入 NLP 库
- 不解析 PDF/DOCX
- 不修改 book-build.yaml 格式
