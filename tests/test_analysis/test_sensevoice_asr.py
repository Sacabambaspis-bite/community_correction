"""SenseVoice 真实 ASR 接入测试：全部用 mock 拦截 httpx.post，禁止真实网络请求。"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.analysis.models import AnalysisInput, ProviderInput
from app.analysis.providers import build_providers
from app.analysis.providers.mock_asr import MockAsrProvider
from app.analysis.providers.scenarios import get_scenario
from app.analysis.providers.sensevoice_asr import SenseVoiceAsrProvider

POST_TARGET = "app.analysis.providers.sensevoice_asr.httpx.post"
TEST_URL = "http://sensevoice.test/recognize"
TEST_KEY = "test-api-key"


@pytest.fixture
def sensevoice_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SENSEVOICE_API_URL", TEST_URL)
    monkeypatch.setenv("SENSEVOICE_API_KEY", TEST_KEY)


def _provider(scenario: str = "normal") -> SenseVoiceAsrProvider:
    return SenseVoiceAsrProvider(get_scenario(scenario))


def _ok_response(payload) -> MagicMock:
    response = MagicMock()
    response.json.return_value = payload
    response.raise_for_status.return_value = None
    return response


def _transcript_file(input: ProviderInput) -> Path:
    return (
        input.storage_root
        / "subjects"
        / input.subject_id
        / "sessions"
        / input.session_id
        / "transcript.txt"
    )


@patch(POST_TARGET)
def test_success_returns_real_text(
    mock_post: MagicMock, sensevoice_env: None, provider_input: ProviderInput
) -> None:
    mock_post.return_value = _ok_response({"text": "  今天状态不错。 "})

    result = _provider().analyze(provider_input)

    assert result["status"] == "ok"
    assert result["reason"] is None
    assert result["output"]["char_count"] == len("今天状态不错。")
    assert (
        _transcript_file(provider_input).read_text(encoding="utf-8")
        == "今天状态不错。"
    )

    call = mock_post.call_args
    assert call.args[0] == TEST_URL
    assert call.kwargs["headers"] == {"Authorization": f"Bearer {TEST_KEY}"}
    assert call.kwargs["timeout"] == 10.0
    assert call.kwargs["files"]["file"][0] == "audio.wav"


@patch(POST_TARGET)
def test_success_accepts_nested_data_text(
    mock_post: MagicMock, sensevoice_env: None, provider_input: ProviderInput
) -> None:
    mock_post.return_value = _ok_response({"data": {"text": "嵌套返回文本"}})

    result = _provider().analyze(provider_input)

    assert result["status"] == "ok"
    assert (
        _transcript_file(provider_input).read_text(encoding="utf-8") == "嵌套返回文本"
    )


@patch(POST_TARGET)
def test_timeout_falls_back_to_mock(
    mock_post: MagicMock, sensevoice_env: None, provider_input: ProviderInput
) -> None:
    mock_post.side_effect = httpx.TimeoutException("timeout")

    result = _provider().analyze(provider_input)

    scenario = get_scenario("normal")
    assert result["status"] == "degraded"
    assert result["reason"] == "sensevoice_fallback"
    assert result["output"]["char_count"] == len(scenario["transcript"])
    assert (
        _transcript_file(provider_input).read_text(encoding="utf-8")
        == scenario["transcript"]
    )


@pytest.mark.parametrize("status_code", [400, 500])
@patch(POST_TARGET)
def test_http_error_falls_back_to_mock(
    mock_post: MagicMock,
    sensevoice_env: None,
    provider_input: ProviderInput,
    status_code: int,
) -> None:
    response = _ok_response({})
    response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "http error", request=MagicMock(), response=MagicMock(status_code=status_code)
    )
    mock_post.return_value = response

    result = _provider().analyze(provider_input)

    assert result["status"] == "degraded"
    assert result["reason"] == "sensevoice_fallback"
    assert (
        _transcript_file(provider_input).read_text(encoding="utf-8")
        == get_scenario("normal")["transcript"]
    )


@patch(POST_TARGET)
def test_missing_text_field_falls_back_to_mock(
    mock_post: MagicMock, sensevoice_env: None, provider_input: ProviderInput
) -> None:
    mock_post.return_value = _ok_response({"code": 0})

    result = _provider().analyze(provider_input)

    assert result["status"] == "degraded"
    assert result["reason"] == "sensevoice_fallback"


@patch(POST_TARGET)
def test_unconfigured_uses_mock_without_http(
    mock_post: MagicMock, provider_input: ProviderInput
) -> None:
    # autouse fixture 已清除环境变量，此时工厂必须返回纯 Mock。
    registry = build_providers("normal")

    assert isinstance(registry["asr"], MockAsrProvider)
    result = registry["asr"].analyze(provider_input)

    assert result["status"] == "ok"
    assert result["reason"] is None
    mock_post.assert_not_called()


@patch(POST_TARGET)
def test_pipeline_success_with_real_api(
    mock_post: MagicMock,
    sensevoice_env: None,
    run_pipeline,
    analysis_input: AnalysisInput,
) -> None:
    mock_post.return_value = _ok_response({"text": "真实转写文本"})

    run = run_pipeline(analysis_input)

    asr = run.result["channels"]["asr"]
    assert run.analysis_status == "done"
    assert asr["status"] == "ok"
    assert asr["model_version"] == "sensevoice-asr@1.0"
    assert asr["output"]["char_count"] == len("真实转写文本")


@patch(POST_TARGET)
def test_pipeline_timeout_degrades_without_blocking(
    mock_post: MagicMock,
    sensevoice_env: None,
    run_pipeline,
    analysis_input: AnalysisInput,
) -> None:
    mock_post.side_effect = httpx.TimeoutException("timeout")

    run = run_pipeline(analysis_input)

    asr = run.result["channels"]["asr"]
    assert run.analysis_status == "degraded"
    assert asr["status"] == "degraded"
    assert asr["reason"] == "sensevoice_fallback"
    # 既有契约：ASR 非 ok 时 psych 跳过；emotion/face 不受影响，管线不失败。
    assert run.result["channels"]["psych"]["status"] == "skipped"
    assert run.result["channels"]["psych"]["reason"] == "asr_unavailable"
    assert run.result["channels"]["emotion"]["status"] == "ok"
    assert run.result["channels"]["face"]["status"] == "ok"
    assert run.result["degraded"] is True
    assert run.result["needs_review"] is True
