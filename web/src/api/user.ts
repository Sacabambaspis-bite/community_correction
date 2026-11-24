/* 用户端接口封装，路径与字段对齐 api@1.5 §5.3 / §7。 */
import { request } from "../lib/http";
import { SUBJECT_ID } from "../lib/env";
import type {
  ConsentData,
  Envelope,
  FeedbackData,
  SessionCreateData,
  SessionData,
} from "./types";

export type ConsentPayload = {
  face: boolean;
  audio: boolean;
  retention_days: number;
};

export type CreateSessionPayload = {
  device_index?: number;
  duration_sec?: number;
};

export function getConsent(
  subjectId: string = SUBJECT_ID,
): Promise<Envelope<ConsentData>> {
  return request<ConsentData>("/api/user/consent", {
    role: "user",
    query: { subject_id: subjectId },
  });
}

export function putConsent(
  payload: ConsentPayload,
  subjectId: string = SUBJECT_ID,
): Promise<Envelope<ConsentData>> {
  return request<ConsentData>("/api/user/consent", {
    method: "PUT",
    role: "user",
    body: { subject_id: subjectId, ...payload },
  });
}

export function revokeConsent(
  subjectId: string = SUBJECT_ID,
): Promise<Envelope<ConsentData>> {
  return request<ConsentData>("/api/user/consent/revoke", {
    method: "POST",
    role: "user",
    body: { subject_id: subjectId },
  });
}

export function createSession(
  payload: CreateSessionPayload = {},
  subjectId: string = SUBJECT_ID,
): Promise<Envelope<SessionCreateData>> {
  return request<SessionCreateData>("/api/sessions", {
    method: "POST",
    role: "user",
    body: { subject_id: subjectId, ...payload },
  });
}

/** 返回完整信封：采集失败时 code=2001 仍携带会话摘要。 */
export function getSession(
  sessionId: string,
  subjectId: string = SUBJECT_ID,
): Promise<Envelope<SessionData>> {
  return request<SessionData>(`/api/sessions/${sessionId}`, {
    role: "user",
    query: { subject_id: subjectId },
  });
}

export function getFeedback(
  sessionId: string,
  subjectId: string = SUBJECT_ID,
): Promise<Envelope<FeedbackData>> {
  return request<FeedbackData>(`/api/user/sessions/${sessionId}/feedback`, {
    role: "user",
    query: { subject_id: subjectId },
  });
}
