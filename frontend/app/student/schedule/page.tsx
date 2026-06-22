"use client";

import { useMemo, useState } from "react";
import {
  AsyncBoundary,
  Card,
  PageHeader,
  EmptyState,
  Badge,
  Toast,
  type BadgeTone,
} from "@/components/ui/primitives";
import { CalendarView, type CalendarViewMode } from "@/components/calendar/CalendarView";
import { EventDetailDrawer } from "@/components/calendar/EventDetailDrawer";
import { useAsync } from "@/lib/useAsync";
import { usePortal } from "@/lib/portalI18n";
import { getStudentCalendar } from "@/lib/api";
import type { CalendarEvent, CalendarEventType } from "@/lib/portalTypes";
import {
  addDays,
  addMonths,
  monthTitle,
  weekTitle,
  timeLabel,
} from "@/lib/calendar";
import { formatDate } from "@/lib/format";
import { IconCalendar } from "@/components/shell/icons";

const EVENT_TONE: Record<CalendarEventType, BadgeTone> = {
  class: "info",
  deadline: "warning",
  exam: "danger",
  event: "success",
  reminder: "gold",
};

const TYPES: CalendarEventType[] = ["class", "deadline", "exam", "event", "reminder"];

function Chevron({ dir }: { dir: "left" | "right" }) {
  return (
    <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor"
      strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d={dir === "left" ? "M15 18l-6-6 6-6" : "M9 18l6-6-6-6"} />
    </svg>
  );
}

export default function StudentCalendarPage() {
  const { p, lang } = usePortal();
  const locale = lang === "vi" ? "vi-VN" : "en-US";
  const cal = useAsync(getStudentCalendar, []);

  const [view, setView] = useState<CalendarViewMode>("month");
  const [cursor, setCursor] = useState<Date>(() => new Date());
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState<CalendarEventType | "all">("all");
  const [selected, setSelected] = useState<CalendarEvent | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  const events = cal.status === "success" ? cal.data : [];

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return events.filter((e) => {
      if (typeFilter !== "all" && e.type !== typeFilter) return false;
      if (!q) return true;
      return [e.title, e.location, e.course, e.category, e.description]
        .filter(Boolean)
        .some((s) => (s as string).toLowerCase().includes(q));
    });
  }, [events, search, typeFilter]);

  const upcoming = useMemo(() => {
    const now = Date.now();
    return filtered
      .filter((e) => new Date(e.start).getTime() >= now)
      .sort((a, b) => new Date(a.start).getTime() - new Date(b.start).getTime())
      .slice(0, 6);
  }, [filtered]);

  const shift = (dir: number) =>
    setCursor((c) => (view === "month" ? addMonths(c, dir) : addDays(c, dir * 7)));

  const title = view === "month" ? monthTitle(cursor, locale) : weekTitle(cursor, locale);

  return (
    <div className="page-inner">
      <PageHeader title={p.cal.title} />

      <div className="cal-toolbar">
        <div className="cal-toolbar-left">
          <button className="btn btn-outline btn-sm" onClick={() => setCursor(new Date())}>
            {p.cal.today}
          </button>
          <div className="cal-nav">
            <button className="icon-btn" onClick={() => shift(-1)} aria-label={p.cal.prev}>
              <Chevron dir="left" />
            </button>
            <button className="icon-btn" onClick={() => shift(1)} aria-label={p.cal.next}>
              <Chevron dir="right" />
            </button>
          </div>
          <span className="cal-title">{title}</span>
        </div>

        <div className="cal-toolbar-right">
          <input
            className="input cal-search"
            placeholder={p.cal.searchPlaceholder}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            aria-label={p.cal.searchPlaceholder}
          />
          <select
            className="select cal-type"
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value as CalendarEventType | "all")}
            aria-label={p.cal.allTypes}
          >
            <option value="all">{p.cal.allTypes}</option>
            {TYPES.map((t) => (
              <option key={t} value={t}>
                {p.enums.eventType[t]}
              </option>
            ))}
          </select>
          <div className="seg" role="group" aria-label="View">
            <button
              className={`seg-opt ${view === "week" ? "active" : ""}`}
              aria-pressed={view === "week"}
              onClick={() => setView("week")}
            >
              {p.cal.week}
            </button>
            <button
              className={`seg-opt ${view === "month" ? "active" : ""}`}
              aria-pressed={view === "month"}
              onClick={() => setView("month")}
            >
              {p.cal.month}
            </button>
          </div>
        </div>
      </div>

      <AsyncBoundary state={cal} onRetry={cal.reload} errorLabel={p.cal.loadError}>
        {() => (
          <div className="cal-layout">
            <Card className="cal-card">
              {filtered.length === 0 ? (
                <EmptyState icon={<IconCalendar size={28} />} title={p.cal.noEvents} />
              ) : (
                <CalendarView
                  events={filtered}
                  view={view}
                  cursor={cursor}
                  onSelectEvent={setSelected}
                  onSelectDay={(d) => {
                    setCursor(d);
                    setView("week");
                  }}
                />
              )}
            </Card>

            <Card className="cal-upcoming">
              <h3 className="section-title" style={{ marginBottom: 12 }}>
                {p.cal.upcoming}
              </h3>
              {upcoming.length === 0 ? (
                <EmptyState title={p.cal.noUpcoming} />
              ) : (
                <div className="upcoming-list">
                  {upcoming.map((e) => (
                    <button key={e.id} className="upcoming-row" onClick={() => setSelected(e)}>
                      <span className={`upcoming-bar ev-${e.type}`} aria-hidden="true" />
                      <span className="upcoming-main">
                        <span className="upcoming-title">{e.title}</span>
                        <span className="upcoming-sub">
                          {formatDate(e.start, locale)}
                          {!e.all_day ? ` · ${timeLabel(e.start, locale)}` : ""}
                        </span>
                      </span>
                      <Badge tone={EVENT_TONE[e.type]}>{p.enums.eventType[e.type]}</Badge>
                    </button>
                  ))}
                </div>
              )}
            </Card>
          </div>
        )}
      </AsyncBoundary>

      <EventDetailDrawer
        event={selected}
        onClose={() => setSelected(null)}
        onAddReminder={() => {
          setToast(p.cal.reminderAdded);
          setSelected(null);
        }}
      />

      {toast && <Toast message={toast} onClose={() => setToast(null)} />}
    </div>
  );
}
