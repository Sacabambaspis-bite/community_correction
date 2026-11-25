import { Link, NavLink, Outlet } from "react-router-dom";
import styles from "./AdminLayout.module.css";

const NAV_LINKS = [
  { to: "/admin/subjects", label: "对象列表" },
  { to: "/admin/tickets", label: "复核队列" },
];

export default function AdminLayout() {
  return (
    <div className={styles.shell}>
      <header className={styles.header}>
        <strong className={styles.brand}>管理端 · 原型</strong>
        <nav className={styles.nav}>
          {NAV_LINKS.map((link) => (
            <NavLink
              key={link.to}
              to={link.to}
              className={({ isActive }) =>
                isActive ? `${styles.navItem} ${styles.navActive}` : styles.navItem
              }
            >
              {link.label}
            </NavLink>
          ))}
        </nav>
        <Link className={styles.exit} to="/">
          返回入口
        </Link>
      </header>
      <main className={styles.main}>
        <Outlet />
      </main>
    </div>
  );
}
