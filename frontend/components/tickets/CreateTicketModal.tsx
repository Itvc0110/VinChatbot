"use client";

import { useEffect, useState } from "react";
import type { TicketCategory, TicketPriority } from "@/lib/portalTypes";
import { useChat } from "@/lib/chat";
import { usePortal, DEPARTMENTS } from "@/lib/portalI18n";
import { Modal } from "@/components/ui/primitives";

const CATEGORIES: TicketCategory[] = [
  "academic",
  "schedule",
  "student_services",
  "technical",
  "other",
];
const PRIORITIES: TicketPriority[] = ["low", "medium", "high", "urgent"];

// PLAN23.6.01 manual create flow: a light intake form. "Continue to review" seeds a blank
// draft (chat.prepareBlankDraft) and closes — the globally-mounted ReviewTicketDrawer then
// opens for final edit + privacy opt-in + "Send to Admin". So a ticket is NEVER sent
// straight to admin: intake → review → send, all on the single submitTicket path.
export function CreateTicketModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { p } = usePortal();
  const chat = useChat();

  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [department, setDepartment] = useState(DEPARTMENTS[0]);
  const [category, setCategory] = useState<TicketCategory>("academic");
  const [priority, setPriority] = useState<TicketPriority>("medium");

  // Reset the intake whenever the modal is (re)opened.
  useEffect(() => {
    if (!open) return;
    setSubject("");
    setBody("");
    setDepartment(DEPARTMENTS[0]);
    setCategory("academic");
<<<<<<< Updated upstream
    setPriority("medium");
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);
=======
    setFiles([]);
  }, [open]);
>>>>>>> Stashed changes

  function continueToReview(e: React.FormEvent) {
    e.preventDefault();
    chat.prepareBlankDraft({
      subject: subject.trim(),
      body: body.trim(),
      department,
      category,
      priority,
    });
    onClose();
  }

  return (
    <Modal open={open} onClose={onClose} title={p.tickets.newTicket} size="lg">
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
            required
            maxLength={120}
          />
        </div>

<<<<<<< Updated upstream
              <form className="form-grid" onSubmit={continueToReview}>
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

                <div className="grid cols-2" style={{ gap: 12 }}>
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
                    <label className="field-label" htmlFor="ct-priority">
                      {p.review.priority}
                    </label>
                    <select
                      id="ct-priority"
                      className="select"
                      value={priority}
                      onChange={(e) => setPriority(e.target.value as TicketPriority)}
                    >
                      {PRIORITIES.map((pr) => (
                        <option key={pr} value={pr}>
                          {p.enums.ticketPriority[pr]}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>

                <div className="field">
                  <label className="field-label" htmlFor="ct-office">
                    {p.review.office}
                  </label>
                  <select
                    id="ct-office"
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

                <div className="review-actions">
                  <button className="btn btn-ghost" type="button" onClick={onClose}>
                    {p.review.cancel}
                  </button>
                  <button
                    className="btn btn-primary"
                    type="submit"
                    disabled={!subject.trim() && !body.trim()}
                  >
                    {p.tickets.continueReview}
                  </button>
                </div>
              </form>
            </div>
          </>
        )}
      </aside>
    </>
=======
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
            required
          />
        </div>

        <div className="field">
          <div className="field-label">{p.review.attachments}</div>
          <label className="ticket-attach-btn">
            <svg
              viewBox="0 0 24 24"
              width="15"
              height="15"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.8"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
            >
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
    </Modal>
>>>>>>> Stashed changes
  );
}
