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
  getActiveSuggestedQuestions,
  getAcademicOverview,
} from "@/lib/api";
import type { AcademicCourse, AcademicScheduleEvent } from "@/lib/api";
import { daysUntil, formatDate } from "@/lib/format";
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
  details: string;
  allDay: string;
  justNow: string;
  hoursAgo: (h: number) => string;
  daysAgo: (d: number) => string;
  updated: (rel: string) => string;
  schedNow: string;
  schedCompleted: string;
  schedUpcoming: string;
  academicProgress: string;
  fieldCpa: string;
  progressOf: (earned: number, required: number) => string;
  completedRequired: string;
  remainingRequired: string;
  failedCourses: string;
  enrolledCourses: string;
  upcomingClasses: string;
  none: string;
  noUpcomingClasses: string;
  viewRecord: string;
  academicUnavailable: string;
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
    details: "Details",
    allDay: "All day",
    justNow: "just now",
    hoursAgo: (h) => `${h}h ago`,
    daysAgo: (d) => `${d}d ago`,
    updated: (rel) => `Updated ${rel}`,
    schedNow: "Now",
    schedCompleted: "Completed",
    schedUpcoming: "Upcoming",
    academicProgress: "Academic Progress",
    fieldCpa: "CPA",
    progressOf: (earned, required) => `${earned} / ${required} credits`,
    completedRequired: "Required completed",
    remainingRequired: "Required remaining",
    failedCourses: "Failed courses",
    enrolledCourses: "Currently enrolled",
    upcomingClasses: "Upcoming classes",
    none: "None",
    noUpcomingClasses: "No upcoming classes.",
    viewRecord: "View full academic record",
    academicUnavailable: "Academic data is unavailable right now.",
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
    details: "Chi tiết",
    allDay: "Cả ngày",
    justNow: "vừa xong",
    hoursAgo: (h) => `${h} giờ trước`,
    daysAgo: (d) => `${d} ngày trước`,
    updated: (rel) => `Cập nhật ${rel}`,
    schedNow: "Đang diễn ra",
    schedCompleted: "Đã qua",
    schedUpcoming: "Sắp tới",
    academicProgress: "Tiến độ học tập",
    fieldCpa: "CPA",
    progressOf: (earned, required) => `${earned} / ${required} tín chỉ`,
    completedRequired: "Bắt buộc đã hoàn thành",
    remainingRequired: "Bắt buộc còn lại",
    failedCourses: "Môn chưa đạt",
    enrolledCourses: "Đang học",
    upcomingClasses: "Lớp học sắp tới",
    none: "Không có",
    noUpcomingClasses: "Không có lớp học sắp tới.",
    viewRecord: "Xem toàn bộ kết quả học tập",
    academicUnavailable: "Hiện chưa tải được dữ liệu học tập.",
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
  const { user, token } = useAuth();
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

  const profile = useAsync(() => getStudentProfile(), [token]);
  const academic = useAsync(() => getAcademicOverview(), [token]);
  const schedule = useAsync(() => getStudentSchedule(), [token]);
  const deadlines = useAsync(() => getStudentDeadlines(), [token]);
  const tickets = useAsync(() => getSupportTickets(), [token]);
  const calendar = useAsync(() => getStudentCalendar(), [token]);
  const suggestedQuestions = useAsync(() => getActiveSuggestedQuestions(lang), [lang, token]);

  const go = (q: string) => router.push(`/student/chat?q=${encodeURIComponent(q)}`);

  const pr = profile.status === "success" ? profile.data : null;
  const ac = academic.status === "success" ? academic.data : null;
  const name = user?.name ?? pr?.preferred_name ?? "";

  // Prefer the academic-record GPA/credits (from the Phase 13B academic DB) over the legacy
  // profile fields when available; fall back to the legacy profile otherwise.
  const gpaText = ac?.current_gpa ?? (pr ? pr.gpa.toFixed(2) : null);
  const creditsText = ac
    ? `${ac.earned_credits}/${ac.required_credits}`
    : pr
    ? `${pr.credits_earned}/${pr.credits_required}`
    : null;
  const progressPct = ac
    ? Math.max(0, Math.min(100, Number(ac.summary.progress_percent) || 0))
    : 0;

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

  // Recommended-for-you: prefer backend contextual suggestions, then fall back to
  // local dashboard cues if the endpoint is empty/loading/error.
  const recs: { icon: React.ReactNode; text: string; onClick: () => void; relatedHref?: string }[] = [];
  const addRec = (item: { icon: React.ReactNode; text: string; onClick: () => void; relatedHref?: string }) => {
    if (recs.some((rec) => rec.text === item.text)) return;
    recs.push(item);
  };
  const liveSuggestions =
    suggestedQuestions.status === "success" ? suggestedQuestions.data.slice(0, 3) : [];
  liveSuggestions.forEach((question, index) => {
    const icon =
      index === 0 ? (
        <IconChat size={18} />
      ) : index === 1 ? (
        <IconClock size={18} />
      ) : (
        <IconCap size={18} />
      );
    addRec({
      icon,
      text: question.question_text,
      onClick: () => go(question.question_text),
      relatedHref:
        question.source_type === "forum_topic" && question.source_id
          ? `/student/forum/topics/${question.source_id}`
          : undefined,
    });
  });
  if (todays[0]) {
    addRec({
      icon: <IconCap size={18} />,
      text: s.startsAt(todays[0].course_code, todays[0].start),
      onClick: () => router.push("/student/schedule"),
    });
  }
  if (deadlines.status === "success" && deadlines.data[0]) {
    const d = deadlines.data[0];
    const n = daysUntil(d.due_at);
    addRec({
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
    addRec({
      icon: <IconTicket size={18} />,
      text: s.needsInput(needsInput.id),
      onClick: () => router.push("/student/support"),
    });
  }
  if (recs.length < 3) {
    addRec({
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
              <Field k={s.fieldGpa} v={gpaText ?? "—"} />
              <Field k={s.fieldCredits} v={creditsText ?? "—"} />
            </div>
          </Card>

          {/* Academic Progress (Phase 13C — GET /academic/me) */}
          <Card>
            <div className="dash-section-head">
              <h2 className="dash-section-title">{s.academicProgress}</h2>
              <Link className="dash-viewall" href="/student/academic">
                {s.viewRecord} <IconArrow size={14} />
              </Link>
            </div>
            {academic.status === "loading" ? (
              <p className="rail-empty" style={{ margin: 0 }}>
                …
              </p>
            ) : academic.status === "error" || !ac ? (
              <p className="rail-empty" style={{ margin: 0 }}>
                {s.academicUnavailable}
              </p>
            ) : (
              <div className="academic-progress">
                <div className="profile-card-grid">
                  <Field k={s.fieldGpa} v={ac.current_gpa ?? "—"} />
                  <Field k={s.fieldCpa} v={ac.cumulative_cpa ?? "—"} />
                  <Field k={s.completedRequired} v={String(ac.summary.completed_required_courses)} />
                  <Field k={s.remainingRequired} v={String(ac.summary.remaining_required_courses)} />
                </div>

                <div style={{ marginTop: 16 }}>
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      fontSize: 13,
                      marginBottom: 6,
                    }}
                  >
                    <span className="profile-field-k">{s.fieldCredits}</span>
                    <span className="profile-field-v">
                      {s.progressOf(ac.earned_credits, ac.required_credits)} · {progressPct}%
                    </span>
                  </div>
                  <div
                    className="academic-progress-bar"
                    role="progressbar"
                    aria-valuenow={progressPct}
                    aria-valuemin={0}
                    aria-valuemax={100}
                    style={{
                      height: 8,
                      borderRadius: 999,
                      background: "var(--surface-2, rgba(0,0,0,0.08))",
                      overflow: "hidden",
                    }}
                  >
                    <div
                      style={{
                        width: `${progressPct}%`,
                        height: "100%",
                        background: "var(--brand, #c8102e)",
                      }}
                    />
                  </div>
                </div>

                <CourseChips title={s.enrolledCourses} courses={ac.enrolled_courses} none={s.none} />
                <CourseChips
                  title={s.failedCourses}
                  courses={ac.failed_courses}
                  none={s.none}
                  tone="warning"
                />

                <div style={{ marginTop: 16 }}>
                  <div className="profile-field-k" style={{ marginBottom: 8 }}>
                    {s.upcomingClasses}
                  </div>
                  {ac.upcoming_meetings.length === 0 ? (
                    <p className="rail-empty" style={{ margin: 0 }}>
                      {s.noUpcomingClasses}
                    </p>
                  ) : (
                    <div className="dash-list">
                      {ac.upcoming_meetings.slice(0, 4).map((m) => (
                        <MeetingRow key={m.id} m={m} locale={locale} />
                      ))}
                    </div>
                  )}
                </div>
              </div>
            )}
          </Card>

          {/* Recommended for You */}
          <div>
            <div className="dash-section-head">
              <h2 className="dash-section-title">{s.recommended}</h2>
            </div>
            <div className="rec-strip">
              {recs.slice(0, 3).map((r, i) => (
                <div key={i} className="rec-card-wrap">
                  <button className="rec-card" onClick={r.onClick}>
                    <span className="rec-icon">{r.icon}</span>
                    <span className="rec-text">{r.text}</span>
                  </button>
                  {r.relatedHref && (
                    <Link className="rec-related" href={r.relatedHref}>
                      {p.forum.relatedForumTopic}
                    </Link>
                  )}
                </div>
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

function CourseChips({
  title,
  courses,
  none,
  tone = "neutral",
}: {
  title: string;
  courses: AcademicCourse[];
  none: string;
  tone?: "neutral" | "warning";
}) {
  return (
    <div style={{ marginTop: 16 }}>
      <div className="profile-field-k" style={{ marginBottom: 8 }}>
        {title}
      </div>
      {courses.length === 0 ? (
        <p className="rail-empty" style={{ margin: 0 }}>
          {none}
        </p>
      ) : (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
          {courses.map((c) => (
            <span key={c.id} className={`ah-chip ${tone === "warning" ? "warning" : "neutral"}`}>
              {c.code}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

function MeetingRow({ m, locale }: { m: AcademicScheduleEvent; locale: string }) {
  const sub = [
    m.section_code ? `${m.course_code} · ${m.section_code}` : m.course_code,
    [m.room_name, m.building].filter(Boolean).join(", "),
    m.instructor_name ?? "",
  ]
    .filter(Boolean)
    .join(" · ");
  return (
    <div className="rail-sched-row">
      <span className="rail-time">
        {formatDate(m.start_at, locale)} · {timeLabel(m.start_at, locale)}
      </span>
      <div className="rail-sched-main">
        <div className="rail-sched-title">{m.title}</div>
        <div className="rail-sched-sub">{sub}</div>
      </div>
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
