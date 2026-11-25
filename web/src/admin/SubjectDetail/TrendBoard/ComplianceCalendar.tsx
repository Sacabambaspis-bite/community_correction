/* 行为依从性日历：签到、汇报两行，三态「已完成 / 逾期 / 未要求」。
 * 独立配色（成功实心 / 逾期描边 / 未要求中性灰），禁止复用五色风险令牌。
 * overdue 为按当前频率从最近完成日回溯的历史口径，与列表页实时逾期可能不同。
 */
import { useMemo, useState } from "react";
import type { SessionKind, TrendDay } from "../../../api/types";
import { formatShortDate, parseDateKey } from "./dateUtils";
import styles from "./TrendBoard.module.css";

type ComplianceState = "completed" | "overdue" | "not_required";

const STATE_TEXT: Record<ComplianceState, string> = {
  completed: "已完成",
  overdue: "逾期",
  not_required: "未要求",
};

const KIND_TEXT: Record<SessionKind, string> = {
  checkin: "签到",
  report: "思想汇报",
};

function stateOf(day: TrendDay, kind: SessionKind): ComplianceState {
  const behavior = day.behavior[kind];
  if (behavior.completed) {
    return "completed";
  }
  return behavior.expected ? "overdue" : "not_required";
}

const STATE_CLASS: Record<ComplianceState, string> = {
  completed: styles.complianceOk,
  overdue: styles.complianceOverdue,
  not_required: styles.complianceNone,
};

export function ComplianceCalendar({ days }: { days: TrendDay[] }) {
  const orderedDays = useMemo(
    () => [...days].sort((left, right) => left.date.localeCompare(right.date)),
    [days],
  );
  const [selected, setSelected] = useState<{ date: string; kind: SessionKind }>(() => ({
    date: orderedDays[0]?.date ?? "",
    kind: "checkin",
  }));

  if (orderedDays.length === 0) {
    return <div className={styles.chartEmpty}>该区间没有日期数据，无法绘制依从性日历。</div>;
  }

  const selectedDate = orderedDays.some((day) => day.date === selected.date)
    ? selected.date
    : orderedDays[0].date;
  const selectedDay = orderedDays.find((day) => day.date === selectedDate) ?? null;
  const selectedState = selectedDay
    ? stateOf(selectedDay, selected.kind)
    : "not_required";

  return (
    <div>
      <div className={styles.complianceRows}>
        {(["checkin", "report"] as const).map((kind) => (
          <div className={styles.complianceRow} key={kind}>
            <span className={styles.complianceLabel}>{KIND_TEXT[kind]}</span>
            <div className={styles.complianceCells}>
              {orderedDays.map((day, index) => {
                const state = stateOf(day, kind);
                const date = parseDateKey(day.date);
                const weekGap =
                  index > 0 && date !== null && date.getDay() === 1
                    ? ` ${styles.complianceWeekGap}`
                    : "";
                const isSelected =
                  selectedDate === day.date && selected.kind === kind;
                const label = `${day.date} ${KIND_TEXT[kind]}：${STATE_TEXT[state]}`;
                return (
                  <button
                    type="button"
                    key={`${kind}-${day.date}`}
                    className={`${styles.complianceCell} ${STATE_CLASS[state]}${
                      isSelected ? ` ${styles.complianceSelected}` : ""
                    }${weekGap}`}
                    aria-label={label}
                    aria-pressed={isSelected}
                    title={label}
                    onClick={() => setSelected({ date: day.date, kind })}
                    onFocus={() => setSelected({ date: day.date, kind })}
                    onMouseEnter={() => setSelected({ date: day.date, kind })}
                  >
                    <span className={styles.srOnly}>{label}</span>
                  </button>
                );
              })}
            </div>
          </div>
        ))}
      </div>

      <ul className={styles.legend}>
        <li className={styles.legendItem}>
          <span className={`${styles.swatch} ${styles.complianceOk}`} aria-hidden="true" />
          已完成
        </li>
        <li className={styles.legendItem}>
          <span
            className={`${styles.swatch} ${styles.complianceOverdue}`}
            aria-hidden="true"
          />
          逾期（描边）
        </li>
        <li className={styles.legendItem}>
          <span
            className={`${styles.swatch} ${styles.complianceNone}`}
            aria-hidden="true"
          />
          未要求
        </li>
      </ul>

      {selectedDay ? (
        <div className={styles.detailPanel} role="status" aria-live="polite">
          <p className={styles.detailTitle}>
            {selectedDay.date} · {KIND_TEXT[selected.kind]} · {STATE_TEXT[selectedState]}
          </p>
          <p className={styles.detailLine}>
            当日会话：共 {selectedDay.sessions.total} 次（签到{" "}
            {selectedDay.sessions.checkin} / 汇报 {selectedDay.sessions.report}）
          </p>
          <p className={styles.detailLine}>
            历史回溯口径：期望 {selectedDay.behavior[selected.kind].expected ? "是" : "否"} ·
            完成 {selectedDay.behavior[selected.kind].completed ? "是" : "否"}
          </p>
        </div>
      ) : null}

      <p className={styles.chartCaption}>
        每格为一天（{orderedDays.length} 天，起点 {formatShortDate(orderedDays[0].date)}）。
        逾期为按对象当前频率从最近完成日回溯的历史口径，与列表页实时逾期、复核任务截止时间可能不同。
      </p>
    </div>
  );
}
