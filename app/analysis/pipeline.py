"""四路 mock 编排、异常隔离、汇总与完整 Schema 校验。"""

from __future__ import annotations

import math
import time
import uuid
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from app.analysis.config import CONFIDENCE_THRESHOLD, THRESHOLD_PROFILE, get_mock_scenario
from app.analysis.consistency import calculate_consistency
from app.analysis.errors import AnalysisInputError, AnalysisSchemaError
from app.analysis.models import AnalysisInput, AnalysisRunResult, ProviderInput
from app.analysis.paths import (
    resolve_session_file,
    session_directory,
    transcript_relative_path,
)
from app.analysis.providers import BaseProvider, build_providers, get_scenario
from app.analysis.schema import validate_channel, validate_result
from app.grading.config import map_risk_level

_CHANNEL_NAMES = ("asr", "emotion", "face", "psych")
_PROVIDER_RESULT_KEYS = {"status", "output", "confidence", "latency_ms", "reason"}


def generate_overall_risk_level(
    text_valence: float, intent_flag: str = "none"
) -> str:
    """把文本极性与意图标记映射为 Schema 内的五档 ``overall.risk_level``。

    阈值与覆写规则唯一来源是 ``app.grading.config.map_risk_level``，本模块不
    复制分段阈值。``intent_flag`` 指向明确意图时强制 ``crisis``。
    """
    return map_risk_level(text_valence, intent_flag)


def _failed(error: str) -> AnalysisRunResult:
    return AnalysisRunResult(analysis_status="failed", result=None, error=error)


def _provider_version(name: str, provider: BaseProvider) -> str:
    version = getattr(provider, "version", "")
    if isinstance(version, str) and version.strip():
        return version
    return f"unknown-{name}@0"


def _channel(
    *,
    name: str,
    provider: BaseProvider,
    status: str,
    confidence: float = 0.0,
    latency_ms: int = 0,
    output: dict[str, Any] | None = None,
    reason: str | None,
) -> dict[str, Any]:
    return {
        "status": status,
        "model_version": _provider_version(name, provider),
        "latency_ms": latency_ms,
        "confidence": confidence,
        "output": output,
        "reason": reason,
    }


def _missing_provider(name: str) -> BaseProvider:
    class MissingProvider:
        version = f"missing-{name}@0"

        def available(self) -> bool:
            return False

        def analyze(self, input: ProviderInput) -> dict[str, Any]:
            raise RuntimeError("provider_not_registered")

    return MissingProvider()


def _validate_identity(value: str) -> bool:
    try:
        parsed = uuid.UUID(value)
    except (ValueError, AttributeError, TypeError):
        return False
    return str(parsed) == value.lower()


def _validate_input(input: AnalysisInput, *, kind: str = "report") -> Path:
    if not _validate_identity(input.session_id) or not _validate_identity(
        input.subject_id
    ):
        raise AnalysisInputError("invalid_session_identity")
    if input.session_status != "captured":
        raise AnalysisInputError("session_not_captured")
    if input.capture_status in {"no_face_no_audio", "error"}:
        raise AnalysisInputError("capture_not_analyzable")
    if input.capture_status not in {"ok", "partial", "no_face", "no_audio"}:
        raise AnalysisInputError("invalid_capture_status")

    expected_coverage = None
    if input.face_path and input.audio_path:
        expected_coverage = "both"
    elif input.face_path:
        expected_coverage = "face_only"
    elif input.audio_path:
        expected_coverage = "audio_only"
    if input.coverage is None or input.coverage != expected_coverage:
        raise AnalysisInputError("coverage_path_mismatch")

    expected_status_coverage = {
        "ok": "both",
        "no_face": "audio_only",
        "no_audio": "face_only",
    }
    expected = expected_status_coverage.get(input.capture_status)
    if kind == "checkin" and input.capture_status == "ok":
        expected = "face_only"
    if expected is not None and input.coverage != expected:
        raise AnalysisInputError("capture_coverage_mismatch")

    if (
        isinstance(input.duration_sec, bool)
        or not isinstance(input.duration_sec, (int, float))
        or not math.isfinite(input.duration_sec)
        or input.duration_sec < 0
        or isinstance(input.speech_ratio, bool)
        or not isinstance(input.speech_ratio, (int, float))
        or not math.isfinite(input.speech_ratio)
        or not 0 <= input.speech_ratio <= 1
    ):
        raise AnalysisInputError("invalid_audio_metadata")

    root = Path(input.storage_root).expanduser().resolve()
    for relative_path in (input.face_path, input.audio_path):
        if relative_path is None:
            continue
        media_file = resolve_session_file(
            root, input.subject_id, input.session_id, relative_path
        )
        if not media_file.is_file():
            raise AnalysisInputError("media_file_missing")
    return root


