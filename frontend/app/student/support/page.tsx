"use client";

import { useEffect, useState } from "react";
import {
  AsyncBoundary,
  Card,
  PageHeader,
  SectionHeader,
  EmptyState,
  Toast,
} from "@/components/ui/primitives";
import {
  TicketFilters,
  DEFAULT_TICKET_FILTERS,
  type TicketFilterState,
} from "@/components/tickets/TicketFilters";
import { TicketList, type TicketHandlers } from "@/components/tickets/TicketList";
import { TicketDetailDrawer } from "@/components/tickets/TicketDetailDrawer";
import { useAsync } from "@/lib/useAsync";
import { usePortal, DEPARTMENTS } from "@/lib/portalI18n";
import {
  getSupportTickets,
  forwardToAdmin,
  archiveSupportTicket,
  restoreSupportTicket,
  deleteSupportTicket,
} from "@/lib/api";
import type { SupportTicket, TicketStatus, TicketCategory } from "@/lib/portalTypes";
import { IconTicket } from "@/components/shell/icons";

const CATEGORIES: TicketCategory[] = [
  "academic",
  "schedule",
  "student_services",
  "technical",
  "other",
];

function matchesVisibility(t: SupportTicket, vis: TicketFilterState["visibility"]): boolean {
  if (vis === "deleted") return !!t.deleted;
  if (vis === "archived") return !!t.archived && !t.deleted;
  return !t.archived && !t.deleted;
}

export default function StudentSupportPage() {
  const { p } = usePortal();
  const loaded = useAsync(getSupportTickets, []);
  const [items, setItems] = useState<SupportTicket[] | null>(null);
  const [filters, setFilters] = useState<TicketFilterState>(DEFAULT_TICKET_FILTERS);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  // new-request form
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [department, setDepartment] = useState(DEPARTMENTS[0]);
  const [category, setCategory] = useState<TicketCategory>("academic");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (loaded.status === "success") setItems((cur) => cur ?? loaded.data);
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

  const handlers: TicketHandlers = {
    onView: (t) => setSelectedId(t.id),
    onArchive: (t) => {
      patch(t.id, { archived: true });
      archiveSupportTicket(t.id).catch(() => setToast(p.tickets.actionFailed));
      setToast(p.tickets.archivedToast);
    },
    onRestore: (t) => {
      patch(t.id, { archived: false, deleted: false });
      restoreSupportTicket(t.id).catch(() => setToast(p.tickets.actionFailed));
      setToast(p.tickets.restoredToast);
    },
    onDelete: (t) => {
      patch(t.id, { deleted: true });
      deleteSupportTicket(t.id).catch(() => setToast(p.tickets.actionFailed));
      setToast(p.tickets.deletedToast);
      if (selectedId === t.id) setSelectedId(null);
    },
  };

  // Status update is frontend-only (no backend route yet).
  const onSetStatus = (t: SupportTicket, status: TicketStatus) => patch(t.id, { status });

  const visible = all
    .filter((t) => matchesVisibility(t, filters.visibility))
    .filter((t) => filters.status === "all" || t.status === filters.status)
    .filter((t) => filters.priority === "all" || t.priority === filters.priority)
    .filter((t) => filters.category === "all" || t.category === filters.category)
    .filter((t) => {
      const q = filters.search.trim().toLowerCase();
      if (!q) return true;
      return [t.subject, t.body, t.id, t.origin_question]
        .filter(Boolean)
        .some((s) => (s as string).toLowerCase().includes(q));
    });

  const selected = all.find((t) => t.id === selectedId) ?? null;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!subject.trim() || !body.trim()) return;
    setSubmitting(true);
    try {
      const ticket = await forwardToAdmin({
        subject: subject.trim(),
        body: body.trim(),
        department,
        category,
      });
      setItems((cur) => [ticket, ...(cur ?? [])]);
      setToast(p.sup.ticketCreated(ticket.id, p.enums.department[department] ?? department));
      setSubject("");
      setBody("");
    } catch {
      setToast(p.sup.submitFailed);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="page-inner">
      <PageHeader title={p.tickets.title} />
      <TicketFilters value={filters} onChange={setFilters} />

      <div className="grid cols-2-1" style={{ marginTop: 16 }}>
        <div>
          <AsyncBoundary state={loaded} onRetry={loaded.reload}>
            {() =>
              all.length === 0 ? (
                <EmptyState
                  icon={<IconTicket size={28} />}
                  title={p.sup.noTicketsTitle}
                  description={p.sup.noTicketsDesc}
                />
              ) : visible.length === 0 ? (
                <EmptyState icon={<IconTicket size={28} />} title={p.tickets.noMatch} />
              ) : (
                <TicketList items={visible} handlers={handlers} />
              )
            }
          </AsyncBoundary>
        </div>

        <Card as="section" className="pad-lg">
          <SectionHeader title={p.sup.newRequest} />
          <form className="form-grid" onSubmit={submit}>
            <div className="field">
              <label className="field-label" htmlFor="t-subject">
                {p.sup.subject}
              </label>
              <input
                id="t-subject"
                className="input"
                value={subject}
                onChange={(e) => setSubject(e.target.value)}
                placeholder={p.sup.subjectPlaceholder}
              />
            </div>
            <div className="field">
              <label className="field-label" htmlFor="t-dept">
                {p.sup.department}
              </label>
              <select
                id="t-dept"
                className="select"
                value={department}
                onChange={(e) => setDepartment(e.target.value)}
              >
                {DEPARTMENTS.map((d) => (
                  <option key={d} value={d}>
                    {p.enums.department[d] ?? d}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label className="field-label" htmlFor="t-cat">
                {p.tickets.categoryLabel}
              </label>
              <select
                id="t-cat"
                className="select"
                value={category}
                onChange={(e) => setCategory(e.target.value as TicketCategory)}
              >
                {CATEGORIES.map((c) => (
                  <option key={c} value={c}>
                    {p.enums.ticketCategory[c]}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label className="field-label" htmlFor="t-body">
                {p.sup.details}
              </label>
              <textarea
                id="t-body"
                className="textarea"
                value={body}
                onChange={(e) => setBody(e.target.value)}
                placeholder={p.sup.detailsPlaceholder}
              />
            </div>
            <button
              className="btn btn-primary"
              type="submit"
              disabled={submitting || !subject.trim() || !body.trim()}
            >
              {submitting ? p.sup.submitting : p.sup.submit}
            </button>
          </form>
        </Card>
      </div>

      <TicketDetailDrawer
        ticket={selected}
        onClose={() => setSelectedId(null)}
        onSetStatus={onSetStatus}
        onArchive={handlers.onArchive}
        onRestore={handlers.onRestore}
        onDelete={handlers.onDelete}
      />

      {toast && <Toast message={toast} onClose={() => setToast(null)} />}
    </div>
  );
}
