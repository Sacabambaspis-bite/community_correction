/* DTO 字段严格对齐 api@1.5 示例，snake_case 不做前端改名。
 * tickets / reviews / dashboard 端点尚未实现（api@1.5 §5.4），
 * 相关类型依据 ui@1.2 §4.5 与 api@1.5 §7.9/§7.11 的字段推导，接口落地后需复核。
 */
import type { Color } from "../lib/colors";

/** api@1.5 §2 统一响应包 */
export type Envelope<T> = {
  code: number;
  message: string;
  data: T | null;
  degraded: string[];
  request_id: string;
};

/** 分页结构，api@1.5 §1 */
export type Paged<T> = {
  items: T[];
  page: number;
  page_size: number;
  total: number;
};

export type DegradedFlag = "capture" | "analysis";

/* ---------- 用户端 consent ---------- */

export type ConsentItem = {
  granted: boolean;
  at: string | null;
};

/** api@1.5 §7.1.1 */
export type ConsentData = {
  subject_id: string;
  general: ConsentItem;
  face: ConsentItem;
  audio: ConsentItem;
  revoked_at: string | null;
  retention_days: number | null;
};

/* ---------- 会话 ---------- */

export type CaptureStatus =
  | "ok"
  | "partial"
  | "no_face"
  | "no_audio"
  | "no_face_no_audio"
  | "error";

export type AnalysisStatus = "pending" | "done" | "degraded" | "failed";

export type Coverage = "both" | "face_only" | "audio_only";

export type SessionStatus = "created" | "captured" | "failed";

export type SessionKind = "checkin" | "report";

/** api@1.5 补记·二：GET /api/user/tasks */
export type UserTaskData = {
  interval_days: number;
  last_completed_at: string | null;
  overdue: boolean;
};

export type UserTasksData = {
  checkin: UserTaskData;
  report: UserTaskData;
};

/** api@1.5 §7.2 POST 返回 */
export type SessionCreateData = {
  session_id: string;
  status: "created";
  kind: SessionKind;
};

/** api@1.5 补记·三：POST /api/sessions/{id}/stop 返回。 */
export type SessionStopData = {
  session_id: string;
};

/** api@1.5 §7.3 */
export type SessionData = {
  session_id: string;
  subject_id: string;
  kind: SessionKind;
  status: SessionStatus;
  capture_status: CaptureStatus | null;
  coverage: Coverage | null;
  face_available: boolean;
  audio_available: boolean;
  duration_sec: number | null;
  captured_at: string | null;
  analysis_status: AnalysisStatus;
  codes: string[];
  created_at: string;
  updated_at: string;
};

/** api@1.5 §7.4 */
export type SessionAnalysisData = {
  session_id: string;
  analysis_status: "done" | "degraded";
  review_id: string;
  review_created: boolean;
  ticket_id: string | null;
};

/* ---------- 用户端 feedback ---------- */

export type Suggestion = "keep_routine" | "talk_to_staff" | "recapture";

/** api@1.5 §7.8，只允许这四个业务字段 + session_id/status */
export type FeedbackData = {
  session_id: string;
  status: SessionStatus;
  summary_text: string;
  suggestion: Suggestion;
  next_action: string;
};

/* ---------- 管理端 ---------- */

export type SubjectOverdue = Record<SessionKind, boolean>;

/** api@1.5 §7.6 与补记·二：对象列表、详情共用摘要。 */
export type SubjectListItem = {
  subject_id: string;
  code: string;
  name: string;
  status: string;
  latest_color: Color | null;
  latest_color_at: string | null;
  latest_rules: string[];
  pending_tickets: number;
  latest_session_at: string | null;
  checkin_interval_days: number;
  report_interval_days: number;
  overdue: SubjectOverdue;
};

export type Gender = "male" | "female" | "unknown";

