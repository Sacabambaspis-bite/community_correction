/* 管理端展示映射：把接口返回的规则编号、证据字段与阈值键转成中文。
 * 仅影响界面文案，接口与留痕仍使用原始编号，便于追溯。
 */

const RULE_TEXT: Record<string, string> = {
  R_SINGLE_RED: "单次明确风险",
  R_SINGLE_ORANGE: "单次风险提示",
  R_TREND_YELLOW: "趋势上行预警",
  R_TREND_ORANGE: "趋势风险升高",
  R_TREND_BLUE: "趋势回落",
  R_TREND_GREEN: "趋势平稳",
  R_BASELINE_INSUFFICIENT: "基线样本不足",
  R_CONSISTENCY_CAP: "一致性封顶",
  R_CONSISTENCY_LOW: "一致性偏低",
  R_DEGRADED_REVIEW: "采集降级复核",
  R_SINGLE_SESSION_YELLOW: "单次会话提示",
  R_SINGLE_SESSION_GREEN: "单次会话平稳",
};

const FIELD_PATH_TEXT: Record<string, string> = {
  consistency: "一致性",
  degraded: "采集降级标记",
  "channels.psych.output.intent_flag": "心理分析·意图标记",
  "psych.output.intent_flag": "心理分析·意图标记",
  "channels.psych.output.signal_strength": "心理分析·信号强度",
  "psych.output.signal_strength": "心理分析·信号强度",
  "channels.emotion.output.label": "情绪分析·情绪标签",
  "channels.face.output.expression_label": "面部识别·表情标签",
  "baseline.sample_count": "基线·样本数",
  "window.usable_session_count": "趋势窗口·可用会话数",
};

const THRESHOLD_KEY_TEXT: Record<string, string> = {
  CONSISTENCY_MIN: "一致性下限",
  CONSISTENCY_CAP_COLOR: "一致性封顶色",
  DEGRADED_REVIEW: "降级复核阈值",
  SINGLE_RED_INTENT_FLAG: "明确意图判红",
  SINGLE_RED_SELFHARM_SIGNAL: "自伤提及判红信号值",
  SINGLE_ORANGE_SIGNAL_MIN: "单次橙色信号下限",
  ORANGE_AUX_EMOTION_LABEL: "橙色辅助·情绪标签",
  ORANGE_AUX_FACE_EXPRESSIONS: "橙色辅助·面部表情",
  TREND_BLUE_OFFSET_MIN: "趋势回落偏移下限",
  TREND_YELLOW_OFFSET_MIN: "趋势上行偏移下限",
  TREND_ORANGE_OFFSET_MIN: "趋势升高偏移下限",
  BASELINE_MIN_SAMPLES: "基线最小样本数",
  TREND_MIN_SESSIONS: "趋势最小可用会话数",
};

const VALUE_TEXT: Record<string, string> = {
  low: "低",
  medium: "中",
  high: "高",
  baseline_insufficient: "基线样本不足",
  window_sessions_insufficient: "窗口可用会话不足",
};

/** 规则编号 → 中文名称；未知规则统一显示「其他规则」，避免露出英文编号。 */
export function ruleText(ruleId: string): string {
  return RULE_TEXT[ruleId] ?? "其他规则";
}

export function ruleListText(rules: string[]): string {
  return rules.length > 0 ? rules.map(ruleText).join("、") : "—";
}

export function fieldPathText(path: string): string {
  return FIELD_PATH_TEXT[path] ?? "分析字段";
}

export function thresholdKeyText(key: string): string {
  return THRESHOLD_KEY_TEXT[key] ?? "其他阈值";
}

/** 证据观测值 / 阈值：布尔与常见枚举转中文，其余保留数字或中文，未知英文以「—」占位。 */
export function evidenceValueText(value: string | number | boolean | null): string {
  if (value === null || value === undefined) {
    return "—";
  }
  if (typeof value === "boolean") {
    return value ? "是" : "否";
  }
  if (typeof value === "number") {
    return String(value);
  }
  const text = value.trim();
  if (VALUE_TEXT[text]) {
    return VALUE_TEXT[text];
  }
  return /[\u4e00-\u9fff]/.test(text) ? text : "—";
}

const EMOTION_TEXT: Record<string, string> = {
  neutral: "中性",
  calm: "平静",
  positive: "积极",
  negative: "消极",
  happy: "愉快",
  sad: "低落",
  angry: "愤怒",
  anxious: "焦虑",
  fear: "恐惧",
  disgust: "厌恶",
  surprise: "惊讶",
  low: "低落",
  medium: "中等",
  high: "较高",
};

/** 情绪标签（来自分析服务）→ 中文；未知标签回退为「其他」。 */
export function emotionText(label: string): string {
  if (!label) {
    return "—";
  }
  return EMOTION_TEXT[label.toLowerCase()] ?? (/[\u4e00-\u9fff]/.test(label) ? label : "其他");
}
