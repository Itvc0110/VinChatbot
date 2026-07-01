"use client";

import { useEffect } from "react";
import { useChat } from "@/lib/chat";
import { usePortal } from "@/lib/portalI18n";

// Fields that benefit from a multi-line editor (free-text reason / content).
const MULTILINE = /(reason|ly_?do|noi_?dung|content|purpose|narrative|mo_?ta|detail)/i;

// Form Assistant review drawer. Vinnie prepares a DRAFT (fields held in ChatProvider state); this drawer
// lets the student edit every field and DOWNLOAD a filled file. Nothing is sent to any office — the student
// downloads the file and submits it themselves. Mounted once globally (StudentChatOverlays) so it overlays
// the full chat page, the floating widget, and the support page alike. Mirrors ReviewTicketDrawer.
export function ReviewFormDrawer() {
  const { p } = usePortal();
  const chat = useChat();
  const draft = chat.formDraft;
  const open = !!draft;
  const suggesting = chat.formSuggesting;

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") chat.cancelFormFill();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, chat]);

  return (
    <>
      <div
        className={`detail-scrim ${open ? "open" : ""}`}
        onClick={chat.cancelFormFill}
        aria-hidden="true"
      />
      <aside
        className={`detail-drawer wide ${open ? "open" : ""}`}
        aria-hidden={!open}
        role="dialog"
        aria-label={p.formReview.banner}
      >
        {draft && (
          <>
            <div className="detail-head">
              <span className="td-strong">{draft.form_title || p.actDraftForm}</span>
              <button
                className="source-drawer-close"
                onClick={chat.cancelFormFill}
                aria-label={p.formReview.close}
                title={p.formReview.close}
              >
                ✕
              </button>
            </div>

            <div className="detail-body">
              {/* Prominent review-before-you-send disclaimer — the STUDENT submits the form, not Vinnie. */}
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
                      {p.formReview.aiDraftedChip}
                    </span>
                  )}
                  <span style={{ fontWeight: 600 }}>{p.formReview.banner}</span>
                  {suggesting && (
                    <span style={{ fontStyle: "italic", opacity: 0.85 }}>{p.formReview.drafting}</span>
                  )}
                  {draft.notice && !suggesting && (
                    <span style={{ opacity: 0.85 }}>{draft.notice}</span>
                  )}
                </div>
              </div>

              {draft.official_url && (
                <p style={{ margin: "0.6rem 0", fontSize: "0.85rem" }}>
                  {p.formReview.officialSource}:{" "}
                  <a href={draft.official_url} target="_blank" rel="noreferrer noopener">
                    {draft.official_url}
                  </a>
                </p>
              )}

              <form
                className="form-grid"
                onSubmit={(e) => {
                  e.preventDefault();
                  void chat.downloadForm();
                }}
              >
                {draft.fields.length === 0 && !suggesting && (
                  <p style={{ opacity: 0.8 }}>{p.formReview.noFields}</p>
                )}
                {draft.fields.map((field) => (
                  <div className="field" key={field.key}>
                    <label className="field-label" htmlFor={`ff-${field.key}`}>
                      {field.label || field.key}
                    </label>
                    {MULTILINE.test(`${field.key} ${field.label}`) ? (
                      <textarea
                        id={`ff-${field.key}`}
                        className="textarea"
                        value={field.value}
                        onChange={(e) => chat.updateFormField(field.key, e.target.value)}
                        disabled={suggesting}
                      />
                    ) : (
                      <input
                        id={`ff-${field.key}`}
                        className="input"
                        value={field.value}
                        onChange={(e) => chat.updateFormField(field.key, e.target.value)}
                        disabled={suggesting}
                      />
                    )}
                  </div>
                ))}

                <div className="review-actions">
                  <button
                    className="btn btn-ghost"
                    type="button"
                    onClick={chat.cancelFormFill}
                    disabled={chat.formBusy}
                  >
                    {p.formReview.cancel}
                  </button>
                  <button
                    className="btn btn-primary"
                    type="submit"
                    disabled={chat.formBusy || suggesting || draft.fields.length === 0}
                  >
                    {chat.formBusy ? p.formReview.preparing : p.formReview.download}
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
