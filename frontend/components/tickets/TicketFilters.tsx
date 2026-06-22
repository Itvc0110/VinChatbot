"use client";

import type {
  TicketStatus,
  TicketPriority,
  TicketCategory,
} from "@/lib/portalTypes";
import { usePortal } from "@/lib/portalI18n";

export type TicketVisibility = "active" | "archived" | "deleted";

export interface TicketFilterState {
  search: string;
  status: TicketStatus | "all";
  priority: TicketPriority | "all";
  category: TicketCategory | "all";
  visibility: TicketVisibility;
}

export const DEFAULT_TICKET_FILTERS: TicketFilterState = {
  search: "",
  status: "all",
  priority: "all",
  category: "all",
  visibility: "active",
};

const STATUSES: TicketStatus[] = ["open", "in_progress", "waiting", "resolved", "closed"];
const PRIORITIES: TicketPriority[] = ["low", "medium", "high"];
const CATEGORIES: TicketCategory[] = [
  "academic",
  "schedule",
  "student_services",
  "technical",
  "other",
];
const VIS: TicketVisibility[] = ["active", "archived", "deleted"];

export function TicketFilters({
  value,
  onChange,
}: {
  value: TicketFilterState;
  onChange: (v: TicketFilterState) => void;
}) {
  const { p } = usePortal();
  const set = (patch: Partial<TicketFilterState>) => onChange({ ...value, ...patch });

  return (
    <div className="ticket-filters">
      <input
        className="input ticket-search"
        placeholder={p.tickets.searchPlaceholder}
        value={value.search}
        onChange={(e) => set({ search: e.target.value })}
        aria-label={p.tickets.searchPlaceholder}
      />
      <select
        className="select"
        value={value.status}
        onChange={(e) => set({ status: e.target.value as TicketStatus | "all" })}
        aria-label={p.tickets.statusLabel}
      >
        <option value="all">
          {p.tickets.statusLabel}: {p.tickets.all}
        </option>
        {STATUSES.map((s) => (
          <option key={s} value={s}>
            {p.enums.ticketStatus[s]}
          </option>
        ))}
      </select>
      <select
        className="select"
        value={value.priority}
        onChange={(e) => set({ priority: e.target.value as TicketPriority | "all" })}
        aria-label={p.tickets.priorityLabel}
      >
        <option value="all">
          {p.tickets.priorityLabel}: {p.tickets.all}
        </option>
        {PRIORITIES.map((s) => (
          <option key={s} value={s}>
            {p.enums.ticketPriority[s]}
          </option>
        ))}
      </select>
      <select
        className="select"
        value={value.category}
        onChange={(e) => set({ category: e.target.value as TicketCategory | "all" })}
        aria-label={p.tickets.categoryLabel}
      >
        <option value="all">
          {p.tickets.categoryLabel}: {p.tickets.all}
        </option>
        {CATEGORIES.map((s) => (
          <option key={s} value={s}>
            {p.enums.ticketCategory[s]}
          </option>
        ))}
      </select>
      <select
        className="select"
        value={value.visibility}
        onChange={(e) => set({ visibility: e.target.value as TicketVisibility })}
        aria-label={p.tickets.visibilityLabel}
      >
        {VIS.map((v) => (
          <option key={v} value={v}>
            {p.tickets.vis[v]}
          </option>
        ))}
      </select>
    </div>
  );
}
