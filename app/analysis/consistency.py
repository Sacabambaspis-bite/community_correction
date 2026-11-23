"""文本、语音、表情方向一致性与四路置信度判定。"""

from __future__ import annotations

from collections import Counter
from typing import Any

from app.analysis.config import CONFIDENCE_THRESHOLD

_CHANNEL_ORDER = ("asr", "emotion", "face", "psych")
_FACE_DIRECTIONS = {
    "neutral": "neutral",
    "sad": "negative",
    "anxious": "negative",
    "angry": "negative",
    "positive": "positive",
}


def _usable_output(channel: dict[str, Any]) -> dict[str, Any] | None:
    output = channel.get("output")
    if channel.get("status") in {"ok", "degraded"} and isinstance(output, dict):
        return output
    return None


def _valence_direction(value: float) -> str:
    if value < 0:
        return "negative"
    if value > 0:
        return "positive"
    return "neutral"


def calculate_consistency(
    *,
    capture_status: str,
    coverage: str,
    channels: dict[str, dict[str, Any]],
    text_valence: float,
    confidence_threshold: float = CONFIDENCE_THRESHOLD,
) -> tuple[str, dict[str, Any]]:
    """冲突和低置信优先；分析降级时 high 最高降为 medium。"""
    directions: dict[str, str] = {}

    if _usable_output(channels["psych"]) is not None:
        directions["psych"] = _valence_direction(text_valence)

    emotion_output = _usable_output(channels["emotion"])
    if emotion_output is not None:
        directions["emotion"] = _valence_direction(emotion_output["valence"])

    face_output = _usable_output(channels["face"])
    if face_output is not None:
        directions["face"] = _FACE_DIRECTIONS[face_output["expression_label"]]

    counts = Counter(directions.values())
    agree_count = max(counts.values(), default=0)
    conflict = counts["negative"] > 0 and counts["positive"] > 0

    low_confidence_channels = []
    for name in _CHANNEL_ORDER:
        channel = channels[name]
        if (
            _usable_output(channel) is not None
            and channel["confidence"] < confidence_threshold
        ):
            low_confidence_channels.append(name)

    degraded = any(
        channel["status"] in {"degraded", "skipped"} for channel in channels.values()
    )
    forced_low = (
        coverage in {"face_only", "audio_only"}
        or capture_status in {"partial", "no_face", "no_audio"}
    )

    if forced_low or conflict or low_confidence_channels or agree_count < 2:
        consistency = "low"
    elif agree_count == 3 and not degraded:
        consistency = "high"
    elif agree_count >= 2:
        consistency = "medium"
    else:
        consistency = "low"

    basis = {
        "agree_count": agree_count,
        "conflict": conflict,
        "low_confidence_channels": low_confidence_channels,
    }
    return consistency, basis
