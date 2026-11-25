/* 单个图表的折叠容器（ui@1.2 §4.2 / 补记 12）：受控组件。
 * 按钮只显示标题与展开指示，描述放在面板顶部；面板仅在展开时挂载，
 * 避免隐藏容器内 Recharts 尺寸为 0 导致空白或错位。
 */
import type { ReactNode } from "react";
import styles from "./TrendBoard.module.css";

type ChartCollapsibleProps = {
  id: string;
  title: string;
  description: string;
  open: boolean;
  onToggle: () => void;
  children: ReactNode;
};

export function ChartCollapsible({
  id,
  title,
  description,
  open,
  onToggle,
  children,
}: ChartCollapsibleProps) {
  const panelId = `${id}-panel`;

  return (
    <div className={styles.chartCollapsible}>
      <button
        type="button"
        className={styles.collapseButton}
        aria-expanded={open}
        aria-controls={panelId}
        onClick={onToggle}
      >
        <span className={styles.collapseTitle}>{title}</span>
        <svg
          className={`${styles.chevron} ${open ? styles.chevronOpen : ""}`}
          viewBox="0 0 16 16"
          aria-hidden="true"
          focusable="false"
        >
          <path
            d="M4 6l4 4 4-4"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.6"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </button>
      {open ? (
        <div
          id={panelId}
          className={styles.collapsePanel}
          role="region"
          aria-label={title}
        >
          <p className={styles.chartDesc}>{description}</p>
          {children}
        </div>
      ) : null}
    </div>
  );
}
