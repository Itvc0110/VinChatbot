"use client";

import { useState } from "react";
import { usePortal } from "@/lib/portalI18n";
import type { ForumMember } from "@/lib/portalTypes";
import { MentionTextarea } from "./MentionTextarea";

export interface CommentSubmitPayload {
  content: string;
  mentioned_user_ids: string[];
}

// Textarea + submit used for both top-level comments and inline replies. The parent decides
// what posting means (add_comment with or without a parent_comment_id) and reloads the thread.
export function CommentComposer({
  onSubmit,
  placeholder,
  submitLabel,
  autoFocus = false,
  onCancel,
}: {
  onSubmit: (payload: CommentSubmitPayload) => Promise<boolean>;
  placeholder: string;
  submitLabel: string;
  autoFocus?: boolean;
  onCancel?: () => void;
}) {
  const { p } = usePortal();
  const [text, setText] = useState("");
  const [mentions, setMentions] = useState<ForumMember[]>([]);
  const [busy, setBusy] = useState(false);

  const canSubmit = text.trim().length > 0 && !busy;

  const submit = async () => {
    if (!canSubmit) return;
    setBusy(true);
    const ok = await onSubmit({
      content: text.trim(),
      mentioned_user_ids: mentions.map((m) => m.id),
    });
    setBusy(false);
    if (ok) {
      setText("");
      setMentions([]);
    }
  };

  return (
    <div className="forum-composer">
      <MentionTextarea
        value={text}
        onChange={setText}
        mentions={mentions}
        onMentionsChange={setMentions}
        placeholder={placeholder}
        rows={onCancel ? 3 : 4}
        autoFocus={autoFocus}
        disabled={busy}
      />
      <div className="forum-composer-actions">
        {onCancel && (
          <button type="button" className="btn btn-ghost btn-sm" onClick={onCancel} disabled={busy}>
            {p.forum.cancel}
          </button>
        )}
        <button
          type="button"
          className="ah-btn-red"
          onClick={submit}
          disabled={!canSubmit}
        >
          {busy ? p.forum.posting : submitLabel}
        </button>
      </div>
    </div>
  );
}
