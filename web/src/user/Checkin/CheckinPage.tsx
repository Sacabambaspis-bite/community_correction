/* 刷脸签到：创建 checkin 会话、轮询至采集终态，完成后触发分析并进入结果页。 */
import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { analyzeSession, createSession, getSession } from "../../api/user";
import type { CaptureStatus } from "../../api/types";
import {
  ErrorBanner,
  LoadingState,
  PageTitle,
} from "../../components/common/StateViews";
import { errorText } from "../../lib/errorMessages";
import { ApiError } from "../../lib/http";
import styles from "../Capture/Capture.module.css";
import { CaptureResult } from "../Capture/CaptureResult";

const POLL_INTERVAL_MS = 1000;
const CHECKIN_STEPS = ["正视摄像头", "拍摄", "等待完成"];

type Phase = "idle" | "starting" | "capturing" | "waiting" | "failed" | "error";

type FailureState = {
  captureStatus: CaptureStatus | null;
  code?: number;
};

function requestErrorText(error: unknown): string {
  return error instanceof ApiError
    ? errorText(error.code, error.message)
    : "网络异常，请检查连接后重试。";
}

export default function CheckinPage() {
  const navigate = useNavigate();
  const [phase, setPhase] = useState<Phase>("idle");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [failure, setFailure] = useState<FailureState | null>(null);

  const pollTimerRef = useRef<number | null>(null);
  const aliveRef = useRef(true);
  const runIdRef = useRef(0);

  const stopPolling = useCallback(() => {
    if (pollTimerRef.current !== null) {
      window.clearTimeout(pollTimerRef.current);
      pollTimerRef.current = null;
    }
  }, []);

  useEffect(() => {
    aliveRef.current = true;
    return () => {
      aliveRef.current = false;
      runIdRef.current += 1;
      stopPolling();
    };
  }, [stopPolling]);

  const handleFailure = useCallback(
    (captureStatus: CaptureStatus | null, code?: number) => {
      stopPolling();
      setFailure({ captureStatus, code });
      setPhase("failed");
    },
    [stopPolling],
  );

  const handleError = useCallback(
    (message: string) => {
      stopPolling();
      setError(message);
      setPhase("error");
    },
    [stopPolling],
  );

  const analyzeCaptured = useCallback(
    async (id: string, runId: number) => {
      setPhase("waiting");
      try {
        const envelope = await analyzeSession(id);
        if (!aliveRef.current || runId !== runIdRef.current) {
          return;
        }
        if (envelope.code === 2003) {
          handleFailure(null, 2003);
          return;
        }
        if (envelope.code !== 0 || envelope.data === null) {
          handleError(errorText(envelope.code, envelope.message));
          return;
        }
        navigate(`/feedback/${id}`);
      } catch (error) {
        if (!aliveRef.current || runId !== runIdRef.current) {
          return;
        }
        handleError(requestErrorText(error));
      }
    },
    [handleError, handleFailure, navigate],
  );

  const pollSession = useCallback(
    async (id: string, runId: number) => {
      try {
        const envelope = await getSession(id);
        if (!aliveRef.current || runId !== runIdRef.current) {
          return;
        }
        if (envelope.code === 2001) {
          handleFailure(envelope.data?.capture_status ?? null, 2001);
          return;
        }
        if (envelope.code === 2003) {
          handleFailure(null, 2003);
          return;
        }
        if (envelope.code !== 0 || envelope.data === null) {
          handleError(errorText(envelope.code, envelope.message));
          return;
        }
        if (envelope.data.status === "captured") {
          stopPolling();
          await analyzeCaptured(id, runId);
          return;
        }
        if (envelope.data.status === "failed") {
          handleFailure(envelope.data.capture_status, 2001);
          return;
        }
        pollTimerRef.current = window.setTimeout(() => {
          void pollSession(id, runId);
        }, POLL_INTERVAL_MS);
      } catch (error) {
        if (!aliveRef.current || runId !== runIdRef.current) {
          return;
        }
        handleError(requestErrorText(error));
      }
    },
    [analyzeCaptured, handleError, handleFailure, stopPolling],
  );

  const handleStart = useCallback(async () => {
    stopPolling();
    const runId = ++runIdRef.current;
    setFailure(null);
    setError(null);
    setSessionId(null);
    setPhase("starting");

    try {
      const envelope = await createSession({ kind: "checkin" });
      if (!aliveRef.current || runId !== runIdRef.current) {
        return;
      }
      if (envelope.code !== 0 || envelope.data === null) {
        handleError(errorText(envelope.code, envelope.message));
        return;
      }

      const id = envelope.data.session_id;
      setSessionId(id);
      setPhase("capturing");
      void pollSession(id, runId);
    } catch (error) {
      if (!aliveRef.current || runId !== runIdRef.current) {
        return;
      }
      handleError(requestErrorText(error));
    }
  }, [handleError, pollSession, stopPolling]);

  return (
    <main className={styles.page}>
      <PageTitle
        title="刷脸签到"
        description="请按提示完成面部图像采集，采集过程中页面会显示红点与「正在采集」提示。"
      />

      <div className={styles.guideGrid}>
        <section className={styles.card}>
          <h2 className={styles.cardTitle}>开始前请准备</h2>
          <ol className={styles.steps}>
            {CHECKIN_STEPS.map((text, index) => (
              <li key={text} className={styles.step}>
                <span className={styles.stepIndex} aria-hidden="true">
                  {index + 1}
                </span>
                <span>{text}</span>
              </li>
            ))}
          </ol>
        </section>

        <section className={styles.card}>
          <h2 className={styles.cardTitle}>设备状态</h2>
          <dl className={styles.deviceList}>
            <div className={styles.deviceRow}>
              <dt>摄像头</dt>
              <dd>原型占位：由后端宿主设备采集</dd>
            </div>
          </dl>
          <p className={styles.hint}>
            本次签到只采集面部图像，不采集声音，也不需要麦克风。
          </p>
        </section>
      </div>

      {phase === "idle" ? (
        <section className={styles.card}>
          <div className={styles.actionRow}>
            <button
              type="button"
              className={styles.primaryButton}
              onClick={() => void handleStart()}
            >
              开始签到
            </button>
          </div>
          <p className={styles.hint}>点击开始后，请正视摄像头并等待拍摄完成。</p>
        </section>
      ) : null}

      {phase === "starting" ? <LoadingState text="正在发起签到…" /> : null}

      {phase === "capturing" || phase === "waiting" ? (
        <section className={styles.recordBox}>
          <div
            className={
              phase === "capturing" ? styles.recording : styles.recordingWaiting
            }
            role="status"
            aria-live="polite"
          >
            <span
              className={phase === "capturing" ? styles.dotActive : styles.dot}
              aria-hidden="true"
            />
            <span className={styles.recordingText}>
              {phase === "capturing"
                ? "正在采集"
                : "采集已结束，正在等待处理结果"}
            </span>
          </div>
          <p className={styles.hint}>
            {phase === "capturing"
              ? "请正视摄像头，保持面部清晰可见。"
              : "正在处理签到结果，请稍候。"}
          </p>
        </section>
      ) : null}

      {phase === "failed" && failure ? (
        <CaptureResult
          captureStatus={failure.captureStatus}
          code={failure.code}
          sessionId={sessionId}
          onRetry={() => void handleStart()}
        />
      ) : null}

      {phase === "error" ? (
        <ErrorBanner
          message={error ?? "签到未完成，请稍后重试。"}
          onRetry={() => void handleStart()}
        />
      ) : null}

      <p className={styles.footerHint}>
        <Link to="/capture">返回模块选择</Link>
        {" · "}
        <Link to="/consent">查看或撤回知情同意</Link>
      </p>
    </main>
  );
}
