"""采集会话编排：抓帧 → 检测 → 裁剪 → 录音 → 写 meta.json。

状态机与字段严格对齐 `docs/contracts/capture.md`（capture@1.2）：
- 六值 `capture_status`：ok / partial / no_face / no_audio / no_face_no_audio / error；
- `coverage` 有产物时为 both / face_only / audio_only，失败态为 null；
- `meta.error` 仅在“零产物且存在设备级/技术级 code”时为非 null；
- 其余失败原因一律进 `meta.warnings[]`，裁剪失败统一记 `crop_failed`。
"""

from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple, Union

from .audio import _encode_wav, record_audio
from .camera import capture_frame
from .config import (
    CROP_MARGIN,
    DEFAULT_MIN_SPEECH_RATIO,
    JPEG_QUALITY,
    OUTPUT_SIDE,
    SPEECH_FRAME_MS,
)
from .face import crop_face, detect_face
from .models import AudioResult, CaptureResult, FaceResult, FrameResult

SCHEMA_VERSION = "capture@1.2"
SAMPLE_RATE = 16000
CHANNELS = 1
BIT_DEPTH = 16

# 业务性缺失：只表示“确实没检出 / 音频确实过短”，不作为 error 的触发 code
_BUSINESS_CODES = frozenset({"no_face", "audio_too_short"})
# 零产物时不足以判 error 的 code（分辨率未知属于非致命降级）
_ZERO_ARTIFACT_NON_FATAL = frozenset(
    {"no_face", "audio_too_short", "camera_resolution_unknown"}
)
_FRAME_ERROR_CODES = frozenset(
    {"camera_unavailable", "camera_open_failed", "invalid_frame"}
)
_AUDIO_DEVICE_REASONS = frozenset(
    {
        "audio_device_unavailable",
        "mic_unavailable",
        "mic_not_found",
        "sounddevice_unavailable",
        "device_unavailable",
    }
)

_REASON_TEXT = {
    "camera_unavailable": "摄像头设备不存在或不可用",
    "camera_open_failed": "摄像头打开失败",
    "invalid_frame": "抓取到的画面为空或尺寸非法",
    "camera_resolution_unknown": "无法读取摄像头分辨率",
    "detector_unavailable": "人脸检测器全部不可用",
    "crop_failed": "人脸裁剪或写图失败",
    "no_face": "未检测到可用人脸",
    "audio_device_unavailable": "麦克风设备不存在或不可用",
    "audio_record_failed": "音频录制失败",
    "audio_too_short": "录音时长不足或有效语音占比过低",
    "storage_write_failed": "会话目录或文件写入失败",
    "unknown": "未归类的采集异常",
}


def _now() -> str:
    return datetime.now().astimezone().isoformat()


def _reason(code: Optional[str]) -> str:
    if not code:
        return ""
    return _REASON_TEXT.get(code, "采集出现异常")


def _relative_path(subject_id: str, session_id: str, name: str) -> str:
    # 库中只存相对路径，统一使用正斜杠，Windows 下也不例外
    return "/".join(("subjects", subject_id, "sessions", session_id, name))


def _dedup(codes) -> list:
    seen = set()
    ordered = []
    for code in codes:
        if code in seen:
            continue
        seen.add(code)
        ordered.append(code)
    return ordered


@dataclass
class _State:
    """本次采集已发生的问题与已落盘产物。"""

    issues: list[str] = field(default_factory=list)  # 按发生顺序、已去重
    details: dict = field(default_factory=dict)
    face_written: bool = False
    audio_written: bool = False
    face_meta: Optional[dict] = None
    face_only: bool = False


def _add_issue(state: _State, code: str, detail=None) -> None:
    """同一 code 至多记录一次；多条原因合并进 detail 的列表表示。"""
    if code not in state.issues:
        state.issues.append(code)
        if detail is not None:
            state.details[code] = detail
    elif detail is not None:
        existing = state.details.get(code)
        if existing is None:
            state.details[code] = detail
        elif isinstance(existing, list):
            if detail not in existing:
                existing.append(detail)
        elif existing != detail:
            state.details[code] = [existing, detail]


