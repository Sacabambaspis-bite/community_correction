"""采集模块公开接口。

`import app.capture` 不会触发 cv2 / sounddevice / mediapipe 导入，
第三方依赖在各自函数内部懒加载。
"""

from __future__ import annotations

from .audio import record_audio
from .camera import capture_frame
from .face import crop_face, detect_face
from .models import (
    AudioResult,
    CaptureDependencyError,
    CaptureResult,
    CaptureStatus,
    FaceResult,
    FrameResult,
)
from .session import run_capture_session

__all__ = [
    "CaptureStatus",
    "FrameResult",
    "FaceResult",
    "AudioResult",
    "CaptureResult",
    "CaptureDependencyError",
    "capture_frame",
    "detect_face",
    "crop_face",
    "record_audio",
    "run_capture_session",
]
