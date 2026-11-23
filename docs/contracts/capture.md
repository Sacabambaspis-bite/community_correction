# 契约 · 采集（capture）

| 项 | 值 |
|---|---|
| 契约版本 | `capture@1.2` |
| 所有者 | capture-engineer（`app/capture/`） |
| 上游 | `POST /api/session`（见 [api.md](./api.md)） |
| 下游 | `app/analysis/` 读取 `face_path` / `audio_path` |

> 本版已冻结，后续仅接受实现驱动的变更。

---

## 1. 职责边界

`app/capture/` 只做四件事：抓拍、人脸检测、裁剪、录音，并把结果打包成会话目录。

**不做**：模型推理、分级判断、数据库写入、字段脱敏。这些分别属于 `analysis`、`grading`、`api`。

## 2. 会话目录结构

```
{STORAGE_ROOT}/subjects/{subject_id}/sessions/{session_id}/
├── face.jpg          # 裁剪后人脸
├── audio.wav         # 录音
├── meta.json         # 任何 capture_status 都写
└── transcript.txt    # 由 analysis/asr 生成，不属于 capture 产出
```

约束：

- 目录层级固定为 `subjects/{subject_id}/sessions/{session_id}/`，不得使用 `{subject_id}/{session_id}` 简写；
- 路径一律以 `{STORAGE_ROOT}` 为根，数据库只存相对路径；
- **文件是否存在一律由第 3 节矩阵判定**，本章不逐文件声明“必有”；
- 目录或文件写入失败按第 3 节矩阵收敛：仍有可用产物 → `partial` + warning `storage_write_failed`；无任何可用产物 → `error` + code `storage_write_failed`；
- **原始帧绝不写入该目录，也不写入任何临时目录**。

## 3. `capture_status` 状态机

六值：`ok` / `partial` / `no_face` / `no_audio` / `no_face_no_audio` / `error`。

`partial` 表示**技术性降级**：至少一路产物可用，但存在非致命故障（检测器不可用、裁剪失败、音频设备/录制失败、分辨率未知等）；`no_face` / `no_audio` 只表示**业务性缺失**（确实没检出人脸、音频确实静音或过短）。

```
开始
 ├─ 设备 / 帧 / 存储 / 技术故障，且无任何可用产物 ─────> error
 ├─ 人脸分支 ─┬─ 检测到 + 裁剪成功 ─> face.jpg
 │            ├─ 未检出人脸 ───────> warning: no_face
 │            ├─ 检测器全不可用 ───> warning: detector_unavailable
 │            └─ 裁剪 / 写入失败 ──> warning: crop_failed
 └─ 音频分支 ─┬─ 录制成功 ─────────> audio.wav
              ├─ 静音 / 过短 ──────> warning: audio_too_short
              └─ 设备 / 录制失败 ──> warning: audio_device_unavailable / audio_record_failed

合成：
  face.jpg + audio.wav + 无 warning   → ok
  face.jpg + audio.wav + 有 warning   → partial
  face.jpg 单路 + 音频业务性缺失      → no_audio
  face.jpg 单路 + 音频技术性故障      → partial
  audio.wav 单路 + 未检出人脸         → no_face
  audio.wav 单路 + 人脸技术性故障     → partial
  两路皆无 + 无致命异常               → no_face_no_audio
  两路皆无 + 致命异常                 → error
```

### 3.1 状态 — 产物 — `sessions.status` — 是否进分析

| `capture_status` | `face.jpg` | `audio.wav` | `coverage` | `sessions.status` | 进分析 | `error` | `warnings` |
|---|---|---|---|---|---|---|---|
| `ok` | 有 | 有 | `both` | `captured` | 是 | `null` | 空数组 |
| `partial` | 至少一路 | 视分支而定 | `both` / `face_only` / `audio_only` | `captured` | 是（可能 `degraded`） | `null` | 非空 |
| `no_face` | 无 | 有 | `audio_only` | `captured` | 是（仅音频路） | `null` | 含 `no_face` |
| `no_audio` | 有 | 无 | `face_only` | `captured` | 是（仅表情路） | `null` | 含 `audio_too_short` |
| `no_face_no_audio` | 无 | 无 | `null` | `failed` | 否 | `null` | 非空 |
| `error` | 无 | 无 | `null` | `failed` | 否 | 非 `null` | 其余原因（可为空） |
| `error`（组合：`no_face` + `audio_device_unavailable`） | 无 | 无 | `null` | `failed` | 否 | `audio_device_unavailable` | 含 `no_face` |

