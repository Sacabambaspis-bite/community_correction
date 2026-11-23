"""采集模块默认参数、环境变量读取与内部常量。"""

from __future__ import annotations

import os
from typing import Tuple


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw.strip())
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        return float(raw.strip())
    except ValueError:
        return default


def _env_resolution(name: str, default: Tuple[int, int]) -> Tuple[int, int]:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    text = raw.strip().lower().replace("*", "x")
    parts = text.split("x")
    if len(parts) != 2:
        return default
    try:
        width, height = int(parts[0]), int(parts[1])
    except ValueError:
        return default
    if width <= 0 or height <= 0:
        return default
    return (width, height)


# 由环境变量驱动的默认值；Web/API 层调用采集函数时应显式传入这些值。
DEFAULT_DEVICE_INDEX = _env_int("CAPTURE_DEVICE_INDEX", 0)
DEFAULT_MIC_INDEX = _env_int("CAPTURE_MIC_INDEX", 0)
DEFAULT_DURATION_SEC = _env_float("CAPTURE_DURATION_SEC", 30.0)
DEFAULT_RESOLUTION = _env_resolution("CAPTURE_RESOLUTION", (1280, 720))
DEFAULT_MIN_SPEECH_RATIO = _env_float("CAPTURE_MIN_SPEECH_RATIO", 0.05)
STORAGE_ROOT = os.environ.get("STORAGE_ROOT") or "./storage"

# 契约固定的内部常量
MIN_FACE_AREA_RATIO = 0.01
SPEECH_FRAME_MS = 30
SPEECH_RMS_THRESHOLD = 0.005
JPEG_QUALITY = 85
CROP_MARGIN = 0.25
MAX_FACE_SIDE = 640
