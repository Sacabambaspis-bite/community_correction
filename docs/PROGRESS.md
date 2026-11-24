# 项目进度（PROGRESS）

> 生成时间：2026-11-24 · 基准提交：`7782e65`（`main` 领先 `origin/main` 1 个提交）+ 本轮未提交变更 · 依据：`git log`、`git tag`、`pytest` 实测、[QA 报告](./reports/qa-2026-11-24.md)。
> 本文只记录仓库里可核实的事实；尚未实现或未定稿的内容标注「待确认」。

## 1. 项目定位与技术栈

**一句话**：社区矫正场景的单对象纵向切片原型——把一次采集（人脸 + 语音）转成结构化信号，经四路分析与五色分级，**分级结果唯一出口是人工复核工单**，系统自身不产生处置动作（[prd.md](./prd.md#L20)）。

| 层 | 选型 | 现状 |
|---|---|---|
| 运行时 | Python 3.11 | 已用（本机 3.11.0rc2） |
| 采集 | OpenCV / MediaPipe / sounddevice | 已实现并硬件验证，封存于 `capture-v1` |
| Web 框架 | FastAPI 0.165.0 + uvicorn 0.54.0 | 骨架 + 用户端 / consent / analyze 接入（`api-v1` → `api@1.5` 实现补记） |
| ORM / 数据库 | SQLAlchemy 2.x（原型阶段手工迁移）/ SQLite | 5 张表已实现（`db-v1`）；本机实际 2.1.9，`requirements` 已锁 `<2.1` |
| 分析 | Provider 抽象 + 确定性 mock | 四路 mock 已实现；`overall.risk_level` 已接 `app.grading.config.map_risk_level`（本轮），真模型未接 |
| 分级 | 五色纯函数规则 + 七日趋势 + 工单草案 | 已实现并接入 analyze / 复盘 / 工单接口（本轮） |
| Schema 校验 | jsonschema（Draft 2020-12 + FormatChecker） | 已引入，分析结果强制校验 |
| 前端 | React + Vite（用户端 / 管理端同仓，按路由分区） | 用户端 3 页 + 管理端 4 页骨架已实现（`601d33d`），联调仍走 mock |
| 测试 | pytest | 224 条全绿（capture 6 / db 13 / api 42 / analysis 55 / grading 108） |

技术栈来源：[architecture.md](./architecture.md#L11-L21)；采集运行在后端宿主设备而非浏览器（[architecture.md](./architecture.md#L23-L31)）。

## 2. 已完成模块与对应标签

| 对象 | 状态 | 标签 / 提交 |
|---|---|---|
| 契约文档 capture@1.2 / grading@1.2 / ui@1.2 | 已冻结 | `contracts-v1.2` → `8698a26` |
| 契约文档 db@1.3 + api@1.3 | 已冻结 | `contracts-v1.3` → `ddd4968` |
| 契约文档 db@1.4 + api@1.4 | 已冻结 | 无独立标签，随 `96aa098` |
| `app/capture/` 采集模块（抓拍 / 人脸检测裁剪 / 录音 / 会话打包） | 已实现，已封存 | `capture-v1` → `55c9a25` |
| `tests/test_capture/`（6 条，全部 mock 设备） | 全绿 | 包含在 `787ee0e` |
| `scripts/verify_capture.py`、`scripts/hw_check.py` | 已实现 | 包含在 `55c9a25` |
| 真实硬件端到端验证 | 已通过 | `ok` / `both` 一次；另有 `no_audio`、`no_face_no_audio` 历史结果 |
| `app/db/` 五张表 + 派生 `coverage` + 服务端默认值 | 已实现 | `db-v1` → `bc83a3e` |
| `app/api/` 骨架（信封 / 鉴权 / 异步采集 / 2001/2003） | 已实现 | `api-v1` → `79e582d` |
| 契约文档 api@1.5（用户端 / consent / 会话归属） | 已冻结 | `4f5d1bf` |
| `app/api/` 用户端端点、consent 三闸、会话归属校验 | 已实现 | `4f5d1bf` |
| `app/analysis/` 四路 mock、Schema 校验、一致性判定 | 已实现（未打标签） | `81a8499` |
| `tests/test_analysis/`（55 条） | 全绿 | `81a8499` |
| `app/grading/` 五色规则、七日趋势偏移、合成封顶、工单草案 | 已实现并接入 API（本轮；未打标签） | `67adee6` + 本轮 |
| `tests/test_grading/`（108 条） | 全绿 | `67adee6` + 本轮 |
| `web/` 用户端 3 页 + 管理端 4 页骨架（mock 联调） | 已实现 | `601d33d` |
| analyze 正式接入 + 复盘 / 工单 / 看板端点 | 已实现（本轮未提交） | 工作区 |
| `map_risk_level` wiring + 低一致性 P0 修复 | 已实现（本轮未提交） | 工作区 |
| 远程仓库 | `main` 领先 `origin/main` 1 个提交 | `origin/main` @ `337fdb9` |
| `scripts/seed_demo.py` 演示数据（含占位素材） | 已实现 | `0bb78b5` |
| QA 核验 + M1–M4/L4/L8 修复 | 已完成 | `638245e`（报告）、`7732930`（修复） |

提交历史（近 16 条）：

```
337fdb9  docs(grading): sync contract with implementation (review_reason, map_risk_level, cap semantics)
67adee6  feat(grading): implement 5-color rules, trend analysis and ticket builder
4f5d1bf  feat(api): user endpoints, consent gates, session ownership (api@1.5)
81a8499  feat(analysis): deterministic four-channel mock pipeline + schema/consistency
9b2a04d  docs: refresh PROGRESS snapshot; fix agents README (5 tables, /api/sessions, tests/test_db)
43d3aba  chore(agents): align analysis/grading instructions with contracts
7732930  fix(qa): M1-M4/L4/L8 - pin SQLAlchemy<2.1, FK test pragma, safe logs, injectable session factory
638245e  docs: QA report 2026-11-24 + db coverage derived note + window_days default
0bb78b5  chore(seed): demo dataset (6 subjects, 42 sessions, 6 reviews, 3 tickets) + placeholder assets
79e582d  feat(api): skeleton with async capture, envelope, auth, degraded                    [api-v1]
96aa098  docs+db: contracts db@1.4/api@1.4, JSON NULL checks, 2003 branch
bc83a3e  feat(db): five tables + derived coverage + server defaults; docs db@1.3              [db-v1]
ddd4968  docs: contracts v1.3 (db defaults + reviews window unique + api created gate)       [contracts-v1.3]
492c764  docs: add PROGRESS snapshot (repo-state based)
55c9a25  feat(capture): verified on real hardware (ok/both); prefer DirectShow, 16k audio    [capture-v1]
787ee0e  feat(capture): align to contract state machine (coverage/warnings/optional crop) + tests
```

**尚未实现**：复盘列表 `GET /api/admin/reviews`、60 秒频控（`1006`）、转写查看、`GET /api/admin/subjects/{id}`。`web/` 骨架已实现（`601d33d`）；`app/api/` 的 analyze / review / tickets / dashboard 已接入（本轮）；`app/capture/` 已封存，`app/db/`、`app/api/`、`app/analysis/` mock 与 `app/grading/` 分级规则均已实现。

采集模块已落地的契约要点：

- 六值 `capture_status`：`ok` / `partial` / `no_face` / `no_audio` / `no_face_no_audio` / `error`；
- `coverage`：`both` / `face_only` / `audio_only`，失败态为 `null`；
- `meta.warnings[]` 承载非致命原因，`meta.error` 仅在 `error` 时非空；
- 人脸检测顺序 MediaPipe → OpenCV DNN → Haar；裁剪外扩 25%、JPEG 质量 85；
- 目录固定为 `storage/subjects/{subject_id}/sessions/{session_id}/`，原始帧不落盘。

数据层、分析层与 API 已落地的要点：

- 五张表：`subjects` / `sessions` / `reviews` / `review_tickets` / `audit_logs`，字段、CHECK、索引与 db@1.4 一致；
- `sessions.coverage` 为派生属性，不落列；`analysis_status`、`gender`、`status`、`window_days` 有服务端默认值；
- `reviews` 唯一约束 `UNIQUE(subject_id, window_end)`；JSON 列统一 `IS NULL OR json_valid(...)`；
- 统一信封 `{code, message, data, degraded, request_id}`，业务错误一律 HTTP 200，未捕获异常 HTTP 500 + `code=5000`；
- 已实现：`GET /api/health`、`POST/GET /api/sessions`、`GET /api/admin/subjects|sessions`、`GET /api/admin/sessions/{id}/face`（写 `audit_logs`）；
- 已实现用户端：`GET/PUT /api/user/consent`、`POST /api/user/consent/revoke`、`GET /api/user/sessions/{id}/feedback`；`POST /api/sessions` 前置 consent 三闸（`consent_revoked` → `consent_required` → `consent_incomplete`）；
- 会话归属校验：`subject` 调用 `GET /api/sessions/{id}` 与 feedback 时必须带 `subject_id`，缺失 `1001`、不匹配 `1003`；
- `POST /api/sessions/{id}/analyze` 已正式接入（本轮）：`captured` 跑四路分析并落 `analysis_json` / `transcript_path` / `analysis_status`，再按自然日窗口生成 `reviews` / `review_tickets`；分析彻底失败 `2003` 且不改 `sessions.status`；重复调用幂等；
- 新增管理端端点（本轮）：`POST /api/admin/reviews`（0 可用会话 → `1005 no_session_in_window`）、`GET /api/admin/reviews/{id}`、`GET /api/admin/tickets`、`GET /api/admin/tickets/{id}`（写 `sensitive.view`）、`POST /api/admin/tickets/{id}/transition`、`GET /api/admin/dashboard`（`subject_id` 可选，缺省取最近采集对象）。

分析模块（`app/analysis/`，全部 mock）已落地的要点：

- 四路 Provider：`mock-asr@1.0` / `mock-emotion@1.0` / `mock-face@1.0` / `mock-psych@1.0`，场景 `normal` / `negative` / `crisis` / `conflict` 确定性输出；
- ASR 生成会话内 `transcript.txt`，结果只存规范相对路径，不返回原文；
- 运行状态与结果分离：`AnalysisRunResult.analysis_status` 为 `done/degraded/failed`，纯 `AnalysisResult` 不含该字段；
- 通道级与完整 JSON Schema 校验（Draft 2020-12 + `FormatChecker`），失败不得进入 grading；
- 单路 `unavailable` → `skipped`，单路异常或非法输出 → `degraded`，互不影响；ASR 失败时 psych 为 `skipped`；四路均无可用输出 → `failed` 且 `result=None`；
- 一致性：单模态、`partial`（即使 `coverage=both`）、方向冲突、低置信均强制 `low + needs_review=true`；`degraded` 时最高 `medium`。

分级模块（`app/grading/`，纯函数，不读写库/文件/网络）已落地的要点：

- 目录结构按 grading@1.2 契约：`config` / `models` / `single` / `trend` / `compose` / `ticket`，编排顺序 `evaluate_session → evaluate_period → compose → build_ticket`；
- 单次规则：`R_SINGLE_RED`（`intent_flag=suicide_intent` 直接红；`self_harm_mention` 且 `signal_strength>=80` 红，红不受一致性封顶）、`R_SINGLE_ORANGE`（`signal>=70` 且非自杀意图，附 emotion/face 辅助佐证证据）；
- 趋势规则：`offset_score=(window_mean - baseline_mean)/max(std, BASELINE_MIN_STD)`，`R_TREND_YELLOW/BLUE/GREEN` 边界 `1.5/0.8`，基线或窗口不足走 `R_BASELINE_INSUFFICIENT` 判蓝并在证据标 `insufficient`、`offset_score` 置 0；窗口按自然日可跨月；
- 合成：取大 → `R_CONSISTENCY_CAP`（low 封顶橙，红豁免；**绿+low 抬至橙**强制复核）→ `manual_review` → `R_DEGRADED_REVIEW` 标 `needs_review`（不改色）；
- 工单草案：`build_ticket` 只返回 dict（无 DB/通知/处置动作）；绿且不复核抛 `ticket_not_allowed_for_green`；色码→`priority`/`suggested_method`，`due_at` 按 P0/P1/P2 加 24/72/168h，幂等；`manual_review=true`（低一致性）覆写 `priority=P0`、方法按最终色；`capture_degraded` 覆写 P0 + `recapture`；
- 历史遗留 `risk_level` 映射：`config.map_risk_level(text_valence, intent_flag)` 先按 `text_valence` 分段（`[-0.8,-0.5,-0.2,0.0]`→crisis/high/elevated/watch/none），`intent_flag∈{suicide_intent,self_harm_mention}` 强制覆写 `crisis`；**已 wiring 进 `app/analysis/pipeline.py`**（本轮，`pending` 占位已删除）；
- 阈值唯一来源 `config.py`（15 项均标 `# TODO: 待标定`），`tests/test_grading/test_config.py` 源码扫描保证规则模块无字面量泄漏。

## 3. 关键决策与理由

| 决策 | 落地位置 | 理由 |
|---|---|---|
| **DirectShow 优先**（Windows 下先 `cv2.CAP_DSHOW`，失败回退默认后端） | `app/capture/camera.py`，提交 `55c9a25` | 本机实测：默认 MSMF 帧连续多次检不出人脸，同一设备 DSHOW 帧可检出；回退设计保证非 Windows 与打不开场景行为不变 |
| **裁剪输出固定 300×300**（`OUTPUT_SIDE = 300`） | [config.py](../app/capture/config.py#L61)、capture@1.2 §5.1 | 统一下游输入尺寸；`meta.face.output_size` 恒为 `[300, 300]` |
| **音频 16 kHz / 单声道 / 16-bit** | [audio.py](../app/capture/audio.py#L22-L27)、architecture §存储 | 语音链路足够、体积小；`speech_ratio` 阈值 0.05 |
| **error 判级规则** | capture@1.2 §3 | 零产物 + 设备/技术级 code → `error`；零产物 + 全业务级 code → `no_face_no_audio`；任一路有产物 → `partial` 或单模态 |
| **`sessions.status` 与 `analysis_status` 拆分** | db@1.2 §3.1 | `status` 只反映采集；分析状态独立，分析失败不回写 `failed` |
| **`degraded` 为字符串数组** | api@1.2 §7.2 | 区分采集与分析降级；新增 `2003`，废弃 `2002` |
| **原型阶段手工迁移，不引 Alembic** | db@1.3 头部 / §9、[migrations/README](../app/db/migrations/README.md) | 当前只有空库初始化；正式部署前再引入 Alembic，避免过早引入迁移工具 |
| **`coverage` 派生、不落列** | db@1.4 §3、[models.py](../app/db/models.py) | 避免路径与字段双写不一致；唯一来源是 `face_path` / `audio_path` |
| **JSON 列允许 NULL，但非 NULL 必须合法** | db@1.4 §4、提交 `96aa098` | `json_valid(NULL)` 返回 NULL 会误伤可空列，改为 `IS NULL OR json_valid(...)` |
| **`reviews` 窗口唯一** | db@1.4 §4 | 防止同一复盘窗口重复生成，幂等重跑更安全 |
| **服务端默认值下沉到 DDL** | db@1.4 §3/§4、`models.py` | `analysis_status=pending`、`gender=unknown`、`status=active`、`window_days=7`，非 ORM 写入也成立 |
| **统一信封 + `request_id`** | api@1.4 §2、[errors.py](../app/api/errors.py)、[main.py](../app/api/main.py) | 中间件生成 uuid4，写 `X-Request-Id`、日志与 `audit_logs`；便于串联一次请求 |
| **异常日志不写异常原文** | api@1.4 §2、[errors.py](../app/api/errors.py) | 只记 `request_id/exception_type/endpoint`，避免绝对路径或 SQL 参数进日志；`DEBUG=1` 才把堆栈打到 stdout |
| **后台采集可注入 + `CAPTURE_FAKE`** | [sessions.py](../app/api/routers/sessions.py)、[deps.py](../app/api/deps.py) | 测试不触真实摄像头；session factory 可替换，后台任务可观测 |
| **SQLAlchemy 临时锁 `<2.1`** | [requirements.txt](../requirements.txt)、[migrations/README](../app/db/migrations/README.md) | 2.1.x 开启外键时多表同事务 flush 顺序错误（QA M1）；seed 的逐表 flush 作为双保险 |
| **分析全走 mock Provider** | [prd.md](./prd.md#L33) | 本轮先跑通链路与契约，不引入模型不确定性 |
| **分析运行状态与结果分离** | [models.py](../app/analysis/models.py)、[pipeline.py](../app/analysis/pipeline.py) | `AnalysisResult` 严格对齐 schema；`done/degraded/failed` 放在独立包装层，失败不产出可进入 grading 的结果 |
| **`risk_level` 映射落在 grading config 并已 wiring** | [config.py](../app/grading/config.py) `map_risk_level`、[pipeline.py](../app/analysis/pipeline.py) | 按 `text_valence` 分段 + 明确意图覆写 `crisis`；本轮删除 `pending` 占位，pipeline 直接调用 `map_risk_level` |
| **一致性阈值权威值在 grading** | [config.py](../app/grading/config.py) `CONSISTENCY_MIN_CONFIDENCE` | grading 侧已定义 0.6；`app/analysis/config.py` 仍用本地常量，迁移时机待定 |
| **分级为纯函数、只出口工单草案** | `app/grading/*`（`build_ticket` 只返回 dict） | 不读写库/文件/网络，不产生处置动作；色码不进入用户端路径 |
| **`review_reason` 承载规则 8 覆写** | [models.py](../app/grading/models.py)、[ticket.py](../app/grading/ticket.py) | `compose` 签名不增参；`AnalysisResult` 不含 `capture_status`，由 backend 用 `replace(..., review_reason="capture_degraded")` 覆写后建 P0+recapture 单 |
| **低一致性 P0 由 `manual_review` 驱动** | [ticket.py](../app/grading/ticket.py) | 规则 5 与色码无关；`review_reason="consistency_conflict"` 只描述原因，不改档位 |
| **复盘窗口按自然日、DB 存 `YYYY-MM-DD`** | [integration.py](../app/api/integration.py)、db@1.4 §4 | 与 grading 证据 `window` 一致；同日多会话共用一个 `window_end`，靠 `UNIQUE(subject_id, window_end)` 幂等 |
| **0 可用会话在上游拦截** | [admin.py](../app/api/routers/admin.py) `POST /api/admin/reviews` | 「可用会话」= `captured` + `analysis_status∈{done,degraded}`；0 条直接 `1005`，不落库、不建单 |
| **analyze 同步完成分析 + 分级** | [sessions.py](../app/api/routers/sessions.py)、[integration.py](../app/api/integration.py) | 原型阶段 mock 分析耗时可接受；省去后台任务与轮询复杂度，失败只用 `analysis_status=failed` 表达 |

## 4. 当前未完成项与阻塞

**未完成（按目录）**

| 目录 | 内容 | 状态 |
|---|---|---|
| `app/analysis/` | 四路 mock、Schema 校验、一致性判定 | 已实现；真模型待接；`risk_level` 已 wiring `map_risk_level`（本轮） |
| `app/grading/` | 五色规则、七日趋势偏移、合成封顶、工单草案 | 已实现并接入 API（本轮）；低一致性 P0 已补 |
| `app/api/` | analyze / reviews / tickets / dashboard | 已接入（本轮）；余项见下 |
| `web/` | 用户端 3 页 + 管理端 4 页 | 骨架已实现（`601d33d`），待与真实 API 联调 |

**API 剩余延期项**

- 复盘列表 `GET /api/admin/reviews`；
- `GET /api/admin/subjects/{subject_id}` 与 `GET /api/admin/sessions/{id}/transcript`（管理端敏感面板）；
- 60 秒重复建会话频控（`1006`）；
- `capture_busy` 专用业务码（当前复用 `code=5000`）。

已补齐（`4f5d1bf`）：`/api/user/*` 全部端点、`POST /api/sessions` 的 consent 三闸、`subject` 会话归属校验。

**演示数据说明**

- `scripts/seed_demo.py` 生成 6 subjects / 42 sessions / 6 reviews / 3 tickets / 4 audit_logs，颜色（2 绿、1 蓝、1 黄、1 橙、1 红）与工单均为**手工指定**，未调用 `app/grading/`，脚本内无阈值判断；
- `face.jpg` 为 300×300 灰底 + 几何剪影 + `placeholder` 的占位素材，`transcript.txt` 为一行占位文本；二者非真实采集，不得用于效果评估或对外宣称；
- 既有个别真实采集产物（`storage/subjects/3b1e7c90-...`）保留，seed 不覆盖已存在文件。

**阻塞 / 风险**

1. **本机 SQLAlchemy 仍是 2.1.9**：`requirements` 已锁 `<2.1`，但环境未重装；约束测试通过显式 `codes` 绕开其 `RETURNING` 包装差异，重装后应消失。
2. **`CAPTURE_FAKE` 无环境守卫**：生产误设会跳过真实采集（只写路径、不落文件），后续应限定 `APP_ENV != production`。
3. **`window_days` 默认值只影响新建表**：reviews 端点落地前需重建 `storage/app.db`（当前库已按 db@1.4 重建过一次）。
4. **500 响应缺 CORS 头**：未捕获异常由最外层 `ServerErrorMiddleware` 处理，浏览器跨域读不到该信封；`X-Request-Id` 与 `request_id` 仍在。
5. **麦克风音量**：本机默认输入曾长期近乎静音（峰值 7/32768、`speech_ratio=0`），最后一次正式验证为 `ok`（`speech_ratio=0.3153`），现场部署前需复核设备与增益。
6. **真实模型未接**：四路均为确定性 mock，Provider 选型与降级策略未定 —— 待确认。
7. **`risk_level` 已 wiring**：`generate_overall_risk_level(text_valence, intent_flag)` 直接返回 `map_risk_level`；阈值仍全部 `# TODO: 待标定`，正式上线前需业务确认。
8. **部署需安装新依赖**：`requirements.txt` 已加入 `jsonschema[format]>=4.23,<5`，本地已安装，其他环境需重新安装。
9. **文档漂移**：[architecture.md](./architecture.md#L53) 的存储路径仍是 `storage/{subject_id}/{session_id}/`，与 capture@1.2 不一致。
10. **`capture_busy` 暂复用 `code=5000`**（`message=capture_busy`），尚无专用业务码。
11. **契约已同步（2026-11-24）**：`grading.md` 补记规则 5 P0、复盘前提、工单主键归属与覆写顺序；`api.md` 补记 analyze / reviews / tickets / dashboard、窗口 `YYYY-MM-DD`、`1005 no_session_in_window`、consent 强校验；`ui.md` §3.1 统一两项齐备；`db.md` 补窗口格式与 0 会话不落库。版本号均保持不变（附加、非破坏）。
12. **管理端前端仍用 mock**：`web/src/api/*` 已按契约声明端点，但 `AdminDashboard` 等页面尚未切真实 API；用户端 consent 按钮门禁需按 ui@1.2 补记调整为「两项齐备才可开始」。
13. **analyze 为同步长请求**：mock 下可接受；接真模型后需评估超时或改后台任务，并复用 `deps.get_session_factory()` 注入。

## 5. 下一步顺序（建议）

1. **fe-user / fe-admin**：把 `web/src/api/*` 从 mock 切到真实端点；用户端 consent 主按钮改为「两项齐备才可开始」，管理端接 `tickets` / `dashboard` / `reviews`。
2. **backend-engineer（余项）**：60 秒频控 `1006`、`capture_busy` 专用码、`GET /api/admin/reviews` 列表、转写查看与 `GET /api/admin/subjects/{id}`。
3. **qa-guard + privacy-check**：每轮合并前跑 qa-guard；本轮新增 analyze/reviews/tickets 端点涉及心理与工单数据，合并前过 privacy-check。

## 6. 三条红线

1. **原图不落盘**：只保留裁剪后的 `face.jpg`，原始帧不落盘、不写日志、不进异常 `detail`（[prd.md](./prd.md#L82)、capture@1.2 §8.1）。
2. **分级只出口复核工单**：任何非绿结果只生成工单，系统不得产生限制、通报、扣分等动作（[grading.md](./grading.md#L20)）。
3. **色码只在管理端**：用户端响应与页面不出现 `final_color` 及任何色码字段，只输出行为建议（[grading.md](./grading.md#L39)、[prd.md](./prd.md#L94)）。

## 7. 目录所有权（subagent 可写范围）

| Subagent | 可写目录 |
|---|---|
| capture-engineer | `app/capture/`、`tests/test_capture/` |
| analysis-engineer | `app/analysis/`、`tests/test_analysis/` |
| grading-engineer | `app/grading/`、`tests/test_grading/` |
| backend-engineer | `app/api/`、`app/db/`、`tests/test_api/`、`tests/test_db/` |
| fe-user | `web/src/user/`（另可新增 `web/src/components/common/` 通用展示组件） |
| fe-admin | `web/src/admin/` |
| qa-guard | `tests/`、`docs/reports/` |
| privacy-check | 无（只读） |

补充：`docs/` 只允许主智能体修改；`scripts/` 归属待确认。

## 8. 环境与验证命令（当前机器）

```
Python 3.11.0rc2 · cv2 4.11.0 · numpy 1.26.4 · sounddevice 0.5.6 · mediapipe 0.10.21
SQLAlchemy 2.1.9（requirements 锁 <2.1）· FastAPI 0.165.0 · uvicorn 0.54.0 · pydantic 2.14.4 · pytest 9.2.0
jsonschema 4.26.0（含 format 校验依赖）
```

```powershell
pytest tests -q                                                      # 224 passed
python -m app.db.init                                                # 建库（幂等）
uvicorn app.api.main:app --port 8000                                 # /docs 可访问
python scripts\seed_demo.py                                          # 演示数据（幂等；--reset 清空后重建）
python scripts\verify_capture.py --device 0 --seconds 10             # 正式验证 → storage/subjects
python scripts\verify_capture.py --device 0 --seconds 5 --out storage/_debug   # 调试/自检
git push origin main                                                 # 远程为 ssh.github.com:443（22 端口被阻断）
```

测试构成：`tests/test_capture/` 6 条、`tests/test_db/` 13 条（含 3 条约束负例）、`tests/test_api/` 42 条（含用户端 / consent / 归属 / 假采集 / 失败 / 并发 / 生产守卫 / analyze 接入 / 复盘 / 工单 / 看板）、`tests/test_analysis/` 55 条（含场景、单模态、降级隔离、Schema、一致性、确定性与隐私）、`tests/test_grading/` 108 条（单次/趋势边界、封顶矩阵、取大六组合、工单字段与 due_at、低一致性 P0、幂等、`map_risk_level`、配置不变量）。

## 9. 待确认清单

- 四路分析的真实 Provider 选型与降级策略；
- `map_risk_level` 的 `text_valence` 分段阈值权威来源（已定义于 `app/grading/config.py`，全部 `# TODO: 待标定`；已 wiring 进 pipeline，阈值仍待业务确认）；
- 一致性阈值从 `app/analysis/config.py` 迁到 `app/grading/config.py` 的适配时机（grading 侧已定义权威值 0.6，analysis 仍用本地常量）；
- 是否为 `app/analysis/` 打标签（如 `analysis-v1`）；
- 是否为 `app/grading/` 打标签（如 `grading-v1`）；
- `architecture.md` 存储路径是否按 capture@1.2 修订；
- `scripts/` 的目录归属；
- `capture_busy` 是否在 api@1.6 增补专用错误码；
- 正式验证用的 `subject_id` 目前是固定 UUID（`3b1e7c90-...`），是否保留为演示对象；
- 是否将本机 SQLAlchemy 重装到 `<2.1` 以彻底消除 M1 现象；
- `CAPTURE_FAKE` 是否增加 `APP_ENV != production` 守卫。
