# 社区矫正智能辅助系统 · 架构设计（单对象纵切原型）

| 项 | 值 |
|---|---|
| 文档版本 | v0.1 |
| 状态 | 待评审 |
| 关联文档 | [prd.md](./prd.md)、[contracts/](./contracts/)、[grading.md](./grading.md) |

---

## 1. 技术栈

| 层 | 选型 | 说明 |
|---|---|---|
| 运行时 | Python 3.11 | 与子智能体定义一致 |
| Web 框架 | FastAPI | 自动生成 OpenAPI，便于契约校验 |
| ORM | SQLAlchemy 2.x | 声明式模型 + Alembic 迁移 |
| 数据库 | SQLite | 原型单机，文件库 |
| 采集 | OpenCV / MediaPipe / sounddevice | 在后端宿主设备执行 |
| 前端 | React + Vite | 用户端与管理端同仓同构建，按路由分区 |
| 模型 | Provider 抽象 + mock | 本轮不接真模型 |

### 1.1 采集位置的约定（重要）

采集模块运行在**后端宿主设备**（矫正中心的终端机 / 一体机），而不是浏览器内 `getUserMedia`。原因：

- 子智能体契约已把采集定义为 OpenCV + sounddevice，属于 Python 进程能力；
- 终端机摄像头与麦克风位置固定，采集条件可控；
- 避免浏览器权限、编码格式、跨设备差异带来的额外变量。

前端负责：授权说明、开始/结束触发、采集状态展示、失败提示。前端**不接触**音视频数据。

## 2. 模块分层

```
┌───────────────────────────────────────────────────────────────┐
│  web/  React + Vite                                           │
│  ├── src/user/    知情同意 · 采集引导 · 结果反馈               │
│  └── src/admin/   对象列表 · 记录检索 · 状态看板 · 复核队列     │
└───────────────────────────┬───────────────────────────────────┘
                            │ HTTP / JSON（统一响应包）
┌───────────────────────────▼───────────────────────────────────┐
│  app/api/   FastAPI 路由 · 鉴权 · 序列化 · 统一错误码           │
├───────────────────────────────────────────────────────────────┤
│  app/db/    SQLAlchemy 模型 · 迁移 · 会话管理                   │
├───────────────────────────────────────────────────────────────┤
│  app/capture/    抓拍 · 人脸检测裁剪 · 录音 · 会话打包           │
│  app/analysis/   四路 Provider · 汇总 · 一致性判定              │
│  app/grading/    规则表 · 合成 · 复核任务草案生成                   │
└───────────────────────────┬───────────────────────────────────┘
                            │
┌───────────────────────────▼───────────────────────────────────┐
│  storage/{subject_id}/{session_id}/                           │
│      face.jpg   audio.wav   meta.json   transcript.txt        │
└───────────────────────────────────────────────────────────────┘
```

### 2.1 依赖方向

```
api  →  capture / analysis / grading  →  db
api  →  db
grading 不反向依赖 analysis（只消费已校验的 AnalysisResult）
```

- `analysis` 只吐结构化的 `AnalysisResult`，不写库、不生成任务；
- `grading` 是纯函数集合，输入 `AnalysisResult` 与历史窗口数据，输出分级与复核任务草案；
- `api` 是唯一编排者，负责落库、生成任务、留痕、序列化脱敏；
- `capture` 不感知任何模型与规则。

## 3. 端到端时序（一次完整会话）

```
前端           api             capture          analysis         grading           db
 │              │                 │                │                │              │
 │ POST /session│                 │                │                │              │
 ├─────────────>│ 建 session(created) ───────────────────────────────────────────>│
 │              │ run_capture ───>│                │                │              │
 │              │                 │ 抓拍/裁剪/录音  │                │              │
 │              │<── CaptureResult│                │                │              │
 │              │ 更新 session(captured|failed) ───────────────────────────────────>│
 │<── 202/200 ──┤                 │                │                │              │
 │              │                 │                │                │              │
 │ POST /analyze│                 │                │                │              │
 ├─────────────>│ 读取 session 元数据 ────────────────────────────────────────────>│
 │              │ analyze_all ───────────────────>│                │              │
 │              │                 │                │ 4×Provider     │              │
 │              │<── AnalysisResult────────────────│                │              │
 │              │ schema 校验     │                │                │              │
 │              │ grading.evaluate ────────────────────────────────>│              │
 │              │<── 五色 + 证据链 ──────────────────────────────────│              │
 │              │ 写 reviews / review_tickets / 更新 session ──────────────────────>│
 │<── 结果(脱敏)┤                 │                │                │              │
 │              │                 │                │                │              │
 │              │ GET /tickets    │                │                │              │
 │<─────────────┤                 │                │                │              │
 │ POST /tickets/{id}/transition → 写 audit_logs ───────────────────────────────>│
```

