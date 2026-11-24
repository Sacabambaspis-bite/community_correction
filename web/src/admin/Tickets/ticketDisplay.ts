import type { SessionKind, TicketListItem } from "../../api/types";

const KIND_TEXT: Record<SessionKind, string> = {
  checkin: "签到",
  report: "思想汇报",
};

const SUGGESTED_METHOD_TEXT: Record<string, string> = {
  urgent_escalation: "当日联系本人并安排工作人员介入",
  priority_interview: "优先安排工作人员面谈",
  focused_interview: "安排针对性面谈",
  routine_checkin: "安排日常问询",
  recapture: "重新采集并复核",
  talk_to_staff: "联系本人，由工作人员谈话核实",
};

export function isOverdueTicket(ticket: TicketListItem): boolean {
  return (
    ticket.detail_json?.overdue_kind === "checkin" ||
    ticket.detail_json?.overdue_kind === "report"
  );
}

export function ticketSourceText(ticket: TicketListItem): string {
  const kind = ticket.detail_json?.overdue_kind;
  if (kind === "checkin" || kind === "report") {
    const days = ticket.detail_json?.overdue_days;
    const dayText =
      typeof days === "number" && Number.isFinite(days) && days >= 0
        ? ` ${Math.floor(days)} 天`
        : "";
    return `${KIND_TEXT[kind]}逾期${dayText}`;
  }
  if (ticket.final_color === null && ticket.triggered_rules.length === 0) {
    return "逾期复核（类型与天数待接口补充）";
  }
  return "分析规则命中";
}

export function suggestedMethodText(method: string | null): string {
  if (!method) {
    return "未指定";
  }
  if (SUGGESTED_METHOD_TEXT[method]) {
    return SUGGESTED_METHOD_TEXT[method];
  }
  return /[\u4e00-\u9fff]/.test(method) ? method : "由工作人员人工复核";
}
