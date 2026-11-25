/* 复盘详情（ui@1.2 §4.6）：看板散点与热力块的证据入口落到本页。
 * 只读：色码必须与 rules_fired 中文名、证据链入口同屏；不提供确认 / 修正 / 关闭等流转动作，
 * 也不展示面部图、音频与转写原文（原始内容仍走复核任务详情的折叠敏感面板）。
 */
import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getReview, getSubject } from "../../api/admin";
import type { ReviewDetail, SubjectDetail } from "../../api/types";
import { ColorBadge } from "../../components/common/ColorBadge";
import {
  ErrorBanner,
  LoadingState,
  PageTitle,
} from "../../components/common/StateViews";
import { COLOR_META } from "../../lib/colors";
import { errorText } from "../../lib/errorMessages";
import { ApiError } from "../../lib/http";
import { EvidenceTable } from "../Tickets/EvidenceTable";
import styles from "./ReviewDetail.module.css";

/** 单次风险口径见 grading@1.2 §3：只产出 red / orange / none。 */
const SINGLE_RISK_TEXT: Record<string, string> = {
  none: "无单次风险",
  red: "红色（单次规则）",
  orange: "橙色（单次规则）",
};

const CONSISTENCY_TEXT: Record<string, string> = {
  low: "低",
  medium: "中",
  high: "高",
};

function riskText(value: string): string {
  return SINGLE_RISK_TEXT[value] ?? "其他取值";
}

function consistencyText(value: string): string {
  return CONSISTENCY_TEXT[value] ?? "—";
}

/** 生成时间等带时区的时间戳；解析失败原样显示，不吞掉原始值。 */
function formatTime(value: string | null): string {
  if (!value) {
    return "—";
  }
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? value
    : date.toLocaleString("zh-CN", { hour12: false });
}

/** 窗口起止按自然日展示：契约要求 YYYY-MM-DD，兼容历史 ISO 写法时只取日期部分。 */
function formatWindowDate(value: string): string {
  if (!value) {
    return "—";
  }
  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) {
    return value;
  }
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? value
    : date.toLocaleDateString("zh-CN", {
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
      });
}

