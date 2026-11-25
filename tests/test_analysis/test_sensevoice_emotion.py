"""SenseVoice 情绪标签接入测试：全部用 mock 拦截 httpx，禁止真实网络请求。"""

from __future__ import annotations

from dataclasses import replace
from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.analysis.models import ProviderInput
from app.analysis.providers import build_providers
from app.analysis.providers.mock_emotion import MockEmotionProvider
from app.analysis.providers.scenarios import get_scenario
from app.analysis.providers.sensevoice_asr import SenseVoiceAsrProvider
from app.analysis.providers.sensevoice_emotion import SenseVoiceEmotionProvider

POST_TARGET = "app.analysis.providers.sensevoice_asr.httpx.post"
TEST_URL = "http://sensevoice.test/recognize"
TEST_KEY = "test-api-key"


@pytest.fixture
def sensevoice_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SENSEVOICE_API_URL", TEST_URL)
    monkeypatch.setenv("SENSEVOICE_API_KEY", TEST_KEY)


def _provider() -> SenseVoiceEmotionProvider:
    return SenseVoiceEmotionProvider(get_scenario("normal"))


def _ok_response(payload) -> MagicMock:
    response = MagicMock()
    response.json.return_value = payload
    response.raise_for_status.return_value = None
    return response


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        ("NEUTRAL", {"valence": 0.0, "arousal": 0.25, "label": "neutral"}),
        ("HAPPY", {"valence": 0.6, "arousal": 0.6, "label": "neutral"}),
        ("SURPRISED", {"valence": 0.1, "arousal": 0.75, "label": "neutral"}),
        ("SAD", {"valence": -0.6, "arousal": 0.3, "label": "negative"}),
        ("DISGUSTED", {"valence": -0.6, "arousal": 0.5, "label": "negative"}),
        ("ANGRY", {"valence": -0.8, "arousal": 0.85, "label": "strong_negative"}),
        ("FEARFUL", {"valence": -0.75, "arousal": 0.8, "label": "strong_negative"}),
    ],
)
def test_label_mapping(
    provider_input: ProviderInput, label: str, expected: dict
) -> None:
    result = _provider().analyze(replace(provider_input, emotion_hint={"label": label}))

    assert result["status"] == "ok"
    assert result["reason"] is None
    assert result["output"] == expected


def test_lowercase_label_is_normalized(provider_input: ProviderInput) -> None:
    result = _provider().analyze(
        replace(provider_input, emotion_hint={"label": "sad"})
    )

    assert result["status"] == "ok"
    assert result["output"]["label"] == "negative"


def test_missing_hint_degrades_with_mock_output(provider_input: ProviderInput) -> None:
    result = _provider().analyze(provider_input)

    assert result["status"] == "degraded"
    assert result["reason"] == "sensevoice_emotion_unavailable"
    assert result["output"] == get_scenario("normal")["emotion"]


def test_unknown_label_degrades(provider_input: ProviderInput) -> None:
    result = _provider().analyze(
        replace(provider_input, emotion_hint={"label": "EMO_UNKNOWN"})
    )

    assert result["status"] == "degraded"
    assert result["reason"] == "sensevoice_emotion_unavailable"


@patch(POST_TARGET)
def test_asr_exposes_parsed_emotion(
    mock_post: MagicMock, sensevoice_env: None, provider_input: ProviderInput
) -> None:
    mock_post.return_value = _ok_response(
        {"text": "<|zh|><|SAD|><|Speech|><|withitn|>最近很累"}
    )
    provider = SenseVoiceAsrProvider(get_scenario("normal"))

    provider.analyze(provider_input)

    assert provider.last_emotion == {"label": "SAD", "event": "SPEECH"}


@patch(POST_TARGET)
def test_asr_without_emotion_tag_leaves_hint_empty(
    mock_post: MagicMock, sensevoice_env: None, provider_input: ProviderInput
) -> None:
    mock_post.return_value = _ok_response({"text": "纯文本无标签"})
    provider = SenseVoiceAsrProvider(get_scenario("normal"))

    provider.analyze(provider_input)

    assert provider.last_emotion is None


@patch(POST_TARGET)
def test_asr_fallback_clears_previous_hint(
    mock_post: MagicMock, sensevoice_env: None, provider_input: ProviderInput
) -> None:
    provider = SenseVoiceAsrProvider(get_scenario("normal"))
    provider.last_emotion = {"label": "HAPPY", "event": "Speech"}
    mock_post.side_effect = httpx.TimeoutException("timeout")

    provider.analyze(provider_input)

    assert provider.last_emotion is None


def test_build_providers_keeps_mock_emotion_when_unconfigured() -> None:
    registry = build_providers("normal")

    assert isinstance(registry["emotion"], MockEmotionProvider)


def test_build_providers_uses_sensevoice_emotion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SENSEVOICE_API_URL", TEST_URL)
    monkeypatch.setenv("SENSEVOICE_API_KEY", TEST_KEY)

    registry = build_providers("normal")

    assert isinstance(registry["asr"], SenseVoiceAsrProvider)
    assert isinstance(registry["emotion"], SenseVoiceEmotionProvider)
