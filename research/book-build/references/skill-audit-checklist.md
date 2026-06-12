# SKILL.md 审计检查清单

> 本检查单用于审计和精简 SKILL.md，确保符合 skill-authoring 规范。每次修改 SKILL.md 后运行。

## 快速检查（5 步）

```bash
# 1. 行数检查
wc -l SKILL.md
# 目标: 复杂管线 150-250 行，300+ 为红牌

# 2. Frontmatter 验证
python3 -c "
import yaml, re
c = open('SKILL.md').read()
assert c.startswith('---')
m = re.search(r'\n---\s*\n', c[3:])
fm = yaml.safe_load(c[3:m.start()+3])
assert 'name' in fm and 'description' in fm
assert len(fm['description']) <= 1024
assert fm['description'].startswith('Use when')
print('PASS')
"

# 3. Code block 比例
python3 -c "
import re
c = open('SKILL.md').read()
blocks = re.findall(r'\`\`\`.*?\n(.*?)\`\`\`', c, re.DOTALL)
code_lines = sum(b.count('\n')+1 for b in blocks)
total = len(c.split('\n'))
pct = code_lines/total*100
print(f'{code_lines}/{total} code lines ({pct:.0f}%)')
assert pct < 30, f'Too much code in SKILL.md: {pct:.0f}%'
"

# 4. 引用完整性
python3 -c "
import os, re
c = open('SKILL.md').read()
broken = []
for m in re.finditer(r'\`(references/[^.]+\.md|scripts/[^.]+\.py|templates/[^.]+\.(md|yaml))\`', c):
    if not os.path.exists(m.group(1)):
        broken.append(m.group(1))
assert len(broken) == 0, f'BROKEN: {broken}'
print('All references resolve.')
"

# 5. 死文件扫描
python3 -c "
import os, re
from pathlib import Path
refs = set()
for metafile in ['SKILL.md', 'references/INDEX.md', 'references/ref-quickref.md']:
    if os.path.exists(metafile):
        c = Path(metafile).read_text()
        for m in re.finditer(r'\b(references/[a-z0-9_-]+\.md|scripts/[a-z0-9_/]+\.py|templates/[a-z0-9_-]+\.(md|yaml))', c):
            refs.add(m.group(1))
dead = []
for f in os.listdir('references'):
    path = f'references/{f}'
    if path not in refs and path not in ['references/INDEX.md', 'references/ref-quickref.md', 'references/changelog.md']:
        dead.append(f'{path} ({os.path.getsize(path)//1024}KB)')
for f in os.listdir('scripts'):
    path = f'scripts/{f}'
    if path not in refs and os.path.isfile(path):
        dead.append(f'{path} ({os.path.getsize(path)//1024}KB)')
if dead:
    print(f'{len(dead)} unreferenced files:')
    for d in dead: print(f'  {d}')
else:
    print('No dead files.')
"
```

## 常见红牌信号

| 红牌 | 描述 | 修复 |
|:-----|:-----|:-----|
| 容量红线表 | "SKILL.md ≤ 300行" 本身占 20+ 行 | 删除整个表，信任代码审查 |
| "SKILL.md 设计原则" | 元规则描述 SKILL.md 自身 | 移到 `references/` |
| 25+ pitfalls | 太多陷阱，Agent 无法全部记忆 | 保留前 10 条核心，其余移入 `references/pitfalls.md` |
| description 非 "Use when..." | 中文或不完整 | 改为 "Use when <trigger>. <one-line behavior>." |
| 引用 `references/chapter-writing-guide-template.md` | 文件在 `templates/` 不在 `references/` | 修正路径 |
| 0KB 文件 | 空文件残留 | `rm -f` |
| 废弃脚本 | `search_kb.py`/`parse_outline.py` 等旧工具 | 删除（git history 可恢复） |
| 旧框架文档 | `six-elements.md`/`six-dimension-audit.md` | 已合并入主系统，删除旧文件 |
