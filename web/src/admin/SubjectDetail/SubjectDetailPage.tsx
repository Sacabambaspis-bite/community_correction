/* 对象详情页（ui@1.3 §4.2）：基础信息、状态概览、打卡与思想汇报（含全部采集记录折叠区）、
 * 双模块频率。原独立「会话时间线」「敏感内容」「记录检索」「当前结果」栏目均已移除。
 * 独立状态看板（ui@1.2 §4.3）已合并到本页，不再提供单独路由。
 */
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type FormEvent,
} from "react";
import { Link, useParams } from "react-router-dom";
import {
  getDashboard,
  getSessions,
  getSubject,
  getSubjectMedia,
  updateFrequency,
} from "../../api/admin";
import type {
  AdminSessionItem,
  AnalysisStatus,
  CaptureStatus,
  DailyMediaRecord,
  DashboardData,
  Gender,
  MediaEmotion,
  SessionKind,
  SubjectDetail,
  SubjectMediaData,
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
import { ruleListText } from "../../lib/ruleText";
import { ApiError, fetchMediaBlob } from "../../lib/http";
import { SessionTimeline } from "./SessionTimeline";
import { EvidenceTable } from "../Tickets/EvidenceTable";
import { TrendStrip } from "./TrendStrip";
import { TrendBoard } from "./TrendBoard/TrendBoard";
import styles from "./SubjectDetail.module.css";

const STATUS_TEXT: Record<string, string> = {
  active: "在矫",
  suspended: "暂停",
  closed: "已结案",
};

const GENDER_TEXT: Record<Gender, string> = {
  male: "男",
  female: "女",
  unknown: "未知",
};

const CAPTURE_STATUS_TEXT: Record<CaptureStatus, string> = {
  ok: "采集完整",
  partial: "部分可用",
  no_face: "未取得面部",
  no_audio: "未取得声音",
  no_face_no_audio: "无可用产物",
  error: "采集异常",
};

const ANALYSIS_STATUS_TEXT: Record<AnalysisStatus, string> = {
  pending: "待分析",
  done: "已分析",
  degraded: "降级可用",
  failed: "分析失败",
};

const CHECKIN_AUDIT_HINT = "本次查看打卡影像已写入访问审计日志";
const REPORT_AUDIT_HINT = "本次查看汇报录音与转写已写入访问审计日志";
const MEDIA_NOTICE =
  "影像与录音均来自真实采集落盘，调阅会写入审计日志，请按权限使用。";

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

/** 档案字段空值统一显示「未登记」，不编造数据。 */
function displayText(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === "") {
    return "未登记";
  }
  return String(value);
}

