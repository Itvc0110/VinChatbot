"use client";

import { useEffect, useMemo, useState } from "react";
import { AsyncBoundary, EmptyState, Toast } from "@/components/ui/primitives";
import {
  TicketFilters,
  DEFAULT_TICKET_FILTERS,
  type TicketFilterState,
} from "@/components/tickets/TicketFilters";
import { TicketCard, type TicketHandlers } from "@/components/tickets/TicketCard";
import { TicketDetailDrawer } from "@/components/tickets/TicketDetailDrawer";
import { CreateTicketModal } from "@/components/tickets/CreateTicketModal";
import { useAsync } from "@/lib/useAsync";
import { usePortal } from "@/lib/portalI18n";
import { useAuth } from "@/lib/auth";
import { useChat } from "@/lib/chat";
import {
  getSupportTickets,
  getSupportTicketDetail,
  addTicketMessage,
} from "@/lib/api";
import type { SupportTicket, TicketStatus } from "@/lib/portalTypes";
import { IconTicket } from "@/components/shell/icons";

const PAGE_SIZE = 6;

type Lang = "en" | "vi";

const STR: Record<Lang, {
  pagination: string;
  prevPage: string;
  nextPage: string;
}> = {
  en: {
    pagination: "Pagination",
    prevPage: "Previous page",
    nextPage: "Next page",
  },
  vi: {
    pagination: "Phân trang",
    prevPage: "Trang trước",
    nextPage: "Trang sau",
  },
};

function matchesVisibility(t: SupportTicket, vis: TicketFilterState["visibility"]): boolean {
  if (vis === "deleted") return !!t.deleted;
  if (vis === "archived") return !!t.archived && !t.deleted;
  return !t.archived && !t.deleted;
}

function PlusIcon() {
  return (
    <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor"
      strokeWidth="2" strokeLinecap="round" aria-hidden="true">
      <path d="M12 5v14M5 12h14" />
    </svg>
  );
}

function Chevron({ dir }: { dir: "left" | "right" }) {
  return (
    <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor"
      strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d={dir === "left" ? "M15 18l-6-6 6-6" : "M9 18l6-6-6-6"} />
    </svg>
  );
}

export default function StudentSupportPage() {
  const { p, lang } = usePortal();
  const s = STR[lang];
  const { token } = useAuth();
  const { ticketsRevision } = useChat();
  const loaded = useAsync(getSupportTickets, [token]);
  const [items, setItems] = useState<SupportTicket[] | null>(null);
  const [filters, setFilters] = useState<TicketFilterState>(DEFAULT_TICKET_FILTERS);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const [page, setPage] = useState(1);

  useEffect(() => {
    setItems(null);
    setSelectedId(null);
    setCreating(false);
    setToast(null);
    setPage(1);
  }, [token]);

  useEffect(() => {
    if (loaded.status === "success") setItems(loaded.data);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loaded.status, loaded.status === "success" ? loaded.data : null]);

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
      setToast(p.tickets.archivedToast);
    },
    onRestore: (t) => {
      patch(t.id, { archived: false, deleted: false });
      setToast(p.tickets.restoredToast);
    },
    onDelete: (t) => {
      patch(t.id, { deleted: true });
      setToast(p.tickets.deletedToast);
      if (selectedId === t.id) setSelectedId(null);
    },
  };

  const onSetStatus = (t: SupportTicket, status: TicketStatus) => {
    patch(t.id, { status });
  };

  useEffect(() => {
    if (!selectedId) return;
    let alive = true;
    getSupportTicketDetail(selectedId)
      .then((ticket) => {
        if (!alive) return;
        setItems((cur) => {
          const list = cur ?? [];
          return list.some((item) => item.id === ticket.id)
            ? list.map((item) => (item.id === ticket.id ? ticket : item))
            : [ticket, ...list];
        });
      })
      .catch(() => {
        if (alive) setToast(p.tickets.actionFailed);
      });
    return () => {
      alive = false;
    };
  }, [p.tickets.actionFailed, selectedId]);

  const onRespond = (t: SupportTicket, body: string) => {
    if (!body.trim()) return;
    addTicketMessage(t.id, { body })
      .then((message) => {
        setItems((cur) =>
          (cur ?? []).map((item) =>
            item.id === t.id
              ? {
                  ...item,
                  messages: [...(item.messages ?? []), message],
                  updated_at: message.created_at,
                }
              : item
          )
        );
      })
      .catch(() => setToast(p.tickets.actionFailed));
  };

  const visible = useMemo(
    () =>
      all
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
        }),
    [all, filters]
  );

  const pageCount = Math.max(1, Math.ceil(visible.length / PAGE_SIZE));
  const safePage = Math.min(page, pageCount);
  const pageItems = visible.slice((safePage - 1) * PAGE_SIZE, safePage * PAGE_SIZE);
  const selected = all.find((t) => t.id === selectedId) ?? null;

  return (
    <div className="page-inner">
      <div className="ah-pagehead">
        <div>
          <h1 className="ah-pagehead-title">{p.tickets.title}</h1>
          <p className="ah-pagehead-sub">{p.tickets.subtitle}</p>
        </div>
        <button className="ah-btn-red" onClick={() => setCreating(true)}>
          <PlusIcon /> {p.tickets.newTicket}
        </button>
      </div>

      <TicketFilters
        value={filters}
        onChange={(f) => {
          setFilters(f);
          setPage(1);
        }}
        variant="student"
      />

      <AsyncBoundary state={loaded} onRetry={loaded.reload}>
        {() =>
          all.length === 0 ? (
            <EmptyState
              icon={<IconTicket size={28} />}
              title={p.sup.noTicketsTitle}
              description={p.sup.noTicketsDesc}
            />
          ) : visible.length === 0 ? (
            <EmptyState
              icon={<IconTicket size={28} />}
              title={p.empty}
              description={p.tickets.subtitle}
            />
          ) : (
            <>
              <div className="ticket-cardlist">
                {pageItems.map((t) => (
                  <TicketCard key={t.id} t={t} h={handlers} variant="student" />
                ))}
              </div>

              {pageCount > 1 && (
                <nav className="ah-pagination" aria-label={s.pagination}>
                  <button
                    className="ah-page-btn"
                    onClick={() => setPage(safePage - 1)}
                    disabled={safePage <= 1}
                    aria-label={s.prevPage}
                  >
                    <Chevron dir="left" />
                  </button>
                  {Array.from({ length: pageCount }, (_, i) => i + 1).map((n) => (
                    <button
                      key={n}
                      className={`ah-page-btn ${n === safePage ? "active" : ""}`}
                      onClick={() => setPage(n)}
                      aria-current={n === safePage ? "page" : undefined}
                    >
                      {n}
                    </button>
                  ))}
                  <button
                    className="ah-page-btn"
                    onClick={() => setPage(safePage + 1)}
                    disabled={safePage >= pageCount}
                    aria-label={s.nextPage}
                  >
                    <Chevron dir="right" />
                  </button>
                </nav>
              )}
            </>
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
        onRespond={onRespond}
      />

      <CreateTicketModal open={creating} onClose={() => setCreating(false)} />

      {toast && <Toast message={toast} onClose={() => setToast(null)} />}
    </div>
  );
}
