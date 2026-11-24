/* 复核队列（ui@1.2 §4.4）：读取 ?subject_id= 作为初始筛选，优先级本地 P0→P1→P2 排序。
 * 不提供批量勾选、批量关闭或一键处置入口。
 */
import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { getTickets } from "../../api/admin";
import type { TicketListItem } from "../../api/types";
import { ColorBadge } from "../../components/common/ColorBadge";
import {
  EmptyState,
  ErrorBanner,
  LoadingState,
  PageTitle,
} from "../../components/common/StateViews";
import { errorText } from "../../lib/errorMessages";
import { ApiError } from "../../lib/http";
import { isOverdueTicket, ticketSourceText } from "./ticketDisplay";
import styles from "./Tickets.module.css";

const STATUS_TEXT: Record<string, string> = {
  pending: "待复核",
  confirmed: "已确认",
  corrected: "已修正",
  closed: "已关闭",
};

const PRIORITY_ORDER: Record<string, number> = {
  P0: 0,
  P1: 1,
  P2: 2,
};

type AppliedQuery = {
  status: string;
  priority: string;
  subject_id: string;
};

function formatTime(value: string | null): string {
  if (!value) {
    return "未设置";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString("zh-CN", { hour12: false });
}

function isOverdue(item: TicketListItem): boolean {
  if (item.status === "closed" || item.due_at === null) {
    return false;
  }
  const due = new Date(item.due_at).getTime();
  return !Number.isNaN(due) && due < Date.now();
}

function sortByPriority(items: TicketListItem[]): TicketListItem[] {
  return [...items].sort((left, right) => {
    const leftRank = PRIORITY_ORDER[left.priority] ?? 9;
    const rightRank = PRIORITY_ORDER[right.priority] ?? 9;
    return leftRank - rightRank;
  });
}

export default function TicketsPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const initialSubjectId = searchParams.get("subject_id") ?? "";

  const [status, setStatus] = useState("");
  const [priority, setPriority] = useState("");
  const [subjectInput, setSubjectInput] = useState(initialSubjectId);
  const [applied, setApplied] = useState<AppliedQuery>({
    status: "",
    priority: "",
    subject_id: initialSubjectId,
  });

  const [items, setItems] = useState<TicketListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadTickets = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const envelope = await getTickets({
        status: applied.status || undefined,
        priority: applied.priority || undefined,
        subject_id: applied.subject_id || undefined,
      });
      if (envelope.code !== 0 || envelope.data === null) {
        setItems([]);
        setTotal(0);
        setError(errorText(envelope.code, envelope.message));
        return;
      }
      setItems(sortByPriority(envelope.data.items));
      setTotal(envelope.data.total);
    } catch (err) {
      setItems([]);
      setTotal(0);
      setError(
        err instanceof ApiError
          ? errorText(err.code, err.message)
          : "网络异常，请检查连接后重试。",
      );
    } finally {
      setLoading(false);
    }
  }, [applied]);

  useEffect(() => {
    void loadTickets();
  }, [loadTickets]);

  return (
    <section>
      <PageTitle
        title="复核队列"
        description="按优先级查看待复核工单，色码与触发规则、证据入口同屏展示。"
      />

      <form
        className={styles.filters}
        onSubmit={(event) => {
          event.preventDefault();
          setApplied({ status, priority, subject_id: subjectInput.trim() });
        }}
      >
        <label className={styles.field}>
          <span className={styles.fieldLabel}>状态</span>
          <select
            className={styles.select}
            value={status}
            onChange={(event) => setStatus(event.target.value)}
          >
            <option value="">全部</option>
            <option value="pending">待复核</option>
            <option value="confirmed">已确认</option>
            <option value="closed">已关闭</option>
          </select>
        </label>
        <label className={styles.field}>
          <span className={styles.fieldLabel}>优先级</span>
          <select
            className={styles.select}
            value={priority}
            onChange={(event) => setPriority(event.target.value)}
          >
            <option value="">全部</option>
            <option value="P0">P0</option>
            <option value="P1">P1</option>
            <option value="P2">P2</option>
          </select>
        </label>
        <label className={styles.field}>
          <span className={styles.fieldLabel}>对象编号</span>
          <input
            className={styles.input}
            type="text"
            value={subjectInput}
            placeholder="subject_id"
            onChange={(event) => setSubjectInput(event.target.value)}
          />
        </label>
        <button className={styles.button} type="submit">
          查询
        </button>
      </form>

      <div className={styles.metaRow}>
        <span className={styles.meta}>共 {total} 条</span>
        {applied.subject_id ? (
          <button
            type="button"
            className={styles.linkButton}
            onClick={() => {
              setSubjectInput("");
              setApplied((previous) => ({ ...previous, subject_id: "" }));
            }}
          >
            清除对象筛选
          </button>
        ) : null}
      </div>

      {loading ? <LoadingState text="正在加载复核队列…" /> : null}

      {!loading && error ? (
        <ErrorBanner message={error} onRetry={() => void loadTickets()} />
      ) : null}

      {!loading && !error && items.length === 0 ? (
        <EmptyState text="当前筛选条件下没有工单。" />
      ) : null}

      {!loading && !error && items.length > 0 ? (
        <div className={styles.tableWrap}>
          <table className={styles.table}>
            <thead>
              <tr>
                <th className={styles.th}>优先级</th>
                <th className={styles.th}>对象</th>
                <th className={styles.th}>工单来源</th>
                <th className={styles.th}>当前色码</th>
                <th className={styles.th}>触发规则</th>
                <th className={styles.th}>建单时间</th>
                <th className={styles.th}>截止</th>
                <th className={styles.th}>状态</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => {
                const overdue = isOverdue(item);
                return (
                  <tr
                    key={item.ticket_id}
                    className={styles.row}
                    tabIndex={0}
                    title="点击查看工单详情"
                    onClick={() => navigate(`/admin/tickets/${item.ticket_id}`)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter") {
                        navigate(`/admin/tickets/${item.ticket_id}`);
                      }
                    }}
                  >
                    <td className={styles.td}>{item.priority}</td>
                    <td className={styles.td}>
                      <span className={styles.subjectCell}>
                        <span className={styles.subjectName}>
                          {item.subject_name ?? "未命名对象"}
                        </span>
                        <span className={styles.subjectId}>{item.subject_id}</span>
                      </span>
                    </td>
                    <td className={styles.td}>
                      <span
                        className={isOverdueTicket(item) ? styles.overdueSource : undefined}
                      >
                        {ticketSourceText(item)}
                      </span>
                    </td>
                    <td className={styles.td}>
                      {item.final_color ? (
                        <ColorBadge
                          color={item.final_color}
                          rules={item.triggered_rules}
                          evidenceHref={`/admin/tickets/${item.ticket_id}`}
                        />
                      ) : (
                        <span className={styles.muted}>
                          {isOverdueTicket(item) ? "逾期工单，无分析色码" : "暂无分析色码"}
                        </span>
                      )}
                    </td>
                    <td className={styles.td}>
                      {item.triggered_rules.length > 0
                        ? item.triggered_rules.join("、")
                        : "—"}
                    </td>
                    <td className={styles.td}>{formatTime(item.opened_at)}</td>
                    <td className={`${styles.td} ${overdue ? styles.overdue : ""}`}>
                      {formatTime(item.due_at)}
                      {overdue ? <span className={styles.overdueTag}>已超期</span> : null}
                    </td>
                    <td className={styles.td}>
                      <span className={styles.statusTag}>
                        {STATUS_TEXT[item.status] ?? item.status}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : null}

      <p className={styles.footHint}>
        仅支持逐单查看与处理，<Link to="/admin/subjects">返回对象列表</Link>
      </p>
    </section>
  );
}