def _validate_channel_semantics(
    name: str,
    channel: dict[str, Any],
    provider_input: ProviderInput,
) -> None:
    status = channel["status"]
    output = channel["output"]
    if status == "ok" and not isinstance(output, dict):
        raise ValueError("missing_success_output")
    if status == "skipped" and output is not None:
        raise ValueError("skipped_channel_has_output")

    if name == "face" and isinstance(output, dict):
        if output["valid_frames"] > output["frame_count"]:
            raise ValueError("invalid_face_frame_counts")

    if name == "asr" and isinstance(output, dict):
        expected = transcript_relative_path(
            provider_input.subject_id, provider_input.session_id
        )
        if output["transcript_path"] != expected:
            raise ValueError("invalid_transcript_path")
        transcript_file = session_directory(
            provider_input.storage_root,
            provider_input.subject_id,
            provider_input.session_id,
        ) / "transcript.txt"
        if not transcript_file.is_file():
            raise ValueError("transcript_file_missing")


def _run_provider(
    name: str,
    provider: BaseProvider,
    provider_input: ProviderInput,
) -> dict[str, Any]:
    try:
        if not provider.available():
            return _channel(
                name=name,
                provider=provider,
                status="skipped",
                reason="provider_unavailable",
            )
    except Exception:
        return _channel(
            name=name,
            provider=provider,
            status="degraded",
            reason="availability_check_failed",
        )

    try:
        raw = provider.analyze(provider_input)
        if not isinstance(raw, dict) or set(raw) != _PROVIDER_RESULT_KEYS:
            raise ValueError("invalid_provider_envelope")
        candidate = {
            "status": raw["status"],
            "model_version": _provider_version(name, provider),
            "latency_ms": raw["latency_ms"],
            "confidence": raw["confidence"],
            "output": raw["output"],
            "reason": raw["reason"],
        }
        validate_channel(name, candidate)
        _validate_channel_semantics(name, candidate, provider_input)
        return candidate
    except Exception:
        return _channel(
            name=name,
            provider=provider,
            status="degraded",
            reason="provider_execution_failed",
        )


def _usable_output(channel: dict[str, Any]) -> bool:
    return channel["status"] in {"ok", "degraded"} and isinstance(
        channel["output"], dict
    )


def _summary(
    scenario: dict[str, Any],
    channels: dict[str, dict[str, Any]],
    *,
    capture_status: str,
    consistency: str,
    basis: dict[str, Any],
    degraded: bool,
) -> str:
    if not _usable_output(channels["psych"]):
        return "文本分析不可用，已保留其他通道结果，建议人工复核"
    if basis["conflict"]:
        return "文本、语音或表情方向存在冲突，建议人工复核"
    if degraded:
        return "部分分析通道降级，结果建议人工复核"
    if capture_status in {"partial", "no_face", "no_audio"}:
        return "采集产物不完整，分析结果建议人工复核"
    if consistency == "low" and basis["low_confidence_channels"]:
        return "部分通道置信度偏低，建议人工复核"
    return scenario["summary"]


def _is_degraded(
    channels: dict[str, dict[str, Any]], *, kind: str = "report"
) -> bool:
    relevant_channels = (
        (channels["face"],) if kind == "checkin" else channels.values()
    )
    return any(
        channel["status"] in {"degraded", "skipped"}
        for channel in relevant_channels
    )


def _assert_invariants(result: dict[str, Any], *, kind: str = "report") -> None:
    channels = result["channels"]
    degraded = _is_degraded(channels, kind=kind)
    if result["degraded"] != degraded:
        raise AnalysisSchemaError("analysis_invariant_failed:degraded")
    expected_review = result["consistency"] == "low" or degraded
    if result["needs_review"] != expected_review:
        raise AnalysisSchemaError("analysis_invariant_failed:needs_review")
    # risk_level 的跨字段不变量暂不检查，等待契约与占位函数补充。


def _iso_time(clock: Callable[[], datetime]) -> str:
    value = clock()
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timezone_required")
    return value.isoformat(timespec="milliseconds")


