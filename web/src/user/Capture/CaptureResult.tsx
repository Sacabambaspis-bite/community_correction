/* 采集失败态：按 capture_status 映射文案并提供重试 / 查看结果 / 联系入口
 * （ui@1.2 §3.2、api@1.5 §3 的 2001 / 2003）。
 */
import { useState } from "react";
import { Link } from "react-router-dom";
import type { CaptureStatus } from "../../api/types";
import styles from "./Capture.module.css";

type CaptureResultProps = {
  captureStatus: CaptureStatus | null;
  /** 信封错误码：2001 采集失败、2003 分析失败。 */
  code?: number;
  sessionId?: string | null;
  onRetry: () => void;
};

type FailureCopy = {
  title: string;
  detail?: string;
  retry: boolean;
  contact: boolean;
  view: boolean;
};

function resolveCopy(
  captureStatus: CaptureStatus | null,
  code?: number,
): FailureCopy {
  if (code === 2003) {
    return {
      title: "分析未完成，结果暂不可用",
      detail: "建议稍后重新采集一次，或与工作人员联系。",
      retry: true,
      contact: true,
      view: false,
    };
  }

  switch (captureStatus) {
    case "partial":
      return {
        title: "本次数据不完整，已转人工复核",
        retry: false,
        contact: false,
        view: true,
      };
    case "no_face":
      return {
        title: "没有识别到面部，请正对摄像头再试一次",
        detail: "已转人工复核",
        retry: true,
        contact: false,
        view: false,
      };
    case "no_audio":
      return {
        title: "没有采集到有效的声音，请靠近麦克风再试一次",
        detail: "已转人工复核",
        retry: true,
        contact: false,
        view: false,
      };
    case "no_face_no_audio":
      return {
        title: "本次采集未成功，请重试或联系工作人员",
        retry: true,
        contact: true,
        view: false,
      };
    case "error":
      return {
        title: "设备暂时不可用，请联系工作人员",
        retry: false,
        contact: true,
        view: false,
      };
    default:
      return {
        title: "本次采集未成功，请重试或联系工作人员",
        retry: true,
        contact: true,
        view: false,
      };
  }
}

export function CaptureResult({
  captureStatus,
  code,
  sessionId,
  onRetry,
}: CaptureResultProps) {
  const [showContact, setShowContact] = useState(false);
  const copy = resolveCopy(captureStatus, code);

  return (
    <section className={styles.resultBox} role="alert">
      <h2 className={styles.resultTitle}>{copy.title}</h2>
      {copy.detail ? <p className={styles.resultText}>{copy.detail}</p> : null}

      <div className={styles.buttonRow}>
        {copy.view && sessionId ? (
          <Link className={styles.primaryButton} to={`/feedback/${sessionId}`}>
            查看结果
          </Link>
        ) : null}
        {copy.retry ? (
          <button type="button" className={styles.primaryButton} onClick={onRetry}>
            重试
          </button>
        ) : null}
        {copy.contact ? (
          <button
            type="button"
            className={styles.secondaryButton}
            onClick={() => setShowContact((value) => !value)}
          >
            联系工作人员
          </button>
        ) : null}
        {/* 失败终态同样提供返回入口，保证录音汇报 / 刷脸签到结束后可自主离开。 */}
        <Link className={styles.secondaryButton} to="/capture">
          返回首页
        </Link>
      </div>

      {showContact ? (
        <p className={styles.hint}>
          请联系你所在司法所的工作人员，说明本次采集未成功，由工作人员协助处理。
        </p>
      ) : null}
    </section>
  );
}
