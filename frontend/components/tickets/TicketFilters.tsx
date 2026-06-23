"use client";

import type {
  TicketStatus,
  TicketPriority,
  TicketCategory,
  TicketSort,
} from "@/lib/portalTypes";
import { usePortal, DEPARTMENTS } from "@/lib/portalI18n";

export type TicketVisibility = "active" | "archived" | "deleted";

export interface TicketFilterState {
  search: string;
  status: TicketStatus | "all";
  priority: TicketPriority | "all";
  category: TicketCategory | "all";
  sort: TicketSort;
  visibility: TicketVisibility; // student-only control
  // Admin-only advanced filters (ignored by the student page).
  assignee: string | "all";
  department: string | "all";
  dateFrom: string; // ISO date (yyyy-mm-dd) or ""
  dateTo: string;
}

export const DEFAULT_TICKET_FILTERS: TicketFilterState = {
  search: "",
  status: "all",
  priority: "all",
  category: "all",
  sort: "updated_desc",
  visibility: "active",
  assignee: "all",
  department: "all",
  dateFrom: "",
  dateTo: "",
};

export const DEFAULT_ADMIN_TICKET_FILTERS: TicketFilterState = {
  ...DEFAULT_TICKET_FILTERS,
};

const STATUSES: TicketStatus[] = [
  "submitted",
  "in_review",
  "waiting_for_student",
  "resolved",
  "closed",
];
const PRIORITIES: TicketPriority[] = ["low", "medium", "high"];
const CATEGORIES: TicketCategory[] = [
  "academic",
  "schedule",
  "student_services",
  "technical",
  "other",
];
const SORTS: TicketSort[] = ["updated_desc", "created_desc", "priority_desc", "sla_asc"];
const VIS: TicketVisibility[] = ["active", "archived", "deleted"];

// Large filters panel (PLAN23.6.01). Always renders search + status/priority/category/sort.
// `variant="admin"` adds assignee / department / date-range; `variant="student"` keeps the
// visibility control. Controlled via { value, onChange }.
export function TicketFilters({
  value,
  onChange,
  variant = "student",
  assignees = [],
}: {
  value: TicketFilterState;
  onChange: (v: TicketFilterState) => void;
  variant?: "student" | "admin";
  assignees?: string[];
}) {
  const { p } = usePortal();
  const set = (patch: Partial<TicketFilterState>) => onChange({ ...value, ...patch });
  const isAdmin = variant === "admin";

  return (
    <div className="ticket-filters-panel">
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
          value={value.sort}
          onChange={(e) => set({ sort: e.target.value as TicketSort })}
          aria-label={p.tickets.sortLabel}
        >
          {SORTS.map((s) => (
            <option key={s} value={s}>
              {p.tickets.sortLabel}: {p.tickets.sort[s]}
            </option>
          ))}
        </select>

        {isAdmin && (
          <>
            <select
              className="select"
              value={value.assignee}
              onChange={(e) => set({ assignee: e.target.value })}
              aria-label={p.adminTickets.assigneeLabel}
            >
              <option value="all">
                {p.adminTickets.assigneeLabel}: {p.tickets.all}
              </option>
              {assignees.map((a) => (
                <option key={a} value={a}>
                  {a}
                </option>
              ))}
            </select>
            <select
              className="select"
              value={value.department}
              onChange={(e) => set({ department: e.target.value })}
              aria-label={p.adminTickets.departmentLabel}
            >
              <option value="all">
                {p.adminTickets.departmentLabel}: {p.tickets.all}
              </option>
              {DEPARTMENTS.map((d) => (
                <option key={d} value={d}>
                  {p.enums.department[d] ?? d}
                </option>
              ))}
            </select>
            <input
              type="date"
              className="input"
              value={value.dateFrom}
              onChange={(e) => set({ dateFrom: e.target.value })}
              aria-label={p.adminTickets.dateFrom}
              title={p.adminTickets.dateFrom}
            />
            <input
              type="date"
              className="input"
              value={value.dateTo}
              onChange={(e) => set({ dateTo: e.target.value })}
              aria-label={p.adminTickets.dateTo}
              title={p.adminTickets.dateTo}
            />
          </>
        )}

        {!isAdmin && (
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
        )}
      </div>
    </div>
  );
}
