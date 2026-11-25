# 社区矫正情绪与状态辅助评估系统（原型）

> 单对象纵向切片原型：把一次采集（人脸 + 语音）转成结构化信号，经四路分析与五色分级，**分级结果唯一出口是人工复核工单**。系统自身不产生任何处置动作。

- 当前状态：原型（非生产可用），核心链路已打通，分析侧除 ASR 外仍为确定性 Mock。
- 最近验证：`pytest tests -q` → 286 passed；`web` 的 `typecheck` 与 `build` 通过。
- 进度与风险：[docs/PROGRESS.md](./docs/PROGRESS.md)
- 产品与架构：[docs/prd.md](./docs/prd.md)、[docs/architecture.md](./docs/architecture.md)

---

## 1. 项目简介

社区矫正场景下，工作人员需要持续了解矫正对象的情绪与状态变化，但敏感数据的采集、分析与使用必须可控、可解释、可复核。本项目为此提供一个可运行的纵向切片：

1. **采集**：刷脸签到（仅人脸）或思想汇报（人脸 + 语音），采集运行在**后端宿主设备**而非浏览器。
2. **分析**：ASR / 情绪 / 表情 / 心理四路 Provider，产出经 JSON Schema 强校验的结构化结果。
3. **分级**：五色规则（红 / 橙 / 黄 / 蓝 / 绿）+ 七日趋势偏移 + 一致性封顶，纯函数实现。
4. **出口**：非绿结果只生成**人工复核工单**，由工作人员线下处置。

### 三条不可突破的红线

| 红线 | 含义 |
|---|---|
| 原图不落盘 | 只保留裁剪后的 `face.jpg`（300×300），原始帧不落盘、不写日志 |
| 分级只出口工单 | 系统不得产生限制、通报、扣分等任何处置动作 |
| 色码只在管理端 | 用户端响应与页面不出现色阶字段，只给行为建议 |

---

## 2. 功能特性

| 模块 | 能力 | 状态 |
|---|---|---|
| 采集 | 摄像头抓拍、人脸检测与裁剪、麦克风录音、会话打包（`meta.json`） | 已实现，真机验证 |
| 采集模式 | `both`（人脸+语音）、`face_only`（签到）、手动录音（用户点击结束才停止） | 已实现 |
| 数据层 | 5 张表、派生 `coverage`、服务端默认值、手工迁移 | 已实现 |
| 分析 | 四路 Provider + Schema 校验 + 一致性判定 + 降级隔离 | 已实现（ASR 可接真实 SenseVoice） |
| 分级 | 单次规则、七日趋势、合成封顶、工单草案 | 已实现 |
| API | 统一响应信封、双 token 鉴权、采集/分析/复盘/工单/看板 | 已实现 |
| 业务形态 | 刷脸签到、录音思想汇报、按对象配置频率、逾期 → P0 复核工单 | 已实现 |
| 用户端 | 登录（含统一知情同意）、模块选择、签到、思想汇报、结果反馈 | 已实现（Mock 联调） |
| 用户端扩展入口 | 「AI援助」「教育学习」两个入口卡片 + 统一「功能待开发」占位页 | **仅前端占位，暂无后端支持** |
| 管理端 | 对象列表/详情、频率配置、复核工单队列 | 已实现（Mock 联调） |
| 管理端对象详情 | 基础档案（性别/年龄/身份证号等）、按日期查看打卡影像与思想汇报录音（在线预览/播放）、状态概览与七日趋势 | 已实现（Mock 媒体） |
| 状态看板 | 已整体合并进对象详情页，不再保留独立入口；`/admin/dashboard` 仅做重定向 | 已合并 |

### 刷脸签到与思想汇报的差异

| 维度 | 刷脸签到 `checkin` | 思想汇报 `report` |
|---|---|---|
| 采集覆盖 | `face_only`，不启动麦克风 | `both`，人脸 + 语音 |
| 录音控制 | 无录音 | 用户手动「开始 / 结束」，无倒计时、无自动终止 |
| 分析通道 | face 正常即 `done`；asr/emotion/psych 的 `skipped` 属预期 | 四路完整分析 |
| 频率默认值 | 每 1 天 | 每 3 天（管理端可按对象调整） |
| 逾期处理 | 生成 P0 复核工单 + 管理端红色「危机·逾期」标记 | 同左 |

