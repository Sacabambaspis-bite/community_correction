# 契约 · 前端界面（ui）

| 项 | 值 |
|---|---|
| 契约版本 | `ui@1.2` |
| 所有者 | fe-user（`web/src/user/`）、fe-admin（`web/src/admin/`） |
| 依赖 | [api.md](./api.md)、[../grading.md](../grading.md)（色码唯一来源） |
| 技术栈 | React + Vite，路由用 `react-router` |

> v1.2 已冻结，后续仅接受实现驱动的变更。

> **v1.2 实现补记（2026-11-24，附加、非破坏）**：§3.1 知情同意的主按钮口径与 api@1.5 §7.2 对齐——面部与语音**两项均勾选**才允许发起采集；单项授权可提交保存，但 `POST /api/sessions` 返回 `1005 consent_incomplete`。删除「允许只勾一项」的历史表述。

> **v1.2 实现补记 2（2026-11-24，附加、非破坏）**：§3.1 调整为「进入用户端后**首次一次性授权**，授权有效期内再次采集不再重复询问，撤回后才需重新授权」；删除保存期限（`retention_days`）的页面展示与填写——期限仍由后端字段承载（api@1.5 §7.1.2 起可选、缺省 180），仅用于留存管理，用户端不得展示。

> **v1.2 实现补记 3（2026-11-24，附加、非破坏）**：用户端改双模块结构——`/capture` 变为**模块选择页**（「刷脸签到」「录音思想汇报」两卡片，各显示频率、上次完成时间与中性逾期提示），新增子页 `/capture/checkin`（face_only 签到）与 `/capture/report`（原双模态采集页，§3.2 作为其契约）；管理端对象详情新增频率编辑（§4.2），对象列表/详情/看板对逾期对象显示红色「危机·逾期」标记（色码仅管理端，§5 硬规则不变）；用户端逾期只显示「已逾期，请尽快完成」，禁止出现危机/色码字样。

> **v1.2 实现补记 4（2026-11-24，附加、非破坏）**：§3.2 思想汇报录音改为**手动控制**——「开始录音」启动、`结束录音` 终止并保存（调 `POST /api/sessions/{id}/stop`，api@1.5 补记·三）；**删除倒计时**，录音中仅显示红点状态标识与正计时时长（mm:ss）；不存在自动终止；保存、轮询、结果反馈逻辑不变。

> **v1.2 实现补记 5（2026-11-24，附加、非破坏）**：
> 1. **同意后直达采集页**：`PUT /api/user/consent` 成功即跳转 `/capture`（`replace`），取消原「进入采集引导」确认按钮与成功提示框，链路为 `/consent → /capture`，不设中间节点。
> 2. **§3.4 模块选择页新增两个入口**：`AI援助`、`教育学习`（与签到/汇报卡片同款样式、同栅格响应式），位于「更多服务」分区，不依赖 `/api/user/tasks` 数据。
> 3. **统一占位跳转**：两入口均跳 `/pending?feature=ai-aid|education`，展示「功能待开发」，提供返回事项选择；当前不对接后端、不实现业务逻辑。
> 4. **AI援助扩展位**：代码注释标注后续可扩展「心理援助 / 法律援助 / 就业帮扶」三类能力，届时拆分为独立入口与页面，不改变现有签到/汇报流程。
> 5. 用户端仍禁止出现色码/危机/分值字样；占位页文案仅中性提示。

> **v1.2 实现补记 6（2026-11-25，附加、非破坏）**：录音汇报与刷脸签到共用结果页 `/feedback/:sessionId`，该页在结论/建议/下一步之后新增主按钮 **「返回首页」**（跳转 `/capture`），失败终态 `CaptureResult` 与结果加载失败提示同样提供「返回首页」；按钮沿用设计系统主色/圆角，最小触控高度 44px，`≤480px` 时整行展示。
>
> 补充：两个采集子页 `/capture/report`、`/capture/checkin` 的**右上角**也提供同文案「返回首页」按钮（次要按钮样式、`min-height: 40px`，跳转 `/capture`），页面底部保留原有文字链接；不改变原有录制、上传、人脸校验与结果展示逻辑。

> **v1.2 实现补记 7（2026-11-25，附加、非破坏）**：用户端新增登录页 `/login`，原独立知情同意页 `/consent` 的功能合并至登录页，不再保留独立页面（`/consent` 仅做跳转到 `/login`）。
> 1. 登录页包含用户名、密码输入与「登录并进入」按钮；开发演示账号为 `张三 / 123456`，可通过 `VITE_DEMO_USERNAME` / `VITE_DEMO_PASSWORD` 覆盖，**仅用于本地联调，不代表真实身份认证**。
> 2. 原「面部图像」与「语音」两项独立勾选合并为**单一统一同意勾选**，一次勾选同时授权两项；提交时仍调用 `PUT /api/user/consent` 并携带 `face=true, audio=true`，api@1.5 契约不变。
> 3. 进入条件：账号密码正确 **且** 已勾选统一同意；同意成功写库后才跳转 `/capture`，任一条不满足均停留登录页并给出中性提示。
> 4. 路由守卫：用户端未登录或后端同意不完整（`general` / `face` / `audio` 任一未授权）统一跳 `/login`；管理端守卫不变。
> 5. 登录态仅保存用户名与时间到 `localStorage` 的 `cc.user.session`，禁止写入人脸、音频、转写等内容；退出登录只清除本地登录态，不撤回已提交的同意。
> 6. 原 §3.1「禁止把两项同意折叠进一个总协议 checkbox」自本条起废止，以本条为准。

