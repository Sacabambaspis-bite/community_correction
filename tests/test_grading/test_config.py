"""config 不变量：缺键抛 KeyError；规则模块源码不含阈值数字字面量。"""

from __future__ import annotations

import io
import tokenize
from pathlib import Path

import pytest

import app.grading.config as cfg
from app.grading.config import THRESHOLDS, validate_config

_RULE_MODULES = ["single.py", "trend.py", "compose.py", "ticket.py"]
_GRADING_DIR = Path(cfg.__file__).resolve().parent


# ---------- validate_config ----------

def test_validate_config_passes():
    validate_config()  # 不应抛异常


@pytest.mark.parametrize("key", [
    "SINGLE_RED_SELFHARM_SIGNAL",
    "TREND_YELLOW_OFFSET_MIN",
    "BASELINE_MIN_STD",
    "CONSISTENCY_CAP_COLOR",
    "RISK_VALENCE_HIGH_MIN",
])
def test_validate_config_missing_key_raises(monkeypatch, key):
    monkeypatch.delitem(cfg.THRESHOLDS, key)
    with pytest.raises(KeyError):
        validate_config()


# ---------- 阈值只在 config 一处 ----------

def _numeric_literals(path: Path) -> set:
    """提取源码中的数字字面量（int/float），用于扫描是否硬编码阈值。"""
    src = path.read_text(encoding="utf-8")
    nums: set = set()
    for tok in tokenize.generate_tokens(io.StringIO(src).readline):
        if tok.type == tokenize.NUMBER:
            try:
                nums.add(eval(tok.string))  # noqa: S307 - 仅解析数字字面量
            except Exception:  # noqa: BLE001
                continue
    return nums


def test_rule_modules_have_no_threshold_literals():
    # 禁止出现在规则模块中的数值阈值。
    # - 用 (type, value) 元组比较：避免下标 window[1] 这类 int 字面量误匹配
    #   float 阈值（Python 中 1 == 1.0）；
    # - float 0.0 是 R_BASELINE_INSUFFICIENT 的「无偏移」哨兵，允许出现。
    forbidden = {
        (type(v), v)
        for v in THRESHOLDS.values()
        if isinstance(v, (int, float)) and not (isinstance(v, float) and v == 0.0)
    }
    offenders: list[str] = []
    for name in _RULE_MODULES:
        path = _GRADING_DIR / name
        literals = _numeric_literals(path)
        leaked = {(type(n), n) for n in literals} & forbidden
        if leaked:
            offenders.append(f"{name}: {sorted(v for _, v in leaked)}")
    assert not offenders, (
        "规则模块出现阈值数字字面量（阈值只能在 config.py）：" + "; ".join(offenders)
    )


def test_config_constants_present():
    assert cfg.THRESHOLD_PROFILE == "default@v1"
    assert cfg.RULE_VERSION == "grading@1.2"
    assert set(cfg.DEADLINE_HOURS) == {"P0", "P1", "P2"}
    assert set(cfg.SUGGESTED_METHOD) >= {"red", "orange", "yellow", "blue"}
