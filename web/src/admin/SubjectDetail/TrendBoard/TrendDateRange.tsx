/* 日期区间条：预设 7 / 14 / 30 天 + 自定义起止；改动只更新草稿，点「查询」才请求。 */
import type { FormEvent } from "react";
import styles from "./TrendBoard.module.css";

export type TrendPreset = 7 | 14 | 30;

type TrendDateRangeProps = {
  start: string;
  end: string;
  activePreset: TrendPreset | null;
  appliedStart: string;
  appliedEnd: string;
  loading: boolean;
  validationError: string | null;
  onStartChange: (value: string) => void;
  onEndChange: (value: string) => void;
  onPreset: (days: TrendPreset) => void;
  onApply: () => void;
};

const PRESETS: TrendPreset[] = [7, 14, 30];

export function TrendDateRange({
  start,
  end,
  activePreset,
  appliedStart,
  appliedEnd,
  loading,
  validationError,
  onStartChange,
  onEndChange,
  onPreset,
  onApply,
}: TrendDateRangeProps) {
  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    onApply();
  };

  return (
    <form className={styles.rangeForm} onSubmit={submit} aria-label="趋势日期区间">
      <div className={styles.presetGroup} role="group" aria-label="快捷区间">
        <span className={styles.filterLabel}>快捷区间</span>
        <div className={styles.presetButtons}>
          {PRESETS.map((days) => (
            <button
              key={days}
              type="button"
              className={`${styles.presetButton} ${
                activePreset === days ? styles.presetButtonActive : ""
              }`}
              aria-pressed={activePreset === days}
              disabled={loading}
              onClick={() => onPreset(days)}
            >
              近 {days} 天
            </button>
          ))}
        </div>
      </div>

      <label className={styles.rangeField}>
        <span className={styles.filterLabel}>开始日期</span>
        <input
          className={styles.input}
          type="date"
          value={start}
          required
          disabled={loading}
          onChange={(event) => onStartChange(event.target.value)}
        />
      </label>

      <label className={styles.rangeField}>
        <span className={styles.filterLabel}>结束日期</span>
        <input
          className={styles.input}
          type="date"
          value={end}
          required
          disabled={loading}
          onChange={(event) => onEndChange(event.target.value)}
        />
      </label>

      <button className={styles.queryButton} type="submit" disabled={loading}>
        {loading ? "查询中…" : "查询"}
      </button>

      <p className={styles.rangeNote}>
        当前展示：{appliedStart} 至 {appliedEnd}；默认近 14 天，跨度上限 366 天。
        {start !== appliedStart || end !== appliedEnd
          ? " 草稿已修改，点击「查询」后生效。"
          : ""}
      </p>

      {validationError ? (
        <p className={styles.validationError} role="alert">
          {validationError}
        </p>
      ) : null}
    </form>
  );
}