def _frame_error_code(reason: Optional[str]) -> str:
    # camera 侧以 "code: detail" 形式带回诊断信息，code 仍是稳定枚举
    code = str(reason or "").split(":", 1)[0].strip()
    if code in _FRAME_ERROR_CODES:
        return code
    return "invalid_frame"


def _frame_error_detail(reason: Optional[str]) -> Optional[str]:
    text = str(reason or "")
    _, separator, detail = text.partition(":")
    detail = detail.strip()
    return detail if separator and detail else None


def _audio_error_code(reason: Optional[str]) -> str:
    if reason in _AUDIO_DEVICE_REASONS:
        return "audio_device_unavailable"
    return "audio_record_failed"


def _base_meta(
    subject_id: str,
    session_id: str,
    device_index: int,
    mic_index: int,
    started_at: str,
) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "session_id": session_id,
        "subject_id": subject_id,
        "capture_status": None,
        "coverage": None,
        "started_at": started_at,
        "finished_at": None,
        "device": {
            "camera_index": int(device_index),
            "camera_resolution": [0, 0],
            "mic_index": int(mic_index),
        },
        "face": None,
        "audio": {
            "recorded": False,
            "duration_sec": 0.0,
            "sample_rate": SAMPLE_RATE,
            "channels": CHANNELS,
            "bit_depth": BIT_DEPTH,
            "format": "wav",
            "speech_ratio": 0.0,
            "audio_path": None,
        },
        "warnings": [],
        "error": None,
    }


def _compute(state: _State):
    """按契约 §3 判级，返回 status / codes / coverage / warning_codes / error_code。"""
    artifact_count = int(state.face_written) + int(state.audio_written)
    error_code: Optional[str] = None

    if state.face_only:
        if state.face_written:
            # face_only 的正常完成态；音频未采集不属于缺失或降级。
            status = "ok"
        else:
            fatal = [c for c in state.issues if c not in _ZERO_ARTIFACT_NON_FATAL]
            if fatal:
                status = "error"
                error_code = fatal[0]
            else:
                status = "no_face"
    elif artifact_count == 0:
        fatal = [c for c in state.issues if c not in _ZERO_ARTIFACT_NON_FATAL]
        if fatal:
            status = "error"
            error_code = fatal[0]
        else:
            status = "no_face_no_audio"
    elif artifact_count == 2:
        status = "ok" if not state.issues else "partial"
    else:
        degraded = [c for c in state.issues if c not in _BUSINESS_CODES]
        if degraded:
            status = "partial"
        elif state.face_written:
            status = "no_audio"
        else:
            status = "no_face"

    if status == "error":
        warning_codes = [c for c in _dedup(state.issues) if c != error_code]
    else:
        warning_codes = _dedup(state.issues)

    codes = ([error_code] + warning_codes) if error_code else list(warning_codes)

    if state.face_written and state.audio_written:
        coverage = "both"
    elif state.face_written:
        coverage = "face_only"
    elif state.audio_written:
        coverage = "audio_only"
    else:
        coverage = None
    if status in ("no_face_no_audio", "error"):
        coverage = None

    return status, codes, coverage, warning_codes, error_code


def _warning_entries(state: _State, codes) -> list:
    return [
        {"code": code, "reason": _reason(code), "detail": state.details.get(code)}
        for code in codes
    ]


def _apply_state(meta: dict, state: _State):
    status, codes, coverage, warning_codes, error_code = _compute(state)
    meta["capture_status"] = status
    meta["coverage"] = coverage
    meta["face"] = state.face_meta if state.face_written else None
    meta["warnings"] = _warning_entries(state, warning_codes)
    meta["error"] = (
        {
            "code": error_code,
            "reason": _reason(error_code),
            "detail": state.details.get(error_code),
        }
        if error_code
        else None
    )
    return status, codes, error_code


