# Concept Quality Audit Methodology (v46.0)

从实际 EMC 教材审计中提炼的批量概念质量控制方法。

## 两阶段审计工作流

### Phase 1: 批量覆盖率扫描（grep 级，1 min）

对 `30_核心概念/` 目录所有 `.md` 文件运行系统性缺陷检测：

```bash
grep -L 'formula_references\|公式引用' *.md | wc -l    # 缺失公式节
grep -L 'figure_references\|图引用' *.md | wc -l       # 缺失图引用
grep -L 'self_check\|自学检验' *.md | wc -l             # 缺失自检题
grep -L 'application_scenarios\|应用场景' *.md | wc -l   # 缺失应用场景
grep -L 'confusion_compare\|相近概念辨析' *.md | wc -l   # 缺失辨析表
grep -l '\$\$' *.md | wc -l                            # 含 LaTeX 公式
```

子节数、wikilink、表格数检测：
```bash
grep -c '^### ' *.md   # <12 = 不合格
grep -c '\[\[' *.md     # <3 = 不合格
grep -c '^|' *.md       # 0 = 缺失辨析表
```

### Phase 2: 深度抽样审计（子代理并行，5-10 min）

选取 3-7 个代表性文件，用 `delegate_task` 并行深度分析：

- **最小文件** → 检查是否因篇幅不足省略了必填字段
- **最大文件** → 检查是否有冗余
- **理论型**（含方程/模型/计算/定理）→ mathematical_model 是否有 LaTeX
- **方法型**（含测量/测试/防护/管理）→ application_scenarios >= 3

每个子代理对照 `concept-content-spec.md` 逐字段检查：
1. 定义句来源可验证性（前120字在源文中能检索到）
2. 公式归属正确性（$$ LaTeX 而非纯文本）
3. Mermaid 图质量（节点数>=5、classDef着色、无内嵌公式）
4. 必填字段完整度（7个缺失=超过<=5红线）
5. 学习目标真实性（Bloom层级+自学检验题）

## 三类典型系统性缺陷

### P0: 零 LaTeX（100% 命中率）
现象: 全部文件用纯文本写公式（`dB=10lg(P1/P0)`），无 `$$` 块级 LaTeX。
根因: 模板 v6.0 未在数学模型节做格式提示；spec 将 formula_references 列为"推荐"。
修复: 模板 v6.1 加 HTML 注释提示；spec 升级为"条件必需"。

### P0: 零图引用（100% 命中率）
现象: 源文有图但概念文件完全未引用。
根因: 模板 v6.0 无 figure_references 占位符；spec 列为"推荐"。
修复: spec 升级为"条件必需"。

### P1: 零自学检验题（100% 命中率）
现象: 模板 v6.0 无 {{self_check_questions}} 占位符。
修复: 模板 v6.1 新增 ### 自学检验 节。

## 概念准入：三标准

核心概念必须同时满足：
1. 篇幅 >= 50 行容器（正文长篇讲授，不是一笔带过）
2. 支撑 >= 3 个公式+图+表
3. 有展开结构（子标题或多段落）

EMC教材实例：8章 182 个容器，通过三标准仅 34 个（18.7%）。其余 148 个容器应归入 KE。

## delegate_task 并行审计模式

```python
tasks = [
    {"goal": "审计第1-2章", "context": "TOC在/tmp/toc_ch1.json..."},
    {"goal": "审计第3-5章", "context": "..."},
    {"goal": "审计第6-8章", "context": "..."},
]
```
