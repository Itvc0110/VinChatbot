"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import {
  AsyncBoundary,
  Card,
  SectionHeader,
  StatCard,
  EmptyState,
} from "@/components/ui/primitives";
import { ClassSessionRow, DeadlineRow } from "@/components/portal/rows";
import { useAsync } from "@/lib/useAsync";
import { usePortal } from "@/lib/portalI18n";
import { useAuth } from "@/lib/auth";
import {
  getStudentProfile,
  getStudentSchedule,
  getStudentDeadlines,
  getTuitionStatus,
} from "@/lib/api";
import { formatVnd, daysUntil } from "@/lib/format";
import { IconArrow, IconWallet, IconClock, IconCap, IconChat } from "@/components/shell/icons";
import type { ScheduleDay } from "@/lib/portalTypes";

const DAY_ORDER: ScheduleDay[] = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
function todayShort(): ScheduleDay {
  return DAY_ORDER[(new Date().getDay() + 6) % 7];
}

export default function StudentDashboardPage() {
  const { p } = usePortal();
  const { user } = useAuth();
  const router = useRouter();
  const [draft, setDraft] = useState("");

  const profile = useAsync(getStudentProfile, []);
  const schedule = useAsync(getStudentSchedule, []);
  const deadlines = useAsync(getStudentDeadlines, []);
  const tuition = useAsync(getTuitionStatus, []);

  const go = (q: string) => router.push(`/student/chat?q=${encodeURIComponent(q)}`);
  const name = user?.name ?? (profile.status === "success" ? profile.data.preferred_name : "");

  return (
    <div className="page-inner">
      <div className="greeting-block">
        <h2 className="greeting-title">
          {p.greetingMorning}
          {name ? `, ${name}` : ""} 👋
        </h2>
        {profile.status === "success" && (
          <p className="greeting-sub">
            {profile.data.program} · {p.year} {profile.data.year} · {p.dash.studentId}{" "}
            {profile.data.student_id}
          </p>
        )}
      </div>

      <div className="hero-ask" style={{ margin: "16px 0 24px" }}>
        <h2>{p.askCta}</h2>
        <p>{p.askAnything}</p>
        <form
          className="hero-ask-field"
          onSubmit={(e) => {
            e.preventDefault();
            if (draft.trim()) go(draft.trim());
          }}
        >
          <input
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder={p.askAnything}
            aria-label={p.askCta}
          />
          <button className="btn btn-primary" type="submit">
            <IconChat size={16} /> {p.askCta}
          </button>
        </form>
      </div>

      <div className="grid grid-3" style={{ marginBottom: 8 }}>
        <AsyncBoundary state={tuition} onRetry={tuition.reload} rows={1}>
          {(t) => (
            <StatCard
              label={p.tuitionStatus}
              value={formatVnd(t.balance_vnd)}
              hint={p.dash.paidOf(formatVnd(t.total_paid_vnd), formatVnd(t.total_charged_vnd))}
              tone={t.balance_vnd > 0 ? "gold" : "success"}
              icon={<IconWallet size={18} />}
            />
          )}
        </AsyncBoundary>

        <AsyncBoundary state={deadlines} onRetry={deadlines.reload} rows={1}>
          {(list) => {
            const thisWeek = list.filter((d) => {
              const n = daysUntil(d.due_at);
              return n >= 0 && n <= 7;
            });
            return (
              <StatCard
                label={p.upcomingDeadlines}
                value={thisWeek.length}
                hint={p.dash.dueNext7}
                tone={thisWeek.length > 0 ? "warning" : "success"}
                icon={<IconClock size={18} />}
              />
            );
          }}
        </AsyncBoundary>

        <AsyncBoundary state={profile} onRetry={profile.reload} rows={1}>
          {(pr) => (
            <StatCard
              label={p.dash.gpaCredits}
              value={pr.gpa.toFixed(2)}
              hint={p.dash.creditsEarned(pr.credits_earned, pr.credits_required)}
              tone="default"
              icon={<IconCap size={18} />}
            />
          )}
        </AsyncBoundary>
      </div>

      <div className="grid cols-2-1" style={{ marginTop: 16 }}>
        <Card>
          <SectionHeader title={p.todaySchedule} />
          <AsyncBoundary state={schedule} onRetry={schedule.reload}>
            {(all) => {
              const today = todayShort();
              let day = today;
              let items = all.filter((s) => s.day === day);
              if (items.length === 0) {
                const upcoming = DAY_ORDER.slice(DAY_ORDER.indexOf(today) + 1)
                  .concat(DAY_ORDER)
                  .find((d) => all.some((s) => s.day === d));
                if (upcoming) {
                  day = upcoming;
                  items = all.filter((s) => s.day === day);
                }
              }
              if (items.length === 0) return <EmptyState title={p.dash.noClasses} />;
              const sorted = [...items].sort((a, b) => a.start.localeCompare(b.start));
              return (
                <>
                  {day !== today && (
                    <p className="td-sub" style={{ marginTop: -4 }}>
                      {p.dash.nextClassDay(p.dayFull[day])}
                    </p>
                  )}
                  {sorted.map((s) => (
                    <ClassSessionRow key={s.id} s={s} />
                  ))}
                </>
              );
            }}
          </AsyncBoundary>
        </Card>

        <Card>
          <SectionHeader
            title={p.upcomingDeadlines}
            action={
              <a className="btn btn-ghost btn-sm" href="/student/schedule">
                {p.viewAll} <IconArrow size={14} />
              </a>
            }
          />
          <AsyncBoundary state={deadlines} onRetry={deadlines.reload}>
            {(list) =>
              list.length === 0 ? (
                <EmptyState title={p.empty} />
              ) : (
                <>
                  {list.slice(0, 4).map((d) => (
                    <DeadlineRow key={d.id} d={d} />
                  ))}
                </>
              )
            }
          </AsyncBoundary>
        </Card>
      </div>

      <SectionHeader title={p.suggestedQuestions} />
      <div className="qchips">
        {p.dash.suggested.map((q) => (
          <button key={q} className="qchip" onClick={() => go(q)}>
            <IconChat size={14} /> {q}
          </button>
        ))}
      </div>
    </div>
  );
}
