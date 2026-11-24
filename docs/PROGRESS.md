# 项目进度（PROGRESS）

> 生成时间：2026-11-24 · 基准提交：`5eef4bb`（`main` 与 `origin/main` 同步）+ 未提交变更（SenseVoice ASR 接入、consent 一次性授权、签到/思想汇报双模块与逾期复核、思想汇报手动录音）· 依据：`git log`、`git tag`、`pytest` 实测、[QA 报告](./reports/qa-2026-11-24.md)。
> 本文只记录仓库里可核实的事实；尚未实现或未定稿的内容标注「待确认」。

## 1. 项目定位与技术栈

**一句话**：社区矫正场景的单对象纵向切片原型——把一次采集（人脸 + 语音）转成结构化信号，经四路分析与五色分级，**分级结果唯一出口是人工复核工单**，系统自身不产生处置动作（[prd.md](./prd.md#L20)）。

| 层 | 选型 | 现状 |
|---|---|---|
| 运行时 | Python 3.11 | 已用（本机 3.11.0rc2） |
| 采集 | OpenCV / MediaPipe / sounddevice | 已实现并硬件验证，封存于 `capture-v1` |
| Web 框架 | FastAPI 0.165.0 + uvicorn 0.54.0 | 骨架 + 用户端 / consent / analyze 接入（`api-v1` → `api@1.5` 实现补记） |
| ORM / 数据库 | SQLAlchemy 2.x（原型阶段手工迁移）/ SQLite | 5 张表已实现（`db-v1`）；本机实际 2.1.9，`requirements` 已锁 `<2.1` |
| 分析 | Provider 抽象 + 确定性 mock（ASR 可选真实 SenseVoice） | 四路 mock 已实现；`overall.risk_level` 已接 `app.grading.config.map_risk_level`（`c46536e`）；ASR 已接真实 SenseVoice API（env 配置启用，失败回退 Mock，未提交） |
| 分级 | 五色纯函数规则 + 七日趋势 + 工单草案 | 已实现并接入 analyze / 复盘 / 工单接口（`c46536e`） |
| Schema 校验 | jsonschema（Draft 2020-12 + FormatChecker） | 已引入，分析结果强制校验 |
| 前端 | React + Vite（用户端 / 管理端同仓，按路由分区） | 用户端 3 页 + 管理端 4 页骨架已实现（`601d33d`），联调仍走 mock |
| 测试 | pytest | 273 条全绿（capture 14 / db 21 / api 61 / analysis 69 / grading 108） |

技术栈来源：[architecture.md](./architecture.md#L11-L21)；采集运行在后端宿主设备而非浏览器（[architecture.md](./architecture.md#L23-L31)）。

## 2. 开发时间线（阶段化）

> 依据 `git log` 的提交时间与标签整理；同一阶段内的提交集中在数十分钟内完成。日期为提交日期（2026-11-23 ～ 2026-11-24）。「工作区」表示已实现但尚未提交。

| 阶段 | 时间 | 主线动作 | 交付物 | 追溯 |
|---|---|---|---|---|
| P0 契约基线 | 11-23 21:44 | 确立 `app/capture/` 与四份契约初稿，明确「分级只出口工单」边界 | 契约 v1.1 | `7a6f0cf` |
| P1 契约冻结 | 11-23 21:54–21:59 | 关闭 `grading` 的 `partial` 歧义、`ui` 的 `no_face/no_audio` 口径、`api` 降级语义；冻结 v1.2 | `contracts-v1.1`、`contracts-v1.2` | `2003967`、`8698a26` |
| P2 采集模块 | 11-23 22:09–23:16 | 状态机对齐契约（`coverage`/`warnings`/可选裁剪）；真机验证 `ok/both`；DirectShow 优先、16k 音频 | `app/capture/`、`tests/test_capture/`、`scripts/verify_capture.py`、`scripts/hw_check.py` | `787ee0e`、`55c9a25`（`capture-v1`） |
| P3 数据层 | 11-23 23:20–23:34 | 五表建模、派生 `coverage`、服务端默认值；`reviews` 窗口唯一 | `app/db/`、db@1.3 | `492c764`、`ddd4968`（`contracts-v1.3`）、`bc83a3e`（`db-v1`） |
| P4 API 骨架 | 11-24 00:03–00:20 | 统一信封、鉴权、异步采集、`2001/2003`、db@1.4/api@1.4；演示数据脚本 | `app/api/`、`scripts/seed_demo.py` | `96aa098`、`79e582d`（`api-v1`）、`0bb78b5` |
| P5 QA 修复 | 11-24 00:49–01:02 | M1–M4/L4/L8：锁 SQLAlchemy、FK 测试开关、日志脱敏、可注入 session 工厂、`CAPTURE_FAKE` | QA 报告 + 修复 + 进度快照 | `638245e`、`7732930`、`43d3aba`、`9b2a04d` |
| P6 分析模块 | 11-24 01:56 | 四路确定性 mock、Schema 校验、一致性判定、运行状态包装层 | `app/analysis/`、`tests/test_analysis/` | `81a8499` |
| P7 用户端 API | 11-24 08:31 | `/api/user/*`、consent 三闸、会话归属校验（api@1.5） | `app/api/routers/user.py` | `4f5d1bf` |
| P8 分级与前端骨架 | 11-24 13:24–13:34 | 五色规则、七日趋势、合成封顶、工单草案；前端用户端 3 页 + 管理端 4 页（mock） | `app/grading/`、`tests/test_grading/`、`web/` | `67adee6`、`601d33d`、`337fdb9`、`7782e65` |
| P9 分析→分级打通 | 11-24 14:18 | `analyze` 正式接入、复盘/工单/看板端点、低一致性强制 P0、契约同步 | `app/api/integration.py`、相关路由 | `1d3fb0e`、`c46536e`、`5eef4bb` |
| P10 工作区增量（未提交） | 11-24 之后 | ① SenseVoice ASR 真实接入（超时回退）② consent 一次性授权、去保存期限 ③ 签到/汇报双模块 + 逾期复核 ④ 思想汇报手动录音 | 见 §3 末段 | 工作区 |

**阶段结论**：P0–P9 已形成「采集 → 数据 → 分析 → 分级 → 工单 → 前端骨架」的完整纵向切片并全部提交；P10 为当前未提交增量，测试总数由 224 增至 273。

## 3. 已完成功能模块与交付物

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
| `tests/test_analysis/`（64 条） | 全绿 | `81a8499` + 工作区（SenseVoice） |
| SenseVoice ASR Provider（真实 API + 10s 超时 + Mock 回退） | 已实现（未提交） | 工作区 |
| `app/grading/` 五色规则、七日趋势偏移、合成封顶、工单草案 | 已实现并接入 API（未打标签） | `67adee6`、`1d3fb0e` |
| `tests/test_grading/`（108 条） | 全绿 | `67adee6`、`1d3fb0e` |
| `web/` 用户端 3 页 + 管理端 4 页骨架（mock 联调） | 已实现 | `601d33d` |
| consent 一次性授权改版（去保存期限、`retention_days` 可选缺省 180） | 已实现（未提交） | 工作区 |
| 双模块：用户端 `/capture` 选择页 + `/capture/checkin`（face_only）+ `/capture/report` | 已实现（未提交） | 工作区 |
| 双模块后端：`sessions.kind`、频率字段、`GET /api/user/tasks`、`PATCH .../frequency`、逾期 P0 工单（惰性幂等） | 已实现（未提交） | 工作区 |
| 管理端：频率编辑、最近签到/汇报时间、红色「危机·逾期」徽标、逾期工单中文展示 | 已实现（未提交） | 工作区 |
| 思想汇报手动录音：`stop_event` 采集模式 + `POST /api/sessions/{id}/stop` + 前端正计时无自动终止 | 已实现（未提交） | 工作区 |
| analyze 正式接入 + 复盘 / 工单 / 看板端点 | 已实现 | `c46536e` |
| `map_risk_level` wiring + 低一致性 P0 修复 | 已实现 | `c46536e`、`1d3fb0e` |
| 远程仓库 | `main` 与 `origin/main` 同步 | `origin/main` @ `5eef4bb` |
| `scripts/seed_demo.py` 演示数据（含占位素材） | 已实现 | `0bb78b5` |
| QA 核验 + M1–M4/L4/L8 修复 | 已完成 | `638245e`（报告）、`7732930`（修复） |

提交历史（近 20 条，倒序；完整记录见 `git log`）：

```
5eef4bb  docs: sync contracts for grading integration and consent alignment
c46536e  feat(api): integrate analysis, grading, reviews, tickets and dashboard
1d3fb0e  fix(grading): force P0 for low-consistency manual review
7782e65  docs(progress): mark grading commits pushed (origin/main @ 337fdb9)
601d33d  feat(web): scaffold user and admin frontend with mock data and routing
337fdb9  docs(grading): sync contract with implementation (review_reason, map_risk_level, cap semantics)
67adee6  feat(grading): implement 5-color rules, trend analysis and ticket builder
4f5d1bf  feat(api): user endpoints, consent gates, session ownership (api@1.5)
9c1386e  docs: refresh PROGRESS for analysis and api@1.5
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

**尚未实现**：复盘列表 `GET /api/admin/reviews`、60 秒频控（`1006`）、转写查看。`web/` 骨架已实现（`601d33d`）；`app/api/` 的 analyze / review / tickets / dashboard / subjects 详情已接入（`c46536e` + 工作区）；`app/capture/` 已封存，`app/db/`、`app/api/`、`app/analysis/` mock 与 `app/grading/` 分级规则均已实现。

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
- `POST /api/sessions/{id}/analyze` 已正式接入（`c46536e`）：`captured` 跑四路分析并落 `analysis_json` / `transcript_path` / `analysis_status`，再按自然日窗口生成 `reviews` / `review_tickets`；分析彻底失败 `2003` 且不改 `sessions.status`；重复调用幂等；
- 新增管理端端点（`c46536e`）：`POST /api/admin/reviews`（0 可用会话 → `1005 no_session_in_window`）、`GET /api/admin/reviews/{id}`、`GET /api/admin/tickets`、`GET /api/admin/tickets/{id}`（写 `sensitive.view`）、`POST /api/admin/tickets/{id}/transition`、`GET /api/admin/dashboard`（`subject_id` 可选，缺省取最近采集对象）。

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
- 历史遗留 `risk_level` 映射：`config.map_risk_level(text_valence, intent_flag)` 先按 `text_valence` 分段（`[-0.8,-0.5,-0.2,0.0]`→crisis/high/elevated/watch/none），`intent_flag∈{suicide_intent,self_harm_mention}` 强制覆写 `crisis`；**已 wiring 进 `app/analysis/pipeline.py`**（`c46536e`，`pending` 占位已删除）；
- 阈值唯一来源 `config.py`（15 项均标 `# TODO: 待标定`），`tests/test_grading/test_config.py` 源码扫描保证规则模块无字面量泄漏。

## 4. 关键决策与理由

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
| **分析默认 mock Provider，ASR 可选真实 SenseVoice** | [prd.md](./prd.md#L33)、[sensevoice_asr.py](../app/analysis/providers/sensevoice_asr.py) | 原型阶段先跑通链路与契约；`SENSEVOICE_API_URL`/`SENSEVOICE_API_KEY` 齐备时 ASR 走真实 API，其余通道仍 mock |
| **SenseVoice 失败回退 Mock + degraded** | [sensevoice_asr.py](../app/analysis/providers/sensevoice_asr.py)、[providers/__init__.py](../app/analysis/providers/__init__.py) | 10s 超时；超时/4xx/5xx/解析失败一律回退 Mock 并标 `degraded / sensevoice_fallback`，管线不中断；ASR 非 ok 时 psych 按既有契约 `skipped/asr_unavailable` |
| **运行时只读 `os.environ`，不自动加载 `.env`** | [sensevoice_asr.py](../app/analysis/providers/sensevoice_asr.py)、[tests/test_analysis/conftest.py](../tests/test_analysis/conftest.py) | 仓库无 dotenv 依赖；避免测试误读真实 Key 触网；测试以 autouse fixture 清 env，HTTP 全部 mock 拦截 |
| **分析运行状态与结果分离** | [models.py](../app/analysis/models.py)、[pipeline.py](../app/analysis/pipeline.py) | `AnalysisResult` 严格对齐 schema；`done/degraded/failed` 放在独立包装层，失败不产出可进入 grading 的结果 |
| **`risk_level` 映射落在 grading config 并已 wiring** | [config.py](../app/grading/config.py) `map_risk_level`、[pipeline.py](../app/analysis/pipeline.py) | 按 `text_valence` 分段 + 明确意图覆写 `crisis`；`c46536e` 删除 `pending` 占位，pipeline 直接调用 `map_risk_level` |
| **一致性阈值权威值在 grading** | [config.py](../app/grading/config.py) `CONSISTENCY_MIN_CONFIDENCE` | grading 侧已定义 0.6；`app/analysis/config.py` 仍用本地常量，迁移时机待定 |
| **分级为纯函数、只出口工单草案** | `app/grading/*`（`build_ticket` 只返回 dict） | 不读写库/文件/网络，不产生处置动作；色码不进入用户端路径 |
| **`review_reason` 承载规则 8 覆写** | [models.py](../app/grading/models.py)、[ticket.py](../app/grading/ticket.py) | `compose` 签名不增参；`AnalysisResult` 不含 `capture_status`，由 backend 用 `replace(..., review_reason="capture_degraded")` 覆写后建 P0+recapture 单 |
| **低一致性 P0 由 `manual_review` 驱动** | [ticket.py](../app/grading/ticket.py) | 规则 5 与色码无关；`review_reason="consistency_conflict"` 只描述原因，不改档位 |
| **复盘窗口按自然日、DB 存 `YYYY-MM-DD`** | [integration.py](../app/api/integration.py)、db@1.4 §4 | 与 grading 证据 `window` 一致；同日多会话共用一个 `window_end`，靠 `UNIQUE(subject_id, window_end)` 幂等 |
| **0 可用会话在上游拦截** | [admin.py](../app/api/routers/admin.py) `POST /api/admin/reviews` | 「可用会话」= `captured` + `analysis_status∈{done,degraded}`；0 条直接 `1005`，不落库、不建单 |
| **analyze 同步完成分析 + 分级** | [sessions.py](../app/api/routers/sessions.py)、[integration.py](../app/api/integration.py) | 原型阶段 mock 分析耗时可接受；省去后台任务与轮询复杂度，失败只用 `analysis_status=failed` 表达 |
| **consent 一次性授权、不展示保存期限** | ui@1.2 §3.1 补记 2、api@1.5 §7.1.2、[ConsentForm.tsx](../web/src/user/Consent/ConsentForm.tsx)、[schemas.py](../app/api/schemas.py) | 进入用户端首次授权后，有效期内再采集不再重复询问，撤回后才需重新授权；两项独立勾选一次提交；`retention_days` 改可选、缺省 180，仅用于留存管理，用户端不展示不填写 |
| **签到 face_only 属正常形态，豁免单模态强制规则** | grading@1.2 补记·三、capture@1.2 补记、[pipeline.py](../app/analysis/pipeline.py)、[consistency.py](../app/analysis/consistency.py) | checkin 的 asr/emotion/psych skipped 不计降级；单 face 通道 consistency 中性 medium；不强制 P0/recapture；`map_risk_level(0.0,"none")`；no_face/error 仍按异常 |
| **逾期 = P0 复核工单 + 管理端危机标记** | api@1.5 补记·二、[integration.py](../app/api/integration.py) | 频率按对象配置（签到默认 1 天、汇报默认 3 天）；管理端读取时惰性判定并幂等建单（`talk_to_staff`、`detail_json.overdue_kind/overdue_days`、初始 `pending`）；不改会话状态、不触发分析；用户端仅中性提示 |
| **思想汇报录音完全手动控制** | capture@1.2 补记·二、api@1.5 补记·三、ui@1.2 补记 4、[CapturePage.tsx](../web/src/user/Capture/CapturePage.tsx) | 不传 `duration_sec` = 手动模式；100ms 分块录音直到 `stop_event.set()`；无倒计时、无自动终止；stop 幂等且不落库；录音中不轮询（消除「倒计时未完但提前结束」的界面假象）；保存/上传/反馈逻辑不变 |

## 5. 待办任务与未完成项

**未完成（按目录）**

| 目录 | 内容 | 状态 |
|---|---|---|
| `app/analysis/` | 四路 mock、Schema 校验、一致性判定 | 已实现；ASR 已接 SenseVoice（工作区未提交），emotion/face/psych 真模型待接；`risk_level` 已 wiring `map_risk_level`（`c46536e`） |
| `app/grading/` | 五色规则、七日趋势偏移、合成封顶、工单草案 | 已实现并接入 API（`c46536e`）；低一致性 P0 已补 |
| `app/api/` | analyze / reviews / tickets / dashboard | 已接入（`c46536e`）；余项见下 |
| `web/` | 用户端 3 页 + 管理端 4 页 | 骨架已实现（`601d33d`），待与真实 API 联调 |

**API 剩余延期项**

- 复盘列表 `GET /api/admin/reviews`；
- `GET /api/admin/sessions/{id}/transcript`（管理端敏感面板）；
- （`GET /api/admin/subjects/{subject_id}` 已随双模块实现，工作区）
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
6. **emotion/face/psych 真模型未接**：仍为确定性 mock，Provider 选型与降级策略待确认；ASR 已接 SenseVoice（真实 URL/Key 在本机 `.env`，运行时需注入 `os.environ`）。
7. **`risk_level` 已 wiring**：`generate_overall_risk_level(text_valence, intent_flag)` 直接返回 `map_risk_level`；阈值仍全部 `# TODO: 待标定`，正式上线前需业务确认。
8. **部署需安装新依赖**：`requirements.txt` 已加入 `jsonschema[format]>=4.23,<5`，本地已安装，其他环境需重新安装。
9. **文档漂移**：[architecture.md](./architecture.md#L53) 的存储路径仍是 `storage/{subject_id}/{session_id}/`，与 capture@1.2 不一致。
10. **`capture_busy` 暂复用 `code=5000`**（`message=capture_busy`），尚无专用业务码。
11. **契约已同步（2026-11-24）**：`grading.md` 补记规则 5 P0、复盘前提、工单主键归属与覆写顺序；`api.md` 补记 analyze / reviews / tickets / dashboard、窗口 `YYYY-MM-DD`、`1005 no_session_in_window`、consent 强校验；`ui.md` §3.1 统一两项齐备；`db.md` 补窗口格式与 0 会话不落库。版本号均保持不变（附加、非破坏）。同日追加：`ui.md` 补记 2（一次性授权、去保存期限）、`api.md` §7.1.2 `retention_days` 可选缺省 180；双模块追加 `ui.md` 补记 3、`api.md` 补记·二、`grading.md` 补记·三、`capture.md` 补记（face_only）、`db.md` 补记（kind/频率/`review_id` 可空/`detail_json`/`talk_to_staff`/`frequency.update`）、`analysis.schema.json` degraded 描述 checkin 例外（均在工作区，未提交）。
12. **管理端前端仍用 mock**：`web/src/api/*` 已按契约声明端点，但 `AdminDashboard` 等页面尚未切真实 API；用户端 consent 已完成两项齐备门禁、一次性授权与去保存期限（工作区，未提交）。
13. **analyze 为同步长请求**：mock 下可接受；ASR 真实 API 已有 10s 超时 + Mock 回退；后续接其余真模型需评估超时或改后台任务，并复用 `deps.get_session_factory()` 注入。
14. **本机库需执行双模块迁移**：`app/db/migrations/202611241200_add_dual_module_tasks.py`（`python -m app.db.migrations.202611241200_add_dual_module_tasks`）；`storage/app.db` 尚未迁移，直接启动旧库会缺 `kind`/频率列。
15. **手动录音未做真实设备联调**：手动闭环已由 fake + 单元测试覆盖（不自动终止、stop 后落盘）；真实麦克风长时间录音的资源占用与 stop 响应时延需现场验证。

## 6. 下一步顺序（建议）

1. **fe-user / fe-admin**：把 `web/src/api/*` 从 mock 切到真实端点；管理端接 `tickets` / `dashboard` / `reviews`（用户端 consent 门禁与一次性授权已完成）。
2. **backend-engineer（余项）**：60 秒频控 `1006`、`capture_busy` 专用码、`GET /api/admin/reviews` 列表、转写查看。
3. **qa-guard + privacy-check**：每轮合并前跑 qa-guard；`c46536e` 新增的 analyze/reviews/tickets 端点涉及心理与工单数据，合并前过 privacy-check。

## 7. 三条红线

1. **原图不落盘**：只保留裁剪后的 `face.jpg`，原始帧不落盘、不写日志、不进异常 `detail`（[prd.md](./prd.md#L82)、capture@1.2 §8.1）。
2. **分级只出口复核工单**：任何非绿结果只生成工单，系统不得产生限制、通报、扣分等动作（[grading.md](./grading.md#L20)）。
3. **色码只在管理端**：用户端响应与页面不出现 `final_color` 及任何色码字段，只输出行为建议（[grading.md](./grading.md#L39)、[prd.md](./prd.md#L94)）。

## 8. 目录所有权（subagent 可写范围）

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

## 9. 环境与验证命令（当前机器）

```
Python 3.11.0rc2 · cv2 4.11.0 · numpy 1.26.4 · sounddevice 0.5.6 · mediapipe 0.10.21
SQLAlchemy 2.1.9（requirements 锁 <2.1）· FastAPI 0.165.0 · uvicorn 0.54.0 · pydantic 2.14.4 · pytest 9.2.0
jsonschema 4.26.0（含 format 校验依赖）
```

```powershell
pytest tests -q                                                      # 273 passed
python -m app.db.init                                                # 建库（幂等）
uvicorn app.api.main:app --port 8000                                 # /docs 可访问
python scripts\seed_demo.py                                          # 演示数据（幂等；--reset 清空后重建）
python scripts\verify_capture.py --device 0 --seconds 10             # 正式验证 → storage/subjects
python scripts\verify_capture.py --device 0 --seconds 5 --out storage/_debug   # 调试/自检
git push origin main                                                 # 远程为 ssh.github.com:443（22 端口被阻断）
```

测试构成：`tests/test_capture/` 14 条（含 face_only、手动录音 stop_event 闭环与 fake 闭环）、`tests/test_db/` 21 条（含 3 条约束负例、双模块默认值/CHECK/索引/迁移回填）、`tests/test_api/` 61 条（含用户端 / consent / 归属 / 假采集 / 失败 / 并发 / 生产守卫 / analyze 接入 / 复盘 / 工单 / 看板 / retention 缺省 / 双模块 kind / tasks / frequency / 逾期幂等 / 序列化字段 / 手动 stop 全流程与异常分支）、`tests/test_analysis/` 69 条（含场景、单模态、降级隔离、Schema、一致性、确定性与隐私、SenseVoice 九项 mock 拦截、checkin 预期 skipped 与一致性豁免）、`tests/test_grading/` 108 条（单次/趋势边界、封顶矩阵、取大六组合、工单字段与 due_at、低一致性 P0、幂等、`map_risk_level`、配置不变量）。

## 10. 待确认清单

- emotion/face/psych 的真实 Provider 选型与降级策略（ASR 已定 SenseVoice + Mock 回退）；
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

## 11. 文档维护约定

| 约定 | 说明 |
|---|---|
| 事实优先 | 本文只写仓库内可核实的事实（提交号、文件路径、测试输出）；推断或未定稿内容一律标「待确认」 |
| 更新时机 | 每完成一个可验证的里程碑（新增目录、接口、契约变更、标签）即更新 §2 时间线、§3 模块表与 §9 测试数 |
| 时间线追加 | 新阶段在 §2 表格末尾追加一行，保留既有行不删除，确保历史可追溯 |
| 提交追溯 | 已提交项写短哈希与标签；未提交项写「工作区」，提交后回填哈希 |
| 风险闭环 | §5 中已消解的风险移入「已消解」，不直接删除 |
| 契约联动 | 契约（`docs/contracts/*`）变更必须同步 §4 决策与 §5 风险，避免文档漂移 |
| 版本口径 | 契约版本号只增不改；实现驱动变更以「实现补记」形式附加，保持冻结语义 |
| 后续扩展位 | 如需新增章节，建议按「§12 性能与容量」「§13 部署与运维」「§14 变更日志」顺序追加，不打断现有编号 |
