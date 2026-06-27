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
import { useAsync } from "@/lib/useAsync";
import { usePortal } from "@/lib/portalI18n";
import {
  getStudentNotifications,
  markNotificationRead,
  markNotificationImportant,
  archiveNotification,
  deleteNotification,
} from "@/lib/api";
import type { Notification } from "@/lib/portalTypes";
import { IconBell, IconCheck } from "@/components/shell/icons";

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
  const { p } = usePortal();
  const loaded = useAsync(getStudentNotifications, []);
  const [items, setItems] = useState<Notification[] | null>(null);
  const [filter, setFilter] = useState<NotifFilter>("all");
  const [toast, setToast] = useState<string | null>(null);

  // Seed the working copy from the backend; mutations below are UI-local until
  // notification mutation endpoints exist.
  useEffect(() => {
    if (loaded.status === "success") setItems(loaded.data);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loaded.status]);

  const all = (items ?? []).filter((n) => !n.archived);
  const unreadCount = all.filter((n) => !n.read).length;

  function patch(id: string, p2: Partial<Notification>) {
    setItems((cur) => (cur ?? []).map((n) => (n.id === id ? { ...n, ...p2 } : n)));
  }

  const handlers: NotificationHandlers = {
    onToggleRead: (n) => {
      patch(n.id, { read: !n.read });
      markNotificationRead(n.id, !n.read).catch(() => setToast(p.notif.actionFailed));
    },
    onToggleImportant: (n) => {
      patch(n.id, { important: !n.important });
      markNotificationImportant(n.id, !n.important).catch(() =>
        setToast(p.notif.actionFailed)
      );
    },
    onArchive: (n) => {
      patch(n.id, { archived: true });
      archiveNotification(n.id).catch(() => setToast(p.notif.actionFailed));
    },
    onDelete: (n) => {
      setItems((cur) => (cur ?? []).filter((x) => x.id !== n.id));
      deleteNotification(n.id).catch(() => setToast(p.notif.actionFailed));
    },
  };

  function markAllRead() {
    setItems((cur) => (cur ?? []).map((n) => ({ ...n, read: true })));
    all
      .filter((n) => !n.read)
      .forEach((n) =>
        markNotificationRead(n.id, true).catch(() => setToast(p.notif.actionFailed))
      );
  }

  const visible = all.filter((n) => matchesFilter(n, filter));

  return (
    <div className="page-inner">
      <PageHeader
        title={p.notif.title}
        description={p.notif.unreadCount(unreadCount)}
        actions={
          unreadCount > 0 ? (
            <button className="btn btn-outline btn-sm" onClick={markAllRead}>
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
            <NotificationList items={visible} handlers={handlers} />
          )
        }
      </AsyncBoundary>

      {toast && <Toast message={toast} tone="danger" onClose={() => setToast(null)} />}
    </div>
  );
}
