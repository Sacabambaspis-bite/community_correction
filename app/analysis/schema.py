"""加载正式 AnalysisResult Schema，并执行通道级与完整校验。"""

from __future__ import annotations

import json
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from app.analysis.errors import AnalysisSchemaError

_DEFAULT_SCHEMA_PATH = (
    Path(__file__).resolve().parents[2]
    / "docs"
    / "contracts"
    / "analysis.schema.json"
)
_FORMAT_CHECKER = FormatChecker()


def default_schema_path() -> Path:
    return _DEFAULT_SCHEMA_PATH


@lru_cache(maxsize=4)
def _load_schema(path_text: str) -> dict[str, Any]:
    try:
        schema = json.loads(Path(path_text).read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
    except Exception:
        raise AnalysisSchemaError("analysis_schema_unavailable") from None
    return schema


def _location(error: Any) -> str:
    parts = [str(part) for part in error.absolute_path]
    return ".".join(parts) if parts else "$"


def _first_error(validator: Draft202012Validator, value: Any) -> Any | None:
    errors = sorted(validator.iter_errors(value), key=lambda error: _location(error))
    return errors[0] if errors else None


def validate_channel(name: str, value: dict[str, Any]) -> None:
    """通道子 schema 保留根 $defs，使 channel_status 引用可解析。"""
    schema = _load_schema(str(_DEFAULT_SCHEMA_PATH))
    try:
        channel_schema = deepcopy(schema["properties"]["channels"]["properties"][name])
    except KeyError:
        raise AnalysisSchemaError("unknown_analysis_channel") from None
    channel_schema["$defs"] = deepcopy(schema["$defs"])
    validator = Draft202012Validator(channel_schema, format_checker=_FORMAT_CHECKER)
    error = _first_error(validator, value)
    if error is not None:
        raise AnalysisSchemaError(
            f"channel_schema_validation_failed:{_location(error)}"
        )


def validate_result(value: dict[str, Any]) -> None:
    schema = _load_schema(str(_DEFAULT_SCHEMA_PATH))
    validator = Draft202012Validator(schema, format_checker=_FORMAT_CHECKER)
    error = _first_error(validator, value)
    if error is not None:
        raise AnalysisSchemaError(f"schema_validation_failed:{_location(error)}")
