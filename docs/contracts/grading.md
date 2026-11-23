# 契约 · 分级（grading）

| 项 | 值 |
|---|---|
| 契约版本 | `grading@1.2` |
| 所有者 | grading-engineer（`app/grading/`） |
| 业务规则 | [../grading.md](../grading.md)（唯一权威） |
| 上游 | `AnalysisResult`（[analysis.schema.json](./analysis.schema.json)） |
| 下游 | `api` 落 `reviews` / `review_tickets` |

> v1.2 已冻结，后续仅接受实现驱动的变更。

> 本文只写**工程契约**：函数签名、数据结构、配置键、测试矩阵。五色含义、规则语义、阈值标定说明一律以 [../grading.md](../grading.md) 为准，本文不重复定义。

---

## 1. 模块边界

`app/grading/` 是**纯函数模块**：不读数据库、不读文件、不发起网络请求、不写日志中的业务数据。

```python
# 允许
from app.grading.config import THRESHOLDS

# 禁止
from app.db import Session          # 不碰库
from app.api import ...             # 不反向依赖
from app.analysis import ...        # 只接受已校验 dict / dataclass
```

目录结构：

```
app/grading/
├── __init__.py
├── config.py         # 阈值与枚举集中定义
├── models.py         # dataclass：输入输出结构
├── single.py         # 单次风险规则
├── trend.py          # 周期趋势规则
├── compose.py        # 合成与封顶
└── ticket.py         # 工单草案生成
```

## 2. 数据结构

```python
from dataclasses import dataclass, field
from typing import Literal, Optional

Color = Literal["green", "blue", "yellow", "orange", "red"]
Priority = Literal["P0", "P1", "P2"]
Consistency = Literal["high", "medium", "low"]


@dataclass(frozen=True)
class RuleHit:
    rule_id: str
    rule_version: str
    field_path: str
    observed_value: float | str | bool
    threshold_key: str
    threshold_value: float | str
    severity: Color
    session_id: Optional[str] = None
    window: Optional[tuple[str, str]] = None
    triggered_at: str = ""

    def to_evidence(self) -> dict: ...


@dataclass(frozen=True)
class SessionGrading:
    single_session_risk: Literal["red", "orange", "none"]
    rule_hits: list[RuleHit] = field(default_factory=list)


@dataclass(frozen=True)
class PeriodGrading:
    trend_color: Literal["green", "blue", "yellow"]
    offset_score: float
    rule_hits: list[RuleHit] = field(default_factory=list)
    window: tuple[str, str] = ("", "")


@dataclass(frozen=True)
class FinalGrading:
    final_color: Color
    manual_review: bool
    needs_review: bool
    rules_fired: list[str]
    evidence: list[dict]
    grading_version: str
```

约束：

- `offset_score` 在 `R_BASELINE_INSUFFICIENT` 命中时置 `0.0`，并在证据里标注 `insufficient`；
- `evidence` 为 `RuleHit.to_evidence()` 的输出列表，字段名与 [db.md](./db.md) `evidence_json` 一致；
- 所有 dataclass 均为 `frozen`，规则函数不得修改入参。

## 3. 规则函数清单

函数名与规则编号**一一对应**，一个规则一个纯函数，返回 `RuleHit | None`。

| 规则编号 | 函数 | 输入 | 输出 | 依据 |
|---|---|---|---|---|
| `R_SINGLE_RED` | `R_SINGLE_RED(analysis) -> RuleHit \| None` | `dict`（已通过 schema 校验） | `severity=red` | grading.md §3 |
| `R_SINGLE_ORANGE` | `R_SINGLE_ORANGE(analysis) -> RuleHit \| None` | 同上 | `severity=orange` | grading.md §3 |
| `R_TREND_GREEN` | `R_TREND_GREEN(offset, window) -> RuleHit \| None` | `float`, `tuple` | `severity=green` | grading.md §4.2 |
| `R_TREND_BLUE` | `R_TREND_BLUE(offset, window) -> RuleHit \| None` | 同上 | `severity=blue` | grading.md §4.2 |
| `R_TREND_YELLOW` | `R_TREND_YELLOW(offset, window) -> RuleHit \| None` | 同上 | `severity=yellow` | grading.md §4.2 |
| `R_BASELINE_INSUFFICIENT` | `R_BASELINE_INSUFFICIENT(reason, window) -> RuleHit` | `reason: str` | `severity=blue` | grading.md §4.2 |
| `R_CONSISTENCY_CAP` | `R_CONSISTENCY_CAP(consistency, prior_color) -> RuleHit \| None` | `str`, `Color` | `severity=orange` | grading.md §5.2 |
| `R_DEGRADED_REVIEW` | `R_DEGRADED_REVIEW(degraded, final_color, now) -> RuleHit \| None` | `bool`, `Color` | `severity` 取 `final_color`，仅用于建单 | grading.md §6 |

