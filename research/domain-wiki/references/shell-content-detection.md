# Shell Content Detection（空壳内容检测）

## 问题

`comprehensive_content_check.py --depth-check` 在知识库中存在大量空壳内容时返回 `0 项`，未能检测到占位符填充。一次审计发现 95 个解答中 76 个 (80%) 是骨架占位符，但 content-check 全部放行。

## 空壳签名模式

以下模式在解答/KP/SP/Scene 中出现意味着该文件是未填充的骨架：

### 解答占位符

```
解答基于教材第X章...
核心特征分析。
考点解析。
常见错误辨析。
解题技巧。
分步解题流程。
关联知识体系。
相关概念的定义和物理意义。
相关数学推导过程。
在实际工程中的应用。
```

### KP/SP/Scene 空壳特征

- 整节空白：`## 二、核心能力层` 后紧跟 `## 三、实践支撑层`（中间零内容）
- Mermaid 图显示 "无" 文本
- 源文件大小 < 阈值 50%（如 KP < 4KB，SP < 3KB，Scene < 3.5KB）

## 批量审计脚本

```python
import os, re

base = "<BOOK_DIR>"
thresholds = {
    "30_核心概念": 8000,
    "40_知识要素": 2000,
    "50_知识点": 8000,
    "60_技能点": 6000,
    "70_应用场景": 7000,
    "80_实体": 500,
}

# === Phase 1: 大小合规率 ===
for dir_name, threshold in thresholds.items():
    dir_path = os.path.join(base, dir_name)
    if not os.path.exists(dir_path):
        continue
    total = below = 0
    for fname in os.listdir(dir_path):
        if not fname.endswith('.md'):
            continue
        total += 1
        if os.path.getsize(os.path.join(dir_path, fname)) < threshold:
            below += 1
    rate = (total - below) / total * 100 if total > 0 else 0
    print(f"{dir_name}: {total-below}/{total} pass ({rate:.0f}%)")

# === Phase 2: 解答占位符检测 ===
placeholders = [
    '解答基于教材', '核心特征分析。', '考点解析。', '常见错误辨析。',
    '解题技巧。', '分步解题流程。', '关联知识体系。',
    '相关概念的定义', '相关数学推导过程', '在实际工程中的应用。',
]
sol_dir = os.path.join(base, "90_习题/解答")
for fname in sorted(os.listdir(sol_dir)):
    if not fname.endswith('.md'):
        continue
    with open(os.path.join(sol_dir, fname)) as f:
        content = f.read()
    if any(ph in content for ph in placeholders):
        print(f"SHELL: {fname} ({os.path.getsize(os.path.join(sol_dir, fname))}B)")

# === Phase 3: 空节检测 ===
for dir_name in thresholds:
    dir_path = os.path.join(base, dir_name)
    if not os.path.exists(dir_path):
        continue
    for fname in sorted(os.listdir(dir_path)):
        if not fname.endswith('.md'):
            continue
        with open(os.path.join(dir_path, fname)) as f:
            lines = f.readlines()
        for i, line in enumerate(lines):
            m = re.match(r'^(#{2,3})\s+(.+)', line)
            if not m:
                continue
            heading = m.group(2).strip()
            hlevel = len(m.group(1))
            next_i = i + 1
            has_content = False
            while next_i < len(lines):
                nl = lines[next_i].strip()
                nm = re.match(r'^(#{1,3})\s+', nl)
                if nm and len(nm.group(1)) <= hlevel:
                    break
                if nl and not nl.startswith('```') and nl not in ['', '>', '---']:
                    has_content = True
                    break
                next_i += 1
            if not has_content:
                print(f"BLANK: {dir_name}/{fname}: '{heading}'")
```

## 修复建议

在 `content_check_rules.py` 中增加 `_check_shell_placeholders()` 函数，对 `.md` 生成文件扫描占位符模式，命中则标记 FAIL 阻断 pipeline。
