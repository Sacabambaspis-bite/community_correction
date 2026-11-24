/* 知情同意页：展示当前同意状态、采集说明、双项独立勾选与撤回入口（ui@1.2 §3.1）。 */
import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { getConsent, putConsent, revokeConsent } from "../../api/user";
import type { ConsentData, ConsentItem } from "../../api/types";
import {
  ErrorBanner,
  LoadingState,
  PageTitle,
} from "../../components/common/StateViews";
import { errorText } from "../../lib/errorMessages";
import { ApiError } from "../../lib/http";
import { ConsentForm, type ConsentFormValue } from "./ConsentForm";
import styles from "./Consent.module.css";

function formatDateTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString("zh-CN", { hour12: false });
}

function ConsentStatusItem({
  label,
  item,
}: {
  label: string;
  item: ConsentItem;
}) {
  return (
    <div className={styles.statusItem}>
      <span className={styles.statusLabel}>{label}</span>
      <span
        className={
          item.granted ? styles.statusGranted : styles.statusNotGranted
        }
      >
        {item.granted ? "已同意" : "未同意"}
      </span>
      <span className={styles.statusMeta}>
        {item.at ? formatDateTime(item.at) : "暂无记录"}
      </span>
    </div>
  );
}

export default function ConsentPage() {
  const navigate = useNavigate();
  const [consent, setConsent] = useState<ConsentData | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState(false);
  const [revoking, setRevoking] = useState(false);
  const [confirmingRevoke, setConfirmingRevoke] = useState(false);
  const [revokeError, setRevokeError] = useState<string | null>(null);

  const loadConsent = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const envelope = await getConsent();
      if (envelope.code !== 0 || envelope.data === null) {
        setConsent(null);
        setLoadError(errorText(envelope.code, envelope.message));
        return;
      }
      setConsent(envelope.data);
    } catch (error) {
      setConsent(null);
      setLoadError(
        error instanceof ApiError
          ? errorText(error.code, error.message)
          : "网络异常，请检查连接后重试。",
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadConsent();
  }, [loadConsent]);

  const handleSubmit = useCallback(async (value: ConsentFormValue) => {
    setSubmitting(true);
    setFormError(null);
    try {
      const envelope = await putConsent(value);
      if (envelope.code !== 0 || envelope.data === null) {
        setFormError(errorText(envelope.code, envelope.message));
        return;
      }
      setConsent(envelope.data);
      setSubmitted(true);
    } catch (error) {
      setFormError(
        error instanceof ApiError
          ? errorText(error.code, error.message)
          : "网络异常，请检查连接后重试。",
      );
    } finally {
      setSubmitting(false);
    }
  }, []);

  const handleRevoke = useCallback(async () => {
    setRevoking(true);
    setRevokeError(null);
    try {
      const envelope = await revokeConsent();
      if (envelope.code !== 0 || envelope.data === null) {
        setRevokeError(errorText(envelope.code, envelope.message));
        return;
      }
      setConsent(envelope.data);
      setSubmitted(false);
      setConfirmingRevoke(false);
    } catch (error) {
      setRevokeError(
        error instanceof ApiError
          ? errorText(error.code, error.message)
          : "网络异常，请检查连接后重试。",
      );
    } finally {
      setRevoking(false);
    }
  }, []);

  return (
    <main className={styles.page}>
      <PageTitle
        title="知情同意"
        description="开始使用前，请了解本次采集的范围、用途以及撤回方式。"
      />

      {loading ? <LoadingState text="正在获取同意状态…" /> : null}

      {!loading && loadError ? (
        <ErrorBanner message={loadError} onRetry={() => void loadConsent()} />
      ) : null}

      {!loading && !loadError && consent ? (
        <>
          <section className={styles.card}>
            <h2 className={styles.cardTitle}>当前同意状态</h2>
            <div className={styles.statusGrid}>
              <ConsentStatusItem label="整体同意" item={consent.general} />
              <ConsentStatusItem label="面部图像" item={consent.face} />
              <ConsentStatusItem label="语音" item={consent.audio} />
            </div>
            {consent.revoked_at ? (
              <p className={styles.revokeTime}>
                撤回时间：{formatDateTime(consent.revoked_at)}
              </p>
            ) : null}
          </section>

          <section className={styles.card}>
            <h2 className={styles.cardTitle}>采集说明</h2>
            <dl className={styles.infoList}>
              <div className={styles.infoRow}>
                <dt>采集内容</dt>
                <dd>面部图像与语音。</dd>
              </div>
              <div className={styles.infoRow}>
                <dt>用途</dt>
                <dd>
                  辅助工作人员了解你近期的生活情况，不用于自动生成判断结论。
                </dd>
              </div>
              <div className={styles.infoRow}>
                <dt>撤回方式</dt>
                <dd>
                  在本页点击「撤回同意」，或联系你所在司法所的工作人员协助撤回。
                </dd>
              </div>
              <div className={styles.infoRow}>
                <dt>撤回后的影响</dt>
                <dd>
                  撤回后无法继续发起新的采集。如需处理已保存的记录，请联系工作人员。
                </dd>
              </div>
            </dl>
          </section>

          <section className={styles.card}>
            <h2 className={styles.cardTitle}>提交或更新同意</h2>
            {submitted ? (
              <div className={styles.successBox} role="status">
                <p>同意已提交，可以开始采集。</p>
                <div className={styles.buttonRow}>
                  <button
                    type="button"
                    className={styles.primaryButton}
                    onClick={() => navigate("/capture")}
                  >
                    进入采集引导
                  </button>
                </div>
              </div>
            ) : (
              <ConsentForm
                submitting={submitting}
                error={formError}
                onSubmit={(value) => void handleSubmit(value)}
              />
            )}
          </section>

          <section className={styles.card}>
            <h2 className={styles.cardTitle}>撤回同意</h2>
            <p className={styles.hint}>
              撤回后无法继续发起新的采集。之后如需再次采集，需要重新提交同意。
            </p>
            {confirmingRevoke ? (
              <div className={styles.revokeBox}>
                <p>确认撤回面部图像与语音的同意吗？</p>
                <div className={styles.buttonRow}>
                  <button
                    type="button"
                    className={styles.dangerButton}
                    disabled={revoking}
                    onClick={() => void handleRevoke()}
                  >
                    {revoking ? "正在撤回…" : "确认撤回"}
                  </button>
                  <button
                    type="button"
                    className={styles.secondaryButton}
                    disabled={revoking}
                    onClick={() => setConfirmingRevoke(false)}
                  >
                    取消
                  </button>
                </div>
              </div>
            ) : (
              <div className={styles.buttonRow}>
                <button
                  type="button"
                  className={styles.secondaryButton}
                  disabled={
                    revoking ||
                    !consent.general.granted ||
                    consent.revoked_at !== null
                  }
                  onClick={() => setConfirmingRevoke(true)}
                >
                  撤回同意
                </button>
              </div>
            )}
            {!consent.general.granted ? (
              <p className={styles.hint}>尚未提交同意，暂无可撤回内容。</p>
            ) : null}
            {consent.revoked_at !== null ? (
              <p className={styles.hint}>同意已撤回，无需重复操作。</p>
            ) : null}
            {revokeError ? (
              <p className={styles.errorText}>{revokeError}</p>
            ) : null}
          </section>
        </>
      ) : null}
    </main>
  );
}
