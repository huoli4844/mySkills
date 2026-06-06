# KBQA Log Analysis Report Template

## 报告结构

每次 KB 状态分析按以下结构输出：

```
📊 KB 状态分析报告

一、自动补齐概况
  ─ 总计已自动补齐：概念 N 个，KE M 个，KP K 个
  ─ 其中已审阅确认：N 个（由用户确认过）
  ─ 其中静默补齐：M 个（v2.0 遗留未确认）

二、高频缺失 TOP 5
  ─ 按补齐频次从高到低排序
  ─ 建议优先用出处原文升级高频缺失项

三、用户纠错统计
  ─ 总计纠错：N 次
  ─ 待验证：M 次（纠错后未验证出处）

四、连通性检查
  ─ 孤立页面（无入站链接）：N 个
  ─ 断链：N 处 wikilink 指向不存在页面

五、升级建议（0.65 → 0.95）
  优先级列表：
    1. {最高优先级概念}（高频缺失 + 可提供出处原文）
    2. {次优先级}（教材生成必需）
```

## log.md 条目格式

每次补齐/纠错操作在 log.md 中以统一格式记录：

```markdown
## [YYYY-MM-DD] kbqa | {操作类型}：{主题}

### 触发
- 问答：{用户问题}
- 检测到：{缺失描述}

### 补齐操作
- 创建 [[概念/XXX]] (confidence: 0.65, source: kbqa-v3-complete)
- 更新 [[概念/YYY]] 关联层

### 链式检查
- ✅ 知识要素/XXX — 已存在
- ✅ 知识点/XXX — 已创建（链式补齐）
```

## analyze_log() 解析规则

```python
# 补齐条目匹配：创建 [[类型/名称]]
creates = re.findall(r'创建 \[\[([^\]]+)\]\]', content)

# 纠错条目匹配：用户纠错：类型/名称
corrections = re.findall(r'用户纠错：([^\n]+)', content)

# 高频术语统计：按补齐次数排序
term_freq = Counter()
for create in creates:
    term = create.split('/')[-1] if '/' in create else create
    term_freq[term] += 1
top_missing = term_freq.most_common(5)

# 连通性：扫描概念/知识要素/知识点 目录，检查入站链接
# 每个页面扫描全库中所有 [[类型/页面名]] 引用
```