> v1.2 实现补记 8（2026-11-25，附加、非破坏）：管理端对象详情新增「思想汇报同步」面板（§4.2）——同步按钮、能力未启用提示、同步记录列表、查看完整报告（转写全文 + 情绪类型/置信度/关键触发片段），展示数据版本、操作人与时间。真实同步由 `SENSEVOICE_SYNC_ENABLED` 控制，默认关闭；关闭时按钮可用但点击返回「同步能力未启用」中性提示，不伪造转写/情绪内容。

> v1.2 实现补记 9（2026-11-25，附加、非破坏）：管理端对象详情增强。① 对象列表「姓名」为详情链接（`/admin/subjects/:subjectId`）；② 详情页新增基础档案（性别、年龄、身份证号、联系电话、住址、矫正类别与起止日期）；③ 新增按日期筛选的「打卡与思想汇报」区块，展示该日打卡影像与思想汇报录音，支持在线预览/播放，媒体统一置于默认折叠的敏感面板；④ 原独立状态看板（§4.3）全部内容合并进对象详情，`/admin/dashboard` 与导航入口下线，旧地址重定向 `/admin/subjects`。档案字段、媒体端点与留痕规则尚待 `db` / `api` 契约补齐；当前原型媒体为演示素材（占位影像 + 2 秒静音 WAV），不得用于真实调阅。

> v1.2 实现补记 10（2026-11-25，附加、非破坏）：管理端界面与相关契约的中文表述统一为「复核任务」——指分级规则命中或逾期后自动生成、由工作人员在复核队列中按优先级与截止时间处理的事项；「任务来源」「生成时间」「自动生成」同步替换原单据化措辞。技术标识 `review_tickets`、`/api/admin/tickets`、`ticket_id` 及状态枚举保持不变，接口语义与流转规则不变。

> **v1.2 实现补记 11（2026-11-25，附加、非破坏）**：对象详情「近 7 天趋势」升级为「心理状态分析看板」（§4.2），对接 api@1.5 §7.18，按**任意日期区间**查询并按四个图表呈现；`TrendStrip` 保留但不再作为主视图。
>
> 1. **日期区间条**：预设「近 7 天 / 近 14 天 / 近 30 天」+ 自定义起止日期；默认近 14 天（含端点）；跨度上限 366 天，超出前端直接拦截提示；日期改动仅更新草稿，点击「查询」后才发起请求；请求需做竞态处理（丢弃过期响应）。
> 2. **图表选型（Recharts）**：
>    - **情绪二维散点图（Russell 环形模型）**：X 轴效价 `valence ∈ [-1,1]`，Y 轴信号强度 `signal ∈ [0,100]`（可切换 Y 轴为唤醒度 `arousal ∈ [0,1]`）；每个点代表一次已分析的思想汇报；点色=该会话所在自然日复盘五色，**无复盘色时使用中性灰且不得使用五色**；点径映射信号强度；背景按四象限分块并标注象限语义；hover tooltip 展示日期、效价、信号、唤醒度、色名、`rules_fired` 中文名与证据入口。
>    - **五色日历热力图**：以周为列/星期为行的日历网格（CSS Grid 自绘），色块=当日 `review.color`，无复盘=中性灰；hover 展示日期、色名、`rules_fired` 与证据入口；图例含「无复盘」。
>    - **稳定性与一致性柱状图**：按日分组柱，分别展示 `degraded`、`consistency=low`、`conflict` 三项计数；缺失日期按 0 展示；hover 展示具体日期与三项计数。
>    - **行为依从性日历（GitHub 风格）**：签到、汇报各一行，按日展示「已完成 / 逾期 / 未要求」三态；**必须使用独立配色（成功/危险描边/中性灰），禁止复用五色风险令牌**；需在图注说明 `overdue` 为历史回溯口径，与列表页实时逾期可能不同。
> 3. **心理学语义提示**：`summary.signals[]` 由 `web/src/lib/psychText.ts` 统一映射为中性描述与建议动作，逐条附「仅作提示，需结合面谈与人工复核」；**严禁**出现「抑郁 / 焦虑症 / 人格障碍 / 精神异常」等诊断词，严禁把信号表述为系统结论（§6 红线）；无 `signals` 时展示中性空提示。
> 4. **色码硬规则不豁免**：散点与热力块展示的任何五色都必须同屏可追溯到 `rules_fired` 与证据入口（§5.2）；纯灰块不承载风险信息。
> 5. **状态**：加载用骨架；接口失败用统一错误横幅 + 重试；区间无数据展示明确空态与引导文案，不渲染空白图表。
> 6. **禁止**：跨对象对比、趋势排名、任何分数或处置动作；不写入 `localStorage` / `IndexedDB`。
> 7. **依赖**：新增 `recharts`（按需引入），不引入全局状态库。