### 3.1 关键时序约束

1. `POST /api/session` 同步执行采集，最长阻塞 `CAPTURE_TIMEOUT_SEC`（默认 60s）。原型不做异步任务队列。
2. `POST /api/session/{id}/analyze` 只在 `session.status == captured` 时可用，否则返回 `1005 状态冲突`。
3. 分析结果必须通过 `analysis.schema.json` 校验后才允许进入 `grading`；校验失败按 `5000` 处理并记日志（不含原文）。
4. 分级结果与复核任务在**同一个事务**内写入，避免出现"有颜色无复核任务"的中间态。

## 4. Provider 抽象

### 4.1 接口

```python
class BaseProvider(Protocol):
    name: str            # asr | emotion | face | psych
    version: str         # 例如 "mock-asr@1.0"

    def available(self) -> bool: ...

    def analyze(self, input: ProviderInput) -> ProviderOutput: ...
```

```python
@dataclass
class ProviderInput:
    session_id: str
    subject_id: str
    face_path: str | None      # storage 相对路径
    audio_path: str | None
    transcript_path: str | None

@dataclass
class ProviderOutput:
    status: Literal["ok", "degraded", "skipped"]
    output: dict               # 结构由 analysis.schema.json 约束
    confidence: float          # 0..1
    latency_ms: int
    reason: str | None = None
```

### 4.2 四路 Provider

| name | 目标真模型 | mock 行为 |
|---|---|---|
| `asr` | SenseVoice | 返回固定转写片段，写入 `transcript.txt` |
| `emotion` | 语音情感模型 | 返回固定 `valence`/`arousal`/`label` |
| `face` | 表情识别模型 | 返回固定 `expression_label`/`intensity` |
| `psych` | PsyCoLLM | 消费 ASR 转写文本，返回固定 `signal_strength`/`intent_flag` |

mock 输出必须**可通过场景参数切换**（如 `MOCK_SCENARIO=normal|negative|crisis|conflict`），否则无法覆盖分级分支与边界测试。

### 4.3 降级与容错

| 情况 | 行为 |
|---|---|
| 单路 `available()` 为 False | 该路 `status=skipped`，整体 `degraded=true` |
| 单路抛异常 | 该路 `status=degraded` + `reason`，整体 `degraded=true`，继续汇总 |
| 四路全部失败 | 返回 `5000`，不生成分级、不生成任务 |
| 超过单路超时（默认 10s） | 按 `degraded` 处理并终止该路 |

`degraded=true` 时仍走分级，但 `consistency` 最多为 `medium`，且强制 `needs_review=true`。

## 5. 一致性判定

| 三路情感结论 | consistency | 后续动作 |
|---|---|---|
| 文本/语音/表情三者方向一致 | `high` | 正常分级 |
| 任意两者一致 | `medium` | 正常分级 |
| 存在方向冲突 | `low` | 强制人工复核 |
| 任一路置信度 < `CONSISTENCY_MIN_CONFIDENCE` | `low` | 强制人工复核 |

**一致性只下调置信度并转人工，绝不修改 `risk_level`。**

## 6. 数据与存储

### 6.1 落盘结构

```
storage/
└── {subject_id}/
    └── {session_id}/
        ├── face.jpg          # 裁剪后正方形人脸，长边 ≤640，质量 85
        ├── audio.wav         # 16kHz / mono / 16bit
        ├── transcript.txt    # 转写文本（敏感，接口默认不下发）
        └── meta.json         # 采集元数据
```

数据库中只保存**相对路径**，不存二进制，不存绝对路径。

### 6.2 数据库五张表

`subjects` / `sessions` / `reviews` / `review_tickets` / `audit_logs`，字段定义见 [contracts/db.md](./contracts/db.md)。

> 注：`trae/agents/README.md` 中写的是 4 张表，本设计经评审确认为 5 张，增补 `audit_logs`，理由是敏感字段查看与复核任务流转必须可追溯。

### 6.3 分析结果存放