function dateRangeText(start: string | null, end: string | null): string {
  if (!start && !end) {
    return "未登记";
  }
  return `${start || "未登记"} 至 ${end || "未登记"}`;
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

/** 单条媒体记录的采集时间、采集状态、分析状态与时长，左右两栏共用。 */
function MediaRecordMeta({ record }: { record: DailyMediaRecord }) {
  return (
    <>
      <p className={styles.mediaLine}>
        采集时间：{formatTime(record.captured_at) || "未记录"}
      </p>
      <p className={styles.mediaLine}>
        采集状态：
        {record.capture_status
          ? CAPTURE_STATUS_TEXT[record.capture_status]
          : "未记录"}
      </p>
      <p className={styles.mediaLine}>
        分析状态：
        {ANALYSIS_STATUS_TEXT[record.analysis_status] ??
          record.analysis_status}
      </p>
      {record.duration_sec !== null ? (
        <p className={styles.mediaLine}>时长：{record.duration_sec} 秒</p>
      ) : null}
    </>
  );
}

export default function SubjectDetailPage() {
  const { subjectId } = useParams<{ subjectId: string }>();

  const [subject, setSubject] = useState<SubjectDetail | null>(null);
  const [subjectLoading, setSubjectLoading] = useState(true);
  const [subjectError, setSubjectError] = useState<string | null>(null);

  const [sessions, setSessions] = useState<AdminSessionItem[]>([]);
  const [sessionsLoading, setSessionsLoading] = useState(true);
  const [sessionsError, setSessionsError] = useState<string | null>(null);

  /* 看板数据独立加载，失败只影响状态概览区块。 */
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [dashboardLoading, setDashboardLoading] = useState(true);
  const [dashboardError, setDashboardError] = useState<string | null>(null);

  /* 打卡与思想汇报各自独立：日期、数据、加载态、错误与索引互不影响。 */
  const [checkinDate, setCheckinDate] = useState("");
  const [reportDate, setReportDate] = useState("");
  const [checkinMedia, setCheckinMedia] = useState<SubjectMediaData | null>(null);
  const [reportMedia, setReportMedia] = useState<SubjectMediaData | null>(null);
  const [checkinLoading, setCheckinLoading] = useState(true);
  const [reportLoading, setReportLoading] = useState(true);
  const [checkinError, setCheckinError] = useState<string | null>(null);
  const [reportError, setReportError] = useState<string | null>(null);
  const [checkinIndex, setCheckinIndex] = useState(0);
  const [reportIndex, setReportIndex] = useState(0);
  const [imageSrc, setImageSrc] = useState<string | null>(null);
  const [audioSrc, setAudioSrc] = useState<string | null>(null);
  const [imageFailed, setImageFailed] = useState(false);
  const [checkinAuditHint, setCheckinAuditHint] = useState<string | null>(null);
  const [reportAuditHint, setReportAuditHint] = useState<string | null>(null);

  /* 丢弃过期响应：快速切换日期时只接受最后一次请求的结果。 */
  const checkinRequestRef = useRef(0);
  const reportRequestRef = useRef(0);

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

  const loadDashboard = useCallback(async () => {
    if (!subjectId) {
      setDashboard(null);
      setDashboardError("缺少对象编号，无法加载状态概览。");
      setDashboardLoading(false);
      return;
    }
    setDashboardLoading(true);
    setDashboardError(null);
    try {
      const envelope = await getDashboard(subjectId);
      if (envelope.code !== 0 || envelope.data === null) {
        setDashboard(null);
        setDashboardError(errorText(envelope.code, envelope.message));
        return;
      }
      setDashboard(envelope.data);
    } catch (err) {
      setDashboard(null);
      setDashboardError(
        err instanceof ApiError
          ? errorText(err.code, err.message)
          : "网络异常，请检查连接后重试。",
      );
    } finally {
      setDashboardLoading(false);
    }
  }, [subjectId]);

  /** 左栏打卡：只更新打卡的日期、数据与索引，不影响右栏。 */
  const loadCheckinMedia = useCallback(
    async (date?: string) => {
      const requestId = checkinRequestRef.current + 1;
      checkinRequestRef.current = requestId;
      if (!subjectId) {
        setCheckinMedia(null);
        setCheckinError("缺少对象编号，无法加载打卡记录。");
        setCheckinLoading(false);
        return;
      }
      setCheckinLoading(true);
      setCheckinError(null);
      setImageFailed(false);
      try {
        const envelope = await getSubjectMedia(subjectId, date);
        if (requestId !== checkinRequestRef.current) {
          return;
        }
        if (envelope.code !== 0 || envelope.data === null) {
          setCheckinMedia(null);
          setCheckinError(errorText(envelope.code, envelope.message));
          return;
        }
        setCheckinMedia(envelope.data);
        setCheckinDate(envelope.data.date);
        const records = envelope.data.items.filter(
          (item) => item.kind === "checkin",
        );
        setCheckinIndex(Math.max(0, records.length - 1));
      } catch (err) {
        if (requestId !== checkinRequestRef.current) {
          return;
        }
        setCheckinMedia(null);
        setCheckinError(
          err instanceof ApiError
            ? errorText(err.code, err.message)
            : "网络异常，请检查连接后重试。",
        );
      } finally {
        if (requestId === checkinRequestRef.current) {
          setCheckinLoading(false);
        }
      }
    },
    [subjectId],
  );

  /** 右栏思想汇报：只更新汇报的日期、数据与索引，不影响左栏。 */
  const loadReportMedia = useCallback(
    async (date?: string) => {
      const requestId = reportRequestRef.current + 1;
      reportRequestRef.current = requestId;
      if (!subjectId) {
        setReportMedia(null);
        setReportError("缺少对象编号，无法加载思想汇报记录。");
        setReportLoading(false);
        return;
      }
      setReportLoading(true);
      setReportError(null);
      try {
        const envelope = await getSubjectMedia(subjectId, date);
        if (requestId !== reportRequestRef.current) {
          return;
        }
        if (envelope.code !== 0 || envelope.data === null) {
          setReportMedia(null);
          setReportError(errorText(envelope.code, envelope.message));
          return;
        }
        setReportMedia(envelope.data);
        setReportDate(envelope.data.date);
        const records = envelope.data.items.filter(
          (item) => item.kind === "report",
        );
        setReportIndex(Math.max(0, records.length - 1));
      } catch (err) {
        if (requestId !== reportRequestRef.current) {
          return;
        }
        setReportMedia(null);
        setReportError(
          err instanceof ApiError
            ? errorText(err.code, err.message)
            : "网络异常，请检查连接后重试。",
        );
      } finally {
        if (requestId === reportRequestRef.current) {
          setReportLoading(false);
        }
      }
    },
    [subjectId],
  );

  /** 首次进入只请求一次：同一天的数据同时初始化两栏，避免重复留痕。 */
  const bootstrapMedia = useCallback(async () => {
    if (!subjectId) {
      setCheckinMedia(null);
      setReportMedia(null);
      setCheckinError("缺少对象编号，无法加载打卡与汇报记录。");
      setReportError("缺少对象编号，无法加载打卡与汇报记录。");
      setCheckinLoading(false);
      setReportLoading(false);
      return;
    }
    setCheckinLoading(true);
    setReportLoading(true);
    setCheckinError(null);
    setReportError(null);
    setImageFailed(false);
    try {
      const envelope = await getSubjectMedia(subjectId);
      if (envelope.code !== 0 || envelope.data === null) {
        const message = errorText(envelope.code, envelope.message);
        setCheckinMedia(null);
        setReportMedia(null);
        setCheckinError(message);
        setReportError(message);
        return;
      }
      const data = envelope.data;
      setCheckinMedia(data);
      setReportMedia(data);
      setCheckinDate(data.date);
      setReportDate(data.date);
      setCheckinIndex(
        Math.max(
          0,
          data.items.filter((item) => item.kind === "checkin").length - 1,
        ),
      );
      setReportIndex(
        Math.max(
          0,
          data.items.filter((item) => item.kind === "report").length - 1,
        ),
      );
    } catch (err) {
      const message =
        err instanceof ApiError
          ? errorText(err.code, err.message)
          : "网络异常，请检查连接后重试。";
      setCheckinMedia(null);
      setReportMedia(null);
      setCheckinError(message);
      setReportError(message);
    } finally {
      setCheckinLoading(false);
      setReportLoading(false);
    }
  }, [subjectId]);

  useEffect(() => {
    void loadSubject();
  }, [loadSubject]);

  useEffect(() => {
    void loadSessions();
  }, [loadSessions]);

  useEffect(() => {
    void loadDashboard();
  }, [loadDashboard]);

  useEffect(() => {
    void bootstrapMedia();
  }, [bootstrapMedia]);

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

  /* 两栏各自过滤，日期与数据互不影响。 */
  const checkinRecords = useMemo(
    () => (checkinMedia?.items ?? []).filter((item) => item.kind === "checkin"),
    [checkinMedia],
  );
  const reportRecords = useMemo(
    () => (reportMedia?.items ?? []).filter((item) => item.kind === "report"),
    [reportMedia],
  );
  const checkinRecord = checkinRecords[checkinIndex] ?? null;
  const reportRecord = reportRecords[reportIndex] ?? null;
  const checkinAvailableDates = checkinMedia?.available_dates ?? [];
  const reportAvailableDates = reportMedia?.available_dates ?? [];

  /* 真实模式下的媒体 URL 需要鉴权，不能直接作为 src；先拉 blob 再转 object URL。
   * mock 模式返回 data URI，走直接分支。 */
  const checkinImageUrl = checkinRecord?.image_url ?? null;
  const reportAudioUrl = reportRecord?.audio_url ?? null;

  useEffect(() => {
    setImageSrc(null);
    setImageFailed(false);
    if (!checkinImageUrl) {
      return;
    }
    if (isInlineUrl(checkinImageUrl)) {
      setImageSrc(checkinImageUrl);
      return;
    }
    let cancelled = false;
    fetchMediaBlob(checkinImageUrl)
      .then((blob) => {
        if (!cancelled) {
          setImageSrc(URL.createObjectURL(blob));
        }
      })
      .catch(() => {
        if (!cancelled) {
          setImageFailed(true);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [checkinImageUrl]);

  useEffect(() => {
    setAudioSrc(null);
    if (!reportAudioUrl) {
      return;
    }
    if (isInlineUrl(reportAudioUrl)) {
      setAudioSrc(reportAudioUrl);
      return;
    }
    let cancelled = false;
    fetchMediaBlob(reportAudioUrl)
      .then((blob) => {
        if (!cancelled) {
          setAudioSrc(URL.createObjectURL(blob));
        }
      })
      .catch(() => {
        if (!cancelled) {
          setAudioSrc(null);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [reportAudioUrl]);

  // 释放上一份 blob URL，避免日期切换时累积。
  useEffect(() => {
    if (!imageSrc || !imageSrc.startsWith("blob:")) {
      return;
    }
    return () => URL.revokeObjectURL(imageSrc);
  }, [imageSrc]);

  useEffect(() => {
    if (!audioSrc || !audioSrc.startsWith("blob:")) {
      return;
    }
    return () => URL.revokeObjectURL(audioSrc);
  }, [audioSrc]);

  const dashboardLastSession = dashboard
    ? formatTime(dashboard.last_session_at)
    : "";

  return (
    <section>
      <PageTitle
        title="对象详情"
        description="基础信息、状态概览、打卡与思想汇报（含全部采集记录）、频率配置与心理状态趋势。"
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
              <span className={styles.infoValue}>{displayText(subject.code)}</span>
            </div>
            <div className={styles.infoItem}>
              <span className={styles.infoLabel}>姓名</span>
              <span className={styles.infoValue}>{displayText(subject.name)}</span>
            </div>
            <div className={styles.infoItem}>
              <span className={styles.infoLabel}>性别</span>
              <span className={styles.infoValue}>
                {subject.gender ? GENDER_TEXT[subject.gender] : "未登记"}
              </span>
            </div>
            <div className={styles.infoItem}>
              <span className={styles.infoLabel}>年龄</span>
              <span className={styles.infoValue}>
                {subject.age === null || subject.age === undefined
                  ? "未登记"
                  : `${subject.age} 岁`}
              </span>
            </div>
            <div className={styles.infoItem}>
              <span className={styles.infoLabel}>身份证号</span>
              <span className={styles.valueWithHint}>
                <span className={styles.infoValue}>{displayText(subject.id_card)}</span>
                <span className={styles.fieldHint}>原型演示数据</span>
              </span>
            </div>
            <div className={styles.infoItem}>
              <span className={styles.infoLabel}>状态</span>
              <span className={styles.infoValue}>
                {subject.status ? STATUS_TEXT[subject.status] ?? "未知状态" : "未登记"}
              </span>
            </div>
            <div className={styles.infoItem}>
              <span className={styles.infoLabel}>联系电话</span>
              <span className={styles.infoValue}>{displayText(subject.phone)}</span>
            </div>
            <div className={styles.infoItem}>
              <span className={styles.infoLabel}>住址</span>
              <span className={styles.infoValue}>{displayText(subject.address)}</span>
            </div>
            <div className={styles.infoItem}>
              <span className={styles.infoLabel}>矫正类型</span>
              <span className={styles.infoValue}>
                {displayText(subject.correction_type)}
              </span>
            </div>
            <div className={styles.infoItem}>
              <span className={styles.infoLabel}>矫正起止日期</span>
              <span className={styles.infoValue}>
                {dateRangeText(subject.start_date, subject.end_date)}
              </span>
            </div>
          </div>
        ) : null}
      </section>

      <section className={styles.section}>
        <h2 className={styles.sectionTitle}>状态概览</h2>
        {dashboardLoading ? <LoadingState text="正在加载状态概览…" /> : null}
        {!dashboardLoading && dashboardError ? (
          <ErrorBanner
            message={dashboardError}
            onRetry={() => void loadDashboard()}
          />
        ) : null}
        {!dashboardLoading && !dashboardError && !dashboard ? (
          <EmptyState text="暂无状态概览数据。" />
        ) : null}
        {!dashboardLoading && !dashboardError && dashboard ? (
          <>
            <div className={styles.dashGrid}>
              <div className={styles.dashCard}>
                <h3 className={styles.cardTitle}>五色分布</h3>
                <div className={styles.distGrid}>
                  {COLOR_ORDER.map((color) => {
                    const meta = COLOR_META[color];
                    const count = dashboard.color_distribution[color] ?? 0;
                    return (
                      <div className={styles.distItem} key={color}>
                        <span
                          className={styles.swatch}
                          style={{ background: `var(${meta.token})` }}
                          aria-hidden="true"
                        />
                        <span className={styles.distName}>{meta.label}</span>
                        <span className={styles.distCount}>{count} 次</span>
                      </div>
                    );
                  })}
                </div>
                <p className={styles.cardNote}>
                  色码统计来自历史复盘结果，每条结论的规则与证据见
                  <Link
                    to={`/admin/tickets?subject_id=${encodeURIComponent(dashboard.subject_id)}`}
                  >
                    复核队列
                  </Link>
                  。
                </p>
                <div className={styles.subjectOverdue}>
                  <OverdueBadge
                    subjectId={dashboard.subject_id}
                    overdue={dashboard.overdue}
                  />
                </div>
              </div>

              <div className={styles.dashCard}>
                <h3 className={styles.cardTitle}>待复核与最近采集</h3>
                <p className={styles.infoLine}>
                  待复核：
                  <Link
                    to={`/admin/tickets?subject_id=${encodeURIComponent(dashboard.subject_id)}`}
                  >
                    {dashboard.pending_tickets} 件
                  </Link>
                </p>
                <p className={styles.infoLine}>
                  最近采集：{dashboardLastSession || "—"}
                </p>
              </div>
            </div>

            <div className={styles.dashCard}>
              <h3 className={styles.cardTitle}>近 7 天趋势</h3>
              <TrendStrip items={dashboard.trend_7d} />
            </div>
          </>
        ) : null}
        <TrendBoard subjectId={subject?.subject_id ?? subjectId ?? ""} />
      </section>

      <section className={styles.section}>
        <h2 className={styles.sectionTitle}>打卡与思想汇报</h2>
        <p className={styles.notice}>
          刷脸打卡与思想汇报各自按日期查看：左栏为打卡影像，右栏为汇报录音与转写。影像与录音默认折叠，查看会写入访问审计日志。
        </p>

        <div className={styles.mediaColumns}>
          <div className={styles.mediaCard}>
            <div className={styles.columnHeader}>
              <h3 className={styles.cardTitle}>刷脸打卡</h3>
              <MediaDatePicker
                availableDates={checkinAvailableDates}
                value={checkinDate}
                disabled={checkinLoading}
                onChange={(date) => {
                  setCheckinAuditHint(null);
                  void loadCheckinMedia(date);
                }}
              />
            </div>

            {checkinLoading ? (
              <p className={styles.mediaEmpty}>正在加载打卡记录…</p>
            ) : null}
            {!checkinLoading && checkinError ? (
              <ErrorBanner
                message={checkinError}
                onRetry={() => void loadCheckinMedia(checkinDate || undefined)}
              />
            ) : null}

            {!checkinLoading && !checkinError && checkinMedia ? (
              <>
                {checkinRecords.length > 0 ? (
                  <div className={styles.recordSwitcher}>
                    <span className={styles.recordCount}>
                      第 {checkinIndex + 1} / {checkinRecords.length} 条
                    </span>
                    <button
                      type="button"
                      className={styles.pageButton}
                      onClick={() =>
                        setCheckinIndex((current) => Math.max(0, current - 1))
                      }
                      disabled={checkinIndex <= 0}
                    >
                      上一条
                    </button>
                    <button
                      type="button"
                      className={styles.pageButton}
                      onClick={() =>
                        setCheckinIndex((current) =>
                          Math.min(checkinRecords.length - 1, current + 1),
                        )
                      }
                      disabled={checkinIndex >= checkinRecords.length - 1}
                    >
                      下一条
                    </button>
                  </div>
                ) : null}

                {checkinRecord ? (
                  <>
                    <MediaRecordMeta record={checkinRecord} />
                    {checkinRecord.image_url ? (
                      <SensitivePanel
                        title="采集影像"
                        onExpand={() => setCheckinAuditHint(CHECKIN_AUDIT_HINT)}
                      >
                        {imageFailed ? (
                          <p className={styles.mediaEmpty}>
                            影像加载失败，可稍后重试
                          </p>
                        ) : imageSrc ? (
                          <img
                            className={styles.mediaImage}
                            src={imageSrc}
                            alt="采集影像"
                            loading="lazy"
                            onError={() => setImageFailed(true)}
                          />
                        ) : (
                          <p className={styles.mediaEmpty}>影像加载中…</p>
                        )}
                      </SensitivePanel>
                    ) : (
                      <p className={styles.mediaEmpty}>该条记录无影像</p>
                    )}
                  </>
                ) : (
                  <p className={styles.mediaEmpty}>该日期无刷脸打卡记录</p>
                )}

                {checkinAuditHint ? (
                  <p className={styles.auditHint} role="status">
                    {checkinAuditHint}
                  </p>
                ) : null}
              </>
            ) : null}
          </div>

          <div className={styles.mediaCard}>
            <div className={styles.columnHeader}>
              <h3 className={styles.cardTitle}>思想汇报</h3>
              <MediaDatePicker
                availableDates={reportAvailableDates}
                value={reportDate}
                disabled={reportLoading}
                onChange={(date) => {
                  setReportAuditHint(null);
                  void loadReportMedia(date);
                }}
              />
            </div>

            {reportLoading ? (
              <p className={styles.mediaEmpty}>正在加载汇报记录…</p>
            ) : null}
            {!reportLoading && reportError ? (
              <ErrorBanner
                message={reportError}
                onRetry={() => void loadReportMedia(reportDate || undefined)}
              />
            ) : null}

            {!reportLoading && !reportError && reportMedia ? (
              <>
                {reportRecords.length > 0 ? (
                  <div className={styles.recordSwitcher}>
                    <span className={styles.recordCount}>
                      第 {reportIndex + 1} / {reportRecords.length} 条
                    </span>
                    <button
                      type="button"
                      className={styles.pageButton}
                      onClick={() =>
                        setReportIndex((current) => Math.max(0, current - 1))
                      }
                      disabled={reportIndex <= 0}
                    >
                      上一条
                    </button>
                    <button
                      type="button"
                      className={styles.pageButton}
                      onClick={() =>
                        setReportIndex((current) =>
                          Math.min(reportRecords.length - 1, current + 1),
                        )
                      }
                      disabled={reportIndex >= reportRecords.length - 1}
                    >
                      下一条
                    </button>
                  </div>
                ) : null}

                {reportRecord ? (
                  <>
                    <MediaRecordMeta record={reportRecord} />
                    {reportRecord.audio_url ? (
                      <SensitivePanel
                        title="采集录音"
                        onExpand={() => setReportAuditHint(REPORT_AUDIT_HINT)}
                      >
                        {audioSrc ? (
                          <audio
                            className={styles.audio}
                            controls
                            preload="auto"
                            src={audioSrc}
                          />
                        ) : (
                          <p className={styles.mediaEmpty}>录音加载中…</p>
                        )}
                        <p className={styles.mediaLine}>转写文本：</p>
                        {reportRecord.transcript_text ? (
                          <p className={styles.transcriptText}>
                            {reportRecord.transcript_text}
                          </p>
                        ) : (
                          <p className={styles.mediaEmpty}>暂无转写文本</p>
                        )}

                        <AnalysisPanel record={reportRecord} />
                      </SensitivePanel>
                    ) : (
                      <p className={styles.mediaEmpty}>该条记录无录音</p>
                    )}
                  </>
                ) : (
                  <p className={styles.mediaEmpty}>该日期无思想汇报记录</p>
                )}

                {reportAuditHint ? (
                  <p className={styles.auditHint} role="status">
                    {reportAuditHint}
                  </p>
                ) : null}
              </>
            ) : null}
          </div>
        </div>

        <p className={styles.mediaNote}>{MEDIA_NOTICE}</p>

        <details className={styles.timelineFold}>
          <summary className={styles.timelineSummary}>
            全部采集记录（含失败）
          </summary>
          {sessionsLoading ? <LoadingState text="正在加载会话记录…" /> : null}
          {!sessionsLoading && sessionsError ? (
            <ErrorBanner
              message={sessionsError}
              onRetry={() => void loadSessions()}
            />
          ) : null}
          {!sessionsLoading && !sessionsError ? (
            <SessionTimeline items={sessions} />
          ) : null}
        </details>
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
    </section>
  );
}

/** mock 直接返回 data URI，真实后端返回需要鉴权的相对路径。 */
function isInlineUrl(url: string): boolean {
  return url.startsWith("data:") || url.startsWith("blob:");
}

const EXPRESSION_TEXT: Record<string, string> = {
  neutral: "中性",
  sad: "低落",
  anxious: "焦虑",
  angry: "愤怒",
  positive: "积极",
};

const INTENT_TEXT: Record<string, string> = {
  none: "无明确意图",
  self_harm_mention: "提及自我伤害",
  suicide_intent: "明确意图标记",
};

/** 数值统一保留两位；缺失显示「—」。 */
function scoreText(value: number | null, digits = 2): string {
  return value === null || value === undefined ? "—" : value.toFixed(digits);
}

/** 非 ok 通道追加中性提示，避免把降级/跳过结果当成完整结论。 */
function channelNotice(status: string | null): string {
  if (!status || status === "ok") {
    return "";
  }
  return status === "degraded" ? "（降级结果，仅供参考）" : "（本次不可用）";
}

/** 思想汇报展开区：人脸、语音情感、心理文本与五色证据同屏展示。 */
function AnalysisPanel({ record }: { record: DailyMediaRecord }) {
  const { analysis } = record;
  const emotion = analysis.emotion ?? record.emotion;
  const face = analysis.face;
  const psych = analysis.psych;

  return (
    <div className={styles.analysisBlock}>
      <p className={styles.mediaLine}>AI 分析结果：</p>
      <div className={styles.analysisGrid}>
        <div className={styles.analysisCard}>
          <h4 className={styles.analysisTitle}>人脸表情</h4>
          {face ? (
            <>
              <p className={styles.analysisLine}>
                表情：
                {face.expression_label
                  ? EXPRESSION_TEXT[face.expression_label] ?? "其他"
                  : "—"}
                {channelNotice(face.status)}
              </p>
              <p className={styles.analysisLine}>
                表情强度：{scoreText(face.intensity)}
              </p>
              <p className={styles.analysisLine}>
                识别置信度：{scoreText(face.face_confidence)} · 有效帧{" "}
                {face.valid_frames ?? "—"} / {face.frame_count ?? "—"}
              </p>
            </>
          ) : (
            <p className={styles.mediaEmpty}>本次无人脸表情结果</p>
          )}
        </div>

        <div className={styles.analysisCard}>
          <h4 className={styles.analysisTitle}>语音情感</h4>
          {emotion ? (
            <>
              <p className={styles.analysisLine}>
                倾向：{emotionTone(emotion)}
                {channelNotice(emotion.status)}
              </p>
              <p className={styles.analysisLine}>
                效价 {scoreText(emotion.valence)} / 唤醒{" "}
                {scoreText(emotion.arousal)}
              </p>
              <p className={styles.analysisLine}>
                情绪标签：{emotion.label ?? "—"}
              </p>
            </>
          ) : (
            <p className={styles.mediaEmpty}>本次无语音情感结果</p>
          )}
        </div>

        <div className={styles.analysisCard}>
          <h4 className={styles.analysisTitle}>心理文本评估</h4>
          {psych ? (
            <>
              <p className={styles.analysisLine}>
                信号强度：{scoreText(psych.signal_strength, 1)} / 100
                {channelNotice(psych.status)}
              </p>
              <p className={styles.analysisLine}>
                意图标记：
                {psych.intent_flag
                  ? INTENT_TEXT[psych.intent_flag] ?? "其他"
                  : "—"}
              </p>
              <p className={styles.analysisLine}>
                触发关键词：
                {psych.keywords.length > 0
                  ? psych.keywords.join("、")
                  : "—"}
              </p>
              <p className={styles.analysisLine}>
                分析依据：{psych.rationale_signal ?? "未提供"}
              </p>
            </>
          ) : (
            <p className={styles.mediaEmpty}>本次无心理文本结果</p>
          )}
        </div>
      </div>

      <div className={styles.analysisRules}>
        <p className={styles.mediaLine}>五色规则与证据：</p>
        {record.rules_fired.length > 0 ? (
          <>
            <p className={styles.ruleLine}>
              {record.review_color ? (
                <span
                  className={styles.swatch}
                  style={{
                    background: `var(${COLOR_META[record.review_color].token})`,
                  }}
                  aria-hidden="true"
                />
              ) : null}
              <span className={styles.ruleColor}>
                {record.review_color
                  ? COLOR_META[record.review_color].label
                  : "未定色"}
              </span>
              <span>{ruleListText(record.rules_fired)}</span>
            </p>
            <EvidenceTable rows={record.evidence} />
          </>
        ) : (
          <p className={styles.mediaEmpty}>
            该会话未命中五色规则，或尚无复盘结果。
          </p>
        )}
      </div>

      <p className={styles.analysisFootnote}>
        以上为采集分析结果，仅作提示，需结合面谈与人工复核。
      </p>
    </div>
  );
}

/** 按 valence 给出可读倾向；`label=neutral` 仍可能偏正向，不能只看 label。 */
function emotionTone(emotion: MediaEmotion): string {
  if (emotion.valence === null) {
    return "未提供数值";
  }
  if (emotion.valence >= 0.3) {
    return "偏正向";
  }
  if (emotion.valence <= -0.3) {
    return "偏负向";
  }
  return "中性";
}

const WEEKDAY_LABELS = ["一", "二", "三", "四", "五", "六", "日"];

type MediaDatePickerProps = {
  availableDates: string[];
  value: string;
  disabled: boolean;
  onChange: (date: string) => void;
};

/** 日期选择器：默认收起，仅点击「查看日期」输入框才展开月历；
 * 仅有记录的日期可点击，点击面板外部、按 Esc 或点「取消」收起。 */
function MediaDatePicker({
  availableDates,
  value,
  disabled,
  onChange,
}: MediaDatePickerProps) {
  const fallback = value || availableDates[0] || "";
  const [open, setOpen] = useState(false);
  const [viewMonth, setViewMonth] = useState(() => fallback.slice(0, 7));
  const fieldRef = useRef<HTMLDivElement | null>(null);
  const triggerRef = useRef<HTMLButtonElement | null>(null);

  useEffect(() => {
    if (value) {
      setViewMonth(value.slice(0, 7));
    }
  }, [value]);

  /* 加载中或没有可用日期时，面板不应保持展开。 */
  useEffect(() => {
    if (disabled || availableDates.length === 0) {
      setOpen(false);
    }
  }, [disabled, availableDates.length]);

  /* 点击组件外部区域或按 Esc 收起面板。 */
  useEffect(() => {
    if (!open) {
      return;
    }
    const handlePointerDown = (event: PointerEvent) => {
      const target = event.target;
      if (target instanceof Node && fieldRef.current?.contains(target)) {
        return;
      }
      setOpen(false);
    };
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setOpen(false);
        triggerRef.current?.focus();
      }
    };
    document.addEventListener("pointerdown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("pointerdown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [open]);

  if (availableDates.length === 0) {
    return (
      <button type="button" className={styles.dateTrigger} disabled>
        暂无可用日期
      </button>
    );
  }

  const available = new Set(availableDates);
  const [yearText, monthText] = (viewMonth || fallback.slice(0, 7)).split("-");
  const year = Number(yearText);
  const month = Number(monthText);

  const shiftMonth = (delta: number) => {
    const base = new Date(year, month - 1 + delta, 1);
    setViewMonth(
      `${base.getFullYear()}-${String(base.getMonth() + 1).padStart(2, "0")}`,
    );
  };

  const daysInMonth = new Date(year, month, 0).getDate();
  const leading = (new Date(year, month - 1, 1).getDay() + 6) % 7;
  const cells: Array<string | null> = [
    ...Array.from({ length: leading }, () => null),
    ...Array.from({ length: daysInMonth }, (_, index) => {
      const day = index + 1;
      return `${year}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
    }),
  ];

  const closePanel = () => {
    setOpen(false);
    triggerRef.current?.focus();
  };

  return (
    <div className={styles.dateField} ref={fieldRef}>
      <button
        ref={triggerRef}
        type="button"
        className={styles.dateTrigger}
        aria-label={`查看日期：${value || "未选择"}`}
        aria-haspopup="dialog"
        aria-expanded={open}
        disabled={disabled}
        onClick={() => setOpen((current) => !current)}
      >
        <span>{value || "选择日期"}</span>
        <span className={styles.dateTriggerIcon} aria-hidden="true">
          ▾
        </span>
      </button>

      {open ? (
        <div className={styles.datePanel} role="dialog" aria-label="选择查看日期">
          <div className={styles.datePickerHeader}>
            <button
              className={styles.datePickerNav}
              type="button"
              onClick={() => shiftMonth(-1)}
              aria-label="上个月"
            >
              ‹
            </button>
            <span className={styles.datePickerTitle}>
              {year} 年 {month} 月
            </span>
            <button
              className={styles.datePickerNav}
              type="button"
              onClick={() => shiftMonth(1)}
              aria-label="下个月"
            >
              ›
            </button>
          </div>
          <div className={styles.datePickerWeekdays}>
            {WEEKDAY_LABELS.map((label) => (
              <span key={label}>{label}</span>
            ))}
          </div>
          <div className={styles.datePickerGrid}>
            {cells.map((date, index) => {
              if (date === null) {
                return <span key={`empty-${index}`} />;
              }
              const isAvailable = available.has(date);
              const isSelected = date === value;
              const classes = [
                styles.datePickerCell,
                isAvailable
                  ? styles.datePickerCellAvailable
                  : styles.datePickerCellDisabled,
                isSelected ? styles.datePickerCellSelected : "",
              ]
                .filter(Boolean)
                .join(" ");
              return (
                <button
                  key={date}
                  type="button"
                  className={classes}
                  disabled={!isAvailable}
                  aria-pressed={isSelected}
                  onClick={() => {
                    onChange(date);
                    setOpen(false);
                  }}
                >
                  {Number(date.slice(8))}
                </button>
              );
            })}
          </div>
          <div className={styles.datePanelFooter}>
            <span className={styles.datePanelHint}>仅可选择有记录的日期</span>
            <button
              className={styles.datePanelAction}
              type="button"
              onClick={closePanel}
            >
              取消
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
