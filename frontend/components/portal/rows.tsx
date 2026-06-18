"use client";

import type { ClassSession, Deadline, DeadlineKind } from "@/lib/portalTypes";
import { Badge, type BadgeTone } from "@/components/ui/primitives";
import { daysUntil, formatDate } from "@/lib/format";
import { usePortal } from "@/lib/portalI18n";
import { IconExternal } from "@/components/shell/icons";

// One class session as a list row with a time pill (used on dashboard + schedule).
export function ClassSessionRow({ s }: { s: ClassSession }) {
  return (
    <div className="list-row">
      <div className="time-pill">
        {s.start}
        <span className="to">{s.end}</span>
      </div>
      <div className="list-row-main">
        <div className="list-row-title">{s.course_title}</div>
        <div className="list-row-sub">
          {s.course_code} · {s.room}, {s.building} · {s.instructor}
        </div>
      </div>
    </div>
  );
}

const KIND_TONE: Record<DeadlineKind, BadgeTone> = {
  assignment: "info",
  exam: "danger",
  registration: "warning",
  tuition: "gold",
  administrative: "neutral",
};

// Maps days-left to a colored badge (today/overdue = urgent).
export function DeadlineRow({ d }: { d: Deadline }) {
  const { p, lang } = usePortal();
  const left = daysUntil(d.due_at);
  const tone: BadgeTone = left < 0 ? "danger" : left <= 2 ? "warning" : "neutral";
  const label =
    left < 0 ? p.overdue : left === 0 ? p.dueToday : p.daysLeft(left);

  return (
    <div className="list-row">
      <div className="list-row-main">
        <div className="list-row-title">{d.title}</div>
        <div className="list-row-sub">
          {d.course_code ? `${d.course_code} · ` : ""}
          {formatDate(d.due_at, lang === "vi" ? "vi-VN" : "en-US")}
          {d.source_title ? ` · ${d.source_title}` : ""}
        </div>
      </div>
      <div className="list-row-aside">
        <Badge tone={KIND_TONE[d.kind]}>{d.kind}</Badge>
        <Badge tone={tone}>{label}</Badge>
        {d.source_url && (
          <a
            className="td-sub"
            href={d.source_url}
            target="_blank"
            rel="noreferrer"
            title={p.openSource}
            style={{ display: "inline-flex", alignItems: "center", gap: 4 }}
          >
            <IconExternal size={12} /> {p.openSource}
          </a>
        )}
      </div>
    </div>
  );
}
