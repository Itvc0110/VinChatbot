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

const OPEN: TicketStatus[] = ["submitted", "in_review", "waiting_for_student"];

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
  const needAdmin = openTickets.filter((t) => t.status === "submitted" || t.status === "in_review");
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
    attention.push({ icon: <IconUpload size={16} />, title: `${pendingReview} uploaded source${pendingReview === 1 ? "" : "s"} waiting for review`, sub: "Knowledge Base · pending review", href: "/admin/sources" });
  if (failedIndex > 0)
    attention.push({ icon: <IconAlert size={16} />, danger: true, title: `${failedIndex} source${failedIndex === 1 ? "" : "s"} failed indexing`, sub: "Re-crawl or fix the source", href: "/admin/sources" });
  if (lowConf > 0)
    attention.push({ icon: <IconShieldMini />, title: `${lowConf} answer${lowConf === 1 ? "" : "s"} had weak or missing citations`, sub: "Vinnie AI · quality", href: "/admin/analytics" });
  if ((s?.unanswered_questions ?? qs.length) > 0)
    attention.push({ icon: <IconInbox size={16} />, title: `${s?.unanswered_questions ?? qs.length} question${(s?.unanswered_questions ?? qs.length) === 1 ? "" : "s"} need a verified answer`, sub: "Review queue", href: "/admin/unanswered" });
  if (scheduledNotifs > 0)
    attention.push({ icon: <IconBell size={16} />, title: `${scheduledNotifs} scheduled announcement${scheduledNotifs === 1 ? "" : "s"} upcoming`, sub: "Notifications · drafts", href: "/admin/notifications" });

  // Recent activity (synthesized from real data)
  const activity: { icon: React.ReactNode; title: string; sub: string; at: string }[] = [];
  const recentTicket = [...tk].sort((a, b) => b.updated_at.localeCompare(a.updated_at))[0];
  if (recentTicket)
    activity.push({ icon: <IconTicket size={14} />, title: `Ticket ${recentTicket.id} updated`, sub: recentTicket.subject, at: recentTicket.updated_at });
  const recentNotif = [...nt].filter((n) => (n.status ?? "published") === "published").sort((a, b) => (b.updated_at ?? b.created_at).localeCompare(a.updated_at ?? a.created_at))[0];
  if (recentNotif)
    activity.push({ icon: <IconBell size={14} />, title: "Notification published", sub: recentNotif.title, at: recentNotif.updated_at ?? recentNotif.created_at });
  const failedSrc = src.find((x) => x.status === "failed");
  if (failedSrc)
    activity.push({ icon: <IconAlert size={14} />, title: "Indexing failed", sub: failedSrc.name, at: failedSrc.last_crawled_at ?? new Date().toISOString() });
  const recentQ = [...qs].sort((a, b) => b.created_at.localeCompare(a.created_at))[0];
  if (recentQ)
    activity.push({ icon: <IconInbox size={14} />, title: "Question flagged for review", sub: recentQ.question, at: recentQ.created_at });
  activity.sort((a, b) => b.at.localeCompare(a.at));

  return (
    <div className="page-inner">
      <div className="adash-grid">
        <div className="adash-main">
          {/* Operational overview */}
          <div>
            <div className="acard-head" style={{ marginBottom: 12 }}>
              <h2 className="acard-title">Operational Overview</h2>
              <span className="ah-chip success">
                <IconCheck size={13} /> System healthy
              </span>
            </div>
            <div className="adash-stats">
              <Stat value={openTickets.length} label="Open tickets" icon={<IconTicket size={18} />} />
              <Stat value={needAdmin.length} label="Need admin response" icon={<IconInbox size={18} />} tone={needAdmin.length > 0 ? "warning" : "success"} />
              <Stat value={pendingReview} label="Pending source review" icon={<IconDatabase size={18} />} tone={pendingReview > 0 ? "warning" : "success"} />
              <Stat value={failedIndex} label="Indexing issues" icon={<IconAlert size={18} />} tone={failedIndex > 0 ? "danger" : "success"} />
              <Stat value={lowConf} label="Low-confidence answers" icon={<IconChart size={18} />} tone={lowConf > 0 ? "warning" : "success"} />
              <Stat value={scheduledNotifs} label="Scheduled notifs" icon={<IconBell size={18} />} />
            </div>
          </div>

          {/* Needs attention */}
          <div className="acard">
            <div className="acard-head">
              <h2 className="acard-title">Needs Attention</h2>
            </div>
            {attention.length === 0 ? (
              <p className="attn-sub" style={{ padding: "8px 0" }}>Nothing urgent right now. 🎉</p>
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
              <h2 className="acard-title">Recent Activity</h2>
            </div>
            {activity.length === 0 ? (
              <p className="attn-sub" style={{ padding: "8px 0" }}>No recent activity.</p>
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
            <div className="acard-head"><h2 className="acard-title">Quick Actions</h2></div>
            <div className="qa-list">
              <Link className="qa-btn" href="/admin/upload"><span className="qa-icon"><IconUpload size={16} /></span> Upload Source</Link>
              <Link className="qa-btn" href="/admin/tickets"><span className="qa-icon"><IconTicket size={16} /></span> Review Tickets</Link>
              <Link className="qa-btn" href="/admin/notifications"><span className="qa-icon"><IconBell size={16} /></span> Create Notification</Link>
              <Link className="qa-btn" href="/admin/analytics"><span className="qa-icon"><IconChart size={16} /></span> Vinnie Monitoring</Link>
            </div>
          </div>

          <div className="acard">
            <div className="acard-head"><h2 className="acard-title">Ticket Categories</h2></div>
            {categories.length === 0 ? (
              <p className="attn-sub">No open tickets.</p>
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
              <h2 className="acard-title">Knowledge Base</h2>
              <Link className="acard-link" href="/admin/sources">Manage <IconArrow size={13} /></Link>
            </div>
            <div className="mgrid">
              <div className="mcell"><div className="mcell-v">{(s?.indexed_documents ?? indexed).toLocaleString()}</div><div className="mcell-k">Indexed documents</div></div>
              <div className="mcell"><div className="mcell-v">{pendingReview}</div><div className="mcell-k">Pending review</div></div>
              <div className="mcell"><div className="mcell-v">{failedIndex}</div><div className="mcell-k">Failed index</div></div>
              <div className="mcell"><div className="mcell-v">{s?.sources_crawled_today ?? 0}</div><div className="mcell-k">Crawled today</div></div>
            </div>
          </div>

          <div className="acard">
            <div className="acard-head">
              <h2 className="acard-title">Vinnie AI Quality</h2>
              <Link className="acard-link" href="/admin/analytics">Details <IconArrow size={13} /></Link>
            </div>
            <div className="mgrid">
              <div className="mcell"><div className="mcell-v">{s ? `${Math.round(s.verified_answer_rate * 100)}%` : "—"}</div><div className="mcell-k">Source coverage</div></div>
              <div className="mcell"><div className="mcell-v">{an ? `${Math.round(an.avg_confidence * 100)}%` : "—"}</div><div className="mcell-k">Avg confidence</div></div>
              <div className="mcell"><div className="mcell-v">{lowConf}</div><div className="mcell-k">Low confidence</div></div>
              <div className="mcell"><div className="mcell-v">{an?.top_topics?.[0]?.topic ?? "—"}</div><div className="mcell-k">Top topic</div></div>
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
