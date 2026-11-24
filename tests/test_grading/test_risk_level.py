"""map_risk_level：断点边界 + monotonic + 意图覆写 + mock 场景自洽。"""

from __future__ import annotations

import pytest

from app.grading import map_risk_level

_LEVEL_RANK = {"none": 0, "watch": 1, "elevated": 2, "high": 3, "crisis": 4}


# ---------- 断点边界 ----------

@pytest.mark.parametrize(
    "valence,expected",
    [
        (0.5, "none"),
        (0.0, "none"),          # RISK_VALENCE_NONE_MIN
        (-0.19, "watch"),
        (-0.2, "watch"),        # RISK_VALENCE_WATCH_MIN
        (-0.49, "elevated"),
        (-0.5, "elevated"),     # RISK_VALENCE_ELEVATED_MIN
        (-0.79, "high"),
        (-0.8, "high"),         # RISK_VALENCE_HIGH_MIN
        (-0.81, "crisis"),
        (-0.9, "crisis"),
    ],
)
def test_risk_level_boundaries(valence, expected):
    assert map_risk_level(valence) == expected


# ---------- 单调 ----------

def test_risk_level_monotonic():
    vals = [0.5, 0.0, -0.19, -0.2, -0.49, -0.5, -0.79, -0.8, -0.81, -1.0]
    levels = [map_risk_level(v) for v in vals]
    ranks = [_LEVEL_RANK[l] for l in levels]
    # valence 递减时 level 单调不减
    assert all(ranks[i] <= ranks[i + 1] for i in range(len(ranks) - 1))
    assert levels[0] == "none"
    assert levels[-1] == "crisis"


# ---------- 意图覆写 ----------

@pytest.mark.parametrize("intent", ["suicide_intent", "self_harm_mention"])
def test_intent_override_to_crisis_even_when_valence_normal(intent):
    # 关键用例：text_valence 正常但出现明确意图 -> crisis
    assert map_risk_level(0.0, intent_flag=intent) == "crisis"
    assert map_risk_level(0.9, intent_flag=intent) == "crisis"


def test_intent_none_does_not_override():
    assert map_risk_level(0.0, intent_flag="none") == "none"


# ---------- mock 场景值自洽（与 app/analysis/providers/scenarios.py 对齐） ----------

@pytest.mark.parametrize(
    "scenario_valence,intent,expected",
    [
        (0.0, "none", "none"),         # normal
        (-0.65, "none", "high"),       # negative
        (-0.9, "suicide_intent", "crisis"),  # crisis
        (-0.6, "none", "high"),        # conflict
    ],
)
def test_mock_scenario_values_self_consistent(scenario_valence, intent, expected):
    assert map_risk_level(scenario_valence, intent_flag=intent) == expected
