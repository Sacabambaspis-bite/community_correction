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
          <Link className={styles.linkCard} to="/login">
            <strong>用户端</strong>
            <span>登录（含知情同意）→ 事项选择 → 采集 → 结果反馈</span>
          </Link>
          <Link className={styles.linkCard} to="/admin/subjects">
            <strong>管理端</strong>
            <span>对象列表（含状态概览）→ 对象详情 → 复核队列</span>
          </Link>
        </div>
        <p className={styles.entryHint}>
          用户端使用开发测试账号登录（登录页内含知情同意）；管理端角色与 token
          由 web/.env 注入。
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