/** 原型扩展档案字段：db@1.5 / api@1.5 尚未定义性别、年龄、身份证号等，联调前需补契约。 */
export type SubjectProfileFields = {
  gender: Gender | null;
  age: number | null;
  id_card: string | null;
  phone: string | null;
  address: string | null;
  correction_type: string | null;
  start_date: string | null;
  end_date: string | null;
};

export type SubjectDetail = SubjectListItem & SubjectProfileFields;


export type SubjectFrequencyPayload = {
  checkin_interval_days?: number;
  report_interval_days?: number;
};

export type SubjectFrequencyData = {
  subject_id: string;
  checkin_interval_days: number;
  report_interval_days: number;
};

/** api@1.5 §7.7；kind 用于区分签到与思想汇报。 */
export type AdminSessionItem = {
  session_id: string;
  subject_id: string;
  kind: SessionKind;
  status: SessionStatus;
  capture_status: CaptureStatus | null;
  coverage: Coverage | null;
  analysis_status: AnalysisStatus;
  captured_at: string | null;
};

export type TicketDetailJson = {
  overdue_kind?: SessionKind;
  overdue_days?: number;
};

/** ui@1.2 §4.4；逾期任务无复盘色码，且可不设截止时间。 */
export type TicketListItem = {
  ticket_id: string;
  subject_id: string;
  subject_name: string | null;
  priority: string;
  final_color: Color | null;
  triggered_rules: string[];
  opened_at: string;
  due_at: string | null;
  status: string;
  detail_json: TicketDetailJson | null;
};

/** ui@1.2 §4.5 证据链表格列，字段沿用 api@1.5 §7.9 evidence */
export type EvidenceRow = {
  rule_id: string;
  field_path: string;
  observed_value: string | number;
  threshold_key: string;
  threshold_value: string | number;
  session_id: string;
};

export type TicketHistoryItem = {
  action: string;
  actor: string;
  note: string | null;
  at: string;
};

export type TicketDetail = TicketListItem & {
  rules_fired: string[];
  suggested_method: string | null;
  evidence: EvidenceRow[];
  history: TicketHistoryItem[];
};

export type TicketAction = "confirm" | "correct" | "close";

export type TransitionPayload = {
  action: TicketAction;
  conclusion_color?: Color;
  note?: string;
  assignee?: string;
};

/** api@1.5 §7.10 */
export type TransitionResult = {
  ticket_id: string;
  status: string;
  previous_status: string;
  action: TicketAction;
  conclusion_color: Color | null;
  conclusion_note: string | null;
  assignee: string | null;
  closed_at: string | null;
};

/** api@1.5 §7.9 */
export type ReviewEvidence = {
  rule_id: string;
  rule_version: string;
  field_path: string;
  observed_value: string | number;
  threshold_key: string;
  threshold_value: string | number;
  offset_score: number;
  session_id: string;
  window: [string, string];
  triggered_at: string;
};

export type ReviewDetail = {
  review_id: string;
  subject_id: string;
  window_start: string;
  window_end: string;
  window_days: number;
  single_session_risk: string;
  trend_color: Color;
  final_color: Color;
  consistency: string;
  manual_review: boolean;
  rules_fired: string[];
  grading_version: string;
  evidence: ReviewEvidence[];
  created_at: string;
};

/* ---------- 管理端 · 思想汇报同步（api@1.5 §7.15–7.17） ---------- */

/** §7.15 / §7.16 列表项；列表不返回转写与情绪片段。 */
export type SensevoiceSyncItem = {
  sync_id: string;
  subject_id: string;
  session_id: string;
  status: string;
  provider: string;
  emotion_primary: string | null;
  emotion_confidence: number | null;
  data_version: string;
  operator: string;
  created_at: string;
};

/** §7.16 分页结构 */
export type SensevoiceSyncList = Paged<SensevoiceSyncItem>;

/** db@1.5 §7.1 情绪片段 */
export type SensevoiceEmotionTrigger = {
  text: string;
  label: string;
  start_sec: number;
  end_sec: number;
};

