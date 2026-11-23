# 项目进度（PROGRESS）

> 生成时间：2026-11-23 · 基准提交：`55c9a25` · 依据：`git log`、工作树文件清单、`docs/contracts/`。
> 本文只记录仓库里可核实的事实；尚未实现或未定稿的内容标注「待确认」。

## 1. 项目定位与技术栈

**一句话**：社区矫正场景的单对象纵向切片原型——把一次采集（人脸 + 语音）转成结构化信号，经四路分析与五色分级，**分级结果唯一出口是人工复核工单**，系统自身不产生处置动作（[prd.md](./prd.md#L20)）。

| 层 | 选型 | 现状 |
|---|---|---|
| 运行时 | Python 3.11 | 已用（本机 3.11.0rc2） |
| 采集 | OpenCV / MediaPipe / sounddevice | 已实现并硬件验证 |
| Web 框架 | FastAPI | 未实现 |
| ORM / 数据库 | SQLAlchemy 2.x + Alembic / SQLite | 未实现 |
| 前端 | React + Vite（用户端 / 管理端同仓，按路由分区） | 未实现 |
| 模型 | Provider 抽象 + mock | 未实现，本轮不接真模型 |
| 测试 | pytest | 已用（6 条采集用例） |

技术栈来源：[architecture.md](./architecture.md#L11-L21)；采集运行在后端宿主设备而非浏览器（[architecture.md](./architecture.md#L23-L31)）。

## 2. 已完成模块与对应标签

| 对象 | 状态 | 标签 / 提交 |
|---|---|---|
| 契约文档 v1.2（capture / db / api / ui / grading） | 已冻结 | `contracts-v1.2` → `8698a26` |
| `app/capture/` 采集模块（抓拍 / 人脸检测裁剪 / 录音 / 会话打包） | 已实现 | `capture-v1` → `55c9a25` |
| `tests/test_capture/`（6 条，全部 mock 设备） | 全绿 | 包含在 `787ee0e` |
| `scripts/verify_capture.py`、`scripts/hw_check.py` | 已实现 | 包含在 `55c9a25` |
| 真实硬件端到端验证 | 已通过 | `ok` / `both` 一次；另有 `no_audio`、`no_face_no_audio` 历史结果 |

提交历史：

```
55c9a25  feat(capture): verified on real hardware (ok/both); prefer DirectShow, 16k audio   [capture-v1]
787ee0e  feat(capture): align to contract state machine (coverage/warnings/optional crop) + tests
8698a26  docs: contracts v1.2 freeze (degraded array + analysis_status + ui copy)           [contracts-v1.2]
2003967  docs: close grading partial + ui no_face/no_audio + api degrade semantics
7a6f0cf  baseline: contracts v1.1 + app/capture                                              [contracts-v1.1]
```

**尚未实现的模块**：`app/analysis/`、`app/grading/`、`app/api/`、`app/db/`、`web/`。仓库中目前只有 `app/capture/` 一个业务包。

采集模块已落地的契约要点：

- 六值 `capture_status`：`ok` / `partial` / `no_face` / `no_audio` / `no_face_no_audio` / `error`；
- `coverage`：`both` / `face_only` / `audio_only`，失败态为 `null`；
- `meta.warnings[]` 承载非致命原因，`meta.error` 仅在 `error` 时非空；
- 人脸检测顺序 MediaPipe → OpenCV DNN → Haar；裁剪外扩 25%、JPEG 质量 85；
- 目录固定为 `storage/subjects/{subject_id}/sessions/{session_id}/`，原始帧不落盘。

## 3. 关键决策与理由

| 决策 | 落地位置 | 理由 |
|---|---|---|
| **DirectShow 优先**（Windows 下先 `cv2.CAP_DSHOW`，失败回退默认后端） | `app/capture/camera.py`，提交 `55c9a25` | 本机实测：默认 MSMF 帧连续多次检不出人脸，同一设备 DSHOW 帧可检出；回退设计保证非 Windows 与打不开场景行为不变，错误 code 语义不变 |
| **裁剪输出固定 300×300**（`OUTPUT_SIDE = 300`，取消“最长边”语义） | [config.py](../app/capture/config.py#L61)、capture@1.2 §5.1 | 统一下游输入尺寸；`meta.face.output_size` 恒为 `[300, 300]`，便于断言与存储控制 |
| **音频 16 kHz / 单声道 / 16-bit** | [audio.py](../app/capture/audio.py#L22-L27)、architecture §存储 | 语音链路足够、体积小（10 秒 WAV = 320,044 B）；`speech_ratio` 阈值 0.05 |
| **error 判级规则** | capture@1.2 §3 | 零产物 + 设备/技术级 code → `error`；零产物 + 全业务级 code → `no_face_no_audio`；任一路有产物 → `partial` 或单模态。避免“设备故障”与“确实没检出”混为一谈 |
| **`sessions.status` 与 `analysis_status` 拆分** | db@1.2 §3.1 | `status` 只反映采集（`created`/`captured`/`failed`）；分析状态独立为 `pending`/`done`/`degraded`/`failed`，分析失败不回写 `failed` |
| **`degraded` 改为字符串数组** | api@1.2 §7.2 | 区分采集降级与分析降级：`[]` / `["capture"]` / `["analysis"]` / `["capture","analysis"]`；新增 `2003` 表示分析彻底失败 |
| **分析全走 mock Provider** | [prd.md](./prd.md#L33) | 本轮先跑通链路与契约，不引入模型不确定性 |

## 4. 当前未完成项与阻塞

**未完成（按目录）**

| 目录 | 内容 | 状态 |
|---|---|---|
| `app/analysis/` | 四路管线（ASR / 语音情感 / 表情 / 心理文本）、Provider 抽象、一致性判定 | 未开始 |
| `app/grading/` | 五色规则、七日趋势偏移、合成封顶、工单草案 | 未开始 |
| `app/db/` | 5 张表（`subjects` / `sessions` / `reviews` / `review_tickets` / `audit_logs`）+ 迁移 | 未开始 |
| `app/api/` | FastAPI 路由、鉴权、统一响应包、错误码 | 未开始 |
| `web/` | 用户端 3 页 + 管理端 4 页 | 未开始 |

**阻塞 / 风险**

1. **麦克风音量**：本机默认输入曾长期近乎静音（峰值 7/32768、`speech_ratio=0`），导致 `audio_too_short`；最后一次正式验证为 `ok`（`speech_ratio=0.3153`），说明设备可用但音量偏低，现场部署前需复核输入设备与增益。
2. **真实模型未接**：四路分析只有 mock 规划，Provider 选型与降级策略未定 —— 待确认。
3. **文档漂移**：[architecture.md](./architecture.md#L53) 的存储路径仍是 `storage/{subject_id}/{session_id}/`，与 capture@1.2 的 `storage/subjects/.../sessions/.../` 不一致；本次未改该文档 —— 待确认是否修订。
4. **表数量口径**：[.trae/agents/README.md](../.trae/agents/README.md) 提到 4 张表，而 [db.md](./contracts/db.md) 与 architecture 已按 5 张（含 `audit_logs`）定稿 —— 以 db.md 为准，README 待同步，待确认。
5. **`scripts/` 无归属**：目录所有权表未列出 `scripts/`，目前由主智能体直接维护 —— 待确认是否划给 qa-guard。

## 5. 下一步顺序（建议）

1. **analysis-engineer**：实现 `app/analysis/` 四路 Provider + `analysis.schema.json` 校验 + 一致性判定，全部 mock，补 `tests/test_analysis/`。
2. **grading-engineer**：实现五色规则、七日趋势、合成封顶、工单草案，按 `docs/grading.md` 与 `contracts/grading.md` 落地，补 `tests/test_grading/`。
3. **backend-engineer**：建 5 张表与迁移，接采集/分析/分级，按 api@1.2 输出统一响应包与错误码。
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
| backend-engineer | `app/api/`、`app/db/`、`tests/test_api/` |
| fe-user | `web/src/user/`（另可新增 `web/src/components/common/` 通用展示组件） |
| fe-admin | `web/src/admin/` |
| qa-guard | `tests/`、`docs/reports/` |
| privacy-check | 无（只读） |

补充：`docs/contracts/` 只允许主智能体修改；`scripts/` 归属待确认。

## 8. 环境与验证命令（当前机器）

```
Python 3.11.0rc2 · cv2 4.11.0 · numpy 1.26.4 · sounddevice 0.5.6 · mediapipe 0.10.21 · pytest 9.2.0
```

```powershell
pytest tests/test_capture/ -q                                        # 6 passed
python scripts\verify_capture.py --device 0 --seconds 10             # 正式验证 → storage/subjects
python scripts\verify_capture.py --device 0 --seconds 5 --out storage/_debug   # 调试/自检
```

## 9. 待确认清单

- 四路分析的真实 Provider 选型与降级策略；
- `architecture.md` 存储路径是否按 capture@1.2 修订；
- README 中“4 张表”是否改为 5 张；
- `scripts/` 的目录归属；
- 正式验证用的 `subject_id` 目前是固定 UUID（`3b1e7c90-...`），是否保留为演示对象。
