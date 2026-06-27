"use client";

import { useState } from "react";
import Link from "next/link";
import type { Notification, NotificationType } from "@/lib/portalTypes";
import { Badge, type BadgeTone } from "@/components/ui/primitives";
import { usePortal } from "@/lib/portalI18n";
import { relativeTime } from "@/lib/format";
import { IconBell, IconChat, IconCheck, IconExternal } from "@/components/shell/icons";

const TYPE_TONE: Record<NotificationType, BadgeTone> = {
  academic: "info",
  schedule: "info",
  deadline: "warning",
  event: "success",
  student_services: "neutral",
  system: "neutral",
  forum: "info",
};

export interface NotificationHandlers {
  onToggleRead: (n: Notification) => void;
  onToggleImportant: (n: Notification) => void;
  onArchive: (n: Notification) => void;
  onDelete: (n: Notification) => void;
}

function StarIcon({ filled }: { filled: boolean }) {
  return (
    <svg viewBox="0 0 24 24" width="15" height="15" aria-hidden="true"
      fill={filled ? "currentColor" : "none"} stroke="currentColor"
      strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 3l2.7 5.5 6 .9-4.3 4.2 1 6-5.4-2.8L6.6 19.6l1-6L3.3 9.4l6-.9L12 3z" />
    </svg>
  );
}

function ArchiveIcon() {
  return (
    <svg viewBox="0 0 24 24" width="15" height="15" aria-hidden="true"
      fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="4" width="18" height="4" rx="1" />
      <path d="M5 8v11a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V8M10 12h4" />
    </svg>
  );
}

function TrashIcon() {
  return (
    <svg viewBox="0 0 24 24" width="15" height="15" aria-hidden="true"
      fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 6h18M8 6V4a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v2M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" />
    </svg>
  );
}

function NotificationItem({
  n,
  h,
  disabled,
}: {
  n: Notification;
  h: NotificationHandlers;
  disabled: boolean;
}) {
  const { p, lang } = usePortal();
  const [confirming, setConfirming] = useState(false);

  return (
    <div className={`notif-item ${n.read ? "read" : "unread"}`}>
      {!n.read && <span className="notif-unread-dot" aria-hidden="true" />}
      <span className="notif-icon" aria-hidden="true">
        <IconBell size={16} />
      </span>

      <div className="notif-main">
        <div className="notif-top">
          <Badge tone={TYPE_TONE[n.type]}>{p.enums.notificationType[n.type]}</Badge>
          {n.important && (
            <span className="notif-important-tag" title={p.notif.markImportant}>
              <StarIcon filled /> {p.notif.filters.important}
            </span>
          )}
          <span className="notif-time">{relativeTime(n.created_at, lang)}</span>
        </div>

        <div className="notif-title">{n.title}</div>
        <p className="notif-message">{n.message}</p>

        {(n.source_url || n.action_href || (n.suggested_questions?.length ?? 0) > 0) && (
          <div className="notif-links">
            {/* Notification-to-Question: jump into Vinnie pre-loaded with a timely question. */}
            {n.suggested_questions && n.suggested_questions.length > 0 && (
              <Link
                className="notif-action"
                href={`/student/chat?q=${encodeURIComponent(
                  n.suggested_questions[0].question_text
                )}`}
              >
                <IconChat size={12} /> {p.askVinnieAbout}
              </Link>
            )}
            {n.action_href && (
              <a className="notif-action" href={n.action_href}>
                {n.action_label ?? p.view} <IconExternal size={12} />
              </a>
            )}
            {n.source_url && (
              <a className="notif-action" href={n.source_url} target="_blank" rel="noreferrer">
                {p.notif.related}: {n.source_title ?? n.source_url} <IconExternal size={12} />
              </a>
            )}
          </div>
        )}

        {confirming && (
          <div className="confirm-row" role="alertdialog">
            <span>{p.notif.deleteConfirm}</span>
            <button className="btn btn-sm btn-danger-soft" onClick={() => h.onDelete(n)}>
              {p.notif.confirmDelete}
            </button>
            <button className="btn btn-sm btn-ghost" onClick={() => setConfirming(false)}>
              {p.notif.cancel}
            </button>
          </div>
        )}
      </div>

      <div className="notif-actions">
        <button
          className="icon-action"
          title={n.read ? p.notif.markUnread : p.notif.markRead}
          aria-label={n.read ? p.notif.markUnread : p.notif.markRead}
          disabled={disabled}
          onClick={() => h.onToggleRead(n)}
        >
          <IconCheck size={15} />
        </button>
        <button
          className={`icon-action ${n.important ? "active" : ""}`}
          title={n.important ? p.notif.unmarkImportant : p.notif.markImportant}
          aria-label={n.important ? p.notif.unmarkImportant : p.notif.markImportant}
          disabled={disabled}
          onClick={() => h.onToggleImportant(n)}
        >
          <StarIcon filled={n.important} />
        </button>
        <button
          className="icon-action"
          title={p.notif.archive}
          aria-label={p.notif.archive}
          disabled={disabled}
          onClick={() => h.onArchive(n)}
        >
          <ArchiveIcon />
        </button>
        <button
          className="icon-action danger"
          title={p.notif.delete}
          aria-label={p.notif.delete}
          disabled={disabled}
          onClick={() => setConfirming(true)}
        >
          <TrashIcon />
        </button>
      </div>
    </div>
  );
}

export function NotificationList({
  items,
  handlers,
  pendingIds,
}: {
  items: Notification[];
  handlers: NotificationHandlers;
  pendingIds?: Set<string>;
}) {
  return (
    <div className="notif-list">
      {items.map((n) => (
        <NotificationItem key={n.id} n={n} h={handlers} disabled={pendingIds?.has(n.id) ?? false} />
      ))}
    </div>
  );
}
