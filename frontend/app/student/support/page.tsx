"use client";

import { useEffect, useState } from "react";
import { AsyncBoundary, PageHeader, EmptyState, Toast } from "@/components/ui/primitives";
import {
  TicketFilters,
  DEFAULT_TICKET_FILTERS,
  type TicketFilterState,
} from "@/components/tickets/TicketFilters";
import { TicketBoard } from "@/components/tickets/TicketBoard";
import { type TicketHandlers } from "@/components/tickets/TicketCard";
import { TicketDetailDrawer } from "@/components/tickets/TicketDetailDrawer";
import { CreateTicketModal } from "@/components/tickets/CreateTicketModal";
import { useAsync } from "@/lib/useAsync";
import { usePortal } from "@/lib/portalI18n";
import { useChat } from "@/lib/chat";
import {
  getSupportTickets,
  updateTicketStatus,
  archiveSupportTicket,
  restoreSupportTicket,
  deleteSupportTicket,
} from "@/lib/api";
import type { SupportTicket, TicketStatus } from "@/lib/portalTypes";
import { IconTicket } from "@/components/shell/icons";

function matchesVisibility(t: SupportTicket, vis: TicketFilterState["visibility"]): boolean {
  if (vis === "deleted") return !!t.deleted;
  if (vis === "archived") return !!t.archived && !t.deleted;
  return !t.archived && !t.deleted;
}

export default function StudentSupportPage() {
  const { p } = usePortal();
  const { ticketsRevision } = useChat();
  const loaded = useAsync(getSupportTickets, []);
  const [items, setItems] = useState<SupportTicket[] | null>(null);
  const [filters, setFilters] = useState<TicketFilterState>(DEFAULT_TICKET_FILTERS);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [toast, setToast] = useState<string | null>(null);

  // Mirror loaded tickets into local state on every successful load (initial + reload).
  // All mutations also persist to the shared store, so a reload re-syncs cleanly.
  useEffect(() => {
    if (loaded.status === "success") setItems(loaded.data);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loaded.status]);

  // A ticket was just sent to admin (via the global Review drawer) — refresh so it appears.
  useEffect(() => {
    if (ticketsRevision > 0) loaded.reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ticketsRevision]);

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

  const onSetStatus = (t: SupportTicket, status: TicketStatus) => {
    patch(t.id, { status });
    updateTicketStatus(t.id, status).catch(() => setToast(p.tickets.actionFailed));
  };

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

  return (
    <div className="page-inner">
      <PageHeader
        title={p.tickets.title}
        description={p.tickets.subtitle}
        actions={
          <button className="btn btn-primary" onClick={() => setCreating(true)}>
            + {p.tickets.newTicket}
          </button>
        }
      />

      <TicketFilters value={filters} onChange={setFilters} variant="student" />

      <AsyncBoundary state={loaded} onRetry={loaded.reload}>
        {() =>
          all.length === 0 ? (
            <EmptyState
              icon={<IconTicket size={28} />}
              title={p.sup.noTicketsTitle}
              description={p.sup.noTicketsDesc}
            />
          ) : (
            <TicketBoard
              variant="student"
              items={visible}
              handlers={handlers}
              sort={filters.sort}
            />
          )
        }
      </AsyncBoundary>

      <TicketDetailDrawer
        ticket={selected}
        onClose={() => setSelectedId(null)}
        onSetStatus={onSetStatus}
        onArchive={handlers.onArchive}
        onRestore={handlers.onRestore}
        onDelete={handlers.onDelete}
      />

      <CreateTicketModal open={creating} onClose={() => setCreating(false)} />

      {toast && <Toast message={toast} onClose={() => setToast(null)} />}
    </div>
  );
}
