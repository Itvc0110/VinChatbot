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
  getStudentDeadlines,
  getSupportTickets,
  getStudentCalendar,
  getActiveSuggestedQuestions,
  getAcademicOverview,
  getMonthlySchedule,
} from "@/lib/api";
import type { AcademicCourse, AcademicScheduleEvent } from "@/lib/api";
import { daysUntil } from "@/lib/format";
import { monthTitle, timeLabel, sameDay } from "@/lib/calendar";
import {
  IconArrow,
  IconClock,
  IconTicket,
  IconChat,
  IconCap,
  IconCalendar,
  IconBell,
} from "@/components/shell/icons";
import type {
  SupportTicket,
  TicketStatus,
  CalendarEvent,
  Deadline,
} from "@/lib/portalTypes";

// "YYYY-MM" for a given date (local wall-clock) — the shape GET /schedule/me?month= expects.
function monthKeyOf(date: Date): string {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`;
}

// ---- Time-aware meeting states (FRONTEND-ONLY; no backend / payload change) -----
type MeetingState = "past" | "current" | "upcoming";
function meetingState(m: AcademicScheduleEvent, now: Date): MeetingState {
  const start = new Date(m.start_at).getTime();
  const end = new Date(m.end_at).getTime();
  const t = now.getTime();
  if (Number.isNaN(start)) return "upcoming";
  if (t >= (Number.isNaN(end) ? start + 90 * 60_000 : end)) return "past";
  if (t >= start) return "current";
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

const MAX_CHIPS = 6; // currently-studying chips before collapsing into "+N more"

const STR: Record<Lang, {
  welcome: string;
  todayFocus: string;
  focusNextClass: string;
  focusTicket: string;
  focusDeadline: string;
  focusEvent: string;
  noMoreClassesToday: string;
  noClassesToday: string;
  noTicketAttention: string;
  ticketsOpen: (n: number) => string;
  needsInput: string;
  noUrgentDeadline: string;
  noUpcomingEventToday: string;
  academicSnapshot: string;
  fieldGpa: string;
  fieldCpa: string;
  fieldCredits: string;
  fieldRequired: string;
  requiredValue: (done: number, remaining: number) => string;
  currentlyStudying: string;
  moreCount: (n: number) => string;
  none: string;
  viewRecord: string;
  academicUnavailable: string;
  recommended: string;
  recommendedSub: string;
  activeTickets: string;
  todayScheduleTitle: string;
  nextClass: string;
  startsSoon: string;
  nowLabel: string;
  completed: string;
  instructorPrefix: string;
  viewFullSchedule: string;
  monthScheduleTitle: string;
  classesThisMonth: (n: number) => string;
  noClassesThisMonth: string;
  scheduleUnavailable: string;
  upcomingEvents: string;
  noUpcomingEvents: string;
  allDay: string;
  details: string;
  dueToday: string;
  dueInDays: (n: number) => string;
  askAnything: string;
  updated: (rel: string) => string;
  justNow: string;
  hoursAgo: (h: number) => string;
  daysAgo: (d: number) => string;
}> = {
  en: {
    welcome: "Welcome to Student Copilot",
    todayFocus: "Today's focus",
    focusNextClass: "Next class",
    focusTicket: "Support",
    focusDeadline: "Deadline",
    focusEvent: "Event",
    noMoreClassesToday: "No more classes today",
    noClassesToday: "No classes today",
    noTicketAttention: "No tickets need attention",
    ticketsOpen: (n) => `${n} open ticket${n === 1 ? "" : "s"}`,
    needsInput: "Awaiting your reply",
    noUrgentDeadline: "No urgent deadline",
    noUpcomingEventToday: "No upcoming event",
    academicSnapshot: "Academic Snapshot",
    fieldGpa: "GPA",
    fieldCpa: "CPA",
    fieldCredits: "Credits",
    fieldRequired: "Required",
    requiredValue: (done, remaining) => `${done} done · ${remaining} left`,
    currentlyStudying: "Currently studying",
    moreCount: (n) => `+${n} more`,
    none: "None",
    viewRecord: "View academic progress",
    academicUnavailable: "Academic data is unavailable right now.",
    recommended: "Suggestions for you",
    recommendedSub: "Based on your schedule, tickets, and recent notifications",
    activeTickets: "Open tickets",
    todayScheduleTitle: "Today's schedule",
    nextClass: "Next class",
    startsSoon: "Starts soon",
    nowLabel: "Now",
    completed: "Done",
    instructorPrefix: "Instructor",
    viewFullSchedule: "View full schedule",
    monthScheduleTitle: "This month's classes",
    classesThisMonth: (n) => `${n} class meeting${n === 1 ? "" : "s"} this month`,
    noClassesThisMonth: "No classes scheduled for this month.",
    scheduleUnavailable: "Couldn't load your schedule right now.",
    upcomingEvents: "Upcoming events",
    noUpcomingEvents: "No upcoming events.",
    allDay: "All day",
    details: "Details",
    dueToday: "Due today",
    dueInDays: (n) => `Due in ${n} day${n === 1 ? "" : "s"}`,
    askAnything: "Ask Vinnie anything about your studies",
    updated: (rel) => `Updated ${rel}`,
    justNow: "just now",
    hoursAgo: (h) => `${h}h ago`,
    daysAgo: (d) => `${d}d ago`,
  },
  vi: {
    welcome: "Chào mừng đến với Student Copilot",
    todayFocus: "Ưu tiên hôm nay",
    focusNextClass: "Lớp kế tiếp",
    focusTicket: "Hỗ trợ",
    focusDeadline: "Hạn chót",
    focusEvent: "Sự kiện",
    noMoreClassesToday: "Hôm nay không còn lớp",
    noClassesToday: "Hôm nay không có lớp",
    noTicketAttention: "Không có phiếu cần xử lý",
    ticketsOpen: (n) => `${n} phiếu đang mở`,
    needsInput: "Đang chờ bạn phản hồi",
    noUrgentDeadline: "Không có hạn chót gấp",
    noUpcomingEventToday: "Không có sự kiện sắp tới",
    academicSnapshot: "Tổng quan học tập",
    fieldGpa: "GPA",
    fieldCpa: "CPA",
    fieldCredits: "Tín chỉ",
    fieldRequired: "Bắt buộc",
    requiredValue: (done, remaining) => `${done} xong · còn ${remaining}`,
    currentlyStudying: "Đang học",
    moreCount: (n) => `+${n} môn`,
    none: "Không có",
    viewRecord: "Xem tiến độ học tập",
    academicUnavailable: "Hiện chưa tải được dữ liệu học tập.",
    recommended: "Gợi ý cho bạn",
    recommendedSub: "Dựa trên lịch học, phiếu hỗ trợ và thông báo gần đây của bạn",
    activeTickets: "Phiếu đang mở",
    todayScheduleTitle: "Lịch hôm nay",
    nextClass: "Lớp kế tiếp",
    startsSoon: "Sắp bắt đầu",
    nowLabel: "Đang diễn ra",
    completed: "Đã xong",
    instructorPrefix: "Giảng viên",
    viewFullSchedule: "Xem lịch đầy đủ",
    monthScheduleTitle: "Lịch học tháng này",
    classesThisMonth: (n) => `${n} buổi học trong tháng này`,
    noClassesThisMonth: "Không có lớp học nào trong tháng này.",
    scheduleUnavailable: "Hiện chưa tải được lịch học.",
    upcomingEvents: "Sự kiện sắp tới",
    noUpcomingEvents: "Không có sự kiện sắp tới.",
    allDay: "Cả ngày",
    details: "Chi tiết",
    dueToday: "Đến hạn hôm nay",
    dueInDays: (n) => `Còn ${n} ngày`,
    askAnything: "Hỏi Vinnie bất cứ điều gì về việc học của bạn",
    updated: (rel) => `Cập nhật ${rel}`,
    justNow: "vừa xong",
    hoursAgo: (h) => `${h} giờ trước`,
    daysAgo: (d) => `${d} ngày trước`,
  },
};

function relTime(iso: string, s: (typeof STR)[Lang]): string {
  const diff = Date.now() - new Date(iso).getTime();
  const h = Math.round(diff / 3_600_000);
  if (h < 1) return s.justNow;
  if (h < 24) return s.hoursAgo(h);
  return s.daysAgo(Math.round(h / 24));
}

function meetingSub(m: AcademicScheduleEvent): string {
  return [
    m.section_code ? `${m.course_code} · ${m.section_code}` : m.course_code,
    [m.room_name, m.building].filter(Boolean).join(", "),
  ]
    .filter(Boolean)
    .join(" · ");
}

export default function StudentDashboardPage() {
  const { p, lang } = usePortal();
  const s = STR[lang];
  const locale = lang === "vi" ? "vi-VN" : "en-US";
  const { user, token } = useAuth();
  const router = useRouter();

  // Local clock for time-aware schedule states. Starts null so SSR and the first client render
  // agree (no hydration mismatch); set on mount, then re-ticks every minute.
  const [now, setNow] = useState<Date | null>(null);
  useEffect(() => {
    setNow(new Date());
    const id = setInterval(() => setNow(new Date()), 60_000);
    return () => clearInterval(id);
  }, []);

  const clock = now ?? new Date();
  const monthKey = monthKeyOf(clock); // stable within a month → no needless refetch on each tick

  const profile = useAsync(() => getStudentProfile(), [token]);
  const academic = useAsync(() => getAcademicOverview(), [token]);
  const monthly = useAsync(() => getMonthlySchedule(monthKey), [token, monthKey]);
  const deadlines = useAsync(() => getStudentDeadlines(), [token]);
  const tickets = useAsync(() => getSupportTickets(), [token]);
  const calendar = useAsync(() => getStudentCalendar(), [token]);
  const suggestedQuestions = useAsync(() => getActiveSuggestedQuestions(lang), [lang, token]);

  const go = (q: string) => router.push(`/student/chat?q=${encodeURIComponent(q)}`);

  const pr = profile.status === "success" ? profile.data : null;
  const ac = academic.status === "success" ? academic.data : null;
  const name = user?.name ?? pr?.preferred_name ?? "";

  // Prefer academic-record values (Phase 13B academic DB); fall back to the legacy profile.
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

  const activeTickets = (tickets.status === "success" ? tickets.data : [])
    .filter((t) => ACTIVE_STATUSES.includes(t.status) && !t.archived && !t.deleted)
    .slice(0, 3);
  const allActiveTickets = (tickets.status === "success" ? tickets.data : []).filter(
    (t) => ACTIVE_STATUSES.includes(t.status) && !t.archived && !t.deleted
  );
  const needsInputTicket = (tickets.status === "success" ? tickets.data : []).find(
    (t) =>
      (t.status === "waiting_for_student" || t.status === "waiting_on_student") &&
      !t.archived &&
      !t.deleted
  );

  const upcomingEvents = (calendar.status === "success" ? calendar.data : [])
    .filter((e) => e.type === "event" && new Date(e.start).getTime() >= Date.now())
    .sort((a, b) => new Date(a.start).getTime() - new Date(b.start).getTime())
    .slice(0, 3);
  const nextDeadline: Deadline | null =
    deadlines.status === "success" && deadlines.data[0] ? deadlines.data[0] : null;

  // ---- Suggestions (prefer backend contextual prompts, fall back to local cues) ----
  const recs: { icon: React.ReactNode; text: string; onClick: () => void; relatedHref?: string }[] = [];
  const addRec = (item: (typeof recs)[number]) => {
    if (recs.some((rec) => rec.text === item.text)) return;
    recs.push(item);
  };
  const liveSuggestions =
    suggestedQuestions.status === "success" ? suggestedQuestions.data.slice(0, 3) : [];
  liveSuggestions.forEach((question, index) => {
    const icon =
      index === 0 ? <IconChat size={18} /> : index === 1 ? <IconClock size={18} /> : <IconCap size={18} />;
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
  if (nextTodayMeeting) {
    addRec({
      icon: <IconCap size={18} />,
      text: `${nextTodayMeeting.course_code} — ${timeLabel(nextTodayMeeting.start_at, locale)}`,
      onClick: () => router.push("/student/schedule"),
    });
  }
  if (nextDeadline) {
    addRec({
      icon: <IconClock size={18} />,
      text: nextDeadline.title,
      onClick: () => go(`Tell me about the deadline: ${nextDeadline.title}`),
    });
  }
  if (needsInputTicket) {
    addRec({
      icon: <IconTicket size={18} />,
      text: needsInputTicket.subject,
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

  // ---- Today Focus items ----
  const dl = nextDeadline ? daysUntil(nextDeadline.due_at) : null;
  const nextEvent = upcomingEvents[0] ?? null;
  const startsSoon =
    nextTodayMeeting &&
    meetingState(nextTodayMeeting, clock) === "upcoming" &&
    new Date(nextTodayMeeting.start_at).getTime() - clock.getTime() <= 60 * 60_000;

  return (
    <div className="page-inner">
      <div className="dash-welcome">
        <h1 className="dash-welcome-title">
          {s.welcome}
          {name ? `, ${name}` : ""} 👋
        </h1>
        <p className="dash-welcome-sub">{p.productTagline}</p>
      </div>

      {/* Today Focus — full-width priority strip */}
      <section className="focus-strip" aria-label={s.todayFocus}>
        <FocusCard
          icon={<IconCap size={18} />}
          label={s.focusNextClass}
          detail={
            nextTodayMeeting
              ? `${timeLabel(nextTodayMeeting.start_at, locale)} · ${nextTodayMeeting.course_name}`
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

      <div className="dash-grid">
        {/* Left / main column */}
        <div className="dash-main">
          {/* Academic Snapshot */}
          <Card className="dash-card dash-card--academic">
            <div className="dash-section-head">
              <h2 className="dash-section-title">{s.academicSnapshot}</h2>
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

                <CourseChips title={s.currentlyStudying} courses={ac.enrolled_courses} none={s.none} more={s.moreCount} />
              </>
            )}
          </Card>

          {/* Suggestions for you */}
          <section className="dash-card dash-card--suggestions">
            <div className="dash-section-head dash-section-head--stacked">
              <div>
                <h2 className="dash-section-title">{s.recommended}</h2>
                <p className="dash-section-sub">{s.recommendedSub}</p>
              </div>
            </div>
            <div className="rec-strip rec-strip--stack">
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
          </section>

          {/* Open tickets */}
          <section className="dash-card dash-card--tickets">
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
                  <TicketCardLite key={t.id} t={t} lang={lang} onClick={() => router.push("/student/support")} />
                ))}
              </div>
            )}
          </section>
        </div>

        {/* Right / side column */}
        <div className="dash-rail">
          {/* Today's schedule / Next class */}
          <div className="rail-card dash-card dash-card--today">
            <div className="rail-head">
              <h3 className="rail-title">{s.todayScheduleTitle}</h3>
              <Link className="dash-viewall" href="/student/schedule">
                {s.viewFullSchedule} <IconArrow size={14} />
              </Link>
            </div>
            {monthly.status === "loading" ? (
              <p className="rail-empty">…</p>
            ) : monthly.status === "error" ? (
              <p className="rail-empty">{s.scheduleUnavailable}</p>
            ) : todayMeetings.length === 0 ? (
              <p className="rail-empty">{s.noClassesToday}</p>
            ) : (
              todayMeetings.map((m) => {
                const state = now ? meetingState(m, clock) : "upcoming";
                const isNext = m.id === nextTodayMeeting?.id;
                return (
                  <div key={m.id} className={`rail-sched-row state-${state}`}>
                    <span className="rail-time">{timeLabel(m.start_at, locale)}</span>
                    <div className="rail-sched-main">
                      <div className="rail-sched-title">
                        {m.course_name}
                        {state === "current" ? (
                          <span className="sched-badge now">
                            <span className="sched-dot" aria-hidden />
                            {s.nowLabel}
                          </span>
                        ) : isNext ? (
                          <span className="sched-badge next">
                            {startsSoon ? s.startsSoon : s.nextClass}
                          </span>
                        ) : state === "past" ? (
                          <span className="sched-badge past">{s.completed}</span>
                        ) : null}
                      </div>
                      <div className="rail-sched-sub">{meetingSub(m)}</div>
                      {m.instructor_name && (
                        <div className="rail-sched-sub">
                          {s.instructorPrefix}: {m.instructor_name}
                        </div>
                      )}
                    </div>
                  </div>
                );
              })
            )}
          </div>

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
                <p className="month-count">{s.classesThisMonth(monthMeetings.length)}</p>
                <div className="month-list">
                  {(upcomingMonth.length > 0 ? upcomingMonth : monthMeetings).slice(0, 4).map((m) => (
                    <div key={m.id} className="rail-sched-row">
                      <span className="rail-time rail-time--date">
                        {new Date(m.start_at).toLocaleDateString(locale, { day: "2-digit", month: "short" })}
                      </span>
                      <div className="rail-sched-main">
                        <div className="rail-sched-title">{m.course_name}</div>
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
          </div>

          {/* Upcoming events */}
          <section className="dash-card dash-card--events">
            <div className="rail-card">
              <div className="rail-head">
                <h3 className="rail-title">
                  <span className="rail-title-icon" aria-hidden>
                    <IconBell size={15} />
                  </span>
                  {s.upcomingEvents}
                </h3>
                <Link className="dash-viewall" href="/student/events">
                  {p.viewAll} <IconArrow size={14} />
                </Link>
              </div>
              {upcomingEvents.length === 0 ? (
                <p className="rail-empty">{s.noUpcomingEvents}</p>
              ) : (
                <div className="month-list">
                  {upcomingEvents.map((e) => (
                    <EventRowLite key={e.id} e={e} locale={locale} lang={lang} />
                  ))}
                </div>
              )}
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}

function Stat({ k, v }: { k: string; v: string }) {
  return (
    <div className="snapshot-stat">
      <div className="profile-field-k">{k}</div>
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
}: {
  title: string;
  courses: AcademicCourse[];
  none: string;
  more: (n: number) => string;
}) {
  const shown = courses.slice(0, MAX_CHIPS);
  const extra = courses.length - shown.length;
  return (
    <div className="snapshot-chips">
      <div className="profile-field-k" style={{ marginBottom: 8 }}>
        {title}
      </div>
      {courses.length === 0 ? (
        <p className="rail-empty" style={{ margin: 0 }}>
          {none}
        </p>
      ) : (
        <div className="chip-row">
          {shown.map((c) => (
            <span key={c.id} className="ah-chip neutral">
              {c.code}
            </span>
          ))}
          {extra > 0 && <span className="ah-chip neutral chip-more">{more(extra)}</span>}
        </div>
      )}
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
        {/* Owner/office only — never the raw ticket UUID. */}
        <div className="dash-ticket-meta">{t.department}</div>
        <div className="dash-ticket-title">{t.subject}</div>
        <p className="dash-ticket-desc">{t.body}</p>
        <div className="dash-ticket-time">{s.updated(relTime(t.updated_at, s))}</div>
      </div>
      <span className={`ah-chip ${TICKET_CHIP[t.status]}`}>{TICKET_STATUS_LABEL[lang][t.status]}</span>
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
    <div className="event-row event-row--compact">
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
    </div>
  );
}
