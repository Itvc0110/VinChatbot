"use client";

import { useState, type KeyboardEvent, type MouseEvent } from "react";
import type { SupportTicket } from "@/lib/portalTypes";
import { usePortal } from "@/lib/portalI18n";
import { formatDateTime } from "@/lib/format";
import { IconAlert, IconClock } from "@/components/shell/icons";
import { TicketBadge, slaState } from "./TicketBadge";

export interface TicketHandlers {
  onView: (t: SupportTicket) => void;
  onArchive: (t: SupportTicket) => void;
  onRestore: (t: SupportTicket) => void;
  onDelete: (t: SupportTicket) => void;
}

export type TicketVariant = "student" | "admin";

// SLA marker shown next to the badges when a ticket is due-soon or overdue.
function SlaMarker({ t }: { t: SupportTicket }) {
  const { p } = usePortal();
  const state = slaState(t);
  if (state === "ok") return null;
  const overdue = state === "overdue";
  const label = overdue ? p.overdue : p.tickets.dueSoon;
  return (
    <span className={`ticket-sla ${overdue ? "overdue" : "due-soon"}`} title={label}>
      {overdue ? <IconAlert size={13} /> : <IconClock size={13} />}
      {label}
    </span>
  );
}

export function TicketCard({
  t,
  h,
  variant = "student",
}: {
  t: SupportTicket;
  h: TicketHandlers;
  variant?: TicketVariant;
}) {
  const { p, lang } = usePortal();
  const locale = lang === "vi" ? "vi-VN" : "en-US";
  const [confirming, setConfirming] = useState(false);
  const isAdmin = variant === "admin";

  const openTicket = () => h.onView(t);
  const onCardKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    if (e.key !== "Enter" && e.key !== " ") return;
    e.preventDefault();
    openTicket();
  };
  const stopCardClick = (e: MouseEvent<HTMLElement>) => e.stopPropagation();
  const stopCardKeyDown = (e: KeyboardEvent<HTMLElement>) => e.stopPropagation();

  return (
    <div
      className="ticket-card ticket-card--clickable"
      role="button"
      tabIndex={0}
      onClick={openTicket}
      onKeyDown={onCardKeyDown}
      aria-label={`${p.tickets.viewDetail}: ${t.subject}`}
    >
      <div className="ticket-card-top">
        <TicketBadge kind="status" value={t.status} />
        <TicketBadge kind="priority" value={t.priority} />
        <span className="ticket-cat">{p.enums.ticketCategory[t.category]}</span>
        <SlaMarker t={t} />
      </div>

      <h3 className="ticket-title-btn">{t.subject}</h3>
      <p className="ticket-preview">{t.body}</p>

      {isAdmin && (
        <div className="ticket-meta-admin">
          {t.student_name && (
            <span>
              {p.adminTickets.colStudent}: {t.student_name}
            </span>
          )}
          <span className={t.assignee ? "" : "unassigned"}>
            {p.adminTickets.assignedTo}: {t.assignee ?? p.adminTickets.unassigned}
          </span>
        </div>
      )}

      <div className="ticket-card-foot">
        <span className="td-sub">
          {p.tickets.created} {formatDateTime(t.created_at, locale)} · {p.tickets.updated}{" "}
          {formatDateTime(t.updated_at, locale)}
        </span>
        {!isAdmin && (
          <div
            className="ticket-card-actions"
            onClick={stopCardClick}
            onKeyDown={stopCardKeyDown}
          >
            {t.deleted ? (
              <button className="btn btn-ghost btn-sm" onClick={() => h.onRestore(t)}>
                {p.tickets.restore}
              </button>
            ) : t.archived ? (
              <>
                <button className="btn btn-ghost btn-sm" onClick={() => h.onRestore(t)}>
                  {p.tickets.restore}
                </button>
                <button
                  className="btn btn-ghost btn-sm danger"
                  onClick={() => setConfirming(true)}
                >
                  {p.tickets.delete}
                </button>
              </>
            ) : (
              <>
                <button className="btn btn-ghost btn-sm" onClick={() => h.onArchive(t)}>
                  {p.tickets.archive}
                </button>
                <button
                  className="btn btn-ghost btn-sm danger"
                  onClick={() => setConfirming(true)}
                >
                  {p.tickets.delete}
                </button>
              </>
            )}
          </div>
        )}
      </div>

      {confirming && (
        <div
          className="confirm-row"
          role="alertdialog"
          onClick={stopCardClick}
          onKeyDown={stopCardKeyDown}
        >
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
