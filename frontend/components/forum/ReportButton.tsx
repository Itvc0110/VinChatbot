"use client";

import { useState } from "react";
import { Modal } from "@/components/ui/primitives";
import { usePortal } from "@/lib/portalI18n";
import { reportForumContent } from "@/lib/api";
import type { ForumVoteTarget } from "@/lib/portalTypes";

// Inline "Report" control for a topic or comment. Opens a small modal, posts to
// /forum/reports, and bubbles a toast message up to the page.
export function ReportButton({
  targetType,
  targetId,
  onReported,
}: {
  targetType: ForumVoteTarget;
  targetId: string;
  onReported: (message: string) => void;
}) {
  const { p } = usePortal();
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    if (!reason.trim() || busy) return;
    setBusy(true);
    try {
      await reportForumContent({ target_type: targetType, target_id: targetId, reason: reason.trim() });
      onReported(p.forum.reportedToast);
      setOpen(false);
      setReason("");
    } catch {
      onReported(p.forum.actionFailed);
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <button type="button" className="forum-link-btn" onClick={() => setOpen(true)}>
        {p.forum.report}
      </button>
      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title={p.forum.reportTitle}
        footer={
          <>
            <button className="btn btn-ghost" onClick={() => setOpen(false)} disabled={busy}>
              {p.forum.cancel}
            </button>
            <button className="ah-btn-red" onClick={submit} disabled={!reason.trim() || busy}>
              {p.forum.submitReport}
            </button>
          </>
        }
      >
        <textarea
          className="textarea"
          rows={4}
          placeholder={p.forum.reportReasonPlaceholder}
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          autoFocus
        />
      </Modal>
    </>
  );
}
