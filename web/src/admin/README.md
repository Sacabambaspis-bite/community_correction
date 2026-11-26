# web/src/admin/

工作人员（staff）管理端：对象列表 / 对象详情 / 复核队列 / 复盘详情。只做展示与频率配置，不承载用户端采集流程。

## 路由（`web/src/App.tsx`，`/admin` 由 `RequireStaff` 守卫，布局 `AdminLayout.tsx`）
- `/admin` → 重定向 `/admin/subjects`
- `/admin/subjects`：对象列表（姓名可点进详情）
- `/admin/subjects/:subjectId`：档案、状态概览与趋势看板、打卡与思想汇报、频率配置
- `/admin/tickets`、`/admin/tickets/:ticketId`：复核队列与任务详情（敏感内容折叠）
- `/admin/reviews/:reviewId`：单条复盘只读详情；`/admin/dashboard` 已下线，仅重定向到对象列表

## 核心文件
- `SubjectDetail/SubjectDetailPage.tsx`：详情主页面；`SubjectDetail/TrendBoard/`：区间选择 + 四图 + `trendDisplay.ts` 证据深链
- `Subjects/`、`Tickets/`、`Reviews/`、`OverdueBadge.tsx`；接口封装在 `web/src/api/admin.ts`

## 色彩规范
- 只能使用 `web/src/styles/tokens.css` 的 CSS 变量（`--color-*`、`--c-green|blue|yellow|orange|red`、`--space-*`、`--radius-*`），禁止硬编码色值
- 五色映射统一走 `web/src/lib/colors.ts` 的 `COLOR_META` 与 `components/common/ColorBadge.tsx`

## 双日历独立状态（打卡 / 汇报）
- 两栏各自持有 `checkinDate` / `reportDate`、`checkinMedia` / `reportMedia`、loading / error / index
- 首屏只调一次 `getSubjectMedia` 同时初始化两栏，之后 `loadCheckinMedia` / `loadReportMedia` 只更新本栏
- 请求带序号守卫丢弃过期响应；审计提示 `checkinAuditHint` / `reportAuditHint` 分栏展示

## 千万不要
- 展示无数据来源的结论；色码只能来自后端
- 影像 / 录音必须带鉴权拉 blob，不可直接引用绝对路径；不要改 `app/` 与接口契约
