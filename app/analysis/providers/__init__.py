"""确定性 mock Provider 注册表。"""

from __future__ import annotations

from app.analysis.providers.base import BaseProvider
from app.analysis.providers.mock_asr import MockAsrProvider
from app.analysis.providers.mock_emotion import MockEmotionProvider
from app.analysis.providers.mock_face import MockFaceProvider
from app.analysis.providers.mock_psych import MockPsychProvider
from app.analysis.providers.scenarios import get_scenario
from app.analysis.providers.sensevoice_asr import (
    SenseVoiceAsrProvider,
    sensevoice_configured,
)
from app.analysis.providers.sensevoice_emotion import SenseVoiceEmotionProvider


def build_mock_providers(scenario: str) -> dict[str, BaseProvider]:
    data = get_scenario(scenario)
    return {
        "asr": MockAsrProvider(data),
        "emotion": MockEmotionProvider(data),
        "face": MockFaceProvider(data),
        "psych": MockPsychProvider(data),
    }


def build_providers(scenario: str) -> dict[str, BaseProvider]:
    """默认注册表：配置 SenseVoice 时 ASR 与 emotion 走真实结果，其余仍为 Mock。"""
    data = get_scenario(scenario)
    if sensevoice_configured():
        return {
            "asr": SenseVoiceAsrProvider(data),
            "emotion": SenseVoiceEmotionProvider(data),
            "face": MockFaceProvider(data),
            "psych": MockPsychProvider(data),
        }
    return {
        "asr": MockAsrProvider(data),
        "emotion": MockEmotionProvider(data),
        "face": MockFaceProvider(data),
        "psych": MockPsychProvider(data),
    }


__all__ = [
    "BaseProvider",
    "SenseVoiceAsrProvider",
    "SenseVoiceEmotionProvider",
    "build_mock_providers",
    "build_providers",
    "get_scenario",
    "sensevoice_configured",
]

