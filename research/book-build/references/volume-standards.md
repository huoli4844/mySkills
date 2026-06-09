### 体量铁律（每章 ≥ 来源书对应章的50%）
- **每章目标**：正文≥80KB，含习题/总结/参考文献后≥100KB（对标路宏敏每章~100KB/1500行）
- 第1章基准（83KB/24公式/2图）用于相对比较——后续章至少为第1章的1.2倍
- **偏薄判别阈值**：行<700 或 KB<35 —— 低于此值必须执行Phiase 0.6差距分析并扩充
- 典型扩充路径（经第8章实战验证）：
  1. 读三书原文，找出当前章节缺失的公式/案例/深度讨论
  2. 按优先级排列：核心公式推导 > 对比表 > 工程经验值 > 数字例题 > Mermaid图
  3. 每节均衡增厚——不要只在一节里塞入全部内容
  4. 中间插入用临时编号 → 全部插入完成后统一重排全部编号系统

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