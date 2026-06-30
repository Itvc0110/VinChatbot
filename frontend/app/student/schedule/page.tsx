"use client";

import { type CSSProperties, useEffect, useMemo, useRef, useState } from "react";
import { AsyncBoundary, Toast } from "@/components/ui/primitives";
import { EventDetailDrawer } from "@/components/calendar/EventDetailDrawer";
import { useAsync } from "@/lib/useAsync";
import { usePortal } from "@/lib/portalI18n";
import { useAuth } from "@/lib/auth";
import { getStudentCalendar, getMonthlySchedule } from "@/lib/api";
import type { AcademicScheduleEvent } from "@/lib/api";
import type { CalendarEvent, CalendarEventType } from "@/lib/portalTypes";
import {
  addDays,
  addMonths,
  isSameMonth,
  isToday,
  monthMatrix,
  startOfWeek,
  timeLabel,
  weekDays,
  ymd,
} from "@/lib/calendar";
import { IconCalendar } from "@/components/shell/icons";

// Map a backend class meeting (GET /schedule/me) onto the calendar's CalendarEvent shape.
// lecture/lab/tutorial/seminar/office_hour render as "class"; exam and deadline keep their type.
function meetingToCalendarEvent(m: AcademicScheduleEvent): CalendarEvent {
  const type: CalendarEvent["type"] =
    m.meeting_type === "exam" ? "exam" : m.meeting_type === "deadline" ? "deadline" : "class";
  const location = [m.room_name, m.building].filter(Boolean).join(", ") || undefined;
  const course = m.section_code ? `${m.course_code} · ${m.section_code}` : m.course_code;
  const description = [
    m.instructor_name ? `Instructor: ${m.instructor_name}` : null,
    m.course_name ? `Course: ${m.course_name}` : null,
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

function monthKeyOf(date: Date): string {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`;
}

type ScheduleViewMode = "week" | "month";
type Lang = "en" | "vi";

type ScheduleCopy = {
  today: string;
  chooseDate: string;
  detailTitle: string;
  loadingSchedule: string;
  noEventsForDay: string;
  noVisibleEvents: string;
  scheduleError: string;
  viewLabel: string;
  prev: string;
  next: string;
  weekPrefix: string;
  period: string;
  allDay: string;
  views: Record<ScheduleViewMode, string>;
  weekdaysShort: string[];
  weekdaysLong: string[];
  fields: {
    time: string;
    location: string;
    lesson: string;
    instructor: string;
  };
};

const STR: Record<Lang, ScheduleCopy> = {
  en: {
    today: "Today",
    chooseDate: "Choose date",
    detailTitle: "Details",
    loadingSchedule: "Loading class schedule...",
    noEventsForDay: "No schedule for the selected day.",
    noVisibleEvents: "No classes scheduled for this period.",
    scheduleError: "Couldn't load your class schedule for this period.",
    viewLabel: "Schedule view",
    prev: "Previous period",
    next: "Next period",
    weekPrefix: "W",
    period: "Period",
    allDay: "All day",
    views: {
      week: "Weekly schedule",
      month: "Monthly schedule",
    },
    weekdaysShort: ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
    weekdaysLong: ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
    fields: {
      time: "Time",
      location: "Location",
      lesson: "Class",
      instructor: "Instructor",
    },
  },
  vi: {
    today: "Hôm nay",
    chooseDate: "Chọn ngày",
    detailTitle: "Thông tin chi tiết",
    loadingSchedule: "Đang tải lịch học...",
    noEventsForDay: "Không có lịch trong ngày đã chọn.",
    noVisibleEvents: "Không có lớp học trong khoảng thời gian này.",
    scheduleError: "Không tải được lịch học trong khoảng thời gian này.",
    viewLabel: "Kiểu lịch",
    prev: "Khoảng trước",
    next: "Khoảng sau",
    weekPrefix: "W",
    period: "Tiết",
    allDay: "Cả ngày",
    views: {
      week: "Lịch tuần",
      month: "Lịch tháng",
    },
    weekdaysShort: ["T2", "T3", "T4", "T5", "T6", "T7", "CN"],
    weekdaysLong: ["Thứ hai", "Thứ ba", "Thứ tư", "Thứ năm", "Thứ sáu", "Thứ bảy", "Chủ nhật"],
    fields: {
      time: "Thời gian",
      location: "Địa điểm",
      lesson: "Bài học",
      instructor: "Giảng viên",
    },
  },
};

const VIEW_KEYS: ScheduleViewMode[] = ["week", "month"];
const TIMETABLE_START_HOUR = 0;
const TIMETABLE_END_HOUR = 24;
const HOUR_HEIGHT = 58;
const TIMETABLE_BODY_HEIGHT = (TIMETABLE_END_HOUR - TIMETABLE_START_HOUR) * HOUR_HEIGHT;
const TIMETABLE_HOURS = Array.from(
  { length: TIMETABLE_END_HOUR - TIMETABLE_START_HOUR + 1 },
  (_, i) => TIMETABLE_START_HOUR + i
);
const MIN_EVENT_HEIGHT = 52;
const NON_OVERLAP_GAP_MINUTES = 15;
const NON_OVERLAP_EVENT_TYPES = new Set<CalendarEventType>(["class", "exam"]);

const PERIODS = [
  { no: 1, start: 6 * 60 + 45, end: 7 * 60 + 30 },
  { no: 2, start: 7 * 60 + 35, end: 8 * 60 + 20 },
  { no: 3, start: 8 * 60 + 30, end: 9 * 60 + 15 },
  { no: 4, start: 9 * 60 + 20, end: 10 * 60 + 5 },
  { no: 5, start: 10 * 60 + 15, end: 11 * 60 },
  { no: 6, start: 11 * 60 + 5, end: 11 * 60 + 50 },
  { no: 7, start: 12 * 60 + 45, end: 13 * 60 + 30 },
  { no: 8, start: 13 * 60 + 35, end: 14 * 60 + 20 },
  { no: 9, start: 14 * 60 + 25, end: 15 * 60 + 10 },
  { no: 10, start: 15 * 60 + 20, end: 16 * 60 + 5 },
  { no: 11, start: 16 * 60 + 10, end: 16 * 60 + 55 },
  { no: 12, start: 17 * 60, end: 17 * 60 + 45 },
];

function Chevron({ dir }: { dir: "left" | "right" | "down" }) {
  const path =
    dir === "left" ? "M15 18l-6-6 6-6" : dir === "right" ? "M9 18l6-6-6-6" : "M6 9l6 6 6-6";
  return (
    <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor"
      strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d={path} />
    </svg>
  );
}

function uniqueEvents(events: CalendarEvent[]): CalendarEvent[] {
  const seen = new Set<string>();
  return events.filter((e) => {
    const key = `${e.type}:${e.id}:${e.start}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function sortEvents(events: CalendarEvent[]): CalendarEvent[] {
  return [...events].sort((a, b) => new Date(a.start).getTime() - new Date(b.start).getTime());
}

function groupByDay(events: CalendarEvent[]): Map<string, CalendarEvent[]> {
  const grouped = new Map<string, CalendarEvent[]>();
  for (const e of events) {
    const key = ymd(new Date(e.start));
    grouped.set(key, [...(grouped.get(key) ?? []), e]);
  }
  for (const [key, value] of grouped) grouped.set(key, sortEvents(value));
  return grouped;
}

function eventsForDay(events: CalendarEvent[], day: Date): CalendarEvent[] {
  const key = ymd(day);
  return sortEvents(events.filter((e) => ymd(new Date(e.start)) === key));
}

function monthKeysForView(cursor: Date, view: ScheduleViewMode): string[] {
  const keys = new Set<string>();
  if (view === "week") {
    weekDays(cursor).forEach((d) => keys.add(monthKeyOf(d)));
  } else {
    monthMatrix(cursor).flat().forEach((d) => keys.add(monthKeyOf(d)));
  }
  keys.add(monthKeyOf(cursor));
  return Array.from(keys).sort();
}

function formatMonthHeading(date: Date, lang: Lang, locale: string): string {
  if (lang === "vi") return `Tháng ${date.getMonth() + 1}, ${date.getFullYear()}`;
  return date.toLocaleDateString(locale, { month: "long", year: "numeric" });
}

function formatWeekDate(date: Date): string {
  return `${date.getDate()}.${date.getMonth() + 1}.${date.getFullYear()}`;
}

function formatHour(hour: number): string {
  return `${hour}:00`;
}

function minutesOfDay(date: Date): number {
  return date.getHours() * 60 + date.getMinutes();
}

function clamp(n: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, n));
}

function isoWeekNumber(date: Date): number {
  const d = new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()));
  const day = d.getUTCDay() || 7;
  d.setUTCDate(d.getUTCDate() + 4 - day);
  const yearStart = new Date(Date.UTC(d.getUTCFullYear(), 0, 1));
  return Math.ceil((((d.getTime() - yearStart.getTime()) / 86_400_000) + 1) / 7);
}