export default function ReviewDetailPage() {
  const { reviewId } = useParams<{ reviewId: string }>();
  const [review, setReview] = useState<ReviewDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [subject, setSubject] = useState<SubjectDetail | null>(null);
  const [subjectMissing, setSubjectMissing] = useState(false);

  const loadReview = useCallback(async () => {
    if (!reviewId) {
      setReview(null);
      setError("缺少复盘编号，无法查看详情。");
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const envelope = await getReview(reviewId);
      if (envelope.code !== 0 || envelope.data === null) {
        setReview(null);
        setError(errorText(envelope.code, envelope.message));
        return;
      }
      setReview(envelope.data);
    } catch (err) {
      setReview(null);
      setError(
        err instanceof ApiError
          ? errorText(err.code, err.message)
          : "网络异常，请检查连接后重试。",
      );
    } finally {
      setLoading(false);
    }
  }, [reviewId]);

  useEffect(() => {
    void loadReview();
  }, [loadReview]);

  const subjectId = review?.subject_id ?? null;

  /* 对象姓名独立加载：失败或不存在时回退显示对象编号，不阻塞复盘主体。 */
  useEffect(() => {
    if (!subjectId) {
      setSubject(null);
      setSubjectMissing(false);
      return;
    }
    let cancelled = false;
    setSubjectMissing(false);
    (async () => {
      try {
        const envelope = await getSubject(subjectId);
        if (cancelled) {
          return;
        }
        if (envelope.code === 0 && envelope.data !== null) {
          setSubject(envelope.data);
        } else {
          setSubject(null);
          setSubjectMissing(true);
        }
      } catch {
        if (!cancelled) {
          setSubject(null);
          setSubjectMissing(true);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [subjectId]);

  const subjectHref = subjectId
    ? `/admin/subjects/${encodeURIComponent(subjectId)}`
    : null;

  return (
    <section>
      <PageTitle
        title="复盘详情"
        description="单条复盘的只读记录：色码、命中规则与证据链同屏展示，本页不提供复核流转动作。"
        extra={
          review ? (
            <Link to={`/admin/subjects/${encodeURIComponent(review.subject_id)}`}>
              返回对象详情
            </Link>
          ) : error ? (
            <Link to="/admin/subjects">返回对象列表</Link>
          ) : null
        }
      />

      {loading ? <LoadingState text="正在加载复盘详情…" /> : null}

      {!loading && error ? (
        <>
          <ErrorBanner message={error} onRetry={() => void loadReview()} />
          <p className={styles.footHint}>
            <Link to="/admin/subjects">返回对象列表</Link>
          </p>
        </>
      ) : null}

      {!loading && !error && review ? (
        <>
          <section className={styles.section}>
            <h2 className={styles.sectionTitle}>基本信息</h2>
            <div className={styles.infoGrid}>
              <div className={styles.infoItem}>
                <span className={styles.infoLabel}>对象</span>
                <span className={styles.infoValue}>
                  {subjectHref ? (
                    <Link to={subjectHref}>{subject?.name ?? review.subject_id}</Link>
                  ) : (
                    review.subject_id
                  )}
                  {subject ? <span className={styles.subjectCode}>{subject.code}</span> : null}
                </span>
                {subjectMissing ? (
                  <span className={styles.footHint}>
                    对象档案暂未取到，仅显示对象编号，不影响复盘内容。
                  </span>
                ) : null}
              </div>
              <div className={styles.infoItem}>
                <span className={styles.infoLabel}>窗口起止</span>
                <span className={styles.infoValue}>
                  {formatWindowDate(review.window_start)} 至{" "}
                  {formatWindowDate(review.window_end)}
                </span>
              </div>
              <div className={styles.infoItem}>
                <span className={styles.infoLabel}>窗口天数</span>
                <span className={styles.infoValue}>{review.window_days} 天</span>
              </div>
              <div className={styles.infoItem}>
                <span className={styles.infoLabel}>生成时间</span>
                <span className={styles.infoValue}>{formatTime(review.created_at)}</span>
              </div>
              <div className={styles.infoItem}>
                <span className={styles.infoLabel}>规则版本</span>
                <span className={styles.infoValue}>{review.grading_version || "—"}</span>
              </div>
            </div>
          </section>

          <section className={styles.section}>
            <h2 className={styles.sectionTitle}>结论区</h2>
            <div className={styles.resultRow}>
              <ColorBadge
                color={review.final_color}
                rules={review.rules_fired}
                evidenceHref="#evidence-chain"
              />
            </div>
            <dl className={styles.metaGrid}>
              <div className={styles.metaItem}>
                <dt className={styles.metaLabel}>趋势色</dt>
                <dd className={styles.metaValue}>
                  {COLOR_META[review.trend_color].label}色
                </dd>
              </div>
              <div className={styles.metaItem}>
                <dt className={styles.metaLabel}>单次风险</dt>
                <dd className={styles.metaValue}>{riskText(review.single_session_risk)}</dd>
              </div>
              <div className={styles.metaItem}>
                <dt className={styles.metaLabel}>一致性</dt>
                <dd className={styles.metaValue}>{consistencyText(review.consistency)}</dd>
              </div>
              <div className={styles.metaItem}>
                <dt className={styles.metaLabel}>人工复核</dt>
                <dd className={styles.metaValue}>{review.manual_review ? "是" : "否"}</dd>
              </div>
            </dl>
            <p className={styles.hint}>
              最终色码与命中规则、证据链入口同屏展示；趋势色、单次风险与一致性是记录字段，不单独承载结论。
            </p>
          </section>

          <section className={styles.section} id="evidence-chain">
            <h2 className={styles.sectionTitle}>证据链</h2>
            <p className={styles.notice}>
              每条命中规则对应一条证据；字段、观测值与阈值名称统一显示中文，原始编号由接口与留痕保存。
            </p>
            <EvidenceTable rows={review.evidence} />
            <p className={styles.footHint}>
              本页为只读复盘记录，不提供确认 / 修正 / 关闭等流转动作，也不展示面部图、音频与转写原文。
              如需查看原始内容，请前往对应复核任务详情中的折叠敏感面板。
            </p>
          </section>
        </>
      ) : null}
    </section>
  );
}