> **v1.2 实现补记 12（2026-11-25，结构重构、非破坏）**：心理状态看板并入「状态概览」，四个图表改为可折叠。
>
> 1. **合并结构**：移除独立的「心理状态分析看板」区块、标题与容器；其全部内容（日期区间条、区间汇总、心理提示卡、四个图表）嵌入 `/admin/subjects/:subjectId` 的「状态概览」卡内，位置在「五色分布 / 待复核与最近采集 / 近 7 天趋势」之后。
> 2. **折叠交互**：四个图表分别封装为可折叠按钮——Russell 二维散点图、五色日历热力图、稳定性与一致性柱状图、行为依从性日历；**默认全部收起，仅显示按钮**（标题 + 展开指示），点击展开完整内容，再次点击收起。按钮使用 `<button type="button" aria-expanded aria-controls>`，支持键盘操作与 `:focus-visible`；展开面板带 `role="region"` 与 `aria-label`。
> 3. **常驻内容**：日期区间条、区间汇总、心理提示卡**不折叠**，始终显示；切换区间后保留各图表的展开/收起状态。
> 4. **渲染与动效**：图表仅在展开时挂载（避免隐藏容器内 Recharts 尺寸为 0 导致空白/错位），收起即卸载；展开使用 160–220ms 的透明度/位移入场过渡。折叠与展开不得造成横向滚动、卡片高度跳变或样式错乱。
> 5. **内容不变**：四图的数据、交互、证据深链（`/admin/reviews/:reviewId`）、空态、图例、免责声明与色彩规则均与补记 11 一致；加载骨架只保留区间汇总与按钮占位，不再预渲染四个空卡片。

> **v1.2 实现补记 13（2026-11-25，排版调整、非破坏）**：五色日历热力图由「周为列 / 星期为行」的纵向矩阵改为**按日期从左到右、自动换行的横向序列**。
>
> 1. 每个日期一格，按 `date` 升序从左到右排列，格下方显示 `MM-DD` 日期标签；容器宽度不足时按行折行，单元格间距统一（6px），不出现横向滚动条。
> 2. 五色映射、无复盘中性灰、选中描边、键盘聚焦、hover/点击详情面板、规则中文、证据深链（`/admin/reviews/:reviewId`）全部不变。
> 3. 移除星期行标签与周列结构；无障碍组标签更新为「按日期从左到右排列」；图注同步说明折行规则。
> 4. 目标：14 天数据在常见桌面宽度下一行完整可见；窄屏按行折行（约 2–3 行）展示，避免纵向长滚动。

> **v1.2 实现补记 14（2026-11-25，新增页面）**：AI 援助由占位页升级为可用的独立对话页 `/ai-aid`。
>
> 1. **入口**：模块选择页「AI援助」卡片直达 `/ai-aid`；`/pending?feature=ai-aid` 重定向至 `/ai-aid`，`/pending` 仅保留「教育学习」占位。路由需 `RequireUser`。
> 2. **页面结构**：标题与范围说明（心理援助、法律援助）→ 未开通/降级提示区 → 消息列表 → 输入区（多行、2000 字计数、发送/停止）。空态提供 3 条引导示例，点击即填入输入框。
> 3. **流式渲染**：解析 SSE 的 `meta` / `delta` / `citation` / `notice` / `done` / `error`；`delta` 逐字追加；仅当用户接近底部时自动滚动；发送中禁用重复提交，提供「停止」；离开页面或点击停止立即 `abort`。
> 4. **合规展示**：每条 AI 消息下方固定展示「目前测试版本的回答基于公开网络信息，仅供参考，不构成专业建议」；页头固定展示「你的问题会发送至第三方模型服务用于生成回答，请勿输入身份证号、住址等敏感信息」；收到 `notice(web_search_unavailable)` 时在该条消息内追加「本次回答未启用联网搜索」。引用来源以纯文本链接列出，`target="_blank"` + `rel="noopener noreferrer"`，无来源则不显示。
> 5. **状态**：`status.enabled=false` 时输入区禁用，展示中性提示「智能援助暂未开通，请联系工作人员」；流内 `error` 以气泡级错误展示并提供重试；`1004` 返回对象列表入口。
> 6. **隐私**：消息仅存内存，禁止写入 `localStorage` / `IndexedDB` / 后端业务表；页面不显示 `subject_id`；提供「清空对话」，刷新即清空。不提供文件/图片上传与语音输入。
> 7. **渲染安全**：AI 文本按纯文本渲染（保留换行），不注入 HTML，不引入 Markdown 渲染库；禁止展示风险色码、评分或诊断结论。

---

## 1. 技术约定

| 项 | 约定 |
|---|---|
| 目录 | 用户端 `web/src/user/`，管理端 `web/src/admin/`，通用组件 `web/src/components/common/` |
| 请求层 | 统一 `web/src/lib/http.ts`，自动带 `Authorization` 与解析响应包 |
| 状态 | 页面级 `useState` + 请求 hook，不引入全局状态库 |
| 样式 | CSS Module 或 Tailwind 二选一，全仓统一 |
| 色码 | 只能来自 `web/src/lib/colors.ts`，取值由第 5 节定义 |
| 缓存 | 禁止把音频、面部图、转写原文写入 `localStorage` / `IndexedDB` |
| 响应处理 | 必须判 `code`，`code != 0` 走统一错误提示 |
| 共享代码 | `web/src/lib/` 与 `web/src/components/common/` 由用户端、管理端共用；新增或改动需在输出中声明，避免两端同名文件冲突 |

