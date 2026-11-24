/* 知情同意表单：面部图像与语音两项独立勾选，不提供「同意全部」，
 * 两项均同意后才允许提交（ui@1.2 §3.1、api@1.5 §7.1.2）。
 */
import { useState, type FormEvent } from "react";
import styles from "./Consent.module.css";

export type ConsentFormValue = {
  face: boolean;
  audio: boolean;
};

type ConsentFormProps = {
  submitting: boolean;
  error: string | null;
  onSubmit: (value: ConsentFormValue) => void;
};

export function ConsentForm({
  submitting,
  error,
  onSubmit,
}: ConsentFormProps) {
  // 无论历史状态如何，两个勾选项都从「未勾选」开始，避免默认同意。
  const [face, setFace] = useState(false);
  const [audio, setAudio] = useState(false);

  const consentIncomplete = !face || !audio;
  const canSubmit = !consentIncomplete && !submitting;

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!canSubmit) {
      return;
    }
    onSubmit({ face, audio });
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
            <span>仅用于确认采集时的在场情况。</span>
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

      <p className={styles.hint}>
        两项需分别勾选；提交同意不会自动开始采集，你可以在本页随时撤回。
      </p>

      {consentIncomplete ? (
        <p className={styles.hint}>面部与语音需同时同意后才能开始采集。</p>
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
