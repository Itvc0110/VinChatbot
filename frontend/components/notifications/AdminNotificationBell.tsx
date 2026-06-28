"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Badge, type BadgeTone } from "@/components/ui/primitives";
import { useAsync } from "@/lib/useAsync";
import { useAuth } from "@/lib/auth";
import { getAdminTickets } from "@/lib/api";
import { relativeTime } from "@/lib/format";
import type { SupportTicket } from "@/lib/portalTypes";
import { IconBell, IconDatabase, IconTicket, IconUpload } from "@/components/shell/icons";
import { useI18n } from "@/lib/i18n";

type OperationalKind = "ticket_new" | "ticket_reply" | "source_review" | "source_verified";

interface OperationalNotification {
  id: string;
  kind: OperationalKind;
  title: string;
  message: string;
  created_at: string;
  href: string;
  tone: BadgeTone;
  label: string;
}

interface OperationalStrings {
  title: string;
  empty: string;
  unread: (n: number) => string;
  open: string;
  newTicket: string;
  ticketReply: string;
  sourceReview: string;
  sourceVerified: string;
  newTicketMsg: (ticket: SupportTicket) => string;
  ticketReplyMsg: (ticket: SupportTicket) => string;
  reviewTitle: string;
  reviewMsg: string;
  verifiedTitle: string;
  verifiedMsg: string;
}

const RECENT_LIMIT = 8;

const STR: Record<"en" | "vi", OperationalStrings> = {
  en: {
    title: "Admin notifications",
    empty: "No operational notifications.",
    unread: (n: number) => (n === 1 ? "1 unread" : `${n} unread`),
    open: "Open notification",
    newTicket: "New support ticket",
    ticketReply: "Student replied",
    sourceReview: "Source approval request",
    sourceVerified: "Source verified",
    newTicketMsg: (ticket: SupportTicket) =>
      `${ticket.student_name ?? ticket.student_id ?? "A student"} submitted "${ticket.subject}".`,
    ticketReplyMsg: (ticket: SupportTicket) =>
      `${ticket.student_name ?? ticket.student_id ?? "A student"} replied on "${ticket.subject}".`,
    reviewTitle: "Document waiting for senior approval",
    reviewMsg:
      "A lower-level admin uploaded Academic policy update 2026. Review it before Vinnie can cite it.",
    verifiedTitle: "Document approved",
    verifiedMsg:
      "A senior admin verified Academic policy update 2026. The source is ready for Vinnie retrieval.",
  },
  vi: {
    title: "Thông báo quản trị",
    empty: "Chưa có thông báo vận hành.",
    unread: (n: number) => `${n} chưa đọc`,
    open: "Mở thông báo",
    newTicket: "Ticket mới",
    ticketReply: "Sinh viên phản hồi",
    sourceReview: "Yêu cầu duyệt tài liệu",
    sourceVerified: "Tài liệu đã xác thực",
    newTicketMsg: (ticket: SupportTicket) =>
      `${ticket.student_name ?? ticket.student_id ?? "Sinh viên"} đã gửi "${ticket.subject}".`,
    ticketReplyMsg: (ticket: SupportTicket) =>
      `${ticket.student_name ?? ticket.student_id ?? "Sinh viên"} đã phản hồi trong "${ticket.subject}".`,
    reviewTitle: "Tài liệu chờ admin cấp cao xác thực",
    reviewMsg:
      "Admin cấp dưới đã upload Academic policy update 2026. Cần duyệt trước khi Vinnie được trích dẫn.",
    verifiedTitle: "Tài liệu đã được xác thực",
    verifiedMsg:
      "Admin cấp cao đã xác thực Academic policy update 2026. Nguồn đã sẵn sàng cho Vinnie truy xuất.",
  },
};

function hoursAgo(hours: number) {
  return new Date(Date.now() - hours * 60 * 60 * 1000).toISOString();
}

