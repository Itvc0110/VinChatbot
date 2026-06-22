"use client";

import type { CalendarEvent } from "@/lib/portalTypes";
import { usePortal } from "@/lib/portalI18n";
import { timeLabel } from "@/lib/calendar";

// A single colored event block. Color is driven by event type (ev-{type} CSS class).
export function CalendarEventCard({
  event,
  onClick,
  compact = false,
}: {
  event: CalendarEvent;
  onClick: (e: CalendarEvent) => void;
  compact?: boolean;
}) {
  const { lang } = usePortal();
  const locale = lang === "vi" ? "vi-VN" : "en-US";
  return (
    <button
      className={`cal-event ev-${event.type} ${compact ? "compact" : ""}`}
      onClick={() => onClick(event)}
      title={event.title}
    >
      {!event.all_day && (
        <span className="cal-event-time">{timeLabel(event.start, locale)}</span>
      )}
      <span className="cal-event-title">{event.title}</span>
    </button>
  );
}
