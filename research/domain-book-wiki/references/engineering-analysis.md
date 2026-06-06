# domain-book-wiki 工程化体系分析

> v50.1 — 对 48 个 .py (21,246 行) 的系统性工程审计

## 一、六层纵深防御

```
preflight → yaml_pre_validate → build staging → content_check → validate_render → quality_score
  (事前)       (Agent后秒级)        (原子写入)      (内容质量)      (渲染正确)       (评分)
```

| 层级 | 脚本 | 触发时机 | 阻断策略 |
|:-----|:-----|:---------|:---------|
| **L0 预检** | `preflight.py` | pipeline init | FAIL → 拒绝启动（`data/` 下有 YAML 直接阻断） |
| **L1 格式** | `yaml_pre_validate.py` | Agent 写完 YAML 后 | FAIL → 必须修 schema/bloom/定义句 |
| **L2 构建** | `build_kb_files.py` | 逐章 build | 逐文件 move + placeholder 消除 + HTML 剥离 |
| **L3 内容** | `content_check_rules.py` + `rules/` | build 后 | FAIL 深度不足/wikilink 断链/图缺失 |
| **L4 渲染** | `validate_render.py` | build 后 | Mermaid 语法 + LaTeX 括号 + 图引用可解析 |
| **L5 综合** | `quality_score.py` | 全书 build 后 | 0-100 评分 + L2/L3/L4 索引覆盖率 |

## 二、关键工程机制

### 2.1 Schema 统一（单一事实来源）

`dag_constants.py` 中 `REQUIRED_BD_FIELDS` 为唯一权威来源：
- `yaml_pre_validate.check_required_fields()` → 从此读取
- `build_kb_files._REQUIRED_BD_FIELDS` → 从此读取
- 效果：255 假阳性 → 0（v50.0）

同样 `DIR` 字典集中管理所有 L1/L2/L3/L4 目录名。

### 2.2 构建原子化

- **目录覆写修复**：`os.rename(dir, dir)` → 逐文件 `os.rename` + `shutil.rmtree`
- **{{placeholder}} 消除**：缺失字段统一填"无"
- **HTML 注释剥离**：`fill_template()` 返回前 `re.sub(r'<!--.*?-->', '', result)`
- **习题命名标准化**：build 时自动修正 + `check_file_naming` warning

构建流程：写入 `.build_tmp/` → 全部成功 → 逐文件 move → 清理临时目录。

### 2.3 可观测性

| 机制 | 产出 | 用途 |
|:------|:-----|:-----|
| `yaml_pre_validate` | FAIL/WARN 计数 + 详细消息 | Agent 写完即知错→立即修复 |
| `pipeline auto` | 进度条 + 每阶段 OK/FAIL | 一键看到哪步卡住 |
| `quality_score.json` | 0-100 分 + errors/warnings/wiki_broken | 每章质量量化对比 |
| `dag_state` | `.dag/{book_id}_ch{N}.json` | 任意时刻恢复 pipeline 状态 |
| `chapter_cache` | SHA256 + template_version | 源文未变→跳过重复 build |
| `check_kp_depth()` | 三指标 FAIL/WARN | 内容深度自动化评判 |

### 2.4 防御性路径管理

`WorkspacePaths`（102 行）是唯一路径推导入口：
- `_is_valid_book` 校验：传入 domain 目录时自动回退修正
- 禁止手拼 `os.path.join(wr, ...)`
- 集中化 11 个路径推导方法

### 2.5 错误处理

- **零裸 `except`**：26 处全部改为 `except Exception as e: log.warning/debug(...)`
- **`PipelineError`**：统一异常类型（含 phase + message）
- **preflight 前向兼容**：`import dag_constants` 失败时 `exec()` 提取模块头部常量

## 三、代码治理

| 动作 | 效果 |
|:------|:-----|
| `content_check_rules.py` → `rules/` 5 文件 | 1327→291 行入口 + 独立模块 |
| 删除 6 个 `build_*.py` 薄包装器 | 死代码清扫 |
| `template_assembler_core` 合并 | 116 行冗余消除 |
| `WorkspacePaths` 独立文件 | 关注点分离 |
| 48 `.py`，零 bare except | AST 验证通过 |

## 四、剩余不足

| 维度 | 评级 | 瓶颈 |
|:-----|:-----|:-----|
| 防御深度 | ⭐⭐⭐⭐ | 6 层闸门，层层可阻断 |
| 可观测性 | ⭐⭐⭐⭐ | 秒级校验 + 章节评分 |
| 故障隔离 | ⭐⭐⭐⭐ | 原子构建 + WorkspacePaths 校验 |
| 确定性 | ⭐⭐⭐ | Agent 写 YAML 是不可控变量 |
| 可维护性 | ⭐⭐⭐⭐ | 零怪物类 + 80+ 陷阱 |
| 数据完整性 | ⭐⭐⭐⭐ | _is_valid_book + 目录前缀修正 |

**改善方向**：
1. `yaml_auto_gen.py` 自动提取定义句/公式/图引用 → 缩小 Agent 变量
2. 核心构建链路集成测试 → 防回归
3. 构建仪表盘/渐进式日志 → 可观测性提升