function periodLabel(event: CalendarEvent, s: ScheduleCopy): string | null {
  if (event.all_day || !event.end) return null;
  const startMin = minutesOfDay(new Date(event.start));
  const endMin = minutesOfDay(new Date(event.end));
  const first = PERIODS.find((p) => startMin >= p.start - 8 && startMin <= p.end + 8);
  const last = [...PERIODS].reverse().find((p) => endMin >= p.start - 8 && endMin <= p.end + 12);
  if (!first || !last) return null;
  return `${s.period} ${first.no}${last.no !== first.no ? ` - ${last.no}` : ""}`;
}

function timeRange(event: CalendarEvent, locale: string, s: ScheduleCopy): string {
  if (event.all_day) return s.allDay;
  return `${timeLabel(event.start, locale)}${event.end ? ` - ${timeLabel(event.end, locale)}` : ""}`;
}

function detailTimeLine(event: CalendarEvent, locale: string, s: ScheduleCopy): string {
  const start = new Date(event.start);
  const weekday = s.weekdaysLong[(start.getDay() + 6) % 7];
  const period = periodLabel(event, s);
  return `${weekday}${period ? `, ${period}` : ""} [${timeRange(event, locale, s)}]`;
}

function instructorFrom(event: CalendarEvent): string | undefined {
  return event.description?.match(/Instructor:\s*([^\n]+)/i)?.[1]?.trim();
}

