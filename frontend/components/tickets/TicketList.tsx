"use client";

// Thin compatibility surface. The card moved to TicketCard.tsx and the tone maps to
// TicketBadge.tsx (PLAN23.6.01); both are re-exported here so existing imports keep working.
// The flat list is still handy as a single-column fallback, but the board (TicketBoard.tsx)
// is now the primary surface on both the student and admin pages.

import type { SupportTicket } from "@/lib/portalTypes";
import { TicketCard, type TicketHandlers, type TicketVariant } from "./TicketCard";

export { TicketCard } from "./TicketCard";
export type { TicketHandlers, TicketVariant } from "./TicketCard";
export { STATUS_TONE, PRIORITY_TONE, TicketBadge, slaState } from "./TicketBadge";

export function TicketList({
  items,
  handlers,
  variant = "student",
}: {
  items: SupportTicket[];
  handlers: TicketHandlers;
  variant?: TicketVariant;
}) {
  return (
    <div className="ticket-list">
      {items.map((t) => (
        <TicketCard key={t.id} t={t} h={handlers} variant={variant} />
      ))}
    </div>
  );
}
