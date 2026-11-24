/* 证据链表格（ui@1.2 §4.5）：字段路径 / 观测值 / 阈值（键 + 值）/ 会话编号。 */
import type { EvidenceRow } from "../../api/types";
import styles from "./Tickets.module.css";

export function EvidenceTable({ rows }: { rows: EvidenceRow[] }) {
  if (rows.length === 0) {
    return <p className={styles.muted}>暂无证据记录。</p>;
  }

  return (
    <div className={styles.tableWrap}>
      <table className={styles.table}>
        <thead>
          <tr>
            <th className={styles.th}>字段路径</th>
            <th className={styles.th}>观测值</th>
            <th className={styles.th}>阈值（键 / 值）</th>
            <th className={styles.th}>会话编号</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={`${row.rule_id}-${row.field_path}-${index}`}>
              <td className={`${styles.td} ${styles.code}`}>{row.field_path}</td>
              <td className={styles.td}>{String(row.observed_value)}</td>
              <td className={styles.td}>
                <span className={styles.cellStack}>
                  <span>{row.threshold_key}</span>
                  <span className={styles.muted}>{String(row.threshold_value)}</span>
                </span>
              </td>
              <td className={`${styles.td} ${styles.code}`}>{row.session_id}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
