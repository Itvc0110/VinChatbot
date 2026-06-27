"use client";

import type { CSSProperties } from "react";
import type {
  SupportTicket,
  TicketStatus,
  TicketSort,
} from "@/lib/portalTypes";
import { usePortal } from "@/lib/portalI18n";
import { slaState } from "./TicketBadge";
import { TicketColumn } from "./TicketColumn";
import type { TicketHandlers, TicketVariant } from "./TicketCard";

// Column definitions per role. Each column owns one or more statuses; `draft` is never
// listed (and is filtered defensively below) so an unsent draft can never surface here.
interface BucketDef {
  key: string;
  statuses: TicketStatus[];
  label: (p: ReturnType<typeof usePortal>["p"]) => string;
}

const STUDENT_BUCKETS: BucketDef[] = [
  { key: "open", statuses: ["submitted", "open"], label: (p) => p.tickets.colOpen },
  { key: "in_progress", statuses: ["in_review", "in_progress"], label: (p) => p.tickets.colInProgress },
  { key: "waiting", statuses: ["waiting_for_student", "waiting_on_student"], label: (p) => p.tickets.colWaiting },
  { key: "closed", statuses: ["resolved", "closed"], label: (p) => p.tickets.colClosed },
];

const ADMIN_BUCKETS: BucketDef[] = [
  { key: "open", statuses: ["submitted", "open"], label: (p) => p.tickets.colOpen },
  { key: "in_progress", statuses: ["in_review", "in_progress"], label: (p) => p.tickets.colInProgress },
  {
    key: "waiting",
    statuses: ["waiting_for_student", "waiting_on_student"],
    label: (p) => p.adminTickets.colWaitingStudent,
  },
  { key: "resolved", statuses: ["resolved"], label: (p) => p.adminTickets.colResolved },
  { key: "closed", statuses: ["closed"], label: (p) => p.tickets.colClosed },
];

const PRIORITY_RANK: Record<SupportTicket["priority"], number> = {
  urgent: 4,
  high: 3,
  medium: 2,
  low: 1,
};
const SLA_RANK = { overdue: 0, due_soon: 1, ok: 2 } as const;

function comparator(sort: TicketSort): (a: SupportTicket, b: SupportTicket) => number {
  switch (sort) {
    case "created_desc":
      return (a, b) => b.created_at.localeCompare(a.created_at);
    case "priority_desc":
      return (a, b) =>
        PRIORITY_RANK[b.priority] - PRIORITY_RANK[a.priority] ||
        b.updated_at.localeCompare(a.updated_at);
    case "sla_asc":
      return (a, b) => {
        const ra = SLA_RANK[slaState(a)];
        const rb = SLA_RANK[slaState(b)];
        if (ra !== rb) return ra - rb;
        // Both same SLA bucket: earlier due date first; ticket without a due date sorts last.
        const da = a.due_at ? new Date(a.due_at).getTime() : Infinity;
        const db = b.due_at ? new Date(b.due_at).getTime() : Infinity;
        return da - db;
      };
    case "updated_desc":
    default:
      return (a, b) => b.updated_at.localeCompare(a.updated_at);
  }
}

export function TicketBoard({
  items,
  handlers,
  variant,
  sort = "updated_desc",
  loading = false,
}: {
  items: SupportTicket[];
  handlers: TicketHandlers;
  variant: TicketVariant;
  sort?: TicketSort;
  loading?: boolean;
}) {
  const { p } = usePortal();
  const buckets = variant === "admin" ? ADMIN_BUCKETS : STUDENT_BUCKETS;

  // Defensive: drafts never appear on a board (mirrors getAdminTickets' structural guarantee).
  const sorted = items.filter((t) => t.status !== "draft").sort(comparator(sort));

  return (
    <div
      className="ticket-board"
      style={{ "--ticket-cols": buckets.length } as CSSProperties}
    >
      {buckets.map((b) => (
        <TicketColumn
          key={b.key}
          title={b.label(p)}
          items={sorted.filter((t) => b.statuses.includes(t.status))}
          handlers={handlers}
          variant={variant}
          loading={loading}
        />
      ))}
    </div>
  );
}