### 3.1 命名约束

- 规则函数大写命名，直接使用规则编号；
- 不允许一个函数处理两条规则；
- 新增规则必须先在 [../grading.md](../grading.md) 定义编号与语义，再在本文登记。

## 4. 编排函数

```python
def evaluate_session(analysis: dict, now: str) -> SessionGrading:
    """单次风险。按 R_SINGLE_RED → R_SINGLE_ORANGE 顺序，先命中即返回。"""


def evaluate_period(
    sessions: list[dict],          # 窗口内会话的 analysis dict，至少含 psych 与 session_id
    baseline: dict,                # subjects.baseline_json 反序列化结果
    window: tuple[str, str],
    now: str,
) -> PeriodGrading:
    """周期趋势。基线/会话不足时返回 R_BASELINE_INSUFFICIENT。"""


def compose(
    session_grading: SessionGrading,
    period_grading: PeriodGrading,
    consistency: str,
    degraded: bool,
    now: str,
) -> FinalGrading:
    """合成：取大 → 低一致性封顶 → 标记复核。
    `degraded` 由 `analysis_status == "degraded"` 得到，仅表示分析降级；采集降级不走此参数。"""


def build_ticket(final: FinalGrading, review_id: str, subject_id: str, now: str) -> dict:
    """生成工单草案，字段与 db.md 的 review_tickets 对齐。
    仅当 final_color == "green" 且 needs_review == false 时抛 ValueError；
    「绿 + 降级」(R_DEGRADED_REVIEW) 属于允许建单的组合。"""
```

### 4.1 编排顺序（不得调换）

```
evaluate_session → evaluate_period → compose → build_ticket
```

`compose` 内部严格按 grading.md §5 的四步执行，顺序错误（例如先封顶再取大）视为实现 bug。

### 4.2 异常约定

| 情况 | 行为 |
|---|---|
| `analysis` 缺 `channels.psych` | 抛 `ValueError("missing_psych_channel")` |
| `analysis` 未通过 schema 校验 | 由调用方拦截；本模块仍做必填键检查 |
| `build_ticket` 传入绿结果 | 绿且 `needs_review=false` 时抛 `ValueError("ticket_not_allowed_for_green")` |
| 阈值配置缺失 | 启动期校验，缺失即 `KeyError`，不做默认兜底 |

## 5. `config.py` 配置键

```python
THRESHOLD_PROFILE = "default@v1"

THRESHOLDS: dict[str, float | str] = {
    "SINGLE_RED_SELFHARM_SIGNAL": 80,      # TODO: 待标定
    "SINGLE_ORANGE_SIGNAL_MIN": 70,        # TODO: 待标定
    "TREND_BLUE_OFFSET_MIN": 0.8,          # TODO: 待标定
    "TREND_YELLOW_OFFSET_MIN": 1.5,        # TODO: 待标定
    "BASELINE_MIN_SAMPLES": 3,             # TODO: 待标定
    "BASELINE_MIN_STD": 1.0,               # TODO: 待标定
    "TREND_MIN_SESSIONS": 2,               # TODO: 待标定
    "CONSISTENCY_MIN_CONFIDENCE": 0.6,     # TODO: 待标定
    "CONSISTENCY_CAP_COLOR": "orange",     # TODO: 待标定
}

DEADLINE_HOURS: dict[str, int] = {"P0": 24, "P1": 72, "P2": 168}

SUGGESTED_METHOD: dict[str, str] = {
    "red": "urgent_escalation",
    "orange": "priority_interview",
    "yellow": "focused_interview",
    "blue": "routine_checkin",
}
```

规则：

- 阈值只允许在 `config.py` 出现一次，规则函数内不得写数字字面量；
- 每个新阈值必须带 `# TODO: 待标定` 或注明具体来源，禁止编造出处；
- 变更阈值不改函数签名，仅改配置。

## 6. 工单草案结构

`build_ticket` 返回（字段与 [db.md](./db.md) `review_tickets` 一一对应）：

