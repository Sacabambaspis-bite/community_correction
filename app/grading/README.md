# app/grading/

五色分级纯函数库（绿 / 蓝 / 黄 / 橙 / 红），产出色码与复核任务草案；分级唯一出口是人工复核任务，本目录不做任何处置。

## 入口（`__init__.py` 导出）
- `single.py` → `evaluate_session`：单次风险（红 / 橙），消费 `channels.psych.output`
- `trend.py` → `evaluate_period`：七日趋势与基线偏移（绿 / 蓝 / 黄）
- `compose.py` → `compose`：取大 → 低一致封顶 → 降级标记，四步顺序不可调换
- `ticket.py` → `build_ticket`：只生成复核任务草案（dict），不写库
- `config.py`：阈值与常量唯一来源（`RULE_VERSION=grading@1.2`、`THRESHOLDS`、`DEADLINE_HOURS`）

## 低一致性强制 P0
- `consistency=low` 命中 `R_CONSISTENCY_CAP`：除红色外封顶为橙，prior 为绿时抬至橙（不得结论为绿）
- `compose` 置 `manual_review=True`；`build_ticket` 据此把 `priority` 覆写为 P0（24h），复核方式仍按最终色
- `review_reason="capture_degraded"`（规则 8）同样强制 P0 + `recapture`

## 红线
- 纯函数：不读写 DB、不发通知、不调外部服务；时间必须由调用方传入带时区 `now`
- 规则函数禁止手写阈值字面量，只能读 `config.THRESHOLDS`（有源码扫描测试兜底）
- `AnalysisResult` 不含 `capture_status`，调用方需 `replace(final, review_reason="capture_degraded")` 后再建单
- 相同输入必须得到相同输出（幂等，不含随机值）
