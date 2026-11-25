/* 思想汇报同步（ui@1.2 §4.2 补记 8 / api@1.5 §7.15–7.17）：
 * 同步按钮 + 同步记录列表；「完整报告」默认折叠，仅在用户点击时请求详情（后端读取留痕）。
 * 真实同步受 SENSEVOICE_SYNC_ENABLED 控制，能力未启用只显示中性提示，不伪造转写或情绪结果。
 */
import { useCallback, useEffect, useRef, useState } from "react";
import {
  getSensevoiceSync,
  getSensevoiceSyncs,
  syncSensevoice,
} from "../../api/admin";
import type {
  SensevoiceSyncDetail,
  SensevoiceSyncItem,
} from "../../api/types";
import {
  EmptyState,
  ErrorBanner,
  LoadingState,
} from "../../components/common/StateViews";
import { errorText } from "../../lib/errorMessages";
import { ApiError } from "../../lib/http";
import styles from "./SensevoiceSyncPanel.module.css";

const SYNC_DISABLED_MESSAGE = "sensevoice_sync_disabled";

function formatTime(value: string | null): string {
  if (!value) {
    return "";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString("zh-CN", { hour12: false });
}

/** 0.87 → 87%；缺省显示「—」。 */
function percent(value: number | null): string {
  if (value === null || Number.isNaN(value)) {
    return "—";
  }
  return `${Math.round(value * 100)}%`;
}

function seconds(value: number): string {
  return Number.isFinite(value) ? value.toFixed(1) : "—";
}

function requestError(err: unknown): string {
  return err instanceof ApiError
    ? errorText(err.code, err.message)
    : "网络异常，请检查连接后重试。";
}

function DetailBody({ detail }: { detail: SensevoiceSyncDetail }) {
  const emotion = detail.emotion;
  const scoreEntries = emotion ? Object.entries(emotion.scores) : [];

  return (
    <div className={styles.detail}>
      <div className={styles.detailBlock}>
        <h4 className={styles.detailTitle}>转写全文</h4>
        <p className={styles.transcript}>{detail.transcript_text || "—"}</p>
      </div>

      <div className={styles.detailBlock}>
        <h4 className={styles.detailTitle}>情绪分析</h4>
        {emotion ? (
          <>
            <p className={styles.detailLine}>
              情绪类型：{emotion.primary}　置信度：{percent(emotion.confidence)}
            </p>
            {scoreEntries.length > 0 ? (
              <ul className={styles.scores}>
                {scoreEntries.map(([label, value]) => (
                  <li key={label} className={styles.scoreItem}>
                    <span>{label}</span>
                    <span className={styles.mono}>{percent(value)}</span>
                  </li>
                ))}
              </ul>
            ) : null}
          </>
        ) : (
          <p className={styles.empty}>暂无情绪分析结果</p>
        )}
      </div>

      <div className={styles.detailBlock}>
        <h4 className={styles.detailTitle}>关键触发片段</h4>
        {emotion && emotion.triggers.length > 0 ? (
          <ul className={styles.triggers}>
            {emotion.triggers.map((trigger, index) => (
              <li key={`${trigger.start_sec}-${trigger.end_sec}-${index}`} className={styles.triggerItem}>
                <p className={styles.triggerText}>{trigger.text}</p>
                <span className={styles.triggerMeta}>
                  标签：{trigger.label} · {seconds(trigger.start_sec)} –{" "}
                  {seconds(trigger.end_sec)} 秒
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <p className={styles.empty}>未标注关键片段</p>
        )}
      </div>
    </div>
  );
}

export function SensevoiceSyncPanel({ subjectId }: { subjectId: string }) {
  const [items, setItems] = useState<SensevoiceSyncItem[]>([]);
  const [listLoading, setListLoading] = useState(true);
  const [listError, setListError] = useState<string | null>(null);
  const [reloadTick, setReloadTick] = useState(0);

  const [syncing, setSyncing] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [syncError, setSyncError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [details, setDetails] = useState<Record<string, SensevoiceSyncDetail>>({});
  const [detailLoadingId, setDetailLoadingId] = useState<string | null>(null);
  const [detailErrors, setDetailErrors] = useState<Record<string, string>>({});

  const subjectRef = useRef(subjectId);
  const syncToken = useRef(0);
  const detailToken = useRef(0);

  /* 切换对象时清空全部本地数据，避免旧对象记录串到新对象。 */
  useEffect(() => {
    subjectRef.current = subjectId;
    syncToken.current += 1;
    detailToken.current += 1;
    setItems([]);
    setListLoading(true);
    setListError(null);
    setSyncing(false);
    setNotice(null);
    setSyncError(null);
    setSuccess(null);
    setExpandedId(null);
    setDetails({});
    setDetailErrors({});
    setDetailLoadingId(null);
  }, [subjectId]);

  useEffect(() => {
    let cancelled = false;
    setListLoading(true);
    setListError(null);

    void (async () => {
      try {
        const envelope = await getSensevoiceSyncs(subjectId);
        if (cancelled) {
          return;
        }
        if (envelope.code !== 0 || envelope.data === null) {
          setItems([]);
          setListError(errorText(envelope.code, envelope.message));
          return;
        }
        setItems(envelope.data.items);
      } catch (err) {
        if (cancelled) {
          return;
        }
        setItems([]);
        setListError(requestError(err));
      } finally {
        if (!cancelled) {
          setListLoading(false);
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [subjectId, reloadTick]);

  const handleSync = async () => {
    if (syncing) {
      return;
    }
    const token = syncToken.current + 1;
    syncToken.current = token;
    const requested = subjectId;

    setSyncing(true);
    setNotice(null);
    setSyncError(null);
    setSuccess(null);

    try {
      const envelope = await syncSensevoice(requested);
      if (syncToken.current !== token || subjectRef.current !== requested) {
        return;
      }
      if (envelope.code !== 0 || envelope.data === null) {
        const text = errorText(envelope.code, envelope.message);
        if (envelope.message === SYNC_DISABLED_MESSAGE) {
          setNotice(text);
        } else {
          setSyncError(text);
        }
        return;
      }
      setSuccess("同步完成");
      setExpandedId(null);
      setReloadTick((tick) => tick + 1);
    } catch (err) {
      if (syncToken.current !== token || subjectRef.current !== requested) {
        return;
      }
      if (err instanceof ApiError && err.message === SYNC_DISABLED_MESSAGE) {
        setNotice(errorText(err.code, err.message));
      } else {
        setSyncError(requestError(err));
      }
    } finally {
      if (syncToken.current === token) {
        setSyncing(false);
      }
    }
  };

  const loadDetail = async (item: SensevoiceSyncItem) => {
    const token = detailToken.current + 1;
    detailToken.current = token;
    const requested = subjectId;

    setDetailLoadingId(item.sync_id);
    setDetailErrors((current) => {
      if (!(item.sync_id in current)) {
        return current;
      }
      const next = { ...current };
      delete next[item.sync_id];
      return next;
    });

    try {
      const envelope = await getSensevoiceSync(item.sync_id);
      if (detailToken.current !== token || subjectRef.current !== requested) {
        return;
      }
      if (envelope.code !== 0 || envelope.data === null) {
        setDetailErrors((current) => ({
          ...current,
          [item.sync_id]: errorText(envelope.code, envelope.message),
        }));
        return;
      }
      const detail = envelope.data;
      setDetails((current) => ({ ...current, [item.sync_id]: detail }));
    } catch (err) {
      if (detailToken.current !== token || subjectRef.current !== requested) {
        return;
      }
      setDetailErrors((current) => ({
        ...current,
        [item.sync_id]: requestError(err),
      }));
    } finally {
      if (detailToken.current === token) {
        setDetailLoadingId(null);
      }
    }
  };

  const toggleDetail = (item: SensevoiceSyncItem) => {
    if (expandedId === item.sync_id) {
      setExpandedId(null);
      return;
    }
    setExpandedId(item.sync_id);
    if (!details[item.sync_id] && detailLoadingId !== item.sync_id) {
      void loadDetail(item);
    }
  };

  const retryList = useCallback(() => {
    setReloadTick((tick) => tick + 1);
  }, []);

  return (
    <section className={styles.section}>
      <div className={styles.headerRow}>
        <h2 className={styles.sectionTitle}>思想汇报同步</h2>
        <button
          className={styles.syncButton}
          type="button"
          disabled={syncing}
          onClick={() => void handleSync()}
        >
          {syncing ? "同步中…" : "同步思想汇报"}
        </button>
      </div>
      <p className={styles.description}>
        调用 SenseVoice 对最近一次思想汇报录音做转写与情绪分析。
      </p>

      {notice ? (
        <p className={styles.notice} role="status">
          {notice}
        </p>
      ) : null}
      {syncError ? (
        <p className={styles.errorText} role="alert">
          {syncError}
        </p>
      ) : null}
      {success ? (
        <p className={styles.successText} role="status">
          {success}
        </p>
      ) : null}

      <h3 className={styles.subTitle}>同步记录</h3>

      {listLoading ? <LoadingState text="正在加载同步记录…" /> : null}
      {!listLoading && listError ? (
        <ErrorBanner message={listError} onRetry={retryList} />
      ) : null}
      {!listLoading && !listError && items.length === 0 ? (
        <EmptyState text="暂无同步记录" />
      ) : null}

      {!listLoading && !listError && items.length > 0 ? (
        <ul className={styles.list}>
          {items.map((item) => {
            const expanded = expandedId === item.sync_id;
            const detail = details[item.sync_id];
            const detailError = detailErrors[item.sync_id];

            return (
              <li key={item.sync_id} className={styles.item}>
                <div className={styles.itemHead}>
                  <span className={styles.itemTime}>
                    {formatTime(item.created_at) || "时间未记录"}
                  </span>
                  <button
                    className={styles.linkButton}
                    type="button"
                    onClick={() => toggleDetail(item)}
                  >
                    {expanded ? "收起" : "查看完整报告"}
                  </button>
                </div>

                <dl className={styles.meta}>
                  <div className={styles.metaItem}>
                    <dt className={styles.metaLabel}>情绪类型</dt>
                    <dd className={styles.metaValue}>{item.emotion_primary ?? "—"}</dd>
                  </div>
                  <div className={styles.metaItem}>
                    <dt className={styles.metaLabel}>置信度</dt>
                    <dd className={styles.metaValue}>
                      {percent(item.emotion_confidence)}
                    </dd>
                  </div>
                  <div className={styles.metaItem}>
                    <dt className={styles.metaLabel}>数据版本</dt>
                    <dd className={`${styles.metaValue} ${styles.mono}`}>
                      {item.data_version || "—"}
                    </dd>
                  </div>
                  <div className={styles.metaItem}>
                    <dt className={styles.metaLabel}>操作人</dt>
                    <dd className={styles.metaValue}>{item.operator || "—"}</dd>
                  </div>
                </dl>
                <p className={styles.itemHint}>会话 {item.session_id}</p>

                {expanded ? (
                  <div className={styles.detailWrap}>
                    {detailLoadingId === item.sync_id && !detail ? (
                      <p className={styles.detailLoading} role="status">
                        正在读取…
                      </p>
                    ) : null}
                    {detailError ? (
                      <ErrorBanner
                        message={detailError}
                        onRetry={() => void loadDetail(item)}
                      />
                    ) : null}
                    {detail ? <DetailBody detail={detail} /> : null}
                  </div>
                ) : null}
              </li>
            );
          })}
        </ul>
      ) : null}
    </section>
  );
}
