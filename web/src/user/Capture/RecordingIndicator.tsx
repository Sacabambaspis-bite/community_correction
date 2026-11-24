/* 采集中的显性标识：红点 + 「正在采集」+ 剩余秒数占位，禁止静默录制（ui@1.2 §3.2）。
 * 倒计时仅前端计数，本轮不录音、不调用 getUserMedia / MediaRecorder。
 */
import styles from "./Capture.module.css";

type RecordingIndicatorProps = {
  secondsLeft: number;
};

export function RecordingIndicator({ secondsLeft }: RecordingIndicatorProps) {
  const active = secondsLeft > 0;

  return (
    <div
      className={active ? styles.recording : styles.recordingWaiting}
      role="status"
      aria-live="polite"
    >
      <span
        className={active ? styles.dotActive : styles.dot}
        aria-hidden="true"
      />
      <span className={styles.recordingText}>
        {active ? "正在采集" : "采集已结束，正在等待处理结果"}
      </span>
      {active ? (
        <span className={styles.recordingCount}>剩余 {secondsLeft} 秒</span>
      ) : null}
    </div>
  );
}
