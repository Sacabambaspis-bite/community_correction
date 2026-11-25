/* 本地 mock：api@1.5 §8 规定假数据放 web/src/mock/。
 * 按 method + path 分发，字段取自各端点示例；写操作只在内存生效，不持久化。
 */
import dashboardMock from "../mock/dashboard.json";
import reviewMock from "../mock/review.json";
import sessionMock from "../mock/session.json";
import subjectMock from "../mock/subject.json";
import ticketMock from "../mock/ticket.json";
import trendMock from "../mock/trend.json";
import { SUBJECT_ID } from "../lib/env";
import type {
  AdminSessionItem,
  AiAssistStatus,
  CaptureStatus,
  ConsentData,
  DailyMedia,
  DashboardData,
  Envelope,
  FeedbackData,
  Paged,
  ReviewDetail,
  SessionCreateData,
  SessionData,
  SessionKind,
  SubjectDetail,
  SubjectFrequencyData,
  SubjectFrequencyPayload,
  SubjectListItem,
  SubjectProfileFields,
  SubjectTrends,
  TicketDetail,
  TicketListItem,
  TransitionPayload,
  TransitionResult,
  UserTaskData,
  UserTasksData,
} from "./types";

type MockOptions = {
  method?: string;
  query?: Record<string, string | number | boolean | null | undefined>;
  body?: unknown;
};

type RawDailyMedia = {
  date: string;
  checkin: {
    checkin_id: string;
    captured_at: string;
    capture_status: CaptureStatus | null;
    image_prompt: string | null;
  } | null;
  report: {
    report_id: string;
    submitted_at: string;
    duration_sec: number | null;
    audio_available: boolean;
  } | null;
};

type SubjectMockFile = Paged<SubjectListItem> & {
  profiles: Record<string, Partial<SubjectProfileFields>>;
  media: Record<string, RawDailyMedia[]>;
};

const subjects = subjectMock as unknown as SubjectMockFile;
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
const dashboardFile = dashboardMock as unknown as Omit<DashboardData, "overdue"> & {
  variants?: Record<string, Omit<DashboardData, "overdue">>;
};
const review = reviewMock as unknown as ReviewDetail;
/** 固定 14 天（2026-11-12 ~ 2026-11-25）；查询参数忽略，字段仍按 api@1.5 §7.18 完整返回。 */
const trend = trendMock as unknown as SubjectTrends;

const adminSessionItems: AdminSessionItem[] = [
  ...sessions.admin_list.items.map((item) => ({ ...item, kind: "report" as const })),
  {
    session_id: "6d4c2a90-1b3e-4f5a-8c7d-2e1f0a9b8c7d",
    subject_id: SUBJECT_ID,
    kind: "checkin",
    status: "captured",
    capture_status: "ok",
    coverage: "face_only",
    analysis_status: "done",
    captured_at: "2026-11-22T09:00:00+08:00",
  },
];

const mockTicketItems: TicketListItem[] = [
  ...tickets.list.items.map((item) => ({ ...item, detail_json: null })),
  {
    ticket_id: "7a1c4e20-8b3d-4f6a-9c2e-5d0f1b7a8e9c",
    subject_id: SUBJECT_ID,
    subject_name: "张某某",
    priority: "P0",
    final_color: null,
    triggered_rules: [],
    opened_at: "2026-11-24T08:00:00+08:00",
    due_at: null,
    status: "pending",
    detail_json: { overdue_kind: "report", overdue_days: 2 },
  },
];

const subjectFrequencies = new Map<string, SubjectFrequencyData>();

const SESSION_MOCK_DELAY_MS = 1200;

let requestSeq = 0;

/* Mock 模式下的同意状态持久化：刷新页面后仍能保持登录后的同意结果。 */
const MOCK_CONSENT_KEY = "cc.mock.consent";

function defaultConsent(): ConsentData {
  return {
    subject_id: SUBJECT_ID,
    general: { granted: false, at: null },
    face: { granted: false, at: null },
    audio: { granted: false, at: null },
    revoked_at: null,
    retention_days: null,
  };
}

