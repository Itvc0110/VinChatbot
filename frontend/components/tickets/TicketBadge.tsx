"use client";

// Shared ticket badge + SLA helpers (PLAN23.6.01). The status/priority tone maps used to
// live in TicketList.tsx; they moved here so the board/column/card/drawer can all share one
// badge call without depending on TicketList. TicketList re-exports them for back-compat.

import type {
  SupportTicket,
  TicketStatus,
  TicketPriority,
  SlaState,
} from "@/lib/portalTypes";
import { Badge, type BadgeTone } from "@/components/ui/primitives";
import { usePortal } from "@/lib/portalI18n";

export const STATUS_TONE: Record<TicketStatus, BadgeTone> = {
  draft: "neutral",
  submitted: "info",
  open: "info",
  in_review: "warning",
  in_progress: "warning",
  waiting_for_student: "gold",
  waiting_on_student: "gold",
  resolved: "success",
  closed: "neutral",
};

export const PRIORITY_TONE: Record<TicketPriority, BadgeTone> = {
  low: "neutral",
  medium: "info",
  high: "danger",
  urgent: "danger",
};

type TicketBadgeProps =
  | { kind: "status"; value: TicketStatus }
  | { kind: "priority"; value: TicketPriority };

// One badge call for status or priority, with the right tone + localized label.
export function TicketBadge(props: TicketBadgeProps) {
  const { p } = usePortal();
  if (props.kind === "status") {
    return <Badge tone={STATUS_TONE[props.value]}>{p.enums.ticketStatus[props.value]}</Badge>;
  }
  return <Badge tone={PRIORITY_TONE[props.value]}>{p.enums.ticketPriority[props.value]}</Badge>;
}

// Pure SLA health: "ok" when there is no due date or the ticket is in a terminal state
// (so old resolved/closed tickets never show "overdue"); otherwise compares due_at to now.
const DAY_MS = 24 * 3_600_000;
export function slaState(t: SupportTicket, now: number = Date.now()): SlaState {
  if (!t.due_at) return "ok";
  if (t.status === "resolved" || t.status === "closed") return "ok";
  const due = new Date(t.due_at).getTime();
  if (Number.isNaN(due)) return "ok";
  if (due <= now) return "overdue";
  if (due - now <= DAY_MS) return "due_soon";
  return "ok";
}