```json
{
  "review_id": "c41d0a77-9b2e-4f83-a1c5-6d7e8f9a0b1c",
  "subject_id": "3b1e7c90-2f4a-4d51-8c6b-7d9e0f1a2b3c",
  "status": "pending",
  "priority": "P2",
  "due_at": "2026-11-30T15:20:00+08:00",
  "triggered_rules": ["R_TREND_BLUE"],
  "evidence_json": [
    {
      "rule_id": "R_TREND_BLUE",
      "rule_version": "grading@1.2",
      "field_path": "channels.psych.output.signal_strength",
      "observed_value": 41.2,
      "threshold_key": "TREND_BLUE_OFFSET_MIN",
      "threshold_value": 0.8,
      "offset_score": 1.02,
      "session_id": "8f3c1b2e-4a5d-4c6e-9f10-1a2b3c4d5e6f",
      "window": ["2026-11-17", "2026-11-23"],
      "triggered_at": "2026-11-23T15:20:00+08:00"
    }
  ],
  "suggested_method": "routine_checkin",
  "opened_at": "2026-11-23T15:20:00+08:00"
}
```

`priority` 取值规则见 [../grading.md](../grading.md#6-复核触发条件)，映射表：

| 最终色 / 条件 | priority |
|---|---|
| `red` / `orange` / 低一致性 | `P0` |
| `yellow` / 降级补采 | `P1` |
| `blue` | `P2` |

## 7. pytest 覆盖矩阵

`tests/test_grading/` 必须覆盖：

| 用例 | 规则 | 断言重点 |
|---|---|---|
| 明确意图 | `R_SINGLE_RED` | `intent_flag=suicide_intent` 直接红，即使 consistency=low 仍为红 |
| 自伤提及边界 | `R_SINGLE_RED` | `signal=79.9` 不红；`80` 红；`80.1` 红 |
| 强消极无意图 | `R_SINGLE_ORANGE` | `signal=69.9/70/70.1` 三点 |
| 单次未命中 | — | 返回 `none` |
| 趋势黄边界 | `R_TREND_YELLOW` | `offset=1.499/1.5/1.501` |
| 趋势蓝边界 | `R_TREND_BLUE` | `offset=0.799/0.8/1.499` |
| 趋势绿 | `R_TREND_GREEN` | `offset<=0` 也为绿 |
| 基线不足 | `R_BASELINE_INSUFFICIENT` | `sample_count=2` → 蓝 |
| 窗口会话不足 | `R_BASELINE_INSUFFICIENT` | 1 条会话 → 蓝 |
| 标准差为零 | 趋势 | `std=0` 时用 `BASELINE_MIN_STD`，不除零 |
| 封顶 | `R_CONSISTENCY_CAP` | 红+low 仍红；橙+low 仍橙；黄+low 仍黄；绿+low 变橙 |
| 取大 | `compose` | 六组组合对照 grading.md §5.1 |
| 复核标记 | `compose` | `low` 必 `manual_review=True`；`degraded` 必 `needs_review=True` |
| 采集降级 | 规则 8 | `capture_status in (partial,no_face,no_audio)` → `consistency=low`、`final_color<=orange`、必建 `P0` 单 |
| 绿 + 降级 | `R_DEGRADED_REVIEW` | 最终绿且 `degraded=True` 时仍建单，`priority=P1` |
| 建单 | `build_ticket` | 绿且 `needs_review=False` 抛异常；「绿 + 降级」不抛；非绿字段齐全；`due_at` 按 P 级计算 |
| 跨月窗口 | `evaluate_period` | `2026-01-28 ~ 2026-02-03` 正常计算 |
| 幂等 | `build_ticket` | 相同输入输出一致，不含随机值 |

边界用例统一用参数化写法：

```python
@pytest.mark.parametrize("signal,expected", [(79.9, None), (80.0, "red"), (80.1, "red")])
def test_red_boundary(signal, expected): ...
```

## 8. 禁止项

1. 规则函数内出现阈值数字字面量；
2. 用 `consistency` 修改 `risk_level` 或 `single_session_risk`；
3. 在 `grading` 内读写数据库、文件、网络；
4. 绿结果且 `needs_review=false` 时生成工单（「绿 + 降级」除外）；
5. 证据缺 `field_path` 或 `threshold_key`；
6. 输出诊断性字段（如 `depression_score`）；
7. 规则函数使用随机数或当前时间作为逻辑输入（时间只能进 `triggered_at`）。
