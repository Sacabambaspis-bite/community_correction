/* 工单详情（ui@1.2 §4.5）：结论区色码与证据链同屏，三种流转动作由 TicketActions 承担。
 * 不提供一键处置、批量改对象状态或批量关闭入口。
 */
import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getTicket } from "../../../api/admin";
import type { TicketDetail } from "../../../api/types";
import { ColorBadge } from "../../../components/common/ColorBadge";
import { SensitivePanel } from "../../../components/common/SensitivePanel";
import {
  ErrorBanner,
  LoadingState,
  PageTitle,
} from "../../../components/common/StateViews";
import { errorText } from "../../../lib/errorMessages";
import { ApiError } from "../../../lib/http";
import { EvidenceTable } from "../EvidenceTable";
import { TicketActions } from "../TicketActions";
import {
  isOverdueTicket,
  suggestedMethodText,
  ticketSourceText,
} from "../ticketDisplay";
import styles from "../Tickets.module.css";

const STATUS_TEXT: Record<string, string> = {
  pending: "待复核",
  confirmed: "已确认",
  corrected: "已修正",
  closed: "已关闭",
};

const ACTION_TEXT: Record<string, string> = {
  opened: "自动建单",
  confirm: "确认",
  correct: "修正",
  close: "关闭",
};

const AUDIT_HINT = "原型：展开动作待接入 audit 留痕接口";

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

function isOverdue(dueAt: string | null, status: string): boolean {
  if (status === "closed" || !dueAt) {
    return false;
  }
  const due = new Date(dueAt).getTime();
  return !Number.isNaN(due) && due < Date.now();
}

