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
> 5. **逾期扫描（惰性、幂等）**：`GET /api/admin/subjects`、`GET /api/admin/subjects/{id}`、`GET /api/admin/dashboard` 调用时对相关对象执行逾期判定（`now - last_completed_at > interval_days`，从未完成过对应类型采集且距 `created_at` 超过频率同样视为逾期）；逾期则生成 P0 复核工单（`suggested_method=talk_to_staff`，`detail_json` 含 `overdue_kind`、`overdue_days`），同对象同类型存在未关闭逾期工单时不重复生成；响应中对象摘要增加 `overdue: {checkin, report}` 布尔标记。逾期判定不修改 `sessions.status`、不触发分析。
> 6. **序列化补齐（前端联调驱动）**：对象列表/详情返回 `checkin_interval_days`、`report_interval_days`；管理端会话列表项返回 `kind`；工单列表/详情返回 `detail_json`（无附加内容时为 null）。

> **v1.5 实现补记·三（2026-11-24，附加、非破坏）**：思想汇报录音改为**用户手动控制**——
> 1. `POST /api/sessions`（`kind=report`）省略 `duration_sec`（或传 null）即进入手动录音模式（capture@1.2 补记·二）；显式传值的定时模式保留兼容。
> 2. 新增 `POST /api/sessions/{id}/stop`（用户端 + subject 归属校验）：仅手动模式且 `status=created` 时有效，置位停止事件，返回 `code=0`、`data={session_id}`；重复调用幂等返回成功；会话已 `captured`/`failed`、非手动模式或 `kind=checkin` 时返回 `1005` 状态冲突；不存在 `1004`、越权 `1003`。
> 3. 手动模式下录音仅因用户调用 stop 而结束，服务端不设计时自动终止；录音保存、状态回写（`created → captured/failed`）、轮询与 analyze 流程不变。

---

## 1. 通用约定

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

**HTTP 语义**：所有可预期的业务错误（`1001` / `1002` / `1003` / `1004` / `1005` / `1006` / `2001` / `2003` / `4000`，以及业务占位用的 `5000`，如 `capture_busy`、`analysis_pipeline_not_ready`）一律返回 HTTP 200；只有**未捕获异常**返回 HTTP 500 + `code=5000`。

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
| 1005 | 状态冲突 | 未同意就采集（`consent_revoked` / `consent_required` / `consent_incomplete`）、工单已关闭（`ticket_closed`）、复盘窗口无可用会话（`no_session_in_window`） |
| 1006 | 频率限制 | 同一对象 60 秒内重复建会话 |
| 2001 | 采集失败（无可用产物） | `sessions.status == failed`；`failed` 会话调用分析 |
| 2003 | 分析失败（结果不可用） | `analysis_status=failed`，需重采或人工处理 |
| 4000 | 会话未采集完成 | `sessions.status == created` 时调用分析 |
| 5000 | 内部错误 / 临时占位 | 未捕获异常；分析管线未就绪（`message=analysis_pipeline_not_ready`）；采集并发冲突（`message=capture_busy`，专用错误码待增补） |

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
| `PUT` | `/api/user/consent` | 已实现 | 提交同意（人脸、音频独立勾选） |
| `POST` | `/api/user/consent/revoke` | 已实现 | 撤回同意 |
| `GET` | `/api/user/sessions/{session_id}/feedback` | 已实现 | 中性结果反馈（不含色码） |

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
| `GET` | `/api/admin/tickets/{ticket_id}` | 已实现 | 工单详情（留痕）（见 §7.13） |
| `POST` | `/api/admin/tickets/{ticket_id}/transition` | 已实现 | 工单流转（见 §7.10） |
| `GET` | `/api/admin/dashboard` | 已实现 | 看板数据（见 §7.11） |

## 6. 序列化脱敏规则

| 接口 | 必须剔除 | 说明 |
|---|---|---|
| `GET /api/user/sessions/{id}/feedback` | `final_color`、`risk_level`、`evidence`、`rules_fired`、`transcript`、`face_path` | 用户端不显示色码 |
| 所有用户端接口 | `consent_json` 之外的其他对象字段 | 仅返回必要信息 |
| `GET /api/admin/tickets/{id}` | 无 | 但需写 `audit_logs(sensitive.view)` |
| `GET /api/admin/sessions/{id}/transcript` | 无 | 必须写留痕 |
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

- 分析可用时写回 `analysis_json` / `transcript_path`（ASR 成功时）/ `analysis_status`，再按会话所属自然日窗口生成复盘与工单；分析失败只写 `analysis_status=failed`，**不回写** `sessions.status`；
- `degraded` 按 §2.1 组装（采集降级 + 分析降级）；
- 幂等：`analysis_json` 已存在时复用，不重复跑分析；同一 `(subject_id, window_end)` 的复盘已存在时复用，不重复建单；`review_created=false` 表示复用；
- `ticket_id` 为 `null` 表示未建单（仅「绿 + 不复核 + 非采集降级」会出现）；
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
| `confirm` | — | 工单已 `closed` → `1005`，`message=ticket_closed` |
| `correct` | `conclusion_color`、`note` | 缺字段 → `1001`；已 `closed` → `1005 ticket_closed` |
| `close` | `note` | 缺字段 → `1001`；已 `closed` → `1005 ticket_closed` |

- 单次请求原子落到终态 `closed` 并写 `closed_at`；`confirm` / `correct` 的中间态只体现在 `audit_logs(action=ticket.transition, detail_json.action)`；
- 每次流转写一条 `audit_logs`：`actor_type=staff`、`actor_id=assignee`（可选）、`action=ticket.transition`、`target_type=ticket`、`target_id={ticket_id}`、`detail_json` 含 `action` / `previous_status` / `conclusion_color` / `note`（`note` 为工作人员结论说明，可入审计；禁止写入音频、转写原文、面部图）；
- 工单不存在 → `1004`；非 `staff` → `1003`。

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
- `history` 由 `audit_logs(action=ticket.transition)` 按时间升序组装，并补一条 `opened` / `system` 的建单记录；流转记录的 `actor` 取审计 `actor_id`（即 `assignee`），未提供时回落 `"staff"`；
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
- **可用会话** = `sessions.status = captured` 且 `analysis_status in (done, degraded)`；窗口内 0 条 → `1005`、`message=no_session_in_window`，**不落库、不建单**；
- 有可用会话时，取窗口内 `captured_at` 最新的一条作为 `source_session_id`，执行 `evaluate_session → evaluate_period → compose`；`capture_status in (partial, no_face, no_audio)` 时覆写 `review_reason="capture_degraded"` 后再 `build_ticket`；
- 同一 `(subject_id, window_end)` 已存在复盘时直接返回该复盘（幂等），不重复建单；
- 成功写 `audit_logs(action=review.create, target_type=review, target_id={review_id})`。

## 8. 前端联调 mock

后端未就绪时，前端使用 `web/src/mock/` 下的固定响应：

| 文件 | 覆盖接口 |
|---|---|
| `subject.json` | `/api/admin/subjects*` |
| `session.json` | `/api/sessions*`、`/api/admin/sessions*` |
| `review.json` | `/api/admin/reviews*` |
| `ticket.json` | `/api/admin/tickets*` |
| `dashboard.json` | `/api/admin/dashboard` |

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
| 1.5（实现补记·二） | 2026-11-24 | 双模块：`POST /api/sessions` 增 `kind`；analyze 按 kind 分流；新增 `GET /api/user/tasks`、`PATCH /api/admin/subjects/{id}/frequency`；管理端读取时惰性幂等生成逾期 P0 工单；`retention_days` 可选缺省 180 |
