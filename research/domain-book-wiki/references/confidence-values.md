# 各类型 confidence 允许值速查表 (v43.5)

| 类型 | YAML 文件 | confidence | 说明 |
|:-----|:---------|:---------:|:-----|
| concept | concepts.yaml | **0.95** | 核心概念，直接来自教材 |
| ke | kes.yaml | **0.85** | 知识要素，简短定义 |
| entity | entities.yaml | **0.85** | 实体，直接来自教材 |
| kp | kps.yaml | **0.85** | 知识点，系统化整合 |
| sp | sps.yaml | **0.75** | 技能点，实操化 |
| scene | scenes.yaml | **0.65** | 应用场景，场景化加工 |
| exercise | (auto-generated) | **0.65** | 习题，自动检测 |
| solution | solutions.yaml | **0.85** (或 0.65) | 习题解答，允许 {0.65, 0.85} |

超过允许值的 YAML 在 `build_kb_files.py` 中会被 FM 校验阻断。
