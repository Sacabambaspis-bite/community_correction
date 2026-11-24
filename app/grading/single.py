"""单次风险规则：红 / 橙。消费 ``channels.psych.output``。"""

from __future__ import annotations

from dataclasses import replace
from typing import Optional

from .config import (
    ORANGE_AUX_EMOTION_LABEL,
    ORANGE_AUX_FACE_EXPRESSIONS,
    RULE_VERSION,
    THRESHOLDS,
)
from .models import RuleHit, SessionGrading


def _psych_output(analysis: dict) -> Optional[dict]:
    """取出可用的 psych output。

    - 缺 ``channels.psych`` -> 抛 ``ValueError("missing_psych_channel")``；
    - ``status`` 不在 {ok, degraded} 或 ``output`` 非 dict -> 返回 ``None``
      （skipped / 无产物不参与单次定级）。
    """
    channels = analysis.get("channels")
    if not isinstance(channels, dict) or "psych" not in channels:
        raise ValueError("missing_psych_channel")
    psych = channels.get("psych")
    if not isinstance(psych, dict):
        raise ValueError("missing_psych_channel")
    if psych.get("status") not in ("ok", "degraded"):
        return None
    output = psych.get("output")
    if not isinstance(output, dict):
        return None
    return output


def _session_id(analysis: dict) -> Optional[str]:
    sid = analysis.get("session_id")
    return sid if isinstance(sid, str) else None


def R_SINGLE_RED(analysis: dict) -> Optional[RuleHit]:
    """明确意图 -> 红（一票定级，不受一致性封顶）。

    满足任一即命中：
    - ``intent_flag == suicide_intent``
    - ``intent_flag == self_harm_mention`` 且 ``signal_strength >= SINGLE_RED_SELFHARM_SIGNAL``
    """
    output = _psych_output(analysis)
    if output is None:
        return None
    intent_flag = output.get("intent_flag")

    if intent_flag == THRESHOLDS["SINGLE_RED_INTENT_FLAG"]:
        return RuleHit(
            rule_id="R_SINGLE_RED",
            rule_version=RULE_VERSION,
            field_path="channels.psych.output.intent_flag",
            observed_value=intent_flag,
            threshold_key="SINGLE_RED_INTENT_FLAG",
            threshold_value=THRESHOLDS["SINGLE_RED_INTENT_FLAG"],
            severity="red",
        )

    if intent_flag == THRESHOLDS["SINGLE_RED_SELFHARM_INTENT_FLAG"]:
        signal = output.get("signal_strength")
        threshold = THRESHOLDS["SINGLE_RED_SELFHARM_SIGNAL"]
        if isinstance(signal, (int, float)) and signal >= threshold:
            return RuleHit(
                rule_id="R_SINGLE_RED",
                rule_version=RULE_VERSION,
                field_path="channels.psych.output.signal_strength",
                observed_value=signal,
                threshold_key="SINGLE_RED_SELFHARM_SIGNAL",
                threshold_value=threshold,
                severity="red",
            )
    return None


def R_SINGLE_ORANGE(analysis: dict) -> Optional[RuleHit]:
    """强消极无明确意图 -> 橙。

    同时满足：psych.status ∈ {ok, degraded}、signal_strength >= SINGLE_ORANGE_SIGNAL_MIN、
    intent_flag != suicide_intent。辅助佐证（emotion/face）不单独触发，仅追加证据，
    见 ``_orange_aux_hits``。
    """
    output = _psych_output(analysis)
    if output is None:
        return None
    if output.get("intent_flag") == THRESHOLDS["SINGLE_RED_INTENT_FLAG"]:
        # 明确意图走红，不触发橙
        return None
    signal = output.get("signal_strength")
    threshold = THRESHOLDS["SINGLE_ORANGE_SIGNAL_MIN"]
    if not isinstance(signal, (int, float)) or signal < threshold:
        return None
    return RuleHit(
        rule_id="R_SINGLE_ORANGE",
        rule_version=RULE_VERSION,
        field_path="channels.psych.output.signal_strength",
        observed_value=signal,
        threshold_key="SINGLE_ORANGE_SIGNAL_MIN",
        threshold_value=threshold,
        severity="orange",
    )


def _orange_aux_hits(analysis: dict) -> list[RuleHit]:
    """橙命中后的辅助佐证：共享 ``rule_id=R_SINGLE_ORANGE``，仅追加证据条目。"""
    hits: list[RuleHit] = []
    channels = analysis.get("channels")
    if not isinstance(channels, dict):
        return hits

    emotion = channels.get("emotion")
    if isinstance(emotion, dict) and emotion.get("status") in ("ok", "degraded"):
        eout = emotion.get("output")
        if isinstance(eout, dict) and eout.get("label") == ORANGE_AUX_EMOTION_LABEL:
            hits.append(
                RuleHit(
                    rule_id="R_SINGLE_ORANGE",
                    rule_version=RULE_VERSION,
                    field_path="channels.emotion.output.label",
                    observed_value=eout.get("label"),
                    threshold_key="ORANGE_AUX_EMOTION_LABEL",
                    threshold_value=ORANGE_AUX_EMOTION_LABEL,
                    severity="orange",
                )
            )

    face = channels.get("face")
    if isinstance(face, dict) and face.get("status") in ("ok", "degraded"):
        fout = face.get("output")
        if (
            isinstance(fout, dict)
            and fout.get("expression_label") in ORANGE_AUX_FACE_EXPRESSIONS
        ):
            hits.append(
                RuleHit(
                    rule_id="R_SINGLE_ORANGE",
                    rule_version=RULE_VERSION,
                    field_path="channels.face.output.expression_label",
                    observed_value=fout.get("expression_label"),
                    threshold_key="ORANGE_AUX_FACE_EXPRESSIONS",
                    threshold_value=list(ORANGE_AUX_FACE_EXPRESSIONS),
                    severity="orange",
                )
            )
    return hits


def evaluate_session(analysis: dict, now: str) -> SessionGrading:
    """单次风险：按 RED -> ORANGE 顺序，先命中即返回。

    每个命中的 ``RuleHit`` 都会被填上 ``session_id`` 与 ``triggered_at``。
    """
    session_id = _session_id(analysis)

    red_hit = R_SINGLE_RED(analysis)
    if red_hit is not None:
        return SessionGrading(
            single_session_risk="red",
            rule_hits=[replace(red_hit, session_id=session_id, triggered_at=now)],
        )

    orange_hit = R_SINGLE_ORANGE(analysis)
    if orange_hit is not None:
        hits = [replace(orange_hit, session_id=session_id, triggered_at=now)]
        for aux in _orange_aux_hits(analysis):
            hits.append(replace(aux, session_id=session_id, triggered_at=now))
        return SessionGrading(single_session_risk="orange", rule_hits=hits)

    return SessionGrading(single_session_risk="none", rule_hits=[])