---

## 3. 技术栈

| 层 | 选型 |
|---|---|
| 运行时 | Python 3.11 |
| 采集 | OpenCV、MediaPipe、sounddevice、numpy |
| Web | FastAPI、uvicorn、pydantic v2 |
| 数据 | SQLAlchemy 2.0（`>=2.0,<2.1`）、SQLite |
| 校验 | jsonschema（Draft 2020-12 + FormatChecker） |
| 前端 | React 18、React Router 6、Vite 5、TypeScript 5（纯 CSS Modules，无 UI 库） |
| 测试 | pytest |

---

## 4. 目录结构

```text
community-correction/
├─ app/
│  ├─ capture/              # 采集：摄像头、人脸、录音、会话打包
│  ├─ db/                   # ORM 模型、连接、建库、手工迁移
│  ├─ analysis/             # 四路 Provider、Schema 校验、一致性
│  │  └─ providers/         # mock_asr / mock_emotion / mock_face / mock_psych / sensevoice_asr
│  ├─ grading/              # 五色规则、趋势、合成、工单草案（纯函数）
│  └─ api/                  # FastAPI 应用、路由、依赖、错误信封、集成层
│     └─ routers/           # health / sessions / user / admin
├─ web/
│  ├─ src/user/             # 用户端：Login / Capture / Checkin / Feedback
│  ├─ src/admin/            # 管理端：Subjects / SubjectDetail（档案+媒体+状态概览）/ Tickets
│  ├─ src/api/              # API 客户端、类型、mock
│  ├─ src/components/common/# 色码徽标、敏感面板、状态视图
│  ├─ src/lib/              # 环境变量、HTTP、守卫、错误文案
│  └─ src/mock/             # 静态演示 JSON
├─ docs/
│  ├─ contracts/            # 冻结契约：capture / db / api / ui / grading / analysis.schema
│  ├─ prd.md                # 产品定义与边界
│  ├─ architecture.md       # 架构与数据流
│  ├─ grading.md            # 分级规则说明
│  ├─ PROGRESS.md           # 进度、时间线、待办与风险
│  └─ reports/              # QA 报告
├─ scripts/                 # 建库种子、采集验证、硬件自检
├─ tests/                   # test_capture / test_db / test_analysis / test_grading / test_api
├─ storage/                 # 本地数据（已 gitignore，不入库）
├─ requirements.txt         # 运行依赖
├─ requirements-dev.txt     # 开发依赖（httpx）
└─ .env.example             # 环境变量模板
```

数据目录固定为：

```text
storage/subjects/{subject_id}/sessions/{session_id}/
├─ face.jpg        # 裁剪后人脸（300×300）
├─ audio.wav       # 语音（16kHz / 单声道 / 16-bit），face_only 模式下不存在
└─ meta.json       # 采集元信息（状态、warnings、模式等）
```

---

## 5. 环境依赖

### 必需

- Python **3.11**
- Node.js **18+**（前端构建；仅跑后端可不需要）
- 摄像头与麦克风（真实采集时需要；无设备可用假采集模式）

### 安装

```powershell
# 后端
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt

# 前端
cd web
npm install
```

> `requirements-dev.txt` 已包含 `requirements.txt`，并额外提供 `httpx`（测试客户端与真实 ASR 调用）。

---

## 6. 快速开始

### 6.1 初始化数据库

```powershell
python -m app.db.init
```

默认数据库文件为 `storage/app.db`，可用 `DB_PATH` 覆盖。

### 6.2 执行双模块迁移（已有旧库时必需）

```powershell
python -m app.db.migrations.202611241200_add_dual_module_tasks
```

为 `subjects` 增加签到/汇报频率字段、为 `sessions` 增加 `kind`，并将存量会话回填为 `report`。

### 6.3 启动后端

```powershell
uvicorn app.api.main:app --port 8000
```

