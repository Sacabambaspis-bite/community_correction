/* AI 援助对话页（ui@1.2 补记 14 / §3.5；api@1.5 §7.19–§7.20）。
 *
 * 隐私：消息只存内存，不写 localStorage / sessionStorage / IndexedDB，刷新即清空；
 * 安全：AI 正文一律按纯文本渲染（保留换行），不做 HTML 注入、不引入 Markdown 库；
 * 合规：每条 AI 消息固定展示免责声明，不展示风险色码、评分或诊断结论。
 */
import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type KeyboardEvent,
} from "react";
import { Link } from "react-router-dom";
import {
  AiStreamError,
  getAiAssistStatus,
  streamAiAssist,
} from "../../api/aiAssist";
import type {
  AiAssistCitation,
  AiAssistEvent,
  AiAssistStatus,
  AiChatMessage,
} from "../../api/types";
import { LoadingState, PageTitle } from "../../components/common/StateViews";
import { errorText } from "../../lib/errorMessages";
import { ApiError } from "../../lib/http";
import styles from "./AiAssist.module.css";

/** 每条 AI 消息下方固定展示的合规文案（api@1.5 §7.20 meta.disclaimer）。 */
const DISCLAIMER = "目前测试版本的回答基于公开网络信息，仅供参考，不构成专业建议";
/** 页头常驻的第三方处理提示（ui@1.2 补记 14 第 4 条），未开通态同样展示。 */
const THIRD_PARTY_HINT =
  "你的问题会发送至第三方模型服务用于生成回答，请勿输入身份证号、住址等敏感信息";
const DISABLED_TEXT = "智能援助暂未开通，请联系工作人员";
const MAX_LENGTH = 2000;
const HISTORY_LIMIT = 12;
const MAX_TOTAL_CHARS = 12000;
/** 打字机节奏：约 16ms / 字。 */
const TYPE_INTERVAL_MS = 16;
/** 距底部小于该像素时视为“接近底部”，自动跟随。 */
const NEAR_BOTTOM_PX = 80;

const EXAMPLE_QUESTIONS = [
  "最近压力很大，心里总是很慌，可以怎么调节？",
  "法律援助怎么申请？需要准备哪些材料？",
  "晚上总是睡不好，有什么可以尝试的放松方法？",
];

type ChatItem = AiChatMessage & {
  id: string;
  citations: AiAssistCitation[];
  /** 该条消息内的中性提示（如未开通、未启用联网搜索）。 */
  notice: string | null;
  stopped: boolean;
  streaming: boolean;
  error: string | null;
  notConfigured: boolean;
  /** SSE meta.disclaimer；非空时优先于固定常量展示。 */
  disclaimer: string | null;
};

function domainOf(url: string): string {
  try {
    return new URL(url).hostname;
  } catch {
    return url;
  }
}

function streamErrorText(code: number, message: string): string {
  switch (message) {
    case "ai_upstream_timeout":
      return "回答生成超时，请重试";
    case "ai_rate_limited":
      return "请求过于频繁，请稍后再试";
    case "ai_upstream_auth_failed":
    case "ai_upstream_failed":
      return "智能援助暂时不可用，请稍后重试";
    case "network_error":
      return "网络连接中断，请检查网络后重试";
    case "invalid_response":
      return "服务返回异常，请稍后重试";
    default:
      break;
  }
  if (code === 1002 || code === 1003) {
    return "登录状态已失效，请重新登录";
  }
  if (code === 1004) {
    return "未找到对应的用户信息，请联系工作人员";
  }
  if (code === 1006) {
    return "请求过于频繁，请稍后再试";
  }
  if (code === 1001) {
    return "消息内容不合规，请调整后再试";
  }
  return "回答生成失败，请重试";
}