function eventTitle(event: CalendarEvent): string {
  if (event.type === "class" && event.course) {
    return `${event.course.replace(" · ", " - ")} - ${event.title}`;
  }
  return event.title;
}

function eventTone(type: CalendarEventType): string {
  if (type === "class") return "class";
  if (type === "exam") return "exam";
  if (type === "deadline") return "deadline";
  if (type === "reminder") return "reminder";
  return "event";
}

type EventSpan = { start: number; end: number };

function eventSpan(event: CalendarEvent): EventSpan {
  const start = new Date(event.start);
  const end = event.end ? new Date(event.end) : new Date(start.getTime() + 60 * 60 * 1000);
  const startMin = event.all_day ? TIMETABLE_START_HOUR * 60 : minutesOfDay(start);
  const rawEndMin = event.all_day ? startMin + 60 : minutesOfDay(end);
  const endMin = rawEndMin <= startMin ? startMin + 60 : rawEndMin;
  return {
    start: clamp(startMin, TIMETABLE_START_HOUR * 60, TIMETABLE_END_HOUR * 60),
    end: clamp(endMin, TIMETABLE_START_HOUR * 60, TIMETABLE_END_HOUR * 60),
  };
}

function dateAtMinutes(base: Date, minutes: number): Date {
  const next = new Date(base);
  next.setHours(Math.floor(minutes / 60), minutes % 60, 0, 0);
  return next;
}

function shouldSeparateEvent(event: CalendarEvent): boolean {
  return !event.all_day && Boolean(event.end) && NON_OVERLAP_EVENT_TYPES.has(event.type);
}

