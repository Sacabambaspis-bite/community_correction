/* api@1.5 §3 错误码 → 可见文案；message 映射覆盖 1005/5000 的具体语义。 */
const CODE_TEXT: Record<number, string> = {
  1001: "参数有误，请检查后重试",
  1002: "未认证，请检查本地 token 配置",
  1003: "无权限访问该资源",
  1004: "资源不存在",
  1005: "当前状态不允许该操作",
  1006: "操作过于频繁，请稍后再试",
  2001: "本次采集未成功",
  2003: "分析未完成，结果暂不可用",
  4000: "本次采集尚未完成",
  5000: "服务暂时不可用，请稍后重试",
};

const MESSAGE_TEXT: Record<string, string> = {
  consent_required: "请先完成知情同意",
  consent_incomplete: "面部图像与语音两项均需同意后才能开始采集",
  consent_revoked: "同意已撤回，如需继续请重新提交同意",
  consent_not_granted: "尚未提交过同意，无需撤回",
  capture_busy: "当前有其他采集正在进行，请稍后再试",
  capture_failed: "本次采集未成功",
  analysis_pipeline_not_ready: "分析功能尚未就绪",
  analysis_failed: "分析未完成，结果暂不可用",
  session_not_captured: "本次采集尚未完成",
};

export function errorText(code: number, message?: string | null): string {
  if (message && MESSAGE_TEXT[message]) {
    return MESSAGE_TEXT[message];
  }
  return CODE_TEXT[code] ?? "操作失败，请稍后重试";
}
