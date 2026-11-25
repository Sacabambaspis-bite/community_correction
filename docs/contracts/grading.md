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

> **v1.2 实现补记（2026-11-24，附加、非破坏）**：随 `app/grading/` 落地（提交 `67adee6`）登记实现驱动新增项——`RuleHit` 可选字段 `offset_score` / `insufficient`、`FinalGrading.review_reason`、`map_risk_level` 与相关配置键、复核任务 `priority` / `suggested_method` 覆写规则、`build_ticket` 的 `now` 时区校验。规则编号与 `rule_version` 均保持 `grading@1.2` 不变。

> **v1.2 实现补记·二（2026-11-24，附加、非破坏）**：backend 集成前补齐 `build_ticket` 的规则 5 语义——`manual_review=True`（低一致性）时 `priority` 覆写为 `P0`，`suggested_method` 仍按最终色；同时明确复盘生成前提（窗口内存在可用分析会话，见 §4.3）、`review_tickets.id` 与 `review_id` 的区别。`rule_version` 仍为 `grading@1.2`。

> **v1.2 实现补记·三（2026-11-24，附加、非破坏）**：双模块适配——
> 1. **`kind=checkin`（刷脸签到，face_only 为期望覆盖）**：规则 8 的「缺音频」强制条款不适用——backend 不得对 checkin 因 `no_audio`/单模态覆写 `capture_degraded`，不强制 `consistency=low`、不强制 P0/recapture；分析时 asr/emotion/psych 的 `skipped` 属**预期**（emotion 依赖音频、psych 依赖 asr），不计入 `degraded`/`needs_review`；色码仅由 face 通道合成，`map_risk_level` 以 `text_valence=0.0, intent_flag="none"` 调用。checkin 出现 `no_face`/`error` 仍属采集异常，按既有规则处理。
> 2. **逾期复核（不走进分析管线、不改会话状态）**：超过 `checkin_interval_days` / `report_interval_days` 未完成对应类型采集时，由 backend 幂等生成 **P0** 复核任务，`suggested_method=talk_to_staff`，`detail_json` 记录 `overdue_kind`（`checkin`/`report`）与逾期天数；管理端对该对象展示红色「危机·逾期」标记（色码仅管理端）；同一对象同一类型存在未关闭（非 `closed`）逾期复核任务时不重复生成。

> **术语同步（2026-11-25，编辑器、无版本变更）**：中文表述统一为「复核任务」；`review_tickets`、`build_ticket`、`ticket_id` 与 `review_reason` 等标识及规则编号保持不变。

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
└── ticket.py         # 复核任务草案生成
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
    threshold_value: float | str | bool | list[str]
    severity: Color
    session_id: Optional[str] = None
    window: Optional[tuple[str, str]] = None
    triggered_at: str = ""
    offset_score: Optional[float] = None      # 趋势规则证据附加；基线不足时为 0.0
    insufficient: Optional[str] = None        # 基线/窗口不足原因，供证据标注

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
    review_reason: str = "routine_check"      # 生成原因，取值见 §5；不落库，仅影响复核任务 priority/method
