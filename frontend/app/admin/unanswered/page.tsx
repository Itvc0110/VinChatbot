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
import type {
  QuestionPriority,
  QuestionStatus,
  QuestionFailureReason,
} from "@/lib/portalTypes";
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
const REASON_LABEL: Record<QuestionFailureReason, string> = {
  no_verified_source: "No verified source",
  low_confidence: "Low confidence",
  out_of_scope: "Out of scope",
  ambiguous: "Ambiguous",
};

const FILTERS: { key: "all" | QuestionStatus; label: string }[] = [
  { key: "all", label: "All" },
  { key: "new", label: "New" },
  { key: "in_review", label: "In review" },
  { key: "forwarded", label: "Forwarded" },
  { key: "resolved", label: "Resolved" },
];

export default function UnansweredPage() {
  const questions = useAsync(getUnansweredQuestions, []);
  const [filter, setFilter] = useState<"all" | QuestionStatus>("all");

  return (
    <div className="page-inner">
      <SectionHeader
        title="Inbox"
        action={
          <div className="seg" role="group" aria-label="Filter by status">
            {FILTERS.map((f) => (
              <button
                key={f.key}
                className={`seg-opt ${filter === f.key ? "active" : ""}`}
                onClick={() => setFilter(f.key)}
              >
                {f.label}
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
                title="Nothing here"
                description="No questions match this filter."
              />
            );
          return (
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Question</th>
                    <th>Reason</th>
                    <th>Department</th>
                    <th>Priority</th>
                    <th>Status</th>
                    <th>Asked</th>
                    <th>Created</th>
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
                        <Badge tone="warning">{REASON_LABEL[q.reason]}</Badge>
                      </td>
                      <td className="td-sub">{q.suggested_department}</td>
                      <td>
                        <Badge tone={PRIORITY_TONE[q.priority]}>{q.priority}</Badge>
                      </td>
                      <td>
                        <Badge tone={STATUS_TONE[q.status]}>{q.status.replace("_", " ")}</Badge>
                      </td>
                      <td>{q.asked_count}×</td>
                      <td className="td-sub">{relativeTime(q.created_at)}</td>
                      <td>
                        <Link className="btn btn-outline btn-sm" href={`/admin/unanswered/${q.id}`}>
                          Resolve <IconArrow size={13} />
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
