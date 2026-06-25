"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { AsyncBoundary, EmptyState, Toast } from "@/components/ui/primitives";
import { useAsync } from "@/lib/useAsync";
import { usePortal } from "@/lib/portalI18n";
import { getUnansweredQuestions, resolveUnansweredQuestion } from "@/lib/api";
import { relativeTime } from "@/lib/format";
import type { QuestionStatus, UnansweredQuestion } from "@/lib/portalTypes";
import { IconInbox, IconArrow, IconCheck } from "@/components/shell/icons";

const STATUS_CHIP: Record<QuestionStatus, string> = {
  new: "info",
  in_review: "warning",
  forwarded: "neutral",
  resolved: "success",
};
const PRIORITY_CHIP: Record<"high" | "medium" | "low", string> = {
  high: "warning",
  medium: "info",
  low: "neutral",
};
const FILTER_KEYS: ("all" | QuestionStatus)[] = ["all", "new", "in_review", "forwarded", "resolved"];

function Stat({ value, label }: { value: number; label: string }) {
  return (
    <div className="astat">
      <div className="astat-top"><span className="astat-icon"><IconInbox size={18} /></span></div>
      <div className="astat-value">{value}</div>
      <div className="astat-label">{label}</div>
    </div>
  );
}

export default function UnansweredPage() {
  const { p, lang } = usePortal();
  const loaded = useAsync(getUnansweredQuestions, []);
  const [items, setItems] = useState<UnansweredQuestion[] | null>(null);
  const [filter, setFilter] = useState<"all" | QuestionStatus>("all");
  const [busyId, setBusyId] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  useEffect(() => {
    if (loaded.status === "success") setItems(loaded.data);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loaded.status]);

  const all = items ?? [];
  const counts = {
    new: all.filter((q) => q.status === "new").length,
    in_review: all.filter((q) => q.status === "in_review").length,
    resolved: all.filter((q) => q.status === "resolved").length,
  };
  const filtered = useMemo(
    () => (filter === "all" ? all : all.filter((q) => q.status === filter)),
    [all, filter]
  );

  function patch(id: string, status: QuestionStatus) {
    setItems((cur) => (cur ?? []).map((q) => (q.id === id ? { ...q, status } : q)));
  }

  async function act(q: UnansweredQuestion, action: "forward" | "mark_resolved") {
    setBusyId(q.id);
    try {
      const updated = await resolveUnansweredQuestion(q.id, {
        action,
        department: action === "forward" ? q.suggested_department : undefined,
      });
      patch(q.id, updated.status);
      setToast(action === "forward" ? "Forwarded to department." : "Marked resolved.");
    } catch {
      setToast("Action failed.");
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="page-inner">
      <div className="arev-summary">
        <Stat value={counts.new} label="New" />
        <Stat value={counts.in_review} label="In review" />
        <Stat value={counts.resolved} label="Resolved" />
      </div>

      <div className="arev-toolbar">
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
      </div>

      <AsyncBoundary state={loaded} onRetry={loaded.reload}>
        {() =>
          filtered.length === 0 ? (
            <EmptyState
              icon={<IconInbox size={28} />}
              title={p.admin.nothingHere}
              description={p.admin.noMatch}
            />
          ) : (
            <div className="arev-list">
              {filtered.map((q) => (
                <div key={q.id} className={`arev-card ${q.priority === "high" ? "urgent" : ""}`}>
                  <div className="arev-top">
                    <span className={`ah-chip ${STATUS_CHIP[q.status]}`}>
                      {p.enums.questionStatus[q.status]}
                    </span>
                    <span className={`ah-chip ${PRIORITY_CHIP[q.priority]}`}>
                      {p.enums.questionPriority[q.priority]}
                    </span>
                    <span className="ah-chip warning">{p.enums.questionReason[q.reason]}</span>
                    <span className="arev-time">{relativeTime(q.created_at, lang)}</span>
                  </div>

                  <h3 className="arev-q">{q.question}</h3>
                  <p className="arev-ctx">{q.student_context}</p>

                  <div className="arev-meta">
                    <span>Asked {q.asked_count}×</span>
                    <span>Suggested: {p.enums.department[q.suggested_department] ?? q.suggested_department}</span>
                  </div>

                  <div className="arev-actions">
                    <Link className="btn btn-primary btn-sm" href={`/admin/unanswered/${q.id}`}>
                      {p.admin.resolve} <IconArrow size={13} />
                    </Link>
                    {q.status !== "forwarded" && q.status !== "resolved" && (
                      <button
                        className="btn btn-outline btn-sm"
                        disabled={busyId === q.id}
                        onClick={() => act(q, "forward")}
                      >
                        Forward to department
                      </button>
                    )}
                    {q.status !== "resolved" && (
                      <button
                        className="btn btn-ghost btn-sm"
                        disabled={busyId === q.id}
                        onClick={() => act(q, "mark_resolved")}
                      >
                        <IconCheck size={13} /> Mark resolved
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )
        }
      </AsyncBoundary>

      {toast && <Toast message={toast} onClose={() => setToast(null)} />}
    </div>
  );
}
