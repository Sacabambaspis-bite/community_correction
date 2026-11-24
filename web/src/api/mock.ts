/* 本地 mock：api@1.5 §8 规定假数据放 web/src/mock/。
 * 按 method + path 分发，字段取自各端点示例；写操作只在内存生效，不持久化。
 */
import dashboardMock from "../mock/dashboard.json";
import reviewMock from "../mock/review.json";
import sessionMock from "../mock/session.json";
import subjectMock from "../mock/subject.json";
import ticketMock from "../mock/ticket.json";
import { SUBJECT_ID } from "../lib/env";
import type {
  AdminSessionItem,
  ConsentData,
  DashboardData,
  Envelope,
  FeedbackData,
  Paged,
  ReviewDetail,
  SessionCreateData,
  SessionData,
  SubjectListItem,
  TicketDetail,
  TicketListItem,
  TransitionPayload,
  TransitionResult,
} from "./types";

type MockOptions = {
  method?: string;
  query?: Record<string, string | number | boolean | null | undefined>;
  body?: unknown;
};

const subjects = subjectMock as unknown as Paged<SubjectListItem>;
const sessions = sessionMock as unknown as {
  detail: SessionData;
  failed: SessionData;
  admin_list: Paged<AdminSessionItem>;
  feedback: FeedbackData;
};
const tickets = ticketMock as unknown as {
  list: Paged<TicketListItem>;
  detail: TicketDetail;
  transition: TransitionResult;
};
const dashboard = dashboardMock as unknown as DashboardData;
const review = reviewMock as unknown as ReviewDetail;

const SESSION_MOCK_DELAY_MS = 1200;

let requestSeq = 0;
let consentState: ConsentData = {
  subject_id: SUBJECT_ID,
  general: { granted: false, at: null },
  face: { granted: false, at: null },
  audio: { granted: false, at: null },
  revoked_at: null,
  retention_days: null,
};
const startedAt = new Map<string, number>();

function now(): string {
  return new Date().toISOString();
}

function requestId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  requestSeq += 1;
  return `mock-${requestSeq}`;
}

function ok<T>(data: unknown, degraded: string[] = []): Envelope<T> {
  return {
    code: 0,
    message: "ok",
    data: data as T,
    degraded,
    request_id: requestId(),
  };
}

function fail<T>(code: number, message: string): Envelope<T> {
  return {
    code,
    message,
    data: null,
    degraded: [],
    request_id: requestId(),
  };
}

function textQuery(options: MockOptions, key: string): string {
  const value = options.query?.[key];
  return value === undefined || value === null ? "" : String(value);
}

function createdSession(id: string): SessionData {
  const at = now();
  return {
    session_id: id,
    subject_id: SUBJECT_ID,
    status: "created",
    capture_status: null,
    coverage: null,
    face_available: false,
    audio_available: false,
    duration_sec: null,
    captured_at: null,
    analysis_status: "pending",
    codes: [],
    created_at: at,
    updated_at: at,
  };
}

function createdFeedback(id: string): FeedbackData {
  return {
    session_id: id,
    status: "created",
    summary_text: "本次记录仍在进行中。",
    suggestion: "keep_routine",
    next_action: "请稍候，完成后可查看结果",
  };
}

