### 0f 公式全编号检查 □
- 每章所有 `$$` 显示公式都必须有 `\tag{N-M}` 编号
- 中间推导步骤、近似公式、分段式、换算关系均需编号
- **tag 格式检查**：`\tag{N-M}` 必须独占一行，闭合 `$$` 另一行。
  `\tag{5-1}$$`（同一行）→ 渲染失败。
  正确：
  ```latex
  $$
  公式内容
  \tag{5-1}
  $$
  ```
- 检查命令：
  ```bash
  python3 -c "import re; c=open('output/第N章.md').read(); eqs=re.findall(r'\$\$[^$]+\$\$',c); tagged=re.findall(r'\\\\\\\\tag\{',c); print(f'{len(eqs)}公式/{len(tagged)}已编号'); assert len(eqs)==len(tagged), f'缺失{len(eqs)-len(tagged)}个编号'"
  ```
- 章节中的中间推导公式（如KVL/KCL方程、微分方程、近似公式）均需编号，不得遗漏
  ```bash
  python3 scripts/fix_formula_numbers.py output/第N章-标题.md
  ```
- 章节中的中间推导公式（如KVL/KCL方程、微分方程、近似公式）均需编号，不得遗漏
- 多文件组装后必须检查重复tag：`python3 -c "import re; from collections import Counter; c=open('output/第N章.md').read(); dups={k:v for k,v in Counter(re.findall(r'tag\{\d+-\d+\}',c)).items() if v>1}; assert not dups, f'重复tag: {dups}'"`