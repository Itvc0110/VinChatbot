"use client";

import { useEffect } from "react";
import type { TicketCategory } from "@/lib/portalTypes";
import { useChat } from "@/lib/chat";
import { usePortal } from "@/lib/portalI18n";

const CATEGORIES: TicketCategory[] = [
  "academic",
  "schedule",
  "student_services",
  "technical",
  "other",
];

// PLAN22.6 Review Ticket drawer. Vinnie prepares a DRAFT (held in ChatProvider state); this
// drawer lets the student edit it and is the ONLY surface that submits a ticket to admin.
// Mounted once globally (StudentChatOverlays) so it overlays the full chat page, the floating
// widget, and the support page alike. Nothing here is persisted until "Send to Admin".
export function ReviewTicketDrawer() {
  const { p } = usePortal();
  const chat = useChat();
  const draft = chat.ticketDraft;
  const open = !!draft;
  const suggesting = chat.draftSuggesting;

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") chat.cancelDraft();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, chat]);

  return (
    <>
      <div
        className={`detail-scrim ${open ? "open" : ""}`}
        onClick={chat.cancelDraft}
        aria-hidden="true"
      />
      <aside
        className={`detail-drawer wide ${open ? "open" : ""}`}
        aria-hidden={!open}
        role="dialog"
        aria-label={p.review.banner}
      >
        {draft && (
          <>
            <div className="detail-head">
              <span className="td-strong">{p.actPrepareTicket}</span>
              <button
                className="source-drawer-close"
                onClick={chat.cancelDraft}
                aria-label={p.review.close}
                title={p.review.close}
              >
                ✕
              </button>
            </div>

            <div className="detail-body">
              {/* Prominent review-before-send disclaimer — the STUDENT sends it, not Vinnie. */}
              <div
                className="review-banner"
                role="note"
                style={{
                  display: "flex",
                  gap: "0.6rem",
                  alignItems: "flex-start",
                  borderLeft: "4px solid #d97706",
                  background: "#fffbeb",
                  color: "#7c2d12",
                  padding: "0.7rem 0.85rem",
                  borderRadius: "8px",
                }}
              >
                <span aria-hidden="true" style={{ fontSize: "1.1rem", lineHeight: 1.2 }}>
                  ⚠️
                </span>
                <div style={{ display: "flex", flexDirection: "column", gap: "0.35rem" }}>
                  {draft.created_by_ai && (
                    <span
                      style={{
                        alignSelf: "flex-start",
                        fontSize: "0.72rem",
                        fontWeight: 700,
                        textTransform: "uppercase",
                        letterSpacing: "0.03em",
                        background: "#d97706",
                        color: "#fff",
                        padding: "0.1rem 0.5rem",
                        borderRadius: "999px",
                      }}
                    >
                      {p.review.aiDraftedChip}
                    </span>
                  )}
                  <span style={{ fontWeight: 600 }}>{p.review.banner}</span>
                  {suggesting && (
                    <span style={{ fontStyle: "italic", opacity: 0.85 }}>{p.review.aiDrafting}</span>
                  )}
                </div>
              </div>

              <form
                className="form-grid"
                onSubmit={(e) => {
                  e.preventDefault();
                  void chat.submitDraft();
                }}
              >
                <div className="field">
                  <label className="field-label" htmlFor="rt-summary">
                    {p.review.summary}
                  </label>
                  <input
                    id="rt-summary"
                    className="input"
                    value={draft.subject}
                    onChange={(e) => chat.updateDraft({ subject: e.target.value })}
                    placeholder={p.review.summaryPlaceholder}
                    disabled={suggesting}
                  />
                </div>

                <div className="field">
                  <label className="field-label" htmlFor="rt-category">
                    {p.review.category}
                  </label>
                  <select
                    id="rt-category"
                    className="select"
                    value={draft.category}
                    onChange={(e) =>
                      chat.updateDraft({ category: e.target.value as TicketCategory })
                    }
                    disabled={suggesting}
                  >
                    {CATEGORIES.map((c) => (
                      <option key={c} value={c}>
                        {p.enums.ticketCategory[c]}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="field">
                  <label className="field-label" htmlFor="rt-description">
                    {p.review.description}
                  </label>
                  <textarea
                    id="rt-description"
                    className="textarea"
                    value={draft.body}
                    onChange={(e) => chat.updateDraft({ body: e.target.value })}
                    placeholder={p.review.descriptionPlaceholder}
                    disabled={suggesting}
                  />
                </div>

                {draft.context_preview && (
                  <div className="field">
                    <div className="field-label">{p.review.relatedContext}</div>
                    <pre className="review-context">{draft.context_preview}</pre>
                    <label className="review-check">
                      <input
                        type="checkbox"
                        checked={draft.include_chat_context}
                        onChange={(e) =>
                          chat.updateDraft({ include_chat_context: e.target.checked })
                        }
                      />
                      <span>
                        {p.review.includeContext}
                        <span className="review-check-help">{p.review.includeContextHelp}</span>
                      </span>
                    </label>
                  </div>
                )}

                <div className="field">
                  <div className="field-label">{p.review.attachments}</div>
                  <button className="btn btn-outline btn-sm" type="button" disabled>
                    {p.review.attachmentsLater}
                  </button>
                </div>

                <div className="review-actions">
                  <button
                    className="btn btn-ghost"
                    type="button"
                    onClick={chat.cancelDraft}
                    disabled={chat.draftBusy}
                  >
                    {p.review.cancel}
                  </button>
                  <button
                    className="btn btn-outline"
                    type="button"
                    onClick={() => void chat.saveDraft()}
                    disabled={chat.draftBusy || suggesting}
                  >
                    {p.review.saveDraft}
                  </button>
                  <button
                    className="btn btn-primary"
                    type="submit"
                    disabled={chat.draftBusy || suggesting || !draft.body.trim()}
                  >
                    {chat.draftBusy ? p.review.sending : p.review.sendToAdmin}
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