export async function mockRequest<T>(
  path: string,
  options: MockOptions = {},
): Promise<Envelope<T>> {
  const method = (options.method ?? "GET").toUpperCase();
  const subjectId = textQuery(options, "subject_id") || SUBJECT_ID;

  /* ---------- 公共 ---------- */
  if (method === "GET" && path === "/api/health") {
    return ok<T>({ status: "ok" });
  }

  /* ---------- 用户端 consent ---------- */
  if (path === "/api/user/consent" && method === "GET") {
    return ok<T>({ ...consentState, subject_id: subjectId });
  }

  if (path === "/api/user/consent" && method === "PUT") {
    const body = (options.body ?? {}) as {
      subject_id?: string;
      face?: boolean;
      audio?: boolean;
      retention_days?: number;
    };
    if (!body.face && !body.audio) {
      return fail<T>(1001, "invalid_consent");
    }
    const at = now();
    consentState = {
      subject_id: body.subject_id ?? SUBJECT_ID,
      general: { granted: Boolean(body.face || body.audio), at },
      face: { granted: Boolean(body.face), at: body.face ? at : null },
      audio: { granted: Boolean(body.audio), at: body.audio ? at : null },
      revoked_at: null,
      retention_days: body.retention_days ?? null,
    };
    return ok<T>(consentState);
  }

  if (path === "/api/user/consent/revoke" && method === "POST") {
    if (!consentState.general.granted) {
      return fail<T>(1005, "consent_not_granted");
    }
    consentState = { ...consentState, revoked_at: consentState.revoked_at ?? now() };
    return ok<T>(consentState);
  }

  /* ---------- 会话 ---------- */
  if (path === "/api/sessions" && method === "POST") {
    if (consentState.revoked_at) {
      return fail<T>(1005, "consent_revoked");
    }
    if (!consentState.general.granted) {
      return fail<T>(1005, "consent_required");
    }
    if (!consentState.face.granted || !consentState.audio.granted) {
      return fail<T>(1005, "consent_incomplete");
    }
    const body = (options.body ?? {}) as { session_id?: string };
    const sessionId = body.session_id ?? `mock-${requestId()}`;
    startedAt.set(sessionId, Date.now());
    const created: SessionCreateData = {
      session_id: sessionId,
      status: "created",
    };
    return ok<T>(created);
  }

  if (method === "GET" && /^\/api\/sessions\/[^/]+$/.test(path)) {
    const sessionId = path.split("/").pop() as string;
    const started = startedAt.get(sessionId);
    if (started !== undefined && Date.now() - started < SESSION_MOCK_DELAY_MS) {
      return ok<T>(createdSession(sessionId));
    }
    return ok<T>({ ...sessions.detail, session_id: sessionId, subject_id: subjectId }, [
      "capture",
    ]);
  }

  /* ---------- 用户端 feedback ---------- */
  if (method === "GET" && /^\/api\/user\/sessions\/[^/]+\/feedback$/.test(path)) {
    const sessionId = path.split("/")[4];
    const started = startedAt.get(sessionId);
    if (started !== undefined && Date.now() - started < SESSION_MOCK_DELAY_MS) {
      return ok<T>(createdFeedback(sessionId));
    }
    return ok<T>({ ...sessions.feedback, session_id: sessionId }, ["capture"]);
  }

  /* ---------- 管理端 ---------- */
  if (path === "/api/admin/subjects" && method === "GET") {
    const keyword = textQuery(options, "keyword").trim();
    const status = textQuery(options, "status");
    let items = subjects.items;
    if (keyword) {
      items = items.filter(
        (item) => item.code.includes(keyword) || item.name.includes(keyword),
      );
    }
    if (status) {
      items = items.filter((item) => item.status === status);
    }
    return ok<T>({
      items,
      page: 1,
      page_size: subjects.page_size,
      total: items.length,
    });
  }

  if (path === "/api/admin/sessions" && method === "GET") {
    const subjectIdFilter = textQuery(options, "subject_id");
    const status = textQuery(options, "status");
    let items = sessions.admin_list.items;
    if (subjectIdFilter) {
      items = items.filter((item) => item.subject_id === subjectIdFilter);
    }
    if (status) {
      items = items.filter((item) => item.status === status);
    }
    return ok<T>({
      items,
      page: 1,
      page_size: sessions.admin_list.page_size,
      total: items.length,
    });
  }

  if (path === "/api/admin/tickets" && method === "GET") {
    const status = textQuery(options, "status");
    const priority = textQuery(options, "priority");
    const subjectIdFilter = textQuery(options, "subject_id");
    let items = tickets.list.items;
    if (status) {
      items = items.filter((item) => item.status === status);
    }
    if (priority) {
      items = items.filter((item) => item.priority === priority);
    }
    if (subjectIdFilter) {
      items = items.filter((item) => item.subject_id === subjectIdFilter);
    }
    return ok<T>({
      items,
      page: 1,
      page_size: tickets.list.page_size,
      total: items.length,
    });
  }

  if (method === "GET" && /^\/api\/admin\/tickets\/[^/]+$/.test(path)) {
    const ticketId = path.split("/").pop() as string;
    return ok<T>({ ...tickets.detail, ticket_id: ticketId });
  }

  if (method === "POST" && /^\/api\/admin\/tickets\/[^/]+\/transition$/.test(path)) {
    const segments = path.split("/");
    const ticketId = segments[4];
    const payload = (options.body ?? {}) as TransitionPayload;
    if (!["confirm", "correct", "close"].includes(payload.action)) {
      return fail<T>(1001, "invalid_action");
    }
    if (payload.action === "correct" && (!payload.conclusion_color || !payload.note)) {
      return fail<T>(1001, "invalid_transition");
    }
    if (payload.action === "close" && !payload.note) {
      return fail<T>(1001, "invalid_transition");
    }
    const status = payload.action === "confirm" ? "confirmed" : "closed";
    const result: TransitionResult = {
      ...tickets.transition,
      ticket_id: ticketId,
      status,
      previous_status: "pending",
      action: payload.action,
      conclusion_color: payload.conclusion_color ?? null,
      conclusion_note: payload.note ?? null,
      assignee: payload.assignee ?? null,
      closed_at: status === "closed" ? now() : null,
    };
    return ok<T>(result);
  }

  if (path === "/api/admin/dashboard" && method === "GET") {
    return ok<T>(dashboard);
  }

  if (method === "GET" && /^\/api\/admin\/reviews\/[^/]+$/.test(path)) {
    const reviewId = path.split("/").pop() as string;
    return ok<T>({ ...review, review_id: reviewId });
  }

  if (method === "GET" && /^\/api\/admin\/sessions\/[^/]+\/face$/.test(path)) {
    return fail<T>(5000, "mock_not_supported");
  }

  return fail<T>(1004, "not_found");
}
