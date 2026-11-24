/* 录音思想汇报子页：手动创建/停止 report 会话，停止后轮询并跳结果页。
 * 对应 ui@1.2 §3.2/§3.4 与补记 4、api@1.5 §7.2/§7.3 与补记·三。
 * 本轮不调用 getUserMedia / MediaRecorder，正计时仅用于展示采集状态。
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { createSession, getSession, stopSession } from "../../api/user";
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

const RECORDING_TICK_MS = 1000;
const POLL_INTERVAL_MS = 1000;

type Phase = "idle" | "starting" | "recording" | "waiting" | "failed" | "error";

type FailureState = {
  captureStatus: CaptureStatus | null;
  code?: number;
};

function requestErrorText(error: unknown): string {
  return error instanceof ApiError
    ? errorText(error.code, error.message)
    : "网络异常，请检查连接后重试。";
}

export default function CapturePage() {
  const navigate = useNavigate();
  const [phase, setPhase] = useState<Phase>("idle");
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [failure, setFailure] = useState<FailureState | null>(null);

  const recordingTimerRef = useRef<number | null>(null);
  const pollTimerRef = useRef<number | null>(null);
  const aliveRef = useRef(true);
  const runIdRef = useRef(0);
  const stopRequestedRef = useRef(false);

  const stopRecordingTimer = useCallback(() => {
    if (recordingTimerRef.current !== null) {
      window.clearInterval(recordingTimerRef.current);
      recordingTimerRef.current = null;
    }
  }, []);

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
      stopRecordingTimer();
      stopPolling();
    };
  }, [stopPolling, stopRecordingTimer]);

  const handleFailure = useCallback(
    (captureStatus: CaptureStatus | null, code?: number) => {
      stopRecordingTimer();
      stopPolling();
      setFailure({ captureStatus, code });
      setPhase("failed");
    },
    [stopPolling, stopRecordingTimer],
  );

  const handleError = useCallback(
    (message: string) => {
      stopRecordingTimer();
      stopPolling();
      setError(message);
      setPhase("error");
    },
    [stopPolling, stopRecordingTimer],
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
          navigate(`/feedback/${id}`);
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
    [handleError, handleFailure, navigate, stopPolling],
  );

  const handleStart = useCallback(async () => {
    stopRecordingTimer();
    stopPolling();
    const runId = ++runIdRef.current;
    stopRequestedRef.current = false;
    setFailure(null);
    setError(null);
    setSessionId(null);
    setElapsedSeconds(0);
    setPhase("starting");

    try {
      const envelope = await createSession({ kind: "report" });
      if (!aliveRef.current || runId !== runIdRef.current) {
        return;
      }
      if (envelope.code !== 0 || envelope.data === null) {
        handleError(errorText(envelope.code, envelope.message));
        return;
      }

      setSessionId(envelope.data.session_id);
      setPhase("recording");
      recordingTimerRef.current = window.setInterval(() => {
        if (aliveRef.current && runId === runIdRef.current) {
          setElapsedSeconds((current) => current + 1);
        }
      }, RECORDING_TICK_MS);
    } catch (error) {
      if (!aliveRef.current || runId !== runIdRef.current) {
        return;
      }
      handleError(requestErrorText(error));
    }
  }, [handleError, stopPolling, stopRecordingTimer]);

  const handleStop = useCallback(async () => {
    if (stopRequestedRef.current) {
      return;
    }
    if (!sessionId) {
      handleError("录音会话尚未创建，请重新开始。");
      return;
    }

    stopRequestedRef.current = true;
    const id = sessionId;
    const runId = runIdRef.current;
    stopRecordingTimer();
    setPhase("waiting");

    try {
      const envelope = await stopSession(id);
      if (!aliveRef.current || runId !== runIdRef.current) {
        return;
      }
      if (envelope.code !== 0 || envelope.data === null) {
        handleError(errorText(envelope.code, envelope.message));
        return;
      }
      void pollSession(id, runId);
    } catch (error) {
      if (!aliveRef.current || runId !== runIdRef.current) {
        return;
      }
      handleError(requestErrorText(error));
    }
  }, [handleError, pollSession, sessionId, stopRecordingTimer]);

  return (
    <main className={styles.page}>
      <PageTitle
        title="录音思想汇报"
        description="请按提示进行思想汇报录音，采集过程中页面会一直显示红点与「正在采集」提示；结束后请手动点击「结束录音」。"
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
              开始录音
            </button>
          </div>
          <p className={styles.hint}>
            点击开始后，请按提示正视摄像头并说出今天的情况。
          </p>
        </section>
      ) : null}

      {phase === "starting" ? <LoadingState text="正在发起采集…" /> : null}

      {phase === "recording" ? (
        <section className={styles.recordBox}>
          <RecordingIndicator elapsedSeconds={elapsedSeconds} />
          <p className={styles.hint}>请正视摄像头，说出今天的情况。</p>
          <div className={styles.actionRow}>
            <button
              type="button"
              className={styles.secondaryButton}
              onClick={() => void handleStop()}
            >
              结束录音
            </button>
          </div>
        </section>
      ) : null}

      {phase === "waiting" ? (
        <LoadingState text="正在保存与处理，请稍候" />
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
        <Link to="/capture">返回模块选择</Link>
        {" · "}
        <Link to="/consent">查看或撤回知情同意</Link>
      </p>
    </main>
  );
}
