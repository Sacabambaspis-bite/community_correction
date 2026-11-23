"""采集会话编排：抓帧 → 检测 → 裁剪 → 录音 → 写 meta.json。"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple, Union

from .audio import record_audio
from .camera import capture_frame
from .config import (
    CROP_MARGIN,
    JPEG_QUALITY,
    MAX_FACE_SIDE,
    DEFAULT_MIN_SPEECH_RATIO,
)
from .face import crop_face, crop_output_size, detect_face
from .models import CaptureDependencyError, CaptureResult

SCHEMA_VERSION = "capture@1.0"
SAMPLE_RATE = 16000
CHANNELS = 1
BIT_DEPTH = 16


def _now() -> str:
    return datetime.now().astimezone().isoformat()


def _relative_path(subject_id: str, session_id: str, name: str) -> str:
    # 库中只存相对路径，统一使用正斜杠，Windows 下也不例外
    return "/".join(("subjects", subject_id, "sessions", session_id, name))


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
        "started_at": started_at,
        "finished_at": None,
        "device": {
            "camera_index": int(device_index),
            "camera_resolution": None,
            "mic_index": int(mic_index),
        },
        "face": {
            "detected": False,
            "detector": None,
            "bbox": None,
            "crop_margin": CROP_MARGIN,
            "output_size": None,
            "jpeg_quality": JPEG_QUALITY,
            "face_path": None,
        },
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
        "error": None,
    }


def _finalize(meta: dict, status: str, reason: Optional[str], session_dir: Path) -> CaptureResult:
    """补全状态与时间戳并写出 meta.json（任何分支都要写）。"""
    meta["capture_status"] = status
    meta["finished_at"] = _now()
    meta["error"] = (
        {"code": reason, "reason": reason, "detail": None}
        if status == "error" and reason
        else None
    )

    try:
        session_dir.mkdir(parents=True, exist_ok=True)
        (session_dir / "meta.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except OSError:
        meta["capture_status"] = "error"
        meta["error"] = {
            "code": "storage_unavailable",
            "reason": "storage_unavailable",
            "detail": None,
        }
        return CaptureResult(
            capture_status="error",
            meta=meta,
            face_path=meta["face"]["face_path"],
            audio_path=meta["audio"]["audio_path"],
            reason="storage_unavailable",
        )

    return CaptureResult(
        capture_status=status,
        meta=meta,
        face_path=meta["face"]["face_path"],
        audio_path=meta["audio"]["audio_path"],
        reason=reason,
    )


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
    session_dir = Path(storage_root) / "subjects" / subject_id / "sessions" / session_id
    meta = _base_meta(subject_id, session_id, device_index, mic_index, started_at)

    try:
        session_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        return _finalize(meta, "error", "storage_unavailable", session_dir)

    try:
        return _run(
            meta=meta,
            subject_id=subject_id,
            session_id=session_id,
            session_dir=session_dir,
            device_index=device_index,
            mic_index=mic_index,
            duration_sec=duration_sec,
            resolution=resolution,
        )
    except Exception:
        return _finalize(meta, "error", "internal_error", session_dir)


def _run(
    meta: dict,
    subject_id: str,
    session_id: str,
    session_dir: Path,
    device_index: int,
    mic_index: int,
    duration_sec: float,
    resolution: Tuple[int, int],
) -> CaptureResult:
    frame_result = capture_frame(device_index=device_index, resolution=resolution)
    if frame_result.resolution:
        meta["device"]["camera_resolution"] = [
            int(frame_result.resolution[0]),
            int(frame_result.resolution[1]),
        ]
    if frame_result.status != "ok" or frame_result.frame is None:
        reason = (
            "camera_unavailable"
            if frame_result.reason == "camera_unavailable"
            else "frame_capture_failed"
        )
        return _finalize(meta, "error", reason, session_dir)

    frame = frame_result.frame
    face = detect_face(frame)
    meta["face"]["detected"] = face.status == "ok"
    meta["face"]["detector"] = face.detector
    meta["face"]["bbox"] = [int(value) for value in face.bbox] if face.bbox else None
    if face.status == "error":
        return _finalize(meta, "error", face.reason or "face_detection_failed", session_dir)

    if face.status == "ok":
        try:
            output_size = crop_output_size(
                frame.shape, face.bbox, CROP_MARGIN, MAX_FACE_SIDE
            )
            jpeg_bytes = crop_face(
                frame,
                face.bbox,
                margin=CROP_MARGIN,
                max_side=MAX_FACE_SIDE,
                jpeg_quality=JPEG_QUALITY,
            )
            (session_dir / "face.jpg").write_bytes(jpeg_bytes)
            meta["face"]["output_size"] = [int(output_size[0]), int(output_size[1])]
            meta["face"]["face_path"] = _relative_path(subject_id, session_id, "face.jpg")
        except CaptureDependencyError:
            return _finalize(meta, "error", "cv2_unavailable", session_dir)
        except OSError:
            return _finalize(meta, "error", "storage_unavailable", session_dir)
        except Exception:
            return _finalize(meta, "error", "crop_failed", session_dir)

    audio = record_audio(
        duration_sec=duration_sec,
        mic_index=mic_index,
        min_speech_ratio=DEFAULT_MIN_SPEECH_RATIO,
    )
    meta["audio"]["duration_sec"] = round(float(audio.duration_sec), 3)
    meta["audio"]["speech_ratio"] = round(float(audio.speech_ratio), 4)

    if audio.status == "error":
        return _finalize(meta, "error", audio.reason or "mic_unavailable", session_dir)
    if audio.status == "ok":
        try:
            (session_dir / "audio.wav").write_bytes(audio.wav_bytes)
        except OSError:
            return _finalize(meta, "error", "storage_unavailable", session_dir)
        meta["audio"]["recorded"] = True
        meta["audio"]["audio_path"] = _relative_path(subject_id, session_id, "audio.wav")

    face_ok = bool(meta["face"]["detected"])
    audio_ok = audio.status == "ok"

    if face_ok and audio_ok:
        return _finalize(meta, "ok", None, session_dir)
    if audio_ok:
        return _finalize(meta, "no_face", None, session_dir)
    if face_ok:
        return _finalize(
            meta, "no_audio", audio.reason or "speech_ratio_too_low", session_dir
        )
    return _finalize(meta, "no_face_no_audio", None, session_dir)