## 2. 路由总览

| 端 | 路径 | 页面 | 组件目录 |
|---|---|---|---|
| user | `/login` | 用户登录页（含统一知情同意） | `web/src/user/Login/` |
| user | `/consent` | 旧同意地址，仅跳转 `/login` | 无独立页面 |
| user | `/capture` | 模块选择页（签到 / 思想汇报） | `web/src/user/Capture/` |
| user | `/capture/checkin` | 刷脸签到子页（face_only） | `web/src/user/Checkin/` |
| user | `/capture/report` | 思想汇报子页（face+audio，原采集引导页） | `web/src/user/Capture/` |
| user | `/pending` | 功能待开发提示页（仅 `?feature=education`） | `web/src/user/ComingSoon/` |
| user | `/ai-aid` | AI 援助对话页（心理援助 / 法律援助，SSE 流式） | `web/src/user/AiAssist/` |
| user | `/feedback/:sessionId` | 结果反馈页 | `web/src/user/Feedback/` |
| admin | `/admin/subjects` | 对象列表 | `web/src/admin/Subjects/` |
| admin | `/admin/subjects/:subjectId` | 对象详情 + 记录检索 | `web/src/admin/SubjectDetail/` |
| admin | `/admin/dashboard` | 状态看板 | `web/src/admin/Dashboard/` |
| admin | `/admin/tickets` | 复核队列 | `web/src/admin/Tickets/` |
| admin | `/admin/tickets/:ticketId` | 复核任务详情 | `web/src/admin/Tickets/Detail` |

路由守卫：

- 用户端：未登录，或 `GET /api/user/consent` 的 `general/face/audio` 任一未授权，访问 `/capture` 强制跳 `/login`（补记 7）；
- 管理端：`role != staff` 时全部跳登录/403 页；
- 用户端登录为开发演示账号（`VITE_DEMO_USERNAME` / `VITE_DEMO_PASSWORD`），token 仍由 `web/.env` 注入。

## 3. 用户端页面

### 3.1 知情同意页 `/consent`（v1.2 补记 7 起已合并至登录页 `/login`，本节仅保留历史契约）

> 现行实现见补记 7：单一统一勾选、登录后一次提交；本节「独立勾选」与「禁止折叠」条款已废止。

**目的**：进入用户端后**首次一次性授权**（原型以 token 注入视同登录），明确采集范围、用途与撤回方式；授权有效期内再次进入 `/capture` 不再要求同意，撤回后需重新授权。

| 区块 | 内容 |
|---|---|
| 说明 | 本次采集什么（面部图像、语音）、用于什么（辅助工作人员了解近况）；**不展示保存期限** |
| 独立勾选 | ① 面部图像采集 ② 语音采集（两项独立，不可合并为一个"同意全部"，同一页面一次提交） |
| 撤回说明 | 写明撤回方式与撤回后的影响 |
| 主按钮 | `开始使用`：**两项均勾选才可点**；仅勾一项时按钮禁用并提示「面部与语音需同时同意后才能开始采集」 |

**禁止**：

- 默认勾选；
- 用"不勾选就无法使用系统"这类胁迫性文案；
- 把两项同意折叠进一个总协议 checkbox。

### 3.2 采集引导页 `/capture`

| 区块 | 内容 |
|---|---|
| 准备说明 | 3 步图示：正视摄像头 → 说出今天的情况 → 等待完成 |
| 设备状态 | 摄像头 / 麦克风可用性检测结果 |
| 录制标识 | 采集中常驻 **红点 + "正在采集"** 文案，禁止静默录制 |
| 时长计时器 | 正计时 mm:ss（手动模式，补记 4）；**禁止倒计时** |
| 主按钮 | `开始` / `结束` |
| 结果 | 成功跳 `/feedback/:sessionId`；失败原地显示原因与重试按钮 |

**失败态文案映射**（`capture_status` → 用户可见文案）

| `capture_status` | 文案 | 副文案 | 操作 |
|---|---|---|---|
| `partial` | 本次数据不完整，已转人工复核 | — | 查看结果 |
| `no_face` | 没有识别到面部，请正对摄像头再试一次 | 已转人工复核 | 重试 |
| `no_audio` | 没有采集到有效的声音，请靠近麦克风再试一次 | 已转人工复核 | 重试 |
| `no_face_no_audio` | 本次采集未成功，请重试或联系工作人员 | — | 重试 / 联系 |
| `error` | 设备暂时不可用，请联系工作人员 | — | 联系 |

### 3.3 结果反馈页 `/feedback/:sessionId`

| 区块 | 内容 |
|---|---|
| 结论 | `summary_text`，中性单句 |
| 建议 | 按 `suggestion` 映射（见下表） |
| 下一步 | `next_action` |
| 撤出入口 | 常驻可见 |

| `suggestion` | 文案 |
|---|---|
| `keep_routine` | 保持现在的节奏，按约定时间再来即可 |
| `talk_to_staff` | 建议和工作人员聊一聊近期的情况 |
| `recapture` | 本次记录不完整，建议稍后重新采集 |

