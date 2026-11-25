# 项目进度（PROGRESS）

> 生成时间：2026-11-25 · 基准提交：`62f21c0`（含 P12–P14，`main` 与 `origin/main` 同步）· 工作区增量：P15 管理端本地化与术语统一 · 依据：`git log`、`git tag`、`pytest` 实测、[QA 报告](./reports/qa-2026-11-24.md)。
> 本文只记录仓库里可核实的事实；尚未实现或未定稿的内容标注「待确认」。

## 1. 项目定位与技术栈

**一句话**：社区矫正场景的单对象纵向切片原型——把一次采集（人脸 + 语音）转成结构化信号，经四路分析与五色分级，**分级结果唯一出口是人工复核任务**，系统自身不产生处置动作（[prd.md](./prd.md#L20)）。

| 层 | 选型 | 现状 |
|---|---|---|
| 运行时 | Python 3.11 | 已用（本机 3.11.0rc2） |
| 采集 | OpenCV / MediaPipe / sounddevice | 已实现并硬件验证，封存于 `capture-v1` |
| Web 框架 | FastAPI 0.165.0 + uvicorn 0.54.0 | 骨架 + 用户端 / consent / analyze 接入（`api-v1` → `api@1.5` 实现补记） |
| ORM / 数据库 | SQLAlchemy 2.x（原型阶段手工迁移）/ SQLite | 5 张表已实现（`db-v1`）；本机实际 2.1.9，`requirements` 已锁 `<2.1` |
| 分析 | Provider 抽象 + 确定性 mock（ASR 可选真实 SenseVoice） | 四路 mock 已实现；`overall.risk_level` 已接 `app.grading.config.map_risk_level`（`c46536e`）；ASR 已接真实 SenseVoice API（env 配置启用，失败回退 Mock，未提交） |
| 分级 | 五色纯函数规则 + 七日趋势 + 复核任务草案 | 已实现并接入 analyze / 复盘 / 复核任务接口（`c46536e`） |
| Schema 校验 | jsonschema（Draft 2020-12 + FormatChecker） | 已引入，分析结果强制校验 |
| 前端 | React + Vite（用户端 / 管理端同仓，按路由分区） | 用户端登录（含同意）+ 采集/反馈 + 管理端列表/详情/复核任务已实现（`601d33d`；P12 登录页；P14 对象详情档案、按日期媒体、状态概览；P15 全量中文化与术语统一） |
| 测试 | pytest | 286 条全绿（capture 14 / db 21 / api 74 / analysis 69 / grading 108） |

技术栈来源：[architecture.md](./architecture.md#L11-L21)；采集运行在后端宿主设备而非浏览器（[architecture.md](./architecture.md#L23-L31)）。

## 2. 开发时间线（阶段化）

> 依据 `git log` 的提交时间与标签整理；同一阶段内的提交集中在数十分钟内完成。日期为提交日期（2026-11-23 ～ 2026-11-25）。「工作区」表示已实现但尚未提交。

| 阶段 | 时间 | 主线动作 | 交付物 | 追溯 |
|---|---|---|---|---|
| P0 契约基线 | 11-23 21:44 | 确立 `app/capture/` 与四份契约初稿，明确「分级只出口复核任务」边界 | 契约 v1.1 | `7a6f0cf` |
| P1 契约冻结 | 11-23 21:54–21:59 | 关闭 `grading` 的 `partial` 歧义、`ui` 的 `no_face/no_audio` 口径、`api` 降级语义；冻结 v1.2 | `contracts-v1.1`、`contracts-v1.2` | `2003967`、`8698a26` |
| P2 采集模块 | 11-23 22:09–23:16 | 状态机对齐契约（`coverage`/`warnings`/可选裁剪）；真机验证 `ok/both`；DirectShow 优先、16k 音频 | `app/capture/`、`tests/test_capture/`、`scripts/verify_capture.py`、`scripts/hw_check.py` | `787ee0e`、`55c9a25`（`capture-v1`） |
| P3 数据层 | 11-23 23:20–23:34 | 五表建模、派生 `coverage`、服务端默认值；`reviews` 窗口唯一 | `app/db/`、db@1.3 | `492c764`、`ddd4968`（`contracts-v1.3`）、`bc83a3e`（`db-v1`） |
| P4 API 骨架 | 11-24 00:03–00:20 | 统一信封、鉴权、异步采集、`2001/2003`、db@1.4/api@1.4；演示数据脚本 | `app/api/`、`scripts/seed_demo.py` | `96aa098`、`79e582d`（`api-v1`）、`0bb78b5` |
| P5 QA 修复 | 11-24 00:49–01:02 | M1–M4/L4/L8：锁 SQLAlchemy、FK 测试开关、日志脱敏、可注入 session 工厂、`CAPTURE_FAKE` | QA 报告 + 修复 + 进度快照 | `638245e`、`7732930`、`43d3aba`、`9b2a04d` |
| P6 分析模块 | 11-24 01:56 | 四路确定性 mock、Schema 校验、一致性判定、运行状态包装层 | `app/analysis/`、`tests/test_analysis/` | `81a8499` |
| P7 用户端 API | 11-24 08:31 | `/api/user/*`、consent 三闸、会话归属校验（api@1.5） | `app/api/routers/user.py` | `4f5d1bf` |
| P8 分级与前端骨架 | 11-24 13:24–13:34 | 五色规则、七日趋势、合成封顶、复核任务草案；前端用户端 3 页 + 管理端 4 页（mock） | `app/grading/`、`tests/test_grading/`、`web/` | `67adee6`、`601d33d`、`337fdb9`、`7782e65` |
| P9 分析→分级打通 | 11-24 14:18 | `analyze` 正式接入、复盘/复核任务/看板端点、低一致性强制 P0、契约同步 | `app/api/integration.py`、相关路由 | `1d3fb0e`、`c46536e`、`5eef4bb` |
| P10 双模块与手动录音 | 11-24 15:05–15:20 | ① SenseVoice ASR 真实接入（超时回退）② consent 一次性授权、去保存期限 ③ 签到/汇报双模块 + 逾期复核 ④ 思想汇报手动录音 | 见 §3 下表 | `fa5a0d7`、`8013d4e` |
| P11 用户端入口调整 | 2026-11-24 16:05 | 同意后直达采集页；事项页新增「AI援助」「教育学习」入口与「功能待开发」占位页；文档同步 | `web/src/user/`、`docs/contracts/ui.md`、`README.md` | 见 §2.1 |
| P12 登录页与同意合并 | 2026-11-25 | 新增 `/login`（用户名 / 密码 / 统一知情同意）；删除独立同意页与组件，旧 `/consent` 仅跳转；演示账号 `张三 / 123456`；守卫改为「登录 + 同意三要素」；默认演示对象改指 seed 的 S001 | `web/src/user/Login/`、`web/src/lib/auth.ts`、`web/src/lib/guards.tsx`、`web/src/App.tsx`、`docs/contracts/ui.md` | 见 §2.2 |
| P13 思想汇报同步脚手架 | 2026-11-25 | 新增 `sensevoice_syncs` 表与迁移；新增同步/列表/详情三个管理端端点（功能开关默认关闭，失败整体回滚）；新增严格 SenseVoice 转写 + 情绪适配层（无 Mock 回退）；对象详情页新增「思想汇报同步」面板；13 条契约测试 | `app/analysis/sensevoice_sync.py`、`app/db/`、`app/api/`、`web/src/admin/SubjectDetail/`、`docs/contracts/{db,api,ui}.md` | 见 §2.3 |
| P14 管理端对象详情增强 | 2026-11-25 | 列表姓名跳转详情；详情补基础档案（性别/年龄/身份证号等）；新增按日期查看打卡影像与思想汇报录音（在线预览/播放，敏感面板默认折叠）；状态看板整体合并进详情并下线独立入口 | `web/src/api/`、`web/src/mock/`、`web/src/admin/`、`web/src/App.tsx` | 见 §2.4 |
| P15 管理端本地化与术语统一 | 2026-11-25 | ① 色码规则、触发规则、证据字段/阈值/取值全部中文化，未知项中性占位；② 移除对象名称下方 UUID；③ 「工单 / 建单」统一改称「复核任务 / 生成任务」，同步五份契约、README、PRD、分级说明与架构文档；④ 修复对象列表「状态 / 最近签到」与复核队列「对象 / 状态」等短文本换行 | `web/src/lib/ruleText.ts`、`web/src/admin/`、`web/src/components/common/ColorBadge.tsx`、`docs/contracts/`、`README.md` | 见 §2.5（工作区） |

**阶段结论**：P0–P10 已形成「采集 → 数据 → 分析 → 分级 → 复核任务 → 前端」的完整纵向切片并全部提交。P11–P14 已提交（用户端入口、登录页合并同意、思想汇报同步脚手架、管理端对象详情增强），P15 为当前工作区增量（管理端本地化、术语统一与表格换行修复）。其中 P13 的同步能力因 SenseVoice 服务不可达与情绪接口协议未确认而**默认关闭**，不产生真实同步数据；P14 的媒体与档案字段仍为前端 mock 扩展，契约待补；P15 仅调整展示文案与样式，不改接口、状态机与流转规则。后端测试总数由 224 增至 286。

### 2.1 进度记录：P11 用户端入口与跳转调整

| 项 | 内容 |
|---|---|
| 完成时间 | 2026-11-24 16:05（Asia/Shanghai） |
| 变更内容 | ① 移除同意后的中间引导步骤：`PUT /api/user/consent` 成功后直接 `replace` 跳转 `/capture`，删除「进入采集引导」按钮与成功提示框<br>② `/capture` 新增「更多服务」分区，加入 **AI援助**、**教育学习** 两个入口卡片（复用事项卡片样式与响应式栅格，不依赖任务接口）<br>③ 新建 `/pending?feature=ai-aid\|education`「功能待开发」占位页，白名单校验参数并提供返回入口<br>④ 代码注释标注 AI援助 后续可扩展心理援助 / 法律援助 / 就业帮扶<br>⑤ 同步 `ui@1.2` 补记 5、README 功能说明与已知限制 |
| 完成状态 | 已完成（前端）；`npm run build` 通过；浏览器实测：同意提交直达 `/capture`、四卡片展示、两个入口跳转与占位页文案均符合预期 |
| 影响范围 | 仅 `web/src/user/`（Consent、Capture、ComingSoon）与 `web/src/App.tsx`；未改动签到 / 汇报 / 分析 / 分级 / 后端逻辑，pytest 仍为 273 passed |
| 后续待办 | ① 为 AI援助 / 教育学习设计并实现后端接口与数据表后再开放入口<br>② 需要时把 AI援助 拆分为心理援助 / 法律援助 / 就业帮扶三个独立入口与页面<br>③ 补充前端路由级测试（当前依赖构建与人工浏览器验证）<br>④ 管理端如需可见入口配置，需新增配置项（当前无） |
| 备注 | 两个新增入口**暂无后端支持**，仅为占位；`feature` 非法取值只显示中性文案，不泄露内部标识 |

### 2.2 进度记录：P12 登录页与知情同意合并

| 项 | 内容 |
|---|---|
| 完成时间 | 2026-11-25（Asia/Shanghai） |
| 变更内容 | ① 新增用户登录页 `/login`：用户名、密码输入框与「登录并进入」按钮，保持现有 tokens 视觉规范与移动端可用性<br>② 原独立知情同意页 `/consent` 的告知、勾选与提交能力合并至登录页，删除 `web/src/user/Consent/` 独立页面与组件，`/consent` 仅保留跳转 `/login`<br>③ 面部图像与语音两项同意合并为**单一统一勾选**，勾选一次即同时授权两项；提交仍调用 `PUT /api/user/consent`（`face=true, audio=true`），后端契约不变<br>④ 配置开发演示账号 `张三 / 123456`（`VITE_DEMO_USERNAME` / `VITE_DEMO_PASSWORD` 可覆盖）；账号与同意均通过后才允许进入系统<br>⑤ 路由守卫由「仅校验同意」改为「校验登录态 + 同意三要素」，未登录/同意不完整统一跳 `/login`<br>⑥ 默认演示对象改为 `seed_demo.py` 生成的 S001（`d0676c19-…`），真实后端模式下同意与签到/汇报数据可实时落库<br>⑦ 同步 `ui.md` 补记 7、`web/.env.example` 与 README 路由说明 |
| 完成状态 | 已完成（前端）；`npm run typecheck` 与 `npm run build` 通过；浏览器实测：登录页三要素齐全、错误密码提示并停留、正确账号 + 勾选同意后跳转 `/capture`；真实后端实测（临时 DB + `CAPTURE_FAKE=1`，端口 8010）：同意写入 `code=0`、签到与汇报会话均落库为 `captured`、`GET /api/user/tasks` 的 `last_completed_at` 已实时更新 |
| 影响范围 | `web/src/user/Login/`（新增）、`web/src/lib/auth.ts`（新增）、`web/src/lib/guards.tsx`、`web/src/App.tsx`、`web/src/EntryPages.tsx`、用户端各页底部入口、`web/src/api/mock.ts`（mock 同意状态持久化）、`web/.env.example`；后端与接口契约无改动，实测 `pytest tests -q` 仍为 273 passed |
| 后续待办 | ① 生产环境接入真实认证（用户表 / 统一身份），移除前端演示账号与明文密码<br>② 如需查看已提交同意或在线撤回，可在登录页补充「同意状态」区块并调用既有 `GET/PUT /api/user/consent`、`POST /api/user/consent/revoke`<br>③ 真实后端联调需 `VITE_USE_MOCK=0` 且先执行 `python scripts/seed_demo.py`，否则默认演示对象不存在会提示 1004<br>④ 补充登录页的路由级自动化测试（当前依赖构建与人工浏览器验证） |
| 备注 | 登录校验为**开发阶段演示账号**，密码会进入前端打包产物，不能视为真实鉴权；Mock 模式下同意状态写入 `localStorage` 以保证刷新后登录态连贯，真实模式以后端为准 |

### 2.3 进度记录：P13 思想汇报同步脚手架

| 项 | 内容 |
|---|---|
| 完成时间 | 2026-11-25（Asia/Shanghai） |
| 变更内容 | ① 契约新增 `db@1.5 §7 sensevoice_syncs`、`api@1.5 §7.15–7.17` 与业务码 `2004/5001`、`ui@1.2 补记 8`<br>② 新增 ORM `SensevoiceSync` 与迁移 `202611251200_add_sensevoice_syncs.py`（幂等，仅新增表与索引）<br>③ 新增严格同步适配层 `app/analysis/sensevoice_sync.py`：ASR + 情绪均失败即抛错，**绝不回退 Mock**；情绪响应防御式映射为 `emotion@1.0`<br>④ 新增 `POST /api/admin/subjects/{id}/sensevoice-sync`（单事务，失败整体回滚）、`GET .../sensevoice-syncs`、`GET /api/admin/sensevoice-syncs/{id}`（读取转写写 `sensitive.view` 留痕）<br>⑤ 对象详情页新增「思想汇报同步」面板：同步按钮、记录列表、按需展开完整报告，能力未启用时只显示中性提示<br>⑥ 新增 13 条契约测试 |
| 完成状态 | 脚手架已完成；`pytest tests -q` 286 passed、`npm run build` 通过；真实库已执行迁移并确认表/索引存在；重启后实测列表返回 `code=0, total=0`、同步返回 `code=5001, message=sensevoice_sync_disabled` |
| 开关与启用条件 | 环境变量 `SENSEVOICE_SYNC_ENABLED`（默认 `0`）控制；启用还需 `SENSEVOICE_API_URL`、`SENSEVOICE_API_KEY`、`SENSEVOICE_EMOTION_API_URL` 三项齐全。当前 `.env` 只有 ASR 地址与 Key，**缺情绪服务地址**；SenseVoice 服务 `8.133.237.222:8000` 连接失败/超时，因此保持关闭 |
| 影响范围 | `app/analysis/sensevoice_sync.py`（新增）、`app/db/models.py`、`app/db/migrations/`、`app/api/{errors,schemas}.py`、`app/api/routers/admin.py`、`web/src/api/{admin,types,mock}.ts`、`web/src/lib/errorMessages.ts`、`web/src/admin/SubjectDetail/`、`tests/test_api/test_sensevoice_sync.py`、三份契约 |
| 后续待办 | ① 待 SenseVoice 恢复并确认情绪接口协议后，配置 `SENSEVOICE_EMOTION_API_URL` 并设 `SENSEVOICE_SYNC_ENABLED=1`<br>② 张三需真实录制 ≥5 秒思想汇报（现有今日会话仅 2 秒且未保存音频；历史 seed 行引用的 `audio.wav` 不存在）<br>③ 启用前用真实音频跑一次同步，核对转写全文、情绪类型/置信度/关键片段<br>④ 复核 `data_version` 秒级粒度的重复同步语义 |
| 备注 | 本轮**未产生任何同步数据**；Mock 模式下同步接口固定返回 `5001 sensevoice_sync_disabled`，不伪造转写或情绪结果。当前 8000 后端已按新代码重启 |

### 2.4 进度记录：P14 管理端对象详情增强与状态看板合并

| 项 | 内容 |
|---|---|
| 完成时间 | 2026-11-25（Asia/Shanghai） |
| 变更内容 | ① 对象列表的**姓名**改为详情链接（`/admin/subjects/:subjectId`）<br>② 详情页新增基础档案：性别、年龄、身份证号、联系电话、住址、矫正类别与起止日期；`SubjectDetail` 类型扩展 `SubjectProfileFields`<br>③ 新增「打卡与思想汇报」日期筛选：日期输入 + 有记录日期快捷按钮，按日展示打卡影像（内联预览）与思想汇报录音（原生播放器），统一放入默认折叠的敏感面板<br>④ 原独立状态看板内容（五色分布、近 7 天趋势、待复核数、最近采集、逾期标记）整体迁入详情页，新增 `TrendStrip`；删除 `web/src/admin/Dashboard/`，导航仅保留「对象列表」「复核队列」<br>⑤ 旧地址 `/admin/dashboard` 重定向至 `/admin/subjects`（绝对路径，避免相对解析成 `/admin/dashboard/subjects`）<br>⑥ 前端 mock 扩展：`subject.json` 增加档案 `profiles` 与按日媒体 `media`，`dashboard.json` 增加对象级 `variants`；新增 `GET /api/admin/subjects/{id}/media` mock 分支 |
| 完成状态 | 已完成（前端）；`npm run typecheck`、`npm run build` 通过；浏览器实测（mock 模式）：姓名链接 URL 正确、档案字段完整显示、默认日期影像加载成功、录音可播放至结束、无录音日期显示中性提示、`/admin/dashboard` 最终停在 `/admin/subjects`、全程无 console error |
| 影响范围 | 仅 `web/`：`src/api/{types,admin,mock}.ts`、`src/mock/{subject,dashboard}.json`、`src/admin/{AdminLayout.tsx,Subjects/*,SubjectDetail/*}`、`src/App.tsx`、`src/EntryPages.tsx`；未改动 `app/`，`docs/contracts/ui.md` 仅追加补记 9，后端 pytest 不受影响 |
| 后续待办 | ① 契约补齐：档案字段（含身份证号脱敏与可见范围）、媒体端点（鉴权/留存期/`audit_logs` 留痕）、单对象 dashboard 变体语义<br>② 真实接口联调：影像与音频改为后端返回，替换文生图占位与 2 秒静音 WAV<br>③ 调阅留痕接入后把敏感面板的提示文案改为真实审计状态 |
| 备注 | 媒体为**演示素材**：影像走文生图占位服务，录音为运行时构造的 2 秒单声道 WAV；不写入 localStorage/IndexedDB，不自动播放；密码、身份证号等敏感信息仅用于原型展示，不可用于生产 |

### 2.5 进度记录：P15 管理端本地化、术语统一与换行修复

| 项 | 内容 |
|---|---|
| 完成时间 | 2026-11-25（Asia/Shanghai） |
| 变更内容 | ① 新增 `web/src/lib/ruleText.ts`：规则编号 → 中文名称、证据字段路径 → 中文、阈值键 → 中文、`low/medium/high` → 低/中/高；色码徽标、触发规则列、证据链统一显示中文，未知项以「其他规则 / 分析字段 / 其他阈值 / —」中性占位<br>② 复核队列对象列与任务详情移除姓名下方的 UUID；筛选占位符改为「请输入对象编号」<br>③ 术语统一：「工单」→「复核任务」、「建单时间」→「生成时间」、「自动建单」→「自动生成」；同步 `ui/api/db/grading/capture` 五份契约、`README.md`、`prd.md`、`grading.md` 与 `architecture.md`<br>④ 修复短文本换行：对象列表「编号 / 状态 / 待复核 / 最近签到 / 最近汇报 / 最近采集」与复核队列「优先级 / 对象 / 任务来源 / 生成时间 / 截止 / 状态」加 `nowrap`，窄屏由横向滚动兜底<br>⑤ 清理固定文案中的 audit / mock / api@1.5 / SenseVoice 等英文，未知状态统一中文兜底 |
| 完成状态 | 已完成（前端 + 文档）；`npm run typecheck`、`npm run build` 通过；浏览器实测四个管理端页面：短文本单行、档案与日期媒体正常、规则/证据/阈值全中文、全页无「工单」与英文残留、无 console error |
| 影响范围 | `web/src/lib/ruleText.ts`（新增）、`web/src/components/common/ColorBadge.tsx`、`web/src/admin/{Subjects,Tickets,SubjectDetail,OverdueBadge.tsx}`、`web/src/api/types.ts`（注释）、`web/src/mock/ticket.json`（文案）；`docs/contracts/{ui,api,db,grading,capture}.md` 增加术语同步说明；`README.md` 功能表与详情说明；`docs/{prd,grading,architecture}.md` 术语同步。未改 `app/` 与接口行为，pytest 仍为 286 passed |
| 后续待办 | ① 补充文本映射的单测与页面快照测试（当前依赖 typecheck/build + 浏览器人工验证）<br>② 档案、媒体、单对象看板的契约缺口仍待补（见 §5）<br>③ 身份证号等敏感字段的脱敏与查看范围需在契约中明确 |
| 备注 | 规则编号等原始标识仍由接口与审计留痕保存，仅界面不再展示；P0/P1/P2、S001 编号与会话 UUID 属机器标识，保留显示 |

### 2.6 进度记录：P16 对象心理状态分析看板（任意区间 + 四图 + 中性语义）

| 项 | 内容 |
|---|---|
| 完成时间 | 2026-11-25（Asia/Shanghai） |
| 变更内容 | ① **契约**：`api.md` 新增 §7.18 `GET /api/admin/subjects/{subject_id}/trends`（任意日期区间、缺省近 14 天、上限 366 天、逐日补齐、字段唯一口径、`signals` 九码枚举），并在 §5.4/§6/§8/变更记录同步；`ui.md` 新增补记 11、§4.2 看板区块、§4.2.1 心理提示文案映射、§8.2 八个新组件、§9 五条验收项<br>② **后端**：新增 `app/api/aggregation.py`（区间校验 + 日粒度聚合 + 9 个信号纯函数，阈值常量标「待标定」）、`schemas.py` 11 个输出模型、`admin.py` 只读路由；单条 `analysis_json` 解析失败跳过并只记 `session_id`<br>③ **种子**：`scripts/seed_demo.py` 为 S001 生成连续 14 天波动窗口（每日 1 签到 + 1 汇报、每日复盘、颜色 `green,green,blue,yellow,yellow,orange,blue,green,blue,yellow,orange,orange,yellow,blue`），含 2 天高唤醒负效价、3 天低效价低唤醒、2 天正向、2 天 `low`（1 天 `conflict`）、2 天 `degraded`，并缺 2 天签到、1 天汇报制造逾期；按 `(subject_id, window_end)` 预检查保证幂等<br>④ **前端**：`SubjectDetail` 新增 `TrendBoard/`（区间条、汇总条、提示卡、四图），`types/admin/mock` 对接 §7.18，新增 `psychText.ts` 与 `mock/trend.json`；引入 `recharts@3.11.1`；`TrendStrip` 保留兼容 |
| 完成状态 | 已完成（契约 + 后端 + 种子 + 前端）。`python -m pytest tests -q` → **301 passed**（新增 15 个趋势契约用例）；`npm run typecheck`、`npm run build` 通过；mock 模式浏览器实测 S001 详情页：看板标题 + 散点图/热力图/柱状图/依从性日历四图全部渲染，无红色报错、无整块空白 |
| 影响范围 | `docs/contracts/{api,ui}.md`；`app/api/{aggregation.py,schemas.py,routers/admin.py}`；`scripts/seed_demo.py`；`tests/test_api/test_trends.py`；`web/package.json`、`web/package-lock.json`、`web/src/api/{types,admin,mock}.ts`、`web/src/mock/trend.json`、`web/src/lib/psychText.ts`、`web/src/admin/SubjectDetail/{SubjectDetailPage.tsx,TrendBoard/*}`。未改 `app/db/`、`app/capture/`、`app/analysis/`、`app/grading/`，不新增表/列、不做迁移 |
| 后续待办 | ① 真实 `storage/app.db` 尚未执行扩充后的 seed（避免覆盖既有真实会话，需确认后再跑）<br>② 历史 `reviews.window_end` 存在完整 ISO 时间戳写法，与契约「`YYYY-MM-DD` 自然日」漂移；端点已兼容，历史数据未清洗<br>③ mock 未放置「无复盘日」样例（14 天均有复盘），灰色块分支仅由代码路径覆盖<br>④ 已补齐（P17）：看板证据入口直达 `/admin/reviews/:reviewId` 单条复盘只读详情<br>⑤ 象限分界与 9 个信号阈值均为「待标定」 |
| 备注 | 文案红线：后端只回 `signals` 机器码，前端 `psychText.ts` 只使用测量学描述并统一附「仅作提示，需结合面谈与人工复核」，全仓库扫描无「抑郁/焦虑症/人格障碍/精神异常/自杀」；行为依从性日历使用独立三态配色，不复用五色风险令牌；`behavior.overdue` 为历史回溯口径，与列表页实时逾期可能不同 |

### 2.7 进度记录：P17 看板证据入口直达单条复盘

| 项 | 内容 |
|---|---|
| 完成时间 | 2026-11-25（Asia/Shanghai） |
| 变更内容 | ① `ui.md` 新增 §4.6 复盘详情 `/admin/reviews/:reviewId`（只读区块、证据入口约定、禁止项），§8.2 组件清单与 §9 验收项同步<br>② 新增 `web/src/admin/Reviews/ReviewDetailPage.tsx` + `ReviewDetail.module.css`：基本信息（对象可点回详情、窗口、生成时间、规则版本）、结论区（`ColorBadge` + `rules_fired` 中文 + 趋势色/单次风险/一致性/人工复核）、证据链（复用 `EvidenceTable`）；只读，无流转动作<br>③ `App.tsx` 在 `/admin` 下新增 `reviews/:reviewId` 路由<br>④ `trendDisplay.ts` 的 `evidenceHref` 改为接收 `review_id`，散点 tooltip/详情面板与热力块全部直达复盘详情；缺 `review_id` 仅显示中性说明，不伪造链接 |
| 完成状态 | 已完成。`npm run typecheck`、`npm run build` 通过；浏览器实测：点击热力图橙色方格（2026-11-22）→「查看依据」→ `/admin/reviews/c41d0a77-…b0b`，页面显示「复盘详情」与 1 行证据链，无红色报错；直接打开复盘 URL 亦正常渲染 |
| 影响范围 | `docs/contracts/ui.md`；`web/src/App.tsx`、`web/src/admin/Reviews/*`、`web/src/admin/SubjectDetail/TrendBoard/{trendDisplay.ts,RussellScatter.tsx,ColorCalendarHeatmap.tsx}`。未改后端、`app/`、`tests/`、`web/src/api/*`、`web/src/mock/*` |
| 后续待办 | mock 对任意 `review_id` 返回同一复盘，`1004` 分支仅能在真实后端复现；真实库联调时需确认复盘 `review_id` 与看板数据一致 |
| 备注 | 复盘详情为只读记录，不展示转写、音频、影像；查看原始内容仍走复核任务详情的折叠敏感面板（留痕） |

### 2.8 进度记录：P18 心理趋势并入状态概览 + 四图折叠

| 项 | 内容 |
|---|---|
| 完成时间 | 2026-11-25（Asia/Shanghai） |
| 变更内容 | ① `ui.md` 新增补记 12：移除独立看板区块/标题，全部内容并入「状态概览」；四图改为可折叠按钮（默认收起、`aria-expanded`、展开时挂载）；§4.2、§8.2、§9 同步<br>② `SubjectDetailPage.tsx` 删除「当前结果」后的独立 `<TrendBoard />`，改为在「状态概览」section 内、dashboard 条件块之后渲染，dashboard 失败时趋势区仍可用；顶部描述改为「心理状态趋势（并入状态概览）」<br>③ `TrendBoard.tsx` 根节点改为无标题的 `div.trendBlock`（仅上分隔线），新增 `openCharts` 受控状态（四键默认 false，切换区间不重置）；`ChartCard` 替换为 `ChartCollapsible`<br>④ 新建 `ChartCollapsible.tsx`：按钮+chevron、`aria-controls`、面板仅展开挂载、180ms 入场动画、`prefers-reduced-motion` 降级；加载骨架改为「汇总骨架 + 4 个按钮同高占位条」 |
| 完成状态 | 已完成。`npm run typecheck`、`npm run build` 通过；浏览器实测：页面无「心理状态分析看板」文本，四个按钮位于「状态概览」内且默认全部收起；点击 Russell 展开出完整散点图（坐标轴/象限/彩色点），再次点击收起；展开状态切换「近 7 天」并查询后仍保持展开；无横向滚动、无红色报错 |
| 影响范围 | `docs/contracts/ui.md`；`web/src/admin/SubjectDetail/SubjectDetailPage.tsx`、`TrendBoard/{TrendBoard.tsx,TrendBoard.module.css,ChartCollapsible.tsx}`。未改四个图表组件、`TrendStrip`、`app/`、`api/`、`mock/`、`tests/` |
| 后续待办 | 折叠状态仅存在内存，刷新页面后回到全收起；如需记住用户偏好再评估是否落 `localStorage`（当前契约禁止写入） |
| 备注 | 日期区间条、汇总与心理提示卡常驻不折叠；四图的数据、证据深链、空态、配色与免责声明均未改变 |

### 2.9 进度记录：P19 五色热力图改为横向折行布局

| 项 | 内容 |
|---|---|
| 完成时间 | 2026-11-25（Asia/Shanghai） |
| 变更内容 | ① `ui.md` 新增补记 13 与 §9 验收项：热力图由「周为列 / 星期为行」改为按日期升序从左到右、容器不足自动折行，移除横向滚动<br>② `ColorCalendarHeatmap.tsx` 删除 `calendarWeeks` / `WEEKDAY_LABELS` 与周列矩阵，改为遍历升序 `orderedDays`；每格为 `div.calendarDayCell`（色块按钮 + `MM-DD` 标签），按钮的 `aria-label` / `aria-pressed` / `title` / 点击与聚焦逻辑原样保留<br>③ `TrendBoard.module.css` 新增 `.calendarDayList`（flex + wrap + gap 6px）、`.calendarDayCell`（40px，≤480px 时 34px / gap 4px）、`.calendarDateLabel`，删除 `.calendarScroll` / `.calendarGrid` / `.calendarRowGroup` / `.weekdayLabel` / `.calendarBlank`<br>④ 组标签与图注同步为横向排列与折行说明 |
| 完成状态 | 已完成。`npm run typecheck`、`npm run build` 通过；浏览器实测（553px 视口）：14 格按日期升序排列，首格 11-12、末格 11-25，折行为 8+6 两行；点击 11-14 显示「蓝色」、11-17 显示「橙色」；无横向滚动、无红色报错 |
| 影响范围 | `docs/contracts/ui.md`；`web/src/admin/SubjectDetail/TrendBoard/{ColorCalendarHeatmap.tsx,TrendBoard.module.css}`。未改 `dateUtils.ts`、`TrendBoard.tsx`、其他图表、`api/`、`mock/`、`app/`、`tests/` |
| 后续待办 | 常见桌面宽度可单行完整展示；窄屏按 2–3 行折行。若后续区间扩大到 30/90 天，可评估按月分组或固定高度滚动，避免行数过多 |
| 备注 | 五色映射、无复盘中性灰、选中描边、键盘聚焦、详情面板、证据深链（`/admin/reviews/:reviewId`）与图例均未改变 |

### 2.10 进度记录：P20 AI 援助接入 DeepSeek 联网搜索

| 项 | 内容 |
|---|---|
| 完成时间 | 2026-11-25（Asia/Shanghai） |
| 变更内容 | ① `api.md` 新增 §7.19（status）与 §7.20（chat SSE）、§5.3/§6/§8/变更记录；`db.md` §6.1 新增 `ai_assist.chat`；`ui.md` 新增补记 14 与 §3.5 AI 援助页<br>② 后端新增 `app/api/routers/ai_assist.py`：`deepseek-flash` + `thinking.type=disabled` + `tools:[{"type":"deepseek_web_search"}]`，**不设 `tool_choice`**；SSE `meta/delta/citation/notice/done/error`；无 Key 中性提示；工具不支持或上游失败自动降级为普通对话并提示「本次回答未启用联网搜索」；不建表、不存对话，仅写 `audit_logs(ai_assist.chat)` 元数据；`requirements.txt` 仅新增 `httpx`<br>③ 前端新增 `/ai-aid` 独立页（`AiAssistPage`）、SSE 解析（`aiAssist.ts`）与逐字渲染：2 条引导、2000 字计数、Enter 发送 / Shift+Enter 换行、停止/重试/清空、引用外链、每条 AI 消息固定免责声明、页头第三方处理提示；`/pending?feature=ai-aid` 重定向；`/capture` 卡片直达；无 `localStorage` / `sessionStorage` / `dangerouslySetInnerHTML` |
| 完成状态 | 已完成。`pytest tests -q` → 317 passed（新增 16）；`npm run typecheck` / `npm run build` 通过；浏览器实测 `/ai-aid` 未开通态：标题与说明、中性提示、输入/发送禁用、无红色报错；`/pending?feature=ai-aid` 正确跳转；隐私审查无阻断项。2026-11-25 使用真实 Key 联调：`status` 返回 `enabled=true / web_search=true / model=deepseek-flash`，单轮 154 个 `delta`、正常 `done`、无降级；前端真实 API 模式端到端问答通过，回复下方免责声明正常，审计仅元数据 |
| 影响范围 | `docs/contracts/{api,ui,db}.md`、`README.md`、`.env.example`；`app/api/routers/ai_assist.py`、`app/api/{main,schemas}.py`、`app/db/constants.py`、`requirements.txt`、`tests/test_api/test_ai_assist.py`；`web/src/user/AiAssist/*`、`web/src/api/{aiAssist.ts,types.ts,mock.ts}`、`web/src/App.tsx`、`CaptureTasksPage.tsx`、`ComingSoonPage.tsx`。未改其他业务模块 |
| 后续待办 | 真实上游已验证（`deepseek_web_search` 声明被接受、无降级）；Key 当前仅注入后端进程内存，重启需重新注入，持久化建议由用户通过 `setx` 或密钥管理工具完成；建议补用户级限流、`subject_id` 与 token 绑定、撤回同意后的停用策略；mock 模式固定未开通，不生成模拟回答 |
| 备注 | 对话不留存：不写 SQLite 业务表、文件与浏览器存储；审计仅 `{model, web_search, turns, status, degraded}`，日志不记录请求体/响应体/异常原文/Key |

## 3. 已完成功能模块与交付物

| 对象 | 状态 | 标签 / 提交 |
|---|---|---|
| 契约文档 capture@1.2 / grading@1.2 / ui@1.2 | 已冻结 | `contracts-v1.2` → `8698a26` |
| 契约文档 db@1.3 + api@1.3 | 已冻结 | `contracts-v1.3` → `ddd4968` |
| 契约文档 db@1.4 + api@1.4 | 已冻结 | 无独立标签，随 `96aa098` |
| `app/capture/` 采集模块（抓拍 / 人脸检测裁剪 / 录音 / 会话打包） | 已实现，已封存 | `capture-v1` → `55c9a25` |
| `tests/test_capture/`（6 条，全部 mock 设备） | 全绿 | 包含在 `787ee0e` |
| `scripts/verify_capture.py`、`scripts/hw_check.py` | 已实现 | 包含在 `55c9a25` |
| 真实硬件端到端验证 | 已通过 | `ok` / `both` 一次；另有 `no_audio`、`no_face_no_audio` 历史结果 |
| `app/db/` 五张表 + 派生 `coverage` + 服务端默认值 | 已实现 | `db-v1` → `bc83a3e` |
| `app/api/` 骨架（信封 / 鉴权 / 异步采集 / 2001/2003） | 已实现 | `api-v1` → `79e582d` |
| 契约文档 api@1.5（用户端 / consent / 会话归属） | 已冻结 | `4f5d1bf` |
| `app/api/` 用户端端点、consent 三闸、会话归属校验 | 已实现 | `4f5d1bf` |
| `app/analysis/` 四路 mock、Schema 校验、一致性判定 | 已实现（未打标签） | `81a8499` |
| `tests/test_analysis/`（69 条） | 全绿 | `81a8499`、`fa5a0d7` |
| SenseVoice ASR Provider（真实 API + 120s 超时 + Mock 回退） | 已实现 | `fa5a0d7` |
| `app/grading/` 五色规则、七日趋势偏移、合成封顶、复核任务草案 | 已实现并接入 API（未打标签） | `67adee6`、`1d3fb0e` |
| `tests/test_grading/`（108 条） | 全绿 | `67adee6`、`1d3fb0e` |
| `web/` 用户端 3 页 + 管理端 4 页骨架（mock 联调） | 已实现 | `601d33d` |
| consent 一次性授权改版（去保存期限、`retention_days` 可选缺省 180） | 已实现 | `fa5a0d7`、`8013d4e` |
| 双模块：用户端 `/capture` 选择页 + `/capture/checkin`（face_only）+ `/capture/report` | 已实现 | `fa5a0d7`、`8013d4e` |
| 双模块后端：`sessions.kind`、频率字段、`GET /api/user/tasks`、`PATCH .../frequency`、逾期 P0 复核任务（惰性幂等） | 已实现 | `fa5a0d7` |
| 管理端：频率编辑、最近签到/汇报时间、红色「危机·逾期」徽标、逾期复核任务中文展示 | 已实现 | `8013d4e` |
| 思想汇报手动录音：`stop_event` 采集模式 + `POST /api/sessions/{id}/stop` + 前端正计时无自动终止 | 已实现 | `fa5a0d7`、`8013d4e` |
| analyze 正式接入 + 复盘 / 复核任务 / 看板端点 | 已实现 | `c46536e` |
| `map_risk_level` wiring + 低一致性 P0 修复 | 已实现 | `c46536e`、`1d3fb0e` |
| 用户端同意提交后直达 `/capture`，移除中间引导步骤 | 已实现（P11） | 本次提交 |
| 用户端登录页 `/login`（用户名 / 密码 / 统一知情同意，演示账号 张三 / 123456） | 已实现（P12） | 本次提交 |
| 独立知情同意页 `/consent` 合并进登录页，旧地址仅跳转 | 已实现（P12） | 本次提交 |
| 思想汇报同步：`sensevoice_syncs` 表 + 迁移 + 同步/列表/详情三个管理端端点（默认关闭、失败回滚、读取留痕） | 已实现（P13） | 本次提交 |
| 思想汇报同步适配层：严格 ASR + 情绪映射（emotion@1.0，无 Mock 回退） | 已实现（P13） | 本次提交 |
| 管理端对象详情「思想汇报同步」面板 + 13 条契约测试 | 已实现（P13） | 本次提交 |
| `/capture` 新增「AI援助」「教育学习」入口 + `/pending` 功能待开发占位页（**暂无后端支持**） | 已实现（P11） | 本次提交 |
| 管理端对象列表姓名跳转详情 + 基础档案字段（性别/年龄/身份证号/住址等） | 已实现（P14，Mock） | 本次提交 |
| 对象详情按日期筛选打卡影像与思想汇报录音（在线预览/播放，敏感面板默认折叠） | 已实现（P14，Mock 媒体） | 本次提交 |
| 状态看板内容合并进对象详情、删除独立看板页面与导航；旧地址重定向对象列表 | 已实现（P14） | 本次提交 |
| 心理状态趋势聚合 API `GET /api/admin/subjects/{id}/trends`（任意区间、逐日补齐、多维指标、9 个信号码、无新增表） | 已实现（P16） | 本次提交 |
| 管理端对象详情「心理状态分析看板」：区间条 + Russell 散点 + 五色热力图 + 稳定性柱状 + 依从性日历（Recharts） | 已实现（P16，mock 联调） | 本次提交 |
| `scripts/seed_demo.py` S001 连续 14 天波动种子（含降级/低一致性/冲突/逾期） | 已实现（P16） | 本次提交 |
| 复盘详情页 `/admin/reviews/:reviewId`（只读：结论、规则中文、证据链） | 已实现（P17） | 本次提交 |
| 看板散点/热力块证据入口按 `review_id` 直达单条复盘；缺 `review_id` 仅中性说明 | 已实现（P17） | 本次提交 |
| 心理状态趋势并入「状态概览」，移除独立看板入口/容器 | 已实现（P18） | 本次提交 |
| 四个图表封装为可折叠按钮，默认收起、独立展开/收起（`ChartCollapsible`） | 已实现（P18） | 本次提交 |
| 五色热力图改为按日期从左到右、窄屏自动折行（移除周列矩阵与横向滚动） | 已实现（P19） | 本次提交 |
| AI 援助 `/ai-aid`：DeepSeek `deepseek-flash` + `deepseek_web_search`，SSE 流式、降级提示、审计元数据 | 已实现（P20） | 本次提交 |
| AI 援助对话零留存：不建表、不写业务表/文件/浏览器存储，仅 `audit_logs(ai_assist.chat)` | 已实现（P20） | 本次提交 |
| 远程仓库 | `main` 与 `origin/main` 同步 | `origin/main` @ `4c38d5d` |
| `scripts/seed_demo.py` 演示数据（含占位素材） | 已实现 | `0bb78b5` |
| QA 核验 + M1–M4/L4/L8 修复 | 已完成 | `638245e`（报告）、`7732930`（修复） |

提交历史（近 20 条，倒序；完整记录见 `git log`）：

```
5eef4bb  docs: sync contracts for grading integration and consent alignment
c46536e  feat(api): integrate analysis, grading, reviews, tickets and dashboard
1d3fb0e  fix(grading): force P0 for low-consistency manual review
7782e65  docs(progress): mark grading commits pushed (origin/main @ 337fdb9)
601d33d  feat(web): scaffold user and admin frontend with mock data and routing
337fdb9  docs(grading): sync contract with implementation (review_reason, map_risk_level, cap semantics)
67adee6  feat(grading): implement 5-color rules, trend analysis and ticket builder
4f5d1bf  feat(api): user endpoints, consent gates, session ownership (api@1.5)
9c1386e  docs: refresh PROGRESS for analysis and api@1.5
81a8499  feat(analysis): deterministic four-channel mock pipeline + schema/consistency
9b2a04d  docs: refresh PROGRESS snapshot; fix agents README (5 tables, /api/sessions, tests/test_db)
43d3aba  chore(agents): align analysis/grading instructions with contracts
7732930  fix(qa): M1-M4/L4/L8 - pin SQLAlchemy<2.1, FK test pragma, safe logs, injectable session factory
638245e  docs: QA report 2026-11-24 + db coverage derived note + window_days default
0bb78b5  chore(seed): demo dataset (6 subjects, 42 sessions, 6 reviews, 3 tickets) + placeholder assets
79e582d  feat(api): skeleton with async capture, envelope, auth, degraded                    [api-v1]
96aa098  docs+db: contracts db@1.4/api@1.4, JSON NULL checks, 2003 branch
bc83a3e  feat(db): five tables + derived coverage + server defaults; docs db@1.3              [db-v1]
ddd4968  docs: contracts v1.3 (db defaults + reviews window unique + api created gate)       [contracts-v1.3]
492c764  docs: add PROGRESS snapshot (repo-state based)
55c9a25  feat(capture): verified on real hardware (ok/both); prefer DirectShow, 16k audio    [capture-v1]
787ee0e  feat(capture): align to contract state machine (coverage/warnings/optional crop) + tests
```

**尚未实现**：复盘列表 `GET /api/admin/reviews`、60 秒频控（`1006`）、转写查看。`web/` 骨架已实现（`601d33d`）；`app/api/` 的 analyze / review / tickets / dashboard / subjects 详情已接入（`c46536e`，增量已提交）；`app/capture/` 已封存，`app/db/`、`app/api/`、`app/analysis/` mock 与 `app/grading/` 分级规则均已实现。

采集模块已落地的契约要点：

- 六值 `capture_status`：`ok` / `partial` / `no_face` / `no_audio` / `no_face_no_audio` / `error`；
- `coverage`：`both` / `face_only` / `audio_only`，失败态为 `null`；
- `meta.warnings[]` 承载非致命原因，`meta.error` 仅在 `error` 时非空；
- 人脸检测顺序 MediaPipe → OpenCV DNN → Haar；裁剪外扩 25%、JPEG 质量 85；
- 目录固定为 `storage/subjects/{subject_id}/sessions/{session_id}/`，原始帧不落盘。

数据层、分析层与 API 已落地的要点：

- 五张表：`subjects` / `sessions` / `reviews` / `review_tickets` / `audit_logs`，字段、CHECK、索引与 db@1.4 一致；
- `sessions.coverage` 为派生属性，不落列；`analysis_status`、`gender`、`status`、`window_days` 有服务端默认值；
- `reviews` 唯一约束 `UNIQUE(subject_id, window_end)`；JSON 列统一 `IS NULL OR json_valid(...)`；
- 统一信封 `{code, message, data, degraded, request_id}`，业务错误一律 HTTP 200，未捕获异常 HTTP 500 + `code=5000`；
- 已实现：`GET /api/health`、`POST/GET /api/sessions`、`GET /api/admin/subjects|sessions`、`GET /api/admin/sessions/{id}/face`（写 `audit_logs`）；
- 已实现用户端：`GET/PUT /api/user/consent`、`POST /api/user/consent/revoke`、`GET /api/user/sessions/{id}/feedback`；`POST /api/sessions` 前置 consent 三闸（`consent_revoked` → `consent_required` → `consent_incomplete`）；
- 会话归属校验：`subject` 调用 `GET /api/sessions/{id}` 与 feedback 时必须带 `subject_id`，缺失 `1001`、不匹配 `1003`；
- `POST /api/sessions/{id}/analyze` 已正式接入（`c46536e`）：`captured` 跑四路分析并落 `analysis_json` / `transcript_path` / `analysis_status`，再按自然日窗口生成 `reviews` / `review_tickets`；分析彻底失败 `2003` 且不改 `sessions.status`；重复调用幂等；
- 新增管理端端点（`c46536e`）：`POST /api/admin/reviews`（0 可用会话 → `1005 no_session_in_window`）、`GET /api/admin/reviews/{id}`、`GET /api/admin/tickets`、`GET /api/admin/tickets/{id}`（写 `sensitive.view`）、`POST /api/admin/tickets/{id}/transition`、`GET /api/admin/dashboard`（`subject_id` 可选，缺省取最近采集对象）。

分析模块（`app/analysis/`，mock 为主、ASR 与语音情绪已接真实）已落地的要点：

- 四路 Provider：`mock-asr@1.0` / `mock-emotion@1.0` / `mock-face@1.0` / `mock-psych@1.0`，场景 `normal` / `negative` / `crisis` / `conflict` 确定性输出（现况：`asr` 已接 `sensevoice-asr@1.0`，`emotion` 已接 `sensevoice-emotion@1.0`，`face` / `psych` 仍为 mock）；
- ASR 生成会话内 `transcript.txt`，结果只存规范相对路径，不返回原文；
- 运行状态与结果分离：`AnalysisRunResult.analysis_status` 为 `done/degraded/failed`，纯 `AnalysisResult` 不含该字段；
- 通道级与完整 JSON Schema 校验（Draft 2020-12 + `FormatChecker`），失败不得进入 grading；
- 单路 `unavailable` → `skipped`，单路异常或非法输出 → `degraded`，互不影响；ASR 失败时 psych 为 `skipped`；四路均无可用输出 → `failed` 且 `result=None`；
- 一致性：单模态、`partial`（即使 `coverage=both`）、方向冲突、低置信均强制 `low + needs_review=true`；`degraded` 时最高 `medium`。

分级模块（`app/grading/`，纯函数，不读写库/文件/网络）已落地的要点：

- 目录结构按 grading@1.2 契约：`config` / `models` / `single` / `trend` / `compose` / `ticket`，编排顺序 `evaluate_session → evaluate_period → compose → build_ticket`；
- 单次规则：`R_SINGLE_RED`（`intent_flag=suicide_intent` 直接红；`self_harm_mention` 且 `signal_strength>=80` 红，红不受一致性封顶）、`R_SINGLE_ORANGE`（`signal>=70` 且非自杀意图，附 emotion/face 辅助佐证证据）；
- 趋势规则：`offset_score=(window_mean - baseline_mean)/max(std, BASELINE_MIN_STD)`，`R_TREND_YELLOW/BLUE/GREEN` 边界 `1.5/0.8`，基线或窗口不足走 `R_BASELINE_INSUFFICIENT` 判蓝并在证据标 `insufficient`、`offset_score` 置 0；窗口按自然日可跨月；
- 合成：取大 → `R_CONSISTENCY_CAP`（low 封顶橙，红豁免；**绿+low 抬至橙**强制复核）→ `manual_review` → `R_DEGRADED_REVIEW` 标 `needs_review`（不改色）；
- 复核任务草案：`build_ticket` 只返回 dict（无 DB/通知/处置动作）；绿且不复核抛 `ticket_not_allowed_for_green`；色码→`priority`/`suggested_method`，`due_at` 按 P0/P1/P2 加 24/72/168h，幂等；`manual_review=true`（低一致性）覆写 `priority=P0`、方法按最终色；`capture_degraded` 覆写 P0 + `recapture`；
- 历史遗留 `risk_level` 映射：`config.map_risk_level(text_valence, intent_flag)` 先按 `text_valence` 分段（`[-0.8,-0.5,-0.2,0.0]`→crisis/high/elevated/watch/none），`intent_flag∈{suicide_intent,self_harm_mention}` 强制覆写 `crisis`；**已 wiring 进 `app/analysis/pipeline.py`**（`c46536e`，`pending` 占位已删除）；
- 阈值唯一来源 `config.py`（15 项均标 `# TODO: 待标定`），`tests/test_grading/test_config.py` 源码扫描保证规则模块无字面量泄漏。

## 4. 关键决策与理由

| 决策 | 落地位置 | 理由 |
|---|---|---|
| **DirectShow 优先**（Windows 下先 `cv2.CAP_DSHOW`，失败回退默认后端） | `app/capture/camera.py`，提交 `55c9a25` | 本机实测：默认 MSMF 帧连续多次检不出人脸，同一设备 DSHOW 帧可检出；回退设计保证非 Windows 与打不开场景行为不变 |
| **裁剪输出固定 300×300**（`OUTPUT_SIDE = 300`） | [config.py](../app/capture/config.py#L61)、capture@1.2 §5.1 | 统一下游输入尺寸；`meta.face.output_size` 恒为 `[300, 300]` |
| **音频 16 kHz / 单声道 / 16-bit** | [audio.py](../app/capture/audio.py#L22-L27)、architecture §存储 | 语音链路足够、体积小；`speech_ratio` 阈值 0.05 |
| **error 判级规则** | capture@1.2 §3 | 零产物 + 设备/技术级 code → `error`；零产物 + 全业务级 code → `no_face_no_audio`；任一路有产物 → `partial` 或单模态 |
| **`sessions.status` 与 `analysis_status` 拆分** | db@1.2 §3.1 | `status` 只反映采集；分析状态独立，分析失败不回写 `failed` |
| **`degraded` 为字符串数组** | api@1.2 §7.2 | 区分采集与分析降级；新增 `2003`，废弃 `2002` |
| **原型阶段手工迁移，不引 Alembic** | db@1.3 头部 / §9、[migrations/README](../app/db/migrations/README.md) | 当前只有空库初始化；正式部署前再引入 Alembic，避免过早引入迁移工具 |
| **`coverage` 派生、不落列** | db@1.4 §3、[models.py](../app/db/models.py) | 避免路径与字段双写不一致；唯一来源是 `face_path` / `audio_path` |
| **JSON 列允许 NULL，但非 NULL 必须合法** | db@1.4 §4、提交 `96aa098` | `json_valid(NULL)` 返回 NULL 会误伤可空列，改为 `IS NULL OR json_valid(...)` |
| **`reviews` 窗口唯一** | db@1.4 §4 | 防止同一复盘窗口重复生成，幂等重跑更安全 |
| **服务端默认值下沉到 DDL** | db@1.4 §3/§4、`models.py` | `analysis_status=pending`、`gender=unknown`、`status=active`、`window_days=7`，非 ORM 写入也成立 |
| **统一信封 + `request_id`** | api@1.4 §2、[errors.py](../app/api/errors.py)、[main.py](../app/api/main.py) | 中间件生成 uuid4，写 `X-Request-Id`、日志与 `audit_logs`；便于串联一次请求 |
| **异常日志不写异常原文** | api@1.4 §2、[errors.py](../app/api/errors.py) | 只记 `request_id/exception_type/endpoint`，避免绝对路径或 SQL 参数进日志；`DEBUG=1` 才把堆栈打到 stdout |
| **后台采集可注入 + `CAPTURE_FAKE`** | [sessions.py](../app/api/routers/sessions.py)、[deps.py](../app/api/deps.py) | 测试不触真实摄像头；session factory 可替换，后台任务可观测 |
| **SQLAlchemy 临时锁 `<2.1`** | [requirements.txt](../requirements.txt)、[migrations/README](../app/db/migrations/README.md) | 2.1.x 开启外键时多表同事务 flush 顺序错误（QA M1）；seed 的逐表 flush 作为双保险 |
| **分析默认 mock Provider，ASR/情绪可选真实 SenseVoice** | [prd.md](./prd.md#L33)、[sensevoice_asr.py](../app/analysis/providers/sensevoice_asr.py) | 原型阶段先跑通链路与契约；`SENSEVOICE_API_URL`/`SENSEVOICE_API_KEY` 齐备时 ASR 走真实 API、emotion 复用其情绪标签，face/psych 仍 mock |
| **emotion 复用 ASR 情绪标签（零额外请求）** | [sensevoice_asr.py](../app/analysis/providers/sensevoice_asr.py) `_parse_emotion`、[sensevoice_emotion.py](../app/analysis/providers/sensevoice_emotion.py)、[pipeline.py](../app/analysis/pipeline.py) | 从 `<|NEUTRAL|>` 等标签映射 `valence/arousal/label`；ASR Provider 经 `last_emotion` 交给 emotion 通道，不重复调用云端；标签缺失时标 `degraded` 并保留 mock 数值，避免占位值被当成真实情绪 |
| **SenseVoice 失败回退 Mock + degraded** | [sensevoice_asr.py](../app/analysis/providers/sensevoice_asr.py)、[providers/__init__.py](../app/analysis/providers/__init__.py) | 默认 120s 超时（`SENSEVOICE_TIMEOUT_SEC` 可覆盖）；超时/4xx/5xx/解析失败一律回退 Mock 并标 `degraded / sensevoice_fallback`，管线不中断；ASR 非 ok 时 psych 按既有契约 `skipped/asr_unavailable`，emotion 因无标签复用标 `degraded / sensevoice_emotion_unavailable` |
| **运行时只读 `os.environ`，不自动加载 `.env`** | [sensevoice_asr.py](../app/analysis/providers/sensevoice_asr.py)、[tests/test_analysis/conftest.py](../tests/test_analysis/conftest.py) | 仓库无 dotenv 依赖；避免测试误读真实 Key 触网；测试以 autouse fixture 清 env，HTTP 全部 mock 拦截 |
| **分析运行状态与结果分离** | [models.py](../app/analysis/models.py)、[pipeline.py](../app/analysis/pipeline.py) | `AnalysisResult` 严格对齐 schema；`done/degraded/failed` 放在独立包装层，失败不产出可进入 grading 的结果 |
| **`risk_level` 映射落在 grading config 并已 wiring** | [config.py](../app/grading/config.py) `map_risk_level`、[pipeline.py](../app/analysis/pipeline.py) | 按 `text_valence` 分段 + 明确意图覆写 `crisis`；`c46536e` 删除 `pending` 占位，pipeline 直接调用 `map_risk_level` |
| **一致性阈值权威值在 grading** | [config.py](../app/grading/config.py) `CONSISTENCY_MIN_CONFIDENCE` | grading 侧已定义 0.6；`app/analysis/config.py` 仍用本地常量，迁移时机待定 |
| **分级为纯函数、只出口复核任务草案** | `app/grading/*`（`build_ticket` 只返回 dict） | 不读写库/文件/网络，不产生处置动作；色码不进入用户端路径 |
| **`review_reason` 承载规则 8 覆写** | [models.py](../app/grading/models.py)、[ticket.py](../app/grading/ticket.py) | `compose` 签名不增参；`AnalysisResult` 不含 `capture_status`，由 backend 用 `replace(..., review_reason="capture_degraded")` 覆写后建 P0+recapture 单 |
| **低一致性 P0 由 `manual_review` 驱动** | [ticket.py](../app/grading/ticket.py) | 规则 5 与色码无关；`review_reason="consistency_conflict"` 只描述原因，不改档位 |
| **复盘窗口按自然日、DB 存 `YYYY-MM-DD`** | [integration.py](../app/api/integration.py)、db@1.4 §4 | 与 grading 证据 `window` 一致；同日多会话共用一个 `window_end`，靠 `UNIQUE(subject_id, window_end)` 幂等 |
| **0 可用会话在上游拦截** | [admin.py](../app/api/routers/admin.py) `POST /api/admin/reviews` | 「可用会话」= `captured` + `analysis_status∈{done,degraded}`；0 条直接 `1005`，不落库、不生成任务 |
| **analyze 同步完成分析 + 分级** | [sessions.py](../app/api/routers/sessions.py)、[integration.py](../app/api/integration.py) | 原型阶段 mock 分析耗时可接受；省去后台任务与轮询复杂度，失败只用 `analysis_status=failed` 表达 |
| **consent 一次性授权、不展示保存期限** | ui@1.2 §3.1 补记 2 / 补记 7、api@1.5 §7.1.2、[LoginPage.tsx](../web/src/user/Login/LoginPage.tsx)、[schemas.py](../app/api/schemas.py) | 进入用户端首次授权后，有效期内再采集不再重复询问，撤回后才需重新授权；P12 起面部与语音合并为**单一统一勾选**一次提交；`retention_days` 改可选、缺省 180，仅用于留存管理，用户端不展示不填写 |
| **签到 face_only 属正常形态，豁免单模态强制规则** | grading@1.2 补记·三、capture@1.2 补记、[pipeline.py](../app/analysis/pipeline.py)、[consistency.py](../app/analysis/consistency.py) | checkin 的 asr/emotion/psych skipped 不计降级；单 face 通道 consistency 中性 medium；不强制 P0/recapture；`map_risk_level(0.0,"none")`；no_face/error 仍按异常 |
| **逾期 = P0 复核任务 + 管理端危机标记** | api@1.5 补记·二、[integration.py](../app/api/integration.py) | 频率按对象配置（签到默认 1 天、汇报默认 3 天）；管理端读取时惰性判定并幂等生成任务（`talk_to_staff`、`detail_json.overdue_kind/overdue_days`、初始 `pending`）；不改会话状态、不触发分析；用户端仅中性提示 |
| **思想汇报录音完全手动控制** | capture@1.2 补记·二、api@1.5 补记·三、ui@1.2 补记 4、[CapturePage.tsx](../web/src/user/Capture/CapturePage.tsx) | 不传 `duration_sec` = 手动模式；100ms 分块录音直到 `stop_event.set()`；无倒计时、无自动终止；stop 幂等且不落库；录音中不轮询（消除「倒计时未完但提前结束」的界面假象）；保存/上传/反馈逻辑不变 |

## 5. 待办任务与未完成项

**未完成（按目录）**

| 目录 | 内容 | 状态 |
|---|---|---|
| `app/analysis/` | 四路 Provider、Schema 校验、一致性判定 | 已实现；ASR 已接 SenseVoice（`fa5a0d7`），emotion 复用 ASR 情绪标签接入（`sensevoice-emotion@1.0`），face/psych 仍为 mock；`risk_level` 已 wiring `map_risk_level`（`c46536e`） |
| `app/grading/` | 五色规则、七日趋势偏移、合成封顶、复核任务草案 | 已实现并接入 API（`c46536e`）；低一致性 P0 已补 |
| `app/api/` | analyze / reviews / tickets / dashboard | 已接入（`c46536e`）；余项见下 |
| `web/` | 用户端页面 + 管理端列表/详情/复核任务 | 骨架已实现（`601d33d`），双模块与手动录音已落地（`8013d4e`）；P11 新增两个占位入口、P12 登录页、P13 同步面板、P14 详情档案/媒体/看板合并已提交；P15 本地化与术语统一在工作区；待与真实 API 联调 |
| `web/` · 新增入口后端 | AI援助 / 教育学习 | **未开始**：无接口、无表、无业务逻辑，仅前端占位 |

**API 剩余延期项**

- 复盘列表 `GET /api/admin/reviews`；
- `GET /api/admin/sessions/{id}/transcript`（管理端敏感面板）；
- （`GET /api/admin/subjects/{subject_id}` 已随双模块实现，`fa5a0d7`）
- `AI援助` / `教育学习` 的接口与数据表（P11 仅前端占位，后端未排期）
- 60 秒重复建会话频控（`1006`）；
- `capture_busy` 专用业务码（当前复用 `code=5000`）；
- 对象档案字段端点/字段定义（性别、年龄、身份证号、住址等，P14 仅前端 mock）；
- 对象按日媒体端点 `GET /api/admin/subjects/{id}/media`（P14 仅前端 mock，缺鉴权/留存/留痕定义）；
- 单对象看板变体语义（P14 以 `GET /api/admin/dashboard?subject_id=` mock 变体模拟）。

已补齐（`4f5d1bf`）：`/api/user/*` 全部端点、`POST /api/sessions` 的 consent 三闸、`subject` 会话归属校验。

**演示数据说明**

- `scripts/seed_demo.py` 生成 **6 subjects / 59 sessions / 20 reviews / 3 tickets / 4 audit_logs**，颜色合计（5 绿、5 蓝、5 黄、4 橙、1 红）与复核任务均为**手工指定**，未调用 `app/grading/`，脚本内无阈值判断；
- P16 起 **S001（张三）为连续 14 天波动窗口**：每日 1 签到 + 1 汇报（缺 2 天签到、1 天汇报制造逾期）、每日 1 条复盘（`green,green,blue,yellow,yellow,orange,blue,green,blue,yellow,orange,orange,yellow,blue`），并含 2 天 `degraded`、2 天 `low`（1 天 `conflict`）；其余 5 个对象维持原有单条复盘形态；
- `face.jpg` 为 300×300 灰底 + 几何剪影 + `placeholder` 的占位素材，`transcript.txt` 为一行占位文本；二者非真实采集，不得用于效果评估或对外宣称；
- 既有个别真实采集产物（`storage/subjects/3b1e7c90-...`）保留，seed 不覆盖已存在文件。

**阻塞 / 风险**

1. **本机 SQLAlchemy 仍是 2.1.9**：`requirements` 已锁 `<2.1`，但环境未重装；约束测试通过显式 `codes` 绕开其 `RETURNING` 包装差异，重装后应消失。
2. **`CAPTURE_FAKE` 无环境守卫**：生产误设会跳过真实采集（只写路径、不落文件），后续应限定 `APP_ENV != production`。
3. **`window_days` 默认值只影响新建表**：reviews 端点落地前需重建 `storage/app.db`（当前库已按 db@1.4 重建过一次）。
4. **500 响应缺 CORS 头**：未捕获异常由最外层 `ServerErrorMiddleware` 处理，浏览器跨域读不到该信封；`X-Request-Id` 与 `request_id` 仍在。
5. **麦克风音量**：本机默认输入曾长期近乎静音（峰值 7/32768、`speech_ratio=0`），最后一次正式验证为 `ok`（`speech_ratio=0.3153`），现场部署前需复核设备与增益。
6. **face/psych 真模型未接**：仍为确定性 mock。ASR 已接 SenseVoice、emotion 已复用其情绪标签（`sensevoice-emotion@1.0`，标记缺失时 `degraded` + `sensevoice_emotion_unavailable`）；face/psych 的 Provider 选型与降级策略待确认（真实 URL/Key 在本机 `.env`，运行时需注入 `os.environ`）。
7. **`risk_level` 已 wiring**：`generate_overall_risk_level(text_valence, intent_flag)` 直接返回 `map_risk_level`；阈值仍全部 `# TODO: 待标定`，正式上线前需业务确认。
8. **部署需安装新依赖**：`requirements.txt` 已加入 `jsonschema[format]>=4.23,<5`，本地已安装，其他环境需重新安装。
9. **文档漂移**：[architecture.md](./architecture.md#L53) 的存储路径仍是 `storage/{subject_id}/{session_id}/`，与 capture@1.2 不一致。
10. **`capture_busy` 暂复用 `code=5000`**（`message=capture_busy`），尚无专用业务码。
11. **契约已同步（2026-11-24）**：`grading.md` 补记规则 5 P0、复盘前提、复核任务主键归属与覆写顺序；`api.md` 补记 analyze / reviews / tickets / dashboard、窗口 `YYYY-MM-DD`、`1005 no_session_in_window`、consent 强校验；`ui.md` §3.1 统一两项齐备；`db.md` 补窗口格式与 0 会话不落库。版本号均保持不变（附加、非破坏）。同日追加：`ui.md` 补记 2（一次性授权、去保存期限）、`api.md` §7.1.2 `retention_days` 可选缺省 180；双模块追加 `ui.md` 补记 3、`api.md` 补记·二、`grading.md` 补记·三、`capture.md` 补记（face_only）、`db.md` 补记（kind/频率/`review_id` 可空/`detail_json`/`talk_to_staff`/`frequency.update`）、`analysis.schema.json` degraded 描述 checkin 例外（已提交）。
12. **管理端前端仍用 mock**：`web/src/api/*` 已声明端点，但管理端页面尚未切真实 API（P14 的档案与媒体也仅 mock）；用户端 consent 已完成两项齐备门禁、一次性授权与去保存期限。
13. **analyze 为同步长请求**：mock 下可接受；ASR 真实 API 超时默认 120s（`SENSEVOICE_TIMEOUT_SEC` 可覆盖，实测冷启约 20s、热调用约 3.5s），失败回退 Mock；后续接其余真模型需评估超时或改后台任务，并复用 `deps.get_session_factory()` 注入。
14. **本机库需执行双模块迁移**：`app/db/migrations/202611241200_add_dual_module_tasks.py`（`python -m app.db.migrations.202611241200_add_dual_module_tasks`）；`storage/app.db` **已执行**该迁移与 P13 的 `202611251200_add_sensevoice_syncs.py`，旧库直接启动会缺 `kind`/频率列/`sensevoice_syncs` 表。
15. **手动录音未做真实设备联调**：手动闭环已由 fake + 单元测试覆盖（不自动终止、stop 后落盘）；真实麦克风长时间录音的资源占用与 stop 响应时延需现场验证。
16. **登录为开发演示账号**：`张三 / 123456` 由前端校验并写入 localStorage，密码会出现在打包产物中，**不可用于生产**；生产需接入真实认证。真实后端模式需 `VITE_USE_MOCK=0`、启动 uvicorn 并先执行 `seed_demo.py`，否则默认演示对象 S001 不存在会返回 `1004`。
17. **思想汇报同步默认关闭、无真实数据**：`SENSEVOICE_SYNC_ENABLED` 默认 `0`；`.env` 缺 `SENSEVOICE_EMOTION_API_URL`，且 SenseVoice 服务 `8.133.237.222:8000` 连接失败/超时。关闭时接口返回 `5001 sensevoice_sync_disabled` 且不落库；张三当前**没有可用汇报音频**（今日 2 秒会话未保存音频，历史 seed 行引用的 `audio.wav` 不存在）。启用前需真实录制 ≥5 秒并确认情绪接口协议。另：`data_version` 为秒级粒度，同一秒内重复同步可能生成相同版本号，语义待定义（api@1.5 仅要求不覆盖历史）。
18. **Uvicorn 需重启才能加载 P13 路由**：8000 服务未启用 `--reload`，新增端点后已手动重启；后续再改后端代码需重启。
19. **P14 档案字段无后端与脱敏定义**：性别/年龄/身份证号/住址等仅存在于前端 mock（`subject.json.profiles`），`db` / `api` 契约未定义字段与可见范围；身份证号当前明文展示，接入真实接口前必须补脱敏与权限规则。
20. **P14 媒体为演示素材**：打卡影像由文生图占位服务生成、录音为运行时构造的 2 秒静音 WAV；`GET /api/admin/subjects/{id}/media` 仅 mock 实现，鉴权、留存期与 `audit_logs` 留痕未定义；敏感面板展开只显示提示文案，未产生真实调阅记录。
21. **P14 单对象看板为 mock 变体**：详情页以 `GET /api/admin/dashboard?subject_id=` 取对象级数据，后端仅支持缺省取最近采集对象；`variants` 为前端模拟，需在契约中明确单对象语义后再联调。
22. **P16 真实库尚未执行新 seed**：扩充后的 `seed_demo.py` 已在临时库验证（59 sessions / 20 reviews），但 `storage/app.db` 未重跑，以免覆盖既有真实会话；真实模式看板目前只能呈现既有数据，需要时按「先备份、再执行、用 `(subject_id, window_end)` 幂等跳过」流程处理。
23. **P16 历史 `window_end` 格式漂移**：早期 `reviews.window_end` 存在完整 ISO 时间戳，契约要求 `YYYY-MM-DD`；趋势端点已兼容（按本地日期部分匹配），但历史数据未清洗，唯一约束在该类数据上可能出现同日多条。
24. **P16 看板为 mock 联调 + 阈值待标定**：四图在 mock 模式验证通过，真实后端联调需 `VITE_USE_MOCK=0` 且先跑 seed；`signals` 9 个阈值与四象限分界均为契约常量标注「待标定」，正式上线前需业务确认。

## 6. 下一步顺序（建议）

1. **fe-user / fe-admin**：把 `web/src/api/*` 从 mock 切到真实端点；管理端接 `tickets` / `dashboard` / `subjects` 详情与媒体（用户端 consent 门禁与一次性授权已完成）；P16 趋势看板改用 `GET /api/admin/subjects/{id}/trends` 真实接口。
2. **契约补齐（P14 前置）**：在 `db.md` / `api.md` / `ui.md` 定义对象档案字段与身份证号脱敏、`GET /api/admin/subjects/{id}/media` 的鉴权/留存/audit 留痕、单对象 dashboard 语义。
3. **backend-engineer（余项）**：60 秒频控 `1006`、`capture_busy` 专用码、`GET /api/admin/reviews` 列表、转写查看、档案字段与媒体端点。
4. **qa-guard + privacy-check**：每轮合并前跑 qa-guard；`c46536e` 新增的 analyze/reviews/tickets 端点涉及心理与复核任务数据，合并前过 privacy-check。P13 新增同步详情会读取转写原文、P14 档案与影像/录音涉敏感个人信息，合并前同样需过 privacy-check。
5. **P13 启用（待外部条件）**：SenseVoice 与情绪服务恢复 → 配置 `SENSEVOICE_EMOTION_API_URL` 与 `SENSEVOICE_SYNC_ENABLED=1` → 张三真实录制 ≥5 秒汇报 → 管理端详情页点「同步思想汇报」→ 核对转写、情绪类型/置信度/关键片段与审计日志。

## 7. 三条红线

1. **原图不落盘**：只保留裁剪后的 `face.jpg`，原始帧不落盘、不写日志、不进异常 `detail`（[prd.md](./prd.md#L82)、capture@1.2 §8.1）。
2. **分级只出口复核任务**：任何非绿结果只生成复核任务，系统不得产生限制、通报、扣分等动作（[grading.md](./grading.md#L20)）。
3. **色码只在管理端**：用户端响应与页面不出现 `final_color` 及任何色码字段，只输出行为建议（[grading.md](./grading.md#L39)、[prd.md](./prd.md#L94)）。

## 8. 目录所有权（subagent 可写范围）

| Subagent | 可写目录 |
|---|---|
| capture-engineer | `app/capture/`、`tests/test_capture/` |
| analysis-engineer | `app/analysis/`、`tests/test_analysis/` |
| grading-engineer | `app/grading/`、`tests/test_grading/` |
| backend-engineer | `app/api/`、`app/db/`、`tests/test_api/`、`tests/test_db/` |
| fe-user | `web/src/user/`（另可新增 `web/src/components/common/` 通用展示组件） |
| fe-admin | `web/src/admin/` |
| qa-guard | `tests/`、`docs/reports/` |
| privacy-check | 无（只读） |

补充：`docs/` 只允许主智能体修改；`scripts/` 归属待确认。

## 9. 环境与验证命令（当前机器）

```
Python 3.11.0rc2 · cv2 4.11.0 · numpy 1.26.4 · sounddevice 0.5.6 · mediapipe 0.10.21
SQLAlchemy 2.1.9（requirements 锁 <2.1）· FastAPI 0.165.0 · uvicorn 0.54.0 · pydantic 2.14.4 · pytest 9.2.0
jsonschema 4.26.0（含 format 校验依赖）
```

```powershell
pytest tests -q                                                      # 286 passed
python -m app.db.init                                                # 建库（幂等）
uvicorn app.api.main:app --port 8000                                 # /docs 可访问
cd web; npm run typecheck; npm run build                             # 前端类型检查与构建
python scripts\seed_demo.py                                          # 演示数据（幂等；--reset 清空后重建）
python scripts\verify_capture.py --device 0 --seconds 10             # 正式验证 → storage/subjects
python scripts\verify_capture.py --device 0 --seconds 5 --out storage/_debug   # 调试/自检
git push origin main                                                 # 远程为 ssh.github.com:443（22 端口被阻断）
```

测试构成（共 334 条）：`tests/test_capture/` 14 条（含 face_only、手动录音 stop_event 闭环与 fake 闭环）、`tests/test_db/` 21 条（含 3 条约束负例、双模块默认值/CHECK/索引/迁移回填）、`tests/test_api/` 105 条（含用户端 / consent / 归属 / 假采集 / 失败 / 并发 / 生产守卫 / analyze 接入 / 复盘 / 复核任务 / 看板 / retention 缺省 / 双模块 kind / tasks / frequency / 逾期幂等 / 序列化字段 / 手动 stop 全流程与异常分支 / P13 同步 13 条）、`tests/test_analysis/` 86 条（含场景、单模态、降级隔离、Schema、一致性、确定性与隐私、SenseVoice ASR 11 条与情绪标签 15 条 mock 拦截、checkin 预期 skipped 与一致性豁免）、`tests/test_grading/` 108 条（单次/趋势边界、封顶矩阵、取大六组合、复核任务字段与 due_at、低一致性 P0、幂等、`map_risk_level`、配置不变量）。

## 10. 待确认清单

- face/psych 的真实 Provider 选型与降级策略（ASR 已定 SenseVoice + Mock 回退；emotion 已定复用 ASR 情绪标签，不重复请求云端）；
- `map_risk_level` 的 `text_valence` 分段阈值权威来源（已定义于 `app/grading/config.py`，全部 `# TODO: 待标定`；已 wiring 进 pipeline，阈值仍待业务确认）；
- 一致性阈值从 `app/analysis/config.py` 迁到 `app/grading/config.py` 的适配时机（grading 侧已定义权威值 0.6，analysis 仍用本地常量）；
- 是否为 `app/analysis/` 打标签（如 `analysis-v1`）；
- 是否为 `app/grading/` 打标签（如 `grading-v1`）；
- `architecture.md` 存储路径是否按 capture@1.2 修订；
- `scripts/` 的目录归属；
- `capture_busy` 是否在 api@1.6 增补专用错误码；
- 正式验证用的 `subject_id` 目前是固定 UUID（`3b1e7c90-...`），是否保留为演示对象；
- 是否将本机 SQLAlchemy 重装到 `<2.1` 以彻底消除 M1 现象；
- `CAPTURE_FAKE` 是否增加 `APP_ENV != production` 守卫；
- SenseVoice 情绪分析接口协议与字段映射（思想汇报同步用的独立情绪接口仍待真实服务确认）；analysis 的 `emotion` 通道已改为复用 ASR 情绪标签（`sensevoice-emotion@1.0`），置信度为经验值 `0.75`，待业务标定；
- 对象档案字段范围与身份证号脱敏规则（是否展示完整号码、谁能查看、是否留痕）；
- 对象按日媒体端点的鉴权、留存期与 `audit_logs` 留痕口径；
- 单对象 dashboard（`subject_id` 变体）的返回语义与失败降级方式；
- `data_version` 同一秒重复同步的版本语义（复用/追加序号/毫秒）。

## 11. 文档维护约定

| 约定 | 说明 |
|---|---|
| 事实优先 | 本文只写仓库内可核实的事实（提交号、文件路径、测试输出）；推断或未定稿内容一律标「待确认」 |
| 更新时机 | 每完成一个可验证的里程碑（新增目录、接口、契约变更、标签）即更新 §2 时间线、§3 模块表与 §9 测试数 |
| 时间线追加 | 新阶段在 §2 表格末尾追加一行，保留既有行不删除，确保历史可追溯 |
| 提交追溯 | 已提交项写短哈希与标签；未提交项写「工作区」，提交后回填哈希 |
| 风险闭环 | §5 中已消解的风险移入「已消解」，不直接删除 |
| 契约联动 | 契约（`docs/contracts/*`）变更必须同步 §4 决策与 §5 风险，避免文档漂移 |
| 版本口径 | 契约版本号只增不改；实现驱动变更以「实现补记」形式附加，保持冻结语义 |
| 后续扩展位 | 如需新增章节，建议按「§12 性能与容量」「§13 部署与运维」「§14 变更日志」顺序追加，不打断现有编号 |
