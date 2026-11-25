/* 趋势看板的日期工具：全部按本地自然日处理，避免 YYYY-MM-DD 被按 UTC 解析而偏移。 */

const DAY_MS = 24 * 60 * 60 * 1000;

function pad2(value: number): string {
  return String(value).padStart(2, "0");
}

export function toDateKey(date: Date): string {
  return `${date.getFullYear()}-${pad2(date.getMonth() + 1)}-${pad2(date.getDate())}`;
}

export function parseDateKey(key: string): Date | null {
  const matched = /^(\d{4})-(\d{2})-(\d{2})$/.exec(key);
  if (!matched) {
    return null;
  }
  const year = Number(matched[1]);
  const month = Number(matched[2]);
  const day = Number(matched[3]);
  const date = new Date(year, month - 1, day);
  if (
    date.getFullYear() !== year ||
    date.getMonth() !== month - 1 ||
    date.getDate() !== day
  ) {
    return null;
  }
  return date;
}

function dayNumber(key: string): number | null {
  const date = parseDateKey(key);
  if (!date) {
    return null;
  }
  return Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()) / DAY_MS;
}

export function addDaysKey(key: string, delta: number): string | null {
  const date = parseDateKey(key);
  if (!date) {
    return null;
  }
  const next = new Date(date.getFullYear(), date.getMonth(), date.getDate() + delta);
  return toDateKey(next);
}

/** 闭区间自然日天数；日期非法返回 null。 */
export function inclusiveDayCount(startKey: string, endKey: string): number | null {
  const start = dayNumber(startKey);
  const end = dayNumber(endKey);
  if (start === null || end === null) {
    return null;
  }
  return end - start + 1;
}

export function todayKey(): string {
  return toDateKey(new Date());
}

export function formatShortDate(key: string): string {
  return key.length >= 10 ? key.slice(5).replace("-", "/") : key;
}

export const WEEKDAY_LABELS = ["一", "二", "三", "四", "五", "六", "日"] as const;

/** 周一为一周起点；返回按周分组的 7 天格子，区间外为 null（仅占位，不渲染数据）。 */
export function calendarWeeks(startKey: string, endKey: string): (string | null)[][] {
  const start = parseDateKey(startKey);
  const end = parseDateKey(endKey);
  if (!start || !end || start > end) {
    return [];
  }

  const leading = (start.getDay() + 6) % 7;
  const cursor = new Date(start.getFullYear(), start.getMonth(), start.getDate() - leading);
  const weeks: (string | null)[][] = [];

  while (cursor <= end) {
    const week: (string | null)[] = [];
    for (let index = 0; index < 7; index += 1) {
      const current = new Date(
        cursor.getFullYear(),
        cursor.getMonth(),
        cursor.getDate() + index,
      );
      week.push(current >= start && current <= end ? toDateKey(current) : null);
    }
    weeks.push(week);
    cursor.setDate(cursor.getDate() + 7);
  }
  return weeks;
}
