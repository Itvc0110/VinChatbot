"use client";

import { useState } from "react";
import Link from "next/link";
import {
  AsyncBoundary,
  SectionHeader,
  Badge,
  EmptyState,
  type BadgeTone,
} from "@/components/ui/primitives";
import { useAsync } from "@/lib/useAsync";
import { usePortal } from "@/lib/portalI18n";
import { getUnansweredQuestions } from "@/lib/api";
import { relativeTime } from "@/lib/format";
import type { QuestionPriority, QuestionStatus } from "@/lib/portalTypes";
import { IconInbox, IconArrow } from "@/components/shell/icons";

const PRIORITY_TONE: Record<QuestionPriority, BadgeTone> = {
  high: "danger",
  medium: "warning",
  low: "neutral",
};
const STATUS_TONE: Record<QuestionStatus, BadgeTone> = {
  new: "info",
  in_review: "warning",
  forwarded: "neutral",
  resolved: "success",
};

const FILTER_KEYS: ("all" | QuestionStatus)[] = [
  "all",
  "new",
  "in_review",
  "forwarded",
  "resolved",
];

export default function UnansweredPage() {
  const { p, lang } = usePortal();
  const questions = useAsync(getUnansweredQuestions, []);
  const [filter, setFilter] = useState<"all" | QuestionStatus>("all");

  return (
    <div className="page-inner">
      <SectionHeader
        title={p.admin.inbox}
        action={
          <div className="seg" role="group" aria-label={p.admin.colStatus}>
            {FILTER_KEYS.map((key) => (
              <button
                key={key}
                className={`seg-opt ${filter === key ? "active" : ""}`}
                onClick={() => setFilter(key)}
              >
                {p.admin.filters[key]}
              </button>
            ))}
          </div>
        }
      />

      <AsyncBoundary state={questions} onRetry={questions.reload}>
        {(list) => {
          const filtered = filter === "all" ? list : list.filter((q) => q.status === filter);
          if (filtered.length === 0)
            return (
              <EmptyState
                icon={<IconInbox size={28} />}
                title={p.admin.nothingHere}
                description={p.admin.noMatch}
              />
            );
          return (
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>{p.admin.colQuestion}</th>
                    <th>{p.admin.colReason}</th>
                    <th>{p.admin.colDepartment}</th>
                    <th>{p.admin.colPriority}</th>
                    <th>{p.admin.colStatus}</th>
                    <th>{p.admin.colAsked}</th>
                    <th>{p.admin.colCreated}</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((q) => (
                    <tr key={q.id}>
                      <td style={{ maxWidth: 320 }}>
                        <div className="td-strong">{q.question}</div>
                        <div className="td-sub">{q.student_context}</div>
                      </td>
                      <td>
                        <Badge tone="warning">{p.enums.questionReason[q.reason]}</Badge>
                      </td>
                      <td className="td-sub">
                        {p.enums.department[q.suggested_department] ?? q.suggested_department}
                      </td>
                      <td>
                        <Badge tone={PRIORITY_TONE[q.priority]}>
                          {p.enums.questionPriority[q.priority]}
                        </Badge>
                      </td>
                      <td>
                        <Badge tone={STATUS_TONE[q.status]}>{p.enums.questionStatus[q.status]}</Badge>
                      </td>
                      <td>{q.asked_count}×</td>
                      <td className="td-sub">{relativeTime(q.created_at, lang)}</td>
                      <td>
                        <Link className="btn btn-outline btn-sm" href={`/admin/unanswered/${q.id}`}>
                          {p.admin.resolve} <IconArrow size={13} />
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          );
        }}
      </AsyncBoundary>
    </div>
  );
}
