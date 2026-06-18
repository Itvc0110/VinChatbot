"use client";

import { useState } from "react";
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
import { getSupportTickets, forwardToAdmin } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import type { SupportTicket, TicketStatus } from "@/lib/portalTypes";
import { IconTicket } from "@/components/shell/icons";

const STATUS_TONE: Record<TicketStatus, BadgeTone> = {
  open: "info",
  in_progress: "warning",
  answered: "success",
  closed: "neutral",
};

const DEPARTMENTS = [
  "Office of the Registrar",
  "Student Financial Services",
  "Office of Financial Aid",
  "Student Affairs",
  "Academic Advising",
  "IT Help Desk",
];

function TicketCard({ t }: { t: SupportTicket }) {
  const { lang } = usePortal();
  const locale = lang === "vi" ? "vi-VN" : "en-US";
  return (
    <Card style={{ marginBottom: 12 }}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
        <div style={{ minWidth: 0 }}>
          <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
            <span className="td-sub mono">{t.id}</span>
            <Badge tone={STATUS_TONE[t.status]}>{t.status.replace("_", " ")}</Badge>
            {t.priority === "high" && <Badge tone="danger">high priority</Badge>}
          </div>
          <div className="list-row-title" style={{ marginTop: 6 }}>
            {t.subject}
          </div>
          <div className="list-row-sub">
            {t.department} · opened {formatDateTime(t.created_at, locale)}
          </div>
        </div>
      </div>
      <p style={{ fontSize: "var(--fs-sm)", color: "var(--muted-foreground)", margin: "10px 0 0" }}>
        {t.body}
      </p>
      {t.origin_question && (
        <p className="td-sub" style={{ marginTop: 8 }}>
          ↳ Forwarded from chat: “{t.origin_question}”
        </p>
      )}
      {t.resolution && (
        <div className="route-card" style={{ marginTop: 10 }}>
          <h3>✓ Resolution</h3>
          <p style={{ margin: 0 }}>{t.resolution}</p>
        </div>
      )}
    </Card>
  );
}

export default function StudentSupportPage() {
  const { p } = usePortal();
  const tickets = useAsync(getSupportTickets, []);
  const [toast, setToast] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [department, setDepartment] = useState(DEPARTMENTS[0]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!subject.trim() || !body.trim()) return;
    setSubmitting(true);
    try {
      const ticket = await forwardToAdmin({ subject: subject.trim(), body: body.trim(), department });
      setToast(`Ticket ${ticket.id} created — ${department} will follow up.`);
      setSubject("");
      setBody("");
      tickets.reload();
    } catch {
      setToast("Couldn't submit the ticket. Try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="page-inner">
      <div className="grid cols-2-1">
        <div>
          <SectionHeader title="Your tickets & forwarded questions" />
          <AsyncBoundary state={tickets} onRetry={tickets.reload}>
            {(list) =>
              list.length === 0 ? (
                <EmptyState
                  icon={<IconTicket size={28} />}
                  title="No tickets yet"
                  description="Questions you forward to admin from the chat will show up here."
                />
              ) : (
                <>
                  {list.map((t) => (
                    <TicketCard key={t.id} t={t} />
                  ))}
                </>
              )
            }
          </AsyncBoundary>
        </div>

        <Card as="section" className="pad-lg">
          <SectionHeader title="New support request" />
          <form className="form-grid" onSubmit={submit}>
            <div className="field">
              <label className="field-label" htmlFor="t-subject">
                Subject
              </label>
              <input
                id="t-subject"
                className="input"
                value={subject}
                onChange={(e) => setSubject(e.target.value)}
                placeholder="e.g. Scholarship renewal criteria"
              />
            </div>
            <div className="field">
              <label className="field-label" htmlFor="t-dept">
                Department
              </label>
              <select
                id="t-dept"
                className="select"
                value={department}
                onChange={(e) => setDepartment(e.target.value)}
              >
                {DEPARTMENTS.map((d) => (
                  <option key={d} value={d}>
                    {d}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label className="field-label" htmlFor="t-body">
                Details
              </label>
              <textarea
                id="t-body"
                className="textarea"
                value={body}
                onChange={(e) => setBody(e.target.value)}
                placeholder="Describe what you need help with…"
              />
            </div>
            <button
              className="btn btn-primary"
              type="submit"
              disabled={submitting || !subject.trim() || !body.trim()}
            >
              {submitting ? "Submitting…" : "Submit ticket"}
            </button>
          </form>
        </Card>
      </div>

      {toast && <Toast message={toast} onClose={() => setToast(null)} />}
    </div>
  );
}
