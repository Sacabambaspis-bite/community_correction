from __future__ import annotations

import json
from dataclasses import replace

from app.analysis.providers import build_mock_providers, get_scenario
from app.analysis.providers.mock_asr import MockAsrProvider


def test_mock_registry_exposes_four_available_versioned_providers():
    registry = build_mock_providers("normal")
    assert tuple(registry) == ("asr", "emotion", "face", "psych")
    assert {provider.version for provider in registry.values()} == {
        "mock-asr@1.0",
        "mock-emotion@1.0",
        "mock-face@1.0",
        "mock-psych@1.0",
    }
    assert all(provider.available() for provider in registry.values())


def test_asr_writes_utf8_transcript_but_returns_only_relative_path(provider_input):
    scenario = get_scenario("negative")
    provider = MockAsrProvider(scenario)
    raw = provider.analyze(provider_input)

    assert raw["output"]["transcript_path"].endswith("/transcript.txt")
    assert "\\" not in raw["output"]["transcript_path"]
    assert raw["output"]["char_count"] == len(scenario["transcript"])
    assert scenario["transcript"] not in json.dumps(raw, ensure_ascii=False)

    transcript_file = (
        provider_input.storage_root
        / raw["output"]["transcript_path"]
    )
    assert transcript_file.read_text(encoding="utf-8") == scenario["transcript"]


def test_all_mock_provider_outputs_are_deterministic(provider_input):
    first = build_mock_providers("normal")
    second = build_mock_providers("normal")

    first_asr = first["asr"].analyze(provider_input)
    second_asr = second["asr"].analyze(provider_input)
    assert first_asr == second_asr

    psych_input = replace(
        provider_input,
        transcript_path=first_asr["output"]["transcript_path"],
    )
    assert first["emotion"].analyze(provider_input) == second["emotion"].analyze(
        provider_input
    )
    assert first["face"].analyze(provider_input) == second["face"].analyze(
        provider_input
    )
    assert first["psych"].analyze(psych_input) == second["psych"].analyze(
        psych_input
    )
