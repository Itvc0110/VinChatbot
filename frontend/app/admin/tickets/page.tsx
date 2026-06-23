"use client";

import { useEffect, useMemo, useState } from "react";
import { AsyncBoundary, PageHeader, EmptyState, Toast } from "@/components/ui/primitives";
import {
  TicketFilters,
  DEFAULT_ADMIN_TICKET_FILTERS,
  type TicketFilterState,
} from "@/components/tickets/TicketFilters";
import { TicketBoard } from "@/components/tickets/TicketBoard";
import { type TicketHandlers } from "@/components/tickets/TicketCard";
import { TicketDetailDrawer } from "@/components/tickets/TicketDetailDrawer";
import { useAsync } from "@/lib/useAsync";
import { usePortal } from "@/lib/portalI18n";
import { getAdminTickets, updateTicketStatus, respondToTicket } from "@/lib/api";
import type { SupportTicket, TicketStatus } from "@/lib/portalTypes";
import { IconTicket } from "@/components/shell/icons";

// Admin submitted-ticket board. getAdminTickets() returns ONLY tickets with
// status !== "draft" && confirmed_by_user === true, so a student's unsent draft can never
// appear here — the structural guarantee behind PLAN22.6's "admin never sees drafts".
const NOOP = () => {};

export default function AdminTicketsPage() {
  const { p } = usePortal();
  const loaded = useAsync(getAdminTickets, []);
  const [items, setItems] = useState<SupportTicket[] | null>(null);
  const [filters, setFilters] = useState<TicketFilterState>(DEFAULT_ADMIN_TICKET_FILTERS);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  useEffect(() => {
    if (loaded.status === "success") setItems(loaded.data);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loaded.status]);

  const all = items ?? [];

  // Distinct assignees seen in the data → drives the assignee filter dropdown.
  const assignees = useMemo(
    () => Array.from(new Set(all.map((t) => t.assignee).filter(Boolean))) as string[],
    [all]
  );

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
    respondToTicket(t.id, body)
      .then((updated) => {
        patch(t.id, { messages: updated.messages, status: updated.status });
        setToast(p.adminTickets.replySent);
      })
      .catch(() => setToast(p.adminTickets.actionFailed));
  };

  // Admin never archives/deletes a student's ticket — the board's admin variant hides those
  // controls, so these handlers exist only to satisfy the shared TicketHandlers shape.
  const handlers: TicketHandlers = {
    onView: (t) => setSelectedId(t.id),
    onArchive: NOOP,
    onRestore: NOOP,
    onDelete: NOOP,
  };

  const visible = all
    .filter((t) => filters.status === "all" || t.status === filters.status)
    .filter((t) => filters.priority === "all" || t.priority === filters.priority)
    .filter((t) => filters.category === "all" || t.category === filters.category)
    .filter((t) => filters.assignee === "all" || t.assignee === filters.assignee)
    .filter((t) => filters.department === "all" || t.department === filters.department)
    .filter((t) => !filters.dateFrom || t.created_at.slice(0, 10) >= filters.dateFrom)
    .filter((t) => !filters.dateTo || t.created_at.slice(0, 10) <= filters.dateTo)
    .filter((t) => {
      const q = filters.search.trim().toLowerCase();
      if (!q) return true;
      return [t.subject, t.body, t.id, t.student_name]
        .filter(Boolean)
        .some((s) => (s as string).toLowerCase().includes(q));
    });

  const selected = all.find((t) => t.id === selectedId) ?? null;

  return (
    <div className="page-inner">
      <PageHeader title={p.adminTickets.title} description={p.adminTickets.subtitle} />

      <TicketFilters
        value={filters}
        onChange={setFilters}
        variant="admin"
        assignees={assignees}
      />

      <AsyncBoundary state={loaded} onRetry={loaded.reload}>
        {() =>
          all.length === 0 ? (
            <EmptyState
              icon={<IconTicket size={28} />}
              title={p.adminTickets.none}
              description={p.adminTickets.noneDesc}
            />
          ) : (
            <TicketBoard
              variant="admin"
              items={visible}
              handlers={handlers}
              sort={filters.sort}
            />
          )
        }
      </AsyncBoundary>

      <TicketDetailDrawer
        ticket={selected}
        mode="admin"
        onClose={() => setSelectedId(null)}
        onSetStatus={onSetStatus}
        onRespond={onRespond}
        onArchive={NOOP}
        onRestore={NOOP}
        onDelete={NOOP}
      />

      {toast && <Toast message={toast} onClose={() => setToast(null)} />}
    </div>
  );
}