判级规则（按顺序执行）：

1. 零产物 + 存在设备级/技术级 code → `error`（设备级/技术级 = 除 `no_face`、`audio_too_short`、`camera_resolution_unknown` 外的所有 code）；
2. 零产物 + 全部为业务级 code（`no_face` / `audio_too_short`）→ `no_face_no_audio`；
3. 任一路有产物 → 两路齐全时按 warning 有无取 `ok` / `partial`；仅单路时按业务性缺失取 `no_face` / `no_audio`，按技术性故障取 `partial`。

`coverage` 双向断言：

- `sessions.status == captured` ⇒ `coverage ∈ {both, face_only, audio_only}`；
- `sessions.status == failed` ⇒ `coverage == null`。

### 3.2 失败会话语义

- `capture_status in (no_face_no_audio, error)` 时 `sessions.status=failed`；
- **保留 `meta.json`** 及其所在会话目录用于排查，不因失败删除；
- 失败会话**不进入分析管线**、**不计入七日复盘**、**不生成复核工单**；
- 重试必须使用新的 `session_id`，不复用失败目录；
- 失败会话的留存与清理遵循 [db.md](./db.md) 第 10 节，采集层不主动删除。

## 4. `meta.json` 结构

```json
{
  "schema_version": "capture@1.2",
  "session_id": "8f3c1b2e-4a5d-4c6e-9f10-1a2b3c4d5e6f",
  "subject_id": "3b1e7c90-2f4a-4d51-8c6b-7d9e0f1a2b3c",
  "capture_status": "ok",
  "coverage": "both",
  "started_at": "2026-11-23T10:12:03+08:00",
  "finished_at": "2026-11-23T10:12:36+08:00",
  "device": {
    "camera_index": 0,
    "camera_resolution": [1280, 720],
    "mic_index": 0
  },
  "face": {
    "detector": "mediapipe",
    "bbox": [412, 168, 236, 240],
    "crop_margin": 0.25,
    "output_size": [300, 300],
    "jpeg_quality": 85,
    "face_path": "subjects/3b1e7c90-2f4a-4d51-8c6b-7d9e0f1a2b3c/sessions/8f3c1b2e-4a5d-4c6e-9f10-1a2b3c4d5e6f/face.jpg"
  },
  "audio": {
    "recorded": true,
    "duration_sec": 30.0,
    "sample_rate": 16000,
    "channels": 1,
    "bit_depth": 16,
    "format": "wav",
    "speech_ratio": 0.62,
    "audio_path": "subjects/3b1e7c90-2f4a-4d51-8c6b-7d9e0f1a2b3c/sessions/8f3c1b2e-4a5d-4c6e-9f10-1a2b3c4d5e6f/audio.wav"
  },
  "warnings": [],
  "error": null
}
```

失败示例（节选）：

```json
{
  "capture_status": "error",
  "coverage": null,
  "face": null,
  "warnings": [],
  "error": { "code": "camera_unavailable", "reason": "摄像头打不开", "detail": null }
}
```

### 4.1 字段说明

| 字段 | 类型 | 必有 | 说明 |
|---|---|---|---|
| `schema_version` | string | 是 | 固定 `capture@1.2` |
| `session_id` | string(uuid) | 是 | 与 `sessions.id` 一致 |
| `subject_id` | string(uuid) | 是 | 与 `subjects.id` 一致 |
| `capture_status` | enum | 是 | 六值，见第 3 节 |
| `coverage` | enum\|null | 是（键必须存在） | `both` / `face_only` / `audio_only`；`captured` 时必为三值之一，`failed` 时恒为 `null` |
| `started_at` / `finished_at` | string(date-time) | 是 | 带时区，ISO 8601 |
| `device.camera_index` | int | 是 | 实际使用的索引，失败时为请求值 |
| `device.camera_resolution` | [int,int] | 是 | local 从 `CAP_PROP_FRAME_WIDTH` / `CAP_PROP_FRAME_HEIGHT` 读取；取不到时填 `[0, 0]` 并记 warning `camera_resolution_unknown` |
| `device.mic_index` | int | 是 | 麦克风索引 |
| `face` | object\|null | 是 | `null` 表示无人脸产物；结构见下 |
| `face.detector` | enum | `face` 非 `null` 时必填 | `mediapipe` / `opencv_dnn` / `haar` |
| `face.bbox` | [int,int,int,int] | `face` 非 `null` 时必填 | 原图坐标 `x, y, w, h` |
| `face.crop_margin` | float | `face` 非 `null` 时必填 | 默认 `0.25` |
| `face.output_size` | [int,int] | `face` 非 `null` 时必填 | 恒等于 `[output_side, output_side]`（当前 `[300, 300]`），正方形 |
| `face.jpeg_quality` | int | `face` 非 `null` 时必填 | 默认 `85` |
| `face.face_path` | string | `face` 非 `null` 时必填 | 相对路径 |
| `audio.recorded` | bool | 是 | 是否写入 wav |
| `audio.duration_sec` | float | 是 | 实际时长 |
| `audio.sample_rate` | int | 是 | 固定 `16000` |
| `audio.channels` | int | 是 | 固定 `1` |
| `audio.bit_depth` | int | 是 | 固定 `16` |
| `audio.speech_ratio` | float | 是 | 有效语音占比 `0..1`，低于 `MIN_SPEECH_RATIO` 判 `audio_too_short` |
| `audio.audio_path` | string | 否 | 相对路径 |
| `warnings` | array | 是 | 恒为数组；元素 `{ "code": ..., "reason": ..., "detail": null }`，结构见 4.2 |
| `error` | object\|null | 是 | **仅 `capture_status == error` 时非 `null`**；其余状态恒为 `null`，失败原因放 `warnings` |

