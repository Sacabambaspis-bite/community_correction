/* 证据链表格（ui@1.2 §4.5）：字段 / 观测值 / 阈值（名称 + 值）/ 会话编号。
 * 字段路径与阈值键在界面统一显示中文，原始编号仍由接口与留痕保存。
 */
import type { EvidenceRow } from "../../api/types";
import {
  evidenceValueText,
  fieldPathText,
  thresholdKeyText,
} from "../../lib/ruleText";
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
            <th className={styles.th}>字段</th>
            <th className={styles.th}>观测值</th>
            <th className={styles.th}>阈值（名称 / 值）</th>
            <th className={styles.th}>会话编号</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={`${row.rule_id}-${row.field_path}-${index}`}>
              <td className={styles.td}>{fieldPathText(row.field_path)}</td>
              <td className={styles.td}>{evidenceValueText(row.observed_value)}</td>
              <td className={styles.td}>
                <span className={styles.cellStack}>
                  <span>{thresholdKeyText(row.threshold_key)}</span>
                  <span className={styles.muted}>
                    {evidenceValueText(row.threshold_value)}
                  </span>
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
