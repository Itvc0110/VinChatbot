"use client";

import { useEffect, useState } from "react";
import type { SupportTicket, TicketStatus } from "@/lib/portalTypes";
import { Badge } from "@/components/ui/primitives";
import { usePortal } from "@/lib/portalI18n";
import { formatDateTime } from "@/lib/format";
import { IconExternal, IconAlert, IconClock } from "@/components/shell/icons";
import { STATUS_TONE, PRIORITY_TONE, slaState } from "./TicketBadge";

const STATUSES: TicketStatus[] = [
  "submitted",
  "open",
  "in_progress",
  "waiting_on_student",
  "resolved",
  "closed",
];

export function TicketDetailDrawer({
  ticket,
  onClose,
  onSetStatus,
  onArchive,
  onRestore,
  onDelete,
  mode = "student",
  onRespond,
}: {
  ticket: SupportTicket | null;
  onClose: () => void;
  onSetStatus: (t: SupportTicket, status: TicketStatus) => void;
  onArchive: (t: SupportTicket) => void;
  onRestore: (t: SupportTicket) => void;
  onDelete: (t: SupportTicket) => void;
  // "admin" shows a Respond box + hides the student-only archive/delete controls.
  mode?: "student" | "admin";
  onRespond?: (t: SupportTicket, body: string) => void;
}) {
  const { p, lang } = usePortal();
  const locale = lang === "vi" ? "vi-VN" : "en-US";
  const open = !!ticket;
  const [reply, setReply] = useState("");

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  const authorLabel = (a: "student" | "admin" | "system") =>
    a === "student" ? p.tickets.you : a === "admin" ? p.tickets.staff : p.tickets.systemAuthor;

  return (
    <>
      <div
        className={`detail-scrim ${open ? "open" : ""}`}
        onClick={onClose}
        aria-hidden="true"
      />
      <aside
        className={`detail-drawer wide ticket-detail-modal ${open ? "open" : ""}`}
        role="dialog"
        aria-modal={open ? "true" : undefined}
        aria-label={ticket?.subject ?? p.tickets.title}
        aria-hidden={!open}
      >
        {ticket && (
          <>
            <div className="detail-head">
              <span className="td-sub">{p.tickets.title}</span>
              <button
                className="source-drawer-close"
                onClick={onClose}
                aria-label={p.tickets.close}
                title={p.tickets.close}
              >
                ✕
              </button>
            </div>

            <div className="detail-body">
              <h3 className="detail-title">{ticket.subject}</h3>
              <div className="ticket-detail-badges">
                <Badge tone={STATUS_TONE[ticket.status]}>
                  {p.enums.ticketStatus[ticket.status]}
                </Badge>
                <Badge tone={PRIORITY_TONE[ticket.priority]}>
                  {p.enums.ticketPriority[ticket.priority]}
                </Badge>
                <span className="ticket-cat">{p.enums.ticketCategory[ticket.category]}</span>
                {(() => {
                  const sla = slaState(ticket);
                  if (sla === "ok") return null;
                  const overdue = sla === "overdue";
                  return (
                    <span className={`ticket-sla ${overdue ? "overdue" : "due-soon"}`}>
                      {overdue ? <IconAlert size={13} /> : <IconClock size={13} />}
                      {overdue ? p.overdue : p.tickets.dueSoon}
                      {ticket.due_at && ` · ${p.tickets.dueOn(formatDateTime(ticket.due_at, locale))}`}
                    </span>
                  );
                })()}
              </div>

              {mode === "admin" && (
                <div className="ticket-meta-admin">
                  {ticket.student_name && (
                    <span>
                      {p.adminTickets.colStudent}: {ticket.student_name}
                    </span>
                  )}
                  <span>
                    {p.adminTickets.departmentLabel}:{" "}
                    {p.enums.department[ticket.department] ?? ticket.department}
                  </span>
                  <span className={ticket.assignee ? "" : "unassigned"}>
                    {p.adminTickets.assignedTo}: {ticket.assignee ?? p.adminTickets.unassigned}
                  </span>
                </div>
              )}

              {ticket.origin_question && (
                <div className="ticket-origin">
                  <div className="field-label">{p.tickets.originalQuestion}</div>
                  <p>“{ticket.origin_question}”</p>
                </div>
              )}

              <div className="field-label" style={{ marginTop: 14 }}>
                {p.tickets.conversation}
              </div>
              <div className="ticket-thread">
                {(ticket.messages && ticket.messages.length > 0
                  ? ticket.messages
                  : [
                      {
                        id: "body",
                        author: "student" as const,
                        body: ticket.body,
                        created_at: ticket.created_at,
                      },
                    ]
                ).map((m) => (
                  <div key={m.id} className={`thread-msg author-${m.author}`}>
                    <div className="thread-msg-head">
                      <span className="thread-author">{authorLabel(m.author)}</span>
                      <span className="td-sub">{formatDateTime(m.created_at, locale)}</span>
                    </div>
                    <p>{m.body}</p>
                  </div>
                ))}
                {ticket.resolution && (
                  <div className="route-card" style={{ marginTop: 4 }}>
                    <h3>✓ {p.sup.resolution}</h3>
                    <p style={{ margin: 0 }}>{ticket.resolution}</p>
                  </div>
                )}
              </div>

              {ticket.source_url && (
                <div style={{ marginTop: 12 }}>
                  <div className="field-label">{p.tickets.attachedSource}</div>
                  <a
                    className="notif-action"
                    href={ticket.source_url}
                    target="_blank"
                    rel="noreferrer"
                  >
                    {ticket.source_title ?? ticket.source_url} <IconExternal size={12} />
                  </a>
                </div>
              )}

              {mode === "admin" && ticket.include_chat_context && ticket.included_context && (
                <div className="ticket-origin" style={{ marginTop: 12 }}>
                  <div className="field-label">{p.adminTickets.includedContext}</div>
                  <pre className="review-context">{ticket.included_context}</pre>
                </div>
              )}

              {onRespond && (
                <div style={{ marginTop: 14 }}>
                  <label className="field-label" htmlFor="ticket-reply">
                    {p.adminTickets.respond}
                  </label>
                  <textarea
                    id="ticket-reply"
                    className="textarea"
                    value={reply}
                    onChange={(e) => setReply(e.target.value)}
                    placeholder={p.adminTickets.respondPlaceholder}
                  />
                  <button
                    className="btn btn-outline btn-sm"
                    style={{ marginTop: 8 }}
                    disabled={!reply.trim()}
                    onClick={() => {
                      onRespond(ticket, reply.trim());
                      setReply("");
                    }}
                  >
                    {p.adminTickets.sendReply}
                  </button>
                </div>
              )}

              {(mode === "admin" || mode === "student") && (
                <div className="ticket-detail-actions">
                  {mode === "admin" && (
                    <>
                      <label className="field-label" htmlFor="ticket-status">
                        {p.tickets.statusLabel}
                      </label>
                      <select
                        id="ticket-status"
                        className="select"
                        value={ticket.status}
                        onChange={(e) => onSetStatus(ticket, e.target.value as TicketStatus)}
                      >
                        {STATUSES.map((s) => (
                          <option key={s} value={s}>
                            {p.enums.ticketStatus[s]}
                          </option>
                        ))}
                      </select>
                    </>
                  )}

                {mode === "student" && (
                  <div className="ticket-detail-buttons">
                    {ticket.deleted ? (
                      <button className="btn btn-outline btn-sm" onClick={() => onRestore(ticket)}>
                        {p.tickets.restore}
                      </button>
                    ) : ticket.archived ? (
                      <button className="btn btn-outline btn-sm" onClick={() => onRestore(ticket)}>
                        {p.tickets.restore}
                      </button>
                    ) : (
                      <button className="btn btn-outline btn-sm" onClick={() => onArchive(ticket)}>
                        {p.tickets.archive}
                      </button>
                    )}
                    <button className="btn btn-sm btn-danger-soft" onClick={() => onDelete(ticket)}>
                      {p.tickets.delete}
                    </button>
                  </div>
                )}
                </div>
              )}
            </div>
          </>
        )}
      </aside>
    </>
  );
}
