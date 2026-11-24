/* 敏感字段默认折叠；展开时由调用方触发留痕（ui@1.2 §4.2/§4.5）。 */
import { useState, type ReactNode } from "react";
import styles from "./SensitivePanel.module.css";

type SensitivePanelProps = {
  title: string;
  hint?: string;
  children?: ReactNode;
  onExpand?: () => void;
};

export function SensitivePanel({
  title,
  hint = "展开即记录查看行为",
  children,
  onExpand,
}: SensitivePanelProps) {
  const [open, setOpen] = useState(false);

  return (
    <section className={styles.panel}>
      <header className={styles.header}>
        <span className={styles.title}>{title}</span>
        <button
          type="button"
          className={styles.toggle}
          onClick={() => {
            if (!open) {
              onExpand?.();
            }
            setOpen(!open);
          }}
        >
          {open ? "收起" : "展开"}
        </button>
      </header>
      {open ? (
        <div className={styles.body}>
          <p className={styles.hint}>{hint}</p>
          {children ?? (
            <p className={styles.placeholder}>
              敏感内容将在接口接入后展示（默认折叠，展开留痕）。
            </p>
          )}
        </div>
      ) : null}
    </section>
  );
}
