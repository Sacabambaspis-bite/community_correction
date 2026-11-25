/* 五色日历热力图（Flex 自绘）：按日期从左到右排列，容器不足时自动折行。
 * 色块只使用 tokens.css 的五色变量；无复盘日为中性灰，不承载风险信息。
 * 每个色块可键盘聚焦，聚焦或点击后在图下展示日期、色名、规则与证据入口。
 */
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import type { TrendDay } from "../../../api/types";
import { COLOR_META, COLOR_ORDER, type Color } from "../../../lib/colors";
import {
  colorName,
  evidenceHref,
  NO_REVIEW_TEXT,
  ruleNames,
} from "./trendDisplay";
import styles from "./TrendBoard.module.css";

function swatchBackground(color: Color): string {
  return `var(${COLOR_META[color].token})`;
}

export function ColorCalendarHeatmap({
  days,
}: {
  days: TrendDay[];
  /** 由看板容器传入，复盘详情深链不再使用 subject_id；保留以兼容既有调用方。 */
  subjectId: string;
}) {
  const orderedDays = useMemo(
    () => [...days].sort((left, right) => left.date.localeCompare(right.date)),
    [days],
  );
  const dayMap = useMemo(
    () => new Map(orderedDays.map((day) => [day.date, day])),
    [orderedDays],
  );

  const [selectedDate, setSelectedDate] = useState<string>(() => {
    const firstReview = orderedDays.find((day) => day.review !== null);
    return firstReview?.date ?? orderedDays[0]?.date ?? "";
  });

  if (orderedDays.length === 0) {
    return <div className={styles.chartEmpty}>该区间没有日期数据，无法绘制热力图。</div>;
  }

  const fallbackDate =
    orderedDays.find((day) => day.review !== null)?.date ?? orderedDays[0].date;
  const effectiveSelectedDate = dayMap.has(selectedDate) ? selectedDate : fallbackDate;
  const selectedDay = dayMap.get(effectiveSelectedDate) ?? null;

  return (
    <div>
      <div
        className={styles.calendarDayList}
        role="group"
        aria-label="五色日历热力图，按日期从左到右排列"
      >
        {orderedDays.map((day) => {
          const dateKey = day.date;
          const review = day.review;
          const selected = dateKey === effectiveSelectedDate;
          const background = review
            ? swatchBackground(review.color)
            : "var(--trend-neutral)";
          const aria = review
            ? `${dateKey}，复盘${COLOR_META[review.color].label}色，规则 ${ruleNames(
                review.rules_fired,
              )}，可查看依据`
            : `${dateKey}，无复盘，不展示色名与规则`;
          return (
            <div className={styles.calendarDayCell} key={dateKey}>
              <button
                type="button"
                className={`${styles.calendarCell} ${
                  review ? "" : styles.calendarCellNoReview
                } ${selected ? styles.calendarCellSelected : ""}`}
                style={{ background }}
                aria-label={aria}
                aria-pressed={selected}
                title={aria}
                onClick={() => setSelectedDate(dateKey)}
                onFocus={() => setSelectedDate(dateKey)}
              >
                <span className={styles.srOnly}>{dateKey}</span>
              </button>
              <span className={styles.calendarDateLabel}>{dateKey.slice(5)}</span>
            </div>
          );
        })}
      </div>

      <ul className={styles.legend}>
        {COLOR_ORDER.map((color) => (
          <li className={styles.legendItem} key={color}>
            <span
              className={styles.swatch}
              style={{ background: swatchBackground(color) }}
              aria-hidden="true"
            />
            {COLOR_META[color].label}色
          </li>
        ))}
        <li className={styles.legendItem}>
          <span className={`${styles.swatch} ${styles.swatchNeutral}`} aria-hidden="true" />
          {NO_REVIEW_TEXT}
        </li>
      </ul>

      {selectedDay ? (
        <div className={styles.detailPanel} role="status" aria-live="polite">
          <p className={styles.detailTitle}>
            {selectedDay.date} · {colorName(selectedDay.review?.color ?? null)}
          </p>
          {selectedDay.review ? (
            <>
              <p className={styles.detailLine}>
                规则：{ruleNames(selectedDay.review.rules_fired)}
              </p>
              <p className={styles.detailLine}>
                一致性：{selectedDay.review.consistency} ·
                {selectedDay.review.manual_review ? " 需人工复核" : " 未标记强制复核"}
              </p>
              {selectedDay.review.review_id ? (
                <Link
                  className={styles.detailLink}
                  to={evidenceHref(selectedDay.review.review_id)}
                >
                  查看依据
                </Link>
              ) : (
                <span className={styles.detailMuted}>该复盘缺少 review_id，暂不提供证据入口</span>
              )}
            </>
          ) : (
            <>
              <p className={styles.detailLine}>
                当日无复盘记录，色块为中性灰，不承载风险信息。
              </p>
              <span className={styles.detailMuted}>无复盘，无证据入口</span>
            </>
          )}
          <p className={styles.detailLine}>
            会话：共 {selectedDay.sessions.total} 次（签到 {selectedDay.sessions.checkin} / 汇报{" "}
            {selectedDay.sessions.report}）
          </p>
        </div>
      ) : null}

      <p className={styles.panelNote}>
        日期从左到右排列，容器较窄时自动折行；色块可聚焦或点击查看日期、规则与证据入口。
        灰色 {NO_REVIEW_TEXT} 块不代表任何风险等级。
      </p>
    </div>
  );
}
