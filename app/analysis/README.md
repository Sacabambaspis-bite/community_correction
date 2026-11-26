# app/analysis/

一次采集 → 四路结构化结果的只读分析管线，输出 `AnalysisResult`（schema 1.0），不写数据库。

## 核心文件
- `pipeline.py`：四路编排、异常隔离、一致性判定、degraded 包装与最终 Schema 校验
- `providers/`：`base.py` 统一接口；`mock_*.py` 确定性 Mock；`sensevoice_asr.py` / `sensevoice_emotion.py` 真实通道；`__init__.py` 注册表
- `schema.py`：加载 `docs/contracts/analysis.schema.json`，做通道级 + 整体强校验
- `config.py`：`CONFIDENCE_THRESHOLD=0.6`、`MOCK_SCENARIO`；`sensevoice_sync.py` 是 P13 严格同步（失败即报错，不回退 Mock）

## 四路 Provider
- `asr`：语音转写，落盘 `transcript.txt`；`emotion`：复用 ASR 情感标签，不重复请求云端
- `face`：面部表情帧统计；`psych`：基于转写的文本极性与意图标记

## Mock / 真实切换
- `SENSEVOICE_API_URL` + `SENSEVOICE_API_KEY` 齐备 → `asr`/`emotion` 走真实 SenseVoice；否则四路全 Mock
- `face`/`psych` 目前始终 Mock；`MOCK_SCENARIO` 选择确定性场景（默认 `normal`）

## 降级策略
- `available()=False` → `skipped(provider_unavailable)`；执行异常或返回结构不符 → `degraded(provider_execution_failed)`
- 缺音频 → asr / emotion / psych skipped；缺面部 → face skipped；全部无可用输出 → 整体 `failed`
- 任一 degraded / skipped 或低一致性 → `needs_review=true`（checkin 的预期音频缺口不算降级）

## 千万不要
- 更改任何通道返回结构必须同步修改 `docs/contracts/analysis.schema.json`，否则运行期直接 failed
- 不要在本目录写 DB、发通知或做处置；Provider 返回值必须恰好是 `status/output/confidence/latency_ms/reason` 五键
