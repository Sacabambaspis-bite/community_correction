/* 管理端接口封装，路径与字段对齐 api@1.5 §5.4 / §7。
 * tickets / reviews / dashboard 端点尚未实现，页面先按 mock 跑通。
 */
import { request } from "../lib/http";
import { API_BASE_URL, USE_MOCK } from "../lib/env";
import type {
  AdminSessionItem,
  DashboardData,
  Envelope,
  Paged,
  ReviewDetail,
  SensevoiceSyncDetail,
  SensevoiceSyncItem,
  SensevoiceSyncList,
  SubjectDetail,
  SubjectFrequencyData,
  SubjectFrequencyPayload,
  SubjectListItem,
  SubjectMediaData,
  SubjectTrends,
  TicketDetail,
  TicketListItem,
  TransitionPayload,
  TransitionResult,
} from "./types";

export type SubjectQuery = {
  keyword?: string;
  status?: string;
  page?: number;
  page_size?: number;
};

export type AdminSessionQuery = {
  subject_id?: string;
  status?: string;
  page?: number;
  page_size?: number;
};

export type TicketQuery = {
  status?: string;
  priority?: string;
  subject_id?: string;
  page?: number;
  page_size?: number;
};

export function getSubjects(
  query: SubjectQuery = {},
): Promise<Envelope<Paged<SubjectListItem>>> {
  return request<Paged<SubjectListItem>>("/api/admin/subjects", {
    role: "admin",
    query,
  });
}

export function getSubject(
  subjectId: string,
): Promise<Envelope<SubjectDetail>> {
  return request<SubjectDetail>(`/api/admin/subjects/${encodeURIComponent(subjectId)}`, {
    role: "admin",
  });
}

export function updateFrequency(
  subjectId: string,
  payload: SubjectFrequencyPayload,
): Promise<Envelope<SubjectFrequencyData>> {
  return request<SubjectFrequencyData>(
    `/api/admin/subjects/${encodeURIComponent(subjectId)}/frequency`,
    {
      method: "PATCH",
      role: "admin",
      body: payload,
    },
  );
}

export function getSessions(
  query: AdminSessionQuery = {},
): Promise<Envelope<Paged<AdminSessionItem>>> {
  return request<Paged<AdminSessionItem>>("/api/admin/sessions", {
    role: "admin",
    query,
  });
}

export function getTickets(
  query: TicketQuery = {},
): Promise<Envelope<Paged<TicketListItem>>> {
  return request<Paged<TicketListItem>>("/api/admin/tickets", {
    role: "admin",
    query,
  });
}

export function getTicket(
  ticketId: string,
): Promise<Envelope<TicketDetail>> {
  return request<TicketDetail>(`/api/admin/tickets/${ticketId}`, {
    role: "admin",
  });
}

export function transitionTicket(
  ticketId: string,
  payload: TransitionPayload,
): Promise<Envelope<TransitionResult>> {
  return request<TransitionResult>(`/api/admin/tickets/${ticketId}/transition`, {
    method: "POST",
    role: "admin",
    body: payload,
  });
}

export function getDashboard(
  subjectId?: string,
): Promise<Envelope<DashboardData>> {
  return request<DashboardData>("/api/admin/dashboard", {
    role: "admin",
    query: subjectId ? { subject_id: subjectId } : {},
  });
}

/** 原型扩展：按日期读取打卡影像与思想汇报录音（契约未定义，mock 提供演示数据）。 */
export function getSubjectMedia(
  subjectId: string,
  date?: string,
): Promise<Envelope<SubjectMediaData>> {
  return request<SubjectMediaData>(
    `/api/admin/subjects/${encodeURIComponent(subjectId)}/media`,
    {
      role: "admin",
      query: date ? { date } : {},
    },
  );
}

/** api@1.5 §7.18：对象心理状态趋势，任意日期区间（缺省近 14 天）。 */
export function getSubjectTrends(
  subjectId: string,
  startDate?: string,
  endDate?: string,
): Promise<Envelope<SubjectTrends>> {
  const query: Record<string, string> = {};
  if (startDate) {
    query.start_date = startDate;
  }
  if (endDate) {
    query.end_date = endDate;
  }
  return request<SubjectTrends>(
    `/api/admin/subjects/${encodeURIComponent(subjectId)}/trends`,
    {
      role: "admin",
      query,
    },
  );
}

export function getReview(reviewId: string): Promise<Envelope<ReviewDetail>> {
  return request<ReviewDetail>(`/api/admin/reviews/${reviewId}`, {
    role: "admin",
  });
}

/** api@1.5 §7.15：触发思想汇报转写 + 情绪同步（缺省取最近一次可用汇报会话）。 */
export function syncSensevoice(
  subjectId: string,
  sessionId?: string,
): Promise<Envelope<SensevoiceSyncItem>> {
  return request<SensevoiceSyncItem>(
    `/api/admin/subjects/${encodeURIComponent(subjectId)}/sensevoice-sync`,
    {
      method: "POST",
      role: "admin",
      body: sessionId ? { session_id: sessionId } : {},
    },
  );
}

/** api@1.5 §7.16：同步记录列表，按 created_at 倒序。 */
export function getSensevoiceSyncs(
  subjectId: string,
  page = 1,
  pageSize = 20,
): Promise<Envelope<SensevoiceSyncList>> {
  return request<SensevoiceSyncList>(
    `/api/admin/subjects/${encodeURIComponent(subjectId)}/sensevoice-syncs`,
    {
      role: "admin",
      query: { page, page_size: pageSize },
    },
  );
}

/** api@1.5 §7.17：同步详情，读取即写 sensitive.view 留痕，仅由用户点击触发。 */
export function getSensevoiceSync(
  syncId: string,
): Promise<Envelope<SensevoiceSyncDetail>> {
  return request<SensevoiceSyncDetail>(
    `/api/admin/sensevoice-syncs/${encodeURIComponent(syncId)}`,
    { role: "admin" },
  );
}

/** 面部图为二进制端点，不走 fetch 封装；mock 模式下不发起请求。 */
export function faceImageUrl(sessionId: string): string | null {
  if (USE_MOCK) {
    return null;
  }
  return `${API_BASE_URL}/api/admin/sessions/${sessionId}/face`;
}
