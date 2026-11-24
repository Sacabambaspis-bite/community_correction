/* 采集前引导：三步说明 + 摄像头/麦克风两行设备状态（ui@1.2 §3.2）。
 * 本轮为原型占位，不调用浏览器设备权限。
 */
import styles from "./Capture.module.css";

const STEPS = ["正视摄像头", "说出今天的情况", "等待完成"];

export function CaptureGuide() {
  return (
    <div className={styles.guideGrid}>
      <section className={styles.card}>
        <h2 className={styles.cardTitle}>开始前请准备</h2>
        <ol className={styles.steps}>
          {STEPS.map((text, index) => (
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
          <div className={styles.deviceRow}>
            <dt>麦克风</dt>
            <dd>原型占位：由后端宿主设备采集</dd>
          </div>
        </dl>
        <p className={styles.hint}>
          本页不会请求浏览器的摄像头或麦克风权限，也不会上传音视频文件。
        </p>
      </section>
    </div>
  );
}
