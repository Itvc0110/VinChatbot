"use client";

import { useState } from "react";
import type {
  SupportTicket,
  TicketStatus,
  TicketPriority,
} from "@/lib/portalTypes";
import { Badge, type BadgeTone } from "@/components/ui/primitives";
import { usePortal } from "@/lib/portalI18n";
import { formatDateTime } from "@/lib/format";

export const STATUS_TONE: Record<TicketStatus, BadgeTone> = {
  open: "info",
  in_progress: "warning",
  waiting: "gold",
  resolved: "success",
  closed: "neutral",
};

export const PRIORITY_TONE: Record<TicketPriority, BadgeTone> = {
  low: "neutral",
  medium: "info",
  high: "danger",
};

export interface TicketHandlers {
  onView: (t: SupportTicket) => void;
  onArchive: (t: SupportTicket) => void;
  onRestore: (t: SupportTicket) => void;
  onDelete: (t: SupportTicket) => void;
}

function TicketCard({ t, h }: { t: SupportTicket; h: TicketHandlers }) {
  const { p, lang } = usePortal();
  const locale = lang === "vi" ? "vi-VN" : "en-US";
  const [confirming, setConfirming] = useState(false);

  return (
    <div className="ticket-card">
      <div className="ticket-card-top">
        <span className="td-sub mono">{t.id}</span>
        <Badge tone={STATUS_TONE[t.status]}>{p.enums.ticketStatus[t.status]}</Badge>
        <Badge tone={PRIORITY_TONE[t.priority]}>{p.enums.ticketPriority[t.priority]}</Badge>
        <span className="ticket-cat">{p.enums.ticketCategory[t.category]}</span>
      </div>

      <button className="ticket-title-btn" onClick={() => h.onView(t)}>
        {t.subject}
      </button>
      <p className="ticket-preview">{t.body}</p>

      <div className="ticket-card-foot">
        <span className="td-sub">
          {p.tickets.created} {formatDateTime(t.created_at, locale)} · {p.tickets.updated}{" "}
          {formatDateTime(t.updated_at, locale)}
        </span>
        <div className="ticket-card-actions">
          <button className="btn btn-ghost btn-sm" onClick={() => h.onView(t)}>
            {p.tickets.viewDetail}
          </button>
          {t.deleted ? (
            <button className="btn btn-ghost btn-sm" onClick={() => h.onRestore(t)}>
              {p.tickets.restore}
            </button>
          ) : t.archived ? (
            <>
              <button className="btn btn-ghost btn-sm" onClick={() => h.onRestore(t)}>
                {p.tickets.restore}
              </button>
              <button className="btn btn-ghost btn-sm danger" onClick={() => setConfirming(true)}>
                {p.tickets.delete}
              </button>
            </>
          ) : (
            <>
              <button className="btn btn-ghost btn-sm" onClick={() => h.onArchive(t)}>
                {p.tickets.archive}
              </button>
              <button className="btn btn-ghost btn-sm danger" onClick={() => setConfirming(true)}>
                {p.tickets.delete}
              </button>
            </>
          )}
        </div>
      </div>

      {confirming && (
        <div className="confirm-row" role="alertdialog">
          <span>{p.tickets.deleteConfirm}</span>
          <button
            className="btn btn-sm btn-danger-soft"
            onClick={() => {
              setConfirming(false);
              h.onDelete(t);
            }}
          >
            {p.tickets.confirmDelete}
          </button>
          <button className="btn btn-sm btn-ghost" onClick={() => setConfirming(false)}>
            {p.tickets.cancel}
          </button>
        </div>
      )}
    </div>
  );
}

export function TicketList({
  items,
  handlers,
}: {
  items: SupportTicket[];
  handlers: TicketHandlers;
}) {
  return (
    <div className="ticket-list">
      {items.map((t) => (
        <TicketCard key={t.id} t={t} h={handlers} />
      ))}
    </div>
  );
}
