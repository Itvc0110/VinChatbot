"use client";

import type { Citation } from "@/lib/types";
import { useI18n } from "@/lib/i18n";

function hostOf(url: string): string {
  try {
    return new URL(url).host;
  } catch {
    return url;
  }
}

// Citations rendered directly under an assistant answer: a "Sources (n)" button plus a
// clickable chip per source. Clicking either opens the shared source drawer focused on
// that source. Sources are always tied to the exact answer they support.
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
      <button className="cite-sources-btn" onClick={() => onOpen(0)}>
        <svg viewBox="0 0 24 24" width="13" height="13" aria-hidden="true"
          fill="none" stroke="currentColor" strokeWidth="1.8"
          strokeLinecap="round" strokeLinejoin="round">
          <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
          <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
        </svg>
        {t.sourcesBtnCount(citations.length)}
      </button>
      <div className="cite-chips">
        {citations.map((c, i) => (
          <button
            key={`${c.source_url}-${i}`}
            className={`cite-chip ${unverified ? "unverified" : ""}`}
            onClick={() => onOpen(i)}
            title={c.title || c.source_url}
          >
            <span className="cite-chip-n">[{i + 1}]</span>
            <span className="cite-chip-title">{c.title || hostOf(c.source_url)}</span>
            {c.section && <span className="cite-chip-sec">· {c.section}</span>}
          </button>
        ))}
      </div>
    </div>
  );
}
