"""确定性 mock Provider 注册表。"""

from __future__ import annotations

from app.analysis.providers.base import BaseProvider
from app.analysis.providers.mock_asr import MockAsrProvider
from app.analysis.providers.mock_emotion import MockEmotionProvider
from app.analysis.providers.mock_face import MockFaceProvider
from app.analysis.providers.mock_psych import MockPsychProvider
from app.analysis.providers.scenarios import get_scenario


def build_mock_providers(scenario: str) -> dict[str, BaseProvider]:
    data = get_scenario(scenario)
    return {
        "asr": MockAsrProvider(data),
        "emotion": MockEmotionProvider(data),
        "face": MockFaceProvider(data),
        "psych": MockPsychProvider(data),
    }


__all__ = ["BaseProvider", "build_mock_providers", "get_scenario"]
