/* 状态看板（ui@1.2 §4.3）：按单对象聚合，不提供跨对象对比、排行或榜单。 */
import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getDashboard } from "../../api/admin";
import type { DashboardData } from "../../api/types";
import {
  EmptyState,
  ErrorBanner,
  LoadingState,
  PageTitle,
} from "../../components/common/StateViews";
import { COLOR_META, COLOR_ORDER } from "../../lib/colors";
import { errorText } from "../../lib/errorMessages";
import { ApiError } from "../../lib/http";
import { OverdueBadge } from "../OverdueBadge";
import { TrendStrip } from "./TrendStrip";
import styles from "./Dashboard.module.css";

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

export default function DashboardPage() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadDashboard = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const envelope = await getDashboard();
      if (envelope.code !== 0 || envelope.data === null) {
        setData(null);
        setError(errorText(envelope.code, envelope.message));
        return;
      }
      setData(envelope.data);
    } catch (err) {
      setData(null);
      setError(
        err instanceof ApiError
          ? errorText(err.code, err.message)
          : "网络异常，请检查连接后重试。",
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadDashboard();
  }, [loadDashboard]);

  const lastSessionText = data ? formatTime(data.last_session_at) : "";

  return (
    <section>
      <PageTitle
        title="状态看板"
        description="单对象五色分布、近 7 天变化趋势、待复核数量与最近采集时间。"
      />

      {loading ? <LoadingState text="正在加载看板数据…" /> : null}

      {!loading && error ? (
        <ErrorBanner message={error} onRetry={() => void loadDashboard()} />
      ) : null}

      {!loading && !error && !data ? <EmptyState text="暂无看板数据。" /> : null}

      {!loading && !error && data ? (
        <>
          <div className={styles.grid}>
            <section className={styles.card}>
              <h2 className={styles.cardTitle}>单对象五色分布</h2>
              <div className={styles.distGrid}>
                {COLOR_ORDER.map((color) => {
                  const meta = COLOR_META[color];
                  const count = data.color_distribution[color] ?? 0;
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
                对象编号 <Link to={`/admin/subjects/${data.subject_id}`}>{data.subject_id}</Link>
              </p>
              <div className={styles.subjectOverdue}>
                <OverdueBadge subjectId={data.subject_id} overdue={data.overdue} />
              </div>
            </section>

            <section className={styles.card}>
              <h2 className={styles.cardTitle}>待复核与最近采集</h2>
              <p className={styles.infoLine}>
                待复核：
                <Link to={`/admin/tickets?subject_id=${encodeURIComponent(data.subject_id)}`}>
                  {data.pending_tickets} 件
                </Link>
              </p>
              <p className={styles.infoLine}>最近采集：{lastSessionText || "—"}</p>
            </section>
          </div>

          <section className={styles.card}>
            <h2 className={styles.cardTitle}>近 7 天趋势</h2>
            <TrendStrip items={data.trend_7d} />
          </section>
        </>
      ) : null}
    </section>
  );
}