/** db@1.5 §7.1 emotion_json 解析结果 */
export type SensevoiceEmotion = {
  schema_version: string;
  primary: string;
  confidence: number;
  scores: Record<string, number>;
  triggers: SensevoiceEmotionTrigger[];
};

/** §7.17 同步详情：列表字段 + 转写全文 + 情绪报告（读取留痕）。 */
export type SensevoiceSyncDetail = SensevoiceSyncItem & {
  transcript_text: string;
  transcript_language: string | null;
  emotion: SensevoiceEmotion | null;
  updated_at: string;
};

/** api@1.5 §7.11 与补记·二 */
export type DashboardData = {
  subject_id: string;
  color_distribution: Record<Color, number>;
  trend_7d: { date: string; color: Color }[];
  pending_tickets: number;
  last_session_at: string | null;
  overdue: SubjectOverdue;
};

/* ---------- 管理端 · 对象心理状态趋势（api@1.5 §7.18） ----------
 * 字段逐字对齐契约，snake_case 不做前端改名。
 */

/** 当日复盘（`reviews.window_end == date`，至多一条）。 */
export type TrendReview = {
  color: Color;
  review_id: string;
  rules_fired: string[];
  consistency: string;
  manual_review: boolean;
  evidence_available: boolean;
};

/** 文本指标统计：`count < 2` 时 `std` 为 null，`count = 0` 时 `mean` 为 null。 */
export type TrendStat = {
  mean: number | null;
  std: number | null;
  count: number;
};

export type TrendSessionCounts = {
  total: number;
  checkin: number;
  report: number;
  analyzed: number;
  failed: number;
};

export type TrendConsistency = {
  degraded: number;
  low: number;
  conflict: number;
};

export type TrendBehaviorKind = {
  expected: boolean;
  completed: boolean;
  overdue: boolean;
};

export type TrendBehaviorState = {
  checkin: TrendBehaviorKind;
  report: TrendBehaviorKind;
};

export type TrendDay = {
  date: string;
  review: TrendReview | null;
  analysis_risk_level: string | null;
  sessions: TrendSessionCounts;
  text_valence: TrendStat;
  text_signal: TrendStat;
  consistency: TrendConsistency;
  behavior: TrendBehaviorState;
};

export type TrendScatterPoint = {
  date: string;
  session_id: string;
  captured_at: string;
  kind: string;
  valence: number;
  signal: number;
  arousal: number | null;
  emotion_label: string | null;
  review_color: Color | null;
  review_rules: string[];
  review_id: string | null;
};

export type TrendQuadrants = {
  q1: number;
  q2: number;
  q3: number;
  q4: number;
};

export type TrendSummary = {
  analyzed_count: number;
  avg_valence: number | null;
  avg_signal: number | null;
  valence_std: number | null;
  signal_std: number | null;
  coverage_rate: number;
  quadrants: TrendQuadrants;
  signals: string[];
};

export type SubjectTrends = {
  subject_id: string;
  start_date: string;
  end_date: string;
  interval_days: { checkin: number; report: number };
  days: TrendDay[];
  scatter_points: TrendScatterPoint[];
  summary: TrendSummary;
  degraded: string[];
};

/* ---------- 管理端 · 按日期的打卡影像与思想汇报录音 ----------
 * 原型扩展：api@1.5 明确不返回音频与原始影像，联调前需补契约与留痕规则。
 */

export type DailyCheckinMedia = {
  checkin_id: string;
  captured_at: string;
  image_url: string | null;
  capture_status: CaptureStatus | null;
};

export type DailyReportMedia = {
  report_id: string;
  submitted_at: string;
  duration_sec: number | null;
  audio_url: string | null;
};

export type DailyMedia = {
  date: string;
  checkin: DailyCheckinMedia | null;
  report: DailyReportMedia | null;
};

export type SubjectMediaData = {
  subject_id: string;
  date: string;
  available_dates: string[];
  item: DailyMedia | null;
};