**硬性禁止**：展示色码、规则编号、任何分数、任何诊断词。接口若返回了这些字段，前端必须丢弃。

### 3.4 模块选择页 `/capture` 与签到子页 `/capture/checkin`（2026-11-24 新增）

模块选择页：

| 区块 | 内容 |
|---|---|
| 签到卡片 | 「刷脸签到」：显示 `checkin.interval_days`（如「每 1 天一次」）、`last_completed_at`；`overdue=true` 时中性提示「已逾期，请尽快完成」 |
| 汇报卡片 | 「录音思想汇报」：显示 `report.interval_days`、`last_completed_at` 与同款逾期提示 |
| AI援助卡片 | 「AI援助」：直达 `/ai-aid`，展示「心理援助 · 法律援助」；不依赖 `tasks` 接口 |
| 教育学习卡片 | 仍跳 `/pending?feature=education` 占位页 |
| 数据来源 | `GET /api/user/tasks`；未授权时仍由路由守卫跳 `/consent` |

签到子页 `/capture/checkin`：

| 区块 | 内容 |
|---|---|
| 准备说明 | 正视摄像头 → 拍摄 → 等待完成（**不包含录音步骤**，不要求麦克风） |
| 录制标识 | 采集中常驻红点 + 「正在采集」 |
| 主按钮 | `开始签到` → `POST /api/sessions`（`kind=checkin`）→ 轮询 → 完成后 `POST /api/sessions/{id}/analyze` → 跳 `/feedback/:sessionId` |

思想汇报子页 `/capture/report` 沿用 §3.2 全部约定，`POST /api/sessions` 携带 `kind=report`。

### 3.5 AI 援助页 `/ai-aid`（2026-11-25 新增）

| 区块 | 内容 |
|---|---|
| 页头 | 标题「AI援助」+ 说明「提供心理援助与法律援助的一般性信息，不替代医生、律师或工作人员」+ 固定第三方处理提示「你的问题会发送至第三方模型服务用于生成回答，请勿输入身份证号、住址等敏感信息」 |
| 状态提示 | `GET /api/user/ai-assist/status`：未开通时禁用输入并显示中性提示；联网不可用时在消息内提示 |
| 消息列表 | 用户消息右对齐、AI 消息左对齐；AI 正文纯文本渲染（保留换行）；流式期间显示光标态；每条 AI 消息下固定免责声明 |
| 引用来源 | 仅当收到 `citation` 时展示，标题 + 域名；链接 `target="_blank" rel="noopener noreferrer"` |
| 输入区 | 多行输入，2000 字上限并显示计数；`Enter` 发送、`Shift+Enter` 换行；发送中显示「停止」 |
| 空态 | 3 条引导示例（如「最近压力很大，怎么调节？」「法律援助怎么申请？」），点击填入输入框 |
| 操作 | 「清空对话」仅清内存；不保存历史、不写入 `localStorage` / `IndexedDB` |

请求与事件协议见 api.md §7.19–§7.20。前端每轮最多携带最近 12 条消息，服务端无状态。

**禁止**：展示风险色码/评分/诊断结论；保存聊天记录；文件、图片或语音上传；HTML/Markdown 注入；在 UI 或日志中显示 `subject_id`、API Key、上游错误原文。

## 4. 管理端页面

### 4.1 对象列表 `/admin/subjects`

| 列 | 字段 | 说明 |
|---|---|---|
| 编号 | `code` | |
| 姓名 | `name` | |
| 状态 | `status` | `active` / `suspended` / `closed` |
| 当前色码 | `latest_color` + `latest_color_at` | **必须带"查看依据"入口**，不可只显示色块 |
| 待复核 | `pending_tickets` | 点击跳队列并按对象过滤 |
| 最近采集 | `latest_session_at` | |

筛选：关键词（编号/姓名）、状态、色码。
**禁止**：排序榜单、跨对象风险排名、"重点人员"标记。

### 4.2 对象详情 `/admin/subjects/:subjectId`

