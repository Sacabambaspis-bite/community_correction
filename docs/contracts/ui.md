# 契约 · 前端界面（ui）

| 项 | 值 |
|---|---|
| 契约版本 | `ui@1.2` |
| 所有者 | fe-user（`web/src/user/`）、fe-admin（`web/src/admin/`） |
| 依赖 | [api.md](./api.md)、[../grading.md](../grading.md)（色码唯一来源） |
| 技术栈 | React + Vite，路由用 `react-router` |

> v1.2 已冻结，后续仅接受实现驱动的变更。

> **v1.2 实现补记（2026-11-24，附加、非破坏）**：§3.1 知情同意的主按钮口径与 api@1.5 §7.2 对齐——面部与语音**两项均勾选**才允许发起采集；单项授权可提交保存，但 `POST /api/sessions` 返回 `1005 consent_incomplete`。删除「允许只勾一项」的历史表述。

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
| user | `/consent` | 知情同意页 | `web/src/user/Consent/` |
| user | `/capture` | 采集引导页 | `web/src/user/Capture/` |
| user | `/feedback/:sessionId` | 结果反馈页 | `web/src/user/Feedback/` |
| admin | `/admin/subjects` | 对象列表 | `web/src/admin/Subjects/` |
| admin | `/admin/subjects/:subjectId` | 对象详情 + 记录检索 | `web/src/admin/SubjectDetail/` |
| admin | `/admin/dashboard` | 状态看板 | `web/src/admin/Dashboard/` |
| admin | `/admin/tickets` | 复核队列 | `web/src/admin/Tickets/` |
| admin | `/admin/tickets/:ticketId` | 工单详情 | `web/src/admin/Tickets/Detail` |

路由守卫：

- 用户端：未同意（`GET /api/me/consent` 的 `general.granted != true`）访问 `/capture` 强制跳 `/consent`；
- 管理端：`role != staff` 时全部跳登录/403 页；
- 原型不做真实登录页，token 由 `web/.env` 注入。

## 3. 用户端页面

### 3.1 知情同意页 `/consent`

**目的**：首次使用必过，明确采集范围、用途、期限、撤回方式。

| 区块 | 内容 |
|---|---|
| 说明 | 本次采集什么（面部图像、语音）、用于什么（辅助工作人员了解近况）、存多久（`retention_days`） |
| 独立勾选 | ① 面部图像采集 ② 语音采集（两项独立，不可合并为一个"同意全部"） |
| 期限展示 | 展示 `retention_days`，单位天 |
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
| 倒计时 | 录音剩余秒数 |
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
| 当前结果 | 最近一次 `reviews` 的 `final_color` + `rules_fired` + 证据摘要（同屏） |
| 会话时间线 | 按 `captured_at` 倒序，显示 `capture_status`、`analysis_status`、色码 |
| 记录检索 | 时间范围、色码筛选 |
| 敏感内容 | 面部图、转写原文默认折叠，点击展开并调用留痕接口 |

### 4.3 状态看板 `/admin/dashboard`

| 区块 | 内容 |
|---|---|
| 色码分布 | 单对象五色计数（`color_distribution`） |
| 7 日趋势 | `trend_7d` 折线或色块序列 |
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
| 建单时间 | `opened_at` |
| 截止 | `due_at`（超期标红） |
| 状态 | `status` |

筛选：状态、优先级、对象、时间范围。

### 4.5 工单详情 `/admin/tickets/:ticketId`

| 区块 | 内容 |
|---|---|
| 基本信息 | 对象、优先级、建单时间、截止时间、建议方式 |
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

**禁止**：一键处置、批量改变对象状态、批量关闭工单。

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
| `EvidenceTable` | `web/src/admin/Tickets/EvidenceTable.tsx` | 证据链表格 |
| `SessionTimeline` | `web/src/admin/SubjectDetail/SessionTimeline.tsx` | 会话记录 |
| `SensitivePanel` | `web/src/components/common/SensitivePanel.tsx` | 折叠敏感字段 + 留痕 |
| `TicketActions` | `web/src/admin/Tickets/TicketActions.tsx` | 三种流转动作与校验 |
| `TrendStrip` | `web/src/admin/Dashboard/TrendStrip.tsx` | 7 日趋势 |

## 9. 验收清单

- [ ] 用户端全流程不出现色码、规则编号、分数
- [ ] 采集过程全程有红点与文案，无静默录制
- [ ] 所有 `capture_status` 分支都有对应文案
- [ ] 管理端任何色码展示都伴随 `rules_fired` 与证据入口
- [ ] 敏感字段默认折叠，展开触发 `sensitive.view` 留痕
- [ ] 工单三种动作校验符合第 4.5 节
- [ ] 无 localStorage / IndexedDB 存储音视频
- [ ] 所有接口错误码都有可见提示
- [ ] 不存在一键处置、批量改状态、跨对象排名入口
- [ ] 色值只在 `tokens.css` 定义一次
