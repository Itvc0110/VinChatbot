"use client";

import { useEffect, useMemo, useState } from "react";
import { AsyncBoundary, Toast } from "@/components/ui/primitives";
import { CalendarView } from "@/components/calendar/CalendarView";
import { EventDetailDrawer } from "@/components/calendar/EventDetailDrawer";
import { DayEventsPopup } from "@/components/calendar/DayEventsPopup";
import { useAsync } from "@/lib/useAsync";
import { usePortal } from "@/lib/portalI18n";
import { useAuth } from "@/lib/auth";
import { getStudentCalendar, getMonthlySchedule } from "@/lib/api";
import type { AcademicScheduleEvent } from "@/lib/api";
import type { CalendarEvent } from "@/lib/portalTypes";
import { addDays, addMonths, monthTitle, weekTitle, timeLabel, ymd } from "@/lib/calendar";
import { formatDate } from "@/lib/format";

// Map a backend class meeting (GET /schedule/me) onto the calendar's CalendarEvent shape.
// lecture/lab/tutorial/seminar/office_hour render as "class"; exam and deadline keep their type.
function meetingToCalendarEvent(m: AcademicScheduleEvent): CalendarEvent {
  const type: CalendarEvent["type"] =
    m.meeting_type === "exam" ? "exam" : m.meeting_type === "deadline" ? "deadline" : "class";
  const location = [m.room_name, m.building].filter(Boolean).join(", ") || undefined;
  const course = m.section_code ? `${m.course_code} · ${m.section_code}` : m.course_code;
  const description = [
    m.instructor_name ? `Instructor: ${m.instructor_name}` : null,
    m.note || null,
  ]
    .filter(Boolean)
    .join("\n");
  return {
    id: m.id,
    type,
    title: m.title || m.course_name,
    start: m.start_at,
    end: m.end_at,
    location,
    course,
    category: m.meeting_type,
    description: description || undefined,
  };
}