| 区块 | 内容 |
|---|---|
| 基础信息 | 编号、姓名、状态、同意状态 |
| 频率配置（2026-11-24 新增） | 签到/汇报间隔天数两个整数输入（≥1），保存调 `PATCH /api/admin/subjects/{id}/frequency` |
| 逾期标记（2026-11-24 新增） | `overdue.checkin/report` 为 true 时显示红色「危机·逾期」徽标与最近完成时间；对象列表与看板同款标记 |
| 当前结果 | 最近一次 `reviews` 的 `final_color` + `rules_fired` + 证据摘要（同屏） |
| 状态概览（2026-11-25 补记 12 合并） | 五色分布、待复核与最近采集、近 7 天趋势，以及并入的「心理状态趋势」：日期区间条（预设 7/14/30 天 + 自定义，默认近 14 天）+ 区间汇总 + 心理提示卡 + 四个**可折叠**图表（Russell 二维散点图、五色日历热力图、稳定性与一致性柱状图、行为依从性日历，默认全部收起仅显示按钮）；数据源 `GET /api/admin/subjects/{id}/trends`（api@1.5 §7.18）；**不设独立看板区块、标题或入口** |
| 会话时间线 | 按 `captured_at` 倒序，显示 `capture_status`、`analysis_status`、色码 |
| 记录检索 | 时间范围、色码筛选 |
| 打卡与思想汇报（2026-11-25 补记 14） | 月历式日期选择器：仅 `available_dates` 内日期可点击，其余日期置灰且 `disabled`。选中日期后展示该日**全部采集记录**：默认选中最近更新的一条，提供「上一条 / 下一条」按采集时间顺序浏览，每条记录分别展示影像（有则）、录音（有则）与转写文本。影像与录音默认折叠，展开即写访问留痕提示。栏目底部以折叠区承载「全部采集记录（含失败）」时间线。数据源 `GET /api/admin/subjects/{id}/media`（api@1.5 §7.21，`items[]` 升序）与 `GET /api/admin/sessions/{id}/audio`（§7.22）。**不再设独立「敏感内容」与「会话时间线」栏目** |
| 思想汇报同步（2026-11-25 新增） | 「同步思想汇报」按钮调用 `POST /api/admin/subjects/{id}/sensevoice-sync`；下方列表展示 `data_version`、情绪类型/置信度、操作人、时间；点击「查看完整报告」调 `GET /api/admin/sensevoice-syncs/{sync_id}`（留痕）并展开转写全文、情绪类型、置信度、关键触发片段。能力未启用时显示中性提示「同步能力未启用，请联系管理员」，**不得展示伪造的转写或情绪结果** |

#### 4.2.1 心理提示文案映射（补记 11）

后端只回 `summary.signals[]` 机器码，前端在 `web/src/lib/psychText.ts` 统一映射；每条提示固定追加「仅作提示，需结合面谈与人工复核」。**禁止使用任何诊断词或结论式判断**。

| signal | 标题（中性） | 建议动作 | 禁用表述 |
|---|---|---|---|
| `insufficient_data` | 有效分析样本不足 | 暂不足以形成趋势提示，可按约定继续采集 | 任何推断性结论 |
| `low_arousal_negative` | 区间内呈现持续低效价、低唤醒的表达特征 | 建议优先安排面谈，核实近期生活与睡眠状况 | 抑郁倾向 / 抑郁状态 |
| `high_arousal_negative` | 出现负向且高强度（高唤醒）的表达 | 建议尽快人工复核，关注是否存在明显紧张或易激惹表现 | 焦虑症 / 躁狂 |
| `persistent_low_valence` | 多日效价持续偏低 | 建议结合面谈核实持续时长与诱因 | 抑郁 / 情绪障碍 |
| `valence_volatility_high` | 情绪效价日间波动较大 | 建议结合采集质量与事件背景复核，避免依据单日结论 | 情绪不稳（作为诊断） |
| `signal_escalating` | 近期信号强度呈上行趋势 | 建议关注近期是否有应激事件，并按优先级复核 | 病情加重 |
| `frequent_low_consistency` | 多日出现跨模态不一致 | 可能受采集质量或表达方式影响，建议核对影像与录音 | 伪装 / 掩饰（作为定性） |
| `frequent_capture_degraded` | 区间内多次出现分析降级 | 建议核对采集环境与设备，必要时重新采集 | — |
| `behavior_overdue_frequent` | 区间内多次未按期完成签到或汇报 | 建议联系核实履约情况 | 违规 / 抗拒监管 |

### 4.3 状态看板 `/admin/dashboard`（补记 9 起已合并进对象详情，本节仅保留历史契约）

| 区块 | 内容 |
|---|---|
| 色码分布 | 单对象五色计数（`color_distribution`） |
| 7 日趋势 | `trend_7d` 折线或色块序列（补记 11 起在本页由心理状态分析看板取代，接口保留兼容） |
| 待复核 | `pending_tickets`，点击跳队列 |
| 最近采集 | `last_session_at` |

**禁止**：多对象对比图、人均排名、部门排行榜。

### 4.4 复核队列 `/admin/tickets`

| 列 | 字段 |
|---|---|
| 优先级 | `priority`（P0 置顶） |
| 对象 | `subject_id` → 姓名 |
| 当前色码 | `final_color`（带证据入口） |
| 触发规则 | `triggered_rules` |
| 生成时间 | `opened_at` |
| 截止 | `due_at`（超期标红） |
| 状态 | `status` |

筛选：状态、优先级、对象、时间范围。

### 4.5 复核任务详情 `/admin/tickets/:ticketId`

| 区块 | 内容 |
|---|---|
| 基本信息 | 对象、优先级、生成时间、截止时间、建议方式 |
| 结论区 | 五色标识 + `rules_fired` + 证据链表格（`field_path` / `observed_value` / `threshold` / `session_id`） |
| 原始内容 | 面部图、转写原文折叠，展开即留痕 |
| 操作区 | `确认` / `修正` / `关闭` |
| 留痕区 | 历史结论、操作人、时间 |

操作表单：

| 动作 | 表单字段 | 校验 |
|---|---|---|
| 确认 | `note`（选填） | — |
| 修正 | `conclusion_color`（必选五色）+ `note`（必填） | 两项都填才能提交 |
| 关闭 | `note`（必填） | 不得为空 |

**禁止**：一键处置、批量改变对象状态、批量关闭复核任务。

### 4.6 复盘详情 `/admin/reviews/:reviewId`

