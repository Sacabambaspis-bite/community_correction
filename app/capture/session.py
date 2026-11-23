"""采集会话编排：抓帧 → 检测 → 裁剪 → 录音 → 写 meta.json。

状态机与字段严格对齐 `docs/contracts/capture.md`（capture@1.2）：
- 六值 `capture_status`：ok / partial / no_face / no_audio / no_face_no_audio / error；
- `coverage` 有产物时为 both / face_only / audio_only，失败态为 null；
- `meta.error` 仅在“零产物且存在设备级/技术级 code”时为非 null；
- 其余失败原因一律进 `meta.warnings[]`，裁剪失败统一记 `crop_failed`。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple, Union

from .audio import record_audio
from .camera import capture_frame
from .config import (
    CROP_MARGIN,
    DEFAULT_MIN_SPEECH_RATIO,
    JPEG_QUALITY,
    OUTPUT_SIDE,
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
    if reason in _FRAME_ERROR_CODES:
        return reason
    return "invalid_frame"


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

    if artifact_count == 0:
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
        {"code": error_code, "reason": _reason(error_code), "detail": None}
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


def _capture_audio(
    meta: dict,
    state: _State,
    subject_id: str,
    session_id: str,
    session_dir: Path,
    mic_index: int,
    duration_sec: float,
) -> None:
    """音频分支：录音 → 写 audio.wav；失败只记 code，不抛异常。"""
    try:
        audio = record_audio(
            duration_sec=duration_sec,
            mic_index=mic_index,
            min_speech_ratio=DEFAULT_MIN_SPEECH_RATIO,
        )
    except Exception:
        audio = AudioResult(status="error", reason="audio_record_failed")

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


def _run(
    meta: dict,
    state: _State,
    subject_id: str,
    session_id: str,
    session_dir: Path,
    device_index: int,
    mic_index: int,
    duration_sec: float,
    resolution: Tuple[int, int],
) -> CaptureResult:
    try:
        frame_result = capture_frame(device_index=device_index, resolution=resolution)
    except Exception:
        frame_result = FrameResult(status="error", frame=None, reason="invalid_frame")

    if frame_result.status != "ok" or frame_result.frame is None:
        # 摄像头 / 帧故障属于零产物的设备级故障，直接收敛为 error，不再录音
        _add_issue(state, _frame_error_code(frame_result.reason))
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
    _capture_audio(
        meta,
        state,
        subject_id,
        session_id,
        session_dir,
        mic_index,
        duration_sec,
    )
    return _finalize(meta, state, session_dir)


def run_capture_session(
    subject_id: str,
    session_id: str,
    storage_root: Union[str, Path],
    device_index: int = 0,
    mic_index: int = 0,
    duration_sec: float = 30.0,
    resolution: Tuple[int, int] = (1280, 720),
) -> CaptureResult:
    """执行一次完整采集，任何失败都转成 CaptureResult，不向上抛异常。"""
    started_at = _now()
    session_dir = (
        Path(storage_root)
        / "subjects"
        / subject_id
        / "sessions"
        / session_id
    )
    meta = _base_meta(subject_id, session_id, device_index, mic_index, started_at)
    state = _State()

    try:
        session_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        _add_issue(state, "storage_write_failed")
        return _finalize(meta, state, session_dir)

    try:
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
        )
    except Exception:
        _add_issue(state, "unknown")
        return _finalize(meta, state, session_dir)
