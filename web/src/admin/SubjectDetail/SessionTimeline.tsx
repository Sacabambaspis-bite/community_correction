/* 会话时间线（ui@1.2 §4.2）：按 captured_at 倒序展示，空态有明确文案。 */
import type { AdminSessionItem } from "../../api/types";
import styles from "./SubjectDetail.module.css";

const SESSION_KIND_TEXT: Record<string, string> = {
  checkin: "签到",
  report: "思想汇报",
};

const SESSION_STATUS_TEXT: Record<string, string> = {
  created: "已创建",
  captured: "已完成",
  failed: "采集失败",
};

const CAPTURE_STATUS_TEXT: Record<string, string> = {
  ok: "采集完整",
  partial: "部分可用",
  no_face: "未取得面部",
  no_audio: "未取得声音",
  no_face_no_audio: "无可用产物",
  error: "采集异常",
};

const ANALYSIS_STATUS_TEXT: Record<string, string> = {
  pending: "待分析",
  done: "已分析",
  degraded: "降级可用",
  failed: "分析失败",
};

function formatTime(value: string | null): string {
  if (!value) {
    return "";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString("zh-CN", { hour12: false });
}

function statusText(map: Record<string, string>, value: string | null): string {
  if (!value) {
    return "—";
  }
  return map[value] ?? "未知";
}

export function SessionTimeline({ items }: { items: AdminSessionItem[] }) {
  if (items.length === 0) {
    return <p className={styles.empty}>该对象暂无会话记录。</p>;
  }

  return (
    <ol className={styles.timeline}>
      {items.map((item) => (
        <li key={item.session_id} className={styles.timelineItem}>
          <div className={styles.timelineMain}>
            <span className={styles.timelineTime}>{formatTime(item.captured_at) || "采集时间未记录"}</span>
            <span className={styles.timelineTags}>
              <span className={styles.tag}>
                类型：{SESSION_KIND_TEXT[item.kind] ?? "类型待补充"}
              </span>
              <span className={styles.tag}>
                会话：{statusText(SESSION_STATUS_TEXT, item.status)}
              </span>
              <span className={styles.tag}>
                采集：{statusText(CAPTURE_STATUS_TEXT, item.capture_status)}
              </span>
              <span className={styles.tag}>
                分析：{statusText(ANALYSIS_STATUS_TEXT, item.analysis_status)}
              </span>
            </span>
            <span className={styles.timelineHint}>会话编号 {item.session_id}</span>
          </div>
        </li>
      ))}
    </ol>
  );
}
