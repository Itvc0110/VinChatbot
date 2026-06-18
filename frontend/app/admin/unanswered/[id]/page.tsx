"use client";

import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  AsyncBoundary,
  Card,
  SectionHeader,
  Badge,
  EmptyState,
  Toast,
  type BadgeTone,
} from "@/components/ui/primitives";
import { useAsync } from "@/lib/useAsync";
import { usePortal } from "@/lib/portalI18n";
import { getUnansweredQuestions, resolveUnansweredQuestion } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import type { QuestionPriority, ResolveQuestionPayload } from "@/lib/portalTypes";
import { IconArrow } from "@/components/shell/icons";

const PRIORITY_TONE: Record<QuestionPriority, BadgeTone> = {
  high: "danger",
  medium: "warning",
  low: "neutral",
};

const DEPARTMENTS = [
  "Office of the Registrar",
  "Student Financial Services",
  "Office of Financial Aid",
  "Student Affairs",
  "Academic Advising",
];

export default function QuestionDetailPage() {
  const { lang } = usePortal();
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const id = params.id;
  const locale = lang === "vi" ? "vi-VN" : "en-US";

  const all = useAsync(getUnansweredQuestions, []);
  const [toast, setToast] = useState<string | null>(null);
  const [working, setWorking] = useState<string | null>(null);

  const [answer, setAnswer] = useState("");
  const [addToKb, setAddToKb] = useState(true);
  const [department, setDepartment] = useState(DEPARTMENTS[0]);
  const [sourceUrl, setSourceUrl] = useState("");

  async function act(
    action: ResolveQuestionPayload["action"],
    extra: Partial<ResolveQuestionPayload> = {}
  ) {
    setWorking(action);
    try {
      await resolveUnansweredQuestion(id, { action, ...extra });
      const msg: Record<typeof action, string> = {
        official_answer:
          "Official answer published" + (addToKb ? " and added to knowledge base." : "."),
        forward: `Forwarded to ${department}.`,
        attach_source: "Source attached to this question.",
        mark_resolved: "Marked as resolved.",
      };
      setToast(msg[action]);
      if (action === "official_answer" || action === "mark_resolved" || action === "forward") {
        setTimeout(() => router.push("/admin/unanswered"), 900);
      }
    } catch {
      setToast("Action failed. Try again.");
    } finally {
      setWorking(null);
    }
  }

  return (
    <div className="page-inner" style={{ maxWidth: 920 }}>
      <a className="btn btn-ghost btn-sm" href="/admin/unanswered" style={{ marginBottom: 14 }}>
        ← Back to inbox
      </a>

      <AsyncBoundary state={all} onRetry={all.reload} rows={2}>
        {(list) => {
          const q = list.find((x) => x.id === id);
          if (!q)
            return (
              <EmptyState
                title="Question not found"
                description="It may have been resolved or removed."
              />
            );
          return (
            <>
              <Card className="pad-lg" style={{ marginBottom: 18 }}>
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 10 }}>
                  <Badge tone={PRIORITY_TONE[q.priority]}>{q.priority} priority</Badge>
                  <Badge tone="warning">{q.reason.replace(/_/g, " ")}</Badge>
                  <Badge tone="info">{q.asked_count}× asked</Badge>
                  <Badge tone="neutral">{q.status.replace("_", " ")}</Badge>
                </div>
                <h2 style={{ margin: "0 0 8px", fontSize: "var(--fs-lg)" }}>{q.question}</h2>
                <div className="kv">
                  <span className="kv-key">Student context (anonymized)</span>
                  <span className="kv-val">{q.student_context}</span>
                </div>
                <div className="kv">
                  <span className="kv-key">Suggested department</span>
                  <span className="kv-val">{q.suggested_department}</span>
                </div>
                <div className="kv">
                  <span className="kv-key">First asked</span>
                  <span className="kv-val">{formatDateTime(q.created_at, locale)}</span>
                </div>
              </Card>

              <div className="grid grid-2">
                <Card>
                  <SectionHeader title="Create official answer" />
                  <div className="form-grid">
                    <textarea
                      className="textarea"
                      placeholder="Write a verified answer citing official policy…"
                      value={answer}
                      onChange={(e) => setAnswer(e.target.value)}
                    />
                    <label
                      style={{ display: "flex", gap: 8, alignItems: "center", fontSize: "var(--fs-sm)" }}
                    >
                      <input
                        type="checkbox"
                        checked={addToKb}
                        onChange={(e) => setAddToKb(e.target.checked)}
                      />
                      Add this answer to the knowledge base
                    </label>
                    <button
                      className="btn btn-primary"
                      disabled={!answer.trim() || working !== null}
                      onClick={() =>
                        act("official_answer", { answer, add_to_knowledge_base: addToKb })
                      }
                    >
                      {working === "official_answer" ? "Publishing…" : "Publish official answer"}
                    </button>
                  </div>
                </Card>

                <Card>
                  <SectionHeader title="Route or attach" />
                  <div className="form-grid">
                    <div className="field">
                      <label className="field-label" htmlFor="dept">
                        Forward to department
                      </label>
                      <div style={{ display: "flex", gap: 8 }}>
                        <select
                          id="dept"
                          className="select"
                          value={department}
                          onChange={(e) => setDepartment(e.target.value)}
                        >
                          {DEPARTMENTS.map((d) => (
                            <option key={d}>{d}</option>
                          ))}
                        </select>
                        <button
                          className="btn btn-outline"
                          disabled={working !== null}
                          onClick={() => act("forward", { department })}
                        >
                          Forward <IconArrow size={14} />
                        </button>
                      </div>
                    </div>

                    <div className="field">
                      <label className="field-label" htmlFor="src">
                        Attach official source
                      </label>
                      <div style={{ display: "flex", gap: 8 }}>
                        <input
                          id="src"
                          className="input"
                          placeholder="https://vinuni.edu.vn/…"
                          value={sourceUrl}
                          onChange={(e) => setSourceUrl(e.target.value)}
                        />
                        <button
                          className="btn btn-outline"
                          disabled={!sourceUrl.trim() || working !== null}
                          onClick={() => act("attach_source", { source_url: sourceUrl })}
                        >
                          Attach
                        </button>
                      </div>
                    </div>

                    <button
                      className="btn btn-ghost"
                      disabled={working !== null}
                      onClick={() => act("mark_resolved")}
                      style={{ justifyContent: "flex-start" }}
                    >
                      ✓ Mark as resolved
                    </button>
                  </div>
                </Card>
              </div>
            </>
          );
        }}
      </AsyncBoundary>

      {toast && <Toast message={toast} onClose={() => setToast(null)} />}
    </div>
  );
}
