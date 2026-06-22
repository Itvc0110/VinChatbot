"use client";

import { useMemo } from "react";
import type { CalendarEvent } from "@/lib/portalTypes";
import { usePortal } from "@/lib/portalI18n";
import {
  isSameMonth,
  isToday,
  monthMatrix,
  weekDays,
  weekdayLabels,
  ymd,
} from "@/lib/calendar";
import { CalendarEventCard } from "./CalendarEventCard";

export type CalendarViewMode = "week" | "month";

function groupByDay(events: CalendarEvent[]): Map<string, CalendarEvent[]> {
  const m = new Map<string, CalendarEvent[]>();
  for (const e of events) {
    const key = ymd(new Date(e.start));
    const arr = m.get(key) ?? [];
    arr.push(e);
    m.set(key, arr);
  }
  for (const arr of m.values()) {
    arr.sort((a, b) => new Date(a.start).getTime() - new Date(b.start).getTime());
  }
  return m;
}

export function CalendarView({
  events,
  view,
  cursor,
  onSelectEvent,
  onSelectDay,
}: {
  events: CalendarEvent[];
  view: CalendarViewMode;
  cursor: Date;
  onSelectEvent: (e: CalendarEvent) => void;
  onSelectDay: (d: Date) => void;
}) {
  const { p, lang } = usePortal();
  const locale = lang === "vi" ? "vi-VN" : "en-US";
  const byDay = useMemo(() => groupByDay(events), [events]);
  const dow = useMemo(() => weekdayLabels(locale), [locale]);

  if (view === "week") {
    const days = weekDays(cursor);
    return (
      <div className="cal-week">
        {days.map((d) => {
          const evs = byDay.get(ymd(d)) ?? [];
          return (
            <div key={ymd(d)} className={`cal-week-col ${isToday(d) ? "is-today" : ""}`}>
              <div className="cal-week-colhead">
                <span className="cal-dow">{d.toLocaleDateString(locale, { weekday: "short" })}</span>
                <span className={`cal-dnum ${isToday(d) ? "today" : ""}`}>{d.getDate()}</span>
              </div>
              <div className="cal-week-events">
                {evs.length === 0 ? (
                  <span className="cal-col-empty" aria-hidden="true">
                    ·
                  </span>
                ) : (
                  evs.map((e) => (
                    <CalendarEventCard key={e.id} event={e} onClick={onSelectEvent} />
                  ))
                )}
              </div>
            </div>
          );
        })}
      </div>
    );
  }

  // Month view
  const matrix = monthMatrix(cursor);
  return (
    <div className="cal-month">
      <div className="cal-month-dow">
        {dow.map((l) => (
          <div key={l} className="cal-dow-cell">
            {l}
          </div>
        ))}
      </div>
      <div className="cal-month-grid">
        {matrix.flat().map((d) => {
          const evs = byDay.get(ymd(d)) ?? [];
          const shown = evs.slice(0, 3);
          const extra = evs.length - shown.length;
          return (
            <div
              key={ymd(d)}
              className={`cal-cell ${isSameMonth(d, cursor) ? "" : "muted"} ${
                isToday(d) ? "is-today" : ""
              }`}
            >
              <div className="cal-cell-num">{d.getDate()}</div>
              <div className="cal-cell-events">
                {shown.map((e) => (
                  <CalendarEventCard key={e.id} event={e} onClick={onSelectEvent} compact />
                ))}
                {extra > 0 && (
                  <button className="cal-more" onClick={() => onSelectDay(d)}>
                    {p.cal.moreEvents(extra)}
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