function lastMessage(ticket: SupportTicket) {
  return ticket.messages?.slice().sort(
    (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
  )[0];
}

function ticketNotifications(tickets: SupportTicket[], s: OperationalStrings): OperationalNotification[] {
  const result: OperationalNotification[] = [];
  tickets
    .filter((ticket) => ticket.confirmed_by_user && !ticket.archived && !ticket.deleted)
    .filter((ticket) => ticket.status !== "resolved" && ticket.status !== "closed")
    .forEach((ticket) => {
      const last = lastMessage(ticket);
      if (last?.author === "student" && last.id !== "m1") {
        result.push({
          id: `ticket-reply:${ticket.id}:${last.id}`,
          kind: "ticket_reply",
          title: s.ticketReply,
          message: s.ticketReplyMsg(ticket),
          created_at: last.created_at,
          href: "/admin/tickets",
          tone: "warning",
          label: s.ticketReply,
        });
        return;
      }

      if (ticket.status === "submitted" || ticket.status === "open" || ticket.status === "in_review") {
        result.push({
          id: `ticket-new:${ticket.id}`,
          kind: "ticket_new",
          title: s.newTicket,
          message: s.newTicketMsg(ticket),
          created_at: ticket.submitted_at ?? ticket.created_at,
          href: "/admin/tickets",
          tone: ticket.priority === "urgent" || ticket.priority === "high" ? "danger" : "info",
          label: s.newTicket,
        });
      }
    });
  return result;
}

function sourceNotifications(roles: string[], s: OperationalStrings): OperationalNotification[] {
  const isSeniorAdmin = roles.includes("global_admin");
  if (isSeniorAdmin) {
    return [{
      id: "source-review:academic-policy-2026",
      kind: "source_review",
      title: s.reviewTitle,
      message: s.reviewMsg,
      created_at: hoursAgo(3),
      href: "/admin/sources",
      tone: "warning",
      label: s.sourceReview,
    }];
  }

  return [{
    id: "source-verified:academic-policy-2026",
    kind: "source_verified",
    title: s.verifiedTitle,
    message: s.verifiedMsg,
    created_at: hoursAgo(5),
    href: "/admin/sources",
    tone: "success",
    label: s.sourceVerified,
  }];
}

function KindIcon({ kind }: { kind: OperationalKind }) {
  if (kind === "source_review") return <IconUpload size={15} />;
  if (kind === "source_verified") return <IconDatabase size={15} />;
  if (kind === "ticket_reply") return <IconTicket size={15} />;
  return <IconTicket size={15} />;
}

export function AdminNotificationBell() {
  const { user, token } = useAuth();
  const { lang } = useI18n();
  const pathname = usePathname();
  const tickets = useAsync(() => getAdminTickets(), [token]);
  const s = STR[lang];
  const storageKey = `vinchatbot:admin-op-notif-read:${user?.email ?? "unknown"}`;
  const [open, setOpen] = useState(false);
  const [readIds, setReadIds] = useState<Set<string>>(() => new Set());
  const wrapRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setOpen(false);
    tickets.reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pathname]);

  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(storageKey);
      setReadIds(new Set(raw ? JSON.parse(raw) as string[] : []));
    } catch {
      setReadIds(new Set());
    }
  }, [storageKey]);

  useEffect(() => {
    if (!open) return;
    function onPointerDown(event: MouseEvent) {
      if (!wrapRef.current?.contains(event.target as Node)) setOpen(false);
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  const items = useMemo(() => {
    const ticketItems =
      tickets.status === "success" ? ticketNotifications(tickets.data, s) : [];
    return [...ticketItems, ...sourceNotifications(user?.roles ?? [], s)]
      .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
      .slice(0, RECENT_LIMIT);
  }, [s, tickets.status, tickets.status === "success" ? tickets.data : null, user?.roles]);

  const unread = items.filter((item) => !readIds.has(item.id)).length;

  function markRead(id: string) {
    setReadIds((cur) => {
      const next = new Set(cur);
      next.add(id);
      try {
        window.localStorage.setItem(storageKey, JSON.stringify([...next]));
      } catch {
        /* local read state is best-effort */
      }
      return next;
    });
  }

  return (
    <div className="ah-notif" ref={wrapRef}>
      <button
        type="button"
        className="ah-iconbtn"
        aria-label={s.title}
        aria-haspopup="dialog"
        aria-expanded={open}
        onClick={() => setOpen((current) => !current)}
      >
        <IconBell />
        {unread > 0 && (
          <span className="ah-notif-count" aria-hidden>
            {unread > 9 ? "9+" : unread}
          </span>
        )}
      </button>

      {open && (
        <div className="ah-notif-panel admin-op-notif-panel" role="dialog" aria-label={s.title}>
          <div className="ah-notif-head">
            <span className="ah-notif-title">{s.title}</span>
            {unread > 0 && (
              <span className="ah-notif-unread">{s.unread(unread)}</span>
            )}
          </div>

          <div className="ah-notif-list">
            {items.length === 0 ? (
              <div className="ah-notif-empty">
                <IconBell size={22} />
                <span>{s.empty}</span>
              </div>
            ) : (
              items.map((item) => {
                const read = readIds.has(item.id);
                return (
                  <Link
                    key={item.id}
                    href={item.href}
                    className={`ah-notif-item ${read ? "read" : "unread"}`}
                    aria-label={`${s.open}: ${item.title}`}
                    onClick={() => {
                      markRead(item.id);
                      setOpen(false);
                    }}
                  >
                    <span className="ah-notif-dot" aria-hidden />
                    <span className="ah-notif-ico" aria-hidden>
                      <KindIcon kind={item.kind} />
                    </span>
                    <span className="ah-notif-body">
                      <span className="ah-notif-row1">
                        <Badge tone={item.tone}>{item.label}</Badge>
                        <span className="ah-notif-time">
                          {relativeTime(item.created_at, lang)}
                        </span>
                      </span>
                      <span className="ah-notif-itemtitle">{item.title}</span>
                      <span className="ah-notif-msg">{item.message}</span>
                    </span>
                  </Link>
                );
              })
            )}
          </div>
        </div>
      )}
    </div>
  );
}
