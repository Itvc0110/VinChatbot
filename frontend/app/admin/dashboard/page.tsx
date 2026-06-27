"use client";

import Link from "next/link";
import { useAsync } from "@/lib/useAsync";
import { usePortal } from "@/lib/portalI18n";
import {
  getAdminStats,
  getAdminTickets,
  getKnowledgeSources,
  getUnansweredQuestions,
  getAnalytics,
  getAdminNotifications,
} from "@/lib/api";
import { relativeTime } from "@/lib/format";
import {
  IconTicket,
  IconInbox,
  IconAlert,
  IconDatabase,
  IconChart,
  IconUpload,
  IconBell,
  IconCheck,
  IconArrow,
} from "@/components/shell/icons";
import type {
  SupportTicket,
  TicketStatus,
  TicketCategory,
} from "@/lib/portalTypes";

const OPEN: TicketStatus[] = [
  "submitted",
  "open",
  "in_review",
  "in_progress",
  "waiting_for_student",
  "waiting_on_student",
];

const STR = {
  en: {
    operationalOverview: "Operational Overview",
    systemHealthy: "System healthy",
    openTickets: "Open tickets",
    needAdminResponse: "Need admin response",
    pendingSourceReview: "Pending source review",
    indexingIssues: "Indexing issues",
    lowConfidenceAnswers: "Low-confidence answers",
    scheduledNotifs: "Scheduled notifs",
    needsAttention: "Needs Attention",
    nothingUrgent: "Nothing urgent right now. 🎉",
    recentActivity: "Recent Activity",
    noRecentActivity: "No recent activity.",
    quickActions: "Quick Actions",
    uploadSource: "Upload Source",
    reviewTickets: "Review Tickets",
    createNotification: "Create Notification",
    vinnieMonitoring: "Vinnie Monitoring",
    ticketCategories: "Ticket Categories",
    noOpenTickets: "No open tickets.",
    knowledgeBase: "Knowledge Base",
    manage: "Manage",
    indexedDocuments: "Indexed documents",
    pendingReview: "Pending review",
    failedIndex: "Failed index",
    crawledToday: "Crawled today",
    vinnieAiQuality: "Vinnie AI Quality",
    details: "Details",
    sourceCoverage: "Source coverage",
    avgConfidence: "Avg confidence",
    lowConfidence: "Low confidence",
    topTopic: "Top topic",
    attnUploadedTitle: (n: number) => `${n} uploaded source${n === 1 ? "" : "s"} waiting for review`,
    attnUploadedSub: "Knowledge Base · pending review",
    attnFailedTitle: (n: number) => `${n} source${n === 1 ? "" : "s"} failed indexing`,
    attnFailedSub: "Re-crawl or fix the source",
    attnWeakTitle: (n: number) => `${n} answer${n === 1 ? "" : "s"} had weak or missing citations`,
    attnWeakSub: "Vinnie AI · quality",
    attnUnansweredTitle: (n: number) => `${n} question${n === 1 ? "" : "s"} need a verified answer`,
    attnUnansweredSub: "Review queue",
    attnScheduledTitle: (n: number) => `${n} scheduled announcement${n === 1 ? "" : "s"} upcoming`,
    attnScheduledSub: "Notifications · drafts",
    actTicketUpdated: (id: string) => `Ticket ${id} updated`,
    actNotifPublished: "Notification published",
    actIndexingFailed: "Indexing failed",
    actQuestionFlagged: "Question flagged for review",
  },
  vi: {
    operationalOverview: "Tổng quan vận hành",
    systemHealthy: "Hệ thống ổn định",
    openTickets: "Phiếu đang mở",
    needAdminResponse: "Cần phản hồi",
    pendingSourceReview: "Nguồn chờ duyệt",
    indexingIssues: "Lỗi lập chỉ mục",
    lowConfidenceAnswers: "Câu trả lời độ tin cậy thấp",
    scheduledNotifs: "Thông báo đã lên lịch",
    needsAttention: "Cần chú ý",
    nothingUrgent: "Hiện không có việc gấp. 🎉",
    recentActivity: "Hoạt động gần đây",
    noRecentActivity: "Không có hoạt động gần đây.",
    quickActions: "Thao tác nhanh",
    uploadSource: "Tải nguồn lên",
    reviewTickets: "Rà soát phiếu",
    createNotification: "Tạo thông báo",
    vinnieMonitoring: "Giám sát Vinnie",
    ticketCategories: "Loại phiếu",
    noOpenTickets: "Không có phiếu đang mở.",
    knowledgeBase: "Kho tri thức",
    manage: "Quản lý",
    indexedDocuments: "Tài liệu đã lập chỉ mục",
    pendingReview: "Chờ duyệt",
    failedIndex: "Lập chỉ mục lỗi",
    crawledToday: "Thu thập hôm nay",
    vinnieAiQuality: "Chất lượng AI Vinnie",
    details: "Chi tiết",
    sourceCoverage: "Độ phủ nguồn",
    avgConfidence: "Độ tin cậy trung bình",
    lowConfidence: "Độ tin cậy thấp",
    topTopic: "Chủ đề hàng đầu",
    attnUploadedTitle: (n: number) => `${n} nguồn tải lên đang chờ duyệt`,
    attnUploadedSub: "Kho tri thức · chờ duyệt",
    attnFailedTitle: (n: number) => `${n} nguồn lập chỉ mục lỗi`,
    attnFailedSub: "Thu thập lại hoặc sửa nguồn",
    attnWeakTitle: (n: number) => `${n} câu trả lời có trích dẫn yếu hoặc thiếu`,
    attnWeakSub: "AI Vinnie · chất lượng",
    attnUnansweredTitle: (n: number) => `${n} câu hỏi cần câu trả lời đã xác minh`,
    attnUnansweredSub: "Hàng đợi rà soát",
    attnScheduledTitle: (n: number) => `${n} thông báo sắp đăng đã lên lịch`,
    attnScheduledSub: "Thông báo · bản nháp",
    actTicketUpdated: (id: string) => `Phiếu ${id} đã cập nhật`,
    actNotifPublished: "Đã đăng thông báo",
    actIndexingFailed: "Lập chỉ mục lỗi",
    actQuestionFlagged: "Câu hỏi được gắn cờ để rà soát",
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

export default function AdminDashboardPage() {
  const { p, lang } = usePortal();
  const tr = STR[lang];

  const stats = useAsync(() => getAdminStats(), []);
  const tickets = useAsync(() => getAdminTickets(), []);
  const sources = useAsync(() => getKnowledgeSources(), []);
  const questions = useAsync(() => getUnansweredQuestions(), []);
  const analytics = useAsync(() => getAnalytics(), []);
  const notifications = useAsync(() => getAdminNotifications(), []);

  const s = stats.status === "success" ? stats.data : null;
  const tk = tickets.status === "success" ? tickets.data : [];
  const src = sources.status === "success" ? sources.data : [];
  const qs = questions.status === "success" ? questions.data : [];
  const an = analytics.status === "success" ? analytics.data : null;
  const nt = notifications.status === "success" ? notifications.data : [];

  const openTickets = tk.filter((t) => OPEN.includes(t.status) && !t.archived && !t.deleted);
  const needAdmin = openTickets.filter(
    (t) => t.status === "submitted" || t.status === "open" || t.status === "in_progress"
  );
  const pendingReview = src.filter((x) => x.status === "pending").length;
  const failedIndex = src.filter((x) => x.status === "failed").length || (s?.failed_crawls ?? 0);
  const indexed = src.filter((x) => x.status === "indexed").length;
  const scheduledNotifs = nt.filter((n) => (n.status ?? "published") === "draft").length;
  const lowConf = s?.low_confidence_responses ?? 0;

  // Ticket categories breakdown
  const catCounts = new Map<TicketCategory, number>();
  for (const t of openTickets) catCounts.set(t.category, (catCounts.get(t.category) ?? 0) + 1);
  const catTotal = openTickets.length || 1;
  const categories = [...catCounts.entries()].sort((a, b) => b[1] - a[1]);

  // Needs attention (only surfaced when > 0)
  const attention: { icon: React.ReactNode; danger?: boolean; title: string; sub: string; href: string }[] = [];
  if (pendingReview > 0)
    attention.push({ icon: <IconUpload size={16} />, title: tr.attnUploadedTitle(pendingReview), sub: tr.attnUploadedSub, href: "/admin/sources" });
  if (failedIndex > 0)
    attention.push({ icon: <IconAlert size={16} />, danger: true, title: tr.attnFailedTitle(failedIndex), sub: tr.attnFailedSub, href: "/admin/sources" });
  if (lowConf > 0)
    attention.push({ icon: <IconShieldMini />, title: tr.attnWeakTitle(lowConf), sub: tr.attnWeakSub, href: "/admin/analytics" });
  if ((s?.unanswered_questions ?? qs.length) > 0)
    attention.push({ icon: <IconInbox size={16} />, title: tr.attnUnansweredTitle(s?.unanswered_questions ?? qs.length), sub: tr.attnUnansweredSub, href: "/admin/unanswered" });
  if (scheduledNotifs > 0)
    attention.push({ icon: <IconBell size={16} />, title: tr.attnScheduledTitle(scheduledNotifs), sub: tr.attnScheduledSub, href: "/admin/notifications" });

  // Recent activity (synthesized from real data)
  const activity: { icon: React.ReactNode; title: string; sub: string; at: string }[] = [];
  const recentTicket = [...tk].sort((a, b) => b.updated_at.localeCompare(a.updated_at))[0];
  if (recentTicket)
    activity.push({ icon: <IconTicket size={14} />, title: tr.actTicketUpdated(recentTicket.id), sub: recentTicket.subject, at: recentTicket.updated_at });
  const recentNotif = [...nt].filter((n) => (n.status ?? "published") === "published").sort((a, b) => (b.updated_at ?? b.created_at).localeCompare(a.updated_at ?? a.created_at))[0];
  if (recentNotif)
    activity.push({ icon: <IconBell size={14} />, title: tr.actNotifPublished, sub: recentNotif.title, at: recentNotif.updated_at ?? recentNotif.created_at });
  const failedSrc = src.find((x) => x.status === "failed");
  if (failedSrc)
    activity.push({ icon: <IconAlert size={14} />, title: tr.actIndexingFailed, sub: failedSrc.name, at: failedSrc.last_crawled_at ?? new Date().toISOString() });
  const recentQ = [...qs].sort((a, b) => b.created_at.localeCompare(a.created_at))[0];
  if (recentQ)
    activity.push({ icon: <IconInbox size={14} />, title: tr.actQuestionFlagged, sub: recentQ.question, at: recentQ.created_at });
  activity.sort((a, b) => b.at.localeCompare(a.at));

  return (
    <div className="page-inner">
      <div className="adash-grid">
        <div className="adash-main">
          {/* Operational overview */}
          <div>
            <div className="acard-head" style={{ marginBottom: 12 }}>
              <h2 className="acard-title">{tr.operationalOverview}</h2>
              <span className="ah-chip success">
                <IconCheck size={13} /> {tr.systemHealthy}
              </span>
            </div>
            <div className="adash-stats">
              <Stat value={openTickets.length} label={tr.openTickets} icon={<IconTicket size={18} />} />
              <Stat value={needAdmin.length} label={tr.needAdminResponse} icon={<IconInbox size={18} />} tone={needAdmin.length > 0 ? "warning" : "success"} />
              <Stat value={pendingReview} label={tr.pendingSourceReview} icon={<IconDatabase size={18} />} tone={pendingReview > 0 ? "warning" : "success"} />
              <Stat value={failedIndex} label={tr.indexingIssues} icon={<IconAlert size={18} />} tone={failedIndex > 0 ? "danger" : "success"} />
              <Stat value={lowConf} label={tr.lowConfidenceAnswers} icon={<IconChart size={18} />} tone={lowConf > 0 ? "warning" : "success"} />
              <Stat value={scheduledNotifs} label={tr.scheduledNotifs} icon={<IconBell size={18} />} />
            </div>
          </div>

          {/* Needs attention */}
          <div className="acard">
            <div className="acard-head">
              <h2 className="acard-title">{tr.needsAttention}</h2>
            </div>
            {attention.length === 0 ? (
              <p className="attn-sub" style={{ padding: "8px 0" }}>{tr.nothingUrgent}</p>
            ) : (
              attention.map((a, i) => (
                <Link key={i} href={a.href} className="attn-row" style={{ textDecoration: "none" }}>
                  <span className={`attn-icon ${a.danger ? "danger" : ""}`}>{a.icon}</span>
                  <span className="attn-main">
                    <span className="attn-title">{a.title}</span>
                    <span className="attn-sub">{a.sub}</span>
                  </span>
                  <IconArrow size={15} />
                </Link>
              ))
            )}
          </div>

          {/* Recent activity */}
          <div className="acard">
            <div className="acard-head">
              <h2 className="acard-title">{tr.recentActivity}</h2>
            </div>
            {activity.length === 0 ? (
              <p className="attn-sub" style={{ padding: "8px 0" }}>{tr.noRecentActivity}</p>
            ) : (
              activity.map((a, i) => (
                <div key={i} className="act-row">
                  <span className="act-dot">{a.icon}</span>
                  <div className="act-main">
                    <div className="act-title">{a.title}</div>
                    <div className="act-sub">{a.sub}</div>
                  </div>
                  <span className="act-time">{relativeTime(a.at, lang)}</span>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Right rail */}
        <div className="adash-rail">
          <div className="acard">
            <div className="acard-head"><h2 className="acard-title">{tr.quickActions}</h2></div>
            <div className="qa-list">
              <Link className="qa-btn" href="/admin/upload"><span className="qa-icon"><IconUpload size={16} /></span> {tr.uploadSource}</Link>
              <Link className="qa-btn" href="/admin/tickets"><span className="qa-icon"><IconTicket size={16} /></span> {tr.reviewTickets}</Link>
              <Link className="qa-btn" href="/admin/notifications"><span className="qa-icon"><IconBell size={16} /></span> {tr.createNotification}</Link>
              <Link className="qa-btn" href="/admin/analytics"><span className="qa-icon"><IconChart size={16} /></span> {tr.vinnieMonitoring}</Link>
            </div>
          </div>

          <div className="acard">
            <div className="acard-head"><h2 className="acard-title">{tr.ticketCategories}</h2></div>
            {categories.length === 0 ? (
              <p className="attn-sub">{tr.noOpenTickets}</p>
            ) : (
              categories.map(([cat, n]) => {
                const pct = Math.round((n / catTotal) * 100);
                return (
                  <div key={cat} className="bd-row">
                    <span className="bd-label">{p.enums.ticketCategory[cat]}</span>
                    <span className="bd-track"><span className="bd-fill" style={{ width: `${pct}%` }} /></span>
                    <span className="bd-val">{pct}%</span>
                  </div>
                );
              })
            )}
          </div>

          <div className="acard">
            <div className="acard-head">
              <h2 className="acard-title">{tr.knowledgeBase}</h2>
              <Link className="acard-link" href="/admin/sources">{tr.manage} <IconArrow size={13} /></Link>
            </div>
            <div className="mgrid">
              <div className="mcell"><div className="mcell-v">{(s?.indexed_documents ?? indexed).toLocaleString()}</div><div className="mcell-k">{tr.indexedDocuments}</div></div>
              <div className="mcell"><div className="mcell-v">{pendingReview}</div><div className="mcell-k">{tr.pendingReview}</div></div>
              <div className="mcell"><div className="mcell-v">{failedIndex}</div><div className="mcell-k">{tr.failedIndex}</div></div>
              <div className="mcell"><div className="mcell-v">{s?.sources_crawled_today ?? 0}</div><div className="mcell-k">{tr.crawledToday}</div></div>
            </div>
          </div>

          <div className="acard">
            <div className="acard-head">
              <h2 className="acard-title">{tr.vinnieAiQuality}</h2>
              <Link className="acard-link" href="/admin/analytics">{tr.details} <IconArrow size={13} /></Link>
            </div>
            <div className="mgrid">
              <div className="mcell"><div className="mcell-v">{s ? `${Math.round(s.verified_answer_rate * 100)}%` : "—"}</div><div className="mcell-k">{tr.sourceCoverage}</div></div>
              <div className="mcell"><div className="mcell-v">{an ? `${Math.round(an.avg_confidence * 100)}%` : "—"}</div><div className="mcell-k">{tr.avgConfidence}</div></div>
              <div className="mcell"><div className="mcell-v">{lowConf}</div><div className="mcell-k">{tr.lowConfidence}</div></div>
              <div className="mcell"><div className="mcell-v">{an?.top_topics?.[0]?.topic ?? "—"}</div><div className="mcell-k">{tr.topTopic}</div></div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// Small inline shield icon for the "weak citations" attention row (avoids an extra import alias).
function IconShieldMini() {
  return (
    <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor"
      strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M12 3l7 3v5c0 4.4-3 8.3-7 9.5C8 19.3 5 15.4 5 11V6z" />
      <path d="M9.5 12l1.8 1.8L15 10" />
    </svg>
  );
}
