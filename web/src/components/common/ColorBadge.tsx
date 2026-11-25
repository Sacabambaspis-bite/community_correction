/* 管理端专用：色码必须与规则名称、证据入口同屏（ui@1.2 §5.2）。
 * 规则编号只用于接口与留痕，界面统一显示中文名称。
 * 用户端组件禁止 import 本文件。
 */
import type { CSSProperties } from "react";
import { Link } from "react-router-dom";
import { COLOR_META, type Color } from "../../lib/colors";
import { ruleListText } from "../../lib/ruleText";
import styles from "./ColorBadge.module.css";

type ColorBadgeProps = {
  color: Color;
  rules: string[];
  evidenceHref?: string;
  at?: string;
};

export function ColorBadge({ color, rules, evidenceHref, at }: ColorBadgeProps) {
  if (rules.length === 0) {
    return (
      <span className={`${styles.badge} ${styles.missing}`} role="alert">
        待补证据
      </span>
    );
  }

  const meta = COLOR_META[color];
  const style = { "--badge-color": `var(${meta.token})` } as CSSProperties;

  return (
    <span className={styles.wrap}>
      <span className={styles.badge} style={style}>
        <span className={styles.dot} aria-hidden="true" />
        {meta.label}
      </span>
      <span className={styles.rules}>{ruleListText(rules)}</span>
      {evidenceHref ? (
        <Link className={styles.link} to={evidenceHref}>
          查看依据
        </Link>
      ) : (
        <span className={styles.linkMissing}>证据入口待补</span>
      )}
      {at ? <span className={styles.at}>{at}</span> : null}
    </span>
  );
}
