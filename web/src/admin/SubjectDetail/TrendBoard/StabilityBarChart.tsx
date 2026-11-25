/* 稳定性与一致性柱状图：按日展示 degraded / consistency=low / conflict 三项计数。
 * 缺失日按 0 展示；系列配色为图表专用色，刻意不复用五色风险令牌。
 */
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { TrendDay } from "../../../api/types";
import { formatShortDate } from "./dateUtils";
import { CHART_SERIES_COLORS } from "./trendDisplay";
import styles from "./TrendBoard.module.css";

type StabilityDatum = {
  date: string;
  degraded: number;
  low: number;
  conflict: number;
};

type StabilityTooltipProps = {
  active?: boolean;
  payload?: Array<{ payload?: StabilityDatum }>;
};

function StabilityTooltip({ active, payload }: StabilityTooltipProps) {
  if (!active || !payload || payload.length === 0) {
    return null;
  }
  const datum = payload[0]?.payload;
  if (!datum) {
    return null;
  }
  return (
    <div className={styles.tooltip}>
      <p className={styles.tooltipTitle}>{datum.date}</p>
      <p>分析降级：{datum.degraded}</p>
      <p>一致性偏低：{datum.low}</p>
      <p>跨模态冲突：{datum.conflict}</p>
    </div>
  );
}

export function StabilityBarChart({ days }: { days: TrendDay[] }) {
  if (days.length === 0) {
    return <div className={styles.chartEmpty}>该区间没有日期数据，无法绘制柱状图。</div>;
  }

  const data: StabilityDatum[] = [...days]
    .sort((left, right) => left.date.localeCompare(right.date))
    .map((day) => ({
      date: day.date,
      degraded: day.consistency.degraded,
      low: day.consistency.low,
      conflict: day.consistency.conflict,
    }));

  return (
    <div>
      <div className={`${styles.chartCanvas} ${styles.barCanvas}`}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 8, right: 12, bottom: 4, left: 0 }}>
            <CartesianGrid stroke="var(--color-border)" strokeDasharray="3 3" vertical={false} />
            <XAxis
              dataKey="date"
              tickFormatter={formatShortDate}
              interval="preserveStartEnd"
              minTickGap={16}
              tick={{ fontSize: 11 }}
            />
            <YAxis allowDecimals={false} width={36} tick={{ fontSize: 11 }} />
            <Tooltip content={<StabilityTooltip />} cursor={{ fill: "var(--color-bg)" }} />
            <Legend />
            <Bar
              dataKey="degraded"
              name="分析降级"
              fill={CHART_SERIES_COLORS.degraded}
              radius={[2, 2, 0, 0]}
            />
            <Bar
              dataKey="low"
              name="一致性偏低"
              fill={CHART_SERIES_COLORS.low}
              radius={[2, 2, 0, 0]}
            />
            <Bar
              dataKey="conflict"
              name="跨模态冲突"
              fill={CHART_SERIES_COLORS.conflict}
              radius={[2, 2, 0, 0]}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <p className={styles.chartCaption}>
        缺失日期按 0 展示；三类计数互不排斥，均来自当日已分析会话。柱色为图表专用配色，与复盘五色无关。
      </p>
    </div>
  );
}
