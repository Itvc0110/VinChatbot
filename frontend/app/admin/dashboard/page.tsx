"use client";

import Link from "next/link";
import { getAdminDashboard } from "@/lib/api";
import { relativeTime } from "@/lib/format";
import { useAuth } from "@/lib/auth";
import { usePortal } from "@/lib/portalI18n";
import type { AdminDashboardCount, AdminDashboardUpcomingItem, TicketPriority, TicketStatus } from "@/lib/portalTypes";
import { useAsync } from "@/lib/useAsync";
import {
  IconAlert,
  IconArrow,
  IconBell,
  IconCheck,
  IconChart,
  IconDatabase,
  IconInbox,
  IconTicket,
  IconUpload,
} from "@/components/shell/icons";

const STR = {
  en: {
    operationalOverview: "Operational Overview",
    systemHealthy: "Live backend data",
    loading: "Loading admin dashboard...",
    loadFailed: "Could not load the admin dashboard.",
    retry: "Retry",
    openTickets: "Open tickets",
    needAdminResponse: "Need admin response",
    totalStudents: "Students",
    urgentTickets: "Urgent tickets",
    upcomingAcademic: "Upcoming academic items",
    publishedNotifs: "Published notifs",
    needsAttention: "Needs Attention",
    nothingUrgent: "Nothing urgent right now.",
    recentActivity: "Recent Tickets",
    noRecentActivity: "No recent tickets.",
    quickActions: "Quick Actions",
    uploadSource: "Upload Source",
    reviewTickets: "Review Tickets",
    createNotification: "Create Notification",
    vinnieMonitoring: "Vinnie Monitoring",
    ticketStatuses: "Ticket Statuses",
    ticketPriorities: "Ticket Priorities",
    studentsByInstitute: "Students by Institute",
    upcomingItems: "Upcoming Items",
    noData: "No data available yet.",
    noUpcoming: "No upcoming items.",
    manage: "Manage",
    globalScope: "Global scope",
    instituteScope: (code: string) => `${code} scope`,
    attnAdminTitle: (n: number) => `${n} ticket${n === 1 ? "" : "s"} need admin response`,
    attnAdminSub: "Ticket console · triage",
    attnUrgentTitle: (n: number) => `${n} urgent ticket${n === 1 ? "" : "s"}`,
    attnUrgentSub: "Review priority queue",
    attnDeadlineTitle: (n: number) => `${n} upcoming deadline${n === 1 ? "" : "s"}`,
    attnDeadlineSub: "Academic calendar",
    ticketMeta: (student: string, institute?: string | null) =>
      institute ? `${student} · ${institute}` : student,
  },
  vi: {
    operationalOverview: "Tổng quan vận hành",
    systemHealthy: "Dữ liệu backend trực tiếp",
    loading: "Đang tải bảng điều khiển...",
    loadFailed: "Không tải được bảng điều khiển.",
    retry: "Thử lại",
    openTickets: "Phiếu đang mở",
    needAdminResponse: "Cần phản hồi",
    totalStudents: "Sinh viên",
    urgentTickets: "Phiếu khẩn cấp",
    upcomingAcademic: "Mục học vụ sắp tới",
    publishedNotifs: "Thông báo đã đăng",
    needsAttention: "Cần chú ý",
    nothingUrgent: "Hiện không có việc gấp.",
    recentActivity: "Phiếu gần đây",
    noRecentActivity: "Không có phiếu gần đây.",
    quickActions: "Thao tác nhanh",
    uploadSource: "Tải nguồn lên",
    reviewTickets: "Rà soát phiếu",
    createNotification: "Tạo thông báo",
    vinnieMonitoring: "Giám sát Vinnie",
    ticketStatuses: "Trạng thái phiếu",
    ticketPriorities: "Mức ưu tiên",
    studentsByInstitute: "Sinh viên theo viện",
    upcomingItems: "Mục sắp tới",
    noData: "Chưa có dữ liệu.",
    noUpcoming: "Không có mục sắp tới.",
    manage: "Quản lý",
    globalScope: "Phạm vi toàn trường",
    instituteScope: (code: string) => `Phạm vi ${code}`,
    attnAdminTitle: (n: number) => `${n} phiếu cần phản hồi`,
    attnAdminSub: "Bảng phiếu · phân loại",
    attnUrgentTitle: (n: number) => `${n} phiếu khẩn cấp`,
    attnUrgentSub: "Rà soát hàng ưu tiên",
    attnDeadlineTitle: (n: number) => `${n} hạn học vụ sắp tới`,
    attnDeadlineSub: "Lịch học vụ",
    ticketMeta: (student: string, institute?: string | null) =>
      institute ? `${student} · ${institute}` : student,
  },
} as const;

function Stat({
  value,
  label,
  icon,
  tone = "default",
}: {
  value: React.ReactNode;
  label: string;
  icon: React.ReactNode;
  tone?: "default" | "danger" | "warning" | "success";
}) {
  return (
    <div className={`astat tone-${tone}`}>
      <div className="astat-top">
        <span className="astat-icon">{icon}</span>
      </div>
      <div className="astat-value">{value}</div>
      <div className="astat-label">{label}</div>
    </div>
  );
}

