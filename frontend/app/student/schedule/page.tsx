"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { AsyncBoundary, Toast } from "@/components/ui/primitives";
import { CalendarView } from "@/components/calendar/CalendarView";
import { EventDetailDrawer } from "@/components/calendar/EventDetailDrawer";
import { useAsync } from "@/lib/useAsync";
import { usePortal } from "@/lib/portalI18n";
import { getStudentCalendar } from "@/lib/api";
import type { CalendarEvent } from "@/lib/portalTypes";
import { addDays, addMonths, monthTitle, weekTitle, timeLabel, ymd } from "@/lib/calendar";
import { formatDate } from "@/lib/format";

type ViewMode = "day" | "week" | "month" | "list";
type CalFilter = "all" | "class" | "exam" | "assignment" | "tuition" | "event";

const FILTERS: { key: CalFilter; label: string }[] = [
  { key: "all", label: "All" },
  { key: "class", label: "Classes" },
  { key: "exam", label: "Exams" },
  { key: "assignment", label: "Assignment Deadlines" },
  { key: "tuition", label: "Tuition Deadlines" },
  { key: "event", label: "Events" },
];

const VIEWS: { key: ViewMode; label: string }[] = [
  { key: "day", label: "Day" },
  { key: "week", label: "Week" },
  { key: "month", label: "Month" },
  { key: "list", label: "List" },
];