### 4.2 `capture_code` 枚举（`error` 与 `warnings` 共用）

| code | 可出现在 `error` | 可出现在 `warnings` | 含义 |
|---|---|---|---|
| `camera_unavailable` | 是 | 否 | 摄像头设备不存在或不可用 |
| `camera_open_failed` | 是 | 否 | 设备存在但打开失败 |
| `invalid_frame` | 是 | 否 | 抓到的帧为空或尺寸非法 |
| `camera_resolution_unknown` | 否 | 是 | 分辨率读取不到，`camera_resolution` 填 `[0, 0]` |
| `detector_unavailable` | 是 | 是 | 三级检测器全部不可用；音频可用时降级为 `partial` + warning |
| `crop_failed` | 是 | 是 | 裁剪或写图失败；音频可用时降级为 `partial` + warning |
| `no_face` | 否 | 是 | 未检测到人脸（业务结果） |
| `audio_device_unavailable` | 是 | 是 | 麦克风不存在或不可用；人脸可用时降级为 `partial` + warning |
| `audio_record_failed` | 是 | 是 | 录音失败；人脸可用时降级为 `partial` + warning |
| `audio_too_short` | 否 | 是 | 录音时长不足或有效语音占比过低 |
| `storage_write_failed` | 是 | 是 | 目录或文件写入失败；已有可用产物时降级为 `partial` + warning |
| `unknown` | 是 | 是 | 未归类异常 |

约束：

- `code` 是**稳定枚举**，只增不改，程序分支、告警与统计一律以此为准；
- `reason` 是面向人的可读文案，允许调整措辞；**禁止写入堆栈、原始帧内容或转写文本**，也**禁止在测试与断言中依赖其字符串**；
- 同一 `code` 在 `warnings` 中至多出现一次，多条原因合并进 `reason` / `detail`；
- `error` 只在 `capture_status == error` 时出现；其余非致命问题一律进 `warnings`；
- `meta.error.code` 只记录触发 `error` 的那个设备级/技术级 code，其余原因写入 `warnings`；完整顺序以 `CaptureResult.codes` 为准。

## 5. 函数签名