分析结果是 JSON，直接存 `sessions.analysis_json`，不单独建表。理由：原型只需按会话读取，无跨会话字段级查询需求。

## 7. 鉴权与权限

| 端 | Header | 角色 | 可访问 |
|---|---|---|---|
| 用户端 | `Authorization: Bearer <user_token>` | `subject` | 本人同意、采集、本人反馈 |
| 管理端 | `Authorization: Bearer <admin_token>` | `staff` | 对象、会话、复盘、复核任务、看板 |
| 采集触发 | 同上 | `subject` \| `staff` | 仅本机终端 |

- 用户端接口的序列化层**必须显式剔除** `final_color`、`risk_level`、`evidence`；
- 管理端接口一律校验 `role == staff`，否则 `1003 无权限`；
- 原型 token 为固定前缀的静态令牌（`user_*` / `admin_*`），文档中标注为待替换项。

## 8. 日志与留痕

### 8.1 日志规范

允许：`session_id`、`subject_id`、状态、耗时、`rule_id`、错误类型。
禁止：音频内容、面部图路径以外的个人信息、转写原文、心理评分明细、异常堆栈中的文件内容。

### 8.2 留痕

写入 `audit_logs` 的动作：

| action | 触发点 |
|---|---|
| `consent.grant` / `consent.revoke` | 同意、撤回 |
| `sensitive.view` | 查看面部图、转写原文 |
| `ticket.transition` | 复核任务确认 / 修正 / 关闭 |
| `session.analyze` | 触发分析 |
| `review.export_evidence` | 导出证据（如后续需要） |

## 9. 目录所有权（与子智能体对齐）

| 目录 | 所有者 | 禁止改动 |
|---|---|---|
| `app/capture/`、`tests/test_capture/` | capture-engineer | 其余全部 |
| `app/analysis/`、`tests/test_analysis/` | analysis-engineer | 其余全部 |
| `app/grading/`、`tests/test_grading/` | grading-engineer | 其余全部 |
| `app/api/`、`app/db/`、`tests/test_api/` | backend-engineer | 其余全部 |
| `web/src/user/` | fe-user | `web/src/admin/`、`app/` |
| `web/src/admin/` | fe-admin | `web/src/user/`、`app/` |
| `tests/`、`docs/reports/` | qa-guard | `app/`、`web/src/` |
| `docs/contracts/` | **仅主智能体** | 子智能体只读 |

## 10. 运行方式（原型）

```bash
# 后端
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# 前端
cd web
npm install
npm run dev
```

默认环境变量：

| 变量 | 默认值 | 用途 |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./data/app.db` | 数据库 |
| `STORAGE_ROOT` | `./storage` | 文件落地根目录 |
| `MOCK_SCENARIO` | `normal` | mock Provider 场景 |
| `CAPTURE_DEVICE_INDEX` | `0` | 摄像头索引 |
| `CAPTURE_DURATION_SEC` | `30` | 录音时长 |
| `CAPTURE_TIMEOUT_SEC` | `60` | 采集整体超时 |
| `PROVIDER_TIMEOUT_SEC` | `10` | 单路分析超时 |
| `GRADING_WINDOW_DAYS` | `7` | 趋势窗口 |

## 11. 非功能要求

| 类别 | 要求 |
|---|---|
| 可解释性 | 每个非绿结果携带 `rule_id` + `field_path` + `observed_value` + `threshold` + `session_id` |
| 幂等性 | 同一 `session_id` 重复调用 `/analyze` 返回已有结果，不重复生成任务 |
| 可测试性 | 采集与分析必须支持假数据注入，测试不依赖真实设备与真模型 |
| 响应时间 | 分析（mock）单会话 < 1s；管理端列表接口 < 300ms（1000 条内） |
| 数据清理 | `RETENTION_DAYS` 默认 180，超期由清理任务删除文件与记录（原型可手动触发） |
| 可移植性 | 无 GPU 依赖；SQLite 单文件可随目录迁移 |

## 12. 与现有子智能体配置的差异说明

| 差异点 | 处理 |
|---|---|
| README 写 4 张表，backend-engineer 写 5 张 | 采用 5 张（含 `audit_logs`），已在 [contracts/db.md](./contracts/db.md) 明确 |
| 用户端可能含对话页 | 本轮不含，`psych` 消费 ASR 转写文本 |
| `grading.md` 出现两份 | `docs/grading.md` 为业务规则唯一权威；`docs/contracts/grading.md` 为工程契约，不重复定义阈值 |
