# 契约 · 数据库（db）

| 项 | 值 |
|---|---|
| 契约版本 | `db@1.4` |
| 所有者 | backend-engineer（`app/db/`） |
| 引擎 | SQLite + SQLAlchemy 2.x（原型阶段手工迁移，正式部署前引入 Alembic） |
| 关联 | [capture.md](./capture.md)、[api.md](./api.md)、[analysis.schema.json](./analysis.schema.json) |

> v1.4 已冻结，后续仅接受实现驱动的变更。

---

## 1. 通用约定

| 约定 | 值 |
|---|---|
| 主键 | 业务表用 UUID v4 字符串（`TEXT`，36 字符）；`audit_logs` 用自增整数 |
| 时间 | `TEXT`，ISO 8601 带时区（`2026-11-23T10:12:03+08:00`），UTC 存储可选但同一库内必须统一 |
| 布尔 | `INTEGER`，`0/1` |
| JSON | `TEXT` + `CHECK (json_valid(col))`；可空 JSON 列（表达「缺失」）用 `CHECK (col IS NULL OR json_valid(col))` |
| 枚举 | `TEXT` + `CHECK (col IN (...))`，不用 SQLite 原生枚举 |
| 删除 | 不做物理删除业务数据；对象停用改 `status` |
| 路径 | 只存相对路径，以 `STORAGE_ROOT` 为根 |
| 命名 | 表名复数、字段 `snake_case` |

## 2. `subjects`（矫正对象）

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `id` | TEXT | PK | UUID v4 |
| `code` | TEXT | NOT NULL, UNIQUE | 矫正编号，如 `S001` |
| `name` | TEXT | NOT NULL | 姓名 |
| `gender` | TEXT | NULL, DEFAULT `'unknown'`, CHECK in (`male`,`female`,`unknown`) | |
| `birth_year` | INTEGER | NULL | 仅年份，不存完整生日 |
| `status` | TEXT | NOT NULL, DEFAULT `'active'`, CHECK in (`active`,`suspended`,`closed`) | |
| `consent_json` | TEXT | NULL, JSON | 同意状态，结构见 2.1 |
| `baseline_json` | TEXT | NULL, JSON | 个人基线，结构见 2.2 |
| `created_at` | TEXT | NOT NULL | |
| `updated_at` | TEXT | NOT NULL | |

### 2.1 `consent_json` 结构

```json
{
  "schema_version": "consent@1.0",
  "general": { "granted": true, "at": "2026-11-20T09:00:00+08:00" },
  "face":    { "granted": true, "at": "2026-11-20T09:00:00+08:00" },
  "audio":   { "granted": true, "at": "2026-11-20T09:00:00+08:00" },
  "revoked_at": null,
  "retention_days": 180
}
```

- 人脸与音频是**独立同意项**；
- `audio.granted=false` 或 `face.granted=false` 时，`POST /api/session` 返回 `1005 状态冲突`；
- 撤回后 `revoked_at` 有值，拒绝发起新采集。

### 2.2 `baseline_json` 结构

```json
{
  "schema_version": "baseline@1.0",
  "sample_count": 5,
  "emotion_valence_mean": -0.05,
  "emotion_valence_std": 0.18,
  "psych_signal_mean": 28.4,
  "psych_signal_std": 7.9,
  "updated_at": "2026-11-22T20:00:00+08:00"
}
```

- `sample_count` 为参与基线计算的会话数；
- `sample_count < BASELINE_MIN_SAMPLES`（默认 3）时，趋势规则走"基线不足"分支（见 [../grading.md](../grading.md)）。

## 3. `sessions`（单次采集会话）

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `id` | TEXT | PK | UUID v4 |
| `subject_id` | TEXT | NOT NULL, FK → `subjects.id` | |
| `status` | TEXT | NOT NULL, CHECK in (`created`,`captured`,`failed`) | 只反映采集结果，不随分析变化；见 3.1 |
| `capture_status` | TEXT | CHECK in (`ok`,`partial`,`no_face`,`no_audio`,`no_face_no_audio`,`error`) | 与 [capture.md](./capture.md) 枚举一致 |
| `face_path` | TEXT | NULL | 相对路径 |
| `audio_path` | TEXT | NULL | 相对路径 |
| `transcript_path` | TEXT | NULL | 由 `analysis/asr` 写入 |
| `duration_sec` | REAL | NULL | 录音实际时长 |
| `captured_at` | TEXT | NULL | 采集完成时间 |
| `analysis_status` | TEXT | NOT NULL, DEFAULT `'pending'`, CHECK in (`pending`,`done`,`degraded`,`failed`) | 分析失败只改此字段，不回写 `status` |
| `analysis_json` | TEXT | NULL, JSON | 通过 schema 校验的完整 `AnalysisResult` |
| `codes` | TEXT | NOT NULL, DEFAULT `'[]'`, JSON | 结构化 code 数组：`error.code` 在前，其余来自 `warnings[].code`；无异常时为空数组；不含堆栈 |
| `created_at` | TEXT | NOT NULL | |
| `updated_at` | TEXT | NOT NULL | |

