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

const ACTIVE_STATUSES: TicketStatus[] = [
  "submitted",
  "open",
  "in_review",
  "in_progress",
  "waiting_for_student",
  "waiting_on_student",
];
const TICKET_CHIP: Record<TicketStatus, string> = {
  draft: "neutral",
  submitted: "info",
  open: "info",
  in_review: "warning",
  in_progress: "warning",
  waiting_for_student: "warning",
  waiting_on_student: "warning",
  resolved: "success",
  closed: "neutral",
};

type Lang = "en" | "vi";

const TICKET_STATUS_LABEL: Record<Lang, Record<TicketStatus, string>> = {
  en: {
    draft: "Draft",
    submitted: "Submitted",
    open: "Open",
    in_review: "In Progress",
    in_progress: "In Progress",
    waiting_for_student: "Needs Input",
    waiting_on_student: "Needs Input",
    resolved: "Resolved",
    closed: "Closed",
  },
  vi: {
    draft: "Bản nháp",
    submitted: "Đã gửi",
    open: "Đang mở",
    in_review: "Đang xử lý",
    in_progress: "Đang xử lý",
    waiting_for_student: "Cần phản hồi",
    waiting_on_student: "Cần phản hồi",
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

<<<<<<< Updated upstream
=======
function meetingSub(m: AcademicScheduleEvent): string {
  return [
    m.section_code ? `${m.course_code} · ${m.section_code}` : m.course_code,
    [m.room_name, m.building].filter(Boolean).join(", "),
  ]
    .filter(Boolean)
    .join(" · ");
}

function localizedCourseName(
  item: AcademicCourse | AcademicScheduleEvent,
  lang: Lang
): string {
  if ("course_name" in item) {
    return lang === "vi" ? item.course_name_vi ?? item.course_name : item.course_name;
  }
  return lang === "vi" ? item.name_vi ?? item.name : item.name;
}

>>>>>>> Stashed changes
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

<<<<<<< Updated upstream
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
=======
  // Prefer rich academic-record values; the profile endpoint exposes the same canonical DB summary.
  const gpaText = ac?.current_gpa ?? (pr ? pr.gpa.toFixed(2) : null);
  const cpaText = ac?.cumulative_cpa ?? null;
  const creditsText = ac
    ? `${ac.earned_credits}/${ac.required_credits}`
    : pr
    ? `${pr.credits_earned}/${pr.credits_required}`
    : null;
  const progressPct = ac
    ? Math.max(0, Math.min(100, Number(ac.summary.progress_percent) || 0))
    : 0;

  // ---- Schedule (dated meetings for the current month) ----
  const monthMeetings = (monthly.status === "success" ? monthly.data : [])
    .slice()
    .sort((a, b) => new Date(a.start_at).getTime() - new Date(b.start_at).getTime());
  const todayMeetings = monthMeetings.filter((m) => sameDay(new Date(m.start_at), clock));
  // The next class still ahead today (ongoing counts as the current focus).
  const nextTodayMeeting = todayMeetings.find((m) => meetingState(m, clock) !== "past");
  const hadClassesToday = todayMeetings.length > 0;
  // Upcoming meetings anywhere in the month (drives the month card list).
  const upcomingMonth = monthMeetings.filter((m) => new Date(m.start_at).getTime() >= clock.getTime());
>>>>>>> Stashed changes

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
    (t) =>
      (t.status === "waiting_for_student" || t.status === "waiting_on_student") &&
      !t.archived &&
      !t.deleted
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

<<<<<<< Updated upstream
=======
      {/* Today Focus — full-width priority strip */}
      <section className="focus-strip" aria-label={s.todayFocus}>
        <FocusCard
          icon={<IconCap size={18} />}
          label={s.focusNextClass}
          detail={
            nextTodayMeeting
              ? `${timeLabel(nextTodayMeeting.start_at, locale)} · ${localizedCourseName(nextTodayMeeting, lang)}`
              : hadClassesToday
              ? s.noMoreClassesToday
              : s.noClassesToday
          }
          status={
            nextTodayMeeting
              ? meetingState(nextTodayMeeting, clock) === "current"
                ? { text: s.nowLabel, tone: "success" }
                : startsSoon
                ? { text: s.startsSoon, tone: "warning" }
                : null
              : null
          }
          muted={!nextTodayMeeting}
          onClick={() => router.push("/student/schedule")}
        />
        <FocusCard
          icon={<IconTicket size={18} />}
          label={s.focusTicket}
          detail={
            needsInputTicket
              ? needsInputTicket.subject
              : allActiveTickets.length > 0
              ? s.ticketsOpen(allActiveTickets.length)
              : s.noTicketAttention
          }
          status={needsInputTicket ? { text: s.needsInput, tone: "warning" } : null}
          muted={!needsInputTicket && allActiveTickets.length === 0}
          onClick={() => router.push("/student/support")}
        />
        <FocusCard
          icon={<IconClock size={18} />}
          label={s.focusDeadline}
          detail={nextDeadline ? nextDeadline.title : s.noUrgentDeadline}
          status={
            nextDeadline
              ? dl !== null && dl <= 0
                ? { text: s.dueToday, tone: "warning" }
                : dl !== null
                ? { text: s.dueInDays(dl), tone: dl <= 3 ? "warning" : "neutral" }
                : null
              : null
          }
          muted={!nextDeadline}
          onClick={nextDeadline ? () => go(`Tell me about the deadline: ${nextDeadline.title}`) : undefined}
        />
        <FocusCard
          icon={<IconCalendar size={18} />}
          label={s.focusEvent}
          detail={
            nextEvent
              ? `${new Date(nextEvent.start).toLocaleDateString(locale, { month: "short", day: "numeric" })} · ${nextEvent.title}`
              : s.noUpcomingEventToday
          }
          muted={!nextEvent}
          onClick={() => router.push("/student/events")}
        />
      </section>

>>>>>>> Stashed changes
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
<<<<<<< Updated upstream
=======
            {academic.status === "loading" ? (
              <p className="rail-empty">
                …
              </p>
            ) : academic.status === "error" || !ac ? (
              <p className="rail-empty">
                {s.academicUnavailable}
              </p>
            ) : (
              <>
                <div className="snapshot-stats">
                  <Stat k={s.fieldGpa} v={gpaText ?? "—"} />
                  <Stat k={s.fieldCpa} v={cpaText ?? "—"} />
                  <Stat k={s.fieldCredits} v={creditsText ?? "—"} />
                  <Stat
                    k={s.fieldRequired}
                    v={s.requiredValue(
                      ac.summary.completed_required_courses,
                      ac.summary.remaining_required_courses
                    )}
                  />
                </div>

                <div className="snapshot-progress">
                  <div className="snapshot-progress-meta">
                    <span className="profile-field-k">{s.fieldCredits}</span>
                    <span className="profile-field-v">{progressPct}%</span>
                  </div>
                  <div
                    className="academic-progress-bar"
                    role="progressbar"
                    aria-valuenow={progressPct}
                    aria-valuemin={0}
                    aria-valuemax={100}
                  >
                    <div className="academic-progress-fill" style={{ width: `${progressPct}%` }} />
                  </div>
                </div>

                <CourseChips
                  title={s.currentlyStudying}
                  courses={ac.enrolled_courses}
                  none={s.none}
                  more={s.moreCount}
                  lang={lang}
                />
              </>
            )}
>>>>>>> Stashed changes
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
<<<<<<< Updated upstream
                        {cls.course_title}
                        {state === "current" && (
=======
                        {localizedCourseName(m, lang)}
                        {state === "current" ? (
>>>>>>> Stashed changes
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

<<<<<<< Updated upstream
          <div className="ask-vinnie-card">
            <h3>{p.askCta}</h3>
            <p>{p.askAnything}</p>
            <button
              className="ask-vinnie-btn"
              onClick={() => go("What's on my schedule today?")}
            >
              <IconChat size={15} /> {s.askVinnieAboutToday}
            </button>
=======
          {/* Current month schedule */}
          <div className="rail-card dash-card dash-card--month">
            <div className="rail-head">
              <h3 className="rail-title">{s.monthScheduleTitle}</h3>
              <span className="month-pill">{monthTitle(clock, locale)}</span>
            </div>
            {monthly.status === "loading" ? (
              <p className="rail-empty">…</p>
            ) : monthly.status === "error" ? (
              <p className="rail-empty">{s.scheduleUnavailable}</p>
            ) : monthMeetings.length === 0 ? (
              <p className="rail-empty">{s.noClassesThisMonth}</p>
            ) : (
              <>
                <div className="month-list">
                  {(upcomingMonth.length > 0 ? upcomingMonth : monthMeetings).slice(0, 4).map((m) => (
                    <div key={m.id} className="rail-sched-row">
                      <span className="rail-time rail-time--date">
                        {new Date(m.start_at).toLocaleDateString(locale, { day: "2-digit", month: "short" })}
                      </span>
                      <div className="rail-sched-main">
                        <div className="rail-sched-title">{localizedCourseName(m, lang)}</div>
                        <div className="rail-sched-sub">
                          {timeLabel(m.start_at, locale)} · {meetingSub(m)}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
                <Link className="dash-viewall month-viewall" href="/student/schedule">
                  {s.viewFullSchedule} <IconArrow size={14} />
                </Link>
              </>
            )}
>>>>>>> Stashed changes
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
<<<<<<< Updated upstream
      <div className="profile-field-v">{v}</div>
=======
      <div className="snapshot-stat-v">{v}</div>
    </div>
  );
}

function FocusCard({
  icon,
  label,
  detail,
  status,
  muted,
  onClick,
}: {
  icon: React.ReactNode;
  label: string;
  detail: string;
  status?: { text: string; tone: "success" | "warning" | "neutral" } | null;
  muted?: boolean;
  onClick?: () => void;
}) {
  const inner = (
    <>
      <span className="focus-icon">{icon}</span>
      <div className="focus-body">
        <div className="focus-label">{label}</div>
        <div className={`focus-detail ${muted ? "muted" : ""}`}>{detail}</div>
      </div>
      {status && <span className={`ah-chip ${status.tone} focus-chip`}>{status.text}</span>}
    </>
  );
  if (!onClick) return <div className="focus-card focus-card--static">{inner}</div>;
  return (
    <button className="focus-card" onClick={onClick}>
      {inner}
    </button>
  );
}

function CourseChips({
  title,
  courses,
  none,
  more,
  lang,
}: {
  title: string;
  courses: AcademicCourse[];
  none: string;
  more: (n: number) => string;
  lang: Lang;
}) {
  const shown = courses.slice(0, MAX_CHIPS);
  const extra = courses.length - shown.length;
  return (
    <div className="snapshot-chips">
      <div className="profile-field-k" style={{ marginBottom: 8 }}>
        {title}
      </div>
      {courses.length === 0 ? (
        <p className="rail-empty">
          {none}
        </p>
      ) : (
        <div className="chip-row">
          {shown.map((c) => (
            <span key={c.id} className="ah-chip neutral" title={localizedCourseName(c, lang)}>
              {c.code}
            </span>
          ))}
          {extra > 0 && <span className="ah-chip neutral chip-more">{more(extra)}</span>}
        </div>
      )}
>>>>>>> Stashed changes
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
