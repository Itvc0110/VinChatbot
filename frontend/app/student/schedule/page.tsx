"use client";

import { AsyncBoundary, Card, SectionHeader, EmptyState } from "@/components/ui/primitives";
import { ClassSessionRow, DeadlineRow } from "@/components/portal/rows";
import { useAsync } from "@/lib/useAsync";
import { usePortal } from "@/lib/portalI18n";
import { getStudentSchedule, getStudentDeadlines } from "@/lib/api";
import type { ScheduleDay } from "@/lib/portalTypes";
import { IconCalendar } from "@/components/shell/icons";

const DAY_ORDER: ScheduleDay[] = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

export default function StudentSchedulePage() {
  const { p } = usePortal();
  const schedule = useAsync(getStudentSchedule, []);
  const deadlines = useAsync(getStudentDeadlines, []);

  return (
    <div className="page-inner">
      <div className="grid cols-2-1">
        <Card>
          <SectionHeader title={p.sched.weekly} />
          <AsyncBoundary state={schedule} onRetry={schedule.reload}>
            {(all) =>
              all.length === 0 ? (
                <EmptyState
                  icon={<IconCalendar size={28} />}
                  title={p.sched.noClassesTitle}
                  description={p.sched.noClassesDesc}
                />
              ) : (
                <>
                  {DAY_ORDER.filter((day) => all.some((s) => s.day === day)).map((day) => {
                    const items = all
                      .filter((s) => s.day === day)
                      .sort((a, b) => a.start.localeCompare(b.start));
                    return (
                      <div key={day}>
                        <div className="day-head">{p.dayFull[day]}</div>
                        {items.map((s) => (
                          <ClassSessionRow key={s.id} s={s} />
                        ))}
                      </div>
                    );
                  })}
                </>
              )
            }
          </AsyncBoundary>
        </Card>

        <Card>
          <SectionHeader title={p.upcomingDeadlines} />
          <AsyncBoundary state={deadlines} onRetry={deadlines.reload}>
            {(list) =>
              list.length === 0 ? (
                <EmptyState title={p.empty} />
              ) : (
                <>
                  {list.map((d) => (
                    <DeadlineRow key={d.id} d={d} />
                  ))}
                </>
              )
            }
          </AsyncBoundary>
        </Card>
      </div>
    </div>
  );
}
