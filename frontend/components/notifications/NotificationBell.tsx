"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { usePortal } from "@/lib/portalI18n";
import { useAuth } from "@/lib/auth";
import { useAsync } from "@/lib/useAsync";
import { getStudentNotifications, markNotificationRead } from "@/lib/api";
import { relativeTime } from "@/lib/format";
import { Badge, type BadgeTone } from "@/components/ui/primitives";
import { IconBell } from "@/components/shell/icons";
import { NotificationDetailModal } from "./NotificationDetailModal";
import type { Notification, NotificationType } from "@/lib/portalTypes";

// Facebook-style notification dropdown for the student top nav. Reads the current
// student's backend notifications and persists mark-as-read through the student API.
const TYPE_TONE: Record<NotificationType, BadgeTone> = {
  academic: "info",
  schedule: "info",
  deadline: "warning",
  event: "success",
  student_services: "neutral",
  system: "neutral",
  forum: "info",
};

const RECENT_LIMIT = 6;
const NOTIFICATIONS_CHANGED_EVENT = "vinchatbot:notifications-changed";

export function NotificationBell({ ariaLabel }: { ariaLabel: string }) {
  const { p, lang } = usePortal();
  const { token } = useAuth();
  const pathname = usePathname();
  const loaded = useAsync(() => getStudentNotifications(lang), [token, lang]);

  const [open, setOpen] = useState(false);
  // The notification whose full-detail popup is open (null = none).
  const [detail, setDetail] = useState<Notification | null>(null);
  const [readIds, setReadIds] = useState<Set<string>>(() => new Set());
  const [pendingIds, setPendingIds] = useState<Set<string>>(() => new Set());
  const wrapRef = useRef<HTMLDivElement>(null);

  // Close when the route changes (navigating via "View all" or any nav link).
  useEffect(() => {
    setOpen(false);
    loaded.reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pathname]);

  useEffect(() => {
    const onChanged = () => loaded.reload();
    window.addEventListener(NOTIFICATIONS_CHANGED_EVENT, onChanged);
    return () => window.removeEventListener(NOTIFICATIONS_CHANGED_EVENT, onChanged);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  useEffect(() => {
    setOpen(false);
    setDetail(null);
    setReadIds(new Set());
    setPendingIds(new Set());
  }, [token]);

  // While open: close on outside click and on Escape.
  useEffect(() => {
    if (!open) return;
    const onPointer = (e: MouseEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onPointer);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onPointer);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const all = (loaded.status === "success" ? loaded.data : []).filter((n) => !n.archived);
  const isRead = (n: Notification) => n.read || readIds.has(n.id);
  const unread = all.filter((n) => !isRead(n)).length;
  const recent = [...all]
    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
    .slice(0, RECENT_LIMIT);

  const setPending = (id: string, pending: boolean) =>
    setPendingIds((cur) => {
      const next = new Set(cur);
      if (pending) next.add(id);
      else next.delete(id);
      return next;
    });

  const markRead = (id: string) => {
    setPending(id, true);
    setReadIds((cur) => {
      if (cur.has(id)) return cur;
      const next = new Set(cur);
      next.add(id);
      return next;
    });
    markNotificationRead(id, true)
      .then(() => loaded.reload())
      .catch(() => {
        setReadIds((cur) => {
          const next = new Set(cur);
          next.delete(id);
          return next;
        });
      })
      .finally(() => setPending(id, false));
  };

  return (
    <>
    <div className="ah-notif" ref={wrapRef}>
      <button
        type="button"
        className="ah-iconbtn"
        aria-label={ariaLabel}
        aria-haspopup="dialog"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
      >
        <IconBell />
        {unread > 0 && (
          <span className="ah-notif-count" aria-hidden>
            {unread > 9 ? "9+" : unread}
          </span>
        )}
      </button>

      {open && (
        <div className="ah-notif-panel" role="dialog" aria-label={p.notif.title}>
          <div className="ah-notif-head">
            <span className="ah-notif-title">{p.notif.title}</span>
            {unread > 0 && (
              <span className="ah-notif-unread">{p.notif.unreadCount(unread)}</span>
            )}
          </div>

          <div className="ah-notif-list">
            {recent.length === 0 ? (
              <div className="ah-notif-empty">
                <IconBell size={22} />
                <span>{p.notif.emptyShort}</span>
              </div>
            ) : (
              recent.map((n) => (
                <button
                  key={n.id}
                  type="button"
                  className={`ah-notif-item ${isRead(n) ? "read" : "unread"}`}
                  disabled={pendingIds.has(n.id)}
                  onClick={() => {
                    if (!isRead(n)) markRead(n.id);
                    setDetail(n);
                    setOpen(false);
                  }}
                >
                  <span className="ah-notif-dot" aria-hidden />
                  <span className="ah-notif-ico" aria-hidden>
                    <IconBell size={15} />
                  </span>
                  <span className="ah-notif-body">
                    <span className="ah-notif-row1">
                      <Badge tone={TYPE_TONE[n.type]}>
                        {p.enums.notificationType[n.type]}
                      </Badge>
                      <span className="ah-notif-time">
                        {relativeTime(n.created_at, lang)}
                      </span>
                    </span>
                    <span className="ah-notif-itemtitle">{n.title}</span>
                    <span className="ah-notif-msg">{n.message}</span>
                  </span>
                </button>
              ))
            )}
          </div>

          <Link
            href="/student/notifications"
            className="ah-notif-foot"
            onClick={() => setOpen(false)}
          >
            {p.viewAll}
          </Link>
        </div>
      )}
    </div>

      <NotificationDetailModal notification={detail} onClose={() => setDetail(null)} />
    </>
  );
}
