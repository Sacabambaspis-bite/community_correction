/* 对象列表页（ui@1.2 §4.1）：关键词 + 状态筛选，数据来自 GET /api/admin/subjects。
 * 色码一律交给 ColorBadge 渲染，保证与规则编号、证据入口同屏。
 */
import { useCallback, useEffect, useState } from "react";
import { getSubjects } from "../../api/admin";
import type { SubjectListItem } from "../../api/types";
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
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadSubjects = useCallback(async () => {
    setLoading(true);
    setError(null);
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
      setItems(envelope.data.items);
      setTotal(envelope.data.total);
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
        description="按编号或姓名检索，查看当前色码与依据入口、待复核数量与最近采集时间。"
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

      {loading ? <LoadingState text="正在加载对象列表…" /> : null}

      {!loading && error ? (
        <ErrorBanner message={error} onRetry={() => void loadSubjects()} />
      ) : null}

      {!loading && !error && items.length === 0 ? (
        <EmptyState text="没有符合筛选条件的对象。" />
      ) : null}

      {!loading && !error && items.length > 0 ? <SubjectTable items={items} /> : null}
    </section>
  );
}
