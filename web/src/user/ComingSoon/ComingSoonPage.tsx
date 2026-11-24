/* 功能待开发提示页：AI援助 / 教育学习入口的统一占位页（ui@1.2 补记 5）。
 * 当前阶段不做任何后端请求，仅展示提示并可返回事项选择页。
 */
import { Link, useSearchParams } from "react-router-dom";
import { PageTitle } from "../../components/common/StateViews";
import styles from "./ComingSoon.module.css";

/** 仅识别白名单内的功能标识，避免把任意 query 直接渲染到页面。 */
const FEATURE_TITLES: Record<string, string> = {
  "ai-aid": "AI援助",
  education: "教育学习",
};

export default function ComingSoonPage() {
  const [searchParams] = useSearchParams();
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
