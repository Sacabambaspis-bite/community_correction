# 项目进度（PROGRESS）

> 生成时间：2026-11-24 · 基准提交：`43d3aba` · 依据：`git log`、`git tag`、`pytest` 实测、[QA 报告](./reports/qa-2026-11-24.md)。
> 本文只记录仓库里可核实的事实；尚未实现或未定稿的内容标注「待确认」。

## 1. 项目定位与技术栈

**一句话**：社区矫正场景的单对象纵向切片原型——把一次采集（人脸 + 语音）转成结构化信号，经四路分析与五色分级，**分级结果唯一出口是人工复核工单**，系统自身不产生处置动作（[prd.md](./prd.md#L20)）。

| 层 | 选型 | 现状 |
|---|---|---|
| 运行时 | Python 3.11 | 已用（本机 3.11.0rc2） |
| 采集 | OpenCV / MediaPipe / sounddevice | 已实现并硬件验证，封存于 `capture-v1` |
| Web 框架 | FastAPI 0.165.0 + uvicorn 0.54.0 | 骨架已实现（`api-v1`） |
| ORM / 数据库 | SQLAlchemy 2.x（原型阶段手工迁移）/ SQLite | 5 张表已实现（`db-v1`）；本机实际 2.1.9，`requirements` 已锁 `<2.1` |
| 前端 | React + Vite（用户端 / 管理端同仓，按路由分区） | 未实现 |
| 模型 | Provider 抽象 + mock | 未实现，本轮不接真模型 |
| 测试 | pytest | 34 条全绿（capture 6 / db 13 / api 15） |

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
| `scripts/seed_demo.py` 演示数据（含占位素材） | 已实现 | `0bb78b5` |
| QA 核验 + M1–M4/L4/L8 修复 | 已完成 | `638245e`（报告）、`7732930`（修复） |

提交历史（近 14 条）：

```
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
8698a26  docs: contracts v1.2 freeze (degraded array + analysis_status + ui copy)           [contracts-v1.2]
2003967  docs: close grading partial + ui no_face/no_audio + api degrade semantics
7a6f0cf  baseline: contracts v1.1 + app/capture                                              [contracts-v1.1]
```

**尚未实现的模块**：`app/analysis/`、`app/grading/`、`web/`。`app/capture/` 已封存；`app/db/` 与 `app/api/` 骨架已实现。

采集模块已落地的契约要点：

- 六值 `capture_status`：`ok` / `partial` / `no_face` / `no_audio` / `no_face_no_audio` / `error`；
- `coverage`：`both` / `face_only` / `audio_only`，失败态为 `null`；
- `meta.warnings[]` 承载非致命原因，`meta.error` 仅在 `error` 时非空；
- 人脸检测顺序 MediaPipe → OpenCV DNN → Haar；裁剪外扩 25%、JPEG 质量 85；
- 目录固定为 `storage/subjects/{subject_id}/sessions/{session_id}/`，原始帧不落盘。

数据层与 API 骨架已落地的要点：

- 五张表：`subjects` / `sessions` / `reviews` / `review_tickets` / `audit_logs`，字段、CHECK、索引与 db@1.4 一致；
- `sessions.coverage` 为派生属性，不落列；`analysis_status`、`gender`、`status`、`window_days` 有服务端默认值；
- `reviews` 唯一约束 `UNIQUE(subject_id, window_end)`；JSON 列统一 `IS NULL OR json_valid(...)`；
- 统一信封 `{code, message, data, degraded, request_id}`，业务错误一律 HTTP 200，未捕获异常 HTTP 500 + `code=5000`；
- 已实现：`GET /api/health`、`POST/GET /api/sessions`、`GET /api/admin/subjects|sessions`、`GET /api/admin/sessions/{id}/face`（写 `audit_logs`）、`POST /api/sessions/{id}/analyze`（占位 `5000 analysis_pipeline_not_ready`）；
- 分析未接入前，`GET /api/sessions/{id}` 已按 `captured→2001`、`analysis failed→2003` 的优先级映射。

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

## 4. 当前未完成项与阻塞

**未完成（按目录）**

| 目录 | 内容 | 状态 |
|---|---|---|
| `app/analysis/` | 四路管线（ASR / 语音情感 / 表情 / 心理文本）、Provider 抽象、一致性判定 | 未开始 |
| `app/grading/` | 五色规则、七日趋势偏移、合成封顶、工单草案 | 未开始 |
| `app/api/` | 用户端端点、consent 校验、review 查询、分析接入 | 骨架已实现，延期项见下 |
| `web/` | 用户端 3 页 + 管理端 4 页 | 未开始 |

**API 骨架延期项（前端开工前必须补齐）**

- `/api/user/*` 全部端点：consent 查询 / 提交 / 撤回、`feedback`；
- `POST /api/sessions` 的 consent 前置校验（`1005 consent_required` / `consent_revoked`）；
- `subject` token 的会话归属校验（只能访问本人 session，越权返回 `1003`）；
- `POST /api/sessions/{id}/analyze` 与 review 查询待 `app/analysis`、`app/grading` 就绪后接入。

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
6. **真实模型未接**：四路分析只有 mock 规划，Provider 选型与降级策略未定 —— 待确认。
7. **文档漂移**：[architecture.md](./architecture.md#L53) 的存储路径仍是 `storage/{subject_id}/{session_id}/`，与 capture@1.2 不一致。
8. **`capture_busy` 暂复用 `code=5000`**（`message=capture_busy`），尚无专用业务码。

## 5. 下一步顺序（建议）

1. **analysis-engineer**：实现 `app/analysis/` 四路 Provider + `analysis.schema.json` 校验 + 一致性判定，全部 mock，补 `tests/test_analysis/`。
2. **grading-engineer**：实现五色规则、七日趋势、合成封顶、工单草案，按 [grading.md](./grading.md) 与 [contracts/grading.md](./contracts/grading.md) 落地，补 `tests/test_grading/`。
3. **backend-engineer**：补 `/api/user/*`、consent 前置校验、会话归属校验；接入 analyze 与 review 查询。
4. **fe-user / fe-admin**：先用户端 3 页，再管理端 4 页，严格对齐 ui@1.2（用户端不出现色码）。
5. **qa-guard + privacy-check**：每轮合并前跑 qa-guard；涉及人脸/音频/心理数据的改动先过 privacy-check。

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
```

```powershell
pytest tests -q                                                      # 34 passed
python -m app.db.init                                                # 建库（幂等）
uvicorn app.api.main:app --port 8000                                 # /docs 可访问
python scripts\seed_demo.py                                          # 演示数据（幂等；--reset 清空后重建）
python scripts\verify_capture.py --device 0 --seconds 10             # 正式验证 → storage/subjects
python scripts\verify_capture.py --device 0 --seconds 5 --out storage/_debug   # 调试/自检
```

测试构成：`tests/test_capture/` 6 条、`tests/test_db/` 13 条（含 3 条约束负例）、`tests/test_api/` 15 条（含假采集/失败/并发/生产守卫）。

## 9. 待确认清单

- 四路分析的真实 Provider 选型与降级策略；
- `architecture.md` 存储路径是否按 capture@1.2 修订；
- `scripts/` 的目录归属；
- `capture_busy` 是否在 api@1.5 增补专用错误码；
- 正式验证用的 `subject_id` 目前是固定 UUID（`3b1e7c90-...`），是否保留为演示对象；
- 是否将本机 SQLAlchemy 重装到 `<2.1` 以彻底消除 M1 现象；
- `CAPTURE_FAKE` 是否增加 `APP_ENV != production` 守卫。