```python
from dataclasses import dataclass, field
from typing import Literal, Optional

CaptureStatus = Literal["ok", "partial", "no_face", "no_audio", "no_face_no_audio", "error"]


@dataclass
class FrameResult:
    status: Literal["ok", "error"]
    frame: Optional["np.ndarray"]     # BGR，仅在内存中
    reason: Optional[str] = None      # 可读文案，禁止用于断言
    resolution: Optional[tuple[int, int]] = None


@dataclass
class FaceResult:
    status: Literal["ok", "no_face", "error"]
    bbox: Optional[tuple[int, int, int, int]] = None   # x, y, w, h
    detector: Optional[Literal["mediapipe", "opencv_dnn", "haar"]] = None
    reason: Optional[str] = None      # 可读文案，禁止用于断言


@dataclass
class AudioResult:
    status: Literal["ok", "no_audio", "error"]
    wav_bytes: Optional[bytes] = None
    duration_sec: float = 0.0
    speech_ratio: float = 0.0
    reason: Optional[str] = None      # 可读文案，禁止用于断言


@dataclass
class CaptureResult:
    capture_status: CaptureStatus
    meta: dict                       # 即 meta.json 内容
    face_path: Optional[str] = None  # 相对路径
    audio_path: Optional[str] = None
    codes: list[str] = field(default_factory=list)  # 首条为最致命 code，其余按发生顺序


def capture_frame(
    device_index: int = 0,
    resolution: tuple[int, int] = (1280, 720),
    warmup_frames: int = 5,
    timeout_sec: float = 5.0,
) -> FrameResult: ...


def detect_face(frame: "np.ndarray") -> FaceResult: ...


def crop_face(
    frame: "np.ndarray",
    bbox: tuple[int, int, int, int],
    margin: float = 0.25,
    output_side: int = 300,
    jpeg_quality: int = 85,
) -> bytes | None: ...   # 失败返回 None，由调用方记 crop_failed，不抛异常


def record_audio(
    duration_sec: float = 30.0,
    sample_rate: int = 16000,
    channels: int = 1,
    mic_index: int = 0,
    min_speech_ratio: float = 0.05,
) -> AudioResult: ...


def run_capture_session(
    subject_id: str,
    session_id: str,
    storage_root: str | "Path",
    device_index: int = 0,
    mic_index: int = 0,
    duration_sec: float = 30.0,
    resolution: tuple[int, int] = (1280, 720),
) -> CaptureResult: ...
```

### 5.1 参数默认值

| 参数 | 默认 | 可配置来源 |
|---|---|---|
| `device_index` | `0` | `CAPTURE_DEVICE_INDEX` |
| `mic_index` | `0` | `CAPTURE_MIC_INDEX` |
| `duration_sec` | `30.0` | `CAPTURE_DURATION_SEC` |
| `resolution` | `(1280, 720)` | `CAPTURE_RESOLUTION` |
| `margin` | `0.25` | 契约固定 |
| `output_side` | `300` | 契约固定（正方形边长，不取最长边语义） |
| `jpeg_quality` | `85` | 契约固定 |
| `sample_rate` | `16000` | 契约固定 |
| `min_speech_ratio` | `0.05` | `CAPTURE_MIN_SPEECH_RATIO` |

## 6. 人脸检测回退顺序

```
MediaPipe Face Detection
    ↓ 不可用（未安装 / 初始化失败）
OpenCV DNN（res10_300x300_ssd）
    ↓ 不可用
Haar Cascade（haarcascade_frontalface_default.xml）
    ↓ 可用但未检出人脸
capture_code = "no_face"
    ↓ 三级全部不可用
capture_code = "detector_unavailable"
```

规则：

- 回退过程写 `face.detector` 实际命中的检测器；
- 三级全部不可用：音频可用 → `partial` + warning `detector_unavailable`；音频不可用 → `error` + code `detector_unavailable`；
- 检测器可用但确实没检出人脸 → `no_face`（业务结果），不得记为 `detector_unavailable`；
- 一帧内检测到多张脸 → 取面积最大者，其余忽略（不报错）。

## 7. 采集流程决策表

| 步骤 | 结果 | `capture_status` | `code` 位置与取值 | 产物 |
|---|---|---|---|---|
| 打开摄像头 | 失败 | `error` | `error.code = camera_unavailable` | 无 |
| 抓帧 | 失败 | `error` | `error.code = invalid_frame` | 无 |
| 检测器全不可用 | 音频可用 | `partial` | warning `detector_unavailable` | 仅 `audio.wav` |
| 检测器全不可用 | 音频不可用 | `error` | `error.code = detector_unavailable` | 无 |
| 检测人脸 | 未检出 | `no_face` | warning `no_face` | 仅 `audio.wav` |
| 裁剪 / 写图 | 失败 | `partial` / `error` | warning `crop_failed` / `error.code = crop_failed` | 视音频分支 |
| 打开麦克风 | 失败 | `partial` / `error` | warning `audio_device_unavailable` / `error.code = audio_device_unavailable` | 视人脸分支 |
| 人脸未检出 + 麦克风不可用 | — | `error` | `error.code = audio_device_unavailable`，warning `no_face` | 无 |
| 录音 | 失败 | `partial` / `error` | warning `audio_record_failed` / `error.code = audio_record_failed` | 视人脸分支 |
| 录音 | 静音 / 过短 | `no_audio` | warning `audio_too_short` | 仅 `face.jpg` |
| 分辨率 | 取不到 | 按其它分支 | warning `camera_resolution_unknown` | 视分支 |
| 两路业务性缺失 | — | `no_face_no_audio` | warnings `no_face` + `audio_too_short` | 无 |
| 全部成功且无 warning | — | `ok` | 无 | `face.jpg` + `audio.wav` |
| 全部成功但有 warning | — | `partial` | 对应 warning | 视分支 |

