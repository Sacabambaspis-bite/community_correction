/* 功能待开发提示页：仅保留「教育学习」占位（ui@1.2 补记 14）。
 * `/pending?feature=ai-aid` 已升级为独立页面，此处做旧地址兼容跳转。
 */
import { Link, Navigate, useSearchParams } from "react-router-dom";
import { PageTitle } from "../../components/common/StateViews";
import styles from "./ComingSoon.module.css";

/** 仅识别白名单内的功能标识，避免把任意 query 直接渲染到页面。 */
const FEATURE_TITLES: Record<string, string> = {
  "ai-aid": "AI援助",
  education: "教育学习",
};

export default function ComingSoonPage() {
  const [searchParams] = useSearchParams();
  if (searchParams.get("feature") === "ai-aid") {
    return <Navigate to="/ai-aid" replace />;
  }
  const feature = FEATURE_TITLES[searchParams.get("feature") ?? ""] ?? "该功能";

  return (
    <main className={styles.page}>
      <PageTitle
        title="功能待开发"
        description={`「${feature}」正在建设中，敬请期待。`}
      />

      <section className={styles.card}>
        <p className={styles.text}>
          当前版本暂未开放该功能，后续将在这里提供统一入口与服务说明。
        </p>
        <p className={styles.hint}>
          如需帮助，可联系你所在司法所的工作人员。
        </p>
        <div className={styles.buttonRow}>
          <Link className={styles.primaryButton} to="/capture">
            返回事项选择
          </Link>
        </div>
      </section>
    </main>
  );
}
