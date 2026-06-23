"use client";

import type { SupportTicket } from "@/lib/portalTypes";
import { usePortal } from "@/lib/portalI18n";
import { EmptyState } from "@/components/ui/primitives";
import { TicketCard, type TicketHandlers, type TicketVariant } from "./TicketCard";

// One status column of the board: header (label + count), then either skeletons (first
// paint), a compact empty state, or the ticket cards.
export function TicketColumn({
  title,
  items,
  handlers,
  variant,
  loading = false,
}: {
  title: string;
  items: SupportTicket[];
  handlers: TicketHandlers;
  variant: TicketVariant;
  loading?: boolean;
}) {
  const { p } = usePortal();

  return (
    <section className="ticket-col">
      <div className="ticket-col-head">
        <span>{title}</span>
        {!loading && <span className="ticket-col-count">{items.length}</span>}
      </div>
      <div className="ticket-col-body">
        {loading ? (
          Array.from({ length: 2 }).map((_, i) => (
            <div key={i} className="skeleton-card">
              <div className="skel-line w-40" />
              <div className="skel-line w-90" />
              <div className="skel-line w-70" />
            </div>
          ))
        ) : items.length === 0 ? (
          <EmptyState title={p.tickets.colEmpty} />
        ) : (
          items.map((t) => <TicketCard key={t.id} t={t} h={handlers} variant={variant} />)
        )}
      </div>
    </section>
  );
}
