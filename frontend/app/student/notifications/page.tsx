"use client";

import { useEffect, useState } from "react";
import {
  AsyncBoundary,
  PageHeader,
  EmptyState,
  Toast,
} from "@/components/ui/primitives";
import {
  NotificationFilters,
  type NotifFilter,
} from "@/components/notifications/NotificationFilters";
import {
  NotificationList,
  type NotificationHandlers,
} from "@/components/notifications/NotificationList";
import { NotificationDetailModal } from "@/components/notifications/NotificationDetailModal";
import { useAsync } from "@/lib/useAsync";
import { usePortal } from "@/lib/portalI18n";
import { useAuth } from "@/lib/auth";
import {
  getStudentNotifications,
  markAllNotificationsRead,
  markNotificationRead,
} from "@/lib/api";
import type { Notification } from "@/lib/portalTypes";
import { IconBell, IconCheck } from "@/components/shell/icons";

const NOTIFICATIONS_CHANGED_EVENT = "vinchatbot:notifications-changed";

function matchesFilter(n: Notification, f: NotifFilter): boolean {
  switch (f) {
    case "all":
      return true;
    case "unread":
      return !n.read;
    case "important":
      return n.important;
    default:
      return n.type === f;
  }
}

export default function StudentNotificationsPage() {
  const { p, lang } = usePortal();
  const { token } = useAuth();
  const loaded = useAsync(() => getStudentNotifications(lang), [token, lang]);
  const [items, setItems] = useState<Notification[] | null>(null);
  const [filter, setFilter] = useState<NotifFilter>("all");
  const [toast, setToast] = useState<string | null>(null);
  const [detail, setDetail] = useState<Notification | null>(null);
  const [pendingIds, setPendingIds] = useState<Set<string>>(() => new Set());
  const [markingAll, setMarkingAll] = useState(false);

  useEffect(() => {
    setItems(null);
    setFilter("all");
    setToast(null);
    setDetail(null);
    setPendingIds(new Set());
    setMarkingAll(false);
  }, [token]);

  useEffect(() => {
    if (loaded.status === "success") setItems(loaded.data);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loaded.status, loaded.status === "success" ? loaded.data : null]);

  const all = (items ?? []).filter((n) => !n.archived);
  const unreadCount = all.filter((n) => !n.read).length;

  function patch(id: string, p2: Partial<Notification>) {
    setItems((cur) => (cur ?? []).map((n) => (n.id === id ? { ...n, ...p2 } : n)));
  }

  function setPending(id: string, pending: boolean) {
    setPendingIds((cur) => {
      const next = new Set(cur);
      if (pending) next.add(id);
      else next.delete(id);
      return next;
    });
  }

  function announceNotificationChange() {
    window.dispatchEvent(new Event(NOTIFICATIONS_CHANGED_EVENT));
  }

  const handlers: NotificationHandlers = {
    onToggleRead: (n) => {
      if (pendingIds.has(n.id)) return;
      const nextRead = !n.read;
      setPending(n.id, true);
      patch(n.id, { read: nextRead });
      markNotificationRead(n.id, nextRead)
        .then((updated) => {
          patch(n.id, { read: updated.read });
          announceNotificationChange();
        })
        .catch(() => {
          patch(n.id, { read: n.read });
          setDetail((current) =>
            current?.id === n.id ? { ...current, read: n.read } : current
          );
          setToast(p.notif.actionFailed);
        })
        .finally(() => setPending(n.id, false));
    },
    onOpen: (n) => {
      setDetail(n.read ? n : { ...n, read: true });
      if (n.read || pendingIds.has(n.id)) return;
      setPending(n.id, true);
      patch(n.id, { read: true });
      markNotificationRead(n.id, true)
        .then((updated) => {
          patch(n.id, { read: updated.read });
          announceNotificationChange();
        })
        .catch(() => {
          patch(n.id, { read: n.read });
          setToast(p.notif.actionFailed);
        })
        .finally(() => setPending(n.id, false));
    },
  };

  function markAllRead() {
    if (markingAll || unreadCount === 0) return;
    const previous = items ?? [];
    setMarkingAll(true);
    setItems((cur) =>
      (cur ?? []).map((n) => (n.archived ? n : { ...n, read: true }))
    );
    markAllNotificationsRead()
      .then(announceNotificationChange)
      .catch(() => {
        setItems(previous);
        setToast(p.notif.actionFailed);
      })
      .finally(() => setMarkingAll(false));
  }

  const visible = all.filter((n) => matchesFilter(n, filter));

  return (
    <div className="page-inner">
      <PageHeader
        title={p.notif.title}
        description={p.notif.unreadCount(unreadCount)}
        actions={
          unreadCount > 0 ? (
            <button
              className="btn btn-outline btn-sm"
              disabled={markingAll}
              onClick={markAllRead}
            >
              <IconCheck size={15} /> {p.notif.markAllRead}
            </button>
          ) : undefined
        }
      />

      <NotificationFilters value={filter} unreadCount={unreadCount} onChange={setFilter} />

      <AsyncBoundary state={loaded} onRetry={loaded.reload} errorLabel={p.notif.loadError}>
        {() =>
          all.length === 0 ? (
            <EmptyState
              icon={<IconBell size={28} />}
              title={p.notif.emptyTitle}
              description={p.notif.emptyDesc}
            />
          ) : visible.length === 0 ? (
            <EmptyState icon={<IconBell size={28} />} title={p.notif.noMatch} />
          ) : (
            <NotificationList items={visible} handlers={handlers} pendingIds={pendingIds} />
          )
        }
      </AsyncBoundary>

      <NotificationDetailModal notification={detail} onClose={() => setDetail(null)} />
      {toast && <Toast message={toast} tone="danger" onClose={() => setToast(null)} />}
    </div>
  );
}
