"""人脸检测与裁剪。

检测器按 MediaPipe → OpenCV DNN → Haar 的顺序回退，任何一级不可用或抛异常
都跳到下一级；三级都不可用才返回 `detector_unavailable`。
"""

from __future__ import annotations

import os
from typing import List, Optional, Sequence, Tuple

from .config import (
    CROP_MARGIN,
    JPEG_QUALITY,
    MIN_FACE_AREA_RATIO,
    OUTPUT_SIDE,
)
from .models import CaptureDependencyError, FaceResult

BBox = Tuple[int, int, int, int]

_HAAR_CASCADE = None
_HAAR_LOADED = False


def _import_cv2():
    try:
        import cv2
    except Exception as exc:  # ImportError 或二进制加载失败
        raise CaptureDependencyError("opencv-python 不可用") from exc
    return cv2


def _clamp_bbox(bbox: Sequence[float], width: int, height: int) -> Optional[BBox]:
    """把任意 bbox 收敛到帧内，非法或过窄时返回 None。"""
    try:
        x, y, w, h = (int(round(float(v))) for v in bbox)
    except Exception:
        return None
    x0 = min(max(x, 0), width - 1)
    y0 = min(max(y, 0), height - 1)
    x1 = min(max(x + w, x0 + 1), width)
    y1 = min(max(y + h, y0 + 1), height)
    if x1 - x0 <= 1 or y1 - y0 <= 1:
        return None
    return (x0, y0, x1 - x0, y1 - y0)


def _detect_mediapipe(frame) -> Optional[List[BBox]]:
    """返回 bbox 列表；检测器不可用时返回 None。"""
    try:
        import cv2
        import mediapipe as mp
    except Exception:
        return None

    result = None
    try:
        detector = mp.solutions.face_detection.FaceDetection(
            model_selection=0, min_detection_confidence=0.5
        )
        try:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            result = detector.process(rgb)
        finally:
            detector.close()
    except Exception:
        return None

    height, width = int(frame.shape[0]), int(frame.shape[1])
    boxes: List[BBox] = []
    detections = getattr(result, "detections", None) or []
    for detection in detections:
        try:
            relative = detection.location_data.relative_bounding_box
            raw = (
                relative.xmin * width,
                relative.ymin * height,
                relative.width * width,
                relative.height * height,
            )
        except Exception:
            continue
        box = _clamp_bbox(raw, width, height)
        if box is not None:
            boxes.append(box)
    return boxes


def _detect_dnn(frame) -> Optional[List[BBox]]:
    """仅在显式提供且存在 DNN 模型文件时可用，否则返回 None。"""
    proto = os.environ.get("FACE_DNN_PROTO")
    weights = os.environ.get("FACE_DNN_WEIGHTS")
    if not proto or not weights:
        return None
    if not (os.path.isfile(proto) and os.path.isfile(weights)):
        return None

    try:
        import cv2
    except Exception:
        return None
    dnn = getattr(cv2, "dnn", None)
    if dnn is None:
        return None

    try:
        net = dnn.readNetFromCaffe(proto, weights)
        height, width = int(frame.shape[0]), int(frame.shape[1])
        blob = dnn.blobFromImage(
            cv2.resize(frame, (300, 300)),
            1.0,
            (300, 300),
            (104.0, 177.0, 123.0),
        )
        net.setInput(blob)
        detections = net.forward()
    except Exception:
        return None

    boxes: List[BBox] = []
    try:
        for index in range(detections.shape[2]):
            confidence = float(detections[0, 0, index, 2])
            if confidence < 0.5:
                continue
            x1 = float(detections[0, 0, index, 3]) * width
            y1 = float(detections[0, 0, index, 4]) * height
            x2 = float(detections[0, 0, index, 5]) * width
            y2 = float(detections[0, 0, index, 6]) * height
            box = _clamp_bbox((x1, y1, x2 - x1, y2 - y1), width, height)
            if box is not None:
                boxes.append(box)
    except Exception:
        return None
    return boxes


def _get_haar_cascade():
    global _HAAR_CASCADE, _HAAR_LOADED
    if _HAAR_LOADED:
        return _HAAR_CASCADE
    _HAAR_LOADED = True
    try:
        import cv2

        cascade_path = os.path.join(
            cv2.data.haarcascades, "haarcascade_frontalface_default.xml"
        )
        cascade = cv2.CascadeClassifier(cascade_path)
        _HAAR_CASCADE = None if cascade.empty() else cascade
    except Exception:
        _HAAR_CASCADE = None
    return _HAAR_CASCADE


