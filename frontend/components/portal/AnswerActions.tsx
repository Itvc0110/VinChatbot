"use client";

import type { ChatResponse } from "@/lib/types";
import { deriveState } from "@/lib/responseState";
import { usePortal } from "@/lib/portalI18n";
import {
  IconChat,
  IconFileText,
  IconTicket,
} from "@/components/shell/icons";

// PLAN22.6.2 action row — a tidy hierarchy of next-step actions anchored to a completed
// answer. Primary: Ask follow-up. Secondary: Prepare ticket
// (opens the Review drawer; Vinnie NEVER auto-submits). Calendar/reminder shortcuts are
// temporarily hidden, and source access stays in the per-answer "Nguồn (n)" button above
// this row. "Report issue" is the existing FlagForm rendered below this in MessageBubble.
export function AnswerActions({
  response,
  onPrepareTicket,
  onAskFollowUp,
  onDraftForm,
}: {
  response: ChatResponse;
  onPrepareTicket: () => void;
  onAskFollowUp: () => void;
  // Present only when the answer cites an official VinUni form file — offers "Draft this form".
  onDraftForm?: () => void;
}) {
  const { p } = usePortal();
  const state = deriveState(response);

  // For conversational replies there's nothing actionable. Source access lives in the
  // per-answer citation list (ChatCitationList), so there's no "View source" here.
  if (state === "conversational") return null;

  return (
    <div className="answer-actions">
      <button className="answer-action primary" onClick={onAskFollowUp}>
        <IconChat size={13} /> {p.actAskFollowUp}
      </button>
      {onDraftForm && (
        <button className="answer-action" onClick={onDraftForm}>
          <IconFileText size={13} /> {p.actDraftForm}
        </button>
      )}
      <button className="answer-action" onClick={onPrepareTicket}>
        <IconTicket size={13} /> {p.actPrepareTicket}
      </button>
    </div>
  );
}
