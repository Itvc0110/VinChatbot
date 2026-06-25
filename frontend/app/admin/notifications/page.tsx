"use client";

import { useEffect, useState } from "react";
import { AsyncBoundary, EmptyState, Toast } from "@/components/ui/primitives";
import { useAsync } from "@/lib/useAsync";
import { usePortal } from "@/lib/portalI18n";
import {
  getAdminNotifications,
  createNotification,
  generateSuggestedQuestions,
} from "@/lib/api";
import { relativeTime } from "@/lib/format";
import type {
  Notification,
  NotificationType,
  NotificationPriority,
  SuggestedQuestion,
} from "@/lib/portalTypes";
import { IconBell } from "@/components/shell/icons";

const CATEGORIES: NotificationType[] = ["academic", "schedule", "deadline", "event", "student_services", "system"];
const PRIORITIES: NotificationPriority[] = ["low", "medium", "high", "urgent"];
const STATUS_CHIP: Record<string, string> = { published: "success", draft: "neutral", archived: "neutral" };

export default function AdminNotificationsPage() {
  const { p, lang } = usePortal();
  const loaded = useAsync(getAdminNotifications, []);
  const [items, setItems] = useState<Notification[] | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  const [title, setTitle] = useState("");
  const [message, setMessage] = useState("");
  const [category, setCategory] = useState<NotificationType>("deadline");
  const [priority, setPriority] = useState<NotificationPriority>("medium");
  const [audience, setAudience] = useState("");
  const [eventDate, setEventDate] = useState("");
  const [deadline, setDeadline] = useState("");
  const [candidates, setCandidates] = useState<SuggestedQuestion[]>([]);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (loaded.status === "success") setItems((cur) => cur ?? loaded.data);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loaded.status]);

  const all = items ?? [];

  async function generate() {
    const list = await generateSuggestedQuestions({
      type: category, title, message,
      deadline: deadline || undefined, event_date: eventDate || undefined, lang,
    });
    setCandidates(list);
  }
  const setCandidate = (id: string, patch: Partial<SuggestedQuestion>) =>
    setCandidates((cur) => cur.map((c) => (c.id === id ? { ...c, ...patch } : c)));
  const approvedCount = candidates.filter((c) => c.approved_by_admin).length;

  async function save(status: "draft" | "published") {
    if (!title.trim() || !message.trim()) return;
    setBusy(true);
    try {
      const questions = candidates.map((c) => ({ ...c, is_active: status === "published" && c.approved_by_admin }));
      const created = await createNotification({
        title, message, type: category, priority,
        target_audience: audience ? audience.split(",").map((s) => s.trim()).filter(Boolean) : undefined,
        deadline: deadline || undefined, event_date: eventDate || undefined,
        status, suggested_questions: questions,
      });
      setItems((cur) => [created, ...(cur ?? [])]);
      setToast(status === "published" ? p.adminNotif.publishedToast : p.adminNotif.draftCreated);
      setTitle(""); setMessage(""); setAudience(""); setEventDate(""); setDeadline(""); setCandidates([]);
    } catch {
      setToast(p.adminNotif.actionFailed);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="page-inner">
      <div className="anotif-grid">
        {/* LEFT — broadcast list */}
        <div>
          <div className="acard-head"><h2 className="acard-title">{p.adminNotif.listHeading}</h2></div>
          <AsyncBoundary state={loaded} onRetry={loaded.reload}>
            {() =>
              all.length === 0 ? (
                <EmptyState icon={<IconBell size={28} />} title={p.adminNotif.listHeading} />
              ) : (
                <div className="anotif-list">
                  {all.map((n) => {
                    const st = n.status ?? "published";
                    return (
                      <div key={n.id} className="anotif-card">
                        <div className="anotif-card-top">
                          <span className={`ah-chip ${STATUS_CHIP[st] ?? "neutral"}`}>{st === "published" ? "Sent" : st}</span>
                          <span className="ah-chip neutral">{p.enums.notificationType[n.type]}</span>
                          {n.target_audience && n.target_audience.length > 0 && (
                            <span className="ah-chip info">{n.target_audience.join(", ")}</span>
                          )}
                          <span className="anotif-card-time">{relativeTime(n.updated_at ?? n.created_at, lang)}</span>
                        </div>
                        <h3 className="anotif-card-title">{n.title}</h3>
                        <p className="anotif-card-msg">{n.message}</p>
                      </div>
                    );
                  })}
                </div>
              )
            }
          </AsyncBoundary>
        </div>

        {/* RIGHT — composer + preview */}
        <div className="anotif-composer">
          <div className="acard">
            <div className="acard-head"><h2 className="acard-title">{p.adminNotif.createHeading}</h2></div>
            <div className="form-grid">
              <div className="field">
                <label className="field-label" htmlFor="n-title">{p.adminNotif.fTitle}</label>
                <input id="n-title" className="input" value={title} onChange={(e) => setTitle(e.target.value)} placeholder={p.adminNotif.fTitlePlaceholder} />
              </div>
              <div className="field">
                <label className="field-label" htmlFor="n-message">{p.adminNotif.fMessage}</label>
                <textarea id="n-message" className="textarea" value={message} onChange={(e) => setMessage(e.target.value)} placeholder={p.adminNotif.fMessagePlaceholder} />
              </div>
              <div className="grid cols-2" style={{ gap: 12 }}>
                <div className="field">
                  <label className="field-label" htmlFor="n-category">{p.adminNotif.fCategory}</label>
                  <select id="n-category" className="select" value={category} onChange={(e) => setCategory(e.target.value as NotificationType)}>
                    {CATEGORIES.map((c) => <option key={c} value={c}>{p.enums.notificationType[c]}</option>)}
                  </select>
                </div>
                <div className="field">
                  <label className="field-label" htmlFor="n-priority">{p.adminNotif.fPriority}</label>
                  <select id="n-priority" className="select" value={priority} onChange={(e) => setPriority(e.target.value as NotificationPriority)}>
                    {PRIORITIES.map((pr) => <option key={pr} value={pr}>{pr}</option>)}
                  </select>
                </div>
              </div>
              <div className="grid cols-2" style={{ gap: 12 }}>
                <div className="field">
                  <label className="field-label" htmlFor="n-deadline">{p.adminNotif.fDeadline}</label>
                  <input id="n-deadline" type="date" className="input" value={deadline} onChange={(e) => setDeadline(e.target.value)} />
                </div>
                <div className="field">
                  <label className="field-label" htmlFor="n-event">{p.adminNotif.fEventDate}</label>
                  <input id="n-event" type="date" className="input" value={eventDate} onChange={(e) => setEventDate(e.target.value)} />
                </div>
              </div>
              <div className="field">
                <label className="field-label" htmlFor="n-audience">{p.adminNotif.fAudience}</label>
                <input id="n-audience" className="input" value={audience} onChange={(e) => setAudience(e.target.value)} placeholder="CS, Year 2" />
              </div>

              <button className="btn btn-outline" type="button" onClick={() => void generate()} disabled={busy}>
                {candidates.length > 0 ? p.adminNotif.regenerate : p.adminNotif.generate}
              </button>

              <div className="field">
                <div className="field-label">{p.adminNotif.suggestedHeading}</div>
                {candidates.length === 0 ? (
                  <p className="td-sub">{p.adminNotif.noQuestions}</p>
                ) : (
                  <>
                    <p className="td-sub" style={{ marginTop: 0 }}>{p.adminNotif.suggestedHint}</p>
                    <div className="sq-review">
                      {candidates.map((c) => (
                        <div key={c.id} className="sq-row">
                          <span className="ah-chip info">{p.adminNotif.phase[c.trigger_phase]}</span>
                          <input className="input" value={c.question_text} onChange={(e) => setCandidate(c.id, { question_text: e.target.value })} />
                          <label className="review-check">
                            <input type="checkbox" checked={c.approved_by_admin} onChange={(e) => setCandidate(c.id, { approved_by_admin: e.target.checked })} />
                            <span>{c.approved_by_admin ? p.adminNotif.approved : p.adminNotif.approve}</span>
                          </label>
                        </div>
                      ))}
                    </div>
                  </>
                )}
              </div>

              <div className="review-actions">
                <button className="btn btn-outline" type="button" onClick={() => void save("draft")} disabled={busy || !title.trim() || !message.trim()}>
                  {p.adminNotif.saveDraftBtn}
                </button>
                <button className="btn btn-primary" type="button" onClick={() => void save("published")} disabled={busy || !title.trim() || !message.trim() || approvedCount === 0} title={approvedCount === 0 ? p.adminNotif.publishHint : undefined}>
                  {busy ? p.adminNotif.publishing : p.adminNotif.publish}
                </button>
              </div>
              {approvedCount === 0 && <p className="td-sub">{p.adminNotif.publishHint}</p>}
            </div>
          </div>

          {/* Live preview */}
          <div className="acard">
            <div className="acard-head"><h2 className="acard-title">Preview</h2></div>
            <div className="anotif-preview-frame">
              <div className="anotif-preview-card">
                <span className="anotif-preview-ic"><IconBell size={16} /></span>
                <div style={{ minWidth: 0 }}>
                  <div className="anotif-preview-title">{title.trim() || "Notification title"}</div>
                  <div className="anotif-preview-msg">{message.trim() || "Your message preview appears here as students will see it."}</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {toast && <Toast message={toast} onClose={() => setToast(null)} />}
    </div>
  );
}
