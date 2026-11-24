/* 采集中的显性标识：红点 + 「正在采集」+ 正计时，禁止静默录制（ui@1.2 §3.2 补记 4）。
 * 本轮不录音、不调用 getUserMedia / MediaRecorder。
 */
import styles from "./Capture.module.css";

type RecordingIndicatorProps = {
  elapsedSeconds: number;
};

function formatElapsedTime(elapsedSeconds: number): string {
  const totalSeconds = Math.max(0, Math.floor(elapsedSeconds));
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}

export function RecordingIndicator({ elapsedSeconds }: RecordingIndicatorProps) {
  return (
    <div className={styles.recording} role="status" aria-live="polite">
      <span className={styles.dotActive} aria-hidden="true" />
      <span className={styles.recordingText}>正在采集</span>
      <span className={styles.recordingCount}>
        {formatElapsedTime(elapsedSeconds)}
      </span>
    </div>
  );
}
