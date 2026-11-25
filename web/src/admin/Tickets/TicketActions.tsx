/* 复核任务三种流转动作（ui@1.2 §4.5）：确认 note 选填；修正五色 + note 必填；关闭 note 必填。
 * 每次提交调用 transitionTicket，成功后展示返回状态并触发详情刷新。
 */
import { useState, type FormEvent } from "react";
import { transitionTicket } from "../../api/admin";
import type {
  TicketAction,
  TransitionPayload,
  TransitionResult,
} from "../../api/types";
import { COLOR_META, COLOR_ORDER, type Color } from "../../lib/colors";
import { errorText } from "../../lib/errorMessages";
import { ApiError } from "../../lib/http";
import styles from "./Tickets.module.css";

const ACTION_TEXT: Record<TicketAction, string> = {
  confirm: "确认",
  correct: "修正",
  close: "关闭",
};

const STATUS_TEXT: Record<string, string> = {
  pending: "待复核",
  confirmed: "已确认",
  closed: "已关闭",
};

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

type TicketActionsProps = {
  ticketId: string;
  status: string;
  onDone: () => void;
};

export function TicketActions({ ticketId, status, onDone }: TicketActionsProps) {
  const [action, setAction] = useState<TicketAction>("confirm");
  const [conclusionColor, setConclusionColor] = useState<Color | "">("");
  const [note, setNote] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<TransitionResult | null>(null);

  const trimmedNote = note.trim();
  const closed = status !== "pending";

  let validationHint: string | null = null;
  if (closed) {
    validationHint = "任务已结束，不再接受新的流转。";
  } else if (action === "correct") {
    if (!conclusionColor && !trimmedNote) {
      validationHint = "修正需选择最终色码并填写说明。";
    } else if (!conclusionColor) {
      validationHint = "修正需选择最终色码。";
    } else if (!trimmedNote) {
      validationHint = "修正需填写说明。";
    }
  } else if (action === "close" && !trimmedNote) {
    validationHint = "关闭需填写说明。";
  }

  const submitDisabled = submitting || validationHint !== null;

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (validationHint !== null) {
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const payload: TransitionPayload = { action };
      if (action === "correct" && conclusionColor) {
        payload.conclusion_color = conclusionColor;
      }
      if (trimmedNote) {
        payload.note = trimmedNote;
      }
      const envelope = await transitionTicket(ticketId, payload);
      if (envelope.code !== 0 || envelope.data === null) {
        setResult(null);
        setError(errorText(envelope.code, envelope.message));
        return;
      }
      setResult(envelope.data);
      onDone();
    } catch (err) {
      setResult(null);
      setError(
        err instanceof ApiError
          ? errorText(err.code, err.message)
          : "网络异常，请检查连接后重试。",
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form className={styles.actions} onSubmit={(event) => void handleSubmit(event)}>
      <div className={styles.actionGroup}>
        {(Object.keys(ACTION_TEXT) as TicketAction[]).map((option) => (
          <label
            key={option}
            className={
              action === option
                ? `${styles.actionOption} ${styles.actionOptionActive}`
                : styles.actionOption
            }
          >
            <input
              type="radio"
              name="ticket-action"
              value={option}
              checked={action === option}
              disabled={closed || submitting}
              onChange={() => {
                setAction(option);
                setError(null);
              }}
            />
            {ACTION_TEXT[option]}
          </label>
        ))}
      </div>

      {action === "correct" ? (
        <div className={styles.fieldGroup}>
          <span className={styles.fieldLabel}>最终色码（必选）</span>
          <div className={styles.colorRow}>
            {COLOR_ORDER.map((color) => {
              const meta = COLOR_META[color];
              return (
                <label
                  key={color}
                  className={
                    conclusionColor === color
                      ? `${styles.colorOption} ${styles.colorOptionActive}`
                      : styles.colorOption
                  }
                >
                  <input
                    type="radio"
                    name="conclusion-color"
                    value={color}
                    checked={conclusionColor === color}
                    disabled={closed || submitting}
                    onChange={() => {
                      setConclusionColor(color);
                      setError(null);
                    }}
                  />
                  <span
                    className={styles.swatch}
                    style={{ background: `var(${meta.token})` }}
                    aria-hidden="true"
                  />
                  {meta.label}
                </label>
              );
            })}
          </div>
        </div>
      ) : null}

      <label className={styles.fieldGroup}>
        <span className={styles.fieldLabel}>
          {action === "confirm" ? "说明（选填）" : "说明（必填）"}
        </span>
        <textarea
          className={styles.noteInput}
          value={note}
          disabled={closed || submitting}
          placeholder={
            action === "confirm"
              ? "可补充人工核对情况"
              : action === "correct"
                ? "请写明修正依据与人工核对结论"
                : "请写明关闭原因"
          }
          onChange={(event) => {
            setNote(event.target.value);
            setError(null);
          }}
        />
      </label>

      {validationHint ? <p className={styles.hint}>{validationHint}</p> : null}
      {error ? (
        <p className={styles.errorHint} role="alert">
          {error}
        </p>
      ) : null}

      <div className={styles.submitRow}>
        <button className={styles.submitButton} type="submit" disabled={submitDisabled}>
          {submitting ? "提交中…" : `提交${ACTION_TEXT[action]}`}
        </button>
        <span className={styles.hint}>人工结论会写入留痕，记录操作人与时间。</span>
      </div>

      {result ? (
        <div className={styles.resultBox} role="status">
          <span>
            动作：{ACTION_TEXT[result.action]}　状态：
            {STATUS_TEXT[result.status] ?? "未知状态"}
          </span>
          <span>
            结论色码：
            {result.conclusion_color ? COLOR_META[result.conclusion_color].label : "未指定"}
          </span>
          <span>结论说明：{result.conclusion_note ?? "—"}</span>
          <span>关闭时间：{formatTime(result.closed_at) || "—"}</span>
        </div>
      ) : null}
    </form>
  );
}
