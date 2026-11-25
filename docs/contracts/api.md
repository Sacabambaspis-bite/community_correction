# 契约 · HTTP API（api）

| 项 | 值 |
|---|---|
| 契约版本 | `api@1.5` |
| 所有者 | backend-engineer（`app/api/`） |
| 基础路径 | `/api` |
| 关联 | [db.md](./db.md)、[capture.md](./capture.md)、[analysis.schema.json](./analysis.schema.json)、[ui.md](./ui.md) |

> v1.5 已冻结，后续仅接受实现驱动的变更。本版落地 `/api/user/*`、subject 会话归属校验与 consent 前置三闸；信封沿用 v1.4 的 `{code, message, data, degraded, request_id}`（业务码 HTTP 200、未捕获异常 HTTP 500），路由统一为 `/api/sessions` + `/api/admin/*` + `/api/user/*`。

> **v1.5 实现补记（2026-11-24，附加、非破坏）**：`POST /api/sessions/{id}/analyze` 正式接入分析与分级；新增 `POST /api/admin/reviews`、`GET /api/admin/reviews/{review_id}`、`GET /api/admin/tickets`、`GET /api/admin/tickets/{ticket_id}`、`POST /api/admin/tickets/{ticket_id}/transition`、`GET /api/admin/dashboard` 的字段契约；明确复盘窗口为 `YYYY-MM-DD` 自然日、0 会话窗口返回 `1005 no_session_in_window`、consent 强校验口径。契约版本号不变。

> **v1.5 实现补记·二（2026-11-24，附加、非破坏）**：双模块（签到/汇报）接入——
> 1. `POST /api/sessions` 入参新增 `kind`（`checkin`/`report`，缺省 `report`）；`checkin` 走 face_only 采集（capture@1.2 补记），`report` 行为不变；响应 `data` 与 `GET /api/sessions/{id}` 返回中增加 `kind`。
> 2. `POST /api/sessions/{id}/analyze`：`kind=checkin` 时不得因缺音频/单模态覆写 `capture_degraded`（grading@1.2 补记·三），`no_face`/`error` 仍按既有异常处理；`kind=report` 规则不变。
> 3. 新增 `GET /api/user/tasks`（用户端，subject 归属校验）：返回 `checkin` / `report` 两类任务的 `interval_days`、`last_completed_at`（最近 `captured` 会话的 `captured_at`，无则 null）、`overdue`（bool）。仅行为提示用途，不含色码/分值。
> 4. 新增 `PATCH /api/admin/subjects/{id}/frequency`（管理端）：body `{checkin_interval_days?, report_interval_days?}`，整数 ≥1，至少一项；写 `audit_logs(action=frequency.update)`。
> 5. **逾期扫描（惰性、幂等）**：`GET /api/admin/subjects`、`GET /api/admin/subjects/{id}`、`GET /api/admin/dashboard` 调用时对相关对象执行逾期判定（`now - last_completed_at > interval_days`，从未完成过对应类型采集且距 `created_at` 超过频率同样视为逾期）；逾期则生成 P0 复核任务（`suggested_method=talk_to_staff`，`detail_json` 含 `overdue_kind`、`overdue_days`），同对象同类型存在未关闭逾期复核任务时不重复生成；响应中对象摘要增加 `overdue: {checkin, report}` 布尔标记。逾期判定不修改 `sessions.status`、不触发分析。
> 6. **序列化补齐（前端联调驱动）**：对象列表/详情返回 `checkin_interval_days`、`report_interval_days`；管理端会话列表项返回 `kind`；复核任务列表/详情返回 `detail_json`（无附加内容时为 null）。

> **v1.5 实现补记·三（2026-11-24，附加、非破坏）**：思想汇报录音改为**用户手动控制**——
> 1. `POST /api/sessions`（`kind=report`）省略 `duration_sec`（或传 null）即进入手动录音模式（capture@1.2 补记·二）；显式传值的定时模式保留兼容。
> 2. 新增 `POST /api/sessions/{id}/stop`（用户端 + subject 归属校验）：仅手动模式且 `status=created` 时有效，置位停止事件，返回 `code=0`、`data={session_id}`；重复调用幂等返回成功；会话已 `captured`/`failed`、非手动模式或 `kind=checkin` 时返回 `1005` 状态冲突；不存在 `1004`、越权 `1003`。
> 3. 手动模式下录音仅因用户调用 stop 而结束，服务端不设计时自动终止；录音保存、状态回写（`created → captured/failed`）、轮询与 analyze 流程不变。

> **v1.5 实现补记·四（2026-11-25，附加、非破坏）**：新增思想汇报同步脚手架——
> 1. 新表 `sensevoice_syncs`（db@1.5 §7）。
> 2. 新增 `POST /api/admin/subjects/{subject_id}/sensevoice-sync`（触发转写 + 情绪同步，单事务，失败回滚）、`GET /api/admin/subjects/{subject_id}/sensevoice-syncs`（记录列表）、`GET /api/admin/sensevoice-syncs/{sync_id}`（详情，读取转写须留痕）。
> 3. 同步能力由环境变量 `SENSEVOICE_SYNC_ENABLED` 控制，**默认关闭**；关闭时接口返回 `5001 sensevoice_sync_disabled`，不落库、不写审计。
> 4. 新增业务码 `2004`（同步失败：`transcription_failed` / `emotion_failed`）、`5001`（外部 AI 能力不可用）。
> 5. 真实情绪分析接口协议未确认前，只落地表、接口与前端面板；禁止用 Mock 结果冒充真实同步。

> **v1.5 实现补记·五（2026-11-25，附加、非破坏）**：新增对象心理状态趋势端点 `GET /api/admin/subjects/{subject_id}/trends`（§7.18）——
> 1. 支持任意日期区间（`start_date` / `end_date`，闭区间，缺省近 14 天，跨度上限 366 天）；区间内无数据的自然日仍逐日返回，保证前端热力图与日历时序完整。
> 2. 只读聚合，聚合来源为 `sessions.analysis_json` + `reviews` + `subjects` 频率字段；**不新增表、不新增列、不做迁移**。
> 3. 返回日粒度五色（`review.color`）、分析侧最高风险档（`analysis_risk_level`）、文本效价/信号均值与标准差、一致性告警计数（degraded / low / conflict）、行为依从性（签到与汇报的 expected / completed / overdue）。
> 4. 心理学语义只返回机器码 `summary.signals[]`，**不返回中文结论文案**；文案由前端统一映射，以满足 ui@1.2 §6 禁用词规则。
> 5. 不返回转写原文、音频路径、影像或 `face_path`；不做跨对象聚合或排名；不产生任何处置动作；`degraded` 固定为 `[]`。
> 6. 保留既有 `GET /api/admin/dashboard` 与 `trend_7d` 不变，供旧页面兼容；新页面改用本端点。

> **术语同步（2026-11-25，编辑器、无版本变更）**：中文表述统一为「复核任务」；`review_tickets`、`/api/admin/tickets`、`ticket_id`、`ticket_closed` 等标识与状态枚举保持不变。

---## 1. 通用约定

| 项 | 约定 |
|---|---|
| 编码 | UTF-8，`application/json` |
| 字段命名 | `snake_case`，与数据库一致 |
| 时间 | ISO 8601 带时区 |
| 复盘窗口 | `reviews.window_start` / `window_end` 使用 `YYYY-MM-DD` 自然日（含端点），与 grading 证据 `window` 数组一致 |
| 分页 | query 参数 `page`（从 1 开始）、`page_size`（默认 20，最大 100） |
| 幂等 | `POST /api/sessions/{id}/analyze` 重复调用返回首次结果 |
| 路径参数 | `{session_id}`、`{subject_id}`、`{ticket_id}`、`{review_id}` 均为 UUID 字符串 |

## 2. 统一响应包

所有 JSON 接口（含错误）返回同一结构：