- 接口文档：<http://127.0.0.1:8000/docs>
- 健康检查：`GET http://127.0.0.1:8000/api/health`

### 6.4 启动前端

```powershell
cd web
npm run dev
```

访问 <http://127.0.0.1:5173>。开发服务器已把 `/api` 代理到 `http://127.0.0.1:8000`，且 CORS 白名单与端口一致。

### 6.5 无摄像头/麦克风时

```powershell
$env:CAPTURE_FAKE = "1"
uvicorn app.api.main:app --port 8000
```

假采集只写入占位产物，用于跑通接口与前端流程，**不代表真实采集结果**。

> 测试默认开启假采集，不会触达真实设备；请在非测试环境显式关闭。

---

## 7. 环境变量

### 后端

| 变量 | 默认值 | 说明 |
|---|---|---|
| `USER_TOKEN` | `user_demo` | 用户端 Bearer token；生产环境必须改为非默认值 |
| `ADMIN_TOKEN` | `admin_demo` | 管理端 Bearer token；生产环境必须改为非默认值 |
| `APP_ENV` | `development` | 设为 `production` 时，若 token 缺失或仍为 demo 值，**启动直接抛 `RuntimeError`** |
| `DB_PATH` | `storage/app.db` | SQLite 文件路径（相对路径基于仓库根） |
| `STORAGE_ROOT` | `./storage` | 采集产物根目录 |
| `CAPTURE_FAKE` | 未设置 | `1` 时启用假采集（不触碰设备） |
| `DEBUG` | 未设置 | `1` 时把异常堆栈输出到 stdout（不写日志文件） |
| `CAPTURE_DEVICE_INDEX` / `CAPTURE_MIC_INDEX` | `0` | 摄像头 / 麦克风设备序号 |
| `CAPTURE_DURATION_SEC` | `30` | 定时采集时长（手动模式不使用） |
| `CAPTURE_MIN_SPEECH_RATIO` | `0.05` | 有效语音占比阈值 |
| `SENSEVOICE_API_URL` | 空 | 与 `SENSEVOICE_API_KEY` 同时配置才启用真实 ASR |
| `SENSEVOICE_API_KEY` | 空 | 同上；请勿提交到仓库 |

### 前端（`web/`）

| 变量 | 默认值 | 说明 |
|---|---|---|
| `VITE_USE_MOCK` | `1` | `0` 时请求真实后端；默认走 mock |
| `VITE_API_BASE_URL` | 空（同源代理） | 直连后端时填写 |
| `VITE_USER_TOKEN` | `user_demo` | 用户端 token |
| `VITE_ADMIN_TOKEN` | `admin_demo` | 管理端 token |
| `VITE_SUBJECT_ID` | S001（`d0676c19-…`） | 登录后使用的演示对象；需先执行 `scripts/seed_demo.py` |
| `VITE_ROLE` | `staff` | 演示角色 |
| `VITE_DEMO_USERNAME` | `张三` | 用户端开发测试账号（仅本地联调，非真实认证） |
| `VITE_DEMO_PASSWORD` | `123456` | 用户端测试密码 |

### 关于 `.env`

仓库**不自动加载 `.env`**：后端只读取 `os.environ`，`.env` 仅作为本地配置备忘（已被 `.gitignore` 忽略）。请通过环境变量注入：

```powershell
$env:USER_TOKEN = "..."
$env:ADMIN_TOKEN = "..."
$env:SENSEVOICE_API_URL = "http://<host>/recognize"
$env:SENSEVOICE_API_KEY = "..."
```

这样设计是为了避免测试误读真实密钥并请求公网。

---

## 8. 使用示例

### 8.1 统一响应信封

所有业务响应固定为：

```json
{
  "code": 0,
  "message": "ok",
  "data": {},
  "degraded": [],
  "request_id": "0f3c..."
}
```

- 业务错误**一律返回 HTTP 200**，以 `code` 区分；
- 仅未捕获异常返回 HTTP 500 + `code=5000`；
- `degraded` 为字符串数组：`[]` / `["capture"]` / `["analysis"]` / `["capture","analysis"]`。

