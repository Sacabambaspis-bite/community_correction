import { Link } from "react-router-dom";
import styles from "./App.module.css";
import { USE_MOCK } from "./lib/env";

export function EntryPage() {
  return (
    <main className={styles.entry}>
      <div className={styles.entryCard}>
        <h1 className={styles.entryTitle}>社区矫正智能辅助系统</h1>
        <p className={styles.entryNote}>
          前端原型入口 · {USE_MOCK ? "Mock 数据模式" : "直连后端 /api"}
        </p>
        <div className={styles.entryLinks}>
          <Link className={styles.linkCard} to="/consent">
            <strong>用户端</strong>
            <span>知情同意 → 采集引导 → 结果反馈</span>
          </Link>
          <Link className={styles.linkCard} to="/admin/subjects">
            <strong>管理端</strong>
            <span>对象列表 / 状态看板 / 复核队列</span>
          </Link>
        </div>
        <p className={styles.entryHint}>
          原型阶段不提供登录页，角色与 token 由 web/.env 注入。
        </p>
      </div>
    </main>
  );
}

export function NotFoundPage() {
  return (
    <main className={styles.entry}>
      <div className={styles.entryCard}>
        <h1 className={styles.entryTitle}>页面不存在</h1>
        <p className={styles.entryNote}>请检查地址，或返回原型入口。</p>
        <Link to="/">返回入口</Link>
      </div>
    </main>
  );
}