## 8. 硬性规则

1. 只保存裁剪后的 `face.jpg`，原始帧不落盘、不写日志、不进异常 `detail`。
2. 所有异常转 `capture_status` + `codes`（`CaptureResult.codes`），采集函数不向上抛未捕获异常。
3. 采集函数必须可注入设备索引、时长、输出根目录，测试用假帧 / 假音频替换。
4. 本模块不引入推理依赖（不 import `app.analysis`）。
5. `meta.json` 必须在任何返回路径下写出；**唯一例外**是存储不可写导致无法落盘，此时 `meta` 通过 `CaptureResult.meta` 返回，并置 `capture_status=error` + `error.code=storage_write_failed`。
6. **断言规则**：失败语义断言只允许 `capture_status`、`error.code`、`warnings[].code` 与文件存在性；**一律禁止断言 `reason` 字符串**。结构、参数与几何校验单独列在 9.1，不得混入失败用例。

## 9. 测试要求（`tests/test_capture/`）

| 用例 | 输入 | 期望（只断言 code / capture_status / 文件） |
|---|---|---|
| 正常采集 | 假帧含 1 张人像 + 30s 假音频 | `capture_status=ok`；`warnings` 为空；三文件齐全 |
| 无人脸 | 纯色假帧 | `capture_status=no_face`；`meta.face=null`；`warnings[].code` 含 `no_face`；`face.jpg` 不存在 |
| 人脸过小 | bbox 面积 < 1% | `capture_status=no_face`；`meta.face=null` |
| 多脸 | 假帧含 2 张脸 | `capture_status=ok`；`face.jpg` 存在 |
| 静音音频 | 全零 PCM | `capture_status=no_audio`；`warnings[].code` 含 `audio_too_short`；`audio.wav` 不存在 |
| 设备不可用 | `device_index=99` | `capture_status=error`；`error.code=camera_unavailable`；不抛异常 |
| 存储不可写 | 只读目录 | `capture_status=error`；`error.code=storage_write_failed` |
| 检测器全不可用 + 音频正常 | 屏蔽三级检测器 | `capture_status=partial`；`warnings[].code` 含 `detector_unavailable`；`audio.wav` 存在 |
| 检测器全不可用 + 音频失败 | 屏蔽三级检测器 + 静音 | `capture_status=error`；`error.code=detector_unavailable` |
| 裁剪失败 + 音频正常 | 强制裁剪异常 | `capture_status=partial`；`warnings[].code` 含 `crop_failed` |
| 麦克风不可用 + 人脸正常 | `mic_index=99` | `capture_status=partial`；`warnings[].code` 含 `audio_device_unavailable` |
| 无人脸 + 麦克风不可用 | 纯色假帧 + `mic_index=99` | `capture_status=error`；`error.code=audio_device_unavailable`；`warnings[].code` 含 `no_face`；无产物 |

规则：**用例表只断言 `capture_status`、`error.code` / `warnings[].code` 与文件存在性，禁止断言 `reason` 文案**；新增用例同样适用。

### 9.1 结构与几何校验（不属于失败语义断言）

| 检查 | 期望 |
|---|---|
| `coverage` 存在性 | 键必须存在；有产物时为 `both` / `face_only` / `audio_only`，无产物为 `null` |
| `coverage` 双向断言 | `sessions.status=captured` ⇒ 三值之一；`sessions.status=failed` ⇒ `null` |
| `meta.face` 结构 | 无人脸时为 `null`；非 `null` 时含 `detector` / `crop_margin` / `output_size` / `jpeg_quality` / `face_path` |
| 裁剪输出 | `face.output_size == [300, 300]`，`face.jpg` 实际边长 `300` |
| 裁剪区域 | `margin=0` / `0.25` 下输出均为 `300×300` |
| 分辨率来源 | 正常设备 `camera_resolution == [1280, 720]` |
| 分辨率缺失 | `camera_resolution == [0, 0]` 且 `warnings[].code` 含 `camera_resolution_unknown` |

## 10. 已知未覆盖项

| 项 | 说明 |
|---|---|
| 活体检测 | 本轮不做，正式版需评估 |
| 多人同框去重 | 仅取最大脸，不识别"是否本人" |
| 设备热插拔 | 不做重连，需重启采集 |
| 音频降噪 | 不做，交下游模型处理 |
