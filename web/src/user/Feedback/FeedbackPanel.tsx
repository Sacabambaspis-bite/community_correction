/* 结果反馈面板：只展示中性结论、建议映射与下一步，并常驻撤出入口
 * （ui@1.2 §3.3、api@1.5 §7.8）。不展示色码、规则编号、分数或诊断词。
 */
import { Link } from "react-router-dom";
import type { FeedbackData, Suggestion } from "../../api/types";
import styles from "./Feedback.module.css";

const SUGGESTION_TEXT: Record<Suggestion, string> = {
  keep_routine: "保持现在的节奏，按约定时间再来即可",
  talk_to_staff: "建议和工作人员聊一聊近期的情况",
  recapture: "本次记录不完整，建议稍后重新采集",
};

export function FeedbackPanel({ feedback }: { feedback: FeedbackData }) {
  return (
    <section className={styles.panel}>
      <div className={styles.block}>
        <h2 className={styles.blockTitle}>结论</h2>
        <p className={styles.summary}>{feedback.summary_text}</p>
      </div>

      <div className={styles.block}>
        <h2 className={styles.blockTitle}>建议</h2>
        <p className={styles.suggestion}>
          {SUGGESTION_TEXT[feedback.suggestion]}
        </p>
      </div>

      <div className={styles.block}>
        <h2 className={styles.blockTitle}>下一步</h2>
        <p className={styles.nextAction}>{feedback.next_action}</p>
      </div>

      {feedback.suggestion === "talk_to_staff" ? (
        <p className={styles.staffHint}>
          如需进一步沟通，可联系你所在司法所的工作人员。
        </p>
      ) : null}

      <div className={styles.footer}>
        <Link to="/consent">查看或撤回知情同意</Link>
      </div>
    </section>
  );
}
