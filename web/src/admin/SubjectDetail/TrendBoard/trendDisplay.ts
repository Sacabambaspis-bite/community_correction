/* 趋势看板的展示映射：色名、证据入口与数字格式。
 * 色码只能引用 COLOR_META / 规则映射，不在前端自造色值。
 */
import { COLOR_META, type Color } from "../../../lib/colors";
import { ruleListText } from "../../../lib/ruleText";

export const NO_REVIEW_TEXT = "无复盘";

/** 有复盘才给中文色名；无复盘时不得暗示风险等级。 */
export function colorName(color: Color | null): string {
  return color ? `${COLOR_META[color].label}色` : NO_REVIEW_TEXT;
}

export function ruleNames(rules: string[]): string {
  return rules.length > 0 ? ruleListText(rules) : "—";
}

/** 证据入口直达单条复盘详情（ui@1.2 §4.6）；缺少 review_id 的点位不得伪造链接。 */
export function evidenceHref(reviewId: string): string {
  return `/admin/reviews/${encodeURIComponent(reviewId)}`;
}

export function formatMetric(value: number | null, digits = 2): string {
  if (value === null || Number.isNaN(value)) {
    return "—";
  }
  return value.toFixed(digits);
}

export function formatPercent(rate: number): string {
  if (!Number.isFinite(rate)) {
    return "—";
  }
  return `${(rate * 100).toFixed(1)}%`;
}

/** 图表专用配色：刻意不使用五色风险令牌，避免与复盘色混淆。 */
export const CHART_SERIES_COLORS = {
  degraded: "#64748b",
  low: "#0e7490",
  conflict: "#b45309",
} as const;