function eventWithTime(event: CalendarEvent, startMin: number, endMin: number): CalendarEvent {
  const start = new Date(event.start);
  const nextStart = dateAtMinutes(start, startMin);
  const nextEnd = dateAtMinutes(start, endMin);
  if (nextStart.getTime() === start.getTime() && event.end && nextEnd.getTime() === new Date(event.end).getTime()) {
    return event;
  }
  return { ...event, start: nextStart.toISOString(), end: nextEnd.toISOString() };
}

function separateOverlappingTimes(events: CalendarEvent[]): CalendarEvent[] {
  const separated: CalendarEvent[] = [];
  const byDay = groupByDay(events);
  const dayEnd = TIMETABLE_END_HOUR * 60;

  for (const dayEvents of byDay.values()) {
    let nextAvailable = TIMETABLE_START_HOUR * 60;

    for (const event of sortEvents(dayEvents)) {
      if (!shouldSeparateEvent(event)) {
        separated.push(event);
        continue;
      }

      const span = eventSpan(event);
      const duration = Math.max(15, span.end - span.start);
      const start = Math.max(span.start, nextAvailable);
      const end = Math.min(dayEnd, start + duration);
      const safeStart = end > start ? start : Math.max(TIMETABLE_START_HOUR * 60, dayEnd - duration);
      const safeEnd = Math.min(dayEnd, safeStart + duration);

      separated.push(eventWithTime(event, safeStart, safeEnd));
      nextAvailable = Math.min(dayEnd, safeEnd + NON_OVERLAP_GAP_MINUTES);
    }
  }

  return sortEvents(separated);
}

function eventPositionStyle(event: CalendarEvent): CSSProperties {
  const { start, end } = eventSpan(event);
  const top = ((start - TIMETABLE_START_HOUR * 60) / 60) * HOUR_HEIGHT;
  const height = ((end - start) / 60) * HOUR_HEIGHT;
  const safeHeight = Math.max(MIN_EVENT_HEIGHT, height);
  return {
    "--event-top": `${clamp(top, 0, TIMETABLE_BODY_HEIGHT - MIN_EVENT_HEIGHT)}px`,
    "--event-height": `${Math.min(safeHeight, TIMETABLE_BODY_HEIGHT)}px`,
  } as CSSProperties;
}

function defaultSelectedDay(events: CalendarEvent[], cursor: Date): Date {
  const today = new Date();
  const monthEvents = sortEvents(events).filter((e) => isSameMonth(new Date(e.start), cursor));
  const todayEvents = monthEvents.filter((e) => ymd(new Date(e.start)) === ymd(today));
  if (isSameMonth(today, cursor) && todayEvents.length > 0) return today;
  const nextEvent = monthEvents.find((e) => new Date(e.start).getTime() >= today.getTime());
  const first = nextEvent ?? monthEvents[0];
  return first ? new Date(first.start) : new Date(cursor.getFullYear(), cursor.getMonth(), 1);
}

function ScheduleToolbar({
  view,
  cursor,
  s,
  onViewChange,
  onToday,
  onPickDate,
}: {
  view: ScheduleViewMode;
  cursor: Date;
  s: ScheduleCopy;
  onViewChange: (view: ScheduleViewMode) => void;
  onToday: () => void;
  onPickDate: (date: Date) => void;
}) {
  const pickerRef = useRef<HTMLInputElement>(null);
  const openPicker = () => {
    const input = pickerRef.current;
    if (!input) return;
    const picker = input as HTMLInputElement & { showPicker?: () => void };
    if (picker.showPicker) picker.showPicker();
    else input.click();
  };

  return (
    <div className="sched-toolbar">
      <div className="sched-toolbar-left">
        <button className="sched-today-btn" type="button" onClick={onToday}>
          {s.today}
        </button>
        <div className="sched-datepick">
          <button
            className="sched-datepick-btn"
            type="button"
            onClick={openPicker}
            aria-label={s.chooseDate}
            title={s.chooseDate}
          >
            <IconCalendar size={17} />
          </button>
          <input
            ref={pickerRef}
            className="sched-native-date"
            type="date"
            value={ymd(cursor)}
            onChange={(e) => {
              if (!e.target.value) return;
              const [year, month, day] = e.target.value.split("-").map(Number);
              onPickDate(new Date(year, month - 1, day));
            }}
            aria-label={s.chooseDate}
          />
        </div>
      </div>

      <label className="sched-view-select-wrap">
        <span className="sr-only">{s.viewLabel}</span>
        <select
          className="sched-view-select"
          value={view}
          onChange={(e) => onViewChange(e.target.value as ScheduleViewMode)}
          aria-label={s.viewLabel}
        >
          {VIEW_KEYS.map((key) => (
            <option key={key} value={key}>
              {s.views[key]}
            </option>
          ))}
        </select>
        <Chevron dir="down" />
      </label>
    </div>
  );
}

