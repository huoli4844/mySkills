# 双遍精读 + 质量审查 Agent 工作流

> v50.8: Agent 自由读源文 → 填全部字段 → 质量审查 → 迭代修正

## 核心理念

```
不限制读取范围，给地图。
  - TOC 结构是地图，不是栅栏
  - suggested_start/end 是起点建议，不是边界
  - Agent 自行判断"这个概念覆盖到哪里，需要读多少行"
```

## 第一遍：精读源文 → 填完整 YAML

### 输入

从 `phase2_tasks.json` 获取：

```json
{
  "container_index": 3,
  "title": "电场屏蔽",
  "suggested_start": 120,
  "suggested_end": 190,
  "line_count": 70,
  "support_count": 55,
  "source_segment": "(前800字预览)",
  "estimated_type": "concept"
}
```

以及整章 `toc_overview`：

```json
[
  {"index": 0, "title": "4.1 接地", "line": 30, "line_end": 110},
  {"index": 1, "title": "4.2 搭接", ...},
  {"index": 2, "title": "4.3 屏蔽", "level": 2, "line": 120, "line_end": 430},
  {"index": 3, "title": "电场屏蔽", "level": 3, "line": 130, "line_end": 200},
  ...
]
```

### Agent 的工作

#### Step 1: 判断读取范围

看 TOC 决定读取范围：
- 如果此概念只占一个容器（`level=3` 子节），读容器范围即可
- 如果概念跨越多个子节（如 `4.3 屏蔽` 包含电场/磁场/薄膜三个子概念），需要扩大读取
- 如果概念是全文核心主题（如 `电磁兼容概述`），可能需要读整章

**Agent 用 `read_file()` 自主决定读多少**，不受脚本限制。

#### Step 2: 精读后写完整 YAML

一次性完成概念模板中全部 43 个字段：

```yaml
- name: 电场屏蔽
  file: 电场屏蔽
  fm:
    source_chapter: "4"
    source_from: "§4.3.1"
    confidence: 0.95
    confidence_note: 精准释义逐字匹配出处原文
  bd:
    # 从源文逐字复制
    definition_sentence: "电场屏蔽是指..."
    term_definition: "利用金属屏蔽体对电场进行衰减的技术..."
    term_english: "Electric Field Shielding"
    # 从源文提取公式
    mathematical_model: |
      $$SE = R + A + B$$
    formula_references: 公式(4-15)~(4-20)
    # 从源文提取参数
    key_parameters: 屏蔽效能 SE(dB)，截止频率 fc(Hz)，材料电导率 σ(S/m)
    # 从源文理解后创作
    structure: 工作原理 + 三种机制 + 影响参数
    application_scenarios: 机箱屏蔽、电缆屏蔽、窗口屏蔽
    engineering_practices: 屏蔽体材料选择、接缝处理、通风孔设计
    # 自行绘制概念图
    core_concept_map: |
      graph TD
        A[入射电场] --> B[反射损耗 R]
        A --> C[吸收损耗 A]
        A --> D[多次反射修正 B]
        B --> E[屏蔽效能 SE=R+A+B]
        C --> E
        D --> E
    core_concept_map_analysis: 上图展示了电场屏蔽的三种物理机制...
    # 教学相关
    learning_objectives: 知道→理解：掌握电场屏蔽的三种损耗机制
    prerequisite_knowledge: 电磁波理论、传输线理论
    self_check_questions: 1. 电场屏蔽与磁场屏蔽的区别？...
    solved_problem: 解决电子设备间的电场耦合干扰问题
    # 关联
    related_concepts_relations: |
      - [[30_核心概念/磁场屏蔽|磁场屏蔽]]：互补关系，高频磁场屏蔽原理不同
      - [[30_核心概念/非实心型屏蔽体屏效计算|非实心型屏蔽体]]：特殊形式
    # 可自动派生或默认的
    domain: 电磁兼容
    classification: 屏蔽技术
    features: 高频特性好、低频需高磁导率材料
    value: 是EMC设计中最基本、最有效的抑制措施之一
    evolution: 从单层金属板→多层复合材料→薄膜屏蔽
```

