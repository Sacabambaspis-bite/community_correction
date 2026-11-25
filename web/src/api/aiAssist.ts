/* 用户端「AI 援助」接口（api@1.5 §7.19–§7.20）。
 * - status 走统一 request() 与 Envelope；
 * - chat 为 SSE，需直接用 fetch 读取 response.body，自行解析 event/data 行；
 * - mock 模式不发起真实请求，只回 notice + done，绝不生成模拟回答。
 */
import { API_BASE_URL, SUBJECT_ID, USE_MOCK, USER_TOKEN } from "../lib/env";
import { request } from "../lib/http";
import type {
  AiAssistEvent,
  AiAssistStatus,
  AiChatMessage,
  Envelope,
} from "./types";

/** 与后端 ai_assist.py 保持一致的中性提示。 */
export const AI_ASSIST_DISABLED_TEXT = "智能援助暂未开通，请联系工作人员";

export class AiStreamError extends Error {
  readonly code: number;

  constructor(code: number, message: string) {
    super(message);
    this.name = "AiStreamError";
    this.code = code;
  }
}

export function getAiAssistStatus(
  subjectId: string = SUBJECT_ID,
): Promise<Envelope<AiAssistStatus>> {
  return request<AiAssistStatus>("/api/user/ai-assist/status", {
    role: "user",
    query: { subject_id: subjectId },
  });
}

export type StreamAiAssistOptions = {
  signal?: AbortSignal;
  onEvent: (event: AiAssistEvent) => void;
};

/** mock：只发 notice(ai_not_configured) + done，不产生任何正文。 */
function mockStream({ signal, onEvent }: StreamAiAssistOptions): Promise<void> {
  return new Promise((resolve) => {
    window.setTimeout(() => {
      if (signal?.aborted) {
        resolve();
        return;
      }
      onEvent({
        type: "notice",
        code: "ai_not_configured",
        message: AI_ASSIST_DISABLED_TEXT,
      });
      onEvent({
        type: "done",
        finish_reason: "disabled",
        degraded: [],
        request_id: "mock-ai-assist",
      });
      resolve();
    }, 0);
  });
}

type Payload = Record<string, unknown>;

function asPayload(value: unknown): Payload {
  return value !== null && typeof value === "object" ? (value as Payload) : {};
}

function str(value: unknown): string {
  return typeof value === "string" ? value : "";
}

/** SSE event 名 → 前端事件；未知事件（含无类型的 message）返回 null 由调用方丢弃。 */
function toEvent(name: string, payload: unknown): AiAssistEvent | null {
  const data = asPayload(payload);
  switch (name) {
    case "meta":
      return {
        type: "meta",
        request_id: str(data.request_id),
        model: typeof data.model === "string" ? data.model : null,
        web_search: data.web_search === true,
        disclaimer: str(data.disclaimer),
      };
    case "delta":
      return typeof data.text === "string" ? { type: "delta", text: data.text } : null;
    case "citation": {
      const title = str(data.title);
      const url = str(data.url);
      if (!title || !url) {
        return null;
      }
      return {
        type: "citation",
        index: typeof data.index === "number" ? data.index : 0,
        title,
        url,
      };
    }
    case "notice":
      return {
        type: "notice",
        code: str(data.code),
        message: str(data.message),
      };
    case "done":
      return {
        type: "done",
        finish_reason: str(data.finish_reason),
        degraded: Array.isArray(data.degraded) ? data.degraded.map(String) : [],
        request_id: str(data.request_id),
      };
    case "error":
      return {
        type: "error",
        code: typeof data.code === "number" ? data.code : 5000,
        message: str(data.message),
        request_id: str(data.request_id),
      };
    // event 缺省即 message：仅兼容带 text 的载荷，其余丢弃，避免误渲染。
    case "message":
      return typeof data.text === "string" ? { type: "delta", text: data.text } : null;
    default:
      return null;
  }
}

async function readEnvelopeError(response: Response): Promise<AiStreamError> {
  try {
    const body = (await response.json()) as Partial<Envelope<unknown>>;
    if (typeof body.code === "number" && body.code !== 0) {
      return new AiStreamError(body.code, str(body.message));
    }
    // 信封成功但未按 SSE 返回：按异常响应处理。
    return new AiStreamError(5000, "invalid_response");
  } catch {
    // 非 JSON 错误体：按中性错误处理，不暴露上游原文。
    return new AiStreamError(5000, "network_error");
  }
}

/**
 * 发起一轮流式对话；`signal` 中止时抛 AbortError，由页面决定保留已生成内容。
 * 只在 HTTP 非 2xx、开流前 JSON 错误体（code!=0）或流中断时抛 AiStreamError。
 */
export async function streamAiAssist(
  messages: AiChatMessage[],
  options: StreamAiAssistOptions,
): Promise<void> {
  const { signal, onEvent } = options;
  if (USE_MOCK) {
    return mockStream(options);
  }

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/api/user/ai-assist/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "text/event-stream",
        Authorization: `Bearer ${USER_TOKEN}`,
      },
      body: JSON.stringify({ subject_id: SUBJECT_ID, messages }),
      signal,
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw error;
    }
    throw new AiStreamError(5000, "network_error");
  }

  if (!response.ok) {
    throw await readEnvelopeError(response);
  }
  const contentType = response.headers.get("content-type") ?? "";
  if (!contentType.includes("text/event-stream")) {
    // 校验失败时后端在开流前返回 JSON 信封（HTTP 200 + code!=0）。
    throw await readEnvelopeError(response);
  }
  if (!response.body) {
    throw new AiStreamError(5000, "network_error");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";
  let eventName = "";
  let dataLines: string[] = [];
  let settled = false;

  const dispatch = () => {
    const name = eventName || "message";
    eventName = "";
    if (dataLines.length === 0) {
      return;
    }
    const raw = dataLines.join("\n");
    dataLines = [];
    if (raw.trim() === "[DONE]") {
      settled = true;
      return;
    }
    let payload: unknown;
    try {
      payload = JSON.parse(raw);
    } catch {
      return;
    }
    const event = toEvent(name, payload);
    if (!event) {
      return;
    }
    if (event.type === "done" || event.type === "error") {
      settled = true;
    }
    onEvent(event);
  };

  const consumeLine = (rawLine: string) => {
    const line = rawLine.endsWith("\r") ? rawLine.slice(0, -1) : rawLine;
    if (line === "") {
      dispatch();
      return;
    }
    if (line.startsWith(":")) {
      // `: keep-alive` 注释行，直接忽略。
      return;
    }
    if (line.startsWith("event:")) {
      eventName = line.slice(6).trim();
      return;
    }
    if (line.startsWith("data:")) {
      const value = line.slice(5);
      dataLines.push(value.startsWith(" ") ? value.slice(1) : value);
    }
  };

  while (!settled) {
    const { value, done } = await reader.read();
    if (done) {
      break;
    }
    buffer += decoder.decode(value, { stream: true });
    let newline = buffer.indexOf("\n");
    while (newline >= 0) {
      consumeLine(buffer.slice(0, newline));
      buffer = buffer.slice(newline + 1);
      newline = buffer.indexOf("\n");
    }
  }

  buffer += decoder.decode();
  if (buffer.length > 0) {
    consumeLine(buffer);
    dispatch();
  }

  if (settled) {
    // done / error 后上游可能仍有尾巴，主动释放连接。
    try {
      await reader.cancel();
    } catch {
      // 连接已关闭时忽略。
    }
  } else if (!signal?.aborted) {
    throw new AiStreamError(5000, "network_error");
  }
}
