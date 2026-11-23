"""摄像头抓拍。

Windows 下优先使用 DirectShow（`cv2.CAP_DSHOW`）打开设备，再回退到
OpenCV 默认后端；其他平台只用默认后端。只保存/返回内存中的帧，不落盘、
不打印，失败原因通过 `FrameResult.reason` 以 `code: detail` 形式带回。
"""

from __future__ import annotations

import sys
import time
from typing import List, Optional, Tuple

from .models import FrameResult

# 合法的设备级失败 code，session 侧按冒号前缀解析，detail 不含图像内容
_OPEN_EXCEPTION = "open_exception"
_NOT_OPENED = "not_opened"
_NO_FRAME = "no_frame"
_INVALID_SIZE = "invalid_size"


def _candidate_backends(cv2) -> List[Tuple[str, Optional[int]]]:
    """按优先级返回 `(后端名, 后端标识)`。

    Windows 且 OpenCV 提供 `CAP_DSHOW` 时优先 DirectShow，随后回退默认后端；
    其余情况只用默认后端。每个后端最多尝试一次，避免反复占用设备。
    """
    backends: List[Tuple[str, Optional[int]]] = []
    if sys.platform.startswith("win"):
        dshow = getattr(cv2, "CAP_DSHOW", None)
        if dshow is not None:
            backends.append(("dshow", int(dshow)))
    backends.append(("default", None))
    return backends


def _open_capture(cv2, device_index: int, backend_flag: Optional[int]):
    if backend_flag is None:
        return cv2.VideoCapture(device_index)
    return cv2.VideoCapture(device_index, backend_flag)


def _read_frame(
    cap,
    cv2,
    resolution: Tuple[int, int],
    warmup_frames: int,
    timeout_sec: float,
):
    """按现有行为设置分辨率并读帧，返回 `(frame, None)` 或 `(None, 失败标记)`。"""
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
        return None, _NO_FRAME

    frame_height, frame_width = int(frame.shape[0]), int(frame.shape[1])
    if frame_height <= 0 or frame_width <= 0:
        return None, _INVALID_SIZE
    return frame, None


def _with_detail(code: str, detail: Optional[str]) -> str:
    """`code` 保持稳定枚举，诊断信息放冒号后的 detail（不含图像内容）。"""
    return "{}: {}".format(code, detail) if detail else code


def capture_frame(
    device_index: int = 0,
    resolution: Tuple[int, int] = (1280, 720),
    warmup_frames: int = 5,
    timeout_sec: float = 5.0,
) -> FrameResult:
    """打开摄像头抓取单帧 BGR 图像。

    原始帧只返回给调用方，本函数不落盘、不打印。设备打不开返回
    `camera_unavailable` / `camera_open_failed`，设备已打开但读帧失败返回
    `invalid_frame`；所有后端都失败后才返回错误。
    """
    try:
        import cv2
    except Exception as exc:
        return FrameResult(
            status="error",
            frame=None,
            reason=_with_detail(
                "camera_unavailable", "cv2_import_exception: {}".format(type(exc).__name__)
            ),
        )

    try:
        index = int(device_index)
    except Exception:
        return FrameResult(
            status="error",
            frame=None,
            reason=_with_detail("invalid_frame", "device_index_invalid"),
        )

    failures: List[str] = []
    any_opened = False
    any_exception = False

    for backend_name, backend_flag in _candidate_backends(cv2):
        cap = None
        try:
            try:
                cap = _open_capture(cv2, index, backend_flag)
            except Exception as exc:
                any_exception = True
                failures.append(
                    "{}={}: {}".format(
                        backend_name, _OPEN_EXCEPTION, type(exc).__name__
                    )
                )
                continue

            if cap is None or not cap.isOpened():
                failures.append("{}={}".format(backend_name, _NOT_OPENED))
                continue

            any_opened = True
            try:
                frame, failure = _read_frame(
                    cap, cv2, resolution, warmup_frames, timeout_sec
                )
            except Exception as exc:
                failures.append(
                    "{}={}: {}".format(
                        backend_name, "read_exception", type(exc).__name__
                    )
                )
                continue

            if frame is None:
                failures.append("{}={}".format(backend_name, failure))
                continue

            frame_height, frame_width = int(frame.shape[0]), int(frame.shape[1])
            if frame_height <= 0 or frame_width <= 0:
                failures.append("{}={}".format(backend_name, _INVALID_SIZE))
                continue

            return FrameResult(
                status="ok",
                frame=frame,
                resolution=(frame_width, frame_height),
            )
        finally:
            if cap is not None:
                try:
                    cap.release()
                except Exception:
                    pass

    detail = "; ".join(failures) if failures else None
    if any_opened:
        code = "invalid_frame"
    elif any_exception:
        code = "camera_open_failed"
    else:
        code = "camera_unavailable"
    return FrameResult(status="error", frame=None, reason=_with_detail(code, detail))
