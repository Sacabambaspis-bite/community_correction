/* 统一请求层：带 Authorization、解析信封、code != 0 抛 ApiError。
 * mock 模式（VITE_USE_MOCK != 0）交由 api/mock.ts 返回本地假数据。
 */
import { mockRequest } from "../api/mock";
import type { Envelope } from "../api/types";
import { ADMIN_TOKEN, API_BASE_URL, USE_MOCK, USER_TOKEN } from "./env";

export type ApiRole = "user" | "admin";

export type RequestOptions = {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  query?: Record<string, string | number | boolean | null | undefined>;
  body?: unknown;
  role?: ApiRole;
};

export class ApiError extends Error {
  readonly code: number;
  readonly requestId: string;
  readonly degraded: string[];

  constructor(envelope: Envelope<unknown>) {
    super(envelope.message);
    this.name = "ApiError";
    this.code = envelope.code;
    this.requestId = envelope.request_id;
    this.degraded = envelope.degraded;
  }
}

function buildUrl(
  path: string,
  query?: RequestOptions["query"],
): string {
  const search = new URLSearchParams();
  Object.entries(query ?? {}).forEach(([key, value]) => {
    if (value === undefined || value === null || value === "") {
      return;
    }
    search.set(key, String(value));
  });
  const suffix = search.toString();
  return `${API_BASE_URL}${path}${suffix ? `?${suffix}` : ""}`;
}

async function fetchEnvelope<T>(
  path: string,
  options: RequestOptions,
): Promise<Envelope<T>> {
  const token = options.role === "admin" ? ADMIN_TOKEN : USER_TOKEN;
  const headers: Record<string, string> = {
    Accept: "application/json",
    Authorization: `Bearer ${token}`,
  };
  const init: RequestInit = { method: options.method ?? "GET", headers };
  if (options.body !== undefined) {
    headers["Content-Type"] = "application/json";
    init.body = JSON.stringify(options.body);
  }

  const response = await fetch(buildUrl(path, options.query), init);
  const fallbackRequestId = response.headers.get("X-Request-Id") ?? "";
  try {
    return (await response.json()) as Envelope<T>;
  } catch {
    throw new ApiError({
      code: 5000,
      message: "invalid_response",
      data: null,
      degraded: [],
      request_id: fallbackRequestId,
    });
  }
}

/** 返回完整信封，供需要读取 2001/2003 附带 data 的页面使用。 */
export async function request<T>(
  path: string,
  options: RequestOptions = {},
): Promise<Envelope<T>> {
  if (USE_MOCK) {
    return mockRequest<T>(path, options);
  }
  return fetchEnvelope<T>(path, options);
}

/** 成功时直接返回 data，code != 0 抛 ApiError（统一错误提示用）。 */
export async function requestData<T>(
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const envelope = await request<T>(path, options);
  if (envelope.code !== 0 || envelope.data === null) {
    throw new ApiError(envelope);
  }
  return envelope.data;
}
