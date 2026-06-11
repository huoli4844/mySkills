# 领域无关审计

每次修改本技能后运行以下命令检查领域词耦合：

```bash
cd ~/.hermes/skills/research/book-build

# 脚本中的领域词（排除测试文件）
grep -rn "EMC\|dBm\|dBuV\|dBμV\|GHz\|MHz\|FDTD\|CISPR\|MIL-STD\|IEC " scripts/ --include="*.py" | grep -v "test_" | grep -v "__pycache__"

# 引用文件中的领域词
grep -rln "EMC\|dBm\|dBuV\|GHz\|MHz\|CISPR\|MIL-STD" references/ --include="*.md"

# 模板中的领域词
grep -rln "EMC\|dBm\|GHz\|MHz" templates/ --include="*.md" --include="*.yaml"
```

**全部返回空才算通过。** 如有匹配，用通用占位符替换（"核心概念"、"标准A"、"策略X"等）。

## 允许的例外

- 测试用例中的领域词（测试数据可以包含虚构的领域术语）
- `generate_outlines.py` 是模板生成器，其中 `CHAPTER_TEMPLATE` 的示例填充内容要用通用占位符