export default function TicketDetailPage() {
  const { ticketId } = useParams<{ ticketId: string }>();
  const [ticket, setTicket] = useState<TicketDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [auditHint, setAuditHint] = useState<string | null>(null);

  const loadTicket = useCallback(async () => {
    if (!ticketId) {
      setTicket(null);
      setError("缺少工单编号，无法查看详情。");
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const envelope = await getTicket(ticketId);
      if (envelope.code !== 0 || envelope.data === null) {
        setTicket(null);
        setError(errorText(envelope.code, envelope.message));
        return;
      }
      setTicket(envelope.data);
    } catch (err) {
      setTicket(null);
      setError(
        err instanceof ApiError
          ? errorText(err.code, err.message)
          : "网络异常，请检查连接后重试。",
      );
    } finally {
      setLoading(false);
    }
  }, [ticketId]);

  useEffect(() => {
    void loadTicket();
  }, [loadTicket]);

  return (
    <section>
      <PageTitle
        title="工单详情"
        description="查看结论、证据链与留痕，并按确认 / 修正 / 关闭逐单处理。"
        extra={<Link to="/admin/tickets">返回复核队列</Link>}
      />

      {loading ? <LoadingState text="正在加载工单详情…" /> : null}

      {!loading && error ? (
        <>
          <ErrorBanner message={error} onRetry={() => void loadTicket()} />
          <p className={styles.footHint}>
            <Link to="/admin/tickets">返回复核队列</Link>
          </p>
        </>
      ) : null}

      {!loading && !error && ticket ? (
        <>
          <section className={styles.section}>
            <h2 className={styles.sectionTitle}>基本信息</h2>
            <div className={styles.infoGrid}>
              <div className={styles.infoItem}>
                <span className={styles.infoLabel}>对象</span>
                <span className={styles.infoValue}>
                  {ticket.subject_name ?? "未命名对象"}（{ticket.subject_id}）
                </span>
              </div>
              <div className={styles.infoItem}>
                <span className={styles.infoLabel}>工单来源</span>
                <span
                  className={`${styles.infoValue} ${
                    isOverdueTicket(ticket) ? styles.overdueSource : ""
                  }`}
                >
                  {ticketSourceText(ticket)}
                </span>
              </div>
              <div className={styles.infoItem}>
                <span className={styles.infoLabel}>优先级</span>
                <span className={styles.infoValue}>{ticket.priority}</span>
              </div>
              <div className={styles.infoItem}>
                <span className={styles.infoLabel}>建单时间</span>
                <span className={styles.infoValue}>{formatTime(ticket.opened_at)}</span>
              </div>
              <div className={styles.infoItem}>
                <span className={styles.infoLabel}>截止时间</span>
                <span
                  className={
                    isOverdue(ticket.due_at, ticket.status)
                      ? `${styles.infoValue} ${styles.overdue}`
                      : styles.infoValue
                  }
                >
                  {formatTime(ticket.due_at) || "未设置"}
                  {isOverdue(ticket.due_at, ticket.status) ? (
                    <span className={styles.overdueTag}>已超期</span>
                  ) : null}
                </span>
              </div>
              <div className={styles.infoItem}>
                <span className={styles.infoLabel}>建议方式</span>
                <span className={styles.infoValue}>
                  {suggestedMethodText(ticket.suggested_method)}
                </span>
              </div>
              <div className={styles.infoItem}>
                <span className={styles.infoLabel}>状态</span>
                <span className={styles.infoValue}>
                  {STATUS_TEXT[ticket.status] ?? ticket.status}
                </span>
              </div>
            </div>
          </section>

          <section className={styles.section}>
            <h2 className={styles.sectionTitle}>结论区</h2>
            <div className={styles.resultRow}>
              {ticket.final_color ? (
                <ColorBadge
                  color={ticket.final_color}
                  rules={
                    ticket.rules_fired.length > 0
                      ? ticket.rules_fired
                      : ticket.triggered_rules
                  }
                  evidenceHref="#evidence-chain"
                />
              ) : (
                <div className={styles.resultBox}>
                  <strong>{ticketSourceText(ticket)}</strong>
                  <span>该工单未关联分析复盘，不展示五色分析结论。</span>
                  <a href="#evidence-chain">查看来源与证据</a>
                </div>
              )}
            </div>
            <p className={styles.hint}>
              {ticket.final_color
                ? "色码与命中规则、证据链入口同屏展示；证据字段见下一区块。"
                : "逾期来源、建议方式与证据入口同屏展示；逾期判定不进入分析管线。"}
            </p>
          </section>

          <section className={styles.section} id="evidence-chain">
            <h2 className={styles.sectionTitle}>证据链</h2>
            <EvidenceTable rows={ticket.evidence} />
          </section>

          <section className={styles.section}>
            <h2 className={styles.sectionTitle}>原始内容</h2>
            <p className={styles.notice}>
              面部图与转写原文默认折叠；展开即需调用留痕接口，本轮仅提示占位文案。
            </p>
            <div className={styles.sensitiveStack}>
              <SensitivePanel title="面部图" onExpand={() => setAuditHint(AUDIT_HINT)} />
              <SensitivePanel
                title="转写原文"
                onExpand={() => setAuditHint(AUDIT_HINT)}
              />
            </div>
            {auditHint ? (
              <p className={styles.auditHint} role="status">
                {auditHint}
              </p>
            ) : null}
          </section>

          <section className={styles.section}>
            <h2 className={styles.sectionTitle}>操作区</h2>
            <TicketActions
              ticketId={ticket.ticket_id}
              status={ticket.status}
              onDone={() => void loadTicket()}
            />
          </section>

          <section className={styles.section}>
            <h2 className={styles.sectionTitle}>留痕</h2>
            {ticket.history.length === 0 ? (
              <p className={styles.empty}>暂无流转记录。</p>
            ) : (
              <div className={styles.tableWrap}>
                <table className={styles.table}>
                  <thead>
                    <tr>
                      <th className={styles.th}>动作</th>
                      <th className={styles.th}>操作人</th>
                      <th className={styles.th}>说明</th>
                      <th className={styles.th}>时间</th>
                    </tr>
                  </thead>
                  <tbody>
                    {ticket.history.map((entry, index) => (
                      <tr key={`${entry.action}-${entry.at}-${index}`}>
                        <td className={styles.td}>
                          {ACTION_TEXT[entry.action] ?? entry.action}
                        </td>
                        <td className={styles.td}>{entry.actor}</td>
                        <td className={styles.td}>{entry.note ?? "—"}</td>
                        <td className={styles.td}>{formatTime(entry.at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </>
      ) : null}
    </section>
  );
}
