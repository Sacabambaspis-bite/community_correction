# 五色分级规则（业务规则唯一权威）

| 项 | 值 |
|---|---|
| 文档版本 | `grading@1.1` |
| 状态 | 待评审 |
| 适用 | 所有实现与前端展示以本文为准 |
| 工程契约 | [contracts/grading.md](./contracts/grading.md)（函数签名、配置键、工单结构） |
| 关联 | [prd.md](./prd.md)、[architecture.md](./architecture.md)、[contracts/db.md](./contracts/db.md) |

> 本版已冻结，后续仅接受实现驱动的变更。

> 本文只定义**业务规则**。阈值的技术取值、配置键名与函数落点在 [contracts/grading.md](./contracts/grading.md)，两处不得重复定义同一阈值。

---

## 1. 定位与三条原则

1. **分级是提示，不是结论。** 输出的是"建议人工关注的程度"，不是诊断，不是管控等级。
2. **唯一出口是复核工单。** 任何非绿结果只生成工单，系统不得据此产生限制、通报、扣分等动作。
3. **无证据不成立。** 每条颜色必须能回答：哪条规则、哪个字段、哪次会话、什么阈值。

## 2. 五色定义

| 色码 | 名称 | 等级 | 含义 | 来源规则 | 默认动作 |
|---|---|---|---|---|---|
| `red` | 红 | 5 | 出现明确的自伤 / 自杀意图信号 | 单次规则 | 当日人工介入（系统只建单） |
| `orange` | 橙 | 4 | 强烈消极信号但无明确意图；或一致性冲突封顶 | 单次规则 / 合成封顶 | 优先面谈 |
| `yellow` | 黄 | 3 | 7 日窗口内相对个人基线出现显著恶化偏移 | 趋势规则 | 安排针对性面谈 |
| `blue` | 蓝 | 2 | 轻度偏移或基线样本不足，需持续观察 | 趋势规则 | 日常问询 |
| `green` | 绿 | 1 | 无明显偏移 | 趋势规则 | 不做额外动作，不建单 |

**等级顺序（用于合成取大）**：`green < blue < yellow < orange < red`。

命名约束：

- 色码字段统一小写英文（`green`…`red`），中文名仅用于展示；
- 前端颜色令牌以本文为准，不得自行新增色值；
- 用户端不出现任何色码（见 [contracts/ui.md](./contracts/ui.md)）。

## 3. 单次风险规则（`single_session_risk`）

输入：单次会话的 `AnalysisResult`（见 [contracts/analysis.schema.json](./contracts/analysis.schema.json)）。
输出：`red` / `orange` / `none`。**单次规则不产出绿、蓝、黄。**

### R_SINGLE_RED → `red`

满足任一：

- `channels.psych.output.intent_flag == "suicide_intent"`
- `channels.psych.output.intent_flag == "self_harm_mention"` 且 `channels.psych.output.signal_strength >= SINGLE_RED_SELFHARM_SIGNAL`（默认 80）

理由：明确意图优先于任何置信度与一致性判断，不再做封顶。

### R_SINGLE_ORANGE → `orange`

同时满足：

- `channels.psych.status in ("ok", "degraded")`
- `channels.psych.output.signal_strength >= SINGLE_ORANGE_SIGNAL_MIN`（默认 70）
- `intent_flag` 不为 `suicide_intent`

辅助佐证（不单独触发，仅写入证据）：

- `channels.emotion.output.label == "strong_negative"` → 证据附加
- `channels.face.output.expression_label in ("sad", "anxious")` → 证据附加

### 未命中

返回 `none`，不产生颜色。

### 单次规则与一致性

`consistency == "low"` **不改变** `single_session_risk` 的取值。一致性只在第 5 节合成阶段起作用。

## 4. 周期趋势规则（`period_trend`）

输入：7 日窗口内的会话集合 + 个人基线。
输出：`green` / `blue` / `yellow`。**趋势规则不产出橙、红。**

### 4.1 偏移分计算

```
window_signal_mean = mean(每次会话的 psych.output.signal_strength)   # 只统计 psych.status=ok
offset_score = (window_signal_mean - baseline.psych_signal_mean)
               / max(baseline.psych_signal_std, BASELINE_MIN_STD)
```

约束：

- 只计算**恶化方向**，`offset_score <= 0` 视为无恶化；
- 窗口内可用会话数 `< TREND_MIN_SESSIONS`（默认 2）→ 走 `R_BASELINE_INSUFFICIENT`；
- 基线 `sample_count < BASELINE_MIN_SAMPLES`（默认 3）→ 走 `R_BASELINE_INSUFFICIENT`；
- 窗口按自然日计算，可跨月、跨年，不做月度对齐。

