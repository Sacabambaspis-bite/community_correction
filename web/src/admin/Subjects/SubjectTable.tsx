/* 对象列表表格（ui@1.2 §4.1）：当前色码必须与规则、证据入口同屏，不允许孤立色块。 */
import { Link } from "react-router-dom";
import type { SubjectListItem } from "../../api/types";
import { ColorBadge } from "../../components/common/ColorBadge";
import styles from "./Subjects.module.css";

const STATUS_TEXT: Record<string, string> = {
  active: "在矫",
  suspended: "暂停",
  closed: "已结案",
};

/** 本地可读时间，空值返回空串，由调用方决定占位符。 */
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

export function SubjectTable({ items }: { items: SubjectListItem[] }) {
  return (
    <div className={styles.tableWrap}>
      <table className={styles.table}>
        <thead>
          <tr>
            <th className={styles.th}>编号</th>
            <th className={styles.th}>姓名</th>
            <th className={styles.th}>状态</th>
            <th className={styles.th}>当前色码</th>
            <th className={styles.th}>待复核</th>
            <th className={styles.th}>最近采集</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => {
            const latestAt = formatTime(item.latest_session_at);
            return (
              <tr key={item.subject_id} className={styles.row}>
                <td className={`${styles.td} ${styles.code}`}>{item.code}</td>
                <td className={styles.td}>{item.name}</td>
                <td className={styles.td}>{STATUS_TEXT[item.status] ?? item.status}</td>
                <td className={styles.td}>
                  {item.latest_color ? (
                    <ColorBadge
                      color={item.latest_color}
                      rules={item.latest_rules}
                      evidenceHref={`/admin/subjects/${item.subject_id}`}
                      at={formatTime(item.latest_color_at) || undefined}
                    />
                  ) : (
                    <span className={styles.muted}>暂无结果</span>
                  )}
                </td>
                <td className={styles.td}>
                  {item.pending_tickets > 0 ? (
                    <Link
                      className={styles.pendingLink}
                      to={`/admin/tickets?subject_id=${encodeURIComponent(item.subject_id)}`}
                    >
                      {item.pending_tickets} 件
                    </Link>
                  ) : (
                    <span className={styles.muted}>0</span>
                  )}
                </td>
                <td className={styles.td}>{latestAt || "—"}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
