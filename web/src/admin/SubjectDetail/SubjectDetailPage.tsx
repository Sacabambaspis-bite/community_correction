/* 对象详情页（ui@1.2 §4.2）。
 * GET /api/admin/subjects/{id} 与 reviews 查询尚未实现（api@1.5 §5.4），
 * 基础信息回退到对象列表数据查找，当前结果只给占位说明，不编造色码。
 */
import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getSessions, getSubjects } from "../../api/admin";
import type { AdminSessionItem, SubjectListItem } from "../../api/types";
import { SensitivePanel } from "../../components/common/SensitivePanel";
import {
  EmptyState,
  ErrorBanner,
  LoadingState,
  PageTitle,
} from "../../components/common/StateViews";
import { COLOR_META, COLOR_ORDER } from "../../lib/colors";
import { errorText } from "../../lib/errorMessages";
import { ApiError } from "../../lib/http";
import { SessionTimeline } from "./SessionTimeline";
import styles from "./SubjectDetail.module.css";

const STATUS_TEXT: Record<string, string> = {
  active: "在矫",
  suspended: "暂停",
  closed: "已结案",
};

const AUDIT_HINT = "原型：展开动作待接入 audit 留痕接口";

function sortByCapturedAtDesc(items: AdminSessionItem[]): AdminSessionItem[] {
  return [...items].sort((left, right) => {
    const leftAt = left.captured_at ? new Date(left.captured_at).getTime() : Number.NEGATIVE_INFINITY;
    const rightAt = right.captured_at ? new Date(right.captured_at).getTime() : Number.NEGATIVE_INFINITY;
    return rightAt - leftAt;
  });
}

