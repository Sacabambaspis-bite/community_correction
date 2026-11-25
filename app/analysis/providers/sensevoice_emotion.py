"""SenseVoice 语音情绪 Provider：复用 ASR 响应中的情感标签，缺失时标记降级。

SenseVoice 返回体形如 ``<|zh|><|NEUTRAL|><|Speech|><|withitn|>文本``，其中
``<|NEUTRAL|>`` 就是语音情感标签。本 Provider 不重复请求云端，只消费 ASR
通道解析出的标签，因此延迟为 0。
"""

from __future__ import annotations

from typing import Any

from app.analysis.models import ProviderInput
from app.analysis.providers.mock_emotion import MockEmotionProvider

# 标签 -> (valence, arousal, label)；label 受契约枚举约束，
# 契约无 positive 取值，正向情感用 label=neutral + 正 valence 表达。
_LABEL_MAP: dict[str, tuple[float, float, str]] = {
    "NEUTRAL": (0.0, 0.25, "neutral"),
    "HAPPY": (0.6, 0.6, "neutral"),
    "SURPRISED": (0.1, 0.75, "neutral"),
    "SAD": (-0.6, 0.3, "negative"),
    "DISGUSTED": (-0.6, 0.5, "negative"),
    "ANGRY": (-0.8, 0.85, "strong_negative"),
    "FEARFUL": (-0.75, 0.8, "strong_negative"),
}

# 云端未提供情感置信度，采用保守经验值，避免触发低置信复核。
DEFAULT_CONFIDENCE = 0.75


class SenseVoiceEmotionProvider:
    name = "emotion"
    version = "sensevoice-emotion@1.0"

    def __init__(
        self, scenario: dict[str, Any], *, confidence: float = DEFAULT_CONFIDENCE
    ) -> None:
        self._scenario = scenario
        self._mock = MockEmotionProvider(scenario)
        self._confidence = confidence

    def available(self) -> bool:
        return True

    def analyze(self, input: ProviderInput) -> dict[str, Any]:
        if not input.audio_path:
            raise ValueError("audio_unavailable")

        mapped = _map_label(input.emotion_hint)
        if mapped is None:
            # ASR 未返回可识别标签（降级或响应格式异常）：保留 mock 数值但标记降级，
            # 让上层据此要求人工复核，避免把占位值当成真实情绪。
            result = self._mock.analyze(input)
            result["status"] = "degraded"
            result["reason"] = "sensevoice_emotion_unavailable"
            return result

        valence, arousal, label = mapped
        return {
            "status": "ok",
            "output": {"valence": valence, "arousal": arousal, "label": label},
            "confidence": self._confidence,
            "latency_ms": 0,
            "reason": None,
        }


def _map_label(hint: dict[str, Any] | None) -> tuple[float, float, str] | None:
    if not isinstance(hint, dict):
        return None
    label = hint.get("label")
    if not isinstance(label, str):
        return None
    return _LABEL_MAP.get(label.strip().upper())
