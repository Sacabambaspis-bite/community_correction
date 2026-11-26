# 数据库迁移约定

本轮仍只提供 `Base.metadata.create_all()` 建库（`python -m app.db.init`），
未引入 Alembic 运行时；存量库的 schema 变化以本目录下的手工迁移脚本补齐。

现有迁移：

| 文件 | 作用 |
|---|---|
| `202611241200_add_dual_module_tasks.py` | 补签到/汇报双模块字段、逾期工单支撑列与索引 |
| `202611261200_drop_sensevoice_syncs.py` | 删除已下线的 `sensevoice_syncs` 表（可重复执行） |

后续 schema 变化按以下规则补充迁移文件。

## 规则

1. **只增不改**：已有迁移文件视为不可变历史，修正只能新增迁移。
2. **命名**：`YYYYMMDDHHMM_<slug>.py`，例如 `202612011030_add_sessions_review_flag.py`。
3. **空库可建**：每个迁移必须能在空库上从头 `upgrade head` 成功。
4. **SQLite 改列**：SQLite 不支持 `ALTER COLUMN`，一律用「建新表 → 拷贝数据 → 换名」，
   并保留原索引与 CHECK 约束。
5. **枚举扩容**：属于兼容变更，但必须在同一提交内同步更新
   `docs/contracts/db.md`（由契约负责人执行），代码侧枚举与 CHECK 取值保持一致。
6. **破坏性变更**：删列 / 改类型必须同时提供新列、回填脚本与兼容期说明，
   且不得修改历史迁移。

> 临时锁定 SQLAlchemy `<2.1`：2.1.x 在开启外键时多表同事务 flush 顺序错误
>（见 `docs/reports/qa-2026-11-24.md` M1），待上游修复后解除。
