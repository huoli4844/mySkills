# comprehensive-content-check 已知假阳性（误判）

## KP Mermaid#2: "有图无说明"

**症状**：`comprehensive-content-check.py` 报告 `[knowledge/xxx] Mermaid#2: 有图无说明（缺少文字解析或仅含"无"）`，但实际生成的 `.md` 文件中 `### 知识脉络图解析` 节有 100+ 字分析文本。

**验证方法**：
```bash
# 独立验证假阳性（对目标文件运行相同检查逻辑）
python3 -B -c "
import importlib.util as u
spec = u.spec_from_file_location('ccc', '$HOME/.hermes/skills/domain-book-wiki/scripts/comprehensive-content-check.py')
mod = u.module_from_spec(spec)
spec.loader.exec_module(mod)
fails, warns = mod.check_file_full('40_知识点/xxx.md', 'knowledge', '.')
print('FAIL:', fails)
print('WARN:', [w for w in warns])
"
# 检查分析文本是否真实存在
grep -A2 "知识脉络图解析" 40_知识点/xxx.md
```

**诱因**（未完全定位）：
1. Python 字节码缓存 `__pycache__/*.pyc` 中缓存了旧版本函数
2. Unicode 字符类中 `\\` 与 `-` 的范围运算符歧义（不同 Python 3.x 小版本行为不一致）

**缓解**：
```bash
rm -rf "$WIKI_ROOT/.dag/check_logs/"  # 清除缓存日志
python3 -B ~/.hermes/skills/domain-book-wiki/scripts/comprehensive-content-check.py "$WIKI_ROOT"
# -B 禁用字节码写入/读取
```

## 相关 pitfall

SKILL.md pitfall #38