def _finalize(meta: dict, state: _State, session_dir: Path) -> CaptureResult:
    """补全状态并写出 meta.json；写不进去时按 §2 / §8.5 收敛。"""
    status, codes, error_code = _apply_state(meta, state)
    meta["finished_at"] = _now()

    try:
        session_dir.mkdir(parents=True, exist_ok=True)
        (session_dir / "meta.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except OSError:
        # 存储不可写：仍有产物按 §2 降级；零产物按 §8.5 收敛为 error
        _add_issue(state, "storage_write_failed")
        status, codes, error_code = _apply_state(meta, state)
        meta["finished_at"] = _now()

    face_path = None
    if state.face_written and state.face_meta:
        face_path = state.face_meta.get("face_path")
    audio_path = meta["audio"].get("audio_path") if state.audio_written else None

    return CaptureResult(
        capture_status=status,
        meta=meta,
        face_path=face_path,
        audio_path=audio_path,
        codes=codes,
    )


def _capture_face(
    meta: dict,
    state: _State,
    frame,
    subject_id: str,
    session_id: str,
    session_dir: Path,
) -> None:
    """人脸分支：检测 → 裁剪 → 写 face.jpg；失败只记 code，不抛异常。"""
    try:
        face_result = detect_face(frame)
    except Exception:
        face_result = FaceResult(status="error", reason="detector_unavailable")

    if face_result.status == "error":
        code = (
            "invalid_frame"
            if face_result.reason == "invalid_frame"
            else "detector_unavailable"
        )
        _add_issue(state, code)
        return
    if face_result.status != "ok" or face_result.bbox is None:
        _add_issue(state, "no_face")
        return

    jpeg_bytes = crop_face(
        frame,
        face_result.bbox,
        margin=CROP_MARGIN,
        output_side=OUTPUT_SIDE,
        jpeg_quality=JPEG_QUALITY,
    )
    if not jpeg_bytes:
        _add_issue(state, "crop_failed")
        return

    try:
        (session_dir / "face.jpg").write_bytes(jpeg_bytes)
    except OSError:
        _add_issue(state, "storage_write_failed")
        return

    face_path = _relative_path(subject_id, session_id, "face.jpg")
    state.face_written = True
    state.face_meta = {
        "detector": face_result.detector,
        "bbox": [int(value) for value in face_result.bbox],
        "crop_margin": CROP_MARGIN,
        "output_size": [int(OUTPUT_SIDE), int(OUTPUT_SIDE)],
        "jpeg_quality": JPEG_QUALITY,
        "face_path": face_path,
    }


def _store_audio_result(
    meta: dict,
    state: _State,
    subject_id: str,
    session_id: str,
    session_dir: Path,
    audio: AudioResult,
) -> None:
    """统一应用音频结果；只有成功返回后才写 audio.wav。"""
    meta["audio"]["duration_sec"] = round(
        float(getattr(audio, "duration_sec", 0.0) or 0.0), 3
    )
    meta["audio"]["speech_ratio"] = round(
        float(getattr(audio, "speech_ratio", 0.0) or 0.0), 4
    )

    if audio.status == "no_audio":
        _add_issue(state, "audio_too_short")
        return
    if audio.status != "ok" or audio.wav_bytes is None:
        _add_issue(state, _audio_error_code(audio.reason))
        return

    try:
        (session_dir / "audio.wav").write_bytes(audio.wav_bytes)
    except OSError:
        _add_issue(state, "storage_write_failed")
        return

    state.audio_written = True
    meta["audio"]["recorded"] = True
    meta["audio"]["audio_path"] = _relative_path(subject_id, session_id, "audio.wav")


def _capture_audio(
    meta: dict,
    state: _State,
    subject_id: str,
    session_id: str,
    session_dir: Path,
    mic_index: int,
    duration_sec: float | None,
    stop_event: threading.Event | None = None,
) -> None:
    """音频分支：录音 → 写 audio.wav；失败只记 code，不抛异常。"""
    try:
        if duration_sec is None:
            audio = record_audio(
                duration_sec=None,
                mic_index=mic_index,
                min_speech_ratio=DEFAULT_MIN_SPEECH_RATIO,
                stop_event=stop_event,
            )
        else:
            # 保持定时模式的既有调用形态，兼容已有测试替身与调用方。
            audio = record_audio(
                duration_sec=duration_sec,
                mic_index=mic_index,
                min_speech_ratio=DEFAULT_MIN_SPEECH_RATIO,
            )
    except Exception:
        audio = AudioResult(status="error", reason="audio_record_failed")

    _store_audio_result(
        meta, state, subject_id, session_id, session_dir, audio
    )


def _capture_fake_face(
    meta: dict,
    state: _State,
    subject_id: str,
    session_id: str,
    session_dir: Path,
) -> None:
    """生成与既有假采集一致的人脸产物，不触达真实摄像头。"""
    bbox = (
        OUTPUT_SIDE // 4,
        OUTPUT_SIDE // 4,
        OUTPUT_SIDE // 2,
        OUTPUT_SIDE // 2,
    )
    try:
        import numpy as np

        frame = np.zeros((OUTPUT_SIDE, OUTPUT_SIDE, 3), dtype=np.uint8)
        jpeg_bytes = crop_face(
            frame,
            bbox,
            margin=CROP_MARGIN,
            output_side=OUTPUT_SIDE,
            jpeg_quality=JPEG_QUALITY,
        )
    except Exception:
        jpeg_bytes = None

    if not jpeg_bytes:
        _add_issue(state, "crop_failed")
        return

    try:
        (session_dir / "face.jpg").write_bytes(jpeg_bytes)
    except OSError:
        _add_issue(state, "storage_write_failed")
        return

    meta["device"]["camera_resolution"] = [OUTPUT_SIDE, OUTPUT_SIDE]
    state.face_written = True
    state.face_meta = {
        "detector": "haar",
        "bbox": [int(value) for value in bbox],
        "crop_margin": CROP_MARGIN,
        "output_size": [int(OUTPUT_SIDE), int(OUTPUT_SIDE)],
        "jpeg_quality": JPEG_QUALITY,
        "face_path": _relative_path(subject_id, session_id, "face.jpg"),
    }


def _run_fake_face_only(
    meta: dict,
    state: _State,
    subject_id: str,
    session_id: str,
    session_dir: Path,
) -> CaptureResult:
    """CAPTURE_FAKE=1 的签到采集：不触达摄像头或麦克风，仅生成假人脸产物。"""
    _capture_fake_face(meta, state, subject_id, session_id, session_dir)
    return _finalize(meta, state, session_dir)


def _fake_manual_audio(duration_sec: float) -> AudioResult:
    """按手动录音实际等待时长生成确定性的假语音 WAV。"""
    try:
        import numpy as np

        total_frames = max(int(float(duration_sec) * SAMPLE_RATE), 0)
    except Exception:
        return AudioResult(status="error", reason="audio_record_failed")

    if total_frames <= 0:
        return AudioResult(status="no_audio", reason="empty_audio")

    timeline = np.arange(total_frames, dtype=np.float64) / SAMPLE_RATE
    pcm = np.rint(np.sin(2 * np.pi * 440 * timeline) * 0.25 * 32767)
    data = pcm.astype(np.int16).reshape(-1, 1)
    duration = round(total_frames / SAMPLE_RATE, 3)
    frame_length = max(int(SAMPLE_RATE * SPEECH_FRAME_MS / 1000), 1)
    speech_ratio = 1.0 if total_frames >= frame_length else 0.0

    if speech_ratio < DEFAULT_MIN_SPEECH_RATIO:
        return AudioResult(
            status="no_audio",
            duration_sec=duration,
            speech_ratio=speech_ratio,
            reason="speech_ratio_too_low",
        )
    return AudioResult(
        status="ok",
        wav_bytes=_encode_wav(data, SAMPLE_RATE, CHANNELS),
        duration_sec=duration,
        speech_ratio=speech_ratio,
    )


def _run_fake_both_manual(
    meta: dict,
    state: _State,
    subject_id: str,
    session_id: str,
    session_dir: Path,
    stop_event: threading.Event,
) -> CaptureResult:
    """假采集手动闭环：先写人脸，等待 stop 后才生成并保存音频。"""
    _capture_fake_face(meta, state, subject_id, session_id, session_dir)
    recording_started_at = time.monotonic()
    stop_event.wait()
    elapsed = max(time.monotonic() - recording_started_at, 0.0)
    audio = _fake_manual_audio(elapsed)
    _store_audio_result(
        meta, state, subject_id, session_id, session_dir, audio
    )
    return _finalize(meta, state, session_dir)


def _run(
    meta: dict,
    state: _State,
    subject_id: str,
    session_id: str,
    session_dir: Path,
    device_index: int,
    mic_index: int,
    duration_sec: float | None,
    resolution: Tuple[int, int],
    stop_event: threading.Event | None = None,
) -> CaptureResult:
    try:
        frame_result = capture_frame(device_index=device_index, resolution=resolution)
    except Exception:
        frame_result = FrameResult(status="error", frame=None, reason="invalid_frame")

    if frame_result.status != "ok" or frame_result.frame is None:
        # 摄像头 / 帧故障属于零产物的设备级故障，直接收敛为 error，不再录音
        _add_issue(
            state,
            _frame_error_code(frame_result.reason),
            detail=_frame_error_detail(frame_result.reason),
        )
        return _finalize(meta, state, session_dir)

    resolution_value = frame_result.resolution
    if (
        resolution_value
        and len(resolution_value) == 2
        and int(resolution_value[0]) > 0
        and int(resolution_value[1]) > 0
    ):
        meta["device"]["camera_resolution"] = [
            int(resolution_value[0]),
            int(resolution_value[1]),
        ]
    else:
        meta["device"]["camera_resolution"] = [0, 0]
        _add_issue(state, "camera_resolution_unknown")

    _capture_face(
        meta, state, frame_result.frame, subject_id, session_id, session_dir
    )
    if not state.face_only:
        _capture_audio(
            meta,
            state,
            subject_id,
            session_id,
            session_dir,
            mic_index,
            duration_sec,
            stop_event=stop_event,
        )
    return _finalize(meta, state, session_dir)


def run_capture_session(
    subject_id: str,
    session_id: str,
    storage_root: Union[str, Path],
    device_index: int = 0,
    mic_index: int = 0,
    duration_sec: float | None = 30.0,
    resolution: Tuple[int, int] = (1280, 720),
    mode: str = "both",
    stop_event: threading.Event | None = None,
) -> CaptureResult:
    """执行一次采集；设备与存储失败均收敛为 CaptureResult。"""
    started_at = _now()
    session_dir = (
        Path(storage_root)
        / "subjects"
        / subject_id
        / "sessions"
        / session_id
    )
    meta = _base_meta(subject_id, session_id, device_index, mic_index, started_at)
    face_only = mode == "face_only"
    manual = mode == "both" and duration_sec is None
    if face_only:
        # 默认 both 的 meta 结构保持原样，仅签到模式追加模式标记。
        meta["mode"] = "face_only"
    if manual:
        meta["audio"]["manual"] = True
    state = _State(face_only=face_only)

    if mode not in ("both", "face_only"):
        _add_issue(state, "unknown", detail="invalid_mode")
        return _finalize(meta, state, session_dir)
    if manual and stop_event is None:
        raise ValueError("stop_event is required when duration_sec is None")

    try:
        session_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        _add_issue(state, "storage_write_failed")
        return _finalize(meta, state, session_dir)

    try:
        fake = os.environ.get("CAPTURE_FAKE") == "1"
        if face_only and fake:
            return _run_fake_face_only(
                meta=meta,
                state=state,
                subject_id=subject_id,
                session_id=session_id,
                session_dir=session_dir,
            )
        if manual and fake:
            return _run_fake_both_manual(
                meta=meta,
                state=state,
                subject_id=subject_id,
                session_id=session_id,
                session_dir=session_dir,
                stop_event=stop_event,
            )
        return _run(
            meta=meta,
            state=state,
            subject_id=subject_id,
            session_id=session_id,
            session_dir=session_dir,
            device_index=device_index,
            mic_index=mic_index,
            duration_sec=duration_sec,
            resolution=resolution,
            stop_event=stop_event,
        )
    except Exception:
        _add_issue(state, "unknown")
        return _finalize(meta, state, session_dir)
