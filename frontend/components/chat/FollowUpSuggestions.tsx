"use client";

import type { ChatResponse } from "@/lib/types";
import { useI18n } from "@/lib/i18n";
import { followUpsFor } from "@/lib/followUps";

// Per-answer follow-up chips, shown under a settled answer. Rule-based today; clicking sends
// the question through the normal chat flow.
export function FollowUpSuggestions({
  question,
  response,
  onPick,
}: {
  question: string;
  response: ChatResponse;
  onPick: (q: string) => void;
}) {
  const { t, lang } = useI18n();
  const items = followUpsFor(question, response, lang);
  if (items.length === 0) return null;
  return (
    <div className="followups">
      <span className="followups-label">{t.followUpHeading}</span>
      <div className="followups-chips">
        {items.map((q) => (
          <button key={q} className="prompt-chip" onClick={() => onPick(q)}>
            {q}
          </button>
        ))}
      </div>
    </div>
  );
}
