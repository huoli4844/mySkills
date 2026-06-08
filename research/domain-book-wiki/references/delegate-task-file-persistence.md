# delegate_task 文件持久化陷阱

## 问题

`delegate_task` 子代理调用 `write_file`（hermes_tools）时，文件写入的是**子代理自身隔离上下文的工作目录**，而非调用者的项目目录。子代理任务完成后，其工作目录被清理，文件消失。

**症状**：子代理 summary 声称"文件创建成功"，但 `ls` 目标路径找不到该文件。写入越大（>10KB）越容易触发，但不是文件大小问题——是路径隔离问题。

**实测数据**（本技能 2026-06-08 第3/4/5章构建）：
- 第3章 concepts.yaml（8条概念）：Agent A 写入成功（`write_file` 走终端→绝对路径）✅
- 第3章 kps.yaml/sps.yaml/scenes.yaml（文件字段缺失修复）：Agent B 失败——写了 5 个文件但全部丢失 ❌
- 第5章 concepts.yaml/kes.yaml/entities.yaml（9+13+19条）：Agent C 声称写入成功但文件找不到 ❌
- 第5章 kps.yaml/sps.yaml/scenes.yaml/exercises.yaml/solutions.yaml（7+3+2+15+15条）：Agent D 同样失败 ❌

**根因**：delegate_task 子代理的 `terminal`/`file` 工具运行在 `chdir(临时目录)` 下，该临时目录随任务结束而删除。`write_file("path/to/file.yaml", content)` 使用相对路径时写入临时目录而非项目目录。绝对路径也可能被 routed 到上下文虚拟目录。

## 解决方案

### 方案 A（推荐）：父代理用 execute_code 写入

子代理 context 中嵌入 YAML 的 Python dict/list 表示，或让子代理返回文件内容的文本摘要。父代理收到 summary 后：

```python
from hermes_tools import write_file
import yaml

data = [{"name": "...", "bd": {...}}, ...]
with open("/abs/path/.dag/第N章/data/concepts.yaml", "w") as f:
    yaml.dump(data, f, allow_unicode=True, default_flow_style=False,
              sort_keys=False, indent=2, width=120)
```

`execute_code` 运行在父代理上下文中，文件写入项目目录后持久保留。

### 方案 B：子代理用 terminal cat > 绝对路径

子代理在 context 末尾必须包含：

```
使用 terminal 执行: python3 -c "
import yaml
data = [...]
with open('/absolute/path/target.yaml', 'w') as f:
    yaml.dump(data, f, allow_unicode=True, default_flow_style=False)
"
```

绝对路径必须在 context 中明确给出。相对路径不可靠。

### 方案 C：先 write_file 后 terminal cp

```python
from hermes_tools import write_file, terminal
# 写入临时目录（子代理 context 内）
write_file("concepts.yaml", content)
# 复制到目标绝对路径
terminal("cp concepts.yaml /target/path/.dag/第N章/data/concepts.yaml")
```

## 验证

无论哪种方案，父代理必须在 delegate_task 返回后独立验证文件存在：

```python
import os
assert os.path.exists(target_path), f"子代理声称写入的文件不存在：{target_path}"
```
