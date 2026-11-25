"""演示数据种子：向真实库写入 6 个对象及其会话 / 复盘 / 工单 / 留痕。

数据全部手工指定（颜色、工单、证据），不引用 `app.grading` 的任何阈值逻辑；
只通过 `app.db` ORM 写入并单事务提交。会话面部图为脚本绘制的 300×300 灰底占位图，
不使用任何真人图像或外部素材；不生成音频文件。

用法：
    python scripts/seed_demo.py            # 幂等补齐
    python scripts/seed_demo.py --reset    # 先清空本脚本的数据域，再重建
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from collections import Counter
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import delete, func, select  # noqa: E402

from app.capture.config import STORAGE_ROOT  # noqa: E402
from app.db.constants import AUDIT_ACTIONS, SUGGESTED_METHODS  # noqa: E402
from app.db.database import SessionLocal  # noqa: E402
from app.db.models import (  # noqa: E402
    AuditLog,
    CaptureSession,
    Review,
    ReviewTicket,
    Subject,
)

FACE_SIDE = 300
FACE_JPEG_QUALITY = 90
FACE_BG = (200, 200, 200)
FACE_FG = (70, 70, 70)
FACE_TEXT = (55, 55, 55)
TRANSCRIPT_PLACEHOLDER = "（占位文本，演示数据）"

TZ = timezone(timedelta(hours=8))
NOW = datetime.now(TZ).replace(microsecond=0)
WINDOW_END = (NOW - timedelta(minutes=10)).replace(microsecond=0)
WINDOW_START = WINDOW_END - timedelta(days=7)
GRADING_VERSION = "grading@1.2"
COLOR_ORDER = ("green", "blue", "yellow", "orange", "red")

SUBJECT_SEEDS = (
    ("S001", "张三", "male", 1985),
    ("S002", "李某某", "female", 1992),
    ("S003", "王某某", "male", 1978),
    ("S004", "赵某某", "female", 1990),
    ("S005", "刘某某", "unknown", 1996),
    ("S006", "陈某某", "unknown", 1988),
)

#: S001 旧版会话由 14 天趋势窗口数据取代（其余对象保持原数量）。
SESSION_COUNTS = {
    "S001": 0,
    "S002": 9,
    "S003": 7,
    "S004": 8,
    "S005": 9,
    "S006": 1,
}

#: S001~S005 每人 2 条降级会话（约 75% 为 ok）：首个为 partial，第二个为 no_audio。
DEGRADED_INDICES = {
    "S001": (),
    "S002": (4, 8),
    "S003": (3, 7),
    "S004": (4, 8),
    "S005": (4, 8),
    "S006": (),
}

#: 手工颜色方案：2 绿、1 蓝、1 黄、1 橙、1 红（S006 危机）。
REVIEW_PLAN = {
    "S001": {
        "color": "green",
        "risk": "none",
        "trend": "green",
        "consistency": "high",
        "manual": 0,
        "rule": "R_TREND_GREEN",
        "evidence": ("TREND_GREEN_OFFSET_MAX", 22.0, 0.8, 0.42),
    },
    "S002": {
        "color": "green",
        "risk": "none",
        "trend": "green",
        "consistency": "medium",
        "manual": 0,
        "rule": "R_TREND_GREEN",
        "evidence": ("TREND_GREEN_OFFSET_MAX", 25.4, 0.8, 0.51),
    },
    "S003": {
        "color": "blue",
        "risk": "none",
        "trend": "blue",
        "consistency": "medium",
        "manual": 0,
        "rule": "R_TREND_BLUE",
        "evidence": ("TREND_BLUE_OFFSET_MIN", 41.2, 0.8, 1.02),
    },
    "S004": {
        "color": "yellow",
        "risk": "none",
        "trend": "yellow",
        "consistency": "low",
        "manual": 1,
        "rule": "R_TREND_YELLOW",
        "evidence": ("TREND_YELLOW_OFFSET_MIN", 58.7, 1.2, 1.31),
    },
    "S005": {
        "color": "orange",
        "risk": "orange",
        "trend": "green",
        "consistency": "low",
        "manual": 1,
        "rule": "R_SINGLE_ORANGE",
        "evidence": ("SINGLE_ORANGE_SIGNAL_MIN", 76.5, 70.0, 1.09),
    },
    "S006": {
        "color": "red",
        "risk": "red",
        "trend": "green",
        "consistency": "low",
        "manual": 1,
        "rule": "R_SINGLE_CRISIS",
        "evidence": (
            "SINGLE_CRISIS_INTENT_FLAG",
            "suicide_intent",
            "suicide_intent",
            1.0,
        ),
        "evidence_field": "psych.output.intent_flag",
    },
}


#: S001 演示波动：以运行当天为终点的连续 14 天（管理端趋势页演示专用）。
S001_WINDOW_DAYS = 14
S001_DAY_COLORS = (
    "green",
    "green",
    "blue",
    "yellow",
    "yellow",
    "orange",
    "blue",
    "green",
    "blue",
    "yellow",
    "orange",
    "orange",
    "yellow",
    "blue",
)
#: 缺 checkin 的日索引（制造行为缺口）。
S001_MISSING_CHECKIN = frozenset({2, 8})
#: 缺 report 的日索引（该日仍保留复盘色块）。
S001_MISSING_REPORT = frozenset({10})
#: 一致性 low 的 report 日与其中触发 conflict 的日。
S001_LOW_CONSISTENCY = frozenset({6, 9})
S001_CONFLICT_DAYS = frozenset({6})
#: 分析降级（analysis_json.degraded=true）的 report 日。
S001_DEGRADED_DAYS = frozenset({4, 13})
#: 日索引 -> (signal_strength, text_valence, arousal, emotion_label)。
S001_REPORT_PROFILE = {
    0: (45.0, -0.05, 0.42, "neutral"),
    1: (30.0, -0.60, 0.22, "low"),
    2: (50.0, -0.10, 0.48, "neutral"),
    3: (25.0, 0.45, 0.50, "neutral"),
    4: (48.0, -0.15, 0.45, "neutral"),
    5: (78.0, -0.40, 0.80, "negative"),
    6: (34.0, -0.70, 0.20, "low"),
    7: (52.0, 0.00, 0.46, "neutral"),
    8: (46.0, -0.08, 0.44, "neutral"),
    9: (28.0, -0.75, 0.18, "low"),
    11: (82.0, -0.45, 0.85, "strong_negative"),
    12: (35.0, 0.45, 0.52, "neutral"),
    13: (44.0, -0.12, 0.40, "neutral"),
}
#: S001 五色 -> (规则, trend_color, single_session_risk, consistency)。
S001_REVIEW_META = {
    "green": ("R_TREND_GREEN", "green", "none", "high"),
    "blue": ("R_TREND_BLUE", "blue", "none", "medium"),
    "yellow": ("R_TREND_YELLOW", "yellow", "none", "medium"),
    "orange": ("R_SINGLE_ORANGE", "green", "orange", "low"),
}
#: 规则 -> (threshold_key, threshold_value, offset_score)。
S001_EVIDENCE_THRESHOLDS = {
    "R_TREND_GREEN": ("TREND_GREEN_OFFSET_MAX", 0.8, 0.42),
    "R_TREND_BLUE": ("TREND_BLUE_OFFSET_MIN", 0.8, 1.02),
    "R_TREND_YELLOW": ("TREND_YELLOW_OFFSET_MIN", 1.2, 1.31),
    "R_SINGLE_ORANGE": ("SINGLE_ORANGE_SIGNAL_MIN", 70.0, 1.09),
}


def _uid(kind: str, key: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"community-correction:{kind}:{key}"))


def _iso(value: datetime) -> str:
    return value.isoformat(timespec="seconds")


def _subject_id(code: str) -> str:
    return _uid("subject", code)


def _session_id(code: str, index: int) -> str:
    return _uid("session", f"{code}:{index:02d}")


def _review_id(code: str) -> str:
    return _uid("review", code)


def _ticket_id(code: str) -> str:
    return _uid("ticket", code)


def _consent_json(granted_at: datetime) -> str:
    at = _iso(granted_at)
    return json.dumps(
        {
            "schema_version": "consent@1.0",
            "general": {"granted": True, "at": at},
            "face": {"granted": True, "at": at},
            "audio": {"granted": True, "at": at},
            "revoked_at": None,
            "retention_days": 180,
        },
        ensure_ascii=False,
    )


def _baseline_json(updated_at: datetime) -> str:
    return json.dumps(
        {
            "schema_version": "baseline@1.0",
            "sample_count": 5,
            "emotion_valence_mean": -0.05,
            "emotion_valence_std": 0.18,
            "psych_signal_mean": 28.4,
            "psych_signal_std": 7.9,
            "updated_at": _iso(updated_at),
        },
        ensure_ascii=False,
    )


def _channel(
    status: str,
    model_version: str,
    latency_ms: int,
    confidence: float,
    output: Optional[dict[str, Any]],
    reason: Optional[str] = None,
) -> dict[str, Any]:
    return {
        "status": status,
        "model_version": model_version,
        "latency_ms": latency_ms,
        "confidence": confidence,
        "output": output,
        "reason": reason,
    }


def _analysis_json(
    *,
    session_id: str,
    subject_id: str,
    captured_at: datetime,
    duration_sec: float,
    transcript_path: Optional[str],
    degraded: bool,
    signal: float,
    valence: float,
    risk_level: str,
    consistency: str,
    seed: int,
    intent_flag: str = "none",
    arousal: Optional[float] = None,
    emotion_label: Optional[str] = None,
    conflict: Optional[bool] = None,
) -> str:
    """组装严格符合 analysis.schema.json 的单次结果；skipped 通道 output=null。

    `arousal` / `emotion_label` / `conflict` 为演示波动预留的可选覆盖；
    不传时保持原有派生逻辑不变。
    """
    if degraded:
        asr = _channel("skipped", "mock-asr@1.0", 0, 0.0, None, "audio_unavailable")
        emotion = _channel(
            "skipped", "mock-emotion@1.0", 0, 0.0, None, "audio_unavailable"
        )
        face = _channel(
            "ok",
            "mock-face@1.0",
            18,
            0.72,
            {
                "expression_label": "neutral",
                "intensity": 0.24,
                "face_confidence": 0.72,
                "frame_count": 3,
                "valid_frames": 3,
            },
        )
        psych = _channel(
            "degraded",
            "mock-psych@1.0",
            31,
            0.55,
            {
                "signal_strength": signal,
                "intent_flag": "none",
                "keywords": ["累", "压力"],
                "rationale_signal": "文本通道降级，仅保留弱信号线索",
            },
            "text_channel_degraded",
        )
        agree_count = 1
        conflict = False if conflict is None else conflict
        low_confidence = ["asr", "emotion"]
        summary = "音频通道不可用，仅表情与弱文本信号，建议人工复核"
    else:
        asr = _channel(
            "ok",
            "mock-asr@1.0",
            12 + seed % 7,
            0.93,
            {
                "transcript_path": transcript_path,
                "duration_sec": duration_sec,
                "speech_ratio": round(0.45 + (seed % 4) * 0.05, 2),
                "char_count": int(duration_sec * 5),
            },
        )
        emotion = _channel(
            "ok",
            "mock-emotion@1.0",
            20 + seed % 5,
            0.81,
            {
                "valence": valence,
                "arousal": arousal
                if arousal is not None
                else round(0.32 + (seed % 5) * 0.04, 2),
                "label": emotion_label
                if emotion_label is not None
                else ("neutral" if signal < 35 else "low"),
            },
        )
        face = _channel(
            "ok",
            "mock-face@1.0",
            16 + seed % 4,
            0.67,
            {
                "expression_label": "neutral" if signal < 45 else "sad",
                "intensity": round(0.18 + (signal % 10) / 100, 2),
                "face_confidence": 0.71,
                "frame_count": 3,
                "valid_frames": 3,
            },
        )
        psych = _channel(
            "ok",
            "mock-psych@1.0",
            30 + seed % 9,
            0.78,
            {
                "signal_strength": signal,
                "intent_flag": intent_flag,
                "keywords": ["不想活"]
                if intent_flag == "suicide_intent"
                else (["累", "睡不着"] if signal >= 40 else ["还好"]),
                "rationale_signal": "出现指向性意图表达，建议立即人工复核"
                if intent_flag == "suicide_intent"
                else "出现疲劳与睡眠相关表达，未出现指向性意图",
            },
        )
        agree_count = {"high": 3, "medium": 2, "low": 1}[consistency]
        conflict = (consistency == "low") if conflict is None else conflict
        low_confidence = ["face"] if consistency == "low" else []
        summary = (
            "文本出现指向性意图表达，建议立即人工复核"
            if intent_flag == "suicide_intent"
            else "语音情绪偏低，文本未出现明确意图，表情中性"
        )

    latency_ms = sum(
        channel["latency_ms"] for channel in (asr, emotion, face, psych)
    )
    needs_review = bool(degraded or consistency == "low")
    result = {
        "schema_version": "1.0",
        "session_id": session_id,
        "subject_id": subject_id,
        "overall": {
            "text_valence": valence,
            "text_signal": signal,
            "risk_level": risk_level,
            "summary_signal": summary,
        },
        "channels": {
            "asr": asr,
            "emotion": emotion,
            "face": face,
            "psych": psych,
        },
        "consistency": consistency,
        "consistency_basis": {
            "agree_count": agree_count,
            "conflict": conflict,
            "low_confidence_channels": low_confidence,
        },
        "needs_review": needs_review,
        "degraded": degraded,
        "threshold_profile": "default@v1",
        "started_at": _iso(captured_at + timedelta(seconds=2)),
        "finished_at": _iso(captured_at + timedelta(seconds=3)),
        "latency_ms": latency_ms,
    }
    return json.dumps(result, ensure_ascii=False)


def _risk_from_signal(signal: float) -> str:
    if signal >= 70:
        return "high"
    if signal >= 55:
        return "elevated"
    if signal >= 40:
        return "watch"
    return "none"


def _s001_report_session_id(day_index: int) -> str:
    """该日 report 会话 id；缺 report 的日回落到前一有效日（仅用于证据引用）。"""
    index = day_index
    while index > 0 and index in S001_MISSING_REPORT:
        index -= 1
    return _session_id("S001", 102 + index * 2)


def _plan_s001_window(now: datetime) -> list[dict[str, Any]]:
    """S001 连续 14 天的 checkin / report 会话（新索引从 101 起，避免旧 id 冲突）。"""
    code = "S001"
    subject_id = _subject_id(code)
    today = now.date()
    rows: list[dict[str, Any]] = []
    for index in range(S001_WINDOW_DAYS):
        day = today - timedelta(days=S001_WINDOW_DAYS - 1 - index)

        if index not in S001_MISSING_CHECKIN:
            session_id = _session_id(code, 101 + index * 2)
            captured_at = datetime.combine(day, time(9, 0), tzinfo=TZ)
            base = f"subjects/{subject_id}/sessions/{session_id}"
            rows.append(
                {
                    "code": code,
                    "subject_id": subject_id,
                    "session_id": session_id,
                    "kind": "checkin",
                    "status": "captured",
                    "capture_status": "ok",
                    "face_path": f"{base}/face.jpg",
                    "audio_path": None,
                    "transcript_path": None,
                    "duration_sec": None,
                    "captured_at": captured_at,
                    "created_at": captured_at - timedelta(minutes=2),
                    "codes": [],
                    "analysis": None,
                    "analysis_status": "pending",
                }
            )

        if index not in S001_MISSING_REPORT:
            session_id = _session_id(code, 102 + index * 2)
            captured_at = datetime.combine(day, time(19, 0), tzinfo=TZ)
            base = f"subjects/{subject_id}/sessions/{session_id}"
            signal, valence, arousal, label = S001_REPORT_PROFILE[index]
            degraded = index in S001_DEGRADED_DAYS
            consistency = (
                "low"
                if index in S001_LOW_CONSISTENCY
                else ("high" if index % 2 == 0 else "medium")
            )
            duration_sec = round(20 + (index % 7) * 3, 1)
            analysis = _analysis_json(
                session_id=session_id,
                subject_id=subject_id,
                captured_at=captured_at,
                duration_sec=duration_sec,
                transcript_path=f"{base}/transcript.txt",
                degraded=degraded,
                signal=signal,
                valence=valence,
                risk_level=_risk_from_signal(signal),
                consistency=consistency,
                seed=100 + index,
                arousal=arousal,
                emotion_label=label,
                conflict=index in S001_CONFLICT_DAYS,
            )
            rows.append(
                {
                    "code": code,
                    "subject_id": subject_id,
                    "session_id": session_id,
                    "kind": "report",
                    "status": "captured",
                    "capture_status": "ok",
                    "face_path": f"{base}/face.jpg",
                    "audio_path": f"{base}/audio.wav",
                    "transcript_path": f"{base}/transcript.txt",
                    "duration_sec": duration_sec,
                    "captured_at": captured_at,
                    "created_at": captured_at - timedelta(minutes=2),
                    "codes": [],
                    "analysis": analysis,
                    "analysis_status": "degraded" if degraded else "done",
                }
            )
    return rows


def _plan_s001_reviews(now: datetime) -> list[dict[str, Any]]:
    """S001 每日一条复盘，颜色序列与规则/一致性/人工复核自洽。"""
    code = "S001"
    subject_id = _subject_id(code)
    today = now.date()
    rows: list[dict[str, Any]] = []
    for index, color in enumerate(S001_DAY_COLORS):
        day = today - timedelta(days=S001_WINDOW_DAYS - 1 - index)
        rule, trend_color, risk, consistency = S001_REVIEW_META[color]
        created_at = min(datetime.combine(day, time(21, 0), tzinfo=TZ), now)
        window_start = day - timedelta(days=6)
        session_id = _s001_report_session_id(index)
        signal = S001_REPORT_PROFILE.get(
            index, S001_REPORT_PROFILE[_s001_report_index(index)]
        )[0]
        threshold_key, threshold_value, offset_score = S001_EVIDENCE_THRESHOLDS[rule]
        evidence = [
            {
                "rule_id": rule,
                "rule_version": GRADING_VERSION,
                "field_path": "channels.psych.output.signal_strength",
                "observed_value": signal,
                "threshold_key": threshold_key,
                "threshold_value": threshold_value,
                "offset_score": offset_score,
                "session_id": session_id,
                "window": [window_start.isoformat(), day.isoformat()],
                "triggered_at": _iso(created_at),
            }
        ]
        rows.append(
            {
                "review_id": _uid("review", f"{code}:{day.isoformat()}"),
                "subject_id": subject_id,
                "source_session_id": session_id,
                "window_start": window_start,
                "window_end": day,
                "window_days": 7,
                "single_session_risk": risk,
                "trend_color": trend_color,
                "final_color": color,
                "consistency": consistency,
                "manual_review": 1 if consistency == "low" else 0,
                "rules_fired": [rule],
                "evidence": evidence,
                "created_at": created_at,
            }
        )
    return rows


def _s001_report_index(day_index: int) -> int:
    """缺 report 的日回落到前一有效日索引（证据引用用）。"""
    index = day_index
    while index > 0 and index in S001_MISSING_REPORT:
        index -= 1
    return index


def _plan_sessions() -> list[dict[str, Any]]:
    plan: list[dict[str, Any]] = []
    for subject_index, (code, _name, _gender, _birth_year) in enumerate(SUBJECT_SEEDS):
        subject_id = _subject_id(code)
        count = SESSION_COUNTS[code]
        degraded_indices = DEGRADED_INDICES[code]
        for index in range(1, count + 1):
            session_id = _session_id(code, index)
            is_degraded = index in degraded_indices
            if is_degraded:
                occurrence = degraded_indices.index(index)
                capture_status = "partial" if occurrence % 2 == 0 else "no_audio"
            else:
                capture_status = "ok"

            captured_at = NOW - timedelta(
                days=count - index, hours=subject_index + 1, minutes=index
            )
            created_at = captured_at - timedelta(minutes=2)
            duration_sec = round(15 + ((subject_index * 5 + index * 3) % 150) / 10, 1)

            signal = round(20 + ((subject_index * 13 + index * 7) % 45), 1)
            is_crisis = code == "S006"
            if code == "S005" and index == 4:
                signal = 76.5
            if is_crisis:
                signal = 96.0
                risk_level = "crisis"
            elif signal >= 70:
                risk_level = "high"
            elif signal >= 55:
                risk_level = "elevated"
            elif signal >= 40:
                risk_level = "watch"
            else:
                risk_level = "none"
            valence = round(-0.05 - (signal - 20) / 100, 2)
            if is_crisis:
                consistency = "low"
            elif capture_status == "ok":
                consistency = ("high", "medium", "low")[
                    (subject_index + index) % 3
                ]
            else:
                consistency = "low"

            base = f"subjects/{subject_id}/sessions/{session_id}"
            face_path = f"{base}/face.jpg"
            has_audio = capture_status == "ok"
            audio_path = f"{base}/audio.wav" if has_audio else None
            transcript_path = f"{base}/transcript.txt" if has_audio else None
            codes = [] if capture_status == "ok" else ["audio_too_short"]

            analysis = _analysis_json(
                session_id=session_id,
                subject_id=subject_id,
                captured_at=captured_at,
                duration_sec=duration_sec,
                transcript_path=transcript_path,
                degraded=not has_audio,
                signal=signal,
                valence=valence,
                risk_level=risk_level,
                consistency=consistency,
                seed=subject_index * 10 + index,
                intent_flag="suicide_intent" if is_crisis else "none",
            )
            plan.append(
                {
                    "code": code,
                    "subject_id": subject_id,
                    "session_id": session_id,
                    "kind": "report",
                    "status": "captured",
                    "capture_status": capture_status,
                    "face_path": face_path,
                    "audio_path": audio_path,
                    "transcript_path": transcript_path,
                    "duration_sec": duration_sec,
                    "captured_at": captured_at,
                    "created_at": created_at,
                    "codes": codes,
                    "analysis": analysis,
                    "analysis_status": "degraded"
                    if capture_status != "ok"
                    else "done",
                }
            )
    plan.extend(_plan_s001_window(NOW))
    return plan


def _evidence(
    plan: dict[str, Any],
    session_id: str,
    observed_value: Any,
    threshold_key: str,
    threshold_value: Any,
    offset_score: float,
    field_path: str = "psych.output.signal_strength",
) -> list[dict[str, Any]]:
    return [
        {
            "rule_id": plan["rule"],
            "rule_version": GRADING_VERSION,
            "field_path": field_path,
            "observed_value": observed_value,
            "threshold_key": threshold_key,
            "threshold_value": threshold_value,
            "offset_score": offset_score,
            "session_id": session_id,
            "window": [
                WINDOW_START.date().isoformat(),
                WINDOW_END.date().isoformat(),
            ],
            "triggered_at": _iso(WINDOW_END),
        }
    ]


def _latest_session(plan: list[dict[str, Any]], code: str) -> dict[str, Any]:
    rows = [row for row in plan if row["code"] == code]
    return max(rows, key=lambda row: row["captured_at"])


def _first_partial_session(plan: list[dict[str, Any]], code: str) -> dict[str, Any]:
    for row in plan:
        if row["code"] == code and row["capture_status"] == "partial":
            return row
    raise RuntimeError(f"no partial session planned for {code}")


def _counts_template() -> dict[str, dict[str, int]]:
    return {
        name: {"inserted": 0, "skipped": 0}
        for name in (
            "subjects",
            "sessions",
            "reviews",
            "review_tickets",
            "audit_logs",
        )
    }


def _reset(db, subject_ids: list[str], session_ids: list[str]) -> dict[str, int]:
    deleted: dict[str, int] = {}
    deleted["tickets"] = db.execute(
        delete(ReviewTicket).where(ReviewTicket.subject_id.in_(subject_ids))
    ).rowcount
    deleted["reviews"] = db.execute(
        delete(Review).where(Review.subject_id.in_(subject_ids))
    ).rowcount
    deleted["audit_logs"] = db.execute(
        delete(AuditLog).where(AuditLog.target_id.in_(session_ids))
    ).rowcount
    deleted["sessions"] = db.execute(
        delete(CaptureSession).where(CaptureSession.subject_id.in_(subject_ids))
    ).rowcount
    deleted["subjects"] = db.execute(
        delete(Subject).where(Subject.id.in_(subject_ids))
    ).rowcount
    return deleted


def _seed(db, plan: list[dict[str, Any]], counts: dict[str, dict[str, int]]) -> None:
    subject_ids = [_subject_id(code) for code, *_ in SUBJECT_SEEDS]

    # subjects
    fresh_subjects = []
    for code, name, gender, birth_year in SUBJECT_SEEDS:
        subject_id = _subject_id(code)
        if db.get(Subject, subject_id) is not None:
            counts["subjects"]["skipped"] += 1
            continue
        consent_at = NOW - timedelta(days=25)
        fresh_subjects.append(
            Subject(
                id=subject_id,
                code=code,
                name=name,
                gender=gender,
                birth_year=birth_year,
                status="active",
                consent_json=_consent_json(consent_at),
                baseline_json=_baseline_json(NOW - timedelta(days=2)),
                created_at=_iso(NOW - timedelta(days=30)),
                updated_at=_iso(NOW - timedelta(days=2)),
            )
        )
        counts["subjects"]["inserted"] += 1
    db.add_all(fresh_subjects)
    db.flush()

    # sessions
    fresh_sessions = []
    for row in plan:
        if db.get(CaptureSession, row["session_id"]) is not None:
            counts["sessions"]["skipped"] += 1
            continue
        fresh_sessions.append(
            CaptureSession(
                id=row["session_id"],
                subject_id=row["subject_id"],
                kind=row["kind"],
                status=row["status"],
                capture_status=row["capture_status"],
                face_path=row["face_path"],
                audio_path=row["audio_path"],
                transcript_path=row["transcript_path"],
                duration_sec=row["duration_sec"],
                captured_at=_iso(row["captured_at"]),
                analysis_status=row["analysis_status"],
                analysis_json=row["analysis"],
                codes=json.dumps(row["codes"]),
                created_at=_iso(row["created_at"]),
                updated_at=_iso(row["captured_at"] + timedelta(seconds=3)),
            )
        )
        counts["sessions"]["inserted"] += 1
    db.add_all(fresh_sessions)
    db.flush()

    # reviews
    review_ids: dict[str, str] = {}
    review_evidence: dict[str, list[dict[str, Any]]] = {}
    fresh_reviews = []
    for code, *_rest in SUBJECT_SEEDS:
        plan_row = REVIEW_PLAN[code]
        review_id = _review_id(code)
        review_ids[code] = review_id
        latest = _latest_session(plan, code)
        evidence_session = (
            _first_partial_session(plan, code)
            if plan_row["color"] == "orange"
            else latest
        )
        threshold_key, observed, threshold_value, offset = plan_row["evidence"]
        evidence = _evidence(
            plan_row,
            evidence_session["session_id"],
            observed,
            threshold_key,
            threshold_value,
            offset,
            plan_row.get("evidence_field", "psych.output.signal_strength"),
        )
        review_evidence[code] = evidence
        if db.get(Review, review_id) is not None:
            counts["reviews"]["skipped"] += 1
            continue
        fresh_reviews.append(
            Review(
                id=review_id,
                subject_id=latest["subject_id"],
                source_session_id=latest["session_id"],
                window_start=_iso(WINDOW_START),
                window_end=_iso(WINDOW_END),
                window_days=7,
                single_session_risk=plan_row["risk"],
                trend_color=plan_row["trend"],
                final_color=plan_row["color"],
                consistency=plan_row["consistency"],
                manual_review=plan_row["manual"],
                rules_fired=json.dumps([plan_row["rule"]]),
                evidence_json=json.dumps(evidence, ensure_ascii=False),
                grading_version=GRADING_VERSION,
                created_at=_iso(WINDOW_END),
            )
        )
        counts["reviews"]["inserted"] += 1
    db.add_all(fresh_reviews)
    db.flush()

    # S001 连续 14 天每日复盘：按 (subject_id, window_end) 预检查，已存在则跳过。
    s001_id = _subject_id("S001")
    existing_window_ends = set(
        db.scalars(
            select(Review.window_end).where(Review.subject_id == s001_id)
        ).all()
    )
    for row in _plan_s001_reviews(NOW):
        window_end = row["window_end"].isoformat()
        if window_end in existing_window_ends or db.get(
            Review, row["review_id"]
        ) is not None:
            counts["reviews"]["skipped"] += 1
            continue
        db.add(
            Review(
                id=row["review_id"],
                subject_id=row["subject_id"],
                source_session_id=row["source_session_id"],
                window_start=row["window_start"].isoformat(),
                window_end=window_end,
                window_days=row["window_days"],
                single_session_risk=row["single_session_risk"],
                trend_color=row["trend_color"],
                final_color=row["final_color"],
                consistency=row["consistency"],
                manual_review=row["manual_review"],
                rules_fired=json.dumps(row["rules_fired"]),
                evidence_json=json.dumps(row["evidence"], ensure_ascii=False),
                grading_version=GRADING_VERSION,
                created_at=_iso(row["created_at"]),
            )
        )
        existing_window_ends.add(window_end)
        counts["reviews"]["inserted"] += 1
    db.flush()

    # review_tickets：橙 -> P0，黄 -> P1，S006 危机 -> P0
    ticket_plan = (
        ("S005", "P0", "priority_interview", "E1024", timedelta(hours=23)),
        ("S004", "P1", "focused_interview", "E2087", timedelta(hours=70)),
        ("S006", "P0", "priority_interview", "E1024", timedelta(hours=20)),
    )
    fresh_tickets = []
    for code, priority, method, assignee, due_delta in ticket_plan:
        assert method in SUGGESTED_METHODS
        ticket_id = _ticket_id(code)
        if db.get(ReviewTicket, ticket_id) is not None:
            counts["review_tickets"]["skipped"] += 1
            continue
        plan_row = REVIEW_PLAN[code]
        fresh_tickets.append(
            ReviewTicket(
                id=ticket_id,
                review_id=review_ids[code],
                subject_id=_subject_id(code),
                status="pending",
                priority=priority,
                due_at=_iso(WINDOW_END + due_delta),
                triggered_rules=json.dumps([plan_row["rule"]]),
                evidence_json=json.dumps(
                    review_evidence[code], ensure_ascii=False
                ),
                suggested_method=method,
                assignee=assignee,
                conclusion_color=None,
                conclusion_note=None,
                opened_at=_iso(WINDOW_END),
                closed_at=None,
            )
        )
        counts["review_tickets"]["inserted"] += 1
    db.add_all(fresh_tickets)
    db.flush()

    # audit_logs：4 条 sensitive.view
    assert "sensitive.view" in AUDIT_ACTIONS
    fresh_audits = []
    for code in ("S001", "S002", "S003", "S004"):
        latest = _latest_session(plan, code)
        request_id = _uid("audit", f"{code}:{SESSION_COUNTS[code]:02d}")
        exists = db.scalars(
            select(AuditLog).where(AuditLog.request_id == request_id)
        ).first()
        if exists is not None:
            counts["audit_logs"]["skipped"] += 1
            continue
        fresh_audits.append(
            AuditLog(
                actor_type="staff",
                actor_id="E1024",
                action="sensitive.view",
                target_type="session",
                target_id=latest["session_id"],
                detail_json=json.dumps({"field": "face"}),
                request_id=request_id,
                created_at=_iso(latest["captured_at"] + timedelta(minutes=5)),
            )
        )
        counts["audit_logs"]["inserted"] += 1
    db.add_all(fresh_audits)


def _print_summary(db, plan, counts, subject_ids, session_ids) -> None:
    for name, row in counts.items():
        print(f"{name}: inserted {row['inserted']} / skipped {row['skipped']}")
    inserted = sum(row["inserted"] for row in counts.values())
    skipped = sum(row["skipped"] for row in counts.values())
    print(f"inserted {inserted} / skipped {skipped}")

    subject_total = db.scalar(
        select(func.count()).select_from(Subject).where(Subject.id.in_(subject_ids))
    )
    session_total = db.scalar(
        select(func.count())
        .select_from(CaptureSession)
        .where(CaptureSession.id.in_(session_ids))
    )
    review_total = db.scalar(
        select(func.count())
        .select_from(Review)
        .where(Review.subject_id.in_(subject_ids))
    )
    ticket_total = db.scalar(
        select(func.count())
        .select_from(ReviewTicket)
        .where(ReviewTicket.subject_id.in_(subject_ids))
    )
    audit_total = db.scalar(
        select(func.count())
        .select_from(AuditLog)
        .where(AuditLog.target_id.in_(session_ids))
    )
    print(
        "seeded: subjects={} sessions={} reviews={} tickets={} audit_logs={}".format(
            subject_total,
            session_total,
            review_total,
            ticket_total,
            audit_total,
        )
    )

    colors = Counter(
        db.scalars(
            select(Review.final_color).where(Review.subject_id.in_(subject_ids))
        ).all()
    )
    print("colors: " + " ".join(f"{color}={colors.get(color, 0)}" for color in COLOR_ORDER))


def _resolve_media_path(root: Path, rel_path: str) -> Path:
    """解析相对路径并做越界保护：结果必须仍在 STORAGE_ROOT 之内。"""
    target = (root / rel_path).resolve()
    if not target.is_relative_to(root):
        raise ValueError("path escapes STORAGE_ROOT")
    return target


def _write_face_placeholder(path: Path) -> None:
    """绘制 300×300 灰底 + 深灰几何剪影 + 底部 ASCII placeholder。"""
    image = np.full((FACE_SIDE, FACE_SIDE, 3), FACE_BG, dtype=np.uint8)
    cv2.circle(image, (150, 112), 46, FACE_FG, -1)
    shoulders = np.array(
        [[92, 258], [208, 258], [178, 172], [122, 172]], dtype=np.int32
    )
    cv2.fillPoly(image, [shoulders], FACE_FG)
    cv2.putText(
        image,
        "placeholder",
        (86, 288),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.5,
        FACE_TEXT,
        1,
        cv2.LINE_AA,
    )
    ok, buffer = cv2.imencode(
        ".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), FACE_JPEG_QUALITY]
    )
    if not ok:
        raise RuntimeError("jpeg encode failed")
    path.write_bytes(buffer.tobytes())

    written = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if written is None or written.shape != (FACE_SIDE, FACE_SIDE, 3):
        raise RuntimeError("placeholder image shape mismatch")


def _write_transcript_placeholder(path: Path) -> None:
    path.write_text(TRANSCRIPT_PLACEHOLDER + "\n", encoding="utf-8")


def _ensure_one_media(
    root: Path,
    rel_path: str,
    writer,
    stats: dict[str, int],
    written_key: str,
    skipped_key: str,
    failures: list[str],
) -> None:
    """只写不覆盖：已存在即跳过，保护可能存在的真实采集数据。"""
    try:
        target = _resolve_media_path(root, rel_path)
        if target.exists():
            stats[skipped_key] += 1
            return
        target.parent.mkdir(parents=True, exist_ok=True)
        writer(target)
        stats[written_key] += 1
    except Exception as exc:  # noqa: BLE001 - 单文件失败不阻断其余文件
        failures.append(rel_path)
        print(f"media error: {rel_path}: {type(exc).__name__}: {exc}")


def _ensure_media(plan: list[dict[str, Any]]) -> tuple[dict[str, int], list[str]]:
    root = Path(STORAGE_ROOT).resolve()
    stats = {
        "faces_written": 0,
        "faces_skipped": 0,
        "transcripts_written": 0,
        "transcripts_skipped": 0,
    }
    failures: list[str] = []
    for row in plan:
        _ensure_one_media(
            root,
            row["face_path"],
            _write_face_placeholder,
            stats,
            "faces_written",
            "faces_skipped",
            failures,
        )
        if row["transcript_path"]:
            _ensure_one_media(
                root,
                row["transcript_path"],
                _write_transcript_placeholder,
                stats,
                "transcripts_written",
                "transcripts_skipped",
                failures,
            )
    return stats, failures


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Seed demo data for community-correction.")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="先删除本脚本数据域（tickets/reviews/audit_logs/sessions/subjects）再重建",
    )
    args = parser.parse_args(argv)

    plan = _plan_sessions()
    subject_ids = [_subject_id(code) for code, *_ in SUBJECT_SEEDS]
    session_ids = [row["session_id"] for row in plan]
    counts = _counts_template()
    media_failures: list[str] = []

    db = SessionLocal()
    try:
        if args.reset:
            deleted = _reset(db, subject_ids, session_ids)
            print(
                "reset: tickets={tickets} reviews={reviews} audit_logs={audit_logs} "
                "sessions={sessions} subjects={subjects}".format(**deleted)
            )
        _seed(db, plan, counts)
        db.commit()
        media_stats, media_failures = _ensure_media(plan)
        _print_summary(db, plan, counts, subject_ids, session_ids)
        print(
            "media: faces_written={faces_written} faces_skipped={faces_skipped} "
            "transcripts_written={transcripts_written} "
            "transcripts_skipped={transcripts_skipped}".format(**media_stats)
        )
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    if media_failures:
        print(f"media_errors={len(media_failures)}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
