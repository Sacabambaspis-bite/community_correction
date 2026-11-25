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

/**
 * 更多服务入口（ui@1.2 补记 5）。
 * 当前阶段仅跳转「功能待开发」占位页，不对接后端、不实现业务逻辑。
 *
 * TODO(可扩展)：AI援助模块后续可扩展三类服务能力——
 *   1) 心理援助：情绪疏导、心理测评与转介；
 *   2) 法律援助：法律咨询、文书指引与援助申请；
 *   3) 就业帮扶：岗位推荐、技能培训与就业指导。
 * 届时在此拆分为独立入口与独立页面，复用本页卡片样式，不改变现有签到/汇报流程。
 */
const EXTRA_MODULES: Array<{
  key: string;
  title: string;
  description: string;
  to: string;
  action: string;
}> = [
  {
    key: "ai-aid",
    title: "AI援助",
    description: "获取心理援助、法律援助与就业帮扶等支持。",
    to: "/pending?feature=ai-aid",
    action: "了解详情",
  },
  {
    key: "education",
    title: "教育学习",
    description: "参与法治教育、思想教育与线上学习任务。",
    to: "/pending?feature=education",
    action: "了解详情",
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

      <section className={styles.extraSection}>
        <h2 className={styles.sectionTitle}>更多服务</h2>
        <div className={styles.taskGrid}>
          {EXTRA_MODULES.map((module) => (
            <Link key={module.key} className={styles.taskCard} to={module.to}>
              <h2 className={styles.taskCardTitle}>{module.title}</h2>
              <p className={styles.taskDescription}>{module.description}</p>
              <span className={styles.taskAction}>{module.action} →</span>
            </Link>
          ))}
        </div>
      </section>

      <p className={styles.footerHint}>
        <Link to="/login">切换账号</Link>
      </p>
    </main>
  );
}
