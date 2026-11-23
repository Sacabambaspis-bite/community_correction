"""采集模块的数据结构。

字段与 `docs/contracts/capture.md` 第 5 节一一对应，不要增删字段名。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Optional, Tuple

CaptureStatus = Literal["ok", "no_face", "no_audio", "no_face_no_audio", "error"]


class CaptureDependencyError(RuntimeError):
    """采集所需的第三方依赖（如 opencv）不可用。"""


@dataclass
class FrameResult:
    status: Literal["ok", "error"]
    frame: Optional[Any]  # BGR ndarray，仅在内存中存在
    reason: Optional[str] = None
    resolution: Optional[Tuple[int, int]] = None


@dataclass
class FaceResult:
    status: Literal["ok", "no_face", "error"]
    bbox: Optional[Tuple[int, int, int, int]] = None  # x, y, w, h
    detector: Optional[Literal["mediapipe", "opencv_dnn", "haar"]] = None
    reason: Optional[str] = None


@dataclass
class AudioResult:
    status: Literal["ok", "no_audio", "error"]
    wav_bytes: Optional[bytes] = None
    duration_sec: float = 0.0
    speech_ratio: float = 0.0
    reason: Optional[str] = None


@dataclass
class CaptureResult:
    capture_status: CaptureStatus
    meta: dict
    face_path: Optional[str] = None
    audio_path: Optional[str] = None
    reason: Optional[str] = None