function MonthSchedule({
  cursor,
  selectedDay,
  events,
  locale,
  lang,
  s,
  onShift,
  onSelectDay,
  onSelectEvent,
}: {
  cursor: Date;
  selectedDay: Date;
  events: CalendarEvent[];
  locale: string;
  lang: Lang;
  s: ScheduleCopy;
  onShift: (dir: number) => void;
  onSelectDay: (day: Date) => void;
  onSelectEvent: (event: CalendarEvent) => void;
}) {
  const matrix = monthMatrix(cursor);
  const byDay = useMemo(() => groupByDay(events), [events]);
  const detailEvents = useMemo(() => eventsForDay(events, selectedDay), [events, selectedDay]);

  return (
    <section className="sched-month-shell" aria-label={s.views.month}>
      <div className="sched-month-calendar">
        <div className="sched-month-head">
          <button className="sched-round-btn" type="button" onClick={() => onShift(-1)} aria-label={s.prev}>
            <Chevron dir="left" />
          </button>
          <h2 className="sched-month-title">{formatMonthHeading(cursor, lang, locale)}</h2>
          <button className="sched-round-btn" type="button" onClick={() => onShift(1)} aria-label={s.next}>
            <Chevron dir="right" />
          </button>
        </div>

        <div className="sched-month-dow">
          {s.weekdaysShort.map((day) => (
            <div key={day}>{day}</div>
          ))}
        </div>

        <div className="sched-month-grid">
          {matrix.flat().map((day) => {
            const key = ymd(day);
            const dayEvents = byDay.get(key) ?? [];
            const selected = ymd(selectedDay) === key;
            return (
              <button
                key={key}
                className={`sched-month-day ${!isSameMonth(day, cursor) ? "muted" : ""} ${
                  selected ? "selected" : ""
                } ${isToday(day) ? "today" : ""}`}
                type="button"
                onClick={() => onSelectDay(day)}
                aria-pressed={selected}
              >
                <span className="sched-month-num">{day.getDate()}</span>
                <span className="sched-month-dots" aria-hidden="true">
                  {dayEvents.slice(0, 4).map((event) => (
                    <span key={`${event.id}-${event.start}`} className={`sched-month-dot ${eventTone(event.type)}`} />
                  ))}
                </span>
              </button>
            );
          })}
        </div>
      </div>

      <div className="sched-month-detail">
        <h2 className="sched-detail-heading">{s.detailTitle}</h2>
        <div className="sched-detail-list">
          {detailEvents.length === 0 ? (
            <div className="sched-detail-empty">{s.noEventsForDay}</div>
          ) : (
            detailEvents.map((event) => (
              <button
                key={`${event.id}-${event.start}`}
                className={`sched-detail-item tone-${eventTone(event.type)}`}
                type="button"
                onClick={() => onSelectEvent(event)}
              >
                <span className="sched-detail-times">
                  <span>{event.all_day ? s.allDay : timeLabel(event.start, locale)}</span>
                  {event.end && <span>{timeLabel(event.end, locale)}</span>}
                </span>
                <span className="sched-detail-rule" aria-hidden="true" />
                <span className="sched-detail-main">
                  <span className="sched-detail-title">{eventTitle(event)}</span>
                  <span className="sched-detail-row">
                    <strong>{s.fields.time}:</strong> {detailTimeLine(event, locale, s)}
                  </span>
                  {event.location && (
                    <span className="sched-detail-row">
                      <strong>{s.fields.location}:</strong> {event.location}
                    </span>
                  )}
                  {event.course && (
                    <span className="sched-detail-row">
                      <strong>{s.fields.lesson}:</strong> {event.course}
                    </span>
                  )}
                  {instructorFrom(event) && (
                    <span className="sched-detail-row">
                      <strong>{s.fields.instructor}:</strong>{" "}
                      <span className="sched-linklike">{instructorFrom(event)}</span>
                    </span>
                  )}
                </span>
              </button>
            ))
          )}
        </div>
      </div>
    </section>
  );
}

