# 公式抽取指南：从 WMF 图片还原 LaTeX

## 问题背景

file2md 将 .docx 中的 OMML 公式转换为 **WMF/EMF 图片**（矢量图），而非 LaTeX。因此 `20_正文/第N章.md` 中的公式显示为：

```
![](assets/image-xxx.wmf)
```

vision_analyze 无法读取 WMF 格式。公式内容需从**上下文**推断并手写 LaTeX。

## 抽取技术

### 公式推断方法

1. **读容器上下文**：用 `read_file(offset=line, limit=N)` 读取概念容器（行号范围从 `chapter_toc.json` 获得）
2. **理解变量含义**：正文中 WMF 图片前后的文字描述给出变量名称和公式结构。例如：
   ```
   导线间的间距![](assets/image-183.wmf)远大于导体半径![](assets/image-184.wmf)
   ```
   推断：`image-183.wmf` = s（间距），`image-184.wmf` = a（半径）
3. **写 LaTeX**：基于上下文复原公式

### 关键公式选择标准

优先抽取 **3-5 个关键公式**/概念，非穷举：
- **定义公式**：概念的核心数学关系（如传输线方程、BLT方程）
- **工程公式**：实际计算用的公式（如辐射场强公式、谐波统计模型）
- **边界公式**：判据/分界条件（如远场条件、频谱边界）

### LaTeX 格式要求

必须使用 **独占三行**格式：

```
$$
\\frac{\\partial V}{\\partial x} + R I = 0
$$
```

否则 `comprehensive-content-check.py` 会 FAIL（"$$ 未独占三行"）。

### Python 写法

使用 `LiteralBlock` 类强制 YAML 的 `|` 块标量样式：

```python
class LiteralBlock(str): pass
yaml.add_representer(LiteralBlock, 
    lambda d, data: d.represent_scalar('tag:yaml.org,2002:str', data, style='|'))

def lb(s): return LiteralBlock(s)

c['bd']['formula_references'] = lb("""$$
\\nabla \\times \\mathbf{H} = \\mathbf{J} + \\frac{\\partial \\mathbf{D}}{\\partial t}
$$""")
```

### 验证

```bash
# 检查公式格式
grep -P '\\$\\$[^\\n]' 30_核心概念/*.md

# 运行综合检查
python3 comprehensive-content-check.py <wiki_root> | grep "公式块"
```

返回 0 个 FAIL 即为通过。
