"""摄像头抓拍。"""

from __future__ import annotations

import time
from typing import Tuple

from .models import FrameResult


def capture_frame(
    device_index: int = 0,
    resolution: Tuple[int, int] = (1280, 720),
    warmup_frames: int = 5,
    timeout_sec: float = 5.0,
) -> FrameResult:
    """打开摄像头抓取单帧 BGR 图像。

    原始帧只返回给调用方，本函数不落盘、不打印。设备打不开返回
    `camera_unavailable` / `camera_open_failed`，设备已打开但读帧失败返回
    `invalid_frame`。
    """
    try:
        import cv2
    except Exception:
        return FrameResult(status="error", frame=None, reason="camera_unavailable")

    cap = None
    try:
        try:
            cap = cv2.VideoCapture(int(device_index))
        except Exception:
            return FrameResult(status="error", frame=None, reason="camera_open_failed")
        if cap is None or not cap.isOpened():
            return FrameResult(status="error", frame=None, reason="camera_unavailable")

        width, height = int(resolution[0]), int(resolution[1])
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

        deadline = time.monotonic() + max(float(timeout_sec), 0.0)
        attempts = max(int(warmup_frames), 1)
        frame = None
        for _ in range(attempts):
            if time.monotonic() > deadline:
                break
            ok, candidate = cap.read()
            if ok and candidate is not None and getattr(candidate, "size", 0) > 0:
                frame = candidate

        if frame is None:
            return FrameResult(status="error", frame=None, reason="invalid_frame")

        frame_height, frame_width = int(frame.shape[0]), int(frame.shape[1])
        if frame_height <= 0 or frame_width <= 0:
            return FrameResult(status="error", frame=None, reason="invalid_frame")
        return FrameResult(
            status="ok",
            frame=frame,
            resolution=(frame_width, frame_height),
        )
    except Exception:
        return FrameResult(status="error", frame=None, reason="invalid_frame")
    finally:
        if cap is not None:
            try:
                cap.release()
            except Exception:
                pass