function WeekSchedule({
  cursor,
  events,
  locale,
  s,
  onShift,
  onSelectEvent,
}: {
  cursor: Date;
  events: CalendarEvent[];
  locale: string;
  s: ScheduleCopy;
  onShift: (dir: number) => void;
  onSelectEvent: (event: CalendarEvent) => void;
}) {
  const days = weekDays(cursor);
  const weekStart = startOfWeek(cursor);
  const byDay = useMemo(() => groupByDay(events), [events]);
  const scrollRef = useRef<HTMLElement>(null);

  useEffect(() => {
    const target = Math.max(0, (6 - TIMETABLE_START_HOUR) * HOUR_HEIGHT);
    scrollRef.current?.scrollTo({ top: target });
  }, [cursor]);

  return (
    <section ref={scrollRef} className="sched-week-scroll" aria-label={s.views.week}>
      <div
        className="sched-week-grid"
        style={
          {
            "--week-body-height": `${TIMETABLE_BODY_HEIGHT}px`,
            "--hour-height": `${HOUR_HEIGHT}px`,
          } as CSSProperties
        }
      >
        <div className="sched-week-nav">
          <button className="sched-week-nav-btn" type="button" onClick={() => onShift(-1)} aria-label={s.prev}>
            <Chevron dir="left" />
          </button>
          <span>
            {s.weekPrefix}{isoWeekNumber(weekStart)} - {weekStart.getFullYear()}
          </span>
          <button className="sched-week-nav-btn" type="button" onClick={() => onShift(1)} aria-label={s.next}>
            <Chevron dir="right" />
          </button>
        </div>

        {days.map((day) => (
          <div key={ymd(day)} className={`sched-week-head ${isToday(day) ? "today" : ""}`}>
            <span>{s.weekdaysLong[(day.getDay() + 6) % 7]}</span>
            <strong>{formatWeekDate(day)}</strong>
          </div>
        ))}

        <div className="sched-time-rail">
          {TIMETABLE_HOURS.map((hour, index) => (
            <span
              key={hour}
              className="sched-hour-label"
              style={{ top: `${index * HOUR_HEIGHT - 8}px` }}
            >
              {formatHour(hour)}
            </span>
          ))}
        </div>

        {days.map((day) => {
          const dayEvents = byDay.get(ymd(day)) ?? [];
          return (
            <div key={ymd(day)} className="sched-week-day">
              {dayEvents.map((event) => (
                <button
                  key={`${event.id}-${event.start}`}
                  className={`sched-week-event tone-${eventTone(event.type)}`}
                  style={eventPositionStyle(event)}
                  type="button"
                  onClick={() => onSelectEvent(event)}
                >
                  <span className="sched-week-event-title">{eventTitle(event)}</span>
                  <span className="sched-week-event-meta">{timeRange(event, locale, s)}</span>
                  {event.location && <span className="sched-week-event-meta">{event.location}</span>}
                  {instructorFrom(event) && (
                    <span className="sched-week-event-meta">{instructorFrom(event)}</span>
                  )}
                </button>
              ))}
            </div>
          );
        })}
      </div>
    </section>
  );
}

