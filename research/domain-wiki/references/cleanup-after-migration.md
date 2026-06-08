# 版本迁移后清理清单 (v48.2)

> 每次大版本模板/架构迁移后，知识库目录会积累残留文件。此清单确保交付物干净。
> 
> **v48.2 更新**: YAML 数据统一存储在 `.dag/第N章/data/`，取消独立 `data/` 目录。
> `.dag/*/data/` 现在是**活跃数据目录**，不可删除。

## 已知残留类型

### 1. 独立 `data/` 目录 (v48.2 反向迁移残留)

v48.2 将 YAML 存储从独立 `data/` 目录移回 `.dag/第N章/data/`。
旧的 `data/` 目录不再被 pipeline 读取，应予删除。

**检测**:
```bash
find $BOOK_DIR -maxdepth 1 -type d -name "data"
```

**清理**:
```bash
# 先确认 YAML 已迁移到 .dag/第N章/data/ 下
find $BOOK_DIR/.dag -path "*/data/*.yaml" | wc -l
# 再删除独立的 data/
rm -rf $BOOK_DIR/data
```

### 2. 模板迁移备份目录

模板升级时 Agent 可能创建 `*_backup_v*` 目录。
确认新版本通过质量闸门后可安全删除。

**检测**:
```bash
find $BOOK_DIR -type d -name "*_backup_v*"
```

**清理**:
```bash
find $BOOK_DIR -type d -name "*_backup_v*" -exec rm -rf {} +
```

### 3. Agent 污染文件

Agent 在知识库目录下手动操作遗留的临时文件。

**已知签名**:
- `*convert*.py` — 批量转换脚本
- `audit*` — 审计脚本/笔记
- `batch_*` — 批处理脚本
- `*报告*.md`, `*report*.md` — 审计报告
- `_test_*.md` — 测试文件
- `references/` 在知识库根或书根 — 设计文档不属于知识库
- 知识库根的空 `10_总揽/`, `领域总控/` 目录 — Agent 用错 `-w` 参数
- `.pytest_cache/` — 在知识库目录下跑了 pytest

**清理**:
```bash
# 在 wiki_root 下
rm -f *.py audit* batch_* *_报告*.md *_report*.md _test_*.md
rm -rf .pytest_cache/ references/ 10_总揽/ 领域总控/
# 移除空的错位书目录
find . -maxdepth 1 -type d -name "0001_*" -empty -exec rm -rf {} +
```

### 4. `.dag/kb_graph.db` — 不要删

`wiki_root/.dag/kb_graph.db` 是 KGraph 的跨领域图数据库，**是设计位置不是垃圾**。
删除后下次 `pipeline insights` 会自动重建，但会丢失历史图状态。

## 完整清理脚本 (v48.2)

```bash
#!/bin/bash
# 在 wiki_root 执行
WIKI_ROOT="$(pwd)"
BOOK_DIR="$WIKI_ROOT/电磁兼容领域/0001_电磁兼容基础教材"

# 1. 独立 data/ 目录 (v48.2 已废弃)
echo "=== 清理废弃 data/ 目录 ==="
if [ -d "$BOOK_DIR/data" ]; then
  rm -rf "$BOOK_DIR/data"
  echo "✓ data/ 已删除"
else
  echo "  (不存在，跳过)"
fi

# 2. 备份目录
echo "=== 清理 backup dirs ==="
find "$BOOK_DIR" -type d -name "*_backup_v*" -exec rm -rf {} + 2>/dev/null
echo "完成"

# 3. Agent 污染
echo "=== 清理 Agent 临时文件 ==="
rm -f "$WIKI_ROOT"/*.py "$WIKI_ROOT"/audit* "$WIKI_ROOT"/batch_* \
      "$WIKI_ROOT"/*_报告*.md "$WIKI_ROOT"/*_report*.md "$WIKI_ROOT"/_test_*.md 2>/dev/null
rm -rf "$WIKI_ROOT"/.pytest_cache "$WIKI_ROOT"/references 2>/dev/null
find "$WIKI_ROOT" -maxdepth 1 -type d \( -name "10_总揽" -o -name "领域总控" -o -name "0001_*" \) -empty \
  -exec rm -rf {} + 2>/dev/null
echo "完成"

# 4. macOS 系统文件
find "$WIKI_ROOT" -name ".DS_Store" -delete 2>/dev/null

echo "=== 清理完成 ==="
```

## 清理后验证

```bash
# 根级应只有: raw/ 知识库总控/ {领域目录}/
ls -d "$WIKI_ROOT"/*/

# 书内应有 10 个目录 (.dag 是隐藏的，不在列表):
# 10_总揽 20_正文 30_核心概念 40_知识要素 50_知识点 60_技能点 70_应用场景 80_实体 90_习题
ls -d "$BOOK_DIR"/*/

# .dag/ 下应有每章的 data/ 子目录
find "$BOOK_DIR/.dag" -path "*/data" -type d | wc -l
```
