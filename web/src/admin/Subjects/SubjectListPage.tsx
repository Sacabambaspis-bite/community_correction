/* 对象列表页（ui@1.2 §4.1）：关键词 + 状态筛选，数据来自 GET /api/admin/subjects。
 * 色码一律交给 ColorBadge 渲染，保证与规则编号、证据入口同屏。
 */
import { useCallback, useEffect, useState } from "react";
import { getSessions, getSubjects } from "../../api/admin";
import type { AdminSessionItem, SubjectListItem } from "../../api/types";
import {
  EmptyState,
  ErrorBanner,
  LoadingState,
  PageTitle,
} from "../../components/common/StateViews";
import { errorText } from "../../lib/errorMessages";
import { ApiError } from "../../lib/http";
import { SubjectTable } from "./SubjectTable";
import styles from "./Subjects.module.css";

type AppliedQuery = {
  keyword: string;
  status: string;
};

export default function SubjectListPage() {
  const [keyword, setKeyword] = useState("");
  const [status, setStatus] = useState("");
  const [applied, setApplied] = useState<AppliedQuery>({ keyword: "", status: "" });
  const [items, setItems] = useState<SubjectListItem[]>([]);
  const [sessionItems, setSessionItems] = useState<AdminSessionItem[]>([]);
  const [recentError, setRecentError] = useState<string | null>(null);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadSubjects = useCallback(async () => {
    setLoading(true);
    setError(null);
    setRecentError(null);
    setSessionItems([]);
    try {
      const envelope = await getSubjects({
        keyword: applied.keyword || undefined,
        status: applied.status || undefined,
      });
      if (envelope.code !== 0 || envelope.data === null) {
        setItems([]);
        setTotal(0);
        setError(errorText(envelope.code, envelope.message));
        return;
      }

      const nextItems = envelope.data.items;
      setItems(nextItems);
      setTotal(envelope.data.total);

      try {
        const responses = await Promise.all(
          nextItems.map((item) =>
            getSessions({
              subject_id: item.subject_id,
              page: 1,
              page_size: 100,
            }),
          ),
        );
        const nextSessions: AdminSessionItem[] = [];
        responses.forEach((response) => {
          if (response.code !== 0 || response.data === null) {
            throw new ApiError(response);
          }
          nextSessions.push(...response.data.items);
        });
        setSessionItems(nextSessions);
      } catch (err) {
        setSessionItems([]);
        setRecentError(
          err instanceof ApiError
            ? errorText(err.code, err.message)
            : "最近签到与汇报时间加载失败，请重试。",
        );
      }
    } catch (err) {
      setItems([]);
      setTotal(0);
      setError(
        err instanceof ApiError
          ? errorText(err.code, err.message)
          : "网络异常，请检查连接后重试。",
      );
    } finally {
      setLoading(false);
    }
  }, [applied]);

  useEffect(() => {
    void loadSubjects();
  }, [loadSubjects]);

  return (
    <section>
      <PageTitle
        title="对象列表"
        description="按编号或姓名检索，查看当前色码与依据、待复核数量及最近签到/汇报时间。"
      />

      <form
        className={styles.filters}
        onSubmit={(event) => {
          event.preventDefault();
          setApplied({ keyword: keyword.trim(), status });
        }}
      >
        <label className={styles.field}>
          <span className={styles.fieldLabel}>关键词</span>
          <input
            className={styles.input}
            type="search"
            value={keyword}
            placeholder="编号或姓名"
            onChange={(event) => setKeyword(event.target.value)}
          />
        </label>
        <label className={styles.field}>
          <span className={styles.fieldLabel}>状态</span>
          <select
            className={styles.select}
            value={status}
            onChange={(event) => setStatus(event.target.value)}
          >
            <option value="">全部</option>
            <option value="active">在矫</option>
            <option value="suspended">暂停</option>
            <option value="closed">已结案</option>
          </select>
        </label>
        <button className={styles.button} type="submit">
          查询
        </button>
      </form>

      <p className={styles.meta}>共 {total} 条</p>

      {recentError ? (
        <ErrorBanner
          message={`最近签到/汇报时间：${recentError}`}
          onRetry={() => void loadSubjects()}
        />
      ) : null}

      {loading ? <LoadingState text="正在加载对象列表…" /> : null}

      {!loading && error ? (
        <ErrorBanner message={error} onRetry={() => void loadSubjects()} />
      ) : null}

      {!loading && !error && items.length === 0 ? (
        <EmptyState text="没有符合筛选条件的对象。" />
      ) : null}

      {!loading && !error && items.length > 0 ? (
        <SubjectTable
          items={items}
          sessions={sessionItems}
          recentUnavailable={recentError !== null}
        />
      ) : null}
    </section>
  );
}