// "YYYY-MM" for the month the calendar cursor is currently showing (local wall-clock).
function monthKeyOf(date: Date): string {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`;
}

type ViewMode = "day" | "week" | "month" | "list";
type CalFilter = "all" | "class" | "exam" | "assignment" | "tuition" | "event";
type Lang = "en" | "vi";

const FILTER_KEYS: CalFilter[] = ["all", "class", "exam", "assignment", "tuition", "event"];
const VIEW_KEYS: ViewMode[] = ["day", "week", "month", "list"];

const STR: Record<Lang, {
  title: string;
  subtitle: string;
  syncCalendar: string;
  syncToast: string;
  viewLabel: string;
  upcoming: string;
  allDay: string;
  noClassesThisMonth: string;
  scheduleError: string;
  filters: Record<CalFilter, string>;
  views: Record<ViewMode, string>;
}> = {
  en: {
    title: "Academic Calendar",
    subtitle: "Manage your schedule, exams, and personal events.",
    syncCalendar: "Sync Calendar",
    syncToast: "Calendar sync link copied (demo).",
    viewLabel: "View",
    upcoming: "Upcoming",
    allDay: "All day",
    noClassesThisMonth: "No classes scheduled this month.",
    scheduleError: "Couldn't load your class schedule for this month.",
    filters: {
      all: "All",
      class: "Classes",
      exam: "Exams",
      assignment: "Assignment Deadlines",
      tuition: "Tuition Deadlines",
      event: "Events",
    },
    views: { day: "Day", week: "Week", month: "Month", list: "List" },
  },
  vi: {
    title: "Lịch học vụ",
    subtitle: "Quản lý lịch học, lịch thi và sự kiện cá nhân.",
    syncCalendar: "Đồng bộ lịch",
    syncToast: "Đã sao chép liên kết đồng bộ lịch (demo).",
    viewLabel: "Xem",
    upcoming: "Sắp tới",
    allDay: "Cả ngày",
    noClassesThisMonth: "Không có lớp học nào trong tháng này.",
    scheduleError: "Không tải được lịch học của tháng này.",
    filters: {
      all: "Tất cả",
      class: "Lớp học",
      exam: "Kỳ thi",
      assignment: "Hạn nộp bài tập",
      tuition: "Hạn học phí",
      event: "Sự kiện",
    },
    views: { day: "Ngày", week: "Tuần", month: "Tháng", list: "Danh sách" },
  },
};

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
  const { token } = useAuth();
  const s = STR[lang];
  const locale = lang === "vi" ? "vi-VN" : "en-US";
  const cal = useAsync(() => getStudentCalendar(), [token]);

  const [view, setView] = useState<ViewMode>("month");
  const [cursor, setCursor] = useState<Date>(() => new Date());

  // Phase 13C: real class meetings for the visible month come from GET /schedule/me?month=YYYY-MM.
  // They replace the legacy recurring-schedule class events; deadlines/events still come from cal.
  const monthKey = monthKeyOf(cursor);
  const sched = useAsync(() => getMonthlySchedule(monthKey), [token, monthKey]);
  const [filter, setFilter] = useState<CalFilter>("all");
  const [selected, setSelected] = useState<CalendarEvent | null>(null);
  const [popupDay, setPopupDay] = useState<Date | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  // Always open on the CURRENT month (today). We deliberately do NOT jump the cursor to the
  // nearest month that happens to contain demo events — the student expects "this month" first
  // and can navigate with the arrows / Today button.
  useEffect(() => {
    setCursor(new Date());
    setSelected(null);
    setPopupDay(null);
  }, [token]);

  // Non-class events (deadlines, exams-as-deadlines, events) from the legacy calendar source.
  // Class events are dropped here because GET /schedule/me now owns dated class meetings.
  const calEvents = useMemo(
    () => (cal.status === "success" ? cal.data.filter((e) => e.type !== "class") : []),
    [cal]
  );
  const academicEvents = useMemo(
    () => (sched.status === "success" ? sched.data.map(meetingToCalendarEvent) : []),
    [sched]
  );
  const events = useMemo(
    () => [...calEvents, ...academicEvents],
    [calEvents, academicEvents]
  );

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
      : s.upcoming;

  const evLine = (e: CalendarEvent) =>
    [
      e.all_day
        ? s.allDay
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
          <h1 className="ah-pagehead-title">{s.title}</h1>
          <p className="ah-pagehead-sub">{s.subtitle}</p>
        </div>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <button
            className="btn btn-outline"
            onClick={() => setToast(s.syncToast)}
          >
            {s.syncCalendar}
          </button>
        </div>
      </div>

      <div className="cal-toolbar-ah">
        <div className="seg" role="group" aria-label={s.viewLabel}>
          {VIEW_KEYS.map((v) => (
            <button
              key={v}
              className={`seg-opt ${view === v ? "active" : ""}`}
              aria-pressed={view === v}
              onClick={() => setView(v)}
            >
              {s.views[v]}
            </button>
          ))}
        </div>
        <button
          className="btn btn-outline btn-sm"
          onClick={() => setCursor(new Date())}
        >
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
        {FILTER_KEYS.map((f) => (
          <button
            key={f}
            className={`cal-filter-chip ${filter === f ? "active" : ""}`}
            onClick={() => setFilter(f)}
          >
            {s.filters[f]}
          </button>
        ))}
      </div>

      <AsyncBoundary state={cal} onRetry={cal.reload} errorLabel={p.cal.loadError}>
        {() => (
          <div className="cal-layout-ah">
            <div className="cal-main-card">
              {sched.status === "error" ? (
                <div className="cal-empty" role="status">{s.scheduleError}</div>
              ) : sched.status === "success" && academicEvents.length === 0 ? (
                <div className="cal-empty" role="status">{s.noClassesThisMonth}</div>
              ) : null}
              {view === "month" || view === "week" ? (
                <CalendarView
                  events={filtered}
                  view={view}
                  cursor={cursor}
                  onSelectEvent={setSelected}
                  onSelectDay={(d) => setPopupDay(d)}
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

      <DayEventsPopup
        day={popupDay}
        events={filtered}
        onClose={() => setPopupDay(null)}
        onSelectEvent={(e) => {
          setSelected(e);
          setPopupDay(null);
        }}
      />

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