常用业务码：`0` 成功、`1001` 参数错误、`1003` 无权限/归属不匹配、`1004` 不存在、`1005` 状态冲突、`2001` 采集失败、`2003` 分析不可用、`5000` 未捕获异常。完整定义见 [api.md](./docs/contracts/api.md)。

### 8.2 典型用户端流程（curl）

```powershell
$U = @{ Authorization = "Bearer user_demo" }
$SID = "3b1e7c90-2f4a-4d51-8c6b-7d9e0f1a2b3c"

# 1) 提交知情同意（登录页单次勾选，同时授权面部与语音，一次提交长期有效）
curl.exe -X PUT "http://127.0.0.1:8000/api/user/consent" -H "Authorization: Bearer user_demo" `
  -H "Content-Type: application/json" `
  -d '{\"subject_id\":\"3b1e7c90-2f4a-4d51-8c6b-7d9e0f1a2b3c\",\"face\":true,\"audio\":true}'

# 2) 查看签到/汇报任务状态与逾期情况
curl.exe "http://127.0.0.1:8000/api/user/tasks?subject_id=$SID" -H "Authorization: Bearer user_demo"

# 3) 创建刷脸签到会话（face_only）
curl.exe -X POST "http://127.0.0.1:8000/api/sessions" -H "Authorization: Bearer user_demo" `
  -H "Content-Type: application/json" `
  -d '{\"subject_id\":\"3b1e7c90-2f4a-4d51-8c6b-7d9e0f1a2b3c\",\"kind\":\"checkin\"}'

# 4) 创建思想汇报会话（手动录音；不传 duration_sec）
curl.exe -X POST "http://127.0.0.1:8000/api/sessions" -H "Authorization: Bearer user_demo" `
  -H "Content-Type: application/json" `
  -d '{\"subject_id\":\"3b1e7c90-2f4a-4d51-8c6b-7d9e0f1a2b3c\",\"kind\":\"report\"}'

# 5) 手动结束录音
curl.exe -X POST "http://127.0.0.1:8000/api/sessions/<session_id>/stop?subject_id=$SID" -H "Authorization: Bearer user_demo"

# 6) 对已采集完成的会话运行分析与分级
curl.exe -X POST "http://127.0.0.1:8000/api/sessions/<session_id>/analyze" -H "Authorization: Bearer user_demo"
```

### 8.3 管理端常用操作

```powershell
# 对象列表（同时惰性生成逾期 P0 工单）
curl.exe "http://127.0.0.1:8000/api/admin/subjects" -H "Authorization: Bearer admin_demo"

# 修改某对象的签到/汇报频率（至少一项，整数 ≥1）
curl.exe -X PATCH "http://127.0.0.1:8000/api/admin/subjects/<subject_id>/frequency" `
  -H "Authorization: Bearer admin_demo" -H "Content-Type: application/json" `
  -d '{\"checkin_interval_days\":1,\"report_interval_days\":3}'

# 复核工单列表 / 工单流转
curl.exe "http://127.0.0.1:8000/api/admin/tickets" -H "Authorization: Bearer admin_demo"
curl.exe -X POST "http://127.0.0.1:8000/api/admin/tickets/<ticket_id>/transition" `
  -H "Authorization: Bearer admin_demo" -H "Content-Type: application/json" `
  -d '{\"action\":\"confirm\",\"note\":\"已电话联系\"}'
```

> `GET /api/admin/sessions/{id}/face` 会写 `audit_logs` 留痕；面部图为二进制，不返回绝对路径。

### 8.4 前端操作路径

