"use client";

import { useEffect, useState } from "react";
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
import { usePortal, DEPARTMENTS } from "@/lib/portalI18n";
import { useAuth } from "@/lib/auth";
import { getUnansweredQuestions, resolveUnansweredQuestion } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import type { QuestionPriority, ResolveQuestionPayload } from "@/lib/portalTypes";
import { IconArrow } from "@/components/shell/icons";

const PRIORITY_TONE: Record<QuestionPriority, BadgeTone> = {
  high: "danger",
  medium: "warning",
  low: "neutral",
};

export default function QuestionDetailPage() {
  const { p, lang } = usePortal();
  const { token } = useAuth();
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const id = params.id;
  const locale = lang === "vi" ? "vi-VN" : "en-US";

  const all = useAsync(getUnansweredQuestions, [token]);
  const [toast, setToast] = useState<string | null>(null);
  const [working, setWorking] = useState<string | null>(null);

  const [answer, setAnswer] = useState("");
  const [addToKb, setAddToKb] = useState(true);
  const [department, setDepartment] = useState(DEPARTMENTS[0]);
  const [sourceUrl, setSourceUrl] = useState("");

  useEffect(() => {
    setToast(null);
    setWorking(null);
    setAnswer("");
    setAddToKb(true);
    setDepartment(DEPARTMENTS[0]);
    setSourceUrl("");
  }, [token]);

  async function act(
    action: ResolveQuestionPayload["action"],
    extra: Partial<ResolveQuestionPayload> = {}
  ) {
    setWorking(action);
    try {
      await resolveUnansweredQuestion(id, { action, ...extra });
      const msg: Record<typeof action, string> = {
        official_answer: addToKb ? p.admin.publishedKb : p.admin.published,
        forward: p.admin.forwardedTo(p.enums.department[department] ?? department),
        attach_source: p.admin.sourceAttached,
        mark_resolved: p.admin.markedResolved,
      };
      setToast(msg[action]);
      if (action === "official_answer" || action === "mark_resolved" || action === "forward") {
        setTimeout(() => router.push("/admin/unanswered"), 900);
      }
    } catch {
      setToast(p.admin.actionFailed);
    } finally {
      setWorking(null);
    }
  }

  return (
    <div className="page-inner" style={{ maxWidth: 920 }}>
      <a className="btn btn-ghost btn-sm" href="/admin/unanswered" style={{ marginBottom: 14 }}>
        {p.admin.backToInbox}
      </a>

      <AsyncBoundary state={all} onRetry={all.reload} rows={2}>
        {(list) => {
          const q = list.find((x) => x.id === id);
          if (!q)
            return (
              <EmptyState
                title={p.admin.notFound}
                description={p.admin.notFoundDesc}
              />
            );
          return (
            <>
              <Card className="pad-lg" style={{ marginBottom: 18 }}>
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 10 }}>
                  <Badge tone={PRIORITY_TONE[q.priority]}>
                    {p.admin.priorityLabel(p.enums.questionPriority[q.priority])}
                  </Badge>
                  <Badge tone="warning">{p.enums.questionReason[q.reason]}</Badge>
                  <Badge tone="info">{p.admin.askedTimes(q.asked_count)}</Badge>
                  <Badge tone="neutral">{p.enums.questionStatus[q.status]}</Badge>
                </div>
                <h2 style={{ margin: "0 0 8px", fontSize: "var(--fs-lg)" }}>{q.question}</h2>
                <div className="kv">
                  <span className="kv-key">{p.admin.studentContext}</span>
                  <span className="kv-val">{q.student_context}</span>
                </div>
                <div className="kv">
                  <span className="kv-key">{p.admin.suggestedDept}</span>
                  <span className="kv-val">
                    {p.enums.department[q.suggested_department] ?? q.suggested_department}
                  </span>
                </div>
                <div className="kv">
                  <span className="kv-key">{p.admin.firstAsked}</span>
                  <span className="kv-val">{formatDateTime(q.created_at, locale)}</span>
                </div>
              </Card>

              <div className="grid grid-2">
                <Card>
                  <SectionHeader title={p.admin.createAnswer} />
                  <div className="form-grid">
                    <textarea
                      className="textarea"
                      placeholder={p.admin.answerPlaceholder}
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
                      {p.admin.addToKb}
                    </label>
                    <button
                      className="btn btn-primary"
                      disabled={!answer.trim() || working !== null}
                      onClick={() =>
                        act("official_answer", { answer, add_to_knowledge_base: addToKb })
                      }
                    >
                      {working === "official_answer" ? p.admin.publishing : p.admin.publishAnswer}
                    </button>
                  </div>
                </Card>

                <Card>
                  <SectionHeader title={p.admin.routeOrAttach} />
                  <div className="form-grid">
                    <div className="field">
                      <label className="field-label" htmlFor="dept">
                        {p.admin.forwardToDept}
                      </label>
                      <div style={{ display: "flex", gap: 8 }}>
                        <select
                          id="dept"
                          className="select"
                          value={department}
                          onChange={(e) => setDepartment(e.target.value)}
                        >
                          {DEPARTMENTS.map((d) => (
                            <option key={d} value={d}>
                              {p.enums.department[d] ?? d}
                            </option>
                          ))}
                        </select>
                        <button
                          className="btn btn-outline"
                          disabled={working !== null}
                          onClick={() => act("forward", { department })}
                        >
                          {p.admin.forward} <IconArrow size={14} />
                        </button>
                      </div>
                    </div>

                    <div className="field">
                      <label className="field-label" htmlFor="src">
                        {p.admin.attachSource}
                      </label>
                      <div style={{ display: "flex", gap: 8 }}>
                        <input
                          id="src"
                          className="input"
                          placeholder={p.admin.urlPlaceholder}
                          value={sourceUrl}
                          onChange={(e) => setSourceUrl(e.target.value)}
                        />
                        <button
                          className="btn btn-outline"
                          disabled={!sourceUrl.trim() || working !== null}
                          onClick={() => act("attach_source", { source_url: sourceUrl })}
                        >
                          {p.admin.attach}
                        </button>
                      </div>
                    </div>

                    <button
                      className="btn btn-ghost"
                      disabled={working !== null}
                      onClick={() => act("mark_resolved")}
                      style={{ justifyContent: "flex-start" }}
                    >
                      {p.admin.markResolved}
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
