"use client";

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
  onOpen: (n: Notification) => void;
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

        <button
          type="button"
          className="notif-title"
          onClick={() => h.onOpen(n)}
          style={{ background: "none", border: 0, padding: 0, textAlign: "left" }}
        >
          {n.title}
        </button>
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
          className="icon-action"
          title={p.view}
          aria-label={p.view}
          disabled={disabled}
          onClick={() => h.onOpen(n)}
        >
          <IconExternal size={15} />
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
