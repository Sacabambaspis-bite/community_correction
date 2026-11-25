/* 结果反馈页：按路由参数获取 feedback，展示中性结论与建议（ui@1.2 §3.3）。 */
import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getFeedback } from "../../api/user";
import type { FeedbackData } from "../../api/types";
import {
  EmptyState,
  ErrorBanner,
  LoadingState,
  PageTitle,
} from "../../components/common/StateViews";
import { errorText } from "../../lib/errorMessages";
import { ApiError } from "../../lib/http";
import { FeedbackPanel } from "./FeedbackPanel";
import styles from "./Feedback.module.css";

export default function FeedbackPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const [feedback, setFeedback] = useState<FeedbackData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadFeedback = useCallback(async () => {
    if (!sessionId) {
      setFeedback(null);
      setError("缺少会话编号，无法查看本次结果。");
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const envelope = await getFeedback(sessionId);
      if (envelope.code !== 0 || envelope.data === null) {
        setFeedback(null);
        setError(errorText(envelope.code, envelope.message));
        return;
      }
      setFeedback(envelope.data);
    } catch (error) {
      setFeedback(null);
      setError(
        error instanceof ApiError
          ? errorText(error.code, error.message)
          : "网络异常，请检查连接后重试。",
      );
    } finally {
      setLoading(false);
    }
  }, [sessionId]);

  useEffect(() => {
    void loadFeedback();
  }, [loadFeedback]);

  return (
    <main className={styles.page}>
      <PageTitle
        title="本次结果"
        description="以下是本次对话采集后的中性反馈，仅供你了解近况参考，如有疑问可与工作人员沟通。"
      />

      {loading ? <LoadingState text="正在获取本次结果…" /> : null}

      {!loading && error ? (
        <>
          <ErrorBanner message={error} onRetry={() => void loadFeedback()} />
          <p className={styles.footerHint}>
            <Link to="/capture">返回首页</Link>
            {" · "}
            <Link to="/login">返回登录页</Link>
          </p>
        </>
      ) : null}

      {!loading && !error && feedback ? (
        <FeedbackPanel feedback={feedback} />
      ) : null}

      {!loading && !error && !feedback ? (
        <EmptyState text="暂无可展示的结果。" />
      ) : null}
    </main>
  );
}
