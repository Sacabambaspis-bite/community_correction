/* 用户登录页：账号密码登录 + 统一知情同意（原独立同意页已合并至本页）。
 * 登录校验为开发阶段演示账号；同意提交成功后直接进入事项选择页。
 */
import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { putConsent } from "../../api/user";
import { errorText } from "../../lib/errorMessages";
import {
  clearUserSession,
  getUserSession,
  saveUserSession,
  verifyDemoAccount,
} from "../../lib/auth";
import { DEMO_PASSWORD, DEMO_USERNAME, USE_MOCK } from "../../lib/env";
import { ApiError } from "../../lib/http";
import styles from "./Login.module.css";

function consentErrorText(code: number, message: string): string {
  if (code === 1004) {
    return "未找到演示对象。请先在项目根目录执行 python scripts/seed_demo.py 初始化演示数据。";
  }
  return errorText(code, message);
}

export default function LoginPage() {
  const navigate = useNavigate();
  const [session, setSession] = useState(() => getUserSession());
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [agreed, setAgreed] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const handleLogout = () => {
    clearUserSession();
    setSession(null);
    setError(null);
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (submitting) {
      return;
    }
    const trimmedUsername = username.trim();
    if (!trimmedUsername || !password) {
      setError("请输入用户名和密码。");
      return;
    }
    if (!verifyDemoAccount(trimmedUsername, password)) {
      setError("用户名或密码不正确，请使用测试账号登录。");
      return;
    }
    if (!agreed) {
      setError("请先阅读并勾选知情同意，才能进入系统。");
      return;
    }

    setSubmitting(true);
    setError(null);
    try {
      // 一次勾选同时授权面部图像与语音；提交成功才允许进入系统。
      const envelope = await putConsent({ face: true, audio: true });
      if (envelope.code !== 0 || envelope.data === null) {
        setError(consentErrorText(envelope.code, envelope.message));
        return;
      }
      saveUserSession(trimmedUsername);
      navigate("/capture", { replace: true });
    } catch (err) {
      if (err instanceof ApiError) {
        setError(consentErrorText(err.code, err.message));
      } else {
        setError("无法连接后端服务，请确认后端已启动后重试。");
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <main className={styles.page}>
      <section className={styles.card}>
        <header className={styles.header}>
          <p className={styles.eyebrow}>社区矫正智能辅助系统</p>
          <h1 className={styles.title}>用户登录</h1>
          <p className={styles.subtitle}>
            请使用司法所发放的账号登录，并阅读下方的采集告知。
          </p>
        </header>

        {session ? (
          <div className={styles.sessionBar}>
            <span>
              当前已登录：<strong>{session.username}</strong>，如需更换账号请退出后重新登录。
            </span>
            <button
              type="button"
              className={styles.linkButton}
              onClick={handleLogout}
            >
              退出登录
            </button>
          </div>
        ) : null}

        <form className={styles.form} onSubmit={(event) => void handleSubmit(event)}>
          <label className={styles.field} htmlFor="login-username">
            <span className={styles.label}>用户名</span>
            <input
              id="login-username"
              className={styles.input}
              type="text"
              name="username"
              autoComplete="username"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              placeholder="请输入用户名"
            />
          </label>

          <label className={styles.field} htmlFor="login-password">
            <span className={styles.label}>密码</span>
            <input
              id="login-password"
              className={styles.input}
              type="password"
              name="password"
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              placeholder="请输入密码"
            />
          </label>

          <fieldset className={styles.consentBox}>
            <legend className={styles.consentLegend}>知情同意</legend>
            <label className={styles.checkboxRow} htmlFor="login-consent">
              <input
                id="login-consent"
                type="checkbox"
                checked={agreed}
                onChange={(event) => setAgreed(event.target.checked)}
              />
              <span className={styles.checkboxText}>
                <strong>我已阅读并同意采集面部图像与语音</strong>
                <span>
                  采集结果仅用于签到与思想汇报的辅助评估，不用于自动生成处置结论；我可随时联系工作人员撤回同意。
                </span>
              </span>
            </label>

            <dl className={styles.noticeList}>
              <div className={styles.noticeRow}>
                <dt>采集内容</dt>
                <dd>面部图像与语音（一次同意同时授权两项）。</dd>
              </div>
              <div className={styles.noticeRow}>
                <dt>用途</dt>
                <dd>辅助工作人员了解你近期的生活情况，不用于自动生成判断结论。</dd>
              </div>
              <div className={styles.noticeRow}>
                <dt>撤回方式</dt>
                <dd>联系你所在司法所的工作人员协助撤回。</dd>
              </div>
              <div className={styles.noticeRow}>
                <dt>撤回影响</dt>
                <dd>撤回后无法继续发起新的采集，已保存记录的处理请联系工作人员。</dd>
              </div>
            </dl>
          </fieldset>

          {error ? (
            <p className={styles.errorText} role="alert">
              {error}
            </p>
          ) : null}

          <button
            type="submit"
            className={styles.primaryButton}
            disabled={submitting}
          >
            {submitting ? "正在登录…" : "登录并进入"}
          </button>

          <p className={styles.devHint}>
            开发测试账号：{DEMO_USERNAME} / {DEMO_PASSWORD}
            {USE_MOCK ? "（当前为 Mock 数据模式）" : ""}
          </p>
        </form>

        <footer className={styles.footer}>
          <Link to="/">返回原型入口</Link>
          {" · "}
          <Link to="/admin/subjects">管理端</Link>
        </footer>
      </section>
    </main>
  );
}