看板（§4.2 补记 11）中散点与热力块的证据入口统一指向本页；数据源 `GET /api/admin/reviews/{review_id}`（api@1.5 §7.9）。**只读**，不提供复核流转动作。

| 区块 | 内容 |
|---|---|
| 基本信息 | 对象（姓名 + 可点回 `/admin/subjects/:subjectId`）、窗口起止与天数、生成时间、`grading_version` |
| 结论区 | `final_color` 色码 + `rules_fired` 中文名 + `trend_color` / `single_session_risk` / `consistency` / `manual_review`；色码与规则、证据链入口同屏 |
| 证据链 | `EvidenceTable`：字段、观测值、阈值名称与值、会话编号 |
| 返回入口 | 返回对象详情；接口 `1004` 时展示错误横幅与重试，不渲染空白页 |

约定：

1. 证据入口携带 `review_id` 直达本页；缺少 `review_id` 的看板点位**不得伪造链接**，只显示中性说明（不拼接 `subject_id` 回退到复核队列）。
2. 本页不展示转写原文、音频、影像；如需查看原始内容，走复核任务详情的折叠敏感面板（留痕）。
3. 未知 `rule_id` / `field_path` / `threshold_key` 沿用 `ruleText.ts` 的中性兜底，不显示英文原始键。

## 5. 色码展示规则

### 5.1 令牌定义

```ts
// web/src/lib/colors.ts
export const COLOR_ORDER = ["green", "blue", "yellow", "orange", "red"] as const;
export type Color = (typeof COLOR_ORDER)[number];

export const COLOR_META: Record<Color, { label: string; token: string }> = {
  green:  { label: "绿", token: "--c-green" },
  blue:   { label: "蓝", token: "--c-blue" },
  yellow: { label: "黄", token: "--c-yellow" },
  orange: { label: "橙", token: "--c-orange" },
  red:    { label: "红", token: "--c-red" },
};
```

色值只在 `web/src/styles/tokens.css` 定义一次，组件只引用变量。

### 5.2 三条硬规则

1. **色码必须与证据链同屏**。任何展示色码的组件必须同屏渲染至少 `rules_fired` 与证据入口，禁止孤立色块。
2. **色码只在管理端出现**。用户端组件不得 import `COLOR_META`。
3. **色码不能单独承载信息**。必须同时给出中文名（绿/蓝/黄/橙/红）与规则编号，满足色觉障碍可读性。

### 5.3 组件契约

```tsx
// web/src/components/common/ColorBadge.tsx（管理端专用）
type ColorBadgeProps = {
  color: Color;
  rules: string[];              // 必填，为空时组件渲染为"待补证据"并标红
  evidenceHref?: string;        // 证据详情入口
  at?: string;
};
```

`rules` 为空时组件必须进入错误态，不允许静默渲染颜色。

## 6. 文案与禁用词

| 禁用 | 替代 |
|---|---|
| 抑郁 / 焦虑症 / 人格障碍 / 精神异常 | 信号强度偏高 / 偏移明显 |
| 自杀倾向（作为结论） | 出现指向性表达，需人工确认 |
| 正常 / 不正常 | 无明显偏移 / 建议关注 |
| 高风险人员 / 重点人 | 本次结果建议优先复核 |
| AI 判定 / 智能诊断 | 规则命中 / 依证据判断 |
| 无感知 / 无感采集 | 对话中了解近况 |

所有面向对象的文案需满足：可解释、不承诺、不恐吓。

## 7. 状态与失败态

| 状态 | 要求 |
|---|---|
| Loading | 有骨架或明确加载文案 |
| 空数据 | 明确空态文案，不显示空白表格 |
| `code=1002/1003` | 提示无权限，不展示业务数据 |
| `code=1004` | 提示资源不存在，给返回入口 |
| `code=1005` | 按 `message` 映射具体提示（如 `consent_required` / `consent_incomplete` / `no_session_in_window`） |
| `code=1006` | 提示稍后再试，倒计时禁用按钮 |
| `code=2001` | `sessions.status=failed`，按 `capture_status`（`no_face_no_audio` / `error`）展示第 3.2 节映射文案 |
| `degraded` 含 `"capture"` | 按 `capture_status`（`partial`）展示第 3.2 节文案，结果页可用 |
| `code=2003` | 分析未完成、结果不可用，提示重采或联系工作人员 |
| `code=5000` | 通用失败提示 + 重试按钮，禁止展示堆栈 |

所有失败态必须有可见文案，不允许白屏或静默失败。

## 8. 组件清单

### 8.1 用户端

| 组件 | 路径 | 职责 |
|---|---|---|
| `ConsentForm` | `web/src/user/Consent/ConsentForm.tsx` | 双项独立勾选 + 期限说明 |
| `CaptureGuide` | `web/src/user/Capture/CaptureGuide.tsx` | 三步引导 + 设备状态 |
| `RecordingIndicator` | `web/src/user/Capture/RecordingIndicator.tsx` | 红点 + 文案 + 倒计时 |
| `CaptureResult` | `web/src/user/Capture/CaptureResult.tsx` | 失败态与重试 |
| `FeedbackPanel` | `web/src/user/Feedback/FeedbackPanel.tsx` | 中性结论与建议 |

### 8.2 管理端

