"use client";

import type { Citation } from "@/lib/types";
import { useI18n } from "@/lib/i18n";

// Citations rendered directly under an assistant answer: ONLY a compact "Sources (n)" button.
// Clicking it opens the shared source drawer with the full list (number / title / type /
// snippet / open action) — the per-source pills used to render here are gone so the answer
// card stays clean and a long citation can't break the layout. The `unverified` flag still
// tints the button so a not-fully-grounded answer reads differently.
export function ChatCitationList({
  citations,
  onOpen,
  unverified = false,
}: {
  citations: Citation[];
  onOpen: (idx: number) => void;
  unverified?: boolean;
}) {
  const { t } = useI18n();
  if (!citations.length) return null;

  return (
    <div className="cite-list">
      <button
        className={`cite-sources-btn ${unverified ? "unverified" : ""}`}
        onClick={() => onOpen(0)}
      >
        <svg viewBox="0 0 24 24" width="13" height="13" aria-hidden="true"
          fill="none" stroke="currentColor" strokeWidth="1.8"
          strokeLinecap="round" strokeLinejoin="round">
          <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
          <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
        </svg>
        {t.sourcesBtnCount(citations.length)}
      </button>
    </div>
  );
}
