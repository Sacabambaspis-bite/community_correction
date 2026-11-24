from __future__ import annotations

import json
from copy import deepcopy

import pytest

from app.analysis.errors import AnalysisSchemaError
from app.analysis.pipeline import generate_overall_risk_level
from app.analysis.schema import default_schema_path, validate_result


def _example() -> dict:
    schema = json.loads(default_schema_path().read_text(encoding="utf-8"))
    return deepcopy(schema["examples"][0])


def _set_path(document: dict, path: tuple[str, ...], value) -> None:
    target = document
    for part in path[:-1]:
        target = target[part]
    target[path[-1]] = value


def test_contract_example_passes_real_schema_validation():
    validate_result(_example())


def test_overall_risk_level_maps_to_legal_enum_values():
    assert generate_overall_risk_level(0.1) == "none"
    assert generate_overall_risk_level(-0.1) == "watch"
    assert generate_overall_risk_level(-0.3) == "elevated"
    assert generate_overall_risk_level(-0.6) == "high"
    assert generate_overall_risk_level(-0.9) == "crisis"
    # 明确意图强制最高档，不受文本极性影响。
    assert generate_overall_risk_level(0.5, "suicide_intent") == "crisis"


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("analysis_status",), "done"),
        (("session_id",), "not-a-uuid"),
        (("started_at",), "2026-11-24T10:00:00"),
        (("channels", "emotion", "confidence"), 1.1),
        (("overall", "risk_level"), "pending"),
    ],
)
def test_schema_rejects_invalid_or_unapproved_fields(path, value):
    document = _example()
    _set_path(document, path, value)
    with pytest.raises(AnalysisSchemaError):
        validate_result(document)
