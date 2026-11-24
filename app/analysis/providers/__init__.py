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


def build_mock_providers(scenario: str) -> dict[str, BaseProvider]:
    data = get_scenario(scenario)
    return {
        "asr": MockAsrProvider(data),
        "emotion": MockEmotionProvider(data),
        "face": MockFaceProvider(data),
        "psych": MockPsychProvider(data),
    }


def build_providers(scenario: str) -> dict[str, BaseProvider]:
    """默认注册表：配置 SenseVoice 时 ASR 走真实 API，其余通道仍为 Mock。"""
    data = get_scenario(scenario)
    asr = SenseVoiceAsrProvider(data) if sensevoice_configured() else MockAsrProvider(data)
    return {
        "asr": asr,
        "emotion": MockEmotionProvider(data),
        "face": MockFaceProvider(data),
        "psych": MockPsychProvider(data),
    }


__all__ = [
    "BaseProvider",
    "SenseVoiceAsrProvider",
    "build_mock_providers",
    "build_providers",
    "get_scenario",
    "sensevoice_configured",
]

