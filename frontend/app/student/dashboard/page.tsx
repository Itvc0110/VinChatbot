"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Card } from "@/components/ui/primitives";
import { useAsync } from "@/lib/useAsync";
import { usePortal } from "@/lib/portalI18n";
import { useAuth } from "@/lib/auth";
import {
  getStudentProfile,
  getStudentSchedule,
  getStudentDeadlines,
  getSupportTickets,
  getStudentCalendar,
} from "@/lib/api";
import { daysUntil } from "@/lib/format";
import { timeLabel } from "@/lib/calendar";
import {
  IconArrow,
  IconClock,
  IconTicket,
  IconChat,
  IconCap,
} from "@/components/shell/icons";
import type {
  ScheduleDay,
  SupportTicket,
  TicketStatus,
  CalendarEvent,
} from "@/lib/portalTypes";

const DAY_ORDER: ScheduleDay[] = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
function todayShort(): ScheduleDay {
  return DAY_ORDER[(new Date().getDay() + 6) % 7];
}

// ---- Time-aware schedule states (FRONTEND-ONLY; no backend / payload change) -----
// Drives the visual "Completed / Now / Upcoming" states on the Today's Schedule card.
type ScheduleState = "past" | "current" | "upcoming";

// "HH:MM" → minutes since midnight (local). Returns NaN for malformed input.
function minutesOfDay(hhmm: string): number {
  const [h, m] = hhmm.split(":").map(Number);
  return h * 60 + (m || 0);
}

// Compare a class to the current local time. With both start and end we use
// [start, end). If an item somehow has only a start, infer a UI-only 90-minute
// duration so it can still resolve a "current" window (presentation only — the
// schedule data structure is unchanged).
function getScheduleItemState(
  item: { start: string; end?: string },
  now: Date
): ScheduleState {
  const cur = now.getHours() * 60 + now.getMinutes();
  const start = minutesOfDay(item.start);
  if (Number.isNaN(start)) return "upcoming";
  const end = item.end ? minutesOfDay(item.end) : start + 90; // 90-min fallback: UI-only
  if (cur >= end) return "past";
  if (cur >= start) return "current";
  return "upcoming";
}

const ACTIVE_STATUSES: TicketStatus[] = ["submitted", "in_review", "waiting_for_student"];
const TICKET_CHIP: Record<TicketStatus, string> = {
  draft: "neutral",
  submitted: "info",
  in_review: "warning",
  waiting_for_student: "warning",
  resolved: "success",
  closed: "neutral",
};

type Lang = "en" | "vi";

const TICKET_STATUS_LABEL: Record<Lang, Record<TicketStatus, string>> = {
  en: {
    draft: "Draft",
    submitted: "Submitted",
    in_review: "In Progress",
    waiting_for_student: "Needs Input",
    resolved: "Resolved",
    closed: "Closed",
  },
  vi: {
    draft: "Bản nháp",
    submitted: "Đã gửi",
    in_review: "Đang xử lý",
    waiting_for_student: "Cần phản hồi",
    resolved: "Đã giải quyết",
    closed: "Đã đóng",
  },
};

