"use client";

import { useEffect, useMemo, useState } from "react";
import { AsyncBoundary, EmptyState, Toast } from "@/components/ui/primitives";
import { TicketBadge } from "@/components/tickets/TicketBadge";
import { useAsync } from "@/lib/useAsync";
import { usePortal } from "@/lib/portalI18n";
import { getAdminTickets, updateTicketStatus, respondToTicket } from "@/lib/api";
import { initials, formatDateTime, relativeTime } from "@/lib/format";
import type { SupportTicket, TicketStatus, TicketPriority } from "@/lib/portalTypes";
import { IconTicket, IconArrow, IconCheck } from "@/components/shell/icons";

const STATUS_OPTS: TicketStatus[] = ["submitted", "in_review", "waiting_for_student", "resolved", "closed"];
const PRIORITY_OPTS: TicketPriority[] = ["low", "medium", "high"];

// Colocated bilingual strings for UI chrome not covered by the portal dictionary.
const STR = {
  en: {
    searchTickets: "Search tickets",
    searchPlaceholder: "Search tickets…",
    statusFilter: "Status filter",
    priorityFilter: "Priority filter",
    allStatus: "All status",
    allPriority: "All priority",
    noMatch: "No tickets match.",
    selectToReview: "Select a ticket to review.",
    studentContext: "Student Context",
    student: "Student",
    ticketId: "Ticket ID",
    assignedOffice: "Assigned office",
    created: "Created",
    updated: "Updated",
    slaDue: "SLA due",
    aiAnalysis: "✦ Vinnie AI Analysis",
    aiDrafted: "Drafted by Vinnie from the student’s question:",
    aiContext: "Context:",
    aiNoDraft: "Submitted directly by the student — no AI draft. Suggested routing below is rule-based.",
    escalateHigh: "Escalate: high priority",
    conversation: "Conversation",
    quickActions: "Quick Actions",
    markInReview: "Mark in review",
    requestInfo: "Request info",
    resolve: "Resolve",
    close: "Close",
    replyPlaceholder: "Write a reply to the student…",
    sendReply: "Send reply",
  },
  vi: {
    searchTickets: "Tìm phiếu",
    searchPlaceholder: "Tìm phiếu…",
    statusFilter: "Lọc theo trạng thái",
    priorityFilter: "Lọc theo ưu tiên",
    allStatus: "Tất cả trạng thái",
    allPriority: "Tất cả ưu tiên",
    noMatch: "Không có phiếu nào khớp.",
    selectToReview: "Chọn một phiếu để rà soát.",
    studentContext: "Bối cảnh sinh viên",
    student: "Sinh viên",
    ticketId: "Mã phiếu",
    assignedOffice: "Phòng ban phụ trách",
    created: "Tạo lúc",
    updated: "Cập nhật",
    slaDue: "Hạn SLA",
    aiAnalysis: "✦ Phân tích AI Vinnie",
    aiDrafted: "Được Vinnie soạn từ câu hỏi của sinh viên:",
    aiContext: "Bối cảnh:",
    aiNoDraft: "Sinh viên gửi trực tiếp — không có bản nháp AI. Đề xuất phân luồng bên dưới dựa trên quy tắc.",
    escalateHigh: "Nâng mức: ưu tiên cao",
    conversation: "Hội thoại",
    quickActions: "Thao tác nhanh",
    markInReview: "Đánh dấu đang xem xét",
    requestInfo: "Yêu cầu bổ sung",
    resolve: "Giải quyết",
    close: "Đóng",
    replyPlaceholder: "Viết phản hồi cho sinh viên…",
    sendReply: "Gửi phản hồi",
  },
} as const;