> `coverage` 为派生值（由 `face_path` / `audio_path` 推导），不落列；读取时由 `CaptureSession.coverage` 属性计算。

### 3.1 `status` 状态机（仅采集）

```
created ──capture 有可用产物──> captured
   │
   └──capture 无可用产物──────> failed
```

| 迁移 | 触发 | 允许条件 |
|---|---|---|
| `created → captured` | `capture_status in (ok, partial, no_face, no_audio)` | `face_path` 或 `audio_path` 任一存在 |
| `created → failed` | `capture_status in (no_face_no_audio, error)` | 无任何可用产物 |

`sessions.status` **只反映采集结果**，分析过程不再改变该字段。

`analysis_status` 状态机：

```
pending ──分析成功且无降级──> done
   ├────任一路降级但结果可用──> degraded
   └────分析彻底失败────────> failed
```

| 迁移 | 触发 |
|---|---|
| `pending → done` | 分析通过 schema 校验且无降级 |
| `pending → degraded` | 任一路降级，结果仍可用 |
| `pending → failed` | 分析彻底失败、结果不可用；**不回写** `sessions.status` |

`capture_status` → `sessions.status` 映射：

| `capture_status` | `sessions.status` | 是否进分析 |
|---|---|---|
| `ok` | `captured` | 是 |
| `partial` | `captured` | 是（`analysis_status` 可能为 `degraded`） |
| `no_face` | `captured` | 是（仅音频路） |
| `no_audio` | `captured` | 是（仅表情路） |
| `no_face_no_audio` | `failed` | 否 |
| `error` | `failed` | 否 |

> 判定规则：只要 `face_path` 或 `audio_path` 任一存在即可进入 `captured`，因此 `partial` / `no_face` / `no_audio` 均可被分析；失败会话保留 `meta.json` 便于排查，不进分析、不计入复盘、不生成工单（详见 [capture.md](./capture.md) 3.2）。分析失败只把 `analysis_status` 置 `failed`，`sessions.status` 保持 `captured`。

### 3.2 `analysis_json` 存放约定

