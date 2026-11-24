/* 采集引导页：发起会话 → 每 1s 轮询会话状态 → 成功后跳结果页（ui@1.2 §3.2、api@1.5 §7.2/§7.3）。
 * 本轮不调用 getUserMedia / MediaRecorder，倒计时仅前端占位计数。
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { createSession, getSession } from "../../api/user";
import type { CaptureStatus } from "../../api/types";
import {
  ErrorBanner,
  LoadingState,
  PageTitle,
} from "../../components/common/StateViews";
import { errorText } from "../../lib/errorMessages";
import { ApiError } from "../../lib/http";
import { CaptureGuide } from "./CaptureGuide";
import { CaptureResult } from "./CaptureResult";
import { RecordingIndicator } from "./RecordingIndicator";
import styles from "./Capture.module.css";

const CAPTURE_SECONDS = 10;
const POLL_INTERVAL_MS = 1000;

type Phase = "idle" | "starting" | "recording" | "waiting" | "failed" | "error";

type FailureState = {
  captureStatus: CaptureStatus | null;
  code?: number;
};

export default function CapturePage() {
  const navigate = useNavigate();
  const [phase, setPhase] = useState<Phase>("idle");
  const [secondsLeft, setSecondsLeft] = useState(CAPTURE_SECONDS);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [failure, setFailure] = useState<FailureState | null>(null);

  const intervalRef = useRef<number | null>(null);
  const startedAtRef = useRef(0);
  const aliveRef = useRef(true);

  const stopPolling = useCallback(() => {
    if (intervalRef.current !== null) {
      window.clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  }, []);

  useEffect(() => {
    aliveRef.current = true;
    return () => {
      aliveRef.current = false;
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

  const pollSession = useCallback(
    async (id: string) => {
      try {
        const envelope = await getSession(id);
        if (!aliveRef.current) {
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
          stopPolling();
          setError(errorText(envelope.code, envelope.message));
          setPhase("error");
          return;
        }
        if (envelope.data.status === "captured") {
          stopPolling();
          navigate(`/feedback/${id}`);
          return;
        }
        if (envelope.data.status === "failed") {
          handleFailure(envelope.data.capture_status, 2001);
          return;
        }
      } catch (error) {
        if (!aliveRef.current) {
          return;
        }
        stopPolling();
        setError(
          error instanceof ApiError
            ? errorText(error.code, error.message)
            : "网络异常，请检查连接后重试。",
        );
        setPhase("error");
      }
    },
    [handleFailure, navigate, stopPolling],
  );

  const handleStart = useCallback(async () => {
    stopPolling();
    setFailure(null);
    setError(null);
    setSessionId(null);
    setSecondsLeft(CAPTURE_SECONDS);
    setPhase("starting");

    try {
      const envelope = await createSession({ duration_sec: CAPTURE_SECONDS });
      if (!aliveRef.current) {
        return;
      }
      if (envelope.code !== 0 || envelope.data === null) {
        setError(errorText(envelope.code, envelope.message));
        setPhase("error");
        return;
      }

      const id = envelope.data.session_id;
      setSessionId(id);
      startedAtRef.current = Date.now();
      setPhase("recording");

      intervalRef.current = window.setInterval(() => {
        if (!aliveRef.current) {
          return;
        }
        const elapsed = Math.floor((Date.now() - startedAtRef.current) / 1000);
        const left = Math.max(0, CAPTURE_SECONDS - elapsed);
        setSecondsLeft(left);
        if (left === 0) {
          setPhase((current) => (current === "recording" ? "waiting" : current));
        }
        void pollSession(id);
      }, POLL_INTERVAL_MS);
    } catch (error) {
      if (!aliveRef.current) {
        return;
      }
      setError(
        error instanceof ApiError
          ? errorText(error.code, error.message)
          : "网络异常，请检查连接后重试。",
      );
      setPhase("error");
    }
  }, [pollSession, stopPolling]);

  const handleStop = useCallback(() => {
    stopPolling();
    if (sessionId) {
      navigate(`/feedback/${sessionId}`);
      return;
    }
    setPhase("idle");
  }, [navigate, sessionId, stopPolling]);

  return (
    <main className={styles.page}>
      <PageTitle
        title="采集引导"
        description={`本次采集约 ${CAPTURE_SECONDS} 秒，采集过程中页面会一直显示红点与「正在采集」提示。`}
      />

      <CaptureGuide />

      {phase === "idle" ? (
        <section className={styles.card}>
          <div className={styles.actionRow}>
            <button
              type="button"
              className={styles.primaryButton}
              onClick={() => void handleStart()}
            >
              开始
            </button>
          </div>
          <p className={styles.hint}>
            点击开始后，请按提示正视摄像头并说出今天的情况。
          </p>
        </section>
      ) : null}

      {phase === "starting" ? <LoadingState text="正在发起采集…" /> : null}

      {phase === "recording" || phase === "waiting" ? (
        <section className={styles.recordBox}>
          <RecordingIndicator secondsLeft={secondsLeft} />
          <p className={styles.hint}>
            {phase === "recording"
              ? "请正视摄像头，说出今天的情况。"
              : "采集已结束，正在等待处理结果，请稍候。"}
          </p>
          <div className={styles.actionRow}>
            <button
              type="button"
              className={styles.secondaryButton}
              onClick={handleStop}
            >
              结束
            </button>
          </div>
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
          message={error ?? "采集失败，请稍后重试。"}
          onRetry={() => void handleStart()}
        />
      ) : null}

      <p className={styles.footerHint}>
        <Link to="/consent">查看或撤回知情同意</Link>
      </p>
    </main>
  );
}