function countValue(rows: AdminDashboardCount[], key: string): number {
  return rows.find((row) => row.key === key)?.count ?? 0;
}

function maxCount(rows: { count: number }[]): number {
  return Math.max(1, ...rows.map((row) => row.count));
}

function itemIcon(item: AdminDashboardUpcomingItem) {
  if (item.item_type === "notification") return <IconBell size={14} />;
  if (item.item_type === "event") return <IconChart size={14} />;
  if (item.item_type === "schedule") return <IconDatabase size={14} />;
  return <IconInbox size={14} />;
}

export default function AdminDashboardPage() {
  const { p, lang } = usePortal();
  const { token } = useAuth();
  const tr = STR[lang];
  const dashboard = useAsync(() => getAdminDashboard(), [token]);

  if (dashboard.status === "loading") {
    return (
      <div className="page-inner">
        <div className="acard">
          <p className="attn-sub" style={{ padding: "8px 0" }}>
            {tr.loading}
          </p>
        </div>
      </div>
    );
  }

  if (dashboard.status === "error") {
    return (
      <div className="page-inner">
        <div className="acard">
          <div className="acard-head">
            <h2 className="acard-title">{tr.loadFailed}</h2>
          </div>
          <p className="attn-sub" style={{ paddingBottom: 12 }}>
            {dashboard.error}
          </p>
          <button className="qa-btn" type="button" onClick={dashboard.reload}>
            {tr.retry}
          </button>
        </div>
      </div>
    );
  }

  const data = dashboard.data;
  const overview = data.overview;
  const statusMax = maxCount(data.ticket_counts_by_status);
  const priorityMax = maxCount(data.ticket_counts_by_priority);
  const studentMax = maxCount(
    data.student_counts_by_institute.map((row) => ({ count: row.student_count }))
  );
  const upcomingAcademic =
    overview.upcoming_deadlines + overview.upcoming_schedules + overview.upcoming_events;
  const scopeLabel =
    data.scope.kind === "global"
      ? tr.globalScope
      : tr.instituteScope(data.scope.institute_code ?? "institute");

  const attention: { icon: React.ReactNode; danger?: boolean; title: string; sub: string; href: string }[] = [];
  if (overview.need_admin_response > 0) {
    attention.push({
      icon: <IconInbox size={16} />,
      title: tr.attnAdminTitle(overview.need_admin_response),
      sub: tr.attnAdminSub,
      href: "/admin/tickets",
    });
  }
  if (overview.urgent_tickets > 0) {
    attention.push({
      icon: <IconAlert size={16} />,
      danger: true,
      title: tr.attnUrgentTitle(overview.urgent_tickets),
      sub: tr.attnUrgentSub,
      href: "/admin/tickets",
    });
  }
  if (overview.upcoming_deadlines > 0) {
    attention.push({
      icon: <IconBell size={16} />,
      title: tr.attnDeadlineTitle(overview.upcoming_deadlines),
      sub: tr.attnDeadlineSub,
      href: "/admin/events",
    });
  }

  return (
    <div className="page-inner">
      <div className="adash-grid">
        <div className="adash-main">
          <div>
            <div className="acard-head" style={{ marginBottom: 12 }}>
              <h2 className="acard-title">{tr.operationalOverview}</h2>
              <span className="ah-chip success">
                <IconCheck size={13} /> {tr.systemHealthy} · {scopeLabel}
              </span>
            </div>
            <div className="adash-stats">
              <Stat value={overview.open_tickets} label={tr.openTickets} icon={<IconTicket size={18} />} />
              <Stat
                value={overview.need_admin_response}
                label={tr.needAdminResponse}
                icon={<IconInbox size={18} />}
                tone={overview.need_admin_response > 0 ? "warning" : "success"}
              />
              <Stat value={overview.total_students} label={tr.totalStudents} icon={<IconDatabase size={18} />} />
              <Stat
                value={overview.urgent_tickets}
                label={tr.urgentTickets}
                icon={<IconAlert size={18} />}
                tone={overview.urgent_tickets > 0 ? "danger" : "success"}
              />
              <Stat value={upcomingAcademic} label={tr.upcomingAcademic} icon={<IconChart size={18} />} />
              <Stat value={overview.published_notifications} label={tr.publishedNotifs} icon={<IconBell size={18} />} />
            </div>
          </div>

          <div className="acard">
            <div className="acard-head">
              <h2 className="acard-title">{tr.needsAttention}</h2>
            </div>
            {attention.length === 0 ? (
              <p className="attn-sub" style={{ padding: "8px 0" }}>
                {tr.nothingUrgent}
              </p>
            ) : (
              attention.map((item) => (
                <Link key={item.title} href={item.href} className="attn-row" style={{ textDecoration: "none" }}>
                  <span className={`attn-icon ${item.danger ? "danger" : ""}`}>{item.icon}</span>
                  <span className="attn-main">
                    <span className="attn-title">{item.title}</span>
                    <span className="attn-sub">{item.sub}</span>
                  </span>
                  <IconArrow size={15} />
                </Link>
              ))
            )}
          </div>

          <div className="acard">
            <div className="acard-head">
              <h2 className="acard-title">{tr.recentActivity}</h2>
              <Link className="acard-link" href="/admin/tickets">
                {tr.manage} <IconArrow size={13} />
              </Link>
            </div>
            {data.recent_tickets.length === 0 ? (
              <p className="attn-sub" style={{ padding: "8px 0" }}>
                {tr.noRecentActivity}
              </p>
            ) : (
              data.recent_tickets.map((ticket) => (
                <div key={ticket.id} className="act-row">
                  <span className="act-dot">
                    <IconTicket size={14} />
                  </span>
                  <div className="act-main">
                    <div className="act-title">{ticket.subject}</div>
                    <div className="act-sub">
                      {tr.ticketMeta(ticket.student_name ?? ticket.student_id ?? "Student", ticket.institute_code)}
                    </div>
                  </div>
                  <span className="act-time">{relativeTime(ticket.updated_at, lang)}</span>
                </div>
              ))
            )}
          </div>
        </div>

        <div className="adash-rail">
          <div className="acard">
            <div className="acard-head">
              <h2 className="acard-title">{tr.quickActions}</h2>
            </div>
            <div className="qa-list">
              <Link className="qa-btn" href="/admin/sources/upload">
                <span className="qa-icon"><IconUpload size={16} /></span> {tr.uploadSource}
              </Link>
              <Link className="qa-btn" href="/admin/tickets">
                <span className="qa-icon"><IconTicket size={16} /></span> {tr.reviewTickets}
              </Link>
              <Link className="qa-btn" href="/admin/notifications">
                <span className="qa-icon"><IconBell size={16} /></span> {tr.createNotification}
              </Link>
              <Link className="qa-btn" href="/admin/analytics">
                <span className="qa-icon"><IconChart size={16} /></span> {tr.vinnieMonitoring}
              </Link>
            </div>
          </div>

          <div className="acard">
            <div className="acard-head">
              <h2 className="acard-title">{tr.ticketStatuses}</h2>
            </div>
            {data.ticket_counts_by_status.every((row) => row.count === 0) ? (
              <p className="attn-sub">{tr.noData}</p>
            ) : (
              data.ticket_counts_by_status.map((row) => {
                const label = p.enums.ticketStatus[row.key as TicketStatus] ?? row.key;
                const pct = Math.round((row.count / statusMax) * 100);
                return (
                  <div key={row.key} className="bd-row">
                    <span className="bd-label">{label}</span>
                    <span className="bd-track"><span className="bd-fill" style={{ width: `${pct}%` }} /></span>
                    <span className="bd-val">{row.count}</span>
                  </div>
                );
              })
            )}
          </div>

          <div className="acard">
            <div className="acard-head">
              <h2 className="acard-title">{tr.ticketPriorities}</h2>
            </div>
            {data.ticket_counts_by_priority.every((row) => row.count === 0) ? (
              <p className="attn-sub">{tr.noData}</p>
            ) : (
              data.ticket_counts_by_priority.map((row) => {
                const label = p.enums.ticketPriority[row.key as TicketPriority] ?? row.key;
                const pct = Math.round((row.count / priorityMax) * 100);
                return (
                  <div key={row.key} className="bd-row">
                    <span className="bd-label">{label}</span>
                    <span className="bd-track"><span className="bd-fill" style={{ width: `${pct}%` }} /></span>
                    <span className="bd-val">{row.count}</span>
                  </div>
                );
              })
            )}
          </div>

          <div className="acard">
            <div className="acard-head">
              <h2 className="acard-title">{tr.studentsByInstitute}</h2>
            </div>
            {data.student_counts_by_institute.length === 0 ? (
              <p className="attn-sub">{tr.noData}</p>
            ) : (
              data.student_counts_by_institute.map((row) => {
                const pct = Math.round((row.student_count / studentMax) * 100);
                return (
                  <div key={row.institute_id} className="bd-row">
                    <span className="bd-label">{row.institute_code}</span>
                    <span className="bd-track"><span className="bd-fill" style={{ width: `${pct}%` }} /></span>
                    <span className="bd-val">{row.student_count}</span>
                  </div>
                );
              })
            )}
          </div>

          <div className="acard">
            <div className="acard-head">
              <h2 className="acard-title">{tr.upcomingItems}</h2>
              <Link className="acard-link" href="/admin/events">
                {tr.manage} <IconArrow size={13} />
              </Link>
            </div>
            {data.upcoming_items.length === 0 ? (
              <p className="attn-sub">{tr.noUpcoming}</p>
            ) : (
              data.upcoming_items.slice(0, 5).map((item) => (
                <div key={`${item.item_type}-${item.id}`} className="act-row">
                  <span className="act-dot">{itemIcon(item)}</span>
                  <div className="act-main">
                    <div className="act-title">{item.title}</div>
                    <div className="act-sub">{item.course_code ?? item.institute_code ?? item.item_type}</div>
                  </div>
                  <span className="act-time">{relativeTime(item.starts_at, lang)}</span>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
