"""四种确定性 mock 场景；文本仅写入临时 transcript，不进入结果 JSON。"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

_SCENARIOS: dict[str, dict[str, Any]] = {
    "normal": {
        "transcript": "今天按时到了，最近作息比较平稳。",
        "text_valence": 0.0,
        "emotion": {"valence": 0.0, "arousal": 0.25, "label": "neutral"},
        "face": {
            "expression_label": "neutral",
            "intensity": 0.1,
            "face_confidence": 0.9,
            "frame_count": 1,
            "valid_frames": 1,
        },
        "psych": {
            "signal_strength": 12.0,
            "intent_flag": "none",
            "keywords": [],
            "rationale_signal": "未出现明显消极或指向性表达",
        },
        "summary": "三路情感方向一致，未出现明确意图",
        "confidence": {"asr": 0.95, "emotion": 0.9, "face": 0.88, "psych": 0.9},
        "latency_ms": {"asr": 12, "emotion": 8, "face": 6, "psych": 10},
    },
    "negative": {
        "transcript": "最近很累，晚上也睡不着。",
        "text_valence": -0.65,
        "emotion": {"valence": -0.65, "arousal": 0.45, "label": "negative"},
        "face": {
            "expression_label": "sad",
            "intensity": 0.65,
            "face_confidence": 0.87,
            "frame_count": 1,
            "valid_frames": 1,
        },
        "psych": {
            "signal_strength": 75.0,
            "intent_flag": "none",
            "keywords": ["累", "睡不着"],
            "rationale_signal": "出现疲劳与睡眠相关表达，未出现指向性意图",
        },
        "summary": "文本、语音与表情均呈消极方向，未出现明确意图",
        "confidence": {"asr": 0.94, "emotion": 0.88, "face": 0.86, "psych": 0.89},
        "latency_ms": {"asr": 12, "emotion": 8, "face": 6, "psych": 10},
    },
    "crisis": {
        "transcript": "固定指向性测试句。",
        "text_valence": -0.9,
        "emotion": {
            "valence": -0.9,
            "arousal": 0.8,
            "label": "strong_negative",
        },
        "face": {
            "expression_label": "anxious",
            "intensity": 0.85,
            "face_confidence": 0.88,
            "frame_count": 1,
            "valid_frames": 1,
        },
        "psych": {
            "signal_strength": 95.0,
            "intent_flag": "suicide_intent",
            "keywords": ["指向性表达"],
            "rationale_signal": "出现指向性表达，建议人工确认",
        },
        "summary": "文本出现指向性表达，建议人工确认",
        "confidence": {"asr": 0.94, "emotion": 0.9, "face": 0.87, "psych": 0.92},
        "latency_ms": {"asr": 12, "emotion": 8, "face": 6, "psych": 10},
    },
    "conflict": {
        "transcript": "最近很累，晚上也睡不着。",
        "text_valence": -0.6,
        "emotion": {"valence": -0.6, "arousal": 0.4, "label": "negative"},
        "face": {
            "expression_label": "positive",
            "intensity": 0.7,
            "face_confidence": 0.86,
            "frame_count": 1,
            "valid_frames": 1,
        },
        "psych": {
            "signal_strength": 60.0,
            "intent_flag": "none",
            "keywords": ["累", "睡不着"],
            "rationale_signal": "文本偏消极，未出现指向性意图",
        },
        "summary": "文本与语音偏消极，表情方向相反，建议人工复核",
        "confidence": {"asr": 0.94, "emotion": 0.88, "face": 0.86, "psych": 0.89},
        "latency_ms": {"asr": 12, "emotion": 8, "face": 6, "psych": 10},
    },
}


def get_scenario(name: str) -> dict[str, Any]:
    if name not in _SCENARIOS:
        raise ValueError("invalid_mock_scenario")
    return deepcopy(_SCENARIOS[name])
