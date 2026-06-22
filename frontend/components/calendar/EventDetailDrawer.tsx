"use client";

import { useEffect } from "react";
import type { CalendarEvent, CalendarEventType } from "@/lib/portalTypes";
import { Badge, type BadgeTone } from "@/components/ui/primitives";
import { usePortal } from "@/lib/portalI18n";
import { formatDate } from "@/lib/format";
import { timeLabel } from "@/lib/calendar";
import { IconBell, IconExternal } from "@/components/shell/icons";

const EVENT_TONE: Record<CalendarEventType, BadgeTone> = {
  class: "info",
  deadline: "warning",
  exam: "danger",
  event: "success",
  reminder: "gold",
};

export function EventDetailDrawer({
  event,
  onClose,
  onAddReminder,
}: {
  event: CalendarEvent | null;
  onClose: () => void;
  onAddReminder: (e: CalendarEvent) => void;
}) {
  const { p, lang } = usePortal();
  const locale = lang === "vi" ? "vi-VN" : "en-US";
  const open = !!event;

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  const timeText = event
    ? event.all_day
      ? `${formatDate(event.start, locale)} · ${p.cal.allDay}`
      : `${formatDate(event.start, locale)} · ${timeLabel(event.start, locale)}${
          event.end ? `–${timeLabel(event.end, locale)}` : ""
        }`
    : "";

  return (
    <>
      <div
        className={`detail-scrim ${open ? "open" : ""}`}
        onClick={onClose}
        aria-hidden="true"
      />
      <aside className={`detail-drawer ${open ? "open" : ""}`} aria-hidden={!open}>
        {event && (
          <>
            <div className="detail-head">
              <Badge tone={EVENT_TONE[event.type]}>{p.enums.eventType[event.type]}</Badge>
              <button
                className="source-drawer-close"
                onClick={onClose}
                aria-label={p.cal.close}
                title={p.cal.close}
              >
                ✕
              </button>
            </div>
            <div className="detail-body">
              <h3 className="detail-title">{event.title}</h3>
              <dl className="detail-kv">
                <div>
                  <dt>{p.cal.time}</dt>
                  <dd>{timeText}</dd>
                </div>
                {event.location && (
                  <div>
                    <dt>{p.cal.location}</dt>
                    <dd>{event.location}</dd>
                  </div>
                )}
                {event.course && (
                  <div>
                    <dt>{p.cal.course}</dt>
                    <dd>{event.course}</dd>
                  </div>
                )}
                {event.category && (
                  <div>
                    <dt>{p.cal.category}</dt>
                    <dd>{event.category}</dd>
                  </div>
                )}
                {event.description && (
                  <div>
                    <dt>{p.cal.description}</dt>
                    <dd>{event.description}</dd>
                  </div>
                )}
                {event.source_url && (
                  <div>
                    <dt>{p.cal.source}</dt>
                    <dd>
                      <a href={event.source_url} target="_blank" rel="noreferrer">
                        {event.source_title ?? event.source_url} <IconExternal size={12} />
                      </a>
                    </dd>
                  </div>
                )}
              </dl>
              <button className="btn btn-primary" onClick={() => onAddReminder(event)}>
                <IconBell size={15} /> {p.cal.addReminder}
              </button>
            </div>
          </>
        )}
      </aside>
    </>
  );
}
