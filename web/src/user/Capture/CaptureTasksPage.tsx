/* 模块选择页：展示签到与思想汇报的频率、最近完成时间和中性逾期提示。 */
import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getTasks } from "../../api/user";
import type { SessionKind, UserTasksData } from "../../api/types";
import {
  EmptyState,
  ErrorBanner,
  LoadingState,
  PageTitle,
} from "../../components/common/StateViews";
import { errorText } from "../../lib/errorMessages";
import { ApiError } from "../../lib/http";
import styles from "./Capture.module.css";

const TASK_MODULES: Array<{
  kind: SessionKind;
  title: string;
  description: string;
  to: string;
  action: string;
}> = [
  {
    kind: "checkin",
    title: "刷脸签到",
    description: "按页面提示正视摄像头，完成本次签到。",
    to: "/capture/checkin",
    action: "进入签到",
  },
  {
    kind: "report",
    title: "录音思想汇报",
    description: "通过摄像头与录音，说说近期的生活情况。",
    to: "/capture/report",
    action: "进入思想汇报",
  },
];

function formatDateTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString("zh-CN", { hour12: false });
}

export default function CaptureTasksPage() {
  const [tasks, setTasks] = useState<UserTasksData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadTasks = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const envelope = await getTasks();
      if (envelope.code !== 0 || envelope.data === null) {
        setTasks(null);
        setError(errorText(envelope.code, envelope.message));
        return;
      }
      setTasks(envelope.data);
    } catch (error) {
      setTasks(null);
      setError(
        error instanceof ApiError
          ? errorText(error.code, error.message)
          : "网络异常，请检查连接后重试。",
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadTasks();
  }, [loadTasks]);

  return (
    <main className={styles.page}>
      <PageTitle
        title="请选择本次事项"
        description="选择刷脸签到或录音思想汇报，进入后按页面提示完成。"
      />

      {loading ? <LoadingState text="正在获取任务信息…" /> : null}

      {!loading && error ? (
        <ErrorBanner message={error} onRetry={() => void loadTasks()} />
      ) : null}

      {!loading && !error && tasks ? (
        <div className={styles.taskGrid}>
          {TASK_MODULES.map((module) => {
            const task = tasks[module.kind];
            return (
              <Link key={module.kind} className={styles.taskCard} to={module.to}>
                <h2 className={styles.taskCardTitle}>{module.title}</h2>
                <p className={styles.taskDescription}>{module.description}</p>
                <p className={styles.taskMeta}>每 {task.interval_days} 天一次</p>
                <p className={styles.taskMeta}>
                  上次完成：
                  {task.last_completed_at
                    ? formatDateTime(task.last_completed_at)
                    : "尚未完成"}
                </p>
                {task.overdue ? (
                  <p className={styles.taskOverdue} role="status">
                    已逾期，请尽快完成
                  </p>
                ) : null}
                <span className={styles.taskAction}>{module.action} →</span>
              </Link>
            );
          })}
        </div>
      ) : null}

      {!loading && !error && !tasks ? (
        <EmptyState text="任务信息暂不可用，请稍后重试。" />
      ) : null}

      <p className={styles.footerHint}>
        <Link to="/consent">查看或撤回知情同意</Link>
      </p>
    </main>
  );
}
