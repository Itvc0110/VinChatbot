"use client";

import { useEffect, useState } from "react";
import type { TicketCategory, TicketPriority } from "@/lib/portalTypes";
import { useChat } from "@/lib/chat";
import { usePortal, DEPARTMENTS } from "@/lib/portalI18n";

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

  // Reset the intake whenever the modal is (re)opened, and wire Esc-to-close.
  useEffect(() => {
    if (!open) return;
    setSubject("");
    setBody("");
    setDepartment(DEPARTMENTS[0]);
    setCategory("academic");
    setPriority("medium");
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

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
  );
}
