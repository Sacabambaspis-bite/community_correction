/* 7 日趋势（ui@1.2 §4.3，已并入对象详情）：日期 + 中文色名 + 小色块，
 * 保持单对象，不做多对象对比。 */
import { COLOR_META, type Color } from "../../lib/colors";
import styles from "./SubjectDetail.module.css";

type TrendPoint = {
  date: string;
  color: Color;
};

export function TrendStrip({ items }: { items: TrendPoint[] }) {
  if (items.length === 0) {
    return <p className={styles.trendEmpty}>近 7 天暂无可展示的趋势数据。</p>;
  }

  return (
    <div className={styles.trendStrip}>
      {items.map((item) => {
        const meta = COLOR_META[item.color];
        return (
          <div
            className={styles.trendItem}
            key={item.date}
            aria-label={`${item.date} ${meta.label}`}
          >
            <span className={styles.trendDate}>{item.date}</span>
            <span
              className={styles.swatch}
              style={{ background: `var(${meta.token})` }}
              aria-hidden="true"
            />
            <span className={styles.trendLabel}>{meta.label}</span>
          </div>
        );
      })}
    </div>
  );
}