export default function AdminTicketsPage() {
  const { p, lang } = usePortal();
  const s = STR[lang];
  const locale = lang === "vi" ? "vi-VN" : "en-US";
  const loaded = useAsync(getAdminTickets, []);
  const [items, setItems] = useState<SupportTicket[] | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<TicketStatus | "all">("all");
  const [priorityFilter, setPriorityFilter] = useState<TicketPriority | "all">("all");
  const [reply, setReply] = useState("");
  const [toast, setToast] = useState<string | null>(null);

  useEffect(() => {
    if (loaded.status === "success") setItems(loaded.data);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loaded.status]);

  const all = items ?? [];

  function patch(id: string, p2: Partial<SupportTicket>) {
    setItems((cur) =>
      (cur ?? []).map((t) =>
        t.id === id ? { ...t, ...p2, updated_at: new Date().toISOString() } : t
      )
    );
  }

  const onSetStatus = (t: SupportTicket, status: TicketStatus) => {
    patch(t.id, { status });
    updateTicketStatus(t.id, status)
      .then(() => setToast(p.adminTickets.statusUpdated))
      .catch(() => setToast(p.adminTickets.actionFailed));
  };

  const onRespond = (t: SupportTicket, body: string) => {
    if (!body.trim()) return;
    respondToTicket(t.id, body)
      .then((updated) => {
        patch(t.id, { messages: updated.messages, status: updated.status });
        setToast(p.adminTickets.replySent);
      })
      .catch(() => setToast(p.adminTickets.actionFailed));
    setReply("");
  };

  const visible = useMemo(
    () =>
      all
        .filter((t) => statusFilter === "all" || t.status === statusFilter)
        .filter((t) => priorityFilter === "all" || t.priority === priorityFilter)
        .filter((t) => {
          const q = search.trim().toLowerCase();
          if (!q) return true;
          return [t.subject, t.body, t.id, t.student_name]
            .filter(Boolean)
            .some((s) => (s as string).toLowerCase().includes(q));
        })
        .sort((a, b) => b.updated_at.localeCompare(a.updated_at)),
    [all, statusFilter, priorityFilter, search]
  );

  // Default the selection to the first visible ticket.
  useEffect(() => {
    if (!selectedId && visible.length > 0) setSelectedId(visible[0].id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [visible.length]);

  const selected = all.find((t) => t.id === selectedId) ?? null;

  return (
    <div className="page-inner">
      <AsyncBoundary state={loaded} onRetry={loaded.reload}>
        {() =>
          all.length === 0 ? (
            <EmptyState
              icon={<IconTicket size={28} />}
              title={p.adminTickets.none}
              description={p.adminTickets.noneDesc}
            />
          ) : (
            <div className="atik-grid">
              {/* LEFT — ticket list */}
              <div className="atik-side">
                <div className="atik-filterbar">
                  <input
                    className="input"
                    placeholder={s.searchPlaceholder}
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    aria-label={s.searchTickets}
                  />
                  <select
                    className="select"
                    value={statusFilter}
                    onChange={(e) => setStatusFilter(e.target.value as TicketStatus | "all")}
                    aria-label={s.statusFilter}
                  >
                    <option value="all">{s.allStatus}</option>
                    {STATUS_OPTS.map((s) => (
                      <option key={s} value={s}>{p.enums.ticketStatus[s]}</option>
                    ))}
                  </select>
                  <select
                    className="select"
                    value={priorityFilter}
                    onChange={(e) => setPriorityFilter(e.target.value as TicketPriority | "all")}
                    aria-label={s.priorityFilter}
                  >
                    <option value="all">{s.allPriority}</option>
                    {PRIORITY_OPTS.map((s) => (
                      <option key={s} value={s}>{p.enums.ticketPriority[s]}</option>
                    ))}
                  </select>
                </div>

                <div className="atik-list">
                  {visible.length === 0 ? (
                    <p className="attn-sub">{s.noMatch}</p>
                  ) : (
                    visible.map((t) => (
                      <button
                        key={t.id}
                        className={`atik-row ${t.id === selectedId ? "active" : ""}`}
                        onClick={() => {
                          setSelectedId(t.id);
                          setReply("");
                        }}
                      >
                        <span className="atik-avatar">{initials(t.student_name ?? "Student")}</span>
                        <span className="atik-row-main">
                          <span className="atik-row-top">
                            <span className="atik-row-id">{t.id}</span>
                            <span className="atik-row-time">{relativeTime(t.updated_at, lang)}</span>
                          </span>
                          <span className="atik-row-name">{t.subject}</span>
                          <span className="atik-row-sub">
                            {t.student_name ?? "Student"} · {p.enums.ticketCategory[t.category]}
                          </span>
                          <span className="atik-row-chips">
                            <TicketBadge kind="status" value={t.status} />
                            <TicketBadge kind="priority" value={t.priority} />
                          </span>
                        </span>
                      </button>
                    ))
                  )}
                </div>
              </div>

              {/* RIGHT — detail panel */}
              <div className="atik-detail">
                {!selected ? (
                  <div className="atik-empty">
                    <IconTicket size={28} />
                    <p>{s.selectToReview}</p>
                  </div>
                ) : (
                  <>
                    <div className="atik-detail-head">
                      <span className="atik-avatar">{initials(selected.student_name ?? "Student")}</span>
                      <div style={{ minWidth: 0, flex: "1 1 auto" }}>
                        <h2 className="atik-detail-title">{selected.subject}</h2>
                        <div className="atik-detail-chips">
                          <TicketBadge kind="status" value={selected.status} />
                          <TicketBadge kind="priority" value={selected.priority} />
                          <span className="ah-chip neutral">{p.enums.ticketCategory[selected.category]}</span>
                        </div>
                      </div>
                    </div>

                    {/* Student context */}
                    <div className="atik-section">
                      <h3 className="atik-section-title">{s.studentContext}</h3>
                      <dl className="atik-kv">
                        <dt>{s.student}</dt><dd>{selected.student_name ?? "—"}</dd>
                        <dt>{s.ticketId}</dt><dd>{selected.id}</dd>
                        <dt>{s.assignedOffice}</dt><dd>{selected.department}</dd>
                        <dt>{s.created}</dt><dd>{formatDateTime(selected.created_at, locale)}</dd>
                        <dt>{s.updated}</dt><dd>{formatDateTime(selected.updated_at, locale)}</dd>
                        {selected.due_at && (
                          <>
                            <dt>{s.slaDue}</dt><dd>{formatDateTime(selected.due_at, locale)}</dd>
                          </>
                        )}
                      </dl>
                    </div>

                    {/* Vinnie AI analysis */}
                    <div className="atik-section">
                      <h3 className="atik-section-title">{s.aiAnalysis}</h3>
                      <div className="atik-ai">
                        {selected.created_by_ai ? (
                          <>
                            {s.aiDrafted}{" "}
                            <em>“{selected.origin_question ?? selected.subject}”</em>.
                            {selected.included_context ? ` ${s.aiContext} ${selected.included_context}` : ""}
                          </>
                        ) : (
                          s.aiNoDraft
                        )}
                        <div className="atik-ai-routing">
                          <span className="ah-chip">{p.enums.ticketCategory[selected.category]}</span>
                          <span className="ah-chip info">{selected.department}</span>
                          {selected.priority === "high" && (
                            <span className="ah-chip warning">{s.escalateHigh}</span>
                          )}
                        </div>
                      </div>
                    </div>

                    {/* Conversation */}
                    <div className="atik-section">
                      <h3 className="atik-section-title">{s.conversation}</h3>
                      <div className="atik-thread">
                        <div className="atik-msg student">
                          <div className="atik-msg-who">{s.student}</div>
                          {selected.body}
                        </div>
                        {(selected.messages ?? [])
                          .filter((m) => m.body !== selected.body)
                          .map((m) => (
                            <div key={m.id} className={`atik-msg ${m.author === "admin" ? "admin" : "student"}`}>
                              <div className="atik-msg-who">{m.author}</div>
                              {m.body}
                            </div>
                          ))}
                      </div>
                    </div>

                    {/* Quick actions */}
                    <div className="atik-section">
                      <h3 className="atik-section-title">{s.quickActions}</h3>
                      <div className="atik-actions" style={{ marginBottom: 12 }}>
                        <button className="btn btn-outline btn-sm" onClick={() => onSetStatus(selected, "in_review")}>
                          {s.markInReview}
                        </button>
                        <button className="btn btn-outline btn-sm" onClick={() => onSetStatus(selected, "waiting_for_student")}>
                          {s.requestInfo}
                        </button>
                        <button className="btn btn-primary btn-sm" onClick={() => onSetStatus(selected, "resolved")}>
                          <IconCheck size={14} /> {s.resolve}
                        </button>
                        <button className="btn btn-ghost btn-sm" onClick={() => onSetStatus(selected, "closed")}>
                          {s.close}
                        </button>
                      </div>
                      <div className="atik-reply">
                        <textarea
                          className="textarea"
                          rows={3}
                          placeholder={s.replyPlaceholder}
                          value={reply}
                          onChange={(e) => setReply(e.target.value)}
                        />
                        <div>
                          <button
                            className="btn btn-primary"
                            disabled={!reply.trim()}
                            onClick={() => onRespond(selected, reply)}
                          >
                            <IconArrow size={14} /> {s.sendReply}
                          </button>
                        </div>
                      </div>
                    </div>
                  </>
                )}
              </div>
            </div>
          )
        }
      </AsyncBoundary>

      {toast && <Toast message={toast} onClose={() => setToast(null)} />}
    </div>
  );
}
