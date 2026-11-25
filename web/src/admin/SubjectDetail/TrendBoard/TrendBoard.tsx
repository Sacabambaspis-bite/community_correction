/* 心理状态趋势（ui@1.2 §4.2 / 补记 11、12）：对接 api@1.5 §7.18。
 * 已并入对象详情「状态概览」，不设独立区块标题与容器；负责日期区间草稿、竞态请求、
 * 加载/空/错态与四个可折叠图表的编排。不做任何处置入口或跨对象对比。
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { getSubjectTrends } from "../../../api/admin";
import type { SubjectTrends, TrendDay, TrendSummary } from "../../../api/types";
import { ErrorBanner } from "../../../components/common/StateViews";
import { ApiError } from "../../../lib/http";
import { errorText } from "../../../lib/errorMessages";
import { ChartCollapsible } from "./ChartCollapsible";
import { ColorCalendarHeatmap } from "./ColorCalendarHeatmap";
import { ComplianceCalendar } from "./ComplianceCalendar";
import { addDaysKey, inclusiveDayCount, parseDateKey, todayKey } from "./dateUtils";
import { PsychInsightList } from "./PsychInsightList";
import { RussellScatter } from "./RussellScatter";
import { StabilityBarChart } from "./StabilityBarChart";
import { TrendDateRange, type TrendPreset } from "./TrendDateRange";
import { formatMetric, formatPercent } from "./trendDisplay";
import styles from "./TrendBoard.module.css";

const MAX_RANGE_DAYS = 366;

type ChartKey = "russell" | "heatmap" | "stability" | "compliance";

function defaultRange(): { start: string; end: string } {
  const end = todayKey();
  return { start: addDaysKey(end, -13) ?? end, end };
}

function dayHasData(day: TrendDay): boolean {
  return (
    day.review !== null ||
    day.sessions.total > 0 ||
    day.consistency.degraded + day.consistency.low + day.consistency.conflict > 0 ||
    day.behavior.checkin.expected ||
    day.behavior.report.expected
  );
}

function SummaryBar({ summary }: { summary: TrendSummary }) {
  const items = [
    { label: "平均效价", value: formatMetric(summary.avg_valence, 2) },
    { label: "平均信号", value: formatMetric(summary.avg_signal, 1) },
    { label: "效价标准差", value: formatMetric(summary.valence_std, 2) },
    { label: "信号标准差", value: formatMetric(summary.signal_std, 1) },
    { label: "覆盖率", value: formatPercent(summary.coverage_rate) },
    { label: "有效样本数", value: String(summary.analyzed_count) },
  ];

  return (
    <section className={styles.summaryPanel} aria-label="区间汇总">
      <div className={styles.summaryGrid}>
        {items.map((item) => (
          <div className={styles.summaryItem} key={item.label}>
            <span className={styles.summaryLabel}>{item.label}</span>
            <span className={styles.summaryValue}>{item.value}</span>
          </div>
        ))}
      </div>
      <p className={styles.panelNote}>
        覆盖率为区间内应有采集日的完成率；标准差在有效样本数小于 2 时显示「—」。
        均值与标准差只描述已分析思想汇报的文本指标，不代表系统结论。
      </p>
    </section>
  );
}

function TrendSkeleton() {
  return (
    <div className={styles.skeletonWrap} role="status" aria-busy="true">
      <span className={styles.srOnly}>正在加载心理状态趋势数据…</span>
      <div className={`${styles.skeletonBar} ${styles.skeletonSummary}`} />
      <div className={styles.skeletonList}>
        {[0, 1, 2, 3].map((index) => (
          <div
            className={`${styles.skeletonBar} ${styles.skeletonButton}`}
            key={index}
          />
        ))}
      </div>
    </div>
  );
}

export function TrendBoard({ subjectId }: { subjectId: string }) {
  const [initialRange] = useState(defaultRange);
  const [draftStart, setDraftStart] = useState(initialRange.start);
  const [draftEnd, setDraftEnd] = useState(initialRange.end);
  const [activePreset, setActivePreset] = useState<TrendPreset | null>(14);
  const [applied, setApplied] = useState(initialRange);
  const [data, setData] = useState<SubjectTrends | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [validationError, setValidationError] = useState<string | null>(null);
  /* 四个图表默认全部收起；切换日期区间重新查询时保持各自展开状态。 */
  const [openCharts, setOpenCharts] = useState<Record<ChartKey, boolean>>({
    russell: false,
    heatmap: false,
    stability: false,
    compliance: false,
  });
  const requestSeq = useRef(0);

  const load = useCallback(
    async (start: string, end: string) => {
      if (!subjectId) {
        setData(null);
        setError("缺少对象编号，无法加载心理状态趋势。");
        setLoading(false);
        return;
      }
      requestSeq.current += 1;
      const seq = requestSeq.current;
      setApplied({ start, end });
      setLoading(true);
      setError(null);
      setData(null);
      try {
        const envelope = await getSubjectTrends(subjectId, start, end);
        if (requestSeq.current !== seq) {
          return;
        }
        if (envelope.code !== 0 || envelope.data === null) {
          setError(errorText(envelope.code, envelope.message));
          return;
        }
        setData(envelope.data);
      } catch (err) {
        if (requestSeq.current !== seq) {
          return;
        }
        setError(
          err instanceof ApiError
            ? errorText(err.code, err.message)
            : "网络异常，请检查连接后重试。",
        );
      } finally {
        if (requestSeq.current === seq) {
          setLoading(false);
        }
      }
    },
    [subjectId],
  );

  useEffect(() => {
    void load(initialRange.start, initialRange.end);
    return () => {
      /* 卸载或重新挂载时丢弃在途响应。 */
      requestSeq.current += 1;
    };
  }, [load, initialRange.end, initialRange.start]);

  const changeStart = (value: string) => {
    setDraftStart(value);
    setActivePreset(null);
  };

  const changeEnd = (value: string) => {
    setDraftEnd(value);
    setActivePreset(null);
  };

  const applyPreset = (days: TrendPreset) => {
    const end = todayKey();
    const start = addDaysKey(end, -(days - 1)) ?? end;
    setDraftStart(start);
    setDraftEnd(end);
    setActivePreset(days);
    setValidationError(null);
  };

  const applyRange = () => {
    const start = parseDateKey(draftStart);
    const end = parseDateKey(draftEnd);
    if (!start || !end) {
      setValidationError("请填写完整的起止日期（YYYY-MM-DD）。");
      return;
    }
    if (start > end) {
      setValidationError("开始日期不能晚于结束日期。");
      return;
    }
    const span = inclusiveDayCount(draftStart, draftEnd);
    if (span === null || span > MAX_RANGE_DAYS) {
      setValidationError(`查询跨度不能超过 ${MAX_RANGE_DAYS} 天，请缩小日期范围。`);
      return;
    }
    setValidationError(null);
    void load(draftStart, draftEnd);
  };

  const toggleChart = (key: ChartKey) => {
    setOpenCharts((current) => ({ ...current, [key]: !current[key] }));
  };

  const hasDayData = data !== null && data.days.some(dayHasData);
  const hasScatter = data !== null && data.scatter_points.length > 0;

  return (
    <div className={styles.trendBlock}>
      <TrendDateRange
        start={draftStart}
        end={draftEnd}
        activePreset={activePreset}
        appliedStart={applied.start}
        appliedEnd={applied.end}
        loading={loading}
        validationError={validationError}
        onStartChange={changeStart}
        onEndChange={changeEnd}
        onPreset={applyPreset}
        onApply={applyRange}
      />

      {loading ? <TrendSkeleton /> : null}

      {!loading && error ? (
        <ErrorBanner
          message={error}
          onRetry={() => void load(applied.start, applied.end)}
        />
      ) : null}

      {!loading && !error && data && !hasDayData ? (
        <div className={styles.boardEmpty} role="status">
          <p className={styles.emptyTitle}>该区间没有会话或复盘记录</p>
          <p className={styles.emptyText}>
            可扩大日期范围后重新查询；也可按约定继续完成签到与思想汇报，数据产生后此处会自动呈现。
          </p>
        </div>
      ) : null}

      {!loading && !error && data && hasDayData ? (
        <>
          <p className={styles.appliedRange}>
            当前展示 {data.start_date} 至 {data.end_date}，共 {data.days.length} 天；
            有效分析样本 {data.summary.analyzed_count} 条。
          </p>

          <SummaryBar summary={data.summary} />
          <PsychInsightList signals={data.summary.signals} />

          <div className={styles.chartList}>
            <ChartCollapsible
              id="trend-chart-russell"
              title="Russell 二维散点图"
              description="X 轴为文本效价、Y 轴为信号强度（可切换唤醒度）；点色只来自当日复盘五色，灰色点表示无复盘。"
              open={openCharts.russell}
              onToggle={() => toggleChart("russell")}
            >
              {hasScatter ? (
                <RussellScatter
                  points={data.scatter_points}
                  subjectId={data.subject_id}
                />
              ) : (
                <div className={styles.chartEmpty}>
                  该区间没有可用的已分析思想汇报，无法绘制散点图。
                </div>
              )}
            </ChartCollapsible>

            <ChartCollapsible
              id="trend-chart-heatmap"
              title="五色日历热力图"
              description="色块为当日复盘五色；无复盘日为中性灰。聚焦或点击色块可查看色名、规则与证据入口。"
              open={openCharts.heatmap}
              onToggle={() => toggleChart("heatmap")}
            >
              <ColorCalendarHeatmap days={data.days} subjectId={data.subject_id} />
            </ChartCollapsible>

            <ChartCollapsible
              id="trend-chart-stability"
              title="稳定性与一致性柱状图"
              description="按日展示分析降级、一致性偏低与跨模态冲突三项计数，缺失日期按 0 展示。"
              open={openCharts.stability}
              onToggle={() => toggleChart("stability")}
            >
              <StabilityBarChart days={data.days} />
            </ChartCollapsible>

            <ChartCollapsible
              id="trend-chart-compliance"
              title="行为依从性日历"
              description="签到与思想汇报两行，按日展示「已完成 / 逾期 / 未要求」；逾期为历史回溯口径。"
              open={openCharts.compliance}
              onToggle={() => toggleChart("compliance")}
            >
              <ComplianceCalendar days={data.days} />
            </ChartCollapsible>
          </div>

          <p className={styles.panelNote}>
            数据来源为趋势聚合接口，只含聚合指标，不包含转写原文、音频或面部影像。
            任何色码与提示都需结合证据链、面谈与人工复核使用。
          </p>
        </>
      ) : null}
    </div>
  );
}