def run_analysis(
    input: AnalysisInput,
    *,
    scenario: str | None = None,
    providers: dict[str, BaseProvider] | None = None,
    overall_risk_level_generator: Callable[[float, str], str] | None = None,
    result_validator: Callable[[dict[str, Any]], None] = validate_result,
    clock: Callable[[], datetime] | None = None,
    monotonic: Callable[[], float] | None = None,
    kind: str = "report",
) -> AnalysisRunResult:
    """执行四路分析；任何 failed 包装都不会携带可进入 grading 的结果。

    checkin 的预期音频缺口不造成分析降级。
    """
    time_source = clock or (lambda: datetime.now().astimezone())
    monotonic_source = monotonic or time.monotonic
    started_monotonic = monotonic_source()

    try:
        root = _validate_input(input, kind=kind)
        scenario_name = scenario or get_mock_scenario()
        scenario_data = get_scenario(scenario_name)
        registry = providers or build_providers(scenario_name)
        registry = {
            name: registry.get(name) or _missing_provider(name)
            for name in _CHANNEL_NAMES
        }
        provider_input = ProviderInput(
            session_id=input.session_id,
            subject_id=input.subject_id,
            storage_root=root,
            face_path=input.face_path,
            audio_path=input.audio_path,
            duration_sec=input.duration_sec,
            speech_ratio=input.speech_ratio,
        )
        started_at = _iso_time(time_source)

        channels: dict[str, dict[str, Any]] = {}
        for name in ("asr", "emotion"):
            provider = registry[name]
            if not input.audio_path:
                channels[name] = _channel(
                    name=name,
                    provider=provider,
                    status="skipped",
                    reason="audio_unavailable",
                )
            else:
                channels[name] = _run_provider(name, provider, provider_input)

        face_provider = registry["face"]
        if not input.face_path:
            channels["face"] = _channel(
                name="face",
                provider=face_provider,
                status="skipped",
                reason="face_unavailable",
            )
        else:
            channels["face"] = _run_provider("face", face_provider, provider_input)

        psych_provider = registry["psych"]
        asr_output = channels["asr"]["output"]
        if not input.audio_path:
            channels["psych"] = _channel(
                name="psych",
                provider=psych_provider,
                status="skipped",
                reason="audio_unavailable",
            )
        elif channels["asr"]["status"] != "ok" or not isinstance(asr_output, dict):
            channels["psych"] = _channel(
                name="psych",
                provider=psych_provider,
                status="skipped",
                reason="asr_unavailable",
            )
        else:
            psych_input = replace(
                provider_input, transcript_path=asr_output["transcript_path"]
            )
            channels["psych"] = _run_provider(
                "psych", psych_provider, psych_input
            )

        if not any(_usable_output(channel) for channel in channels.values()) and not (
            kind == "checkin"
            and input.face_path
            and channels["face"]["status"] in {"degraded", "skipped"}
        ):
            return _failed("no_usable_channel_output")

        psych_available = _usable_output(channels["psych"])
        text_valence = float(scenario_data["text_valence"]) if psych_available else 0.0
        consistency, basis = calculate_consistency(
            capture_status=input.capture_status,
            coverage=input.coverage,
            channels=channels,
            text_valence=text_valence,
            confidence_threshold=CONFIDENCE_THRESHOLD,
            kind=kind,
        )
        degraded = _is_degraded(channels, kind=kind)
        needs_review = consistency == "low" or degraded
        risk_generator = overall_risk_level_generator or generate_overall_risk_level
        psych_output = channels["psych"]["output"] if psych_available else None
        intent_flag = (
            psych_output.get("intent_flag") if psych_available else "none"
        )
        overall = {
            "text_valence": text_valence,
            "text_signal": psych_output["signal_strength"] if psych_output else 0.0,
            "risk_level": risk_generator(
                0.0 if kind == "checkin" else text_valence,
                "none" if kind == "checkin" else intent_flag,
            ),
            "summary_signal": _summary(
                scenario_data,
                channels,
                capture_status=input.capture_status,
                consistency=consistency,
                basis=basis,
                degraded=degraded,
            ),
        }

        finished_monotonic = monotonic_source()
        result = {
            "schema_version": "1.0",
            "session_id": input.session_id,
            "subject_id": input.subject_id,
            "overall": overall,
            "channels": channels,
            "consistency": consistency,
            "consistency_basis": basis,
            "needs_review": needs_review,
            "degraded": degraded,
            "threshold_profile": THRESHOLD_PROFILE,
            "started_at": started_at,
            "finished_at": _iso_time(time_source),
            "latency_ms": max(
                0, int(round((finished_monotonic - started_monotonic) * 1000))
            ),
        }
        _assert_invariants(result, kind=kind)
        result_validator(result)
        status = "degraded" if degraded else "done"
        return AnalysisRunResult(analysis_status=status, result=result, error=None)
    except AnalysisInputError as error:
        return _failed(str(error))
    except AnalysisSchemaError as error:
        return _failed(str(error))
    except Exception:
        return _failed("analysis_pipeline_error")