function isTuition(e: CalendarEvent): boolean {
  return /tuition|fee|học phí|hoc phi/i.test(`${e.title} ${e.category ?? ""}`);
}
function matchFilter(e: CalendarEvent, f: CalFilter): boolean {
  switch (f) {
    case "all":
      return true;
    case "class":
      return e.type === "class";
    case "exam":
      return e.type === "exam";
    case "event":
      return e.type === "event" || e.type === "reminder";
    case "assignment":
      return e.type === "deadline" && !isTuition(e);
    case "tuition":
      return e.type === "deadline" && isTuition(e);
  }
}

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
  const router = useRouter();
  const cal = useAsync(() => getStudentCalendar(), []);

  const [view, setView] = useState<ViewMode>("month");
  const [cursor, setCursor] = useState<Date>(() => new Date());
  const [filter, setFilter] = useState<CalFilter>("all");
  const [selected, setSelected] = useState<CalendarEvent | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  const events = cal.status === "success" ? cal.data : [];
  const filtered = useMemo(
    () => events.filter((e) => matchFilter(e, filter)),
    [events, filter]
  );

  const todays = useMemo(() => {
    const key = ymd(new Date());
    return filtered
      .filter((e) => ymd(new Date(e.start)) === key)
      .sort((a, b) => new Date(a.start).getTime() - new Date(b.start).getTime());
  }, [filtered]);

  const dayEvents = useMemo(() => {
    const key = ymd(cursor);
    return filtered
      .filter((e) => ymd(new Date(e.start)) === key)
      .sort((a, b) => new Date(a.start).getTime() - new Date(b.start).getTime());
  }, [filtered, cursor]);

  const listEvents = useMemo(
    () =>
      [...filtered]
        .filter((e) => new Date(e.start).getTime() >= Date.now() - 86_400_000)
        .sort((a, b) => new Date(a.start).getTime() - new Date(b.start).getTime())
        .slice(0, 40),
    [filtered]
  );

  const shift = (dir: number) => {
    if (view === "month") setCursor((c) => addMonths(c, dir));
    else if (view === "week") setCursor((c) => addDays(c, dir * 7));
    else if (view === "day") setCursor((c) => addDays(c, dir));
  };

  const period =
    view === "month"
      ? monthTitle(cursor, locale)
      : view === "week"
      ? weekTitle(cursor, locale)
      : view === "day"
      ? formatDate(cursor.toISOString(), locale)
      : "Upcoming";

  const evLine = (e: CalendarEvent) =>
    [
      e.all_day
        ? "All day"
        : `${timeLabel(e.start, locale)}${e.end ? ` – ${timeLabel(e.end, locale)}` : ""}`,
      e.location,
      e.course,
    ]
      .filter(Boolean)
      .join(" · ");

  return (
    <div className="page-inner">
      <div className="ah-pagehead">
        <div>
          <h1 className="ah-pagehead-title">Academic Calendar</h1>
          <p className="ah-pagehead-sub">Manage your schedule, exams, and personal events.</p>
        </div>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <button
            className="btn btn-outline"
            onClick={() => setToast("Calendar sync link copied (demo).")}
          >
            Sync Calendar
          </button>
          <button
            className="btn btn-outline"
            onClick={() =>
              router.push(
                `/student/chat?q=${encodeURIComponent("What's on my schedule this week?")}`
              )
            }
          >
            Ask Vinnie about my week
          </button>
        </div>
      </div>

      <div className="cal-toolbar-ah">
        <div className="seg" role="group" aria-label="View">
          {VIEWS.map((v) => (
            <button
              key={v.key}
              className={`seg-opt ${view === v.key ? "active" : ""}`}
              aria-pressed={view === v.key}
              onClick={() => setView(v.key)}
            >
              {v.label}
            </button>
          ))}
        </div>
        <button className="btn btn-outline btn-sm" onClick={() => setCursor(new Date())}>
          {p.cal.today}
        </button>
        {view !== "list" && (
          <div className="cal-nav-ah">
            <button className="icon-btn" onClick={() => shift(-1)} aria-label={p.cal.prev}>
              <Chevron dir="left" />
            </button>
            <button className="icon-btn" onClick={() => shift(1)} aria-label={p.cal.next}>
              <Chevron dir="right" />
            </button>
          </div>
        )}
        <span className="cal-period">{period}</span>
      </div>

      <div className="cal-filters">
        {FILTERS.map((f) => (
          <button
            key={f.key}
            className={`cal-filter-chip ${filter === f.key ? "active" : ""}`}
            onClick={() => setFilter(f.key)}
          >
            {f.label}
          </button>
        ))}
      </div>

      <AsyncBoundary state={cal} onRetry={cal.reload} errorLabel={p.cal.loadError}>
        {() => (
          <div className="cal-layout-ah">
            <div className="cal-main-card">
              {view === "month" || view === "week" ? (
                <CalendarView
                  events={filtered}
                  view={view}
                  cursor={cursor}
                  onSelectEvent={setSelected}
                  onSelectDay={(d) => {
                    setCursor(d);
                    setView("day");
                  }}
                />
              ) : (
                <div className="cal-list">
                  {(view === "day" ? dayEvents : listEvents).length === 0 ? (
                    <div className="cal-empty">{p.cal.noEvents}</div>
                  ) : (
                    (view === "day" ? dayEvents : listEvents).map((e) => (
                      <button
                        key={e.id}
                        className="cal-list-row"
                        onClick={() => setSelected(e)}
                      >
                        <span className="cal-list-time">
                          {view === "list" ? formatDate(e.start, locale) : timeLabel(e.start, locale)}
                        </span>
                        <span className="cal-list-main">
                          <span className="cal-list-title">{e.title}</span>
                          <span className="cal-list-sub">{evLine(e)}</span>
                        </span>
                      </button>
                    ))
                  )}
                </div>
              )}
            </div>

            <div className="rail-card">
              <h3 className="rail-title">{p.todaySchedule}</h3>
              {todays.length === 0 ? (
                <p className="rail-empty">{p.dash.noClasses}</p>
              ) : (
                todays.map((e) => (
                  <div key={e.id} className="rail-sched-row">
                    <span className="rail-time">
                      {e.all_day ? "—" : timeLabel(e.start, locale)}
                    </span>
                    <div className="rail-sched-main">
                      <div className="rail-sched-title">{e.title}</div>
                      <div className="rail-sched-sub">
                        {[e.category, e.location].filter(Boolean).join(" · ")}
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
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
