"use client";

import { useMemo } from "react";
import type { CalendarEvent } from "@/lib/portalTypes";
import { usePortal } from "@/lib/portalI18n";
import { ymd, timeLabel } from "@/lib/calendar";
import { formatDate } from "@/lib/format";
import { Modal } from "@/components/ui/primitives";

const STR = {
  en: { empty: "Nothing scheduled for this day." },
  vi: { empty: "Không có lịch nào trong ngày này." },
} as const;

// Popup shown when a student clicks a date in the calendar: the full schedule (classes, exams,
// deadlines, events) for that day. Each row opens the existing event detail drawer.
export function DayEventsPopup({
  day,
  events,
  onClose,
  onSelectEvent,
}: {
  day: Date | null;
  events: CalendarEvent[];
  onClose: () => void;
  onSelectEvent: (e: CalendarEvent) => void;
}) {
  const { p, lang } = usePortal();
  const locale = lang === "vi" ? "vi-VN" : "en-US";
  const s = STR[lang];

  const dayEvents = useMemo(() => {
    if (!day) return [];
    const key = ymd(day);
    return events
      .filter((e) => ymd(new Date(e.start)) === key)
      .sort((a, b) => new Date(a.start).getTime() - new Date(b.start).getTime());
  }, [day, events]);

  const title = day ? formatDate(day.toISOString(), locale) : "";

  return (
    <Modal open={!!day} onClose={onClose} title={title} size="md">
      {dayEvents.length === 0 ? (
        <p className="day-pop-empty">{s.empty}</p>
      ) : (
        <ul className="day-pop-list">
          {dayEvents.map((e) => (
            <li key={e.id}>
              <button className="day-pop-row" onClick={() => onSelectEvent(e)}>
                <span className="day-pop-time">
                  {e.all_day ? p.cal.allDay : timeLabel(e.start, locale)}
                </span>
                <span className="day-pop-main">
                  <span className="day-pop-title">{e.title}</span>
                  {[e.location, e.course, e.category].filter(Boolean).length > 0 && (
                    <span className="day-pop-sub">
                      {[e.location, e.course, e.category].filter(Boolean).join(" · ")}
                    </span>
                  )}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </Modal>
  );
}