```json
{
  "code": 0,
  "message": "ok",
  "data": {},
  "degraded": [],
  "request_id": "6f1c2d3e-4a5b-4c7d-8e9f-0a1b2c3d4e5f"
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `code` | int | `0` 成功，非 0 见第 3 节 |
| `message` | string | 机器可读短句，不包含个人信息 |
| `data` | object \| array \| null | 业务数据；错误时为 `null`（会话查询失败态例外，见 7.3） |
| `degraded` | string[] | 降级标记，见 2.1 |
| `request_id` | string | 中间件为每个请求生成的 uuid4；同时写入响应头 `X-Request-Id`、服务日志与 `audit_logs.request_id` |

- 每个请求由中间件生成新的 uuid4，响应头 `X-Request-Id` 与信封 `request_id` 必须同值；
- `request_id` 只用于日志关联，不包含任何个人信息。

**HTTP 语义**：所有可预期的业务错误（`1001` / `1002` / `1003` / `1004` / `1005` / `1006` / `2001` / `2003` / `2004` / `4000` / `5001`，以及业务占位用的 `5000`，如 `capture_busy`、`analysis_pipeline_not_ready`）一律返回 HTTP 200；只有**未捕获异常**返回 HTTP 500 + `code=5000`。

**唯一例外**：`GET /api/admin/sessions/{session_id}/face` 成功时直接返回 `image/jpeg` 二进制（不走信封）；鉴权失败、留痕失败、文件缺失等错误情况仍返回上述 JSON 信封。

### 2.1 `degraded` 取值

| 值 | 含义 |
|---|---|
| `[]` | 未降级 |
| `["capture"]` | 采集降级（`capture_status in (partial, no_face, no_audio)`） |
| `["analysis"]` | 分析降级（`analysis_status=degraded`，结果可用） |
| `["capture","analysis"]` | 两者同时降级 |

- 数组元素去重，固定顺序 `capture` → `analysis`；
- 与具体会话无关的接口（health、列表等）固定返回 `[]`；
- `analysis_status=failed` 不属于降级：返回 `2003`。

## 3. 错误码

| code | 含义 | 典型场景 |
|---|---|---|
| 0 | 成功 | — |
| 1001 | 参数错误 | 缺字段、类型不符、枚举越界 |
| 1002 | 未认证 | 缺 token 或 token 无效 |
| 1003 | 无权限 | 用户端 token 访问管理端接口 |
| 1004 | 资源不存在 | session / subject / review / ticket / 面部图文件不存在 |
| 1005 | 状态冲突 | 未同意就采集（`consent_revoked` / `consent_required` / `consent_incomplete`）、复核任务已关闭（`ticket_closed`）、复盘窗口无可用会话（`no_session_in_window`） |
| 1006 | 频率限制 | 同一对象 60 秒内重复建会话 |
| 2001 | 采集失败（无可用产物） | `sessions.status == failed`；`failed` 会话调用分析 |
| 2003 | 分析失败（结果不可用） | `analysis_status=failed`，需重采或人工处理 |
| 2004 | 思想汇报同步失败（结果不可用） | `transcription_failed` / `emotion_failed`；本次同步已回滚，可重试或人工处理 |
| 4000 | 会话未采集完成 | `sessions.status == created` 时调用分析 |
| 5000 | 内部错误 / 临时占位 | 未捕获异常；分析管线未就绪（`message=analysis_pipeline_not_ready`）；采集并发冲突（`message=capture_busy`，专用错误码待增补） |
| 5001 | 外部 AI 能力不可用 | 同步开关未启用（`sensevoice_sync_disabled`）；SenseVoice 未配置或服务不可达（`sensevoice_unavailable`） |

> 业务错误均返回 HTTP 200，业务结果以 `code` 为准；未捕获异常返回 HTTP 500 + `code=5000`。
> `2001` / `2003` 不视为 HTTP 错误，前端依据 `code` 决定展示哪种提示。
> `partial` / `no_face` / `no_audio` 返回 `code=0` 且 `degraded` 含 `"capture"`；只有 `sessions.status == failed` 才返回 `2001`。

## 4. 鉴权

```
Authorization: Bearer <token>
```

| 角色 | token 来源 | 缺省值（仅本地开发） | 说明 |
|---|---|---|---|
| `subject` | `USER_TOKEN` | `user_demo` | 用户端，仅能访问 `/api/user/*` 与本人会话 |
| `staff` | `ADMIN_TOKEN` | `admin_demo` | 管理端，可访问 `/api/admin/*` 与共享会话接口 |

规则：

- `/api/admin/*` 一律要求 `staff`；
- `POST /api/sessions/{id}/analyze` 要求 `staff`；
- `POST /api/sessions`、`GET /api/sessions/{id}` 接受 `subject` 或 `staff`；
- `GET /api/health` 无需鉴权；
- 令牌为静态值直接比较，不要求前缀；缺失或格式错误返回 `1002`，角色不符返回 `1003`；
- 非生产环境未设置环境变量时使用缺省 demo 值并在启动日志打 `WARNING`；
- `APP_ENV=production` 时，`USER_TOKEN` / `ADMIN_TOKEN` 未配置或仍等于 `user_demo` / `admin_demo`，启动直接抛 `RuntimeError`，不提供默认值；
- 原型阶段 `subject` 身份由客户端显式声明 `subject_id`（`PUT` / `POST revoke` 在 body，`GET` 在 query `?subject_id=`），后端据此做会话归属校验；`staff` 无需声明、跳过归属校验。

## 5. 端点清单

标注「未实现」的端点仅为规划，本轮不落地。所有 `/api/admin/*` 需 `staff`。

### 5.1 公共

| 方法 | 路径 | 状态 | 说明 |
|---|---|---|---|
| `GET` | `/api/health` | 已实现 | 健康检查，免鉴权 |

### 5.2 会话（`subject` 或 `staff`）

| 方法 | 路径 | 状态 | 说明 |
|---|---|---|---|
| `POST` | `/api/sessions` | 已实现 | 异步发起一次采集，立即返回 `created` |
| `GET` | `/api/sessions/{session_id}` | 已实现 | 查询会话（前端轮询用） |
| `POST` | `/api/sessions/{session_id}/analyze` | 已实现 | 触发四路分析与五色分级，落 `reviews` / `review_tickets`（仅 `staff`；见 §7.4） |

### 5.3 用户端（`/api/user/*`，需 `subject`）

| 方法 | 路径 | 状态 | 说明 |
|---|---|---|---|
| `GET` | `/api/user/consent` | 已实现 | 查询本人同意状态 |
| `PUT` | `/api/user/consent` | 已实现 | 提交同意（请求体 `face` / `audio` 两个布尔；用户端已合并为单次勾选，见 ui.md 补记 7） |
| `POST` | `/api/user/consent/revoke` | 已实现 | 撤回同意 |
| `GET` | `/api/user/sessions/{session_id}/feedback` | 已实现 | 中性结果反馈（不含色码） |
| `GET` | `/api/user/ai-assist/status` | 已实现 | AI 援助可用状态（不暴露 Key；见 §7.19） |
| `POST` | `/api/user/ai-assist/chat` | 已实现 | AI 援助流式对话（SSE；无状态、不落业务表；见 §7.20） |

### 5.4 管理端（`/api/admin/*`，需 `staff`）

| 方法 | 路径 | 状态 | 说明 |
|---|---|---|---|
| `GET` | `/api/admin/subjects` | 已实现 | 对象列表（分页、关键词、状态） |
| `POST` | `/api/admin/subjects` | 未实现 | 新建对象 |
| `GET` | `/api/admin/subjects/{subject_id}` | 已实现 | 对象详情（含 `overdue` 与频率字段，惰性逾期扫描） |
| `PATCH` | `/api/admin/subjects/{subject_id}` | 未实现 | 更新对象基础信息 |
| `GET` | `/api/admin/sessions` | 已实现 | 会话列表（`subject_id`、`status` 过滤） |
| `GET` | `/api/admin/sessions/{session_id}/face` | 已实现 | 查看面部图（敏感，留痕） |
| `GET` | `/api/admin/sessions/{session_id}/transcript` | 未实现 | 查看转写原文（敏感，留痕） |
| `POST` | `/api/admin/reviews` | 已实现 | 按窗口计算复盘；0 可用会话返回 `1005 no_session_in_window`（见 §7.14） |
| `GET` | `/api/admin/reviews` | 未实现 | 复盘列表 |
| `GET` | `/api/admin/reviews/{review_id}` | 已实现 | 复盘详情（含证据链）（见 §7.9） |
| `GET` | `/api/admin/tickets` | 已实现 | 复核队列（见 §7.12） |
| `GET` | `/api/admin/tickets/{ticket_id}` | 已实现 | 复核任务详情（留痕）（见 §7.13） |
| `POST` | `/api/admin/tickets/{ticket_id}/transition` | 已实现 | 复核任务流转（见 §7.10） |
| `GET` | `/api/admin/dashboard` | 已实现 | 看板数据（见 §7.11） |
| `POST` | `/api/admin/subjects/{subject_id}/sensevoice-sync` | 已实现（默认关闭） | 触发思想汇报转写 + 情绪同步；受 `SENSEVOICE_SYNC_ENABLED` 控制（见 §7.15） |
| `GET` | `/api/admin/subjects/{subject_id}/sensevoice-syncs` | 已实现 | 同步记录列表（见 §7.16） |
| `GET` | `/api/admin/sensevoice-syncs/{sync_id}` | 已实现 | 同步详情（含转写全文与情绪报告，读取留痕；见 §7.17） |
| `GET` | `/api/admin/subjects/{subject_id}/trends` | 已实现 | 对象心理状态趋势（任意日期区间、多维聚合；见 §7.18） |

## 6. 序列化脱敏规则

| 接口 | 必须剔除 | 说明 |
|---|---|---|
| `GET /api/user/sessions/{id}/feedback` | `final_color`、`risk_level`、`evidence`、`rules_fired`、`transcript`、`face_path` | 用户端不显示色码 |
| 所有用户端接口 | `consent_json` 之外的其他对象字段 | 仅返回必要信息 |
| `GET /api/admin/tickets/{id}` | 无 | 但需写 `audit_logs(sensitive.view)` |
| `GET /api/admin/sessions/{id}/transcript` | 无 | 必须写留痕 |
| `GET /api/admin/sensevoice-syncs/{id}` | 无 | 含转写原文，必须写留痕 |
| `GET /api/admin/subjects/{id}/trends` | 转写原文、`transcript_path`、`audio_path`、影像、`face_path` | 仅返回聚合指标，不含个体敏感原文 |
| `/api/user/ai-assist/*` | 用户消息原话、AI 回复原文、上游响应体、`DEEPSEEK_API_KEY` | 对话不落库、不写日志；`audit_logs.detail_json` 仅记录模型、轮次、状态等元数据 |
| 全局日志 | 音频内容、转写原文、面部图 base64、`audio_path` 绝对路径 | 红线 |

`feedback` 只允许返回：`status`、`summary_text`（中性表述）、`suggestion`（枚举）、`next_action`。

## 7. 端点详情

### 7.1 `/api/user/consent` 系列（GET / PUT / revoke）

三个端点均要求 `subject` 角色（`staff` 调用返回 `1003`）；`subject_id`：`PUT` / `revoke` 在 body，`GET` 在 query `?subject_id=`。对象不存在返回 `1004`。`PUT` 成功写一条 `audit_logs(action=consent.grant)`，`revoke` 成功写一条 `audit_logs(action=consent.revoke)`，`detail_json` 不含敏感信息。

`consent_json` 结构与 [db.md §2.1](./db.md) 一致：`schema_version`、`general`、`face`、`audio`、`revoked_at`、`retention_days`。

#### 7.1.1 `GET /api/user/consent`

```bash
curl "http://localhost:8000/api/user/consent?subject_id=3b1e7c90-2f4a-4d51-8c6b-7d9e0f1a2b3c" \
  -H "Authorization: Bearer user_demo"
```

尚未同意时返回全 `granted: false`、`at: null`、`revoked_at: null`、`retention_days: null`：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "subject_id": "3b1e7c90-2f4a-4d51-8c6b-7d9e0f1a2b3c",
    "general": { "granted": false, "at": null },
    "face": { "granted": false, "at": null },
    "audio": { "granted": false, "at": null },
    "revoked_at": null,
    "retention_days": null
  },
  "degraded": [],
  "request_id": "6f1c2d3e-4a5b-4c7d-8e9f-0a1b2c3d4e5f"
}
```

#### 7.1.2 `PUT /api/user/consent`

```bash
curl -X PUT http://localhost:8000/api/user/consent \
  -H "Authorization: Bearer user_demo" \
  -H "Content-Type: application/json" \
  -d '{
    "subject_id": "3b1e7c90-2f4a-4d51-8c6b-7d9e0f1a2b3c",
    "face": true,
    "audio": true,
    "retention_days": 180
  }'
```

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "subject_id": "3b1e7c90-2f4a-4d51-8c6b-7d9e0f1a2b3c",
    "general": { "granted": true, "at": "2026-11-23T10:00:00+08:00" },
    "face": { "granted": true, "at": "2026-11-23T10:00:00+08:00" },
    "audio": { "granted": true, "at": "2026-11-23T10:00:00+08:00" },
    "revoked_at": null,
    "retention_days": 180
  },
  "degraded": [],
  "request_id": "6f1c2d3e-4a5b-4c7d-8e9f-0a1b2c3d4e5f"
}
```

- 入参：`subject_id`（body）、`face`（bool）、`audio`（bool）、`retention_days`（int，≥1，**可选，缺省 180**；2026-11-24 起由必填改为可选，服务端补齐默认值）；
- `retention_days` 仅用于留存管理与审计，**用户端页面不得展示或要求填写**（ui@1.2 §3.1 补记 2）；响应中仍返回该字段；
- `face` 与 `audio` 至少一项为 `true`，否则 `1001`；`general.granted = face or audio`；
- 单项授权仅用于记录本人意愿，**不构成可采集状态**：发起采集前 `face` 与 `audio` 必须同时为 `true`，否则 `POST /api/sessions` 返回 `1005 consent_incomplete`（见 7.2）。该强校验口径与 ui@1.2 §3.1 一致；
- 成功后覆写 `subjects.consent_json`，`at` 取服务端当前时间，`revoked_at` 置 `null`。

#### 7.1.3 `POST /api/user/consent/revoke`

```bash
curl -X POST http://localhost:8000/api/user/consent/revoke \
  -H "Authorization: Bearer user_demo" \
  -H "Content-Type: application/json" \
  -d '{ "subject_id": "3b1e7c90-2f4a-4d51-8c6b-7d9e0f1a2b3c" }'
```

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "subject_id": "3b1e7c90-2f4a-4d51-8c6b-7d9e0f1a2b3c",
    "general": { "granted": true, "at": "2026-11-23T10:00:00+08:00" },
    "face": { "granted": true, "at": "2026-11-23T10:00:00+08:00" },
    "audio": { "granted": true, "at": "2026-11-23T10:00:00+08:00" },
    "revoked_at": "2026-11-24T09:00:00+08:00",
    "retention_days": 180
  },
  "degraded": [],
  "request_id": "6f1c2d3e-4a5b-4c7d-8e9f-0a1b2c3d4e5f"
}
```

- 入参：`subject_id`（body）；
- 从未同意（`consent_json` 为空）时撤回返回 `1005`、`message=consent_not_granted`；
- 已撤回再次撤回幂等：`revoked_at` 保持首次撤回时间，不重复写留痕；
- 撤回后 `POST /api/sessions` 拒绝发起新采集（见 7.2）。

### 7.2 `POST /api/sessions`

异步发起一次采集：接口立即返回 `status=created`，采集由后台任务执行；完成后回写 `status` / `capture_status` / `face_path` / `audio_path` / `codes` / `duration_sec` / `captured_at`，失败也落库为 `status=failed` + `codes`。

- 异步返回 `created`，不代表采集完成；
- 状态流转固定为 `created → captured` 或 `created → failed`，不出现其他中间态；
- 前端轮询 `GET /api/sessions/{id}` 获取最终状态；
- 同一时刻仅允许一个采集任务，第二个请求返回 `code=5000`、`message=capture_busy`（专用错误码待增补）；
- 入参 `subject_id` 必须已存在，否则 `1004`。
- 入参 `kind`（`checkin`/`report`，缺省 `report`，见顶部补记·二）：`checkin` 为 face_only 采集；`report` 为 face+audio 双模态采集。

```bash
curl -X POST http://localhost:8000/api/sessions \
  -H "Authorization: Bearer user_demo" \
  -H "Content-Type: application/json" \
  -d '{
    "subject_id": "3b1e7c90-2f4a-4d51-8c6b-7d9e0f1a2b3c",
    "device_index": 0,
    "duration_sec": 10
  }'
```

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "session_id": "8f3c1b2e-4a5d-4c6e-9f10-1a2b3c4d5e6f",
    "status": "created"
  },
  "degraded": [],
  "request_id": "6f1c2d3e-4a5b-4c7d-8e9f-0a1b2c3d4e5f"
}
```

采集并发冲突：

```json
{
  "code": 5000,
  "message": "capture_busy",
  "data": null,
  "degraded": [],
  "request_id": "6f1c2d3e-4a5b-4c7d-8e9f-0a1b2c3d4e5f"
}
```

前置校验：

| 条件 | 失败返回 |
|---|---|
| 同时已有采集任务 | `5000`，`message=capture_busy` |
| `subject_id` 不存在 | `1004` |
| `consent.revoked_at != null` | `1005`，`message=consent_revoked` |
| `consent.general.granted != true` | `1005`，`message=consent_required` |
| `consent.face.granted != true` 或 `consent.audio.granted != true` | `1005`，`message=consent_incomplete` |
| 60 秒内重复请求 | `1006`（未实现） |

校验顺序：并发闸 → `subject_id` 存在 → consent 三道闸（`revoked` → `general` → `face/audio`）。consent 任一命中即返回，不创建会话、不写库。三道 consent 闸与 [db.md §2.1](./db.md) 对齐，消除历史不一致。

### 7.3 `GET /api/sessions/{session_id}`

```bash
curl http://localhost:8000/api/sessions/8f3c1b2e-4a5d-4c6e-9f10-1a2b3c4d5e6f \
  -H "Authorization: Bearer user_demo"
```

采集进行中：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "session_id": "8f3c1b2e-4a5d-4c6e-9f10-1a2b3c4d5e6f",
    "subject_id": "3b1e7c90-2f4a-4d51-8c6b-7d9e0f1a2b3c",
    "status": "created",
    "capture_status": null,
    "coverage": null,
    "face_available": false,
    "audio_available": false,
    "duration_sec": null,
    "captured_at": null,
    "analysis_status": "pending",
    "codes": [],
    "created_at": "2026-11-23T10:12:03+08:00",
    "updated_at": "2026-11-23T10:12:03+08:00"
  },
  "degraded": [],
  "request_id": "6f1c2d3e-4a5b-4c7d-8e9f-0a1b2c3d4e5f"
}
```

采集降级（`partial` / `no_face` / `no_audio`）：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "session_id": "8f3c1b2e-4a5d-4c6e-9f10-1a2b3c4d5e6f",
    "subject_id": "3b1e7c90-2f4a-4d51-8c6b-7d9e0f1a2b3c",
    "status": "captured",
    "capture_status": "partial",
    "coverage": "face_only",
    "face_available": true,
    "audio_available": false,
    "duration_sec": 10.0,
    "captured_at": "2026-11-23T10:12:36+08:00",
    "analysis_status": "pending",
    "codes": ["no_face"],
    "created_at": "2026-11-23T10:12:03+08:00",
    "updated_at": "2026-11-23T10:12:36+08:00"
  },
  "degraded": ["capture"],
  "request_id": "6f1c2d3e-4a5b-4c7d-8e9f-0a1b2c3d4e5f"
}
```

采集失败：

```json
{
  "code": 2001,
  "message": "capture_failed",
  "data": {
    "session_id": "8f3c1b2e-4a5d-4c6e-9f10-1a2b3c4d5e6f",
    "subject_id": "3b1e7c90-2f4a-4d51-8c6b-7d9e0f1a2b3c",
    "status": "failed",
    "capture_status": "error",
    "coverage": null,
    "face_available": false,
    "audio_available": false,
    "duration_sec": null,
    "captured_at": "2026-11-23T10:12:05+08:00",
    "analysis_status": "pending",
    "codes": ["camera_unavailable"],
    "created_at": "2026-11-23T10:12:03+08:00",
    "updated_at": "2026-11-23T10:12:05+08:00"
  },
  "degraded": [],
  "request_id": "6f1c2d3e-4a5b-4c7d-8e9f-0a1b2c3d4e5f"
}
```

- `coverage` 只能来自 `CaptureSession.coverage` 派生属性，API 层不得重新推导；
- `face_available` / `audio_available` 由 `face_path` / `audio_path` 是否非空决定；
- 响应只给相对 `face_path` 语义的可用性标记，不返回路径本身、不返回音频或图像二进制；
- `code` 判定：`status == failed` → `2001`（`message=capture_failed`）；否则 `analysis_status == failed` → `2003`（`message=analysis_failed`）；其余 `code=0`；两种失败都仍返回会话摘要便于展示 `codes`；
- 归属校验：`subject` 角色调用时必须带 query `subject_id`，且 `session.subject_id == subject_id`，否则 `1003`；缺 `subject_id` 返回 `1001`。`staff` 角色无需 `subject_id`、跳过归属校验。

### 7.4 `POST /api/sessions/{session_id}/analyze`

```bash
curl -X POST http://localhost:8000/api/sessions/8f3c1b2e-4a5d-4c6e-9f10-1a2b3c4d5e6f/analyze \
  -H "Authorization: Bearer admin_demo"
```

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "session_id": "8f3c1b2e-4a5d-4c6e-9f10-1a2b3c4d5e6f",
    "analysis_status": "done",
    "review_id": "c41d0a77-9b2e-4f83-a1c5-6d7e8f9a0b1c",
    "review_created": true,
    "ticket_id": "5e2f9b11-3c4d-4a6b-8e7f-0a1b2c3d4e5f"
  },
  "degraded": [],
  "request_id": "6f1c2d3e-4a5b-4c7d-8e9f-0a1b2c3d4e5f"
}
```

| 条件 | 返回 |
|---|---|
| 会话不存在 | `1004` |
| `status == created` | `4000`，`message=session_not_captured` |
| `status == failed` | `2001`，`message=capture_failed` |
| `status == captured`，分析彻底失败 | `2003`，`message=analysis_failed`，`data` 为会话摘要（同 7.3） |
| `status == captured`，分析可用 | `0`，`analysis_status` 为 `done` / `degraded` |
| 非 `staff` token | `1003` |

- 分析可用时写回 `analysis_json` / `transcript_path`（ASR 成功时）/ `analysis_status`，再按会话所属自然日窗口生成复盘与复核任务；分析失败只写 `analysis_status=failed`，**不回写** `sessions.status`；
- `degraded` 按 §2.1 组装（采集降级 + 分析降级）；
- 幂等：`analysis_json` 已存在时复用，不重复跑分析；同一 `(subject_id, window_end)` 的复盘已存在时复用，不重复生成任务；`review_created=false` 表示复用；
- `ticket_id` 为 `null` 表示未生成任务（仅「绿 + 不复核 + 非采集降级」会出现）；
- 每次调用写一条 `audit_logs(action=session.analyze, target_type=session, target_id={session_id})`，`detail_json` 不含转写原文与路径；响应 `degraded` 按 §2.1 组装。

### 7.5 `GET /api/admin/sessions/{session_id}/face`

```bash
curl -o face.jpg http://localhost:8000/api/admin/sessions/8f3c1b2e-4a5d-4c6e-9f10-1a2b3c4d5e6f/face \
  -H "Authorization: Bearer admin_demo"
```

- 成功：`image/jpeg` 二进制（信封唯一例外）；
- 路径按 `STORAGE_ROOT + face_path` 解析，且必须落在 `STORAGE_ROOT` 之内；
- 每次成功读取前写一条 `audit_logs`：`actor_type=staff`、`action=sensitive.view`、`target_type=session`、`target_id={session_id}`、`detail_json={"field":"face"}`、`request_id={本次请求 id}`，**不得写入路径或图像内容**；
- 留痕写入失败 → `5000`、`message=audit_write_failed`，且不得返回图片；
- 会话不存在或文件缺失 → `1004`；
- 非 `staff` token → `1003`。

### 7.6 `GET /api/admin/subjects`

```bash
curl "http://localhost:8000/api/admin/subjects?keyword=S001&status=active&page=1&page_size=20" \
  -H "Authorization: Bearer admin_demo"
```

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "items": [
      {
        "subject_id": "3b1e7c90-2f4a-4d51-8c6b-7d9e0f1a2b3c",
        "code": "S001",
        "name": "张某某",
        "status": "active",
        "latest_color": null,
        "latest_color_at": null,
        "latest_rules": [],
        "pending_tickets": 0,
        "latest_session_at": "2026-11-23T10:12:36+08:00"
      }
    ],
    "page": 1,
    "page_size": 20,
    "total": 1
  },
  "degraded": [],
  "request_id": "6f1c2d3e-4a5b-4c7d-8e9f-0a1b2c3d4e5f"
}
```

`latest_color` 必须同时返回 `latest_color_at` 与 `latest_rules`；前端渲染色码时必须并列展示规则与证据入口，不允许只渲染颜色块。尚无复盘数据时三者分别为 `null` / `null` / `[]`。

### 7.7 `GET /api/admin/sessions`

```bash
curl "http://localhost:8000/api/admin/sessions?subject_id=3b1e7c90-2f4a-4d51-8c6b-7d9e0f1a2b3c&status=captured" \
  -H "Authorization: Bearer admin_demo"
```

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "items": [
      {
        "session_id": "8f3c1b2e-4a5d-4c6e-9f10-1a2b3c4d5e6f",
        "subject_id": "3b1e7c90-2f4a-4d51-8c6b-7d9e0f1a2b3c",
        "status": "captured",
        "capture_status": "partial",
        "coverage": "face_only",
        "analysis_status": "pending",
        "captured_at": "2026-11-23T10:12:36+08:00"
      }
    ],
    "page": 1,
    "page_size": 20,
    "total": 1
  },
  "degraded": [],
  "request_id": "6f1c2d3e-4a5b-4c7d-8e9f-0a1b2c3d4e5f"
}
```

### 7.8 `GET /api/user/sessions/{session_id}/feedback`

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "session_id": "8f3c1b2e-4a5d-4c6e-9f10-1a2b3c4d5e6f",
    "status": "captured",
    "summary_text": "本次记录已完成。",
    "suggestion": "keep_routine",
    "next_action": "下次按约定时间再来即可"
  },
  "degraded": [],
  "request_id": "6f1c2d3e-4a5b-4c7d-8e9f-0a1b2c3d4e5f"
}
```

`suggestion` 枚举：`keep_routine` / `talk_to_staff` / `recapture`。
**不得出现**色码、规则编号、分数、诊断词。

- 需 `subject` 角色，必须带 query `subject_id` 且 `session.subject_id == subject_id`，否则 `1003`；缺 `subject_id` 返回 `1001`；会话不存在返回 `1004`；
- `grading` 未接入前，`suggestion` / `summary_text` / `next_action` 由采集状态确定性映射（中性，不含任何色码/规则/分数/诊断）：

| `status` / `capture_status` | `suggestion` | `summary_text` | `next_action` |
|---|---|---|---|
| `created` | `keep_routine` | 本次记录仍在进行中。 | 请稍候，完成后可查看结果 |
| `captured` / `ok` | `keep_routine` | 本次记录已完成。 | 下次按约定时间再来即可 |
| `captured` / `partial` | `keep_routine` | 本次记录已完成。 | 结果已转工作人员复核，按约定时间再来即可 |
| `captured` / `no_face`、`no_audio`、`no_face_no_audio` | `recapture` | 本次记录已完成。 | 建议稍后重新采集一次 |
| `failed` / `error` | `talk_to_staff` | 本次记录未完成。 | 设备暂时不可用，请联系工作人员 |
| `failed` / 其他 | `recapture` | 本次记录未完成。 | 建议稍后重新采集一次 |

- `grading` 就绪后，`suggestion` 改由复盘结果派生，但脱敏边界（仅返回 `status` / `summary_text` / `suggestion` / `next_action`）保持不变。

### 7.9 `GET /api/admin/reviews/{review_id}`

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "review_id": "c41d0a77-9b2e-4f83-a1c5-6d7e8f9a0b1c",
    "subject_id": "3b1e7c90-2f4a-4d51-8c6b-7d9e0f1a2b3c",
    "window_start": "2026-11-17",
    "window_end": "2026-11-23",
    "window_days": 7,
    "single_session_risk": "none",
    "trend_color": "blue",
    "final_color": "blue",
    "consistency": "medium",
    "manual_review": false,
    "rules_fired": ["R_TREND_BLUE"],
    "grading_version": "grading@1.2",
    "evidence": [
      {
        "rule_id": "R_TREND_BLUE",
        "rule_version": "grading@1.2",
        "field_path": "channels.psych.output.signal_strength",
        "observed_value": 41.2,
        "threshold_key": "TREND_BLUE_OFFSET_MIN",
        "threshold_value": 0.8,
        "offset_score": 1.02,
        "session_id": "8f3c1b2e-4a5d-4c6e-9f10-1a2b3c4d5e6f",
        "window": ["2026-11-17", "2026-11-23"],
        "triggered_at": "2026-11-23T10:13:00+08:00"
      }
    ],
    "created_at": "2026-11-23T10:13:00+08:00"
  },
  "degraded": [],
  "request_id": "6f1c2d3e-4a5b-4c7d-8e9f-0a1b2c3d4e5f"
}
```

- `window_start` / `window_end` 为 `YYYY-MM-DD` 自然日（含端点），与证据 `window` 一致；
- `evidence` 原样返回 `reviews.evidence_json`；`offset_score` / `insufficient` / `window` 为可选字段，按实际存在返回；
- `review_id` 不存在返回 `1004`；非 `staff` 返回 `1003`。

### 7.10 `POST /api/admin/tickets/{ticket_id}/transition`

```bash
curl -X POST http://localhost:8000/api/admin/tickets/5e2f9b11-3c4d-4a6b-8e7f-0a1b2c3d4e5f/transition \
  -H "Authorization: Bearer admin_demo" \
  -H "Content-Type: application/json" \
  -d '{
    "action": "correct",
    "conclusion_color": "green",
    "note": "面谈确认近期家庭事务较多，情绪波动属情境性，无需升级关注。",
    "assignee": "E1024"
  }'
```

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "ticket_id": "5e2f9b11-3c4d-4a6b-8e7f-0a1b2c3d4e5f",
    "status": "closed",
    "previous_status": "pending",
    "action": "correct",
    "conclusion_color": "green",
    "conclusion_note": "面谈确认近期家庭事务较多，情绪波动属情境性，无需升级关注。",
    "assignee": "E1024",
    "closed_at": "2026-11-23T15:20:00+08:00"
  },
  "degraded": [],
  "request_id": "6f1c2d3e-4a5b-4c7d-8e9f-0a1b2c3d4e5f"
}
```

校验：

| 动作 | 必填 | 失败返回 |
|---|---|---|
| `confirm` | — | 复核任务已 `closed` → `1005`，`message=ticket_closed` |
| `correct` | `conclusion_color`、`note` | 缺字段 → `1001`；已 `closed` → `1005 ticket_closed` |
| `close` | `note` | 缺字段 → `1001`；已 `closed` → `1005 ticket_closed` |

- 单次请求原子落到终态 `closed` 并写 `closed_at`；`confirm` / `correct` 的中间态只体现在 `audit_logs(action=ticket.transition, detail_json.action)`；
- 每次流转写一条 `audit_logs`：`actor_type=staff`、`actor_id=assignee`（可选）、`action=ticket.transition`、`target_type=ticket`、`target_id={ticket_id}`、`detail_json` 含 `action` / `previous_status` / `conclusion_color` / `note`（`note` 为工作人员结论说明，可入审计；禁止写入音频、转写原文、面部图）；
- 复核任务不存在 → `1004`；非 `staff` → `1003`。

### 7.11 `GET /api/admin/dashboard`

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "subject_id": "3b1e7c90-2f4a-4d51-8c6b-7d9e0f1a2b3c",
    "color_distribution": { "green": 3, "blue": 2, "yellow": 0, "orange": 0, "red": 0 },
    "trend_7d": [
      { "date": "2026-11-17", "color": "green" },
      { "date": "2026-11-23", "color": "blue" }
    ],
    "pending_tickets": 1,
    "last_session_at": "2026-11-23T10:12:36+08:00"
  },
  "degraded": [],
  "request_id": "6f1c2d3e-4a5b-4c7d-8e9f-0a1b2c3d4e5f"
}
```

> 看板按**单对象**聚合。不提供跨对象排行、榜单类字段。

- query `subject_id` 可选：缺省时取「最近一次 `captured` 会话所属对象」，保证前端无需额外参数；库内无任何对象/会话时返回 `1004`；
- `color_distribution` 统计该对象全部 `reviews.final_color`；`trend_7d` 按 `reviews.created_at` 所在自然日聚合，只返回近 7 个自然日内存在复盘的日期（同日多条取 `created_at` 最新），无复盘的日期不返回；
- 不提供跨对象聚合。

### 7.12 `GET /api/admin/tickets`

```bash
curl "http://localhost:8000/api/admin/tickets?status=pending&priority=P0&subject_id=3b1e7c90-2f4a-4d51-8c6b-7d9e0f1a2b3c&page=1&page_size=20" \
  -H "Authorization: Bearer admin_demo"
```

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "items": [
      {
        "ticket_id": "5e2f9b11-3c4d-4a6b-8e7f-0a1b2c3d4e5f",
        "subject_id": "3b1e7c90-2f4a-4d51-8c6b-7d9e0f1a2b3c",
        "subject_name": "张某某",
        "priority": "P0",
        "final_color": "orange",
        "triggered_rules": ["R_SINGLE_ORANGE"],
        "opened_at": "2026-11-23T15:20:00+08:00",
        "due_at": "2026-11-24T15:20:00+08:00",
        "status": "pending"
      }
    ],
    "page": 1,
    "page_size": 20,
    "total": 1
  },
  "degraded": [],
  "request_id": "6f1c2d3e-4a5b-4c7d-8e9f-0a1b2c3d4e5f"
}
```

- 过滤：`status`（`pending`/`confirmed`/`corrected`/`closed`）、`priority`（`P0`/`P1`/`P2`）、`subject_id`、分页；非法枚举 → `1001`；
- 排序：`priority ASC, opened_at DESC`（P0 置顶）；
- `final_color` 来自关联 `reviews.final_color`；`subject_name` 取 `subjects.name`。

### 7.13 `GET /api/admin/tickets/{ticket_id}`

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "ticket_id": "5e2f9b11-3c4d-4a6b-8e7f-0a1b2c3d4e5f",
    "subject_id": "3b1e7c90-2f4a-4d51-8c6b-7d9e0f1a2b3c",
    "subject_name": "张某某",
    "priority": "P0",
    "final_color": "orange",
    "triggered_rules": ["R_SINGLE_ORANGE"],
    "rules_fired": ["R_SINGLE_ORANGE"],
    "suggested_method": "priority_interview",
    "status": "pending",
    "opened_at": "2026-11-23T15:20:00+08:00",
    "due_at": "2026-11-24T15:20:00+08:00",
    "evidence": [
      {
        "rule_id": "R_SINGLE_ORANGE",
        "field_path": "channels.psych.output.signal_strength",
        "observed_value": 72.5,
        "threshold_key": "SINGLE_ORANGE_SIGNAL_MIN",
        "threshold_value": 70,
        "session_id": "8f3c1b2e-4a5d-4c6e-9f10-1a2b3c4d5e6f"
      }
    ],
    "history": [
      { "action": "opened", "actor": "system", "note": null, "at": "2026-11-23T15:20:00+08:00" },
      { "action": "correct", "actor": "E1024", "note": "面谈确认…", "at": "2026-11-23T15:25:00+08:00" }
    ]
  },
  "degraded": [],
  "request_id": "6f1c2d3e-4a5b-4c7d-8e9f-0a1b2c3d4e5f"
}
```

- `evidence` 原样返回 `review_tickets.evidence_json`（可选字段按实际存在返回）；
- `history` 由 `audit_logs(action=ticket.transition)` 按时间升序组装，并补一条 `opened` / `system` 的生成记录；流转记录的 `actor` 取审计 `actor_id`（即 `assignee`），未提供时回落 `"staff"`；
- 读取成功前写一条 `audit_logs(action=sensitive.view, target_type=ticket, target_id={ticket_id}, detail_json={"field":"ticket"})`；留痕失败 → `5000 audit_write_failed`，不返回数据；
- 不存在 → `1004`；非 `staff` → `1003`。

### 7.14 `POST /api/admin/reviews`

窗口复盘（手动补算 / 演示）。入参：

```json
{ "subject_id": "3b1e7c90-2f4a-4d51-8c6b-7d9e0f1a2b3c", "window_end": "2026-11-23", "window_days": 7 }
```

```json
{ "code": 0, "message": "ok", "data": { "...": "同 §7.9 ReviewDetail" }, "degraded": [], "request_id": "..." }
```

- `subject_id` 必填；`window_end` 可选（默认今天，`YYYY-MM-DD`）；`window_days` 可选（默认 7，≥1）；非法 → `1001`；对象不存在 → `1004`；
- 窗口 `[window_end - (window_days - 1), window_end]`，按自然日；
- **可用会话** = `sessions.status = captured` 且 `analysis_status in (done, degraded)`；窗口内 0 条 → `1005`、`message=no_session_in_window`，**不落库、不生成任务**；
- 有可用会话时，取窗口内 `captured_at` 最新的一条作为 `source_session_id`，执行 `evaluate_session → evaluate_period → compose`；`capture_status in (partial, no_face, no_audio)` 时覆写 `review_reason="capture_degraded"` 后再 `build_ticket`；
- 同一 `(subject_id, window_end)` 已存在复盘时直接返回该复盘（幂等），不重复生成任务；
- 成功写 `audit_logs(action=review.create, target_type=review, target_id={review_id})`。

### 7.15 `POST /api/admin/subjects/{subject_id}/sensevoice-sync`

触发一次「思想汇报音频 → SenseVoice 转写 → 情绪分析 → 落库」同步。需 `staff`。

请求体（可省略或传空对象）：

```json
{ "session_id": "8f3c1b2e-4a5d-4c6e-9f10-1a2b3c4d5e6f" }
```

- `session_id` 可选；缺省取该对象最近一次可用汇报会话（`kind='report'` 且 `status='captured'` 且 `audio_path IS NOT NULL`，按 `captured_at` 倒序）；
- 成功返回 `data` 为同步摘要（字段同 §7.16 列表项）；
- 单事务：选会话 → 调 ASR → 调情绪 → 写 `sensevoice_syncs` → 写 `audit_logs`；任一步失败整体回滚，不留同步记录；
- 同一会话允许重复同步，每次生成新的 `data_version`，不覆盖历史记录。

错误：

| 情况 | code | message |
|---|---|---|
| 对象不存在 / 指定的 `session_id` 不属于该对象 | 1004 | `not_found` |
| `SENSEVOICE_SYNC_ENABLED` 未开启（默认关闭） | 5001 | `sensevoice_sync_disabled` |
| `SENSEVOICE_API_URL` / `SENSEVOICE_API_KEY` 缺失或服务不可达 | 5001 | `sensevoice_unavailable` |
| 指定会话非 `report` / 非 `captured` / 无音频；或缺省时无可用汇报会话 | 1005 | `no_report_audio` |
| 转写失败 | 2004 | `transcription_failed` |
| 情绪分析失败 | 2004 | `emotion_failed` |

- 开关关闭、无可用会话时**不落库、不写审计**；
- 成功写一条 `audit_logs(action=sensevoice.sync, target_type=sensevoice_sync, target_id={sync_id})`，`detail_json` 仅含 `session_id`、`data_version`、`operator`，**不含转写原文**；
- 成功响应示例（`degraded` 固定为 `[]`）：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "sync_id": "c1a2b3c4-d5e6-4f70-8a9b-0c1d2e3f4a5b",
    "subject_id": "3b1e7c90-2f4a-4d51-8c6b-7d9e0f1a2b3c",
    "session_id": "8f3c1b2e-4a5d-4c6e-9f10-1a2b3c4d5e6f",
    "status": "succeeded",
    "provider": "sensevoice",
    "emotion_primary": "焦虑",
    "emotion_confidence": 0.87,
    "data_version": "sensevoice@1.0+20261125T101203",
    "operator": "staff",
    "created_at": "2026-11-25T10:12:05+08:00"
  },
  "degraded": [],
  "request_id": "6f1c2d3e-4a5b-4c7d-8e9f-0a1b2c3d4e5f"
}
```

### 7.16 `GET /api/admin/subjects/{subject_id}/sensevoice-syncs`

同步记录列表，按 `created_at` 倒序。需 `staff`。

query：`page`（默认 1）、`page_size`（默认 20，最大 100）。对象不存在 → `1004`。

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "items": [
      {
        "sync_id": "c1a2b3c4-d5e6-4f70-8a9b-0c1d2e3f4a5b",
        "subject_id": "3b1e7c90-2f4a-4d51-8c6b-7d9e0f1a2b3c",
        "session_id": "8f3c1b2e-4a5d-4c6e-9f10-1a2b3c4d5e6f",
        "status": "succeeded",
        "provider": "sensevoice",
        "emotion_primary": "焦虑",
        "emotion_confidence": 0.87,
        "data_version": "sensevoice@1.0+20261125T101203",
        "operator": "staff",
        "created_at": "2026-11-25T10:12:05+08:00"
      }
    ],
    "page": 1,
    "page_size": 20,
    "total": 1
  },
  "degraded": [],
  "request_id": "6f1c2d3e-4a5b-4c7d-8e9f-0a1b2c3d4e5f"
}
```

- 列表**不返回**转写原文与情绪片段（敏感内容走 §7.17 详情并留痕）。

### 7.17 `GET /api/admin/sensevoice-syncs/{sync_id}`

同步详情，含转写全文与情绪报告。需 `staff`。不存在 → `1004`。

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "sync_id": "c1a2b3c4-d5e6-4f70-8a9b-0c1d2e3f4a5b",
    "subject_id": "3b1e7c90-2f4a-4d51-8c6b-7d9e0f1a2b3c",
    "session_id": "8f3c1b2e-4a5d-4c6e-9f10-1a2b3c4d5e6f",
    "status": "succeeded",
    "provider": "sensevoice",
    "transcript_text": "最近工作压力比较大，晚上总是睡不好……",
    "transcript_language": "zh",
    "emotion": {
      "schema_version": "emotion@1.0",
      "primary": "焦虑",
      "confidence": 0.87,
      "scores": { "焦虑": 0.87, "平静": 0.13 },
      "triggers": [
        {
          "text": "最近总是睡不好，心里很慌",
          "label": "焦虑",
          "start_sec": 3.2,
          "end_sec": 5.1
        }
      ]
    },
    "data_version": "sensevoice@1.0+20261125T101203",
    "operator": "staff",
    "created_at": "2026-11-25T10:12:05+08:00",
    "updated_at": "2026-11-25T10:12:05+08:00"
  },
  "degraded": [],
  "request_id": "6f1c2d3e-4a5b-4c7d-8e9f-0a1b2c3d4e5f"
}
```

- 返回数据前写一条 `audit_logs(action=sensitive.view, target_type=sensevoice_sync, target_id={sync_id}, detail_json={"field":"transcript"})`；留痕失败 → `5000 audit_write_failed`，不返回数据；
- `emotion` 为 `emotion_json` 解析后的对象（结构见 db@1.5 §7.1）。

### 7.18 `GET /api/admin/subjects/{subject_id}/trends`

对象心理状态趋势：按任意日期区间聚合日粒度五色、文本心理指标、一致性与行为依从性，供管理端对象详情页多维度看板使用。需 `staff`。

```bash
curl "http://localhost:8000/api/admin/subjects/3b1e7c90-2f4a-4d51-8c6b-7d9e0f1a2b3c/trends?start_date=2026-11-12&end_date=2026-11-25" \
  -H "Authorization: Bearer admin_demo"
```

**查询参数**

| 参数 | 必填 | 默认 | 说明 |
|---|---|---|---|
| `start_date` | 否 | `end_date - 13` 天 | `YYYY-MM-DD` 自然日，闭区间 |
| `end_date` | 否 | 服务端当天 | `YYYY-MM-DD` 自然日，闭区间 |
| 只传 `start_date` | — | `end_date = start_date + 13` | 保持 14 天窗口 |
| 只传 `end_date` | — | `start_date = end_date - 13` | 保持 14 天窗口 |

**校验与错误**

| 条件 | 返回 |
|---|---|
| 日期非 `YYYY-MM-DD` | `1001`，`message=invalid_date` |
| `start_date > end_date` | `1001`，`message=invalid_date_range` |
| 区间跨度 > 366 天（含端点） | `1001`，`message=date_range_too_large` |
| 对象不存在 | `1004`，`message=not_found` |
| 区间内无任何会话与复盘 | `code=0`，`days` 逐日返回空指标，不报错 |

**响应 `data`**

```json
{
  "subject_id": "3b1e7c90-2f4a-4d51-8c6b-7d9e0f1a2b3c",
  "start_date": "2026-11-12",
  "end_date": "2026-11-25",
  "interval_days": { "checkin": 1, "report": 3 },
  "days": [
    {
      "date": "2026-11-20",
      "review": {
        "color": "yellow",
        "review_id": "c41d0a77-9b2e-4f83-a1c5-6d7e8f9a0b1c",
        "rules_fired": ["R_TREND_YELLOW"],
        "consistency": "medium",
        "manual_review": false,
        "evidence_available": true
      },
      "analysis_risk_level": "watch",
      "sessions": { "total": 2, "checkin": 1, "report": 1, "analyzed": 2, "failed": 0 },
      "text_valence": { "mean": -0.32, "std": 0.11, "count": 2 },
      "text_signal": { "mean": 48.5, "std": 9.2, "count": 2 },
      "consistency": { "degraded": 1, "low": 0, "conflict": 0 },
      "behavior": {
        "checkin": { "expected": true, "completed": true, "overdue": false },
        "report": { "expected": true, "completed": true, "overdue": false }
      }
    }
  ],
  "scatter_points": [
    {
      "date": "2026-11-20",
      "session_id": "8f3c1b2e-4a5d-4c6e-9f10-1a2b3c4d5e6f",
      "captured_at": "2026-11-20T09:12:36+08:00",
      "kind": "report",
      "valence": -0.42,
      "signal": 41.2,
      "arousal": 0.36,
      "emotion_label": "negative",
      "review_color": "yellow",
      "review_rules": ["R_TREND_YELLOW"],
      "review_id": "c41d0a77-9b2e-4f83-a1c5-6d7e8f9a0b1c"
    }
  ],
  "summary": {
    "analyzed_count": 6,
    "avg_valence": -0.30,
    "avg_signal": 45.0,
    "valence_std": 0.21,
    "signal_std": 11.4,
    "coverage_rate": 0.83,
    "quadrants": { "q1": 1, "q2": 2, "q3": 2, "q4": 1 },
    "signals": ["low_arousal_negative", "valence_volatility_high"]
  },
  "degraded": []
}
```

**字段语义（唯一口径，前端与后端不得各自推导）**

| 字段 | 类型 | 定义 |
|---|---|---|
| `days[]` | array | 区间内**每一天**一条，按日期升序；无数据的日期指标为 `null` 或 0 |
| `interval_days` | object | 对象**当前**频率配置 `{checkin, report}`，供前端解释行为期望与逾期口径 |
| `days[].review` | object \| null | `reviews.window_end == date` 的复盘（唯一约束保证至多一条）；无则 `null`。兼容历史数据中 `window_end` 为完整 ISO 时间戳的写法：按本地日期部分匹配；同日出现多条时优先精确 `YYYY-MM-DD` 行 |
| `days[].review.color` | enum | 五色 `green/blue/yellow/orange/red`，与 `reviews.final_color` 一致 |
| `days[].review.rules_fired` | string[] | 原样返回 `reviews.rules_fired`；前端渲染色块时必须同屏展示并给证据入口（ui@1.2 §5.2） |
| `days[].analysis_risk_level` | enum \| null | 当日 `analysis_status ∈ {done,degraded}` 的会话中 `overall.risk_level` 的最高档，序 `none < watch < elevated < high < crisis`；无则 `null`（pending/failed 不参与，避免残留 JSON 抬档） |
| `days[].sessions` | object | 当日会话计数：`total` 全部、`checkin` / `report` 按 `kind`、`analyzed` 为 `analysis_status ∈ {done,degraded}`、`failed` 为 `analysis_status=failed` |
| `days[].text_valence` / `text_signal` | object | 仅统计 `kind=report` 且 `analysis_status ∈ {done,degraded}` 且 `analysis_json` 可解析的会话；`mean` 算术均值，`std` 样本标准差，**`count < 2` 时 `std=null`**；`count=0` 时 `mean=null`；`count` 为该项**各自**可用数值个数 |
| `days[].consistency.degraded` | int | 当日 `analysis_status=degraded` 或 `analysis_json.degraded=true` 的会话数 |
| `days[].consistency.low` | int | 当日 `analysis_json.consistency=low` 的会话数 |
| `days[].consistency.conflict` | int | 当日 `analysis_json.consistency_basis.conflict=true` 的会话数 |
| `days[].behavior.<kind>.expected` | bool | 该自然日是否落在频率周期内，按**对象当前** `interval_days` 从最近一次完成日回溯计算 |
| `days[].behavior.<kind>.completed` | bool | 当日存在该 `kind` 且 `status=captured` 的会话 |
| `days[].behavior.<kind>.overdue` | bool | `expected && !completed`；**历史回溯值，与 §7.6/§7.11 的实时逾期不同** |
| `scatter_points[]` | array | 每次 `kind=report` 且 `analysis_status ∈ {done,degraded}` 的会话一条，按 `captured_at` 升序 |
| `scatter_points[].valence` | number | `overall.text_valence`，范围 `[-1, 1]` |
| `scatter_points[].signal` | number | `overall.text_signal`，范围 `[0, 100]` |
| `scatter_points[].arousal` | number \| null | `channels.emotion.output.arousal`，范围 `[0, 1]`；通道不可用时 `null` |
| `scatter_points[].emotion_label` | string \| null | `channels.emotion.output.label` |
| `scatter_points[].review_color` / `review_rules` / `review_id` | — | 该会话 `captured_at` 所在自然日的复盘五色、规则与 id；无复盘时分别为 `null` / `[]` / `null`（前端**不得**为此类点着色） |
| `summary.analyzed_count` | int | `scatter_points` 数量 |
| `summary.avg_valence` / `avg_signal` | number \| null | 全部散点的算术均值；无点时为 `null` |
| `summary.valence_std` / `signal_std` | number \| null | 全部散点的样本标准差；`analyzed_count < 2` 时为 `null` |
| `summary.coverage_rate` | number | 区间内应有采集日的完成率：签到与汇报两类会话的 `expected` 日次合并为分母、`completed` 日次合并为分子，结果保留 4 位小数；分母为 0 时为 `0` |
| `summary.quadrants` | object | q1=效价≥0&信号≥50；q2=效价<0&信号≥50；q3=效价<0&信号<50；q4=效价≥0&信号<50 |
| `summary.signals` | string[] | 见下方枚举，去重、固定顺序；**只回机器码，不回中文文案** |
| `degraded` | string[] | 固定 `[]`（与具体会话无关的聚合接口） |

**`summary.signals` 枚举（只增不改）**

| 码 | 含义（前端据此映射中性文案） |
|---|---|
| `insufficient_data` | 有效分析点 < 3 |
| `low_arousal_negative` | 均值效价 < 0 且均值信号 < 35 |
| `high_arousal_negative` | 均值效价 < 0 且均值信号 ≥ 70 |
| `persistent_low_valence` | 至少 3 个点且全部效价 < -0.3 |
| `valence_volatility_high` | `valence_std ≥ 0.35` 且有效点 ≥ 3 |
| `signal_escalating` | 后 3 点均值 − 前 3 点均值 ≥ 15 且点数 ≥ 6 |
| `frequent_low_consistency` | `low` 合计 ≥ 3 或占已分析会话 ≥ 40% |
| `frequent_capture_degraded` | `degraded` 合计 ≥ 3 |
| `behavior_overdue_frequent` | 区间内 `overdue` 日数 ≥ 3 |

> 上述阈值与象限分界为**契约常量**，标注「待标定」，后续统一迁入阈值配置；变更需版本化。

**明确不做**

1. 不返回转写原文、`transcript_path`、`audio_path`、影像或 `face_path`；
2. 不做跨对象聚合、排名或对比字段；
3. 不产生处置动作，不写业务表（只读），不写 `audit_logs`（不含个体敏感原文）；
4. 计算失败的单条 `analysis_json` 跳过该会话并在日志记录 `session_id`，不得使整个请求失败，也不得把异常原文写进响应。

### 7.19 `GET /api/user/ai-assist/status`

查询参数 `subject_id`；需 `subject` 角色；对象不存在 `1004`。响应 `code=0`：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "enabled": true,
    "web_search": true,
    "model": "deepseek-flash",
    "notice": null
  },
  "degraded": [],
  "request_id": "…"
}
```

- 未配置 `DEEPSEEK_API_KEY`：`enabled=false`、`web_search=false`、`model=null`，`notice="智能援助暂未开通，请联系工作人员"`，HTTP 200、`code=0`，**不返回 500**。
- `web_search` 表示本次部署是否声明了联网工具；`notice` 为空时为 `null`。
- 禁止返回 Key、Base URL 凭据或上游错误原文。

### 7.20 `POST /api/user/ai-assist/chat`（SSE）

需 `subject` 角色。请求体：

```json
{
  "subject_id": "3b1e7c90-2f4a-4d51-8c6b-7d9e0f1a2b3c",
  "messages": [
    { "role": "user", "content": "最近总是睡不着，心里很慌" },
    { "role": "assistant", "content": "……" },
    { "role": "user", "content": "我该怎么办？" }
  ]
}
```

| 字段 | 规则 |
|---|---|
| `subject_id` | 必填，对象必须存在，否则 `1004` |
| `messages` | 1–12 条；仅 `user` / `assistant`；最后一条必须为 `user` |
| 单条 `content` | 1–2000 字符 |
| 总字符数 | ≤ 12000 |

校验失败在开流前返回 JSON 信封（`1001` / `1004`）。通过后返回 `Content-Type: text/event-stream; charset=utf-8`，响应头含 `Cache-Control: no-cache, no-transform`、`X-Accel-Buffering: no`；每 15s 发送 `: keep-alive`。

SSE 事件（`data` 均为 JSON）：

| event | 载荷 | 说明 |
|---|---|---|
| `meta` | `{request_id, model, web_search, disclaimer}` | 首帧；`disclaimer` 为固定合规文案 |
| `delta` | `{text}` | 增量正文，前端逐字拼接 |
| `citation` | `{index, title, url}` | 可选；仅透传上游真实来源，**禁止编造** |
| `notice` | `{code, message}` | 降级提示，如 `web_search_unavailable` |
| `done` | `{finish_reason, degraded, request_id}` | 正常结束 |
| `error` | `{code, message, request_id}` | 流内错误；HTTP 仍为 200 |

上游调用（OpenAI 兼容 `POST {DEEPSEEK_BASE_URL}/chat/completions`，`Authorization: Bearer $DEEPSEEK_API_KEY`）：

```json
{
  "model": "deepseek-flash",
  "stream": true,
  "thinking": { "type": "disabled" },
  "messages": [{ "role": "system", "content": "……固定 System Prompt……" }, { "role": "user", "content": "……" }],
  "tools": [{ "type": "deepseek_web_search" }],
  "temperature": 0.3,
  "max_tokens": 800
}
```

- **禁止**设置 `tool_choice`（命名内置工具会 400）；是否搜索由模型决定。
- System Prompt 固定：仅回答心理援助与法律援助；不做诊断/开药/定罪/再犯预测；自伤伤人等紧急情形引导联系工作人员、120/110；提醒勿输入身份证号、住址、案件细节；超范围明确拒绝并引导工作人员；引用网络信息须给真实来源；结尾附「仅供参考，不构成专业建议」。
- 上游报错（含不支持工具声明、400/401/403/429/5xx、超时）：**自动降级为不带 `tools` 的普通对话**并发送 `notice(code="web_search_unavailable", message="本次回答未启用联网搜索")`；仍失败则发 `error`，不得 500，不得返回上游响应体。
- 未配置 Key：直接 `notice` + `done`，不请求上游。
- 若上游返回需要客户端执行的 `tool_calls`：不执行、不伪造结果，按降级处理。

**隐私与审计**

1. 不新增数据表、不写 SQLite 业务表、不写文件、不接收 `conversation_id`；历史由前端每轮携带。
2. 每次 POST 结束（含成功、降级、错误、客户端断连）写一条 `audit_logs`：`actor_type="subject"`、`actor_id=subject_id`、`action="ai_assist.chat"`、`target_type="subject"`、`target_id=subject_id`。
3. `detail_json` 仅允许 `{model, web_search, turns, status, degraded}`；`status ∈ ok|degraded|error|aborted|disabled`；**严禁**写入用户原话、AI 回复、消息摘要、prompt 或上游响应体。
4. 日志仅记录 `request_id`、端点、状态、上游 HTTP 状态码与耗时；不记录请求体、响应体与异常原文。
5. 流内审计使用新的 session 工厂上下文，不复用请求级 Session；审计失败不得中断已发送的流。

## 8. 前端联调 mock

后端未就绪时，前端使用 `web/src/mock/` 下的固定响应：

| 文件 | 覆盖接口 |
|---|---|
| `subject.json` | `/api/admin/subjects*` |
| `session.json` | `/api/sessions*`、`/api/admin/sessions*` |
| `review.json` | `/api/admin/reviews*` |
| `ticket.json` | `/api/admin/tickets*` |
| `dashboard.json` | `/api/admin/dashboard` |
| `trend.json` | `/api/admin/subjects/{id}/trends` |
| mock 内联（不落文件） | `/api/user/ai-assist/status` 返回 `enabled=false` + 中性提示；`/api/user/ai-assist/chat` 返回 `notice` + `done`，不产生模拟回答 |

mock 数据必须与本节示例字段完全一致，不得增删字段。

## 9. 契约变更流程

1. 子智能体不得直接改本文件，发现缺口在输出中列出；
2. 主智能体修改契约后，同步更新 `db.md` / `ui.md` 中受影响的字段；
3. 变更后由 `qa-guard` 跑一次契约校验；
4. 破坏性变更需在文件顶部追加变更记录。

### 变更记录

| 版本 | 日期 | 内容 |
|---|---|---|
| 1.0 | 2026-11-23 | 初版 |
| 1.3 | 2026-11-23 | 补 `created` 会话不可分析、不计入复盘 |
| 1.4 | 2026-11-23 | 信封改为 `{code,message,data,degraded,request_id}`（中间件 uuid4 + `X-Request-Id` + 日志/audit）；业务码 HTTP 200、未捕获异常 HTTP 500；路由统一为 `/api/sessions` + `/api/admin/*` + `/api/user/*`；`POST /api/sessions` 改异步 + 轮询；新增 `4000`；`5000` 增加 `analysis_pipeline_not_ready` / `capture_busy` 临时语义；鉴权改为 `USER_TOKEN` / `ADMIN_TOKEN`，`APP_ENV=production` 缺配置直接启动失败 |
| 1.5 | 2026-11-24 | 落地 `/api/user/*`（consent 查询/提交/撤回、feedback）；明确 subject 身份由客户端声明 `subject_id`（GET 走 query、写操作走 body）+ 会话归属校验（越权 `1003`）；`POST /api/sessions` 补齐 consent 三道闸（`revoked` → `general` → `face/audio`），新增 `consent_incomplete`，消除 db.md §2.1 与 api 不一致；`feedback` 在 grading 就绪前用采集状态做中性映射；60s 频控（1006）、analyze 接入、review 查询仍延期 |
| 1.5（实现补记） | 2026-11-24 | `analyze` 正式接入分析与五色分级（`2003`、幂等、`audit_logs(session.analyze)`）；新增 reviews（POST / GET 详情）、tickets（列表 / 详情 / 流转）、dashboard 契约；复盘窗口统一 `YYYY-MM-DD`；0 可用会话 → `1005 no_session_in_window`；consent 单项授权不可采集（`consent_incomplete`）；60s 频控仍延期 |
| 1.5（实现补记·二） | 2026-11-24 | 双模块：`POST /api/sessions` 增 `kind`；analyze 按 kind 分流；新增 `GET /api/user/tasks`、`PATCH /api/admin/subjects/{id}/frequency`；管理端读取时惰性幂等生成逾期 P0 复核任务；`retention_days` 可选缺省 180 |
| 1.5（实现补记·四） | 2026-11-25 | 思想汇报同步脚手架：新增 `sensevoice_syncs` 表（db@1.5 §7）与三个管理端端点（§7.15–7.17）；`SENSEVOICE_SYNC_ENABLED` 默认关闭；新增业务码 `2004` / `5001`；读取转写写 `sensitive.view`，同步成功写 `sensevoice.sync` |
| 1.5（实现补记·五） | 2026-11-25 | 新增 `GET /api/admin/subjects/{subject_id}/trends`（§7.18）：任意日期区间多维聚合（日五色、分析最高风险档、文本效价/信号均值与标准差、一致性告警、行为依从性、散点）；缺省近 14 天、上限 366 天；只回 `signals` 机器码不回中文结论；只读不落库、不含敏感原文；保留 dashboard / `trend_7d` 兼容 |
| 1.5（实现补记·六） | 2026-11-25 | 新增 AI 援助 `GET /api/user/ai-assist/status`、`POST /api/user/ai-assist/chat`（§7.19–7.20）：DeepSeek `deepseek-flash` + `thinking.type=disabled` + `tools:[{"type":"deepseek_web_search"}]`，不设 `tool_choice`；SSE 流式；无 Key 返回中性提示不报 500；不支持工具时自动降级并提示「本次回答未启用联网搜索」；对话不落业务表，仅写 `audit_logs(ai_assist.chat)` 元数据 |
