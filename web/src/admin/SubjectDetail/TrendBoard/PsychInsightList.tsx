/* 心理学语义提示：只渲染 psychText 的中性文案，每条附固定免责声明。 */
import { PSYCH_DISCLAIMER, psychSignalTexts } from "../../../lib/psychText";
import styles from "./TrendBoard.module.css";

export function PsychInsightList({ signals }: { signals: string[] }) {
  const items = psychSignalTexts(signals);

  return (
    <section className={styles.insightPanel} aria-labelledby="psych-insight-title">
      <h3 id="psych-insight-title" className={styles.panelTitle}>
        心理学语义提示
      </h3>
      {items.length === 0 ? (
        <p className={styles.insightEmpty}>
          本区间暂无可映射的提示项，指标仅用于辅助观察，请结合面谈与人工复核。
        </p>
      ) : (
        <ul className={styles.insightList}>
          {items.map((item) => (
            <li className={styles.insightItem} key={item.code}>
              <p className={styles.insightTitle}>{item.title}</p>
              <p className={styles.insightSuggestion}>建议动作：{item.suggestion}</p>
              <p className={styles.insightDisclaimer}>{PSYCH_DISCLAIMER}</p>
            </li>
          ))}
        </ul>
      )}
      <p className={styles.panelNote}>
        提示由区间聚合指标映射而来，不是系统结论，也不构成诊断；处置以人工复核为准。
      </p>
    </section>
  );
}
