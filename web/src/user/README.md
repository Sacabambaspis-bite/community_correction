# web/src/user/

社矫人员侧页面：登录（含统一知情同意）、事项选择、刷脸签到、思想汇报录制、结果反馈与 AI 援助。

## 路由（`web/src/App.tsx`）
- `/login`：账号密码 + 统一知情同意（旧 `/consent` 仅重定向到这里）
- `/capture`：事项选择；`/capture/checkin`：刷脸签到；`/capture/report`：思想汇报
- `/feedback/:sessionId`：采集结果反馈（成功 / 失败终态）；`/ai-aid`：AI 援助；`/pending?feature=...`：待开发占位

## 核心文件
- `Login/LoginPage.tsx`：登录与同意拦截
- `Capture/`：`CaptureTasksPage`、`CheckinPage`、`CapturePage`、`CaptureResult`
- `Feedback/FeedbackPage.tsx` + `FeedbackPanel.tsx`；`AiAssist/AiAssistPage.tsx`
- 登录态 `web/src/lib/auth.ts`，路由守卫 `web/src/lib/guards.tsx`

## 拦截逻辑
- `RequireUser` 先查 `getUserSession()`（localStorage `cc.user.session`），再调 `GET /api/user/consent`
- `general` / `face` / `audio` 三要素必须全部 `granted`，否则一律 `Navigate` 到 `/login`
- 登录页要求：演示账号校验通过 + 勾选统一同意 → `PUT /api/user/consent(face=true, audio=true)` 成功后才跳 `/capture`

## 红线
- 用户端绝不展示五色色码、风险等级、分析结论或证据链（这些只属于管理端）
- 不把录音、转写、面部图像写入 localStorage / IndexedDB；AI 消息只存内存，刷新即清空
- 演示账号仅用于开发联调，不是真实身份认证