- 存**完整** `AnalysisResult` 对象，字段与 [analysis.schema.json](./analysis.schema.json) 一一对应；
- 不额外包裹、不裁剪字段；
- 接口返回时按角色脱敏（见 [api.md](./api.md#6-序列化脱敏规则)），脱敏发生在序列化层，不改库内容。

## 4. `reviews`（周期复盘）

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `id` | TEXT | PK | UUID v4 |
| `subject_id` | TEXT | NOT NULL, FK → `subjects.id` | |
| `source_session_id` | TEXT | NULL, FK → `sessions.id` | 触发本次复盘的单次会话 |
| `window_start` | TEXT | NOT NULL | 窗口起始（含） |
| `window_end` | TEXT | NOT NULL | 窗口结束（含） |
| `window_days` | INTEGER | NOT NULL, DEFAULT 7 | 窗口天数 |
| `single_session_risk` | TEXT | NOT NULL, CHECK in (`red`,`orange`,`none`) | 单次规则结果 |
| `trend_color` | TEXT | NOT NULL, CHECK in (`green`,`blue`,`yellow`) | 趋势规则结果 |
| `final_color` | TEXT | NOT NULL, CHECK in (`green`,`blue`,`yellow`,`orange`,`red`) | 合成结果 |
| `consistency` | TEXT | NOT NULL, CHECK in (`high`,`medium`,`low`) | 来自 `AnalysisResult` |
| `manual_review` | INTEGER | NOT NULL, CHECK in (0,1) | 是否强制人工复核 |
| `rules_fired` | TEXT | NOT NULL, JSON | 命中的规则编号数组 |
| `evidence_json` | TEXT | NOT NULL, JSON | 证据链数组 |
| `grading_version` | TEXT | NOT NULL | 如 `grading@1.2` |
| `created_at` | TEXT | NOT NULL | |

约束：

- `trend_color` 的枚举不含 `orange` / `red`：趋势规则本身只产出绿/蓝/黄，橙与红只来自单次规则或合成封顶；
- `single_session_risk=none` 表示单次规则未命中；
- `final_color != green` 必须存在对应 `review_tickets` 记录（由 `api` 层在同一事务保证）；
- 同一对象的同一 `window_end` 只允许一条复盘记录（`UNIQUE(subject_id, window_end)`），防止同一窗口重复生成；
- `window_start` / `window_end` 为 `YYYY-MM-DD` 自然日（含端点），与 grading 证据的 `window` 数组一致；
- 窗口内 0 条**可用分析会话**（`sessions.status = captured` 且 `analysis_status in (done, degraded)`）时不落 `reviews`，复盘接口返回 `1005 no_session_in_window`；
- 有可用会话但无 `psych.status = ok` 样本时（如 `no_audio`）仍可落 `reviews`，趋势走 `R_BASELINE_INSUFFICIENT` 判蓝（见 [../grading.md §4.3](../grading.md)）。

## 5. `review_tickets`（复核工单）

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `id` | TEXT | PK | UUID v4 |
| `review_id` | TEXT | NOT NULL, FK → `reviews.id` | |
| `subject_id` | TEXT | NOT NULL, FK → `subjects.id` | |
| `status` | TEXT | NOT NULL, CHECK in (`pending`,`confirmed`,`corrected`,`closed`) | 见 5.1 |
| `priority` | TEXT | NOT NULL, CHECK in (`P0`,`P1`,`P2`) | 见 [../grading.md](../grading.md#6-复核触发条件) |
| `due_at` | TEXT | NULL | 建议处理截止时间 |
| `triggered_rules` | TEXT | NOT NULL, JSON | 规则编号数组，如 `["R_SINGLE_ORANGE"]` |
| `evidence_json` | TEXT | NOT NULL, JSON | 与 `reviews.evidence_json` 同结构 |
| `suggested_method` | TEXT | NOT NULL | 建议复核方式，取值见 5.2 |
| `assignee` | TEXT | NULL | 处理人工号 |
| `conclusion_color` | TEXT | NULL, CHECK in (`green`,`blue`,`yellow`,`orange`,`red`) | 人工结论色 |
| `conclusion_note` | TEXT | NULL | 人工说明 |
| `opened_at` | TEXT | NOT NULL | |
| `closed_at` | TEXT | NULL | |

> `id` 为工单主键（UUID v4，由 API 层生成）；`review_id` 指向 `reviews.id`。`grading.build_ticket` 的输出只提供后者，不含 `id`。

### 5.1 工单状态机

```
pending ──confirm──> confirmed ──(自动)──> closed
   │                    │
   ├──correct──────────> corrected ──(自动)──> closed
   └──close──────────────────────────────────> closed
```

| 动作 | 语义 | 必填 | 结果状态 |
|---|---|---|---|
| `confirm` | 认可系统结论 | `note` 可选 | `confirmed` → `closed` |
| `correct` | 修正结论 | `conclusion_color` + `note` | `corrected` → `closed` |
| `close` | 无需处理 / 重复 / 信息不足 | `note` | `closed` |

- 终态 `closed` 记录 `closed_at`；
- 已 `closed` 的工单不允许再次流转，返回 `1005 状态冲突`；
- 每次流转写一条 `audit_logs`（`action=ticket.transition`）。

### 5.2 `suggested_method` 取值

| 值 | 场景 |
|---|---|
| `routine_checkin` | 蓝：日常问询即可 |
| `focused_interview` | 黄：安排一次针对性面谈 |
| `priority_interview` | 橙：优先安排面谈，必要时联系家属 |
| `urgent_escalation` | 红：当日内启动危机处置流程（系统只提示，不执行） |
| `recapture` | 采集质量问题导致的复核 |

## 6. `audit_logs`（访问与操作留痕）

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `id` | INTEGER | PK AUTOINCREMENT | |
| `actor_type` | TEXT | NOT NULL, CHECK in (`subject`,`staff`,`system`) | |
| `actor_id` | TEXT | NULL | 对象 id 或工号 |
| `action` | TEXT | NOT NULL | 见 6.1 |
| `target_type` | TEXT | NULL | `subject` / `session` / `review` / `ticket` |
| `target_id` | TEXT | NULL | |
| `detail_json` | TEXT | NULL, JSON | 不含音频、转写原文、面部图内容 |
| `request_id` | TEXT | NULL | 请求追踪 id |
| `created_at` | TEXT | NOT NULL | |

### 6.1 `action` 取值

| action | 触发点 |
|---|---|
| `consent.grant` | 同意提交 |
| `consent.revoke` | 撤回 |
| `sensitive.view` | 查看面部图 / 转写原文 |
| `session.analyze` | 触发分析 |
| `ticket.transition` | 工单流转 |
| `subject.update` | 对象信息修改 |
| `review.create` | 复盘创建 |

`detail_json` 示例（`sensitive.view`）：

```json
{ "field": "transcript", "session_id": "8f3c1b2e-4a5d-4c6e-9f10-1a2b3c4d5e6f" }
```

## 7. 索引

| 表 | 索引 | 用途 |
|---|---|---|
| `subjects` | `UNIQUE(code)` | 编号查询 |
| `subjects` | `(status)` | 列表筛选 |
| `sessions` | `(subject_id, captured_at DESC)` | 对象会话时间线 |
| `sessions` | `(status)` | 失败会话巡检 |
| `reviews` | `(subject_id, created_at DESC)` | 对象复盘历史 |
| `reviews` | `(final_color)` | 看板色码分布 |
| `reviews` | `UNIQUE(subject_id, window_end)` | 同一窗口防重复生成 |
| `review_tickets` | `(status, priority, opened_at DESC)` | 复核队列排序 |
| `review_tickets` | `(subject_id)` | 对象工单 |
| `review_tickets` | `UNIQUE(review_id)` | 一次复盘只开一张单，保证幂等 |
| `audit_logs` | `(target_type, target_id, created_at DESC)` | 溯源 |
| `audit_logs` | `(actor_id, created_at DESC)` | 人员操作审计 |

## 8. `sessions` 样例行

```json
{
  "id": "8f3c1b2e-4a5d-4c6e-9f10-1a2b3c4d5e6f",
  "subject_id": "3b1e7c90-2f4a-4d51-8c6b-7d9e0f1a2b3c",
  "status": "captured",
  "capture_status": "ok",
  "face_path": "subjects/3b1e7c90-2f4a-4d51-8c6b-7d9e0f1a2b3c/sessions/8f3c1b2e-4a5d-4c6e-9f10-1a2b3c4d5e6f/face.jpg",
  "audio_path": "subjects/3b1e7c90-2f4a-4d51-8c6b-7d9e0f1a2b3c/sessions/8f3c1b2e-4a5d-4c6e-9f10-1a2b3c4d5e6f/audio.wav",
  "transcript_path": "subjects/3b1e7c90-2f4a-4d51-8c6b-7d9e0f1a2b3c/sessions/8f3c1b2e-4a5d-4c6e-9f10-1a2b3c4d5e6f/transcript.txt",
  "duration_sec": 30.0,
  "captured_at": "2026-11-23T10:12:36+08:00",
  "analysis_status": "degraded",
  "analysis_json": "{\"schema_version\":\"1.0\", ... }",
  "codes": [],
  "created_at": "2026-11-23T10:12:03+08:00",
  "updated_at": "2026-11-23T10:12:38+08:00"
}
```

## 9. 迁移约定

> 原型阶段手工迁移（`python -m app.db.init` 建表 + 手工迁移脚本），正式部署前引入 Alembic。

1. 迁移文件放在 `app/db/migrations/`，命名 `YYYYMMDDHHMM_<slug>.py`（引入 Alembic 后作为 revision 文件）；
2. **只新增迁移，不改历史迁移**；
3. 破坏性变更（删列、改类型）必须同时提供：新列 + 回填脚本 + 兼容期说明；
4. 每个迁移必须可在空库上从头执行成功（引入 Alembic 后即 `upgrade head`）；
5. SQLite 不支持 `ALTER COLUMN`，改列用"建新表 → 拷数据 → 换名"；
6. 枚举新增值属于兼容变更，但必须同步更新本契约文档。

## 10. 数据清理

| 规则 | 值 |
|---|---|
| 留存期 | `RETENTION_DAYS`，默认 180 |
| 清理对象 | `sessions` 及其文件目录、`analysis_json` 中的转写引用 |
| 不清理 | `reviews`、`review_tickets`、`audit_logs`（保留审计价值，但脱敏） |
| 触发 | 手动脚本 `python -m app.db.cleanup`（原型不做定时任务） |

## 11. 禁止项

- 禁止在 `sessions` 中出现任何原始帧相关字段（如 `raw_frame_path`、`full_image`）；
- 禁止在库中存音频 / 图片二进制；
- 禁止在 `audit_logs.detail_json` 中写入转写原文或心理评分明细；
- 禁止物理删除 `audit_logs`。