```

约束：

- `offset_score` 在 `R_BASELINE_INSUFFICIENT` 命中时置 `0.0`，并在证据里标注 `insufficient`；
- `evidence` 为 `RuleHit.to_evidence()` 的输出列表，字段名与 [db.md](./db.md) `evidence_json` 一致；
- 所有 dataclass 均为 `frozen`，规则函数不得修改入参；
- `offset_score` / `insufficient` 为**可选**证据字段，仅在对应规则场景出现，`to_evidence()` 跳过 `None`；
- `review_reason` 不写入 `review_tickets`（db 无该列），只用于 `build_ticket` 选择 `priority` / `suggested_method`。取值枚举见 §5 `REVIEW_REASON_VALUES`。

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
| `R_DEGRADED_REVIEW` | `R_DEGRADED_REVIEW(degraded, final_color, now) -> RuleHit \| None` | `bool`, `Color` | `severity` 取 `final_color`，仅用于生成任务 | grading.md §6 |

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
    """合成：取大 → 低一致性封顶 → 标记复核。严格按 grading.md §5 四步，顺序不得调换。
    `degraded` 由 `analysis_status == "degraded"` 得到，仅表示分析降级；采集降级不走此参数。

    低一致性封顶（`consistency == "low"`，见 grading.md §5.2）：
    - `red` 豁免，保持 `red`；
    - `orange` / `yellow` / `blue` 保持原色（本就不高于封顶色）；
    - `green` 抬至 `orange`（低一致性下不得结论为「绿」，强制人工复核）。
    命中封顶时 `rules_fired` 必含 `R_CONSISTENCY_CAP`。"""


def build_ticket(final: FinalGrading, review_id: str, subject_id: str, now: str) -> dict:
    """生成复核任务草案，字段与 db.md 的 review_tickets 对齐（不含 `review_reason`，db 无该列）。
    仅当 final_color == "green" 且 needs_review == false 时抛 ValueError；
    「绿 + 降级」(R_DEGRADED_REVIEW) 与 `review_reason == "capture_degraded"` 属于允许生成任务的组合。
    `manual_review == true`（低一致性，规则 5）时 `priority` 覆写为 `P0`，`suggested_method`
    仍按最终色（契约 §6）。
    `now` 必须为带时区 ISO 时间，否则抛 ValueError("now_must_be_timezone_aware")。

    输出不含复核任务主键 `id`：`review_tickets.id` 由调用方（API 层）生成，`review_id` 指向
    `reviews.id`。"""


def map_risk_level(text_valence: float, intent_flag: str = "none") -> str:
    """analysis 侧 `overall.risk_level` 五档映射（历史遗留），阈值见 §5。
    五色规则**不消费**该函数；`intent_flag` 指向明确意图时强制覆写为 `crisis`。"""
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
| `build_ticket` 传入绿结果 | 绿且 `needs_review=false` 且 `review_reason != "capture_degraded"` 时抛 `ValueError("ticket_not_allowed_for_green")` |
| `build_ticket` 的 `now` 无时区 | 抛 `ValueError("now_must_be_timezone_aware")` |
| 阈值配置缺失 | 启动期 `validate_config()` 校验，缺失即 `KeyError`，不做默认兜底 |

### 4.3 `review_reason` 与规则 8 接线

`AnalysisResult` 不含 `capture_status`（schema `additionalProperties: false`），grading 无法自行判定规则 8。`compose` 不新增入参，仅给出默认 `review_reason`：

| 条件 | `compose` 默认 `review_reason` |
|---|---|
| `degraded == true` | `analysis_degraded` |
| 否则 `consistency == "low"` | `consistency_conflict` |
| 其余 | `routine_check` |

- 调用方（backend）在已知 `capture_status in (partial, no_face, no_audio)` 时，须用 `dataclasses.replace(final, review_reason="capture_degraded")` 覆写后再 `build_ticket`；
- `build_ticket` 见 `review_reason == "capture_degraded"` 时，`priority` 覆写为 `P0`、`suggested_method` 覆写为 `recapture`，且不受「绿 + 不复核」拒单守卫拦截；
- 低一致性（`consistency == "low"`）时 `compose` 默认 `review_reason="consistency_conflict"`，但该值**不直接改变** `priority`；规则 5 的 `P0` 由 `FinalGrading.manual_review == true` 驱动（`build_ticket` 覆写 `priority`，`suggested_method` 仍按最终色）；
- **复盘生成前提**：窗口内存在「可用分析会话」——`sessions.status == "captured"` 且 `analysis_status in ("done", "degraded")`。0 条时不落 `reviews`、不生成复核任务，复盘接口返回 `1005 no_session_in_window`（趋势偏移样本仍只统计 `psych.status == "ok"`，两者不是同一口径，见 [../grading.md §4.3](../grading.md)）；
- **主键归属**：`build_ticket` 输出不含 `id`；`review_tickets.id` 由 API 层生成，输出中的 `review_id` 指向 `reviews.id`。

## 5. `config.py` 配置键

```python
THRESHOLD_PROFILE = "default@v1"
RULE_VERSION = "grading@1.2"

THRESHOLDS: dict[str, float | str] = {
    # 单次红
    "SINGLE_RED_INTENT_FLAG": "suicide_intent",              # TODO: 待标定
    "SINGLE_RED_SELFHARM_INTENT_FLAG": "self_harm_mention",  # TODO: 待标定
    "SINGLE_RED_SELFHARM_SIGNAL": 80,                        # TODO: 待标定
    # 单次橙
    "SINGLE_ORANGE_SIGNAL_MIN": 70,                          # TODO: 待标定
    # 趋势偏移
    "TREND_BLUE_OFFSET_MIN": 0.8,                            # TODO: 待标定
    "TREND_YELLOW_OFFSET_MIN": 1.5,                          # TODO: 待标定
    # 基线 / 窗口
    "BASELINE_MIN_SAMPLES": 3,                               # TODO: 待标定
    "BASELINE_MIN_STD": 1.0,                                 # TODO: 待标定
    "TREND_MIN_SESSIONS": 2,                                 # TODO: 待标定
    # 一致性
    "CONSISTENCY_MIN_CONFIDENCE": 0.6,                       # TODO: 待标定
    "CONSISTENCY_CAP_COLOR": "orange",                       # TODO: 待标定
    # map_risk_level 分段（analysis 侧 overall.risk_level，非五色）
    "RISK_VALENCE_NONE_MIN": 0.0,                            # TODO: 待标定
    "RISK_VALENCE_WATCH_MIN": -0.2,                          # TODO: 待标定
    "RISK_VALENCE_ELEVATED_MIN": -0.5,                       # TODO: 待标定
    "RISK_VALENCE_HIGH_MIN": -0.8,                           # TODO: 待标定
}

# 非数值常量
ORANGE_AUX_FACE_EXPRESSIONS = ("sad", "anxious")
ORANGE_AUX_EMOTION_LABEL = "strong_negative"
RISK_INTENT_CRISIS_FLAGS = ("suicide_intent", "self_harm_mention")
REVIEW_REASON_VALUES = ("routine_check", "capture_degraded", "consistency_conflict", "analysis_degraded")
COLOR_RANK = {"none": 0, "green": 1, "blue": 2, "yellow": 3, "orange": 4, "red": 5}

