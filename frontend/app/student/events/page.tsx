"use client";

import { useMemo, useState } from "react";
import { AsyncBoundary, EmptyState, Toast } from "@/components/ui/primitives";
import { EventDetailDrawer } from "@/components/calendar/EventDetailDrawer";
import { useAsync } from "@/lib/useAsync";
import { usePortal } from "@/lib/portalI18n";
import { getStudentCalendar } from "@/lib/api";
import type { CalendarEvent } from "@/lib/portalTypes";
import { formatDate } from "@/lib/format";
import { timeLabel } from "@/lib/calendar";
import { IconCalendar, IconArrow } from "@/components/shell/icons";

type EventFilter = "all" | "workshop" | "seminar" | "club" | "career";
const FILTERS: { key: EventFilter; label: string; match: RegExp }[] = [
  { key: "all", label: "All", match: /.*/ },
  { key: "workshop", label: "Workshops", match: /workshop|lab|hands-on/i },
  { key: "seminar", label: "Seminars", match: /seminar|lecture|talk|guest/i },
  { key: "club", label: "Clubs", match: /club|society|meetup|social/i },
  { key: "career", label: "Career", match: /career|fair|intern|job|employer/i },
];

function PinIcon() {
  return (
    <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor"
      strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0z" />
      <circle cx="12" cy="10" r="3" />
    </svg>
  );
}
function ClockMini() {
  return (
    <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor"
      strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v5l3 2" />
    </svg>
  );
}

function isRecommended(e: CalendarEvent): boolean {
  return /workshop|ai|machine learning|cs|tech|career|data/i.test(`${e.title} ${e.category ?? ""}`);
}

export default function StudentEventsPage() {
  const { p, lang } = usePortal();
  const locale = lang === "vi" ? "vi-VN" : "en-US";
  const cal = useAsync(() => getStudentCalendar(), []);

  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<EventFilter>("all");
  const [selected, setSelected] = useState<CalendarEvent | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  const all = cal.status === "success" ? cal.data : [];

  const events = useMemo(() => {
    const def = FILTERS.find((f) => f.key === filter)!;
    const q = search.trim().toLowerCase();
    return all
      .filter((e) => e.type === "event" || e.type === "reminder")
      .filter((e) => new Date(e.start).getTime() >= Date.now() - 86_400_000)
      .filter((e) => filter === "all" || def.match.test(`${e.title} ${e.category ?? ""}`))
      .filter((e) =>
        !q
          ? true
          : [e.title, e.location, e.category, e.description]
              .filter(Boolean)
              .some((s) => (s as string).toLowerCase().includes(q))
      )
      .sort((a, b) => new Date(a.start).getTime() - new Date(b.start).getTime());
  }, [all, filter, search]);

  const featured = events[0] ?? null;
  const rest = featured ? events.slice(1) : [];

  const register = (e: CalendarEvent) => setToast(`Registered for "${e.title}" (demo).`);

  const dateBadge = (iso: string) => {
    const d = new Date(iso);
    return { mon: d.toLocaleDateString(locale, { month: "short" }), day: d.getDate() };
  };
  const timeRange = (e: CalendarEvent) =>
    e.all_day
      ? "All day"
      : `${timeLabel(e.start, locale)}${e.end ? ` – ${timeLabel(e.end, locale)}` : ""}`;

  return (
    <div className="page-inner">
      <div className="ah-pagehead">
        <div>
          <h1 className="ah-pagehead-title">Events</h1>
          <p className="ah-pagehead-sub">
            Discover academic, career, and campus activities recommended for you.
          </p>
        </div>
      </div>

      <div className="events-toolbar">
        <input
          className="input events-search"
          placeholder="Search events…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          aria-label="Search events"
        />
        <div className="cal-filters" style={{ margin: 0 }}>
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
      </div>

      <AsyncBoundary state={cal} onRetry={cal.reload}>
        {() =>
          events.length === 0 ? (
            <EmptyState
              icon={<IconCalendar size={28} />}
              title="No events found"
              description="Try a different filter or search term."
            />
          ) : (
            <>
              {/* Featured hero */}
              {featured && (
                <div className="events-hero">
                  <div>
                    <span className="events-hero-badge">Featured Event</span>
                    <h2 className="events-hero-title">{featured.title}</h2>
                    {featured.description && (
                      <p className="events-hero-desc">{featured.description}</p>
                    )}
                    <div className="events-hero-meta">
                      <span>{formatDate(featured.start, locale)}</span>
                      <span>{timeRange(featured)}</span>
                      {featured.location && <span>{featured.location}</span>}
                    </div>
                  </div>
                  <div className="events-hero-aside">
                    {featured.category && (
                      <span className="events-hero-stat">{featured.category}</span>
                    )}
                    <button className="events-hero-btn" onClick={() => register(featured)}>
                      Register Now <IconArrow size={15} />
                    </button>
                    <button
                      className="events-hero-stat"
                      style={{ background: "none", border: "none", color: "#fff", cursor: "pointer", textDecoration: "underline", padding: 0 }}
                      onClick={() => setSelected(featured)}
                    >
                      View details
                    </button>
                  </div>
                </div>
              )}

              {/* Upcoming activities grid */}
              <h2 className="events-section-title">Upcoming Activities</h2>
              {rest.length === 0 ? (
                <EmptyState title="No more upcoming activities." />
              ) : (
                <div className="events-grid">
                  {rest.map((e) => {
                    const b = dateBadge(e.start);
                    return (
                      <div key={e.id} className="event-card2">
                        <div className="event-card2-thumb">
                          <IconCalendar size={30} />
                          <div className="event-card2-date">
                            <div className="event-card2-date-mon">{b.mon}</div>
                            <div className="event-card2-date-day">{b.day}</div>
                          </div>
                        </div>
                        <div className="event-card2-body">
                          <div className="event-card2-tags">
                            {e.category && <span className="ah-chip neutral">{e.category}</span>}
                            {isRecommended(e) && (
                              <span className="ah-chip">Recommended</span>
                            )}
                          </div>
                          <div className="event-card2-title">{e.title}</div>
                          <div className="event-card2-meta">
                            <span className="event-card2-row">
                              <ClockMini /> {timeRange(e)}
                            </span>
                            {e.location && (
                              <span className="event-card2-row">
                                <PinIcon /> {e.location}
                              </span>
                            )}
                          </div>
                          <div className="event-card2-actions">
                            <button className="btn btn-primary btn-sm" onClick={() => register(e)}>
                              Register
                            </button>
                            <button className="btn btn-outline btn-sm" onClick={() => setSelected(e)}>
                              Details
                            </button>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </>
          )
        }
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