const STR: Record<Lang, {
  welcome: string;
  academicProfile: string;
  recommended: string;
  activeTickets: string;
  upcomingEvents: string;
  noUpcomingEvents: string;
  fieldProgram: string;
  fieldYear: string;
  fieldTerm: string;
  fieldAdvisor: string;
  fieldGpa: string;
  fieldCredits: string;
  yearOf: (n: number | string) => string;
  startsAt: (code: string, time: string) => string;
  dueToday: (title: string) => string;
  dueInDays: (title: string, n: number) => string;
  needsInput: (id: string) => string;
  askAnything: string;
  askVinnieAboutToday: string;
  details: string;
  allDay: string;
  justNow: string;
  hoursAgo: (h: number) => string;
  daysAgo: (d: number) => string;
  updated: (rel: string) => string;
  schedNow: string;
  schedCompleted: string;
  schedUpcoming: string;
}> = {
  en: {
    welcome: "Welcome to Student Copilot",
    academicProfile: "Academic Profile",
    recommended: "Recommended for You",
    activeTickets: "Active Tickets",
    upcomingEvents: "Upcoming Events",
    noUpcomingEvents: "No upcoming events.",
    fieldProgram: "Program",
    fieldYear: "Year",
    fieldTerm: "Term",
    fieldAdvisor: "Advisor",
    fieldGpa: "GPA",
    fieldCredits: "Credits",
    yearOf: (n) => `Year ${n}`,
    startsAt: (code, time) => `${code} starts at ${time}`,
    dueToday: (title) => `${title} is due today`,
    dueInDays: (title, n) => `${title} is due in ${n} day${n === 1 ? "" : "s"}`,
    needsInput: (id) => `Ticket ${id} needs your input`,
    askAnything: "Ask Vinnie anything about your studies",
    askVinnieAboutToday: "Ask Vinnie about today",
    details: "Details",
    allDay: "All day",
    justNow: "just now",
    hoursAgo: (h) => `${h}h ago`,
    daysAgo: (d) => `${d}d ago`,
    updated: (rel) => `Updated ${rel}`,
    schedNow: "Now",
    schedCompleted: "Completed",
    schedUpcoming: "Upcoming",
  },
  vi: {
    welcome: "Chào mừng đến với Student Copilot",
    academicProfile: "Hồ sơ học vụ",
    recommended: "Gợi ý cho bạn",
    activeTickets: "Phiếu đang mở",
    upcomingEvents: "Sự kiện sắp tới",
    noUpcomingEvents: "Không có sự kiện sắp tới.",
    fieldProgram: "Chương trình",
    fieldYear: "Năm học",
    fieldTerm: "Học kỳ",
    fieldAdvisor: "Cố vấn",
    fieldGpa: "GPA",
    fieldCredits: "Tín chỉ",
    yearOf: (n) => `Năm ${n}`,
    startsAt: (code, time) => `${code} bắt đầu lúc ${time}`,
    dueToday: (title) => `${title} đến hạn hôm nay`,
    dueInDays: (title, n) => `${title} đến hạn trong ${n} ngày`,
    needsInput: (id) => `Phiếu ${id} cần bạn phản hồi`,
    askAnything: "Hỏi Vinnie bất cứ điều gì về việc học của bạn",
    askVinnieAboutToday: "Hỏi Vinnie về hôm nay",
    details: "Chi tiết",
    allDay: "Cả ngày",
    justNow: "vừa xong",
    hoursAgo: (h) => `${h} giờ trước`,
    daysAgo: (d) => `${d} ngày trước`,
    updated: (rel) => `Cập nhật ${rel}`,
    schedNow: "Đang diễn ra",
    schedCompleted: "Đã qua",
    schedUpcoming: "Sắp tới",
  },
};

function relTime(iso: string, s: (typeof STR)[Lang]): string {
  const diff = Date.now() - new Date(iso).getTime();
  const h = Math.round(diff / 3_600_000);
  if (h < 1) return s.justNow;
  if (h < 24) return s.hoursAgo(h);
  return s.daysAgo(Math.round(h / 24));
}

