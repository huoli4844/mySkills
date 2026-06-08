# 质量审查体系审计模式（v27.0 审计产出）

对多层验证系统的系统性审计方法论。适用于 `pipeline validate`、CI/CD 质量闸门、或任何"生成→验证→阻断"管道。

## 审计维度（7 层检查的常见反模式）

| 反模式 | 检测信号 | 修复方向 |
|:-------|:---------|:---------|
| **异常静默为 pass** | `except Exception: return "pass"` | 改为 `return "fail"` 或 `return "skip"` |
| **先设 done 后验证** | 状态先写磁盘再检查 | 先设 `in_progress`，通过后提升 `done` |
| **重复检查不同入口** | 同一指标在两处独立计算 | 用跟踪变量（`_tracked` dict）传递结果 |
| **双重运行同一脚本** | `--quiet` 跑一次再完整版跑一次 | 一次运行，仅 FAIL 时获取详情 |
| **文档与代码阈值脱节** | spec 文档要求 4000 字，代码检查 1600 字 | 对齐到较低值（代码为准）或提高代码阈值 |
| **编号不一致** | 注释写 11 项，实际输出 12 项 | 以代码输出为准更新文档 |
| **basename-only 匹配** | 只比文件名不比路径 | 同时存储 basename 和完整相对路径 |
| **标记词/常量多处定义** | 3 个文件各自维护标记词列表 | 提取为模块级常量，统一引用 |
| **层级检查空壳** | `result = "pass"  # 简化` | 实现真正的扫描逻辑 |
| **占位符检测不一致** | 两套 PLACEHOLDER_PATTERN 不同 | 确保所有检测点引用同一常量 |

## 修复优先级分类

| 级别 | 含义 | 修复要求 |
|:-----|:-----|:---------|
| 🔴 P0 | 影响验证可靠性（异常静默、竞态条件、阻塞逻辑不统一） | 必须修复 |
| 🟡 P1 | 文档与代码脱节、重复逻辑 | 应当修复 |
| 🟠 P2 | 检查覆盖率不足、边缘情况 | 建议修复 |
| 🔵 P3 | 代码风格、消息措辞 | 可选修复 |

## 验证后必须确认

```bash
# 1. 编译所有修改的 .py 文件
python3 -m py_compile <file>.py

# 2. 运行单元测试
python3 -m pytest tests/ -v --tb=short

# 3. 确认编号/阈值一致性
grep -n '\[.*\/.*\]' dag_controller.py  # 检查编号
grep -n 'min_body_chars' comprehensive-content-check.py  # 检查阈值
```


---

## 10 维扫描法（原 engineering-audit.md）


# 工程化审计清单

## 10 维扫描法

每次工程化改造前，按此维度扫描技能代码库：

| # | 维度 | 扫描方法 |
|:-:|:-----|:---------|
| 1 | 死代码 | `find . -name "*.py" -exec grep -l "import.*engine\|import.*state_manager" {} +` + 检查未调用函数 |
| 2 | 硬编码路径 | `grep -rn "电磁兼容基础\|测试-全书\|~/Desktop" scripts/` |
| 3 | 版本漂移 | 对比模板 `template_version` vs 配置中 `v` 字段 |
| 4 | 测试夹具同步 | `grep -rn '\[\[01_资料库/' tests/fixtures/`（应为 `[[01_领域/01_资料库/`） |
| 5 | 大函数 | `grep -c '^def ' <file>` 配合 `wc -l`，>150 行需拆分 |
| 6 | 反模式 | `grep -rn 'class FA'` 匿名类 |
| 7 | 跨模块依赖 | 检查 `from X import Y` 是否存在循环 |
| 8 | 测试覆盖率 | `ls tests/` 对照核心模块列表 |
| 9 | 模板-检查同步 | 比较模板 `###` 计数 vs `SECTION_COUNTS` |
| 10 | 缓存清理 | `find . -type d \( -name __pycache__ -o -name .pytest_cache \)` |

## v25.4 已完成 14/17 项

完成清单见 SKILL.md 改变日志 v25.4。

## 剩余待办（低优先级）

- **P1-6** validate 去重：`comprehensive-content-check.py` 与 `pipeline_validate` 内容深度检查重叠
- **P2-11** 文档合并：29 个 reference 文档可适当合并
- **P2-15** 极少数过时 reference（如老版本号的 per-chapter-data-format）
