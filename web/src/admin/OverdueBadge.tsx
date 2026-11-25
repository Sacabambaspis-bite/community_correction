/* 管理端逾期标记：红色仅取 grading 色码令牌，并同屏说明来源与复核任务入口。 */
import type { CSSProperties } from "react";
import { Link } from "react-router-dom";
import type { SessionKind, SubjectOverdue } from "../api/types";
import { COLOR_META } from "../lib/colors";
import styles from "./OverdueBadge.module.css";

const KIND_TEXT: Record<SessionKind, string> = {
  checkin: "签到",
  report: "思想汇报",
};

type OverdueBadgeProps = {
  subjectId: string;
  overdue: SubjectOverdue | null | undefined;
};

export function OverdueBadge({ subjectId, overdue }: OverdueBadgeProps) {
  const kinds = (["checkin", "report"] as const).filter(
    (kind) => overdue?.[kind] === true,
  );
  if (kinds.length === 0) {
    return null;
  }

  const style = {
    "--overdue-color": `var(${COLOR_META.red.token})`,
  } as CSSProperties;
  const source = kinds.map((kind) => KIND_TEXT[kind]).join("、");

  return (
    <span className={styles.wrap}>
      <span className={styles.badge} style={style}>
        危机·逾期
      </span>
      <span className={styles.source}>{source}逾期</span>
      <Link
        className={styles.link}
        to={`/admin/tickets?subject_id=${encodeURIComponent(subjectId)}`}
      >
        查看逾期任务
      </Link>
    </span>
  );
}
