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
  SubjectDetail,
  SubjectFrequencyData,
  SubjectFrequencyPayload,
  SubjectListItem,
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

export function getDashboard(): Promise<Envelope<DashboardData>> {
  return request<DashboardData>("/api/admin/dashboard", { role: "admin" });
}

export function getReview(reviewId: string): Promise<Envelope<ReviewDetail>> {
  return request<ReviewDetail>(`/api/admin/reviews/${reviewId}`, {
    role: "admin",
  });
}

/** 面部图为二进制端点，不走 fetch 封装；mock 模式下不发起请求。 */
export function faceImageUrl(sessionId: string): string | null {
  if (USE_MOCK) {
    return null;
  }
  return `${API_BASE_URL}/api/admin/sessions/${sessionId}/face`;
}