### 4.2 阈值映射

| 条件 | 规则 | `trend_color` |
|---|---|---|
| `offset_score >= TREND_YELLOW_OFFSET_MIN`（默认 1.5） | `R_TREND_YELLOW` | `yellow` |
| `TREND_BLUE_OFFSET_MIN <= offset_score < TREND_YELLOW_OFFSET_MIN`（默认 0.8 ~ 1.5） | `R_TREND_BLUE` | `blue` |
| `offset_score < TREND_BLUE_OFFSET_MIN` | `R_TREND_GREEN` | `green` |
| 基线样本不足或窗口会话不足 | `R_BASELINE_INSUFFICIENT` | `blue`（附说明，不升级） |

`R_BASELINE_INSUFFICIENT` 判蓝而非绿，是因为"无法判断"不等于"正常"；但也不升级为黄，避免误报。

### 4.3 窗口无数据

窗口内没有任何 `psych.status=ok` 的会话：

- 不生成 `reviews` 记录；
- `POST /api/reviews` 返回 `code=1005`、`message=no_session_in_window`；
- 不建工单。

## 5. 合成规则

```
step1  final_color = max(single_session_risk, period_trend)      # 按 green<blue<yellow<orange<red
step2  if consistency == "low":  final_color = min(final_color, orange)
step3  if consistency == "low":  manual_review = true
step4  if degraded == true:      needs_review = true，并计入 R_DEGRADED_REVIEW
```

`step4` 不改变 `final_color`，只决定是否建单。因此存在"绿 + 降级"的组合，见第 6 节条件 6。

`max` 的 `none` 处理：`single_session_risk = none` 时按等级 0 参与比较，即直接取趋势色。

### 5.1 合成示例

| 单次 | 趋势 | 一致性 | 最终 | 强制复核 | 说明 |
|---|---|---|---|---|---|
| `none` | `green` | `high` | `green` | 否 | 不建单 |
| `none` | `blue` | `high` | `blue` | 否 | P2 工单 |
| `none` | `yellow` | `medium` | `yellow` | 否 | P1 工单 |
| `red` | `green` | `low` | `red` | 是 | 红不受封顶约束 |
| `orange` | `yellow` | `low` | `orange` | 是 | 封顶到橙，强制复核 |
| `orange` | `green` | `high` | `orange` | 否 | P0 工单 |

### 5.2 封顶规则（R_CONSISTENCY_CAP）

- `consistency == "low"` 时 `final_color` 最高为 `orange`；
- 该封顶**不作用于 `red`**：红来自明确意图，不允许被一致性下调；
- 封顶发生时，`rules_fired` 必须包含 `R_CONSISTENCY_CAP`。

## 6. 复核触发条件

| # | 条件 | 是否建单 | 优先级 | 建议处理时限 |
|---|---|---|---|---|
| 1 | `final_color == "red"` | 是 | `P0` | 24 小时内 |
| 2 | `final_color == "orange"` | 是 | `P0` | 24 小时内 |
| 3 | `final_color == "yellow"` | 是 | `P1` | 72 小时内 |
| 4 | `final_color == "blue"` | 是 | `P2` | 7 天内 |
| 5 | `consistency == "low"`（无论最终色） | 是，且强制 `manual_review=1` | `P0` | 24 小时内 |
| 6 | `degraded == true` 且最终色为绿（`R_DEGRADED_REVIEW`） | 是（补采 / 复核单） | `P1` | 72 小时内 |
| 7 | `final_color == "green"` 且无上述情况 | **否** | — | — |
| 8 | `capture_status in (partial, no_face, no_audio)`（技术性降级或单模态） | 是，且强制 `manual_review=1` | `P0`（同规则 5） | 24 小时内 |
| 8a | `capture_status in (no_face_no_audio, error)`（无任何可用产物） | **否** | — | 由前端提示重采，不进分析队列 |
| 9 | 窗口无可用会话 | **否** | — | 返回 `no_session_in_window` |
| 10 | `R_BASELINE_INSUFFICIENT` 单独命中 | 随蓝一起建单 | `P2` | 7 天内 |

> 命中规则 8 的会话：`consistency` 强制 `low`，`final_color` 上限 `orange`（计算结果为 `red` 时封顶为 `orange`），`rules_fired` 记 `R_CONSISTENCY_CAP`，且**必须生成复核工单**。与规则 6 同时命中时，按规则 8 的 `P0` 建单。

### 6.1 建议复核方式映射