export default function StudentDashboardPage() {
  const { p, lang } = usePortal();
  const s = STR[lang];
  const locale = lang === "vi" ? "vi-VN" : "en-US";
  const { user } = useAuth();
  const router = useRouter();

  // Local clock for time-aware schedule states. Starts null so SSR and the first
  // client render agree (no hydration mismatch); set on mount, then re-ticks every
  // minute. Cleaned up on unmount. Frontend-only — no network involved.
  const [now, setNow] = useState<Date | null>(null);
  useEffect(() => {
    setNow(new Date());
    const id = setInterval(() => setNow(new Date()), 60_000);
    return () => clearInterval(id);
  }, []);

  const profile = useAsync(() => getStudentProfile(), []);
  const schedule = useAsync(() => getStudentSchedule(), []);
  const deadlines = useAsync(() => getStudentDeadlines(), []);
  const tickets = useAsync(() => getSupportTickets(), []);
  const calendar = useAsync(() => getStudentCalendar(), []);

  const go = (q: string) => router.push(`/student/chat?q=${encodeURIComponent(q)}`);

  const pr = profile.status === "success" ? profile.data : null;
  const name = user?.name ?? pr?.preferred_name ?? "";

  // Today's classes (fall back to next day with classes, like the original).
  const allClasses = schedule.status === "success" ? schedule.data : [];
  const today = todayShort();
  let schedDay = today;
  let todays = allClasses.filter((s) => s.day === schedDay);
  if (todays.length === 0) {
    const next = DAY_ORDER.slice(DAY_ORDER.indexOf(today) + 1)
      .concat(DAY_ORDER)
      .find((d) => allClasses.some((s) => s.day === d));
    if (next) {
      schedDay = next;
      todays = allClasses.filter((s) => s.day === schedDay);
    }
  }
  todays = [...todays].sort((a, b) => a.start.localeCompare(b.start));
  // Time-aware states only make sense when the rail is actually showing *today*.
  // When today has no classes we fall back to the next day with classes — those
  // are all genuinely upcoming, so we skip the now/past comparison.
  const isToday = schedDay === today;

  const activeTickets = (tickets.status === "success" ? tickets.data : [])
    .filter((t) => ACTIVE_STATUSES.includes(t.status) && !t.archived && !t.deleted)
    .slice(0, 3);

  const upcomingEvents = (calendar.status === "success" ? calendar.data : [])
    .filter((e) => e.type === "event" && new Date(e.start).getTime() >= Date.now())
    .sort((a, b) => new Date(a.start).getTime() - new Date(b.start).getTime())
    .slice(0, 3);

  // Recommended-for-you: derived, urgency-first.
  const recs: { icon: React.ReactNode; text: string; onClick: () => void }[] = [];
  if (todays[0]) {
    recs.push({
      icon: <IconCap size={18} />,
      text: s.startsAt(todays[0].course_code, todays[0].start),
      onClick: () => router.push("/student/schedule"),
    });
  }
  if (deadlines.status === "success" && deadlines.data[0]) {
    const d = deadlines.data[0];
    const n = daysUntil(d.due_at);
    recs.push({
      icon: <IconClock size={18} />,
      text: n <= 0 ? s.dueToday(d.title) : s.dueInDays(d.title, n),
      onClick: () => go(`Tell me about the deadline: ${d.title}`),
    });
  }
  const needsInput = (tickets.status === "success" ? tickets.data : []).find(
    (t) => t.status === "waiting_for_student" && !t.archived && !t.deleted
  );
  if (needsInput) {
    recs.push({
      icon: <IconTicket size={18} />,
      text: s.needsInput(needsInput.id),
      onClick: () => router.push("/student/support"),
    });
  }
  while (recs.length < 3) {
    recs.push({
      icon: <IconChat size={18} />,
      text: s.askAnything,
      onClick: () => router.push("/student/chat"),
    });
  }

  return (
    <div className="page-inner">
      <div className="dash-welcome">
        <h1 className="dash-welcome-title">
          {s.welcome}{name ? `, ${name}` : ""} 👋
        </h1>
        <p className="dash-welcome-sub">{p.productTagline}</p>
      </div>

      <div className="dash-grid">
        <div className="dash-main">
          {/* Academic Profile */}
          <Card>
            <div className="dash-section-head">
              <h2 className="dash-section-title">{s.academicProfile}</h2>
            </div>
            <div className="profile-card-grid">
              <Field k={s.fieldProgram} v={pr?.program ?? "—"} />
              <Field k={s.fieldYear} v={pr ? s.yearOf(pr.year) : "—"} />
              <Field k={s.fieldTerm} v={pr?.intake ?? "—"} />
              <Field k={s.fieldAdvisor} v={pr?.advisor ?? "—"} />
              <Field k={s.fieldGpa} v={pr ? pr.gpa.toFixed(2) : "—"} />
              <Field
                k={s.fieldCredits}
                v={pr ? `${pr.credits_earned}/${pr.credits_required}` : "—"}
              />
            </div>
          </Card>

          {/* Recommended for You */}
          <div>
            <div className="dash-section-head">
              <h2 className="dash-section-title">{s.recommended}</h2>
            </div>
            <div className="rec-strip">
              {recs.slice(0, 3).map((r, i) => (
                <button key={i} className="rec-card" onClick={r.onClick}>
                  <span className="rec-icon">{r.icon}</span>
                  <span className="rec-text">{r.text}</span>
                </button>
              ))}
            </div>
          </div>

          {/* Active Tickets */}
          <div>
            <div className="dash-section-head">
              <h2 className="dash-section-title">{s.activeTickets}</h2>
              <Link className="dash-viewall" href="/student/support">
                {p.viewAll} <IconArrow size={14} />
              </Link>
            </div>
            {activeTickets.length === 0 ? (
              <Card>
                <p className="rail-empty" style={{ margin: 0 }}>
                  {p.sup.noTicketsTitle}
                </p>
              </Card>
            ) : (
              <div className="dash-list">
                {activeTickets.map((t) => (
                  <TicketCardLite
                    key={t.id}
                    t={t}
                    lang={lang}
                    onClick={() => router.push("/student/support")}
                  />
                ))}
              </div>
            )}
          </div>

          {/* Upcoming Events */}
          <div>
            <div className="dash-section-head">
              <h2 className="dash-section-title">{s.upcomingEvents}</h2>
              <Link className="dash-viewall" href="/student/events">
                {p.viewAll} <IconArrow size={14} />
              </Link>
            </div>
            {upcomingEvents.length === 0 ? (
              <Card>
                <p className="rail-empty" style={{ margin: 0 }}>
                  {s.noUpcomingEvents}
                </p>
              </Card>
            ) : (
              <div className="dash-list">
                {upcomingEvents.map((e) => (
                  <EventRowLite key={e.id} e={e} locale={locale} lang={lang} />
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Right rail */}
        <div className="dash-rail">
          <div className="rail-card">
            <h3 className="rail-title">
              {p.todaySchedule}
              {schedDay !== today ? ` · ${p.dayFull[schedDay]}` : ""}
            </h3>
            {todays.length === 0 ? (
              <p className="rail-empty">{p.dash.noClasses}</p>
            ) : (
              todays.map((cls) => {
                const state =
                  isToday && now ? getScheduleItemState(cls, now) : "upcoming";
                const stateLabel =
                  state === "current"
                    ? s.schedNow
                    : state === "past"
                    ? s.schedCompleted
                    : s.schedUpcoming;
                return (
                  <div
                    key={cls.id}
                    className={`rail-sched-row state-${state}`}
                    title={stateLabel}
                  >
                    <span className="rail-time">{cls.start}</span>
                    <div className="rail-sched-main">
                      <div className="rail-sched-title">
                        {cls.course_title}
                        {state === "current" && (
                          <span className="sched-badge now">
                            <span className="sched-dot" aria-hidden />
                            {s.schedNow}
                          </span>
                        )}
                        {state === "past" && (
                          <span className="sched-badge past">{s.schedCompleted}</span>
                        )}
                      </div>
                      <div className="rail-sched-sub">
                        {cls.room}, {cls.building} · {cls.instructor}
                      </div>
                    </div>
                  </div>
                );
              })
            )}
          </div>

          <div className="ask-vinnie-card">
            <h3>{p.askCta}</h3>
            <p>{p.askAnything}</p>
            <button
              className="ask-vinnie-btn"
              onClick={() => go("What's on my schedule today?")}
            >
              <IconChat size={15} /> {s.askVinnieAboutToday}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function Field({ k, v }: { k: string; v: string }) {
  return (
    <div>
      <div className="profile-field-k">{k}</div>
      <div className="profile-field-v">{v}</div>
    </div>
  );
}

function TicketCardLite({
  t,
  lang,
  onClick,
}: {
  t: SupportTicket;
  lang: Lang;
  onClick: () => void;
}) {
  const s = STR[lang];
  return (
    <button className="dash-ticket-card" onClick={onClick}>
      <span className="rec-icon">
        <IconTicket size={18} />
      </span>
      <div className="dash-ticket-main">
        <div className="dash-ticket-meta">
          {t.department} · {t.id}
        </div>
        <div className="dash-ticket-title">{t.subject}</div>
        <p className="dash-ticket-desc">{t.body}</p>
        <div className="dash-ticket-time">{s.updated(relTime(t.updated_at, s))}</div>
      </div>
      <span className={`ah-chip ${TICKET_CHIP[t.status]}`}>
        {TICKET_STATUS_LABEL[lang][t.status]}
      </span>
    </button>
  );
}

function EventRowLite({ e, locale, lang }: { e: CalendarEvent; locale: string; lang: Lang }) {
  const s = STR[lang];
  const start = new Date(e.start);
  const mon = start.toLocaleDateString(locale, { month: "short" });
  const day = start.getDate();
  const time = e.all_day
    ? s.allDay
    : `${timeLabel(e.start, locale)}${e.end ? ` – ${timeLabel(e.end, locale)}` : ""}`;
  return (
    <div className="event-row">
      <div className="event-date">
        <div className="event-date-mon">{mon}</div>
        <div className="event-date-day">{day}</div>
      </div>
      <div className="event-main">
        <div className="event-title">{e.title}</div>
        <div className="event-meta">
          <span>{time}</span>
          {e.location && <span>· {e.location}</span>}
        </div>
      </div>
      <Link className="btn btn-outline btn-sm" href="/student/events">
        {s.details}
      </Link>
    </div>
  );
}