export default function StudentCalendarPage() {
  const { p, lang } = usePortal();
  const { token } = useAuth();
  const s = STR[lang];
  const locale = lang === "vi" ? "vi-VN" : "en-US";
  const cal = useAsync(() => getStudentCalendar(), [token]);

  const [view, setView] = useState<ScheduleViewMode>("week");
  const [cursor, setCursor] = useState<Date>(() => new Date());
  const [selectedDay, setSelectedDay] = useState<Date>(() => new Date());
  const [manualDayPick, setManualDayPick] = useState(false);
  const [selected, setSelected] = useState<CalendarEvent | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  const visibleMonthKeys = useMemo(() => monthKeysForView(cursor, view), [cursor, view]);
  const visibleMonthKey = visibleMonthKeys.join(",");

  const sched = useAsync(
    async () => {
      const months = await Promise.all(visibleMonthKeys.map((month) => getMonthlySchedule(month)));
      return uniqueEvents(months.flat().map(meetingToCalendarEvent));
    },
    [token, visibleMonthKey]
  );

  useEffect(() => {
    const today = new Date();
    setCursor(today);
    setSelectedDay(today);
    setManualDayPick(false);
    setSelected(null);
  }, [token]);

  const calEvents = useMemo(
    () => (cal.status === "success" ? cal.data.filter((e) => e.type !== "class") : []),
    [cal]
  );
  const academicEvents = useMemo(
    () => (sched.status === "success" ? sched.data : []),
    [sched]
  );
  const events = useMemo(
    () => separateOverlappingTimes(uniqueEvents([...calEvents, ...academicEvents])),
    [calEvents, academicEvents]
  );

  useEffect(() => {
    if (view !== "month") return;
    if (manualDayPick && isSameMonth(selectedDay, cursor)) return;
    const next = defaultSelectedDay(events, cursor);
    if (ymd(next) !== ymd(selectedDay)) setSelectedDay(next);
  }, [cursor, events, manualDayPick, selectedDay, view]);

  const visibleEvents = useMemo(() => {
    if (view === "month") {
      return events.filter((event) => {
        const day = new Date(event.start);
        return monthMatrix(cursor).flat().some((d) => ymd(d) === ymd(day));
      });
    }
    const start = startOfWeek(cursor).getTime();
    const end = addDays(startOfWeek(cursor), 7).getTime();
    return events.filter((event) => {
      const t = new Date(event.start).getTime();
      return t >= start && t < end;
    });
  }, [cursor, events, view]);

  const shift = (dir: number) => {
    setManualDayPick(false);
    setCursor((current) => (view === "month" ? addMonths(current, dir) : addDays(current, dir * 7)));
  };

  const goToday = () => {
    const today = new Date();
    setCursor(today);
    setSelectedDay(today);
    setManualDayPick(true);
  };

  const pickDate = (date: Date, manual = true) => {
    setCursor(date);
    setSelectedDay(date);
    setManualDayPick(manual);
  };

  const changeView = (next: ScheduleViewMode) => {
    setManualDayPick(false);
    setView(next);
  };

  return (
    <div className="page-inner schedule-page">
      <ScheduleToolbar
        view={view}
        cursor={cursor}
        s={s}
        onViewChange={changeView}
        onToday={goToday}
        onPickDate={pickDate}
      />

      <AsyncBoundary state={cal} onRetry={cal.reload} errorLabel={p.cal.loadError}>
        {() => (
          <>
            {sched.status === "loading" && (
              <div className="sched-status" role="status">{s.loadingSchedule}</div>
            )}
            {sched.status === "error" && (
              <div className="sched-status danger" role="status">{s.scheduleError}</div>
            )}
            {sched.status === "success" && academicEvents.length === 0 && (
              <div className="sched-status" role="status">{s.noVisibleEvents}</div>
            )}

            {view === "month" ? (
              <MonthSchedule
                cursor={cursor}
                selectedDay={selectedDay}
                events={visibleEvents}
                locale={locale}
                lang={lang}
                s={s}
                onShift={shift}
                onSelectDay={(day) => pickDate(day, true)}
                onSelectEvent={setSelected}
              />
            ) : (
              <WeekSchedule
                cursor={cursor}
                events={visibleEvents}
                locale={locale}
                s={s}
                onShift={shift}
                onSelectEvent={setSelected}
              />
            )}
          </>
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