| 最终色 | `suggested_method` |
|---|---|
| `red` | `urgent_escalation` |
| `orange` | `priority_interview` |
| `yellow` | `focused_interview` |
| `blue` | `routine_checkin` |
| 条件 6（降级补采） | `recapture` |
| 条件 8（技术性降级 / 单模态） | `recapture` |

### 6.2 幂等约束

- 一次 `reviews` 记录最多对应一张 `review_tickets`（`UNIQUE(review_id)`）；
- 同一会话重复触发分析，不重复建单；
- 已关闭的工单不再接受新流转。

## 7. 证据链要求

每条非绿结果**必须**包含完整证据链，缺失即视为 bug。

### 7.1 最小字段集

| 字段 | 说明 |
|---|---|
| `rule_id` | 规则编号，如 `R_TREND_BLUE` |
| `rule_version` | 规则版本，如 `grading@1.1` |
| `field_path` | 触发字段路径，如 `channels.psych.output.signal_strength` |
| `observed_value` | 实际观测值 |
| `threshold_key` | 阈值配置键名 |
| `threshold_value` | 阈值实际取值 |
| `session_id`（单次规则必填） | 触发会话 |
| `window`（趋势规则必填） | `[start_date, end_date]` |
| `triggered_at` | 触发时间 |

### 7.2 多规则命中

- 同时命中多条规则时，`rules_fired` 为数组，按等级从高到低排列；
- 证据数组与 `rules_fired` 一一对应，不允许只有规则没有证据。

### 7.3 禁止项

- 禁止只给颜色不给证据；
- 禁止用"综合判断""模型认为"替代 `field_path`；
- 禁止把原始转写文本写入证据，只允许 `keywords` 与字段值。

## 8. 表述与文案边界

| 禁止表述 | 替代表述 |
|---|---|
| 抑郁、焦虑症、人格障碍、精神异常 | 信号强度偏高、偏移程度明显 |
| 有自杀倾向（作为结论） | 出现指向性表达，建议人工确认 |
| 正常 / 不正常 | 无明显偏移 / 建议关注 |
| 高风险人员、重点人 | 本次结果建议优先复核 |
| 系统判定、模型认定 | 规则命中、依据如下 |

补充约束：

- 用户端完全不出色码，只输出行为建议；
- 管理端文案必须与证据同行，禁止只渲染颜色块；
- 对外材料不得出现"AI 诊断""智能判级"这类表述。

## 9. 未标定阈值清单

> 以下阈值**均无实证依据**，实现时必须在 `app/grading/config.py` 注明 `# TODO: 待标定`，不得声称来自文献或临床标准。

| 配置键 | 默认值 | 含义 | 建议标定方法 |
|---|---|---|---|
| `SINGLE_RED_SELFHARM_SIGNAL` | 80 | 自伤提及判红的信号强度门槛 | 与专业人员共同标注 200+ 真实会话后确定 |
| `SINGLE_ORANGE_SIGNAL_MIN` | 70 | 单次判橙门槛 | 同上，重点看假阳性率 |
| `TREND_BLUE_OFFSET_MIN` | 0.8 | 蓝的偏移下限 | 用个人历史数据做回测，控制蓝的比例 |
| `TREND_YELLOW_OFFSET_MIN` | 1.5 | 黄的偏移下限 | 同上，需保证黄的数量工作人员可处理 |
| `BASELINE_MIN_SAMPLES` | 3 | 基线最少样本数 | 统计基线标准差收敛所需样本量 |
| `BASELINE_MIN_STD` | 1.0 | 标准差下限，防除零 | 观察低方差个体的分布 |
| `TREND_MIN_SESSIONS` | 2 | 窗口最少会话数 | 结合采集频次设定 |
| `CONSISTENCY_MIN_CONFIDENCE` | 0.6 | 单路置信度下限 | 对比各模型置信度分布 |
| `CONSISTENCY_CAP_COLOR` | `orange` | 低一致性封顶色 | 需与合规、业务共同确认 |

## 10. 版本与变更

| 版本 | 日期 | 变更 |
|---|---|---|
| `grading@1.0` | 2026-11-23 | 初版：五色定义、单次与趋势规则、合成封顶、复核触发 |
| `grading@1.1` | 2026-11-23 | 规则 8 收敛：partial 与单模态强制 `consistency=low`、颜色上限 `orange`、必须建单；无产物会话不建单 |

变更要求：

1. 规则编号一经发布不得复用或改义，废弃用 `R_XXX_DEPRECATED` 保留；
2. 阈值调整只改 `config.py` 与第 9 节，不改规则编号；
3. 任何规则变更必须同步补 pytest 边界用例；
4. 涉及封顶逻辑的变更需 `privacy-check` 与业务方共同确认。