| 组件 | 路径 | 职责 |
|---|---|---|
| `SubjectTable` | `web/src/admin/Subjects/SubjectTable.tsx` | 列表与筛选 |
| `ColorBadge` | `web/src/components/common/ColorBadge.tsx` | 色码 + 规则 + 证据入口 |
| `EvidenceTable` | `web/src/admin/Tickets/EvidenceTable.tsx` | 证据链表格（复盘详情复用） |
| `ReviewDetailPage` | `web/src/admin/Reviews/ReviewDetailPage.tsx` | 单条复盘只读详情：结论、规则中文、证据链（§4.6） |
| `SessionTimeline` | `web/src/admin/SubjectDetail/SessionTimeline.tsx` | 会话记录 |
| `SensitivePanel` | `web/src/components/common/SensitivePanel.tsx` | 折叠敏感字段 + 留痕 |
| `SensevoiceSyncPanel` | `web/src/admin/SubjectDetail/SensevoiceSyncPanel.tsx` | 思想汇报同步按钮、记录列表、完整报告展开 |
| `TicketActions` | `web/src/admin/Tickets/TicketActions.tsx` | 三种流转动作与校验 |
| `TrendStrip` | `web/src/admin/SubjectDetail/TrendStrip.tsx` | 7 日趋势（随看板合并迁移，补记 9；补记 11 起保留但不再作为主视图） |
| `TrendBoard` | `web/src/admin/SubjectDetail/TrendBoard/TrendBoard.tsx` | 心理状态趋势容器（嵌入「状态概览」）：区间联动、请求竞态、加载/空/错态、图表折叠编排（补记 11 / 12） |
| `ChartCollapsible` | `web/src/admin/SubjectDetail/TrendBoard/ChartCollapsible.tsx` | 图表折叠按钮与面板：默认收起、`aria-expanded` 控制、展开时挂载图表、入场过渡 |
| `TrendDateRange` | `web/src/admin/SubjectDetail/TrendBoard/TrendDateRange.tsx` | 预设 7/14/30 天 + 自定义区间，跨度上限 366 天 |
| `RussellScatter` | `web/src/admin/SubjectDetail/TrendBoard/RussellScatter.tsx` | 效价 × 信号/唤醒散点，五色 + 证据入口、四象限底纹 |
| `ColorCalendarHeatmap` | `web/src/admin/SubjectDetail/TrendBoard/ColorCalendarHeatmap.tsx` | 日粒度五色日历热力图（CSS Grid），无复盘中性灰 |
| `StabilityBarChart` | `web/src/admin/SubjectDetail/TrendBoard/StabilityBarChart.tsx` | 每日 degraded / low / conflict 分组柱 |
| `ComplianceCalendar` | `web/src/admin/SubjectDetail/TrendBoard/ComplianceCalendar.tsx` | 签到/汇报依从性日历，独立三态配色 |
| `PsychInsightList` | `web/src/admin/SubjectDetail/TrendBoard/PsychInsightList.tsx` | `signals` → 中性提示 + 免责声明 |
| `psychText` | `web/src/lib/psychText.ts` | signal 码 → 中性文案映射（补记 11 §4.2.1） |

## 9. 验收清单

- [ ] 用户端全流程不出现色码、规则编号、分数
- [ ] 采集过程全程有红点与文案，无静默录制
- [ ] 所有 `capture_status` 分支都有对应文案
- [ ] 管理端任何色码展示都伴随 `rules_fired` 与证据入口
- [ ] 敏感字段默认折叠，展开触发 `sensitive.view` 留痕
- [ ] 复核任务三种动作校验符合第 4.5 节
- [ ] 无 localStorage / IndexedDB 存储音视频
- [ ] 所有接口错误码都有可见提示
- [ ] 趋势看板日期区间默认近 14 天、上限 366 天，超出有前置拦截提示
- [ ] 趋势看板五色块/散点均可追溯 `rules_fired` 与证据入口，无复盘日不着五色
- [ ] 看板证据入口可直达 `/admin/reviews/:reviewId`；缺 `review_id` 时给出中性说明，不伪造链接
- [ ] 心理状态趋势已并入「状态概览」，页面不存在独立的「心理状态分析看板」区块或标题
- [ ] 四个图表默认收起，仅显示按钮；点击可展开、再次点击可收起，键盘可操作，无布局跳动
- [ ] 五色热力图按日期从左到右排列，窄屏自动折行，颜色、规则与证据交互保持不变
- [ ] 心理提示仅使用中性表述且附「仅供参考，需人工复核」，无任何诊断词
- [ ] 行为依从性日历不使用五色风险令牌
- [ ] 不存在一键处置、批量改状态、跨对象排名入口
- [ ] 色值只在 `tokens.css` 定义一次
- [ ] 对象详情页不存在独立「敏感内容」栏目，留痕提示已并入「打卡与思想汇报」
- [ ] 日期选择器为月历形态，不可用日期置灰且不可点击，页面无「可用日期」文字列表
- [ ] AI 援助页在 `enabled=true` 时可输入并发送，回答流式渲染
- [ ] 同日多条采集记录可通过「上一条 / 下一条」切换，默认展示该日最新一条
- [ ] 页面不存在独立「会话时间线」栏目，全部采集记录折叠于「打卡与思想汇报」底部