DEADLINE_HOURS: dict[str, int] = {"P0": 24, "P1": 72, "P2": 168}

SUGGESTED_METHOD: dict[str, str] = {
    "red": "urgent_escalation",
    "orange": "priority_interview",
    "yellow": "focused_interview",
    "blue": "routine_checkin",
}
```

`map_risk_level(text_valence, intent_flag="none")` 分段（全部未标定）：

| 条件 | `risk_level` |
|---|---|
| `intent_flag in ("suicide_intent", "self_harm_mention")` | `crisis`（强制覆写，最高优先） |
| `text_valence >= 0.0` | `none` |
| `-0.2 <= text_valence < 0.0` | `watch` |
| `-0.5 <= text_valence < -0.2` | `elevated` |
| `-0.8 <= text_valence < -0.5` | `high` |
| `text_valence < -0.8` | `crisis` |

> 该函数仅供 analysis 侧填充 `overall.risk_level`；五色分级不消费 `risk_level`。

规则：

- 阈值只允许在 `config.py` 出现一次，规则函数内不得写数字字面量；
- 每个新阈值必须带 `# TODO: 待标定` 或注明具体来源，禁止编造出处；
- 变更阈值不改函数签名，仅改配置。

## 6. 复核任务草案结构

`build_ticket` 返回（字段与 [db.md](./db.md) `review_tickets` 一一对应）：

```json
{
  "review_id": "c41d0a77-9b2e-4f83-a1c5-6d7e8f9a0b1c",
  "subject_id": "3b1e7c90-2f4a-4d51-8c6b-7d9e0f1a2b3c",
  "status": "pending",
  "priority": "P2",
  "due_at": "2026-11-30T15:20:00.000+08:00",
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

`priority` / `suggested_method` 取值规则见 [../grading.md](../grading.md#6-复核触发条件)。注意输出**不含** `review_reason`（db 无该列），它只在 `FinalGrading` 内部影响下表选择：

| 最终色 / 条件 | priority | suggested_method |
|---|---|---|
| `review_reason == "capture_degraded"`（规则 8，覆写） | `P0` | `recapture` |
| `red` / `orange` / 低一致性（`manual_review=true`） | `P0` | 按最终色 |
| `yellow` / 分析降级补采（绿 + `degraded`） | `P1` | 按最终色 / `recapture` |
| `blue` | `P2` | `routine_checkin` |

覆写顺序固定，不可调换：

```
capture_degraded → P0/recapture
绿 + needs_review → P1/recapture
manual_review=true（低一致性）→ P0，方法按最终色
其余 → 按最终色映射
```

`due_at = now + DEADLINE_HOURS[priority]`，保持时区、输出毫秒精度 ISO；相同输入必须输出一致（幂等，不含随机值）。

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
| 封顶 | `R_CONSISTENCY_CAP` | 红+low 仍红；橙+low 仍橙；黄+low 仍黄；蓝+low 仍蓝；绿+low 变橙 |
| 取大 | `compose` | 六组组合对照 grading.md §5.1 |
| 复核标记 | `compose` | `low` 必 `manual_review=True`；`degraded` 必 `needs_review=True` |
| 采集降级 | 规则 8 | `capture_status in (partial,no_face,no_audio)` → `consistency=low`、`review_reason=capture_degraded`、必生成 `P0` 任务；封顶对 `red` 豁免（`red` 保持） |
| 复核任务覆写 | `build_ticket` | `review_reason=capture_degraded` → `P0`+`recapture`；即便最终绿也不抛 `ticket_not_allowed_for_green` |
| 低一致性 P0 | 规则 5 | `manual_review=true` 时蓝/黄也出 `P0`，`suggested_method` 保持 `routine_checkin` / `focused_interview` |
| 复盘前提 | 调用方 | 窗口内 0 条可用分析会话（`captured` + `analysis_status∈{done,degraded}`）不落 `reviews`，接口返回 `1005 no_session_in_window` |
| risk_level 映射 | `map_risk_level` | 五档断点；`text_valence` 正常但 `intent_flag=suicide_intent` → `crisis` |
| 绿 + 降级 | `R_DEGRADED_REVIEW` | 最终绿且 `degraded=True` 时仍生成任务，`priority=P1` |
| 生成任务 | `build_ticket` | 绿且 `needs_review=False` 抛异常；「绿 + 降级」不抛；非绿字段齐全；`due_at` 按 P 级计算 |
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
4. 绿结果且 `needs_review=false` 时生成复核任务（「绿 + 降级」除外）；
5. 证据缺 `field_path` 或 `threshold_key`；
6. 输出诊断性字段（如 `depression_score`）；
7. 规则函数使用随机数或当前时间作为逻辑输入（时间只能进 `triggered_at`）；
8. 把 `review_reason` 写入 `review_tickets` 或任何用户端响应（它只在进程内影响复核任务 `priority` / `suggested_method`）。
