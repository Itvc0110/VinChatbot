import { useState } from "react";
import { useI18n } from "@/lib/i18n";

type Status = "idle" | "open" | "sending" | "done" | "error";

// Flag/report affordance under an assistant answer. Low-friction: a small link that
// opens an inline reason box and posts to /api/feedback (a Next route handler).
export function FlagForm({
  conversationId,
  messageId,
  answerExcerpt,
}: {
  conversationId: string;
  messageId: string;
  answerExcerpt: string;
}) {
  const { t } = useI18n();
  const [status, setStatus] = useState<Status>("idle");
  const [reason, setReason] = useState("");

  if (status === "done") {
    return <span className="reported-badge">{t.reported}</span>;
  }

  if (status === "idle" || status === "error") {
    return (
      <button className="flag-link" onClick={() => setStatus("open")}>
        {t.flag}
        {status === "error" && <span className="flag-err">{t.flagSendFail}</span>}
      </button>
    );
  }

  const submit = async () => {
    setStatus("sending");
    try {
      const res = await fetch("/api/feedback", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          conversation_id: conversationId,
          message_id: messageId,
          reason: reason.trim(),
          answer_excerpt: answerExcerpt,
        }),
      });
      setStatus(res.ok ? "done" : "error");
    } catch {
      setStatus("error");
    }
  };

  return (
    <div className="flag-form">
      <textarea
        rows={2}
        placeholder={t.flagPlaceholder}
        value={reason}
        onChange={(e) => setReason(e.target.value)}
        autoFocus
      />
      <div className="flag-actions">
        <button
          className="flag-submit"
          onClick={submit}
          disabled={status === "sending"}
        >
          {status === "sending" ? t.flagSending : t.flagSubmit}
        </button>
        <button className="flag-cancel" onClick={() => setStatus("idle")}>
          {t.cancel}
        </button>
      </div>
    </div>
  );
}
