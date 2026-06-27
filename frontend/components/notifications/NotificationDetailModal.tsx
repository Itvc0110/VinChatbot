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
  const n = notification;

  return (
    <Modal open={!!n} onClose={onClose} title={n?.title} size="md">
      {n && (
        <div className="notif-detail">
          <div className="notif-detail-meta">
            <Badge tone={TYPE_TONE[n.type]}>{p.enums.notificationType[n.type]}</Badge>
            <span className="notif-detail-time">
              {formatDate(n.created_at, locale)} · {relativeTime(n.created_at, lang)}
            </span>
          </div>

          <p className="notif-detail-msg">{n.message}</p>

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