| 路径 | 页面 | 说明 |
|---|---|---|
| `/login` | 用户登录 | 用户名 / 密码 + 统一知情同意；开发测试账号 `张三 / 123456`，登录并同意后进入 `/capture` |
| `/consent` | 旧同意地址 | 独立页面已移除，访问即跳转 `/login` |
| `/capture` | 事项选择 | 四张卡片：刷脸签到 / 录音思想汇报（含频率与逾期提示）+ AI援助 / 教育学习 |
| `/capture/checkin` | 刷脸签到 | 正视摄像头 → 拍摄 → 等待完成 |
| `/capture/report` | 思想汇报 | 开始录音 → 结束录音 → 保存处理 → 结果反馈 |
| `/pending?feature=ai-aid\|education` | 功能待开发 | 新增入口的统一占位页，可返回事项选择 |
| `/feedback/:sessionId` | 结果反馈 | 仅展示行为建议，不显示色码 |
| `/admin/subjects` | 对象列表 | 最近签到/汇报时间、逾期徽标 |
| `/admin/subjects/:subjectId` | 对象详情 | 基础档案、按日期影像/录音、五色分布与趋势、频率编辑、会话时间线 |
| `/admin/dashboard` | 旧看板地址 | 独立看板已合并进对象详情，访问即跳转 `/admin/subjects` |
| `/admin/tickets` | 复核队列 | 工单列表 |
| `/admin/tickets/:ticketId` | 工单详情 | 证据、逾期来源、流转操作 |

### 8.5 新增入口说明（暂无后端支持）

「事项选择」页（`/capture`）在签到 / 思想汇报之下新增「更多服务」分区，包含两个入口：

| 入口 | 当前行为 | 说明 |
|---|---|---|
| AI援助 | 跳转 `/pending?feature=ai-aid`，显示「功能待开发」 | 代码注释标注后续可扩展**心理援助 / 法律援助 / 就业帮扶**三类服务能力 |
| 教育学习 | 跳转 `/pending?feature=education`，显示「功能待开发」 | 后续承载法治教育、思想教育等学习任务 |

注意事项：

- **前端占位**：两个入口仅做路由跳转与提示展示，**未对接任何后端接口，也没有业务逻辑**；后端无对应端点与数据表。
- **不依赖任务接口**：入口为静态渲染，`/api/user/tasks` 失败时仍正常显示，不影响签到与思想汇报。
- **占位页参数受白名单限制**：`feature` 仅识别 `ai-aid` / `education`，其他取值只显示中性文案「该功能」。
- **样式一致**：复用事项卡片的栅格与卡片样式（`auto-fit, minmax(240px, 1fr)`），窄屏自动单列。
- 扩展时的建议：新增独立路由与页面，并在后端补对应接口后再开放入口，不修改现有签到 / 汇报链路。

### 8.6 管理端对象详情增强（本期新增）

对象列表的**姓名**字段可直接点击进入 `/admin/subjects/:subjectId`，详情页由三部分组成：

| 区域 | 内容 | 数据来源（当前） |
|---|---|---|
| 基础档案 | 姓名、编号、状态、性别、年龄、身份证号、联系电话、住址、矫正类别与起止日期 | `GET /api/admin/subjects/{id}`（mock 扩展 `profiles`） |
| 打卡与思想汇报 | 选择日期后展示该日打卡影像与思想汇报录音；影像内联预览、录音原生播放；另提供该对象有记录的日期快捷按钮 | `GET /api/admin/subjects/{id}/media?date=YYYY-MM-DD`（mock） |
| 状态概览 | 五色分布、近 7 天趋势、待复核工单数、最近采集与「危机·逾期」标记 | `GET /api/admin/dashboard?subject_id=...`（mock `variants`） |

交互与隐私约定：

- 媒体统一放入敏感面板（`SensitivePanel`），**默认折叠**，展开时提示「调阅记录待接入 audit 留痕」；不写入浏览器持久化存储，不自动播放。
- 日期筛选与状态概览并行加载，任一失败只影响对应区块，不影响档案展示。
- 状态概览与原独立看板内容一致，原 `/admin/dashboard` 与导航入口均已下线。

> 当前媒体为演示素材：影像由文生图占位服务生成，录音为运行时构造的 2 秒静音 WAV；真实影像/音频接口、留存期与审计留痕尚未进入契约，联调时需一并补齐。

---

## 9. 数据库与迁移

