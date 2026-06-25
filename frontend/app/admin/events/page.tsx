"use client";

import { useMemo, useState } from "react";
import { Toast } from "@/components/ui/primitives";
import { IconCalendar, IconCheck } from "@/components/shell/icons";

// Admin Campus Events management (Phase 4, new route). Demo-only: there is no events backend, so the
// list is local demo state (create/edit/publish/archive mutate local state). No live API touched.

type EventStatus = "draft" | "scheduled" | "published" | "closed";
interface AdminEvent {
  id: string; title: string; date: string; time: string; location: string;
  category: string; audience: string; status: EventStatus; registered: number; capacity: number;
}
const STATUS_CHIP: Record<EventStatus, string> = { draft: "neutral", scheduled: "info", published: "success", closed: "warning" };
const STATUS_LABEL: Record<EventStatus, string> = { draft: "Draft", scheduled: "Scheduled", published: "Published", closed: "Closed" };
const CATEGORIES = ["Academic", "Career", "Social", "Workshop", "Sports"];
const AUDIENCES = ["All Students", "Final-year", "CS, Data Science", "Freshmen"];

const SEED: AdminEvent[] = [
  { id: "e1", title: "Annual Career Fair 2024", date: "2026-07-15", time: "10:00 AM – 3:00 PM", location: "Main Campus Expo Center", category: "Career", audience: "All Students", status: "published", registered: 1240, capacity: 2000 },
  { id: "e2", title: "Guest Lecture: AI in Healthcare", date: "2026-07-18", time: "2:00 PM – 4:00 PM", location: "Hall B, Science Building", category: "Academic", audience: "CS, Data Science", status: "scheduled", registered: 84, capacity: 200 },
  { id: "e3", title: "Lunar New Year Celebration", date: "2026-02-10", time: "6:00 PM – 9:00 PM", location: "Main Plaza", category: "Social", audience: "All Students", status: "closed", registered: 540, capacity: 540 },
  { id: "e4", title: "Resume Workshop", date: "2026-07-22", time: "1:00 PM – 3:00 PM", location: "Innovation Lab 3B", category: "Workshop", audience: "Final-year", status: "draft", registered: 0, capacity: 60 },
  { id: "e5", title: "Library Research Skills", date: "2026-07-25", time: "11:00 AM – 12:30 PM", location: "Learning Commons", category: "Academic", audience: "All Students", status: "published", registered: 96, capacity: 120 },
];

const BLANK: AdminEvent = { id: "", title: "", date: "", time: "", location: "", category: "Academic", audience: "All Students", status: "draft", registered: 0, capacity: 100 };

function Stat({ value, label }: { value: React.ReactNode; label: string }) {
  return (
    <div className="astat">
      <div className="astat-top"><span className="astat-icon"><IconCalendar size={18} /></span></div>
      <div className="astat-value">{value}</div>
      <div className="astat-label">{label}</div>
    </div>
  );
}