/** 只保留有正文的消息，最多 12 条且总字符 ≤ 12000（api@1.5 §7.20）。 */
function toHistory(items: ChatItem[]): AiChatMessage[] {
  const cleaned = items
    .filter((item) => !item.error && !item.notConfigured && item.content.trim().length > 0)
    .map((item) => ({ role: item.role, content: item.content }));
  const trimmed = cleaned.slice(-HISTORY_LIMIT);
  let total = trimmed.reduce((sum, item) => sum + item.content.length, 0);
  while (trimmed.length > 1 && total > MAX_TOTAL_CHARS) {
    const removed = trimmed.shift();
    total -= removed ? removed.content.length : 0;
  }
  return trimmed;
}

function MessageBubble({
  item,
  onRetry,
}: {
  item: ChatItem;
  onRetry: (id: string) => void;
}) {
  if (item.role === "user") {
    return (
      <div className={`${styles.row} ${styles.rowUser}`}>
        <div className={`${styles.bubble} ${styles.bubbleUser}`}>
          <p className={styles.text}>{item.content}</p>
        </div>
      </div>
    );
  }

  return (
    <div className={`${styles.row} ${styles.rowAi}`}>
      <div className={`${styles.bubble} ${styles.bubbleAi}`}>
        {item.notConfigured ? (
          <p className={styles.text}>{item.notice ?? DISABLED_TEXT}</p>
        ) : (
          <p className={styles.text}>
            {item.content}
            {item.streaming ? <span className={styles.caret} aria-hidden="true" /> : null}
          </p>
        )}

        {item.notice && !item.notConfigured ? (
          <p className={styles.inlineNotice}>{item.notice}</p>
        ) : null}

        {item.stopped ? <p className={styles.metaNote}>已停止</p> : null}

        {item.error ? (
          <div className={styles.errorBox} role="alert">
            <span>{item.error}</span>
            <button
              type="button"
              className={styles.retryButton}
              aria-label="重试本次回答"
              onClick={() => onRetry(item.id)}
            >
              重试
            </button>
          </div>
        ) : null}

        {item.citations.length > 0 ? (
          <div className={styles.citations}>
            <p className={styles.citationsTitle}>参考来源</p>
            <ul className={styles.citationList}>
              {item.citations.map((citation) => (
                <li key={citation.url}>
                  <a
                    href={citation.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className={styles.citationLink}
                  >
                    {citation.title}
                    <span className={styles.citationDomain}>
                      （{domainOf(citation.url)}）
                    </span>
                  </a>
                </li>
              ))}
            </ul>
          </div>
        ) : null}

        <p className={styles.disclaimer}>
          {item.disclaimer && item.disclaimer.trim()
            ? item.disclaimer
            : DISCLAIMER}
        </p>
      </div>
    </div>
  );
}

export default function AiAssistPage() {
  const [status, setStatus] = useState<AiAssistStatus | null>(null);
  const [statusLoading, setStatusLoading] = useState(true);
  const [statusError, setStatusError] = useState<string | null>(null);

  const [messages, setMessages] = useState<ChatItem[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);

  const idSeq = useRef(0);
  const pendingRef = useRef(new Map<string, string>());
  const activeIdRef = useRef<string | null>(null);
  const timerRef = useRef<number | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const requestIdRef = useRef<string | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLTextAreaElement | null>(null);
  const nearBottomRef = useRef(true);

  const nextId = () => {
    idSeq.current += 1;
    return `ai-${idSeq.current}`;
  };

  /* ---------- 可用状态 ---------- */

  const loadStatus = useCallback(async () => {
    setStatusLoading(true);
    setStatusError(null);
    try {
      const envelope = await getAiAssistStatus();
      if (envelope.code !== 0 || envelope.data === null) {
        setStatus(null);
        setStatusError(errorText(envelope.code, envelope.message));
        return;
      }
      setStatus(envelope.data);
    } catch (error) {
      setStatus(null);
      setStatusError(
        error instanceof ApiError
          ? errorText(error.code, error.message)
          : "网络异常，请检查连接后重试。",
      );
    } finally {
      setStatusLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadStatus();
  }, [loadStatus]);

  /* ---------- 逐字渲染 ---------- */

  const stopTyping = useCallback(() => {
    if (timerRef.current !== null) {
      window.clearInterval(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  const appendTyped = useCallback((id: string, text: string) => {
    if (!text) {
      return;
    }
    pendingRef.current.set(id, (pendingRef.current.get(id) ?? "") + text);
    if (timerRef.current !== null) {
      return;
    }
    timerRef.current = window.setInterval(() => {
      const activeId = activeIdRef.current;
      const queue = activeId ? pendingRef.current.get(activeId) ?? "" : "";
      if (!activeId || !queue) {
        if (timerRef.current !== null) {
          window.clearInterval(timerRef.current);
          timerRef.current = null;
        }
        return;
      }
      const char = queue.slice(0, 1);
      pendingRef.current.set(activeId, queue.slice(1));
      setMessages((prev) =>
        prev.map((item) =>
          item.id === activeId ? { ...item, content: item.content + char } : item,
        ),
      );
    }, TYPE_INTERVAL_MS);
  }, []);

  /** done / error / 停止时立即冲刷剩余字符。 */
  const flushTyping = useCallback(
    (id: string) => {
      stopTyping();
      const rest = pendingRef.current.get(id) ?? "";
      pendingRef.current.delete(id);
      if (rest) {
        setMessages((prev) =>
          prev.map((item) =>
            item.id === id ? { ...item, content: item.content + rest } : item,
          ),
        );
      }
    },
    [stopTyping],
  );

  const handleEvent = useCallback(
    (id: string, event: AiAssistEvent) => {
      switch (event.type) {
        case "meta":
          // 仅记录 request_id 便于排查，不展示；disclaimer 非空时用于该条消息。
          requestIdRef.current = event.request_id || null;
          if (event.disclaimer && event.disclaimer.trim()) {
            setMessages((prev) =>
              prev.map((item) =>
                item.id === id ? { ...item, disclaimer: event.disclaimer } : item,
              ),
            );
          }
          break;
        case "delta":
          appendTyped(id, event.text);
          break;
        case "citation":
          setMessages((prev) =>
            prev.map((item) => {
              if (item.id !== id) {
                return item;
              }
              if (item.citations.some((citation) => citation.url === event.url)) {
                return item;
              }
              return {
                ...item,
                citations: [
                  ...item.citations,
                  { index: event.index, title: event.title, url: event.url },
                ],
              };
            }),
          );
          break;
        case "notice":
          if (event.code === "web_search_unavailable") {
            setMessages((prev) =>
              prev.map((item) =>
                item.id === id ? { ...item, notice: "本次回答未启用联网搜索" } : item,
              ),
            );
          } else if (event.code === "ai_not_configured") {
            setMessages((prev) =>
              prev.map((item) =>
                item.id === id
                  ? {
                      ...item,
                      notConfigured: true,
                      notice: event.message || DISABLED_TEXT,
                    }
                  : item,
              ),
            );
          }
          break;
        case "done":
          flushTyping(id);
          activeIdRef.current = null;
          setMessages((prev) =>
            prev.map((item) => (item.id === id ? { ...item, streaming: false } : item)),
          );
          break;
        case "error":
          flushTyping(id);
          activeIdRef.current = null;
          setMessages((prev) =>
            prev.map((item) =>
              item.id === id
                ? {
                    ...item,
                    streaming: false,
                    error: streamErrorText(event.code, event.message),
                  }
                : item,
            ),
          );
          break;
        default:
          break;
      }
    },
    [appendTyped, flushTyping],
  );

  const beginStream = useCallback(
    (id: string, history: AiChatMessage[]) => {
      if (history.length === 0 || history[history.length - 1].role !== "user") {
        return;
      }
      activeIdRef.current = id;
      pendingRef.current.set(id, "");
      const controller = new AbortController();
      abortRef.current = controller;
      setStreaming(true);
      nearBottomRef.current = true;

      streamAiAssist(history, {
        signal: controller.signal,
        onEvent: (event) => handleEvent(id, event),
      })
        .catch((error: unknown) => {
          if (controller.signal.aborted) {
            return;
          }
          if (activeIdRef.current === id) {
            activeIdRef.current = null;
          }
          flushTyping(id);
          const text =
            error instanceof AiStreamError
              ? streamErrorText(error.code, error.message)
              : "网络连接中断，请检查网络后重试";
          setMessages((prev) =>
            prev.map((item) =>
              item.id === id ? { ...item, streaming: false, error: text } : item,
            ),
          );
        })
        .finally(() => {
          if (abortRef.current === controller) {
            abortRef.current = null;
            setStreaming(false);
          }
        });
    },
    [flushTyping, handleEvent],
  );

  /* ---------- 发送 / 停止 / 重试 / 清空 ---------- */

  const canSend = Boolean(status?.enabled) && !streaming && input.trim().length > 0;

  const handleSend = useCallback(() => {
    const content = input.trim();
    if (!content || streaming || !status?.enabled) {
      return;
    }
    const userItem: ChatItem = {
      id: nextId(),
      role: "user",
      content,
      citations: [],
      notice: null,
      stopped: false,
      streaming: false,
      error: null,
      notConfigured: false,
      disclaimer: null,
    };
    const assistantItem: ChatItem = {
      id: nextId(),
      role: "assistant",
      content: "",
      citations: [],
      notice: null,
      stopped: false,
      streaming: true,
      error: null,
      notConfigured: false,
      disclaimer: null,
    };
    const history = toHistory([...messages, userItem]);
    setMessages([...messages, userItem, assistantItem]);
    setInput("");
    beginStream(assistantItem.id, history);
  }, [beginStream, input, messages, status, streaming]);

  const stopStream = useCallback(() => {
    const controller = abortRef.current;
    const id = activeIdRef.current;
    if (id) {
      flushTyping(id);
      setMessages((prev) =>
        prev.map((item) =>
          item.id === id ? { ...item, streaming: false, stopped: true } : item,
        ),
      );
    }
    activeIdRef.current = null;
    abortRef.current = null;
    if (controller) {
      controller.abort();
    }
    setStreaming(false);
  }, [flushTyping]);

  const retryMessage = useCallback(
    (failedId: string) => {
      const index = messages.findIndex((item) => item.id === failedId);
      if (index < 0 || streaming) {
        return;
      }
      const base = messages.slice(0, index);
      const history = toHistory(base);
      if (history.length === 0 || history[history.length - 1].role !== "user") {
        return;
      }
      const assistantItem: ChatItem = {
        id: nextId(),
        role: "assistant",
        content: "",
        citations: [],
        notice: null,
        stopped: false,
        streaming: true,
        error: null,
        notConfigured: false,
        disclaimer: null,
      };
      setMessages([...base, assistantItem]);
      beginStream(assistantItem.id, history);
    },
    [beginStream, messages, streaming],
  );

  const clearConversation = useCallback(() => {
    const controller = abortRef.current;
    activeIdRef.current = null;
    abortRef.current = null;
    if (controller) {
      controller.abort();
    }
    stopTyping();
    pendingRef.current.clear();
    requestIdRef.current = null;
    setMessages([]);
    setInput("");
    setStreaming(false);
    nearBottomRef.current = true;
  }, [stopTyping]);

  /* ---------- 滚动跟随（仅接近底部时） ---------- */

  const handleScroll = useCallback(() => {
    const element = scrollRef.current;
    if (!element) {
      return;
    }
    const distance =
      element.scrollHeight - element.scrollTop - element.clientHeight;
    nearBottomRef.current = distance <= NEAR_BOTTOM_PX;
  }, []);

  useLayoutEffect(() => {
    const element = scrollRef.current;
    if (!element || !nearBottomRef.current) {
      return;
    }
    element.scrollTop = element.scrollHeight;
  }, [messages]);

  useEffect(() => {
    return () => {
      // 离开页面立即中止流与打字机，避免后台继续请求。
      if (abortRef.current) {
        abortRef.current.abort();
      }
      if (timerRef.current !== null) {
        window.clearInterval(timerRef.current);
      }
    };
  }, []);

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key !== "Enter" || event.shiftKey) {
      return;
    }
    if (event.nativeEvent.isComposing) {
      return;
    }
    event.preventDefault();
    handleSend();
  };

  const fillExample = (question: string) => {
    setInput(question);
    inputRef.current?.focus();
  };

  return (
    <main className={styles.page}>
      <header className={styles.pageHeader}>
        <PageTitle
          title="AI援助"
          description="提供心理援助与法律援助的一般性信息，不替代医生、律师或工作人员"
          extra={
            <Link className={styles.backLink} to="/capture">
              返回事项选择
            </Link>
          }
        />
        <p className={styles.privacyHint}>{THIRD_PARTY_HINT}</p>
      </header>

      {statusLoading ? <LoadingState text="正在确认智能援助状态…" /> : null}

      {!statusLoading && statusError ? (
        <section className={styles.noticeCard} role="alert">
          <p className={styles.noticeText}>{statusError}</p>
          <div className={styles.noticeActions}>
            <button
              type="button"
              className={styles.secondaryButton}
              onClick={() => void loadStatus()}
            >
              重试
            </button>
            <Link className={styles.secondaryButton} to="/capture">
              返回事项选择
            </Link>
          </div>
        </section>
      ) : null}

      {!statusLoading && !statusError && status ? (
        <>
          {!status.enabled ? (
            <section className={styles.noticeCard} role="status">
              <p className={styles.noticeText}>{status.notice ?? DISABLED_TEXT}</p>
            </section>
          ) : null}

          <div className={styles.chat}>
            <div
              className={styles.messages}
              ref={scrollRef}
              onScroll={handleScroll}
              aria-live="polite"
              aria-relevant="additions text"
              aria-busy={streaming}
            >
              {messages.length === 0 ? (
                <div className={styles.empty}>
                  <p className={styles.emptyTitle}>可以这样开始</p>
                  <ul className={styles.exampleList}>
                    {EXAMPLE_QUESTIONS.map((question) => (
                      <li key={question}>
                        <button
                          type="button"
                          className={styles.exampleButton}
                          onClick={() => fillExample(question)}
                        >
                          {question}
                        </button>
                      </li>
                    ))}
                  </ul>
                </div>
              ) : (
                messages.map((item) => (
                  <MessageBubble key={item.id} item={item} onRetry={retryMessage} />
                ))
              )}
            </div>

            <div className={styles.composer}>
              <div className={styles.composerHeader}>
                <span className={styles.composerHint}>
                  仅提供一般性信息，请勿输入身份证号、住址或案件细节。
                </span>
                <button
                  type="button"
                  className={styles.clearButton}
                  onClick={clearConversation}
                  disabled={messages.length === 0}
                  aria-label="清空对话"
                >
                  清空对话
                </button>
              </div>

              <textarea
                ref={inputRef}
                id="ai-aid-input"
                className={styles.textarea}
                value={input}
                maxLength={MAX_LENGTH}
                rows={3}
                onChange={(event) => setInput(event.target.value)}
                onKeyDown={handleKeyDown}
                disabled={!status.enabled}
                placeholder={
                  status.enabled
                    ? "描述你的情况或问题；Enter 发送，Shift+Enter 换行"
                    : DISABLED_TEXT
                }
                aria-label="输入你的问题"
              />

              <div className={styles.composerFooter}>
                <span className={styles.counter}>
                  {input.length}/{MAX_LENGTH}
                </span>
                {streaming ? (
                  <button
                    type="button"
                    className={styles.stopButton}
                    onClick={stopStream}
                    aria-label="停止当前回答"
                  >
                    停止
                  </button>
                ) : (
                  <button
                    type="button"
                    className={styles.sendButton}
                    onClick={handleSend}
                    disabled={!canSend}
                    aria-label="发送消息"
                  >
                    发送
                  </button>
                )}
              </div>
            </div>
          </div>
        </>
      ) : null}
    </main>
  );
}
