"use client";

import Link from "next/link";
import type { Notification, NotificationType } from "@/lib/portalTypes";
import { Badge, type BadgeTone, Modal } from "@/components/ui/primitives";
import { usePortal } from "@/lib/portalI18n";
import { relativeTime, formatDate } from "@/lib/format";
import { IconChat, IconExternal } from "@/components/shell/icons";

const TYPE_TONE: Record<NotificationType, BadgeTone> = {
  academic: "info",
  schedule: "info",
  deadline: "warning",
  event: "success",
  student_services: "neutral",
  system: "neutral",
  forum: "info",
};

const STR = {
  en: {
    read: "Read",
    unread: "Unread",
    priority: "Priority",
    status: "Status",
    starts: "Starts",
    ends: "Ends",
    deadline: "Deadline",
    event: "Event",
  },
  vi: {
    read: "Đã đọc",
    unread: "Chưa đọc",
    priority: "Mức ưu tiên",
    status: "Trạng thái",
    starts: "Bắt đầu",
    ends: "Kết thúc",
    deadline: "Hạn chót",
    event: "Sự kiện",
  },
} as const;

// Full-detail popup for a single notification, opened from the bell dropdown. Shows the type,
// timestamp, full message, and any related links (Ask-Vinnie deep link, action, source).
export function NotificationDetailModal({
  notification,
  onClose,
}: {
  notification: Notification | null;
  onClose: () => void;
}) {
  const { p, lang } = usePortal();
  const locale = lang === "vi" ? "vi-VN" : "en-US";
  const s = STR[lang];
  const n = notification;

  return (
    <Modal open={!!n} onClose={onClose} title={n?.title} size="md">
      {n && (
        <div className="notif-detail">
          <div className="notif-detail-meta">
            <Badge tone={TYPE_TONE[n.type]}>{p.enums.notificationType[n.type]}</Badge>
            <Badge tone={n.read ? "neutral" : "info"}>{n.read ? s.read : s.unread}</Badge>
            <span className="notif-detail-time">
              {formatDate(n.created_at, locale)} · {relativeTime(n.created_at, lang)}
            </span>
          </div>

          <p className="notif-detail-msg">{n.message}</p>

          <div className="notif-detail-meta">
            {n.priority && <span>{s.priority}: {n.priority}</span>}
            {n.status && <span>{s.status}: {n.status}</span>}
            {n.start_date && <span>{s.starts}: {formatDate(n.start_date, locale)}</span>}
            {n.end_date && <span>{s.ends}: {formatDate(n.end_date, locale)}</span>}
            {n.deadline && <span>{s.deadline}: {formatDate(n.deadline, locale)}</span>}
            {n.event_date && <span>{s.event}: {formatDate(n.event_date, locale)}</span>}
          </div>

          {(n.source_url || n.action_href || (n.suggested_questions?.length ?? 0) > 0) && (
            <div className="notif-links">
              {n.suggested_questions && n.suggested_questions.length > 0 && (
                <Link
                  className="notif-action"
                  href={`/student/chat?q=${encodeURIComponent(
                    n.suggested_questions[0].question_text
                  )}`}
                  onClick={onClose}
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
      )}
    </Modal>
  );
}
