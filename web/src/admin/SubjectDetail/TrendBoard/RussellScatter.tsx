/* Russell 二维散点：X=效价，Y=信号强度（可切换唤醒度）。
 * 点色只来自该点所在自然日的复盘五色；无复盘点用中性灰且不展示色名/规则。
 * 每个点可键盘聚焦，聚焦后在图下详情面板展示与 tooltip 等价的信息与证据入口。
 */
import { useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import {
  CartesianGrid,
  ReferenceArea,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { TrendScatterPoint } from "../../../api/types";
import { COLOR_META } from "../../../lib/colors";
import {
  colorName,
  evidenceHref,
  formatMetric,
  NO_REVIEW_TEXT,
  ruleNames,
} from "./trendDisplay";
import styles from "./TrendBoard.module.css";

type YMode = "signal" | "arousal";

type DotShapeProps = {
  cx?: number;
  cy?: number;
  payload?: TrendScatterPoint;
};

type ScatterTooltipProps = {
  active?: boolean;
  payload?: Array<{ payload?: TrendScatterPoint }>;
};

function pointRadius(point: TrendScatterPoint): number {
  const clamped = Math.max(0, Math.min(100, point.signal));
  return 4.5 + (clamped / 100) * 6;
}

function pointAriaLabel(point: TrendScatterPoint): string {
  const parts = [
    point.date,
    `效价 ${formatMetric(point.valence, 2)}`,
    `信号 ${formatMetric(point.signal, 1)}`,
    `唤醒度 ${point.arousal === null ? "不可用" : formatMetric(point.arousal, 2)}`,
  ];
  if (point.review_color) {
    parts.push(`复盘${COLOR_META[point.review_color].label}色`);
    parts.push(`规则 ${ruleNames(point.review_rules)}`);
  } else {
    parts.push(NO_REVIEW_TEXT);
  }
  return parts.join("，");
}

function renderDot(raw: unknown, onFocus: (point: TrendScatterPoint) => void): ReactNode {
  const { cx, cy, payload } = raw as DotShapeProps;
  if (!payload || cx === undefined || cy === undefined) {
    return <g />;
  }
  const fill = payload.review_color
    ? `var(${COLOR_META[payload.review_color].token})`
    : "var(--trend-neutral)";
  return (
    <g
      tabIndex={0}
      role="img"
      aria-label={pointAriaLabel(payload)}
      onFocus={() => onFocus(payload)}
      onMouseEnter={() => onFocus(payload)}
    >
      <title>{pointAriaLabel(payload)}</title>
      <circle
        cx={cx}
        cy={cy}
        r={pointRadius(payload)}
        fill={fill}
        fillOpacity={0.88}
        stroke="var(--color-surface)"
        strokeWidth={1.5}
      />
    </g>
  );
}

function ScatterTooltip({ active, payload }: ScatterTooltipProps) {
  if (!active || !payload || payload.length === 0) {
    return null;
  }
  const point = payload[0]?.payload;
  if (!point) {
    return null;
  }
  return (
    <div className={styles.tooltip}>
      <p className={styles.tooltipTitle}>{point.date}</p>
      <p>效价：{formatMetric(point.valence, 2)}</p>
      <p>信号强度：{formatMetric(point.signal, 1)}</p>
      <p>唤醒度：{point.arousal === null ? "—" : formatMetric(point.arousal, 2)}</p>
      <p>复盘色：{colorName(point.review_color)}</p>
      <p>
        规则：
        {point.review_color
          ? ruleNames(point.review_rules)
          : "无复盘日不展示色名与规则"}
      </p>
      {point.review_color && point.review_id ? (
        <Link className={styles.detailLink} to={evidenceHref(point.review_id)}>
          查看依据
        </Link>
      ) : null}
    </div>
  );
}

export function RussellScatter({
  points,
}: {
  points: TrendScatterPoint[];
  /** 由看板容器传入，复盘详情深链不再使用 subject_id；保留以兼容既有调用方。 */
  subjectId: string;
}) {
  const [yMode, setYMode] = useState<YMode>("signal");
  const [focused, setFocused] = useState<TrendScatterPoint | null>(null);

  const plotPoints =
    yMode === "arousal" ? points.filter((point) => point.arousal !== null) : points;
  const missingArousal = points.length - plotPoints.length;
  const focusedPoint =
    focused !== null && points.some((point) => point.session_id === focused.session_id)
      ? focused
      : null;
  const activePoint = focusedPoint ?? points[0] ?? null;
  const boundary = yMode === "signal" ? 50 : 0.5;
  const yMax = yMode === "signal" ? 100 : 1;

  return (
    <div>
      <div className={styles.modeToggle} role="group" aria-label="Y 轴指标切换">
        <span className={styles.filterLabel}>Y 轴</span>
        <button
          type="button"
          className={`${styles.modeButton} ${
            yMode === "signal" ? styles.modeButtonActive : ""
          }`}
          aria-pressed={yMode === "signal"}
          onClick={() => setYMode("signal")}
        >
          信号强度（0–100）
        </button>
        <button
          type="button"
          className={`${styles.modeButton} ${
            yMode === "arousal" ? styles.modeButtonActive : ""
          }`}
          aria-pressed={yMode === "arousal"}
          onClick={() => setYMode("arousal")}
        >
          唤醒度（0–1）
        </button>
      </div>

      {plotPoints.length === 0 ? (
        <div className={styles.chartEmpty}>
          {yMode === "arousal"
            ? "该区间没有带唤醒度数值的已分析思想汇报，无法绘制唤醒度视图。"
            : "该区间没有可用的已分析思想汇报，无法绘制散点图。"}
        </div>
      ) : (
        <>
          <div className={`${styles.chartCanvas} ${styles.scatterCanvas}`}>
            <ResponsiveContainer width="100%" height="100%">
              <ScatterChart margin={{ top: 16, right: 20, bottom: 8, left: 0 }}>
                <CartesianGrid stroke="var(--color-border)" strokeDasharray="3 3" />
                <XAxis
                  type="number"
                  dataKey="valence"
                  name="效价"
                  domain={[-1, 1]}
                  ticks={[-1, -0.5, 0, 0.5, 1]}
                  tickFormatter={(value: number) => value.toFixed(1)}
                  label={{
                    value: "效价（-1 至 1）",
                    position: "insideBottom",
                    offset: -2,
                    fill: "var(--color-text-muted)",
                    fontSize: 11,
                  }}
                />
                <YAxis
                  type="number"
                  dataKey={yMode}
                  name={yMode === "signal" ? "信号强度" : "唤醒度"}
                  domain={[0, yMax]}
                  tickFormatter={(value: number) =>
                    yMode === "signal" ? String(value) : value.toFixed(1)
                  }
                  width={58}
                  label={{
                    value: yMode === "signal" ? "信号强度（0–100）" : "唤醒度（0–1）",
                    angle: -90,
                    position: "insideLeft",
                    fill: "var(--color-text-muted)",
                    fontSize: 11,
                  }}
                />
                <ReferenceLine x={0} stroke="var(--color-text-muted)" strokeDasharray="4 4" />
                <ReferenceArea
                  x1={0}
                  x2={1}
                  y1={boundary}
                  y2={yMax}
                  fill="var(--trend-quadrant-q1)"
                  fillOpacity={0.7}
                  label={{
                    value: yMode === "signal" ? "高效价 · 高信号" : "高效价 · 高唤醒",
                    position: "insideTopLeft",
                    fill: "var(--color-text-muted)",
                    fontSize: 11,
                  }}
                />
                <ReferenceArea
                  x1={-1}
                  x2={0}
                  y1={boundary}
                  y2={yMax}
                  fill="var(--trend-quadrant-q2)"
                  fillOpacity={0.7}
                  label={{
                    value: yMode === "signal" ? "低效价 · 高信号" : "低效价 · 高唤醒",
                    position: "insideTopLeft",
                    fill: "var(--color-text-muted)",
                    fontSize: 11,
                  }}
                />
                <ReferenceArea
                  x1={-1}
                  x2={0}
                  y1={0}
                  y2={boundary}
                  fill="var(--trend-quadrant-q3)"
                  fillOpacity={0.5}
                  label={{
                    value: yMode === "signal" ? "低效价 · 低信号" : "低效价 · 低唤醒",
                    position: "insideBottomLeft",
                    fill: "var(--color-text-muted)",
                    fontSize: 11,
                  }}
                />
                <ReferenceArea
                  x1={0}
                  x2={1}
                  y1={0}
                  y2={boundary}
                  fill="var(--trend-quadrant-q4)"
                  fillOpacity={0.5}
                  label={{
                    value: yMode === "signal" ? "高效价 · 低信号" : "高效价 · 低唤醒",
                    position: "insideBottomRight",
                    fill: "var(--color-text-muted)",
                    fontSize: 11,
                  }}
                />
                <Tooltip
                  cursor={{ strokeDasharray: "3 3" }}
                  content={<ScatterTooltip />}
                />
                <Scatter
                  name="已分析思想汇报"
                  data={plotPoints}
                  shape={(raw: unknown) => renderDot(raw, setFocused)}
                />
              </ScatterChart>
            </ResponsiveContainer>
          </div>

          <p className={styles.chartCaption}>
            X 轴为文本效价，Y 轴为{yMode === "signal" ? "文本信号强度" : "情绪唤醒度"}；
            点径随信号强度增大。点色只取自该会话所在自然日的复盘五色，灰色点表示无复盘。
            {yMode === "arousal" && missingArousal > 0
              ? ` 当前视图已隐藏 ${missingArousal} 个唤醒度缺失的点，可切回信号强度查看全部。`
              : ""}
          </p>

          <ul className={styles.legend}>
            {(["green", "blue", "yellow", "orange", "red"] as const).map((color) => (
              <li className={styles.legendItem} key={color}>
                <span
                  className={styles.swatch}
                  style={{ background: `var(${COLOR_META[color].token})` }}
                  aria-hidden="true"
                />
                {COLOR_META[color].label}色
              </li>
            ))}
            <li className={styles.legendItem}>
              <span
                className={`${styles.swatch} ${styles.swatchNeutral}`}
                aria-hidden="true"
              />
              {NO_REVIEW_TEXT}
            </li>
          </ul>

          {activePoint ? (
            <div className={styles.detailPanel} role="status" aria-live="polite">
              <p className={styles.detailTitle}>
                {activePoint.date} · {colorName(activePoint.review_color)}
              </p>
              <p className={styles.detailLine}>
                效价 {formatMetric(activePoint.valence, 2)} · 信号{" "}
                {formatMetric(activePoint.signal, 1)} · 唤醒度{" "}
                {activePoint.arousal === null ? "—" : formatMetric(activePoint.arousal, 2)}
              </p>
              <p className={styles.detailLine}>
                规则：
                {activePoint.review_color
                  ? ruleNames(activePoint.review_rules)
                  : "无复盘日不展示色名与规则"}
              </p>
              {activePoint.review_color && activePoint.review_id ? (
                <Link
                  className={styles.detailLink}
                  to={evidenceHref(activePoint.review_id)}
                >
                  查看依据
                </Link>
              ) : (
                <span className={styles.detailMuted}>无复盘，无证据入口</span>
              )}
            </div>
          ) : null}

          <p className={styles.panelNote}>
            散点仅用于观察区间内的分布与波动，不代表系统结论；每点可追溯的规则与证据以复盘记录为准。
          </p>
        </>
      )}
    </div>
  );
}
