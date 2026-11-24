/* 知情同意表单：面部图像与语音两项独立勾选，不提供「同意全部」，
 * 保存期限默认 180 天，至少勾选一项才允许提交（ui@1.2 §3.1、api@1.5 §7.1.2）。
 */
import { useState, type FormEvent } from "react";
import styles from "./Consent.module.css";

export type ConsentFormValue = {
  face: boolean;
  audio: boolean;
  retention_days: number;
};

type ConsentFormProps = {
  /** 已保存的保存期限，未同意时为 null，表单回落到 180 天。 */
  retentionDays: number | null;
  submitting: boolean;
  error: string | null;
  onSubmit: (value: ConsentFormValue) => void;
};

export function ConsentForm({
  retentionDays,
  submitting,
  error,
  onSubmit,
}: ConsentFormProps) {
  // 无论历史状态如何，两个勾选项都从「未勾选」开始，避免默认同意。
  const [face, setFace] = useState(false);
  const [audio, setAudio] = useState(false);
  const [retention, setRetention] = useState(
    String(retentionDays !== null && retentionDays >= 1 ? retentionDays : 180),
  );

  const retentionValue = Number(retention);
  const retentionValid =
    retention.trim() !== "" &&
    Number.isInteger(retentionValue) &&
    retentionValue >= 1;
  const noSelection = !face && !audio;
  const canSubmit = !noSelection && retentionValid && !submitting;

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!canSubmit) {
      return;
    }
    onSubmit({ face, audio, retention_days: retentionValue });
  };

  return (
    <form className={styles.form} onSubmit={handleSubmit}>
      <fieldset className={styles.fieldset}>
        <legend className={styles.legend}>请分别选择同意项</legend>

        <label className={styles.checkboxRow} htmlFor="consent-face">
          <input
            id="consent-face"
            type="checkbox"
            checked={face}
            onChange={(event) => setFace(event.target.checked)}
          />
          <span className={styles.checkboxText}>
            <strong>我同意采集面部图像</strong>
            <span>仅用于确认采集时的在场情况，由工作人员按保存期限管理。</span>
          </span>
        </label>

        <label className={styles.checkboxRow} htmlFor="consent-audio">
          <input
            id="consent-audio"
            type="checkbox"
            checked={audio}
            onChange={(event) => setAudio(event.target.checked)}
          />
          <span className={styles.checkboxText}>
            <strong>我同意采集语音</strong>
            <span>用于了解我近期的表述内容，转写内容仅供工作人员复核。</span>
          </span>
        </label>
      </fieldset>

      <div className={styles.fieldRow}>
        <label className={styles.fieldLabel} htmlFor="consent-retention">
          保存期限（天）
        </label>
        <input
          id="consent-retention"
          className={styles.input}
          type="number"
          inputMode="numeric"
          min={1}
          step={1}
          value={retention}
          onChange={(event) => setRetention(event.target.value)}
        />
        <span className={styles.hint}>最小 1 天，默认 180 天。</span>
      </div>
      {!retentionValid ? (
        <p className={styles.errorText}>保存期限需为不小于 1 的整数天。</p>
      ) : null}

      <p className={styles.hint}>
        两项可以分别选择；只勾选一项时，缺失的部分无法采集，两项都同意后才能开始完整采集。
        提交同意不会自动开始采集，你可以在本页随时撤回。
      </p>

      {noSelection ? (
        <p className={styles.hint}>请至少勾选一项后再提交。</p>
      ) : null}
      {error ? <p className={styles.errorText}>{error}</p> : null}

      <div className={styles.buttonRow}>
        <button type="submit" className={styles.primaryButton} disabled={!canSubmit}>
          {submitting ? "正在提交…" : "提交同意"}
        </button>
      </div>
    </form>
  );
}