export default function SubjectDetailPage() {
  const { subjectId } = useParams<{ subjectId: string }>();

  const [subject, setSubject] = useState<SubjectListItem | null>(null);
  const [subjectLoading, setSubjectLoading] = useState(true);
  const [subjectError, setSubjectError] = useState<string | null>(null);

  const [sessions, setSessions] = useState<AdminSessionItem[]>([]);
  const [sessionsLoading, setSessionsLoading] = useState(true);
  const [sessionsError, setSessionsError] = useState<string | null>(null);

  const [auditHint, setAuditHint] = useState<string | null>(null);

  const loadSubject = useCallback(async () => {
    if (!subjectId) {
      setSubject(null);
      setSubjectError("缺少对象编号，无法查看详情。");
      setSubjectLoading(false);
      return;
    }
    setSubjectLoading(true);
    setSubjectError(null);
    try {
      const envelope = await getSubjects({ page: 1, page_size: 100 });
      if (envelope.code !== 0 || envelope.data === null) {
        setSubject(null);
        setSubjectError(errorText(envelope.code, envelope.message));
        return;
      }
      const found = envelope.data.items.find((item) => item.subject_id === subjectId) ?? null;
      setSubject(found);
    } catch (err) {
      setSubject(null);
      setSubjectError(
        err instanceof ApiError
          ? errorText(err.code, err.message)
          : "网络异常，请检查连接后重试。",
      );
    } finally {
      setSubjectLoading(false);
    }
  }, [subjectId]);

  const loadSessions = useCallback(async () => {
    if (!subjectId) {
      setSessions([]);
      setSessionsLoading(false);
      return;
    }
    setSessionsLoading(true);
    setSessionsError(null);
    try {
      const envelope = await getSessions({ subject_id: subjectId, page: 1, page_size: 100 });
      if (envelope.code !== 0 || envelope.data === null) {
        setSessions([]);
        setSessionsError(errorText(envelope.code, envelope.message));
        return;
      }
      setSessions(sortByCapturedAtDesc(envelope.data.items));
    } catch (err) {
      setSessions([]);
      setSessionsError(
        err instanceof ApiError
          ? errorText(err.code, err.message)
          : "网络异常，请检查连接后重试。",
      );
    } finally {
      setSessionsLoading(false);
    }
  }, [subjectId]);

  useEffect(() => {
    void loadSubject();
  }, [loadSubject]);

  useEffect(() => {
    void loadSessions();
  }, [loadSessions]);

  return (
    <section>
      <PageTitle
        title="对象详情"
        description="基础信息、当前结果、会话时间线与敏感内容折叠查看。"
        extra={<Link to="/admin/subjects">返回对象列表</Link>}
      />

      <section className={styles.section}>
        <h2 className={styles.sectionTitle}>基础信息</h2>
        {subjectLoading ? <LoadingState text="正在加载对象信息…" /> : null}
        {!subjectLoading && subjectError ? (
          <ErrorBanner message={subjectError} onRetry={() => void loadSubject()} />
        ) : null}
        {!subjectLoading && !subjectError && !subject ? (
          <EmptyState text="对象不存在或接口未实现（对象详情接口尚未落地，已回退到列表数据查找）。" />
        ) : null}
        {!subjectLoading && !subjectError && subject ? (
          <div className={styles.infoGrid}>
            <div className={styles.infoItem}>
              <span className={styles.infoLabel}>编号</span>
              <span className={styles.infoValue}>{subject.code}</span>
            </div>
            <div className={styles.infoItem}>
              <span className={styles.infoLabel}>姓名</span>
              <span className={styles.infoValue}>{subject.name}</span>
            </div>
            <div className={styles.infoItem}>
              <span className={styles.infoLabel}>状态</span>
              <span className={styles.infoValue}>
                {STATUS_TEXT[subject.status] ?? subject.status}
              </span>
            </div>
            <div className={styles.infoItem}>
              <span className={styles.infoLabel}>同意状态</span>
              <span className={styles.infoValue}>
                未接入（对象详情接口未实现，api@1.5 §5.4）
              </span>
            </div>
          </div>
        ) : null}
      </section>

      <section className={styles.section}>
        <h2 className={styles.sectionTitle}>当前结果</h2>
        <p className={styles.notice}>
          复盘结果接口未实现（api@1.5 §5.4），暂不展示色码与证据链，避免展示无来源的结论。
        </p>
      </section>

      <section className={styles.section}>
        <h2 className={styles.sectionTitle}>会话时间线</h2>
        {sessionsLoading ? <LoadingState text="正在加载会话记录…" /> : null}
        {!sessionsLoading && sessionsError ? (
          <ErrorBanner message={sessionsError} onRetry={() => void loadSessions()} />
        ) : null}
        {!sessionsLoading && !sessionsError ? <SessionTimeline items={sessions} /> : null}
      </section>

      <section className={styles.section}>
        <h2 className={styles.sectionTitle}>记录检索</h2>
        <p className={styles.notice}>
          契约尚未提供时间范围与色码过滤参数（api@1.5 §7.7 仅支持 subject_id / status /
          分页），以下控件为占位，暂不可用。
        </p>
        <fieldset className={styles.filterBox} disabled>
          <label className={styles.filterField}>
            <span className={styles.filterLabel}>开始日期</span>
            <input className={styles.input} type="date" />
          </label>
          <label className={styles.filterField}>
            <span className={styles.filterLabel}>结束日期</span>
            <input className={styles.input} type="date" />
          </label>
          <label className={styles.filterField}>
            <span className={styles.filterLabel}>色码</span>
            <select className={styles.select} defaultValue="">
              <option value="">全部</option>
              {COLOR_ORDER.map((color) => (
                <option key={color} value={color}>
                  {COLOR_META[color].label}
                </option>
              ))}
            </select>
          </label>
          <button className={styles.button} type="button" disabled>
            检索
          </button>
        </fieldset>
      </section>

      <section className={styles.section}>
        <h2 className={styles.sectionTitle}>敏感内容</h2>
        <p className={styles.notice}>
          默认折叠；展开需留痕，本轮仅提示占位文案，接入后调用 audit 留痕接口。
        </p>
        <div className={styles.sensitiveStack}>
          <SensitivePanel title="面部图" onExpand={() => setAuditHint(AUDIT_HINT)} />
          <SensitivePanel title="转写原文" onExpand={() => setAuditHint(AUDIT_HINT)} />
        </div>
        {auditHint ? (
          <p className={styles.auditHint} role="status">
            {auditHint}
          </p>
        ) : null}
      </section>
    </section>
  );
}
