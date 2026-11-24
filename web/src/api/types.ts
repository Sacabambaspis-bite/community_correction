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

/** api@1.5 §7.2 POST 返回 */
export type SessionCreateData = {
  session_id: string;
  status: "created";
};

/** api@1.5 §7.3 */
export type SessionData = {
  session_id: string;
  subject_id: string;
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

/** api@1.5 §7.6 */
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
};

/** api@1.5 §7.7 */
export type AdminSessionItem = {
  session_id: string;
  subject_id: string;
  status: SessionStatus;
  capture_status: CaptureStatus | null;
  coverage: Coverage | null;
  analysis_status: AnalysisStatus;
  captured_at: string | null;
};

/** ui@1.2 §4.4 列表列 + ticket_id；api@1.5 尚无 tickets 列表示例 */
export type TicketListItem = {
  ticket_id: string;
  subject_id: string;
  subject_name: string | null;
  priority: string;
  final_color: Color;
  triggered_rules: string[];
  opened_at: string;
  due_at: string;
  status: string;
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

/** api@1.5 无工单详情示例，按 ui@1.2 §4.5 区块推导 */
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

/** api@1.5 §7.11 */
export type DashboardData = {
  subject_id: string;
  color_distribution: Record<Color, number>;
  trend_7d: { date: string; color: Color }[];
  pending_tickets: number;
  last_session_at: string | null;
};