export default function AdminEventsPage() {
  const [events, setEvents] = useState<AdminEvent[]>(SEED);
  const [search, setSearch] = useState("");
  const [statusF, setStatusF] = useState<EventStatus | "all">("all");
  const [draft, setDraft] = useState<AdminEvent | null>(null); // open drawer when set
  const [toast, setToast] = useState<string | null>(null);

  const counts = {
    total: events.length,
    published: events.filter((e) => e.status === "published").length,
    drafts: events.filter((e) => e.status === "draft").length,
    regs: events.reduce((n, e) => n + e.registered, 0),
  };

  const visible = useMemo(
    () =>
      events
        .filter((e) => statusF === "all" || e.status === statusF)
        .filter((e) => {
          const q = search.trim().toLowerCase();
          return !q || [e.title, e.location, e.category, e.audience].some((s) => s.toLowerCase().includes(q));
        }),
    [events, statusF, search]
  );

  const setStatus = (id: string, status: EventStatus, msg: string) => {
    setEvents((cur) => cur.map((e) => (e.id === id ? { ...e, status } : e)));
    setToast(msg);
  };

  const save = () => {
    if (!draft) return;
    if (draft.id) {
      setEvents((cur) => cur.map((e) => (e.id === draft.id ? draft : e)));
      setToast("Event updated.");
    } else {
      setEvents((cur) => [{ ...draft, id: `e${cur.length + 1}-${Date.now() % 10000}` }, ...cur]);
      setToast("Event created.");
    }
    setDraft(null);
  };

  return (
    <div className="page-inner">
      <div className="aev-stats">
        <Stat value={counts.total} label="Total events" />
        <Stat value={counts.published} label="Published" />
        <Stat value={counts.drafts} label="Drafts" />
        <Stat value={counts.regs.toLocaleString()} label="Total registrations" />
      </div>

      <div className="aev-toolbar">
        <input className="input" placeholder="Search events…" value={search} onChange={(e) => setSearch(e.target.value)} aria-label="Search events" />
        <select className="select" value={statusF} onChange={(e) => setStatusF(e.target.value as EventStatus | "all")} aria-label="Status filter">
          <option value="all">All status</option>
          {(["draft", "scheduled", "published", "closed"] as EventStatus[]).map((s) => (
            <option key={s} value={s}>{STATUS_LABEL[s]}</option>
          ))}
        </select>
        <div className="aev-toolbar-actions">
          <button className="ah-btn-red" onClick={() => setDraft({ ...BLANK })}>+ Create Event</button>
        </div>
      </div>

      {visible.length === 0 ? (
        <div className="acard" style={{ textAlign: "center", color: "var(--ah-muted)", padding: 40 }}>No events match.</div>
      ) : (
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr><th>Event</th><th>Category</th><th>Audience</th><th>Status</th><th>Registrations</th><th>Actions</th></tr>
            </thead>
            <tbody>
              {visible.map((e) => {
                const pct = e.capacity > 0 ? Math.round((e.registered / e.capacity) * 100) : 0;
                return (
                  <tr key={e.id}>
                    <td>
                      <div className="td-strong">{e.title}</div>
                      <div className="td-sub">{e.date} · {e.time} · {e.location}</div>
                    </td>
                    <td><span className="ah-chip neutral">{e.category}</span></td>
                    <td className="td-sub">{e.audience}</td>
                    <td><span className={`ah-chip ${STATUS_CHIP[e.status]}`}>{STATUS_LABEL[e.status]}</span></td>
                    <td>
                      <span className="aev-cap">
                        <span className="aev-cap-bar"><span className="aev-cap-fill" style={{ width: `${Math.min(pct, 100)}%` }} /></span>
                        {e.registered.toLocaleString()}/{e.capacity.toLocaleString()}
                      </span>
                    </td>
                    <td>
                      <div className="aev-actions-cell">
                        <button className="btn btn-ghost btn-sm" onClick={() => setToast(`Preview "${e.title}" (demo).`)}>Preview</button>
                        <button className="btn btn-outline btn-sm" onClick={() => setDraft({ ...e })}>Edit</button>
                        {e.status !== "published" && e.status !== "closed" && (
                          <button className="btn btn-primary btn-sm" onClick={() => setStatus(e.id, "published", "Event published.")}>Publish</button>
                        )}
                        {e.status !== "closed" && (
                          <button className="btn btn-ghost btn-sm" onClick={() => setStatus(e.id, "closed", "Event archived.")}>Archive</button>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Create / Edit drawer */}
      <div className={`detail-scrim ${draft ? "open" : ""}`} onClick={() => setDraft(null)} aria-hidden="true" />
      <aside className={`detail-drawer wide ${draft ? "open" : ""}`} role="dialog" aria-label="Event editor" aria-hidden={!draft}>
        {draft && (
          <>
            <div className="detail-head">
              <span className="td-strong">{draft.id ? "Edit event" : "Create event"}</span>
              <button className="source-drawer-close" onClick={() => setDraft(null)} aria-label="Close">✕</button>
            </div>
            <div className="detail-body">
              <form className="aev-form" onSubmit={(e) => { e.preventDefault(); save(); }}>
                <div className="field">
                  <label className="field-label" htmlFor="ev-title">Title</label>
                  <input id="ev-title" className="input" value={draft.title} onChange={(e) => setDraft({ ...draft, title: e.target.value })} placeholder="Event title" />
                </div>
                <div className="grid cols-2" style={{ gap: 12 }}>
                  <div className="field">
                    <label className="field-label" htmlFor="ev-date">Date</label>
                    <input id="ev-date" type="date" className="input" value={draft.date} onChange={(e) => setDraft({ ...draft, date: e.target.value })} />
                  </div>
                  <div className="field">
                    <label className="field-label" htmlFor="ev-time">Time</label>
                    <input id="ev-time" className="input" value={draft.time} onChange={(e) => setDraft({ ...draft, time: e.target.value })} placeholder="10:00 AM – 12:00 PM" />
                  </div>
                </div>
                <div className="field">
                  <label className="field-label" htmlFor="ev-loc">Location</label>
                  <input id="ev-loc" className="input" value={draft.location} onChange={(e) => setDraft({ ...draft, location: e.target.value })} placeholder="Venue" />
                </div>
                <div className="grid cols-2" style={{ gap: 12 }}>
                  <div className="field">
                    <label className="field-label" htmlFor="ev-cat">Category</label>
                    <select id="ev-cat" className="select" value={draft.category} onChange={(e) => setDraft({ ...draft, category: e.target.value })}>
                      {CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
                    </select>
                  </div>
                  <div className="field">
                    <label className="field-label" htmlFor="ev-aud">Audience</label>
                    <select id="ev-aud" className="select" value={draft.audience} onChange={(e) => setDraft({ ...draft, audience: e.target.value })}>
                      {AUDIENCES.map((a) => <option key={a} value={a}>{a}</option>)}
                    </select>
                  </div>
                </div>
                <div className="grid cols-2" style={{ gap: 12 }}>
                  <div className="field">
                    <label className="field-label" htmlFor="ev-cap">Capacity</label>
                    <input id="ev-cap" type="number" className="input" value={draft.capacity} onChange={(e) => setDraft({ ...draft, capacity: Number(e.target.value) || 0 })} />
                  </div>
                  <div className="field">
                    <label className="field-label" htmlFor="ev-status">Status</label>
                    <select id="ev-status" className="select" value={draft.status} onChange={(e) => setDraft({ ...draft, status: e.target.value as EventStatus })}>
                      {(["draft", "scheduled", "published", "closed"] as EventStatus[]).map((s) => <option key={s} value={s}>{STATUS_LABEL[s]}</option>)}
                    </select>
                  </div>
                </div>
                <div style={{ display: "flex", gap: 8, marginTop: 4 }}>
                  <button type="button" className="btn btn-ghost" onClick={() => setDraft(null)}>Cancel</button>
                  <button type="submit" className="btn btn-primary" disabled={!draft.title.trim()}>
                    <IconCheck size={14} /> Save event
                  </button>
                </div>
              </form>
            </div>
          </>
        )}
      </aside>

      {toast && <Toast message={toast} onClose={() => setToast(null)} />}
    </div>
  );
}