#### 写作质量要求

```
每个 ≥50 字（不准一句话带过）
定义句 = 逐字复制源文（含正确引号字符）
公式 = 正确 LaTeX 语法
场景 = ≥2 个具体场景
误区 = ≥2 个常见错误认知
关联 = ≥2 个关联概念
```

## 第二遍：质量审查

### Step 3: 写入 review 字段

写完所有 `bd` 字段后，**对自己写的内容逐条审查**，结果写入 `review` 字段：

```yaml
- name: 电场屏蔽
  fm: {...}
  bd: {...}
  # ── 质量审查（Agent 自审） ──
  review:
    status: PASS             # 或 NEED_REVISION
    checks:
      rigorous:
        status: PASS
        comment: 定义句逐字匹配源文，LaTeX 语法正确
      richness:
        status: PASS
        comment: 场景3个，工程实践2个，误区2个
      depth:
        status: NEED_REVISION
        details:
          - core_concept_map_analysis 不够详细（仅50字）
            → 应展开说明三种损耗的物理机制
      teaching:
        status: PASS
        comment: 学习目标按 Bloom 分层，自检题3道
```

### 审查标准

#### 1. 严谨性 (rigorous)

| 检查项 | 标准 |
|:-------|:-----|
| definition_sentence | 前 120 字可在源文中逐字检索 |
| mathematical_model | LaTeX 花括号平衡，无空 `\frac{}` |
| 公式符号 | 公式中所有符号在正文中有定义 |
| 概念名 | 名词短语，非动词短语 |
| source_from | 与实际 TOC 位置一致 |

#### 2. 丰富性 (richness)

| 检查项 | 标准 |
|:-------|:-----|
| term_definition | ≥50 字，完整定义 |
| application_scenarios | ≥2 个场景，每场景 ≥50 字 |
| engineering_practices | ≥1 个具体实践描述 |
| related_concepts_relations | ≥2 个关联概念 |
| common_misconceptions | ≥1 个常见误区 |

#### 3. 层次深度 (depth)

| 检查项 | 标准 |
|:-------|:-----|
| 内容递进 | 是否按"是什么→为什么→怎么用"组织 |
| learning_objectives | 是否按 Bloom 分层（知道→理解→应用） |
| core_concept_map | 概念图是否展示内部结构（≥3 节点） |
| core_concept_map_analysis | 是否对概念图有文字解析 |
| 推导过程 | 关键结论是否有推导依据 |

#### 4. 教学有效性 (teaching)

| 检查项 | 标准 |
|:-------|:-----|
| learning_objectives | 目标可衡量，不是空话 |
| prerequisite_knowledge | 明确列出前置知识 |
| self_check_questions | ≥2 道自检题，有参考价值 |
| solved_problem | 明确指出此概念解决什么问题 |

### Step 4: 修正循环

如果审查结果为 `NEED_REVISION`：

```
1. 定位到 details 中的具体字段
2. 重新精读源文对应段落
3. 修正 YAML 字段内容
4. 更新 review.status = "PASS"
5. 重跑: pipeline auto
```

如果全部 `PASS`：

```
YAML 就绪 → 脚本自动:
  yaml_pre_validate 格式校验
  → PASS → pipeline auto (build + 质量闸门)
  → PASS → pipeline review (A/B/C/D 分层)
```

## pipeline 集成

```
pipeline build-all --source-dir raw/ -w $KB --book-id XX

Phase 0-1.5: 全自动（文件转换+初始化+TOC）
  ↓
phase2_tasks.json 生成（含 TOC + 每个容器的 suggested_start/end）
  ↓
Agent 逐个任务:
  Step 1: 读 TOC → 判断读取范围 → read_file()
  Step 2: 精读 → 写完整 YAML（全部字段）
  Step 3: 质量审查 → 写入 review 字段
  Step 4: NEED_REVISION → 修正 → 再审
  Step 5: PASS → 下一容器
  ↓
pipeline batch --retry 3: 全自动（build + 闸门 + 索引）
  ↓
pipeline review: 内容深度分层（A/B/C/D）
  ↓
Agent 处理 D-tier → 修复 → 完成
```
