"use client";

import { useEffect, useState } from "react";
import { useI18n } from "@/lib/i18n";
import { Modal } from "@/components/ui/primitives";

const STR = {
  en: {
    report: "Report a problem",
    heading: "Report a problem",
    intro: "Hit a bug or something that looks broken? Tell us what happened.",
    descLabel: "What went wrong?",
    descPlaceholder: "Describe the issue — what you did and what you expected…",
    attachLabel: "Attachment (optional)",
    addFiles: "Add files",
    removeFile: "Remove",
    cancel: "Cancel",
    send: "Send report",
    sending: "Sending…",
    doneTitle: "Thanks for the report",
    doneBody: "Our team will take a look. You can close this now.",
    close: "Close",
    failed: "Couldn't send the report. Please try again.",
  },
  vi: {
    report: "Báo lỗi",
    heading: "Báo lỗi hệ thống",
    intro: "Gặp lỗi hoặc thấy điều gì đó hỏng? Hãy cho chúng tôi biết.",
    descLabel: "Đã xảy ra chuyện gì?",
    descPlaceholder: "Mô tả vấn đề — bạn đã làm gì và mong đợi điều gì…",
    attachLabel: "Tệp đính kèm (tuỳ chọn)",
    addFiles: "Thêm tệp",
    removeFile: "Xoá",
    cancel: "Huỷ",
    send: "Gửi báo cáo",
    sending: "Đang gửi…",
    doneTitle: "Cảm ơn bạn đã báo lỗi",
    doneBody: "Đội ngũ của chúng tôi sẽ xem xét. Bạn có thể đóng cửa sổ này.",
    close: "Đóng",
    failed: "Không gửi được báo cáo. Vui lòng thử lại.",
  },
} as const;

type Status = "idle" | "sending" | "done" | "error";

// Global floating "report a problem" button (paired with the Vinnie chat bubble). Opens a small
// modal where the student describes a bug and optionally names attachments. Posts to the existing
// /api/feedback sink with type:"system_error" plus the current page path for triage.
export function ReportProblemButton() {
  const { lang } = useI18n();
  const s = STR[lang];

  const [open, setOpen] = useState(false);
  const [desc, setDesc] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [status, setStatus] = useState<Status>("idle");

  // Reset the form each time the modal opens.
  useEffect(() => {
    if (!open) return;
    setDesc("");
    setFiles([]);
    setStatus("idle");
  }, [open]);

  function addFiles(list: FileList | null) {
    if (!list || list.length === 0) return;
    setFiles((cur) => [...cur, ...Array.from(list)]);
  }
  function removeFile(idx: number) {
    setFiles((cur) => cur.filter((_, i) => i !== idx));
  }

  async function submit() {
    if (!desc.trim() || status === "sending") return;
    setStatus("sending");
    const path = typeof window !== "undefined" ? window.location.pathname : "";
    const attachments = files.length ? ` | attachments: ${files.map((f) => f.name).join(", ")}` : "";
    try {
      const res = await fetch("/api/feedback", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          type: "system_error",
          reason: desc.trim(),
          context: `page: ${path}${attachments}`,
        }),
      });
      setStatus(res.ok ? "done" : "error");
    } catch {
      setStatus("error");
    }
  }

  return (
    <>
      <button
        className="report-fab"
        onClick={() => setOpen(true)}
        aria-label={s.report}
        title={s.report}
      >
        <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor"
          strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
          <line x1="12" y1="9" x2="12" y2="13" />
          <line x1="12" y1="17" x2="12.01" y2="17" />
        </svg>
      </button>

      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title={status === "done" ? s.doneTitle : s.heading}
        size="sm"
        footer={
          status === "done" ? (
            <button className="btn btn-primary" onClick={() => setOpen(false)}>
              {s.close}
            </button>
          ) : (
            <>
              <button
                className="btn btn-ghost"
                onClick={() => setOpen(false)}
                disabled={status === "sending"}
              >
                {s.cancel}
              </button>
              <button
                className="btn btn-primary"
                onClick={submit}
                disabled={status === "sending" || !desc.trim()}
              >
                {status === "sending" ? s.sending : s.send}
              </button>
            </>
          )
        }
      >
        {status === "done" ? (
          <p className="report-done">{s.doneBody}</p>
        ) : (
          <div className="form-grid">
            <p className="report-intro">{s.intro}</p>
            <div className="field">
              <label className="field-label" htmlFor="rp-desc">
                {s.descLabel}
              </label>
              <textarea
                id="rp-desc"
                className="textarea"
                value={desc}
                onChange={(e) => setDesc(e.target.value)}
                placeholder={s.descPlaceholder}
                autoFocus
              />
            </div>

            <div className="field">
              <div className="field-label">{s.attachLabel}</div>
              <label className="ticket-attach-btn">
                <svg viewBox="0 0 24 24" width="15" height="15" fill="none"
                  stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"
                  strokeLinejoin="round" aria-hidden="true">
                  <path d="M21.44 11.05l-9.19 9.19a5 5 0 0 1-7.07-7.07l9.19-9.19a3 3 0 0 1 4.24 4.24l-9.2 9.19a1 1 0 0 1-1.41-1.41l8.49-8.49" />
                </svg>
                {s.addFiles}
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
              {files.length > 0 && (
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

            {status === "error" && <p className="report-error">{s.failed}</p>}
          </div>
        )}
      </Modal>
    </>
  );
}
