"use client";

import { usePortal } from "@/lib/portalI18n";

export type NotifFilter =
  | "all"
  | "unread"
  | "important"
  | "academic"
  | "schedule"
  | "deadline"
  | "event"
  | "system";

const ORDER: NotifFilter[] = [
  "all",
  "unread",
  "important",
  "academic",
  "schedule",
  "deadline",
  "event",
  "system",
];

export function NotificationFilters({
  value,
  unreadCount,
  onChange,
}: {
  value: NotifFilter;
  unreadCount: number;
  onChange: (f: NotifFilter) => void;
}) {
  const { p } = usePortal();
  return (
    <div className="filter-bar" role="tablist" aria-label={p.notif.title}>
      {ORDER.map((f) => (
        <button
          key={f}
          role="tab"
          aria-selected={value === f}
          className={`filter-chip ${value === f ? "active" : ""}`}
          onClick={() => onChange(f)}
        >
          {p.notif.filters[f]}
          {f === "unread" && unreadCount > 0 && (
            <span className="filter-count">{unreadCount}</span>
          )}
        </button>
      ))}
    </div>
  );
}