- 5 张表：`subjects`、`sessions`、`reviews`、`review_tickets`、`audit_logs`。
- `sessions.coverage` 为派生属性，不落列。
- 原型阶段**不引入 Alembic**，采用 `app/db/migrations/` 下的手工迁移脚本，正式部署前再切换。
- 表结构权威定义见 [docs/contracts/db.md](./docs/contracts/db.md)。

```powershell
python -m app.db.init                                        # 建库（幂等）
python -m app.db.migrations.202611241200_add_dual_module_tasks  # 双模块迁移
```

---

## 10. 演示数据

```powershell
python scripts\seed_demo.py            # 幂等写入
python scripts\seed_demo.py --reset    # 清空后重建
```

生成 6 个对象、42 条会话、6 份复盘、3 张工单及审计记录。

> 演示数据的色阶与工单均为**手工指定**，未调用分级规则；`face.jpg` 与 `transcript.txt` 是占位素材，**不得用于效果评估或对外宣称**。

---

## 11. 测试

```powershell
pytest tests -q                 # 全量：286 passed
pytest tests/test_api -q        # 接口
pytest tests/test_analysis -q   # 分析
pytest tests/test_grading -q    # 分级
pytest tests/test_capture -q    # 采集
pytest tests/test_db -q         # 数据层
```

前端校验：

```powershell
cd web
npm run typecheck
npm run build
```

测试约定：

- 采集测试全部使用假设备 / 假采集，不触碰真实硬件；
- 分析测试用 `unittest.mock` 拦截 `httpx.post`，**绝不请求公网**；
- `tests/test_analysis/conftest.py` 以 autouse fixture 清除 `SENSEVOICE_*`，防止本机真实密钥被误用。

---

## 12. 常见问题（FAQ）

<details>
<summary><b>Q1：没有摄像头 / 麦克风，能跑完整流程吗？</b></summary>

可以。设置 `CAPTURE_FAKE=1` 后启动后端，采集会写占位产物并正常走完分析、分级与反馈。该模式仅用于联调，不代表真实采集效果。

</details>

<details>
<summary><b>Q2：`.env` 里填了密钥，为什么没生效？</b></summary>

后端只读取 `os.environ`，不自动加载 `.env`。请用环境变量注入（PowerShell 用 `$env:KEY="value"`）。这是为了避免测试误触真实外部服务。

</details>

<details>
<summary><b>Q3：启动时报缺少 `kind` / `checkin_interval_days` 列？</b></summary>

旧数据库未迁移。执行 `python -m app.db.migrations.202611241200_add_dual_module_tasks`。

</details>

<details>
<summary><b>Q4：前端页面全是假数据？</b></summary>

默认 `VITE_USE_MOCK=1`。切真实接口：先启动后端，再 `$env:VITE_USE_MOCK="0"; npm run dev`。

</details>

<details>
<summary><b>Q5：接口返回 HTTP 200 但 `code` 不是 0？</b></summary>

这是设计约定：业务错误统一走 HTTP 200 + 业务码，便于前端统一拦截。只有未捕获异常才是 HTTP 500 + `code=5000`。排查时请带上响应头 `X-Request-Id` 对应日志。

</details>

<details>
<summary><b>Q6：请求返回 1003 / 1004？</b></summary>

`1003` 表示无权限或 `subject_id` 归属不匹配（用户端调用会话接口必须带自己的 `subject_id`）；`1004` 表示对象或会话不存在。

</details>

<details>
<summary><b>Q7：`APP_ENV=production` 启动直接崩溃？</b></summary>

生产环境要求 `USER_TOKEN` / `ADMIN_TOKEN` 显式配置且不能等于 demo 默认值，否则启动即抛 `RuntimeError`（安全守卫，避免误用默认凭据）。

</details>

<details>
<summary><b>Q8：安装依赖后仍出现 SQLAlchemy 外键写入顺序错误？</b></summary>

请确认版本为 `>=2.0,<2.1`。2.1.x 在同事务多表外键写入时存在 flush 顺序问题，`requirements.txt` 已锁定上限。

</details>

<details>
<summary><b>Q9：为什么记录里有工单，但没有任何"处置"？</b></summary>

