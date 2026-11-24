import type { ReactNode } from "react";
import styles from "./StateViews.module.css";

export function LoadingState({ text = "加载中…" }: { text?: string }) {
  return (
    <div className={styles.state} role="status">
      {text}
    </div>
  );
}

export function EmptyState({ text = "暂无数据" }: { text?: string }) {
  return <div className={styles.state}>{text}</div>;
}

export function ErrorBanner({
  message,
  onRetry,
}: {
  message: string;
  onRetry?: () => void;
}) {
  return (
    <div className={`${styles.state} ${styles.error}`} role="alert">
      <span>{message}</span>
      {onRetry ? (
        <button type="button" className={styles.retry} onClick={onRetry}>
          重试
        </button>
      ) : null}
    </div>
  );
}

export function Forbidden({ text = "无权限访问该页面" }: { text?: string }) {
  return <div className={`${styles.state} ${styles.error}`}>{text}</div>;
}

export function PageTitle({
  title,
  description,
  extra,
}: {
  title: string;
  description?: string;
  extra?: ReactNode;
}) {
  return (
    <div className={styles.titleRow}>
      <div>
        <h1 className={styles.title}>{title}</h1>
        {description ? <p className={styles.description}>{description}</p> : null}
      </div>
      {extra ? <div className={styles.extra}>{extra}</div> : null}
    </div>
  );
}