function loadMockConsent(): ConsentData {
  try {
    const raw = window.localStorage.getItem(MOCK_CONSENT_KEY);
    if (!raw) {
      return defaultConsent();
    }
    const parsed = JSON.parse(raw) as ConsentData;
    if (
      parsed.subject_id !== SUBJECT_ID ||
      typeof parsed.general?.granted !== "boolean"
    ) {
      return defaultConsent();
    }
    return parsed;
  } catch {
    return defaultConsent();
  }
}

function saveMockConsent(state: ConsentData): void {
  try {
    window.localStorage.setItem(MOCK_CONSENT_KEY, JSON.stringify(state));
  } catch {
    // 存储不可用时仅影响刷新后的表现，不阻断本次操作。
  }
}

let consentState: ConsentData = loadMockConsent();
const startedAt = new Map<string, number>();
const stopRequestedAt = new Map<string, number>();
const manualSessionIds = new Set<string>();
const sessionStates = new Map<string, SessionData>();

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

function createdSession(
  id: string,
  kind: SessionKind,
  subjectId: string = SUBJECT_ID,
): SessionData {
  const at = now();
  return {
    session_id: id,
    subject_id: subjectId,
    kind,
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

function completedSession(
  id: string,
  subjectId: string,
  kind: SessionKind,
): SessionData {
  const existing = sessionStates.get(id);
  const at = now();
  if (kind === "checkin") {
    return {
      session_id: id,
      subject_id: subjectId,
      kind,
      status: "captured",
      capture_status: "ok",
      coverage: "face_only",
      face_available: true,
      audio_available: false,
      duration_sec: null,
      captured_at: at,
      analysis_status: "pending",
      codes: [],
      created_at: existing?.created_at ?? at,
      updated_at: at,
    };
  }

  const isNewSession = existing?.status === "created";
  return {
    ...sessions.detail,
    session_id: id,
    subject_id: subjectId,
    kind: "report",
    captured_at: isNewSession ? at : sessions.detail.captured_at,
    created_at: existing?.created_at ?? sessions.detail.created_at,
    updated_at: isNewSession ? at : sessions.detail.updated_at,
  };
}

function completedManualSession(id: string, subjectId: string): SessionData {
  const existing = sessionStates.get(id);
  const at = now();
  const started = startedAt.get(id) ?? Date.now();
  const stopped = stopRequestedAt.get(id) ?? Date.now();
  const durationSeconds = Math.max(
    0.1,
    Math.round(((stopped - started) / 1000) * 10) / 10,
  );
  return {
    session_id: id,
    subject_id: subjectId,
    kind: "report",
    status: "captured",
    capture_status: "ok",
    coverage: "both",
    face_available: true,
    audio_available: true,
    duration_sec: durationSeconds,
    captured_at: at,
    analysis_status: "pending",
    codes: [],
    created_at: existing?.created_at ?? new Date(started).toISOString(),
    updated_at: at,
  };
}

function sessionDegraded(session: SessionData): string[] {
  const flags: string[] = [];
  if (
    session.capture_status === "partial" ||
    session.capture_status === "no_face" ||
    session.capture_status === "no_audio" ||
    session.capture_status === "no_face_no_audio"
  ) {
    flags.push("capture");
  }
  if (session.analysis_status === "degraded") {
    flags.push("analysis");
  }
  return flags;
}

function sessionEnvelope<T>(session: SessionData): Envelope<T> {
  const degraded = sessionDegraded(session);
  if (session.status === "failed") {
    return {
      code: 2001,
      message: "capture_failed",
      data: session as T,
      degraded,
      request_id: requestId(),
    };
  }
  if (session.analysis_status === "failed") {
    return {
      code: 2003,
      message: "analysis_failed",
      data: session as T,
      degraded,
      request_id: requestId(),
    };
  }
  return ok<T>(session, degraded);
}

function frequencyState(subjectId: string): SubjectFrequencyData {
  const existing = subjectFrequencies.get(subjectId);
  if (existing) {
    return existing;
  }
  const created: SubjectFrequencyData = {
    subject_id: subjectId,
    checkin_interval_days: 1,
    report_interval_days: 3,
  };
  subjectFrequencies.set(subjectId, created);
  return created;
}

function allAdminSessions(): AdminSessionItem[] {
  const byId = new Map(adminSessionItems.map((item) => [item.session_id, item]));
  sessionStates.forEach((session) => {
    byId.set(session.session_id, {
      session_id: session.session_id,
      subject_id: session.subject_id,
      kind: session.kind,
      status: session.status,
      capture_status: session.capture_status,
      coverage: session.coverage,
      analysis_status: session.analysis_status,
      captured_at: session.captured_at,
    });
  });
  return [...byId.values()];
}

function subjectSummary(item: SubjectListItem): SubjectListItem {
  const frequency = frequencyState(item.subject_id);
  const tasks = mockTasks(item.subject_id);
  return {
    ...item,
    checkin_interval_days: frequency.checkin_interval_days,
    report_interval_days: frequency.report_interval_days,
    overdue:
      item.subject_id === SUBJECT_ID
        ? { checkin: tasks.checkin.overdue, report: tasks.report.overdue }
        : { checkin: true, report: true },
  };
}

function profileOf(subjectId: string): SubjectProfileFields {
  return {
    gender: null,
    age: null,
    id_card: null,
    phone: null,
    address: null,
    correction_type: null,
    start_date: null,
    end_date: null,
    ...subjects.profiles[subjectId],
  };
}

function dashboardFor(subjectId: string): Omit<DashboardData, "overdue"> {
  const variant = dashboardFile.variants?.[subjectId];
  if (variant) {
    return variant;
  }
  return {
    subject_id: subjectId,
    color_distribution: dashboardFile.color_distribution,
    trend_7d: dashboardFile.trend_7d,
    pending_tickets: dashboardFile.pending_tickets,
    last_session_at: dashboardFile.last_session_at,
  };
}

const mockAudioCache = new Map<string, string>();

function writeAscii(view: DataView, offset: number, text: string): void {
  for (let index = 0; index < text.length; index += 1) {
    view.setUint8(offset + index, text.charCodeAt(index));
  }
}

/** 原型占位录音：2 秒 8kHz 单声道提示音，仅用于演示音频播放器。 */
function mockAudioUrl(seed: string): string {
  const cached = mockAudioCache.get(seed);
  if (cached) {
    return cached;
  }
  const seconds = 2;
  const rate = 8000;
  const total = seconds * rate;
  const buffer = new ArrayBuffer(44 + total * 2);
  const view = new DataView(buffer);
  writeAscii(view, 0, "RIFF");
  view.setUint32(4, 36 + total * 2, true);
  writeAscii(view, 8, "WAVE");
  writeAscii(view, 12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, rate, true);
  view.setUint32(28, rate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  writeAscii(view, 36, "data");
  view.setUint32(40, total * 2, true);

  const baseFreq = 300 + (seed.charCodeAt(0) % 5) * 40;
  for (let index = 0; index < total; index += 1) {
    const time = index / rate;
    const envelope = Math.min(1, time * 8) * Math.max(0, 1 - time / seconds);
    const value = Math.sin(2 * Math.PI * baseFreq * time) * envelope * 0.18;
    view.setInt16(44 + index * 2, Math.round(value * 32767), true);
  }

  let binary = "";
  const bytes = new Uint8Array(buffer);
  for (let index = 0; index < bytes.length; index += 1) {
    binary += String.fromCharCode(bytes[index]);
  }
  const url = `data:audio/wav;base64,${btoa(binary)}`;
  mockAudioCache.set(seed, url);
  return url;
}

function mockImageUrl(prompt: string | null): string | null {
  if (!prompt) {
    return null;
  }
  return `https://trae-api-cn.mchost.guru/api/ide/v1/text_to_image?prompt=${encodeURIComponent(prompt)}&image_size=portrait_4_3`;
}

function dailyMediaOf(raw: RawDailyMedia): DailyMedia {
  return {
    date: raw.date,
    checkin: raw.checkin
      ? {
          checkin_id: raw.checkin.checkin_id,
          captured_at: raw.checkin.captured_at,
          capture_status: raw.checkin.capture_status,
          image_url: mockImageUrl(raw.checkin.image_prompt),
        }
      : null,
    report: raw.report
      ? {
          report_id: raw.report.report_id,
          submitted_at: raw.report.submitted_at,
          duration_sec: raw.report.duration_sec,
          audio_url: raw.report.audio_available
            ? mockAudioUrl(raw.report.report_id)
            : null,
        }
      : null,
  };
}

function taskState(subjectId: string, kind: SessionKind): UserTaskData {
  const history = allAdminSessions();
  let lastCompletedAt: string | null = null;
  let lastCompletedTime = Number.NEGATIVE_INFINITY;

  history.forEach((session) => {
    if (
      session.subject_id !== subjectId ||
      session.kind !== kind ||
      session.status !== "captured" ||
      session.captured_at === null
    ) {
      return;
    }
    const completedTime = Date.parse(session.captured_at);
    if (!Number.isNaN(completedTime) && completedTime > lastCompletedTime) {
      lastCompletedAt = session.captured_at;
      lastCompletedTime = completedTime;
    }
  });

  const frequency = frequencyState(subjectId);
  const intervalDays =
    kind === "checkin"
      ? frequency.checkin_interval_days
      : frequency.report_interval_days;
  return {
    interval_days: intervalDays,
    last_completed_at: lastCompletedAt,
    overdue:
      lastCompletedAt !== null &&
      Date.now() - lastCompletedTime > intervalDays * 24 * 60 * 60 * 1000,
  };
}

function mockTasks(subjectId: string): UserTasksData {
  return {
    checkin: taskState(subjectId, "checkin"),
    report: taskState(subjectId, "report"),
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

  /* ---------- 用户端任务与 consent ---------- */
  if (path === "/api/user/tasks" && method === "GET") {
    return ok<T>(mockTasks(subjectId));
  }

  if (path === "/api/user/consent" && method === "GET") {
    return ok<T>({ ...consentState, subject_id: subjectId });
  }

  if (path === "/api/user/consent" && method === "PUT") {
    const body = (options.body ?? {}) as {
      subject_id?: string;
      face?: boolean;
      audio?: boolean;
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
      retention_days: 180,
    };
    saveMockConsent(consentState);
    return ok<T>(consentState);
  }

  if (path === "/api/user/consent/revoke" && method === "POST") {
    if (!consentState.general.granted) {
      return fail<T>(1005, "consent_not_granted");
    }
    consentState = { ...consentState, revoked_at: consentState.revoked_at ?? now() };
    saveMockConsent(consentState);
    return ok<T>(consentState);
  }

  /* 用户端 AI 援助状态（api@1.5 §7.19）：mock 固定「未开通」，不伪造回答。 */
  if (path === "/api/user/ai-assist/status" && method === "GET") {
    const data: AiAssistStatus = {
      enabled: false,
      web_search: false,
      model: null,
      notice: "智能援助暂未开通，请联系工作人员",
    };
    return ok<T>(data);
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
    const body = (options.body ?? {}) as {
      session_id?: string;
      subject_id?: string;
      kind?: SessionKind;
      duration_sec?: number | null;
    };
    const sessionId = body.session_id ?? `mock-${requestId()}`;
    const sessionSubjectId = body.subject_id ?? SUBJECT_ID;
    const kind = body.kind ?? "report";
    const isManual =
      kind === "report" &&
      (body.duration_sec === undefined || body.duration_sec === null);
    startedAt.set(sessionId, Date.now());
    stopRequestedAt.delete(sessionId);
    if (isManual) {
      manualSessionIds.add(sessionId);
    } else {
      manualSessionIds.delete(sessionId);
    }
    sessionStates.set(
      sessionId,
      createdSession(sessionId, kind, sessionSubjectId),
    );
    const created: SessionCreateData = {
      session_id: sessionId,
      status: "created",
      kind,
    };
    return ok<T>(created);
  }

  if (method === "POST" && /^\/api\/sessions\/[^/]+\/stop$/.test(path)) {
    const sessionId = path.split("/")[3];
    const session = sessionStates.get(sessionId);
    if (!session) {
      return fail<T>(1004, "not_found");
    }
    const requestedSubjectId = textQuery(options, "subject_id");
    if (!requestedSubjectId) {
      return fail<T>(1001, "invalid_request");
    }
    if (session.subject_id !== requestedSubjectId) {
      return fail<T>(1003, "forbidden");
    }
    if (
      session.kind !== "report" ||
      session.status !== "created" ||
      !manualSessionIds.has(sessionId)
    ) {
      return fail<T>(1005, "session_not_stoppable");
    }
    if (!stopRequestedAt.has(sessionId)) {
      stopRequestedAt.set(sessionId, Date.now());
    }
    return ok<T>({ session_id: sessionId });
  }

  if (method === "GET" && /^\/api\/sessions\/[^/]+$/.test(path)) {
    const sessionId = path.split("/").pop() as string;
    const existing = sessionStates.get(sessionId);
    const started = startedAt.get(sessionId);
    if (existing && manualSessionIds.has(sessionId)) {
      if (existing.status !== "created") {
        return sessionEnvelope<T>(existing);
      }
      const stopped = stopRequestedAt.get(sessionId);
      if (
        stopped === undefined ||
        Date.now() - stopped < SESSION_MOCK_DELAY_MS
      ) {
        return sessionEnvelope<T>(existing);
      }
      const completed = completedManualSession(sessionId, existing.subject_id);
      sessionStates.set(sessionId, completed);
      return sessionEnvelope<T>(completed);
    }
    if (started !== undefined && Date.now() - started < SESSION_MOCK_DELAY_MS) {
      return sessionEnvelope<T>(
        existing ?? createdSession(sessionId, "report", subjectId),
      );
    }
    if (existing && existing.status !== "created") {
      return sessionEnvelope<T>(existing);
    }
    const completed = completedSession(
      sessionId,
      existing?.subject_id ?? subjectId,
      existing?.kind ?? "report",
    );
    sessionStates.set(sessionId, completed);
    return sessionEnvelope<T>(completed);
  }

  if (method === "POST" && /^\/api\/sessions\/[^/]+\/analyze$/.test(path)) {
    const sessionId = path.split("/")[3];
    const session = sessionStates.get(sessionId);
    if (!session || session.status === "created") {
      return fail<T>(4000, "session_not_captured");
    }
    if (session.status === "failed") {
      return fail<T>(2001, "capture_failed");
    }
    const analyzed: SessionData = { ...session, analysis_status: "done" };
    sessionStates.set(sessionId, analyzed);
    return ok<T>(
      {
        session_id: sessionId,
        analysis_status: "done",
        review_id: review.review_id,
        review_created: true,
        ticket_id: null,
      },
      sessionDegraded(analyzed),
    );
  }

  /* ---------- 用户端 feedback ---------- */
  if (method === "GET" && /^\/api\/user\/sessions\/[^/]+\/feedback$/.test(path)) {
    const sessionId = path.split("/")[4];
    const started = startedAt.get(sessionId);
    if (started !== undefined && Date.now() - started < SESSION_MOCK_DELAY_MS) {
      return ok<T>(createdFeedback(sessionId));
    }
    const session = sessionStates.get(sessionId);
    if (session?.kind === "checkin" && session.status === "captured") {
      const feedback: FeedbackData = {
        session_id: sessionId,
        status: "captured",
        summary_text: "本次签到已完成。",
        suggestion: "keep_routine",
        next_action: "下次按约定时间再来即可",
      };
      return ok<T>(feedback);
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
      items: items.map(subjectSummary),
      page: 1,
      page_size: subjects.page_size,
      total: items.length,
    });
  }

  if (
    method === "PATCH" &&
    /^\/api\/admin\/subjects\/[^/]+\/frequency$/.test(path)
  ) {
    const subjectId = decodeURIComponent(path.split("/")[4]);
    const subject = subjects.items.find((item) => item.subject_id === subjectId);
    if (!subject) {
      return fail<T>(1004, "not_found");
    }
    const payload = (options.body ?? {}) as SubjectFrequencyPayload;
    const checkin = payload.checkin_interval_days;
    const report = payload.report_interval_days;
    if (checkin === undefined && report === undefined) {
      return fail<T>(1001, "invalid_request");
    }
    if (
      (checkin !== undefined &&
        (!Number.isInteger(checkin) || checkin < 1)) ||
      (report !== undefined && (!Number.isInteger(report) || report < 1))
    ) {
      return fail<T>(1001, "invalid_request");
    }
    const previous = frequencyState(subjectId);
    const next: SubjectFrequencyData = {
      subject_id: subjectId,
      checkin_interval_days: checkin ?? previous.checkin_interval_days,
      report_interval_days: report ?? previous.report_interval_days,
    };
    subjectFrequencies.set(subjectId, next);
    return ok<T>(next);
  }

  /* 思想汇报同步（api@1.5 §7.15–7.17）：能力默认关闭，mock 不伪造转写/情绪结果。 */
  if (
    method === "POST" &&
    /^\/api\/admin\/subjects\/[^/]+\/sensevoice-sync$/.test(path)
  ) {
    return fail<T>(5001, "sensevoice_sync_disabled");
  }

  if (
    method === "GET" &&
    /^\/api\/admin\/subjects\/[^/]+\/sensevoice-syncs$/.test(path)
  ) {
    return ok<T>({
      items: [],
      page: Number(textQuery(options, "page")) || 1,
      page_size: Number(textQuery(options, "page_size")) || 20,
      total: 0,
    });
  }

  if (
    method === "GET" &&
    /^\/api\/admin\/sensevoice-syncs\/[^/]+$/.test(path)
  ) {
    return fail<T>(1004, "not_found");
  }

  /* 对象心理状态趋势（api@1.5 §7.18）：必须早于通用 /api/admin/subjects/{id} 分支，
   * 否则会被对象详情吞掉。start_date / end_date 可忽略，固定返回 14 天完整字段。 */
  if (
    method === "GET" &&
    /^\/api\/admin\/subjects\/[^/]+\/trends$/.test(path)
  ) {
    const subjectId = decodeURIComponent(path.split("/")[4]);
    return ok<T>({ ...trend, subject_id: subjectId });
  }

  if (
    method === "GET" &&
    /^\/api\/admin\/subjects\/[^/]+\/media$/.test(path)
  ) {
    const subjectId = decodeURIComponent(path.split("/")[4]);
    const rawDays = subjects.media[subjectId] ?? [];
    const availableDates = rawDays
      .map((day) => day.date)
      .sort((left, right) => right.localeCompare(left));
    const requestedDate = textQuery(options, "date") || availableDates[0] || "";
    const raw = rawDays.find((day) => day.date === requestedDate) ?? null;
    return ok<T>({
      subject_id: subjectId,
      date: requestedDate,
      available_dates: availableDates,
      item: raw ? dailyMediaOf(raw) : null,
    });
  }

  if (method === "GET" && /^\/api\/admin\/subjects\/[^/]+$/.test(path)) {
    const subjectId = decodeURIComponent(path.split("/")[4]);
    const subject = subjects.items.find((item) => item.subject_id === subjectId);
    if (!subject) {
      return fail<T>(1004, "not_found");
    }
    const detail: SubjectDetail = {
      ...subjectSummary(subject),
      ...profileOf(subjectId),
    };
    return ok<T>(detail);
  }

  if (path === "/api/admin/sessions" && method === "GET") {
    const subjectIdFilter = textQuery(options, "subject_id");
    const status = textQuery(options, "status");
    let items = allAdminSessions();
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
    let items = mockTicketItems;
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
    const item =
      mockTicketItems.find((ticket) => ticket.ticket_id === ticketId) ??
      ({ ...mockTicketItems[0], ticket_id: ticketId } as TicketListItem);
    const overdue = item.detail_json?.overdue_kind !== undefined;
    return ok<T>({
      ...tickets.detail,
      ...item,
      ticket_id: ticketId,
      rules_fired: item.triggered_rules,
      suggested_method: overdue ? "talk_to_staff" : tickets.detail.suggested_method,
      evidence: item.final_color === null ? [] : tickets.detail.evidence,
      detail_json: item.detail_json ?? null,
    });
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
    const requestedId = textQuery(options, "subject_id") || dashboardFile.subject_id;
    const base = dashboardFor(requestedId);
    const tasks = mockTasks(requestedId);
    return ok<T>({
      ...base,
      subject_id: requestedId,
      overdue: { checkin: tasks.checkin.overdue, report: tasks.report.overdue },
    });
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
