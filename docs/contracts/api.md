# 契约 · HTTP API（api）

| 项 | 值 |
|---|---|
| 契约版本 | `api@1.1` |
| 所有者 | backend-engineer（`app/api/`） |
| 基础路径 | `/api` |
| 关联 | [db.md](./db.md)、[capture.md](./capture.md)、[analysis.schema.json](./analysis.schema.json)、[ui.md](./ui.md) |

> 本版已冻结，后续仅接受实现驱动的变更。

---

## 1. 通用约定

| 项 | 约定 |
|---|---|
| 编码 | UTF-8，`application/json` |
| 字段命名 | `snake_case`，与数据库一致 |
| 时间 | ISO 8601 带时区 |
| 分页 | query 参数 `page`（从 1 开始）、`page_size`（默认 20，最大 100） |
| 幂等 | `POST /api/session/{id}/analyze` 重复调用返回首次结果 |
| 路径参数 | `{session_id}`、`{subject_id}`、`{ticket_id}`、`{review_id}` 均为 UUID 字符串 |

## 2. 统一响应包

所有接口（含错误）返回同一结构：

```json
{
  "code": 0,
  "message": "ok",
  "data": {},
  "request_id": "req_01HF8Z3K9Q"
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `code` | int | `0` 成功，非 0 见第 3 节 |
| `message` | string | 机器可读短句，不包含个人信息 |
| `data` | object \| array \| null | 业务数据；错误时为 `null` |
| `request_id` | string | 用于日志关联 |

HTTP 状态码与 `code` 同时使用：业务错误返回 4xx 但 **`code` 才是判定依据**；未捕获异常统一 500 + `code=5000`。

**唯一例外**：`GET /api/session/{session_id}/face` 成功时直接返回 `image/jpeg` 二进制（不走信封）；鉴权失败、留痕失败等错误情况仍返回上述 JSON 信封。

## 3. 错误码

| code | HTTP | 含义 | 典型场景 |
|---|---|---|---|
| 0 | 200 | 成功 | — |
| 1001 | 400 | 参数错误 | 缺字段、类型不符、枚举越界 |
| 1002 | 401 | 未认证 | 缺 token 或 token 无效 |
| 1003 | 403 | 无权限 | 用户端 token 访问管理端接口 |
| 1004 | 404 | 资源不存在 | session / ticket 不存在 |
| 1005 | 409 | 状态冲突 | 未同意就采集、未采集就分析、工单已关闭 |
| 1006 | 429 | 频率限制 | 同一对象 60 秒内重复建会话 |
| 2001 | 200 | 采集失败（无可用产物） | `sessions.status == failed`，业务仍返回 200 |
| 2002 | 200 | 分析降级 | `analysis_status=degraded`，结果可用 |
| 5000 | 500 | 内部错误 | 未捕获异常，`data=null` |

> `2001` / `2002` 不视为 HTTP 错误，前端依据 `code` 决定展示哪种提示。
> `partial` / `no_face` / `no_audio` 返回 `code=0` 且 `degraded=true`；只有 `sessions.status == failed` 才返回 `2001`。

## 4. 鉴权

```
Authorization: Bearer <token>
```

| 角色 | token 前缀 | 说明 |
|---|---|---|
| `subject` | `user_` | 用户端，仅能访问 `/api/me/*` 与本人 `session` |
| `staff` | `admin_` | 管理端，可访问全部 `/api/*` |

规则：

- 用户端接口访问**他人** `subject_id` 返回 `1003`；
- 管理端接口一律要求 `role=staff`；
- 原型为静态令牌，值从 `AUTH_USER_TOKEN` / `AUTH_ADMIN_TOKEN` 读取；
- 缺失或格式错误返回 `1002`。

## 5. 端点清单

### 5.1 用户端（`subject`）

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/me/consent` | 查询本人同意状态 |
| `PUT` | `/api/me/consent` | 提交同意（人脸、音频独立勾选） |
| `POST` | `/api/me/consent/revoke` | 撤回同意 |
| `POST` | `/api/session` | 发起一次采集 |
| `GET` | `/api/session/{session_id}` | 查询本人会话状态 |
| `GET` | `/api/session/{session_id}/feedback` | 获取中性结果反馈（不含色码） |

### 5.2 管理端（`staff`）

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/subjects` | 对象列表（分页、关键词、状态） |
| `POST` | `/api/subjects` | 新建对象 |
| `GET` | `/api/subjects/{subject_id}` | 对象详情（含当前色码与证据摘要） |
| `PATCH` | `/api/subjects/{subject_id}` | 更新对象基础信息 |
| `GET` | `/api/subjects/{subject_id}/sessions` | 对象会话时间线 |
| `POST` | `/api/session/{session_id}/analyze` | 触发四路分析 + 分级 + 建单 |
| `GET` | `/api/session/{session_id}/transcript` | 查看转写原文（敏感，留痕） |
| `GET` | `/api/session/{session_id}/face` | 查看面部图（敏感，留痕） |
| `POST` | `/api/reviews` | 按窗口计算复盘 |
| `GET` | `/api/reviews` | 复盘列表（按对象、色码、时间） |
| `GET` | `/api/reviews/{review_id}` | 复盘详情（含证据链） |
| `GET` | `/api/tickets` | 复核队列 |
| `GET` | `/api/tickets/{ticket_id}` | 工单详情（留痕） |
| `POST` | `/api/tickets/{ticket_id}/transition` | 工单流转 |
| `GET` | `/api/dashboard` | 看板数据（色码分布、7 日趋势、待复核数） |

## 6. 序列化脱敏规则

| 接口 | 必须剔除 | 说明 |
|---|---|---|
| `GET /api/session/{id}/feedback` | `final_color`、`risk_level`、`evidence`、`rules_fired`、`transcript`、`face_path` | 用户端不显示色码 |
| 所有用户端接口 | `consent_json` 之外的其他对象字段 | 仅返回必要信息 |
| `GET /api/tickets/{id}` | 无 | 但需写 `audit_logs(sensitive.view)` |
| `GET /api/session/{id}/transcript` | 无 | 必须写留痕 |
| 全局日志 | 音频内容、转写原文、面部图 base64 | 红线 |

`feedback` 只允许返回：`status`、`summary_text`（中性表述）、`suggestion`（枚举）、`next_action`。

## 7. 端点详情

### 7.1 `PUT /api/me/consent`

```bash
curl -X PUT http://localhost:8000/api/me/consent \
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
  "request_id": "req_01HF8Z3K9Q"
}
```

### 7.2 `POST /api/session`

同步执行采集，最长阻塞 `CAPTURE_TIMEOUT_SEC`。

```bash
curl -X POST http://localhost:8000/api/session \
  -H "Authorization: Bearer user_demo" \
  -H "Content-Type: application/json" \
  -d '{
    "subject_id": "3b1e7c90-2f4a-4d51-8c6b-7d9e0f1a2b3c",
    "device_index": 0,
    "duration_sec": 30
  }'
```

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "session_id": "8f3c1b2e-4a5d-4c6e-9f10-1a2b3c4d5e6f",
    "subject_id": "3b1e7c90-2f4a-4d51-8c6b-7d9e0f1a2b3c",
    "status": "captured",
    "capture_status": "ok",
    "captured_at": "2026-11-23T10:12:36+08:00",
    "duration_sec": 30.0,
    "face_available": true,
    "audio_available": true,
    "codes": []
  },
  "request_id": "req_01HF8Z4A1B"
}
```

采集降级（`sessions.status=captured`，`capture_status in (partial, no_face, no_audio)`）：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "session_id": "8f3c1b2e-4a5d-4c6e-9f10-1a2b3c4d5e6f",
    "status": "captured",
    "capture_status": "partial",
    "degraded": true,
    "face_available": false,
    "audio_available": true,
    "codes": ["detector_unavailable"]
  },
  "request_id": "req_01HF8Z4A1B"
}
```

采集失败（`sessions.status=failed`）：

```json
{
  "code": 2001,
  "message": "capture_failed",
  "data": {
    "session_id": "8f3c1b2e-4a5d-4c6e-9f10-1a2b3c4d5e6f",
    "status": "failed",
    "capture_status": "error",
    "degraded": false,
    "face_available": false,
    "audio_available": false,
    "codes": ["camera_unavailable"]
  },
  "request_id": "req_01HF8Z4A1B"
}
```

前置校验：

| 条件 | 失败返回 |
|---|---|
| `consent.general.granted != true` | `1005`，`message=consent_required` |
| `face=true` 但 `audio=false` 且本次请求有 `duration_sec` | 允许，仅采集人脸 |
| `revoked_at != null` | `1005`，`message=consent_revoked` |
| 60 秒内重复请求 | `1006` |

### 7.3 `POST /api/session/{session_id}/analyze`

```bash
curl -X POST http://localhost:8000/api/session/8f3c1b2e-4a5d-4c6e-9f10-1a2b3c4d5e6f/analyze \
  -H "Authorization: Bearer admin_demo"
```

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "session_id": "8f3c1b2e-4a5d-4c6e-9f10-1a2b3c4d5e6f",
    "analysis_status": "ok",
    "consistency": "medium",
    "needs_review": false,
    "degraded": false,
    "analysis": { "schema_version": "1.0", "channels": { "...": "..." } },
    "review": {
      "review_id": "c41d0a77-9b2e-4f83-a1c5-6d7e8f9a0b1c",
      "single_session_risk": "none",
      "trend_color": "blue",
      "final_color": "blue",
      "manual_review": false,
      "rules_fired": ["R_TREND_BLUE"]
    },
    "ticket": {
      "ticket_id": "5e2f9b11-3c4d-4a6b-8e7f-0a1b2c3d4e5f",
      "status": "pending",
      "priority": "P2"
    }
  },
  "request_id": "req_01HF8Z5C2D"
}
```

- `session.status != captured` → `1005`；
- 重复调用返回首次结果，不重复建单；
- 绿结果时 `ticket` 为 `null`；**例外**：`degraded=true` 且最终色为绿时按 `R_DEGRADED_REVIEW` 建 `P1` 单（见 [../grading.md](../grading.md#6-复核触发条件)）；若会话为采集 `partial` / 单模态，按规则 8 取 `P0`。

### 7.4 `GET /api/session/{session_id}/feedback`（用户端）

```bash
curl http://localhost:8000/api/session/8f3c1b2e-4a5d-4c6e-9f10-1a2b3c4d5e6f/feedback \
  -H "Authorization: Bearer user_demo"
```

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "session_id": "8f3c1b2e-4a5d-4c6e-9f10-1a2b3c4d5e6f",
    "status": "analyzed",
    "summary_text": "本次记录已完成。",
    "suggestion": "keep_routine",
    "next_action": "下次按约定时间再来即可"
  },
  "request_id": "req_01HF8Z6D3E"
}
```

`suggestion` 枚举：`keep_routine` / `talk_to_staff` / `recapture`。
**不得出现**色码、规则编号、分数、诊断词。

### 7.5 `GET /api/subjects`（管理端）

```bash
curl "http://localhost:8000/api/subjects?keyword=S001&status=active&page=1&page_size=20" \
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
        "latest_color": "blue",
        "latest_color_at": "2026-11-23T10:13:00+08:00",
        "latest_rules": ["R_TREND_BLUE"],
        "pending_tickets": 1,
        "latest_session_at": "2026-11-23T10:12:36+08:00"
      }
    ],
    "page": 1,
    "page_size": 20,
    "total": 1
  },
  "request_id": "req_01HF8Z7E4F"
}
```

`latest_color` 必须同时返回 `latest_color_at` 与 `latest_rules`；前端渲染色码时必须并列展示规则与证据入口，不允许只渲染颜色块。

### 7.6 `GET /api/reviews/{review_id}`

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "review_id": "c41d0a77-9b2e-4f83-a1c5-6d7e8f9a0b1c",
    "subject_id": "3b1e7c90-2f4a-4d51-8c6b-7d9e0f1a2b3c",
    "window_start": "2026-11-17T00:00:00+08:00",
    "window_end": "2026-11-23T23:59:59+08:00",
    "window_days": 7,
    "single_session_risk": "none",
    "trend_color": "blue",
    "final_color": "blue",
    "consistency": "medium",
    "manual_review": false,
    "rules_fired": ["R_TREND_BLUE"],
    "grading_version": "grading@1.1",
    "evidence": [
      {
        "rule_id": "R_TREND_BLUE",
        "rule_version": "grading@1.1",
        "field_path": "psych.output.signal_strength",
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
  "request_id": "req_01HF8Z8F5G"
}
```

### 7.7 `POST /api/tickets/{ticket_id}/transition`

```bash
curl -X POST http://localhost:8000/api/tickets/5e2f9b11-3c4d-4a6b-8e7f-0a1b2c3d4e5f/transition \
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
  "request_id": "req_01HF8Z9G6H"
}
```

校验：

| 动作 | 必填 | 失败返回 |
|---|---|---|
| `confirm` | — | 工单非 `pending` → `1005` |
| `correct` | `conclusion_color`、`note` | 缺字段 → `1001` |
| `close` | `note` | 缺字段 → `1001` |

### 7.8 `GET /api/dashboard`

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
  "request_id": "req_01HF8ZAH7J"
}
```

> 看板按**单对象**聚合。不提供跨对象排行、榜单类字段。

## 8. 前端联调 mock

后端未就绪时，前端使用 `web/src/mock/` 下的固定响应：

| 文件 | 覆盖接口 |
|---|---|
| `subject.json` | `/api/subjects*` |
| `session.json` | `/api/session*` |
| `review.json` | `/api/reviews*` |
| `ticket.json` | `/api/tickets*` |
| `dashboard.json` | `/api/dashboard` |

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