这是产品红线：分级结果唯一出口是人工复核工单，系统不执行限制、通报、扣分等动作，最终判断由工作人员线下完成。

</details>

<details>
<summary><b>Q10：跨域 500 响应读不到 `request_id`？</b></summary>

已知问题：未捕获异常由最外层中间件处理，500 响应可能缺少 CORS 头，但响应头 `X-Request-Id` 与日志中的 `request_id` 仍然存在。已记录在进度文档风险项。

</details>

---

## 13. 已知限制

| 限制 | 说明 |
|---|---|
| 分析模型 | 除 ASR 外（SenseVoice 可选），情绪 / 表情 / 心理均为确定性 Mock，阈值为 `TODO: 待标定` |
| 前端联调 | 默认 mock；管理端尚未整体切换真实接口 |
| 未实现端点 | 复盘列表 `GET /api/admin/reviews`、转写查看、60 秒频控（`1006`） |
| 同步分析 | `analyze` 为同步长请求，原型阶段可接受 |
| 采集设备 | 采集运行在后端宿主设备，暂不支持浏览器内采集 |
| 手动录音 | 已通过假采集与单元测试闭环，真实长时录音的设备侧表现待现场验证 |
| AI援助 / 教育学习 | 仅前端入口与「功能待开发」占位页，**无后端接口、无业务逻辑、无数据留存** |
| 用户登录 | 开发阶段演示账号（前端校验，密码会进入打包产物），**非真实身份认证**；生产需接入真实用户体系 |
| 管理端档案字段 | 性别 / 年龄 / 身份证号 / 住址等由前端 mock 扩展，`db` / `api` 契约尚未定义；身份证号目前明文展示，接入真实接口前需补脱敏与权限规则 |
| 管理端媒体预览 | 打卡影像为文生图占位、录音为运行时生成的 2 秒静音 WAV；媒体端点、鉴权、留存期与 audit 留痕未入契约，暂不可用于真实调阅 |
| 状态看板 | 已合并进对象详情，独立页面与导航入口已移除 |

---

## 14. 文档索引

| 文档 | 内容 |
|---|---|
| [docs/prd.md](./docs/prd.md) | 产品定位、用户、边界与不做清单 |
| [docs/architecture.md](./docs/architecture.md) | 分层架构、数据流、存储与部署形态 |
| [docs/grading.md](./docs/grading.md) | 五色分级规则与工单策略 |
| [docs/contracts/capture.md](./docs/contracts/capture.md) | 采集契约（状态机、目录、裁剪、模式） |
| [docs/contracts/db.md](./docs/contracts/db.md) | 表结构、约束、索引与迁移约定 |
| [docs/contracts/api.md](./docs/contracts/api.md) | 端点、信封、错误码、鉴权 |
| [docs/contracts/ui.md](./docs/contracts/ui.md) | 页面结构、文案与展示红线 |
| [docs/contracts/grading.md](./docs/contracts/grading.md) | 分级契约（规则版本、优先级、覆写） |
| [docs/contracts/analysis.schema.json](./docs/contracts/analysis.schema.json) | 分析结果 JSON Schema |
| [docs/PROGRESS.md](./docs/PROGRESS.md) | 时间线、已完成模块、待办与风险 |

---

## 15. 贡献与扩展约定

- **契约先行**：任何跨层改动先更新 `docs/contracts/`，再落代码；契约版本号只增不改，实现变更以「实现补记」形式附加。
- **目录所有权**：按模块划分可写范围（见 [PROGRESS.md §8](./docs/PROGRESS.md)），避免多人并行时越界修改。
- **隐私优先**：涉及人脸、音频、心理数据的改动，合并前需通过隐私审查；日志禁止写入敏感原文与绝对路径。
- **测试要求**：新增端点或规则需带正例与边界负例，且不得依赖真实设备或公网。
- **预留扩展位**：后续可在本 README 追加「性能与容量」「部署与运维」「变更日志」章节；进度与风险统一维护在 `docs/PROGRESS.md`。

---

> 本项目为原型验证用途，尚未完成安全加固、容量评估与合规评审，请勿直接用于生产环境。
