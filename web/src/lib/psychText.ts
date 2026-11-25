/* 心理状态提示文案映射（ui@1.2 §4.2.1 / 补记 11）。
 *
 * 后端只回 `summary.signals[]` 机器码，本文件只做中性测量学描述，
 * 严禁出现诊断词或结论式判断；每条提示固定附免责声明。
 */

export type PsychSignalText = {
  code: string;
  title: string;
  suggestion: string;
};

export const PSYCH_DISCLAIMER = "仅作提示，需结合面谈与人工复核";

const PSYCH_SIGNAL_TEXT: Record<string, Omit<PsychSignalText, "code">> = {
  insufficient_data: {
    title: "有效分析样本不足",
    suggestion: "暂不足以形成趋势提示，可按约定继续采集。",
  },
  low_arousal_negative: {
    title: "区间内呈现持续低效价、低唤醒的表达特征",
    suggestion: "建议优先安排面谈，核实近期生活与睡眠状况。",
  },
  high_arousal_negative: {
    title: "出现负向且高强度（高唤醒）的表达",
    suggestion: "建议尽快人工复核，关注是否存在明显紧张或易激惹表现。",
  },
  persistent_low_valence: {
    title: "多日效价持续偏低",
    suggestion: "建议结合面谈核实持续时长与诱因。",
  },
  valence_volatility_high: {
    title: "情绪效价日间波动较大",
    suggestion: "建议结合采集质量与事件背景复核，避免依据单日结论。",
  },
  signal_escalating: {
    title: "近期信号强度呈上行趋势",
    suggestion: "建议关注近期是否有应激事件，并按优先级复核。",
  },
  frequent_low_consistency: {
    title: "多日出现跨模态不一致",
    suggestion: "可能受采集质量或表达方式影响，建议核对影像与录音。",
  },
  frequent_capture_degraded: {
    title: "区间内多次出现分析降级",
    suggestion: "建议核对采集环境与设备，必要时重新采集。",
  },
  behavior_overdue_frequent: {
    title: "区间内多次未按期完成签到或汇报",
    suggestion: "建议联系核实履约情况。",
  },
};

/** 未知机器码也保持中性，不推断含义、不暴露原始编号。 */
const UNKNOWN_SIGNAL: Omit<PsychSignalText, "code"> = {
  title: "暂未识别的提示项",
  suggestion: "当前版本暂无对应说明，建议结合面谈与人工复核。",
};

export function psychSignalText(code: string): PsychSignalText {
  const text = PSYCH_SIGNAL_TEXT[code] ?? UNKNOWN_SIGNAL;
  return { code, title: text.title, suggestion: text.suggestion };
}

/** 去重并保持后端固定顺序，未知码同样降级为中性文案。 */
export function psychSignalTexts(codes: string[]): PsychSignalText[] {
  const seen = new Set<string>();
  const result: PsychSignalText[] = [];
  codes.forEach((code) => {
    if (seen.has(code)) {
      return;
    }
    seen.add(code);
    result.push(psychSignalText(code));
  });
  return result;
}
