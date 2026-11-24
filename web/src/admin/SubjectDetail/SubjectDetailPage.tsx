/* 对象详情页（ui@1.2 §4.2）：对象摘要、双模块频率与最近完成时间。
 * 当前复盘列表仍无查询端点，因此当前结果保留占位，不编造色码。
 */
import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";
import { getSessions, getSubject, updateFrequency } from "../../api/admin";
import type {
  AdminSessionItem,
  SessionKind,
  SubjectDetail,
} from "../../api/types";
import { OverdueBadge } from "../OverdueBadge";
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

function formatTime(value: string | null): string {
  if (!value) {
    return "";
  }
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? value
    : date.toLocaleString("zh-CN", { hour12: false });
}

function latestCapturedAt(
  items: AdminSessionItem[],
  kind: SessionKind,
): string | null {
  const latest = items.find(
    (item) =>
      item.kind === kind &&
      item.status === "captured" &&
      item.captured_at !== null,
  );
  return latest?.captured_at ?? null;
}

function parseInterval(value: string): number | null {
  if (!/^[1-9]\d*$/.test(value)) {
    return null;
  }
  const parsed = Number(value);
  return Number.isSafeInteger(parsed) ? parsed : null;
}

export default function SubjectDetailPage() {
  const { subjectId } = useParams<{ subjectId: string }>();

  const [subject, setSubject] = useState<SubjectDetail | null>(null);
  const [subjectLoading, setSubjectLoading] = useState(true);
  const [subjectError, setSubjectError] = useState<string | null>(null);

  const [sessions, setSessions] = useState<AdminSessionItem[]>([]);
  const [sessionsLoading, setSessionsLoading] = useState(true);
  const [sessionsError, setSessionsError] = useState<string | null>(null);

  const [auditHint, setAuditHint] = useState<string | null>(null);
  const [checkinInterval, setCheckinInterval] = useState("1");
  const [reportInterval, setReportInterval] = useState("3");
  const [frequencySaving, setFrequencySaving] = useState(false);
  const [frequencyError, setFrequencyError] = useState<string | null>(null);
  const [frequencyMessage, setFrequencyMessage] = useState<string | null>(null);

  const loadSubject = useCallback(async () => {
    if (!subjectId) {
      setSubject(null);
      setSubjectError("缺少对象编号，无法查看详情。");
      setSubjectLoading(false);
      return;
    }
    setSubjectLoading(true);
    setSubjectError(null);
    setFrequencyError(null);
    setFrequencyMessage(null);
    try {
      const envelope = await getSubject(subjectId);
      if (envelope.code !== 0 || envelope.data === null) {
        setSubject(null);
        setSubjectError(errorText(envelope.code, envelope.message));
        return;
      }
      const data = envelope.data;
      setSubject(data);
      setCheckinInterval(String(data.checkin_interval_days ?? 1));
      setReportInterval(String(data.report_interval_days ?? 3));
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

  const saveFrequency = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!subject) {
      return;
    }
    const checkin = parseInterval(checkinInterval);
    const report = parseInterval(reportInterval);
    if (checkin === null || report === null) {
      setFrequencyError("签到与汇报间隔均须填写为不小于 1 的整数。");
      setFrequencyMessage(null);
      return;
    }

    setFrequencySaving(true);
    setFrequencyError(null);
    setFrequencyMessage(null);
    try {
      const envelope = await updateFrequency(subject.subject_id, {
        checkin_interval_days: checkin,
        report_interval_days: report,
      });
      if (envelope.code !== 0 || envelope.data === null) {
        setFrequencyError(errorText(envelope.code, envelope.message));
        return;
      }
      const saved = envelope.data;
      setSubject((current) => (current ? { ...current, ...saved } : current));
      setCheckinInterval(String(saved.checkin_interval_days));
      setReportInterval(String(saved.report_interval_days));
      setFrequencyMessage("频率配置已保存。");

      try {
        const refreshed = await getSubject(subject.subject_id);
        if (refreshed.code === 0 && refreshed.data !== null) {
          setSubject({
            ...refreshed.data,
            checkin_interval_days: saved.checkin_interval_days,
            report_interval_days: saved.report_interval_days,
          });
        } else {
          setFrequencyMessage("频率已保存；逾期状态暂未刷新，请稍后重试。");
        }
      } catch {
        setFrequencyMessage("频率已保存；逾期状态暂未刷新，请稍后重试。");
      }
    } catch (err) {
      setFrequencyMessage(null);
      setFrequencyError(
        err instanceof ApiError
          ? errorText(err.code, err.message)
          : "网络异常，频率配置未保存，请重试。",
      );
    } finally {
      setFrequencySaving(false);
    }
  };

  const recentText = (kind: SessionKind): string => {
    if (sessionsLoading) {
      return "正在加载…";
    }
    if (sessionsError) {
      return "暂不可用";
    }
    return formatTime(latestCapturedAt(sessions, kind)) || "尚未完成";
  };

  return (
    <section>
      <PageTitle
        title="对象详情"
        description="基础信息、双模块频率、最近完成时间、会话时间线与敏感内容。"
        extra={<Link to="/admin/subjects">返回对象列表</Link>}
      />

      <section className={styles.section}>
        <h2 className={styles.sectionTitle}>基础信息</h2>
        {subjectLoading ? <LoadingState text="正在加载对象信息…" /> : null}
        {!subjectLoading && subjectError ? (
          <ErrorBanner message={subjectError} onRetry={() => void loadSubject()} />
        ) : null}
        {!subjectLoading && !subjectError && !subject ? (
          <EmptyState text="对象不存在。" />
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
                对象摘要未返回同意状态
              </span>
            </div>
          </div>
        ) : null}
      </section>

      <section className={styles.section}>
        <h2 className={styles.sectionTitle}>频率配置</h2>
        {subject ? (
          <>
            <div className={styles.overdueRow}>
              <OverdueBadge subjectId={subject.subject_id} overdue={subject.overdue} />
            </div>
            {subject.checkin_interval_days == null ||
            subject.report_interval_days == null ? (
              <p className={styles.notice}>
                接口未返回频率初值，当前按默认值 1 天 / 3 天显示，保存前请确认。
              </p>
            ) : null}
            <form className={styles.frequencyForm} onSubmit={saveFrequency}>
              <div className={styles.frequencyField}>
                <label className={styles.filterField}>
                  <span className={styles.filterLabel}>签到间隔（天）</span>
                  <input
                    className={styles.input}
                    type="number"
                    min={1}
                    step={1}
                    required
                    value={checkinInterval}
                    disabled={frequencySaving}
                    onChange={(event) => setCheckinInterval(event.target.value)}
                  />
                </label>
                <p className={styles.lastCompletion}>
                  最近签到：{recentText("checkin")}
                </p>
              </div>
              <div className={styles.frequencyField}>
                <label className={styles.filterField}>
                  <span className={styles.filterLabel}>汇报间隔（天）</span>
                  <input
                    className={styles.input}
                    type="number"
                    min={1}
                    step={1}
                    required
                    value={reportInterval}
                    disabled={frequencySaving}
                    onChange={(event) => setReportInterval(event.target.value)}
                  />
                </label>
                <p className={styles.lastCompletion}>
                  最近汇报：{recentText("report")}
                </p>
              </div>
              <button
                className={`${styles.button} ${styles.saveButton}`}
                type="submit"
                disabled={frequencySaving}
              >
                {frequencySaving ? "保存中…" : "保存频率"}
              </button>
            </form>
            {!sessionsLoading &&
            !sessionsError &&
            sessions.some((item) => item.kind === undefined) ? (
              <p className={styles.notice}>
                会话接口未返回类型，最近签到/汇报时间可能不完整。
              </p>
            ) : null}
            {frequencyError ? (
              <p className={styles.errorText} role="alert">
                {frequencyError}
              </p>
            ) : null}
            {frequencyMessage ? (
              <p className={styles.successText} role="status">
                {frequencyMessage}
              </p>
            ) : null}
          </>
        ) : (
          <p className={styles.notice}>对象信息加载成功后可配置频率。</p>
        )}
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
