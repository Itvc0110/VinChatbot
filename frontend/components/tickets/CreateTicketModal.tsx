"use client";

import { useEffect, useState } from "react";
import type { TicketCategory, TicketDraft } from "@/lib/portalTypes";
import { useChat } from "@/lib/chat";
import { usePortal, DEPARTMENTS } from "@/lib/portalI18n";

const CATEGORIES: TicketCategory[] = [
  "academic",
  "schedule",
  "student_services",
  "technical",
  "other",
];

const STR = {
  en: {
    submit: "Submit",
    sending: "Submitting…",
    attachHint: "Attach a file (optional)",
    chooseFiles: "Add files",
    removeFile: "Remove",
  },
  vi: {
    submit: "Gửi",
    sending: "Đang gửi…",
    attachHint: "Đính kèm tệp (tuỳ chọn)",
    chooseFiles: "Thêm tệp",
    removeFile: "Xoá",
  },
} as const;

// Student manual ticket intake. Students provide only Title, Category, and Description (priority
// and routing department are decided by staff, not the student), plus optional file attachments.
// The form is self-contained: Submit sends straight to admin and Save Draft stores it — both via
// the single api.submitTicket / saveTicketDraft paths in chat.tsx (no separate "review" step).
export function CreateTicketModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { p, lang } = usePortal();
  const s = STR[lang];
  const chat = useChat();

  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [category, setCategory] = useState<TicketCategory>("academic");
  const [files, setFiles] = useState<File[]>([]);

  // Reset the intake whenever the modal is (re)opened, and wire Esc-to-close.
  useEffect(() => {
    if (!open) return;
    setSubject("");
    setBody("");
    setCategory("academic");
    setFiles([]);
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  function addFiles(list: FileList | null) {
    if (!list || list.length === 0) return;
    setFiles((cur) => [...cur, ...Array.from(list)]);
  }
  function removeFile(idx: number) {
    setFiles((cur) => cur.filter((_, i) => i !== idx));
  }

  // The backend ticket contract has no file-upload field yet, so attachments are recorded by
  // name in the description (so admins see what was referenced) rather than silently dropped.
  function buildDraft(): TicketDraft {
    const text = body.trim();
    const names = files.map((f) => f.name);
    const withAttachments = names.length
      ? `${text}${text ? "\n\n" : ""}Attachments: ${names.join(", ")}`
      : text;
    return {
      id: `draft-${Date.now()}`,
      subject: subject.trim(),
      body: withAttachments,
      department: DEPARTMENTS[0],
      category,
      priority: "medium",
      include_chat_context: false,
      context_preview: "",
    };
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!subject.trim() || !body.trim() || chat.draftBusy) return;
    const ok = await chat.submitDraft(buildDraft());
    if (ok) onClose();
  }

  async function onSaveDraft() {
    if (chat.draftBusy) return;
    const ok = await chat.saveDraft(buildDraft());
    if (ok) onClose();
  }

  const hasContent = subject.trim().length > 0 || body.trim().length > 0;

  return (
    <>
      <div
        className={`detail-scrim ${open ? "open" : ""}`}
        onClick={onClose}
        aria-hidden="true"
      />
      <aside
        className={`detail-drawer wide ${open ? "open" : ""}`}
        aria-hidden={!open}
        role="dialog"
        aria-label={p.tickets.newTicket}
      >
        {open && (
          <>
            <div className="detail-head">
              <span className="td-strong">{p.tickets.newTicket}</span>
              <button
                className="source-drawer-close"
                onClick={onClose}
                aria-label={p.review.close}
                title={p.review.close}
              >
                ✕
              </button>
            </div>

            <div className="detail-body">
              <p className="review-banner">{p.tickets.createIntro}</p>

              <form className="form-grid" onSubmit={onSubmit}>
                <div className="field">
                  <label className="field-label" htmlFor="ct-summary">
                    {p.review.summary}
                  </label>
                  <input
                    id="ct-summary"
                    className="input"
                    value={subject}
                    onChange={(e) => setSubject(e.target.value)}
                    placeholder={p.review.summaryPlaceholder}
                  />
                </div>

                <div className="field">
                  <label className="field-label" htmlFor="ct-category">
                    {p.review.category}
                  </label>
                  <select
                    id="ct-category"
                    className="select"
                    value={category}
                    onChange={(e) => setCategory(e.target.value as TicketCategory)}
                  >
                    {CATEGORIES.map((c) => (
                      <option key={c} value={c}>
                        {p.enums.ticketCategory[c]}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="field">
                  <label className="field-label" htmlFor="ct-description">
                    {p.review.description}
                  </label>
                  <textarea
                    id="ct-description"
                    className="textarea"
                    value={body}
                    onChange={(e) => setBody(e.target.value)}
                    placeholder={p.review.descriptionPlaceholder}
                  />
                </div>

                <div className="field">
                  <div className="field-label">{p.review.attachments}</div>
                  <label className="ticket-attach-btn">
                    <svg viewBox="0 0 24 24" width="15" height="15" fill="none"
                      stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"
                      strokeLinejoin="round" aria-hidden="true">
                      <path d="M21.44 11.05l-9.19 9.19a5 5 0 0 1-7.07-7.07l9.19-9.19a3 3 0 0 1 4.24 4.24l-9.2 9.19a1 1 0 0 1-1.41-1.41l8.49-8.49" />
                    </svg>
                    {s.chooseFiles}
                    <input
                      type="file"
                      multiple
                      className="ticket-attach-input"
                      onChange={(e) => {
                        addFiles(e.target.files);
                        e.target.value = "";
                      }}
                    />
                  </label>
                  {files.length === 0 ? (
                    <p className="field-hint">{s.attachHint}</p>
                  ) : (
                    <ul className="ticket-attach-list">
                      {files.map((f, i) => (
                        <li key={`${f.name}-${i}`} className="ticket-attach-chip">
                          <span className="ticket-attach-name">{f.name}</span>
                          <button
                            type="button"
                            className="ticket-attach-remove"
                            onClick={() => removeFile(i)}
                            aria-label={`${s.removeFile} ${f.name}`}
                            title={s.removeFile}
                          >
                            ✕
                          </button>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>

                <div className="review-actions">
                  <button
                    className="btn btn-ghost"
                    type="button"
                    onClick={onClose}
                    disabled={chat.draftBusy}
                  >
                    {p.review.cancel}
                  </button>
                  <button
                    className="btn btn-outline"
                    type="button"
                    onClick={onSaveDraft}
                    disabled={chat.draftBusy || !hasContent}
                  >
                    {p.review.saveDraft}
                  </button>
                  <button
                    className="btn btn-primary"
                    type="submit"
                    disabled={chat.draftBusy || !subject.trim() || !body.trim()}
                  >
                    {chat.draftBusy ? s.sending : s.submit}
                  </button>
                </div>
              </form>
            </div>
          </>
        )}
      </aside>
    </>
  );
}