def _detect_haar(frame) -> Optional[List[BBox]]:
    cascade = _get_haar_cascade()
    if cascade is None:
        return None
    try:
        import cv2

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if frame.ndim == 3 else frame
        faces = cascade.detectMultiScale(
            gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30)
        )
    except Exception:
        return None

    boxes: List[BBox] = []
    for face in faces:
        box = _clamp_bbox(tuple(face), int(frame.shape[1]), int(frame.shape[0]))
        if box is not None:
            boxes.append(box)
    return boxes


_DETECTORS = (
    ("mediapipe", _detect_mediapipe),
    ("opencv_dnn", _detect_dnn),
    ("haar", _detect_haar),
)


def detect_face(frame) -> FaceResult:
    """检测一帧中最大的人脸。"""
    try:
        shape = frame.shape
        if frame is None or len(shape) != 3:
            raise ValueError
        height, width = int(shape[0]), int(shape[1])
    except Exception:
        return FaceResult(status="error", reason="invalid_frame")
    if height <= 0 or width <= 0:
        return FaceResult(status="error", reason="invalid_frame")

    frame_area = float(height * width)
    available = False
    for name, detector in _DETECTORS:
        try:
            boxes = detector(frame)
        except Exception:
            boxes = None
        if boxes is None:
            continue
        available = True

        best: Optional[BBox] = None
        best_area = 0
        for bbox in boxes:
            clamped = _clamp_bbox(bbox, width, height)
            if clamped is None:
                continue
            area = clamped[2] * clamped[3]
            if area > best_area:
                best, best_area = clamped, area
        if best is None:
            continue

        # 面积占比过小说明画面中即使有脸也不可用，按“未检出”处理
        if best_area / frame_area < MIN_FACE_AREA_RATIO:
            return FaceResult(status="no_face")
        return FaceResult(status="ok", bbox=best, detector=name)

    if not available:
        return FaceResult(status="error", reason="detector_unavailable")
    return FaceResult(status="no_face")


def _crop_box(shape, bbox: BBox, margin: float) -> Tuple[int, int, int]:
    """计算以 bbox 为中心的正方形裁剪区域，必要时向内收缩以落在帧内。"""
    try:
        height, width = int(shape[0]), int(shape[1])
    except Exception:
        raise ValueError("invalid frame shape")
    if height <= 0 or width <= 0:
        raise ValueError("invalid frame shape")

    clamped = _clamp_bbox(bbox, width, height)
    if clamped is None:
        raise ValueError("invalid bbox")
    x, y, box_width, box_height = clamped

    side = int(max(box_width, box_height) * (1 + 2 * float(margin)))
    side = max(side, 1)
    # 边长超过帧的短边时无法完整落盘，先收缩到短边，再按中心回推起点
    side = min(side, width, height)
    center_x = x + box_width // 2
    center_y = y + box_height // 2
    left = min(max(center_x - side // 2, 0), width - side)
    top = min(max(center_y - side // 2, 0), height - side)
    return left, top, side


def crop_face(
    frame,
    bbox: BBox,
    margin: float = CROP_MARGIN,
    output_side: int = OUTPUT_SIDE,
    jpeg_quality: int = JPEG_QUALITY,
) -> Optional[bytes]:
    """裁剪人脸并编码为固定 output_side × output_side 的正方形 JPEG。

    任何失败（依赖缺失、空帧、非法 bbox、编码失败等）一律返回 None，
    不向上抛异常；由调用方记为 `crop_failed`。
    """
    try:
        cv2 = _import_cv2()
        if frame is None:
            return None

        shape = getattr(frame, "shape", None)
        if not shape or len(shape) < 2:
            return None

        left, top, side = _crop_box(shape, bbox, margin)
        image = frame[top : top + side, left : left + side]
        if image is None or int(getattr(image, "size", 0)) <= 0:
            return None

        side_out = int(output_side)
        if side_out <= 0:
            return None
        # 固定正方形输出：无论裁剪区域多大，一律缩放到 output_side 见方
        image = cv2.resize(
            image, (side_out, side_out), interpolation=cv2.INTER_AREA
        )

        ok, buffer = cv2.imencode(
            ".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), int(jpeg_quality)]
        )
        if not ok or buffer is None:
            return None
        return buffer.tobytes()
    except Exception:
        return None
