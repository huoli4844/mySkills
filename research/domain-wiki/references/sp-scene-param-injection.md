# SP/Scene 批量参数注入

> v50.3 — 当 SP/Scene 缺工具名+量化参数时，机械注入标准参数再委托 Agent 精修

## 注入模板

### SP 注入到 `core_operation`

```
工具：ANSYS HFSS, CST Studio Suite, Altair FEKO, Gmsh
关键参数：网格尺寸 ≤λ/10(最高频率), 自适应迭代 ΔS<0.01, 网格数 10^5-10^7
```

### Scene 注入三个字段

- `scene_elements`：工程约束参数（成本/频率/限值/工具）
- `node_descriptions`：8 节点工作流描述（1→2→...→8 格式）
- `solution_detail`：方案详解（一、二、三、四 分项）

## 实战效果（EMC 教材）

SP: 10F → 4F（6 个修复，工具名+数值达标；4 个剩余还需更多数值）
Scene: 30F → 18F（节点描述+方案详解写入，但 checker 节标题匹配仍需调优）

## 局限

- 纯机械注入无法替代 Agent 精读源文后的深度内容生成
- Scene `_extract_subsections` 按 `###` 标题匹配，需确保注入字段与模板节标题一致
- 数值参数取自领域标准知识，非直接从源文提取
