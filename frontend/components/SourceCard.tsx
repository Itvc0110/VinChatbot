import { useState } from "react";
import type { Citation } from "@/lib/types";
import { useI18n } from "@/lib/i18n";

export type SourceVariant = "grounded" | "unverified";

// Derives the displayable host, source type and official status from a citation URL.
// (The chat backend's Citation has no explicit type/official field — we infer it the same
//  way the admin source table does in api.ts mapSummaryToSource.)
export function sourceMeta(url: string): {
  host: string;
  isOfficial: boolean;
  type: "pdf" | "url" | "database" | "official";
} {
  let host = url;
  try {
    host = new URL(url).host;
  } catch {
    /* leave raw if not a valid URL */
  }
  const isOfficial = /vinuni\.edu\.vn/i.test(url);
  let type: "pdf" | "url" | "database" | "official";
  if (/\.pdf(\?|#|$)/i.test(url)) type = "pdf";
  else if (/(drive\.|\/db\/|database|spreadsheet|\.csv|\.xlsx?)/i.test(url)) type = "database";
  else if (isOfficial) type = "official";
  else type = "url";
  return { host, isOfficial, type };
}

export function SourceCard({
  c,
  index,
  variant = "grounded",
  highlighted = false,
  cardRef,
}: {
  c: Citation;
  index: number;
  variant?: SourceVariant;
  highlighted?: boolean;
  cardRef?: (el: HTMLDivElement | null) => void;
}) {
  const { t } = useI18n();
  const [expanded, setExpanded] = useState(false);
  const { host, isOfficial, type } = sourceMeta(c.source_url);

  return (
    <div
      ref={cardRef}
      className={[
        "source-card",
        `variant-${variant}`,
        highlighted ? "is-highlighted" : "",
      ].join(" ")}
    >
      <button
        className="src-title-btn"
        onClick={() => setExpanded((v) => !v)}
        aria-expanded={expanded}
        title={t.showPassage}
      >
        <span className="title">
          {index + 1}. {c.title || host || t.untitledSource}
        </span>
        <span className="src-caret">{expanded ? "▾" : "▸"}</span>
      </button>

      {/* Status labels never contradict: a grounded official source reads "Official source";
          an unverified one reads "Needs confirmation" — we don't show a green ✓ on a source
          the answer couldn't actually be grounded on. */}
      <div className="src-tags">
        <span className={`tag tag-type tag-type-${type}`}>{t.srcType[type]}</span>
        {variant === "unverified" ? (
          <span className="tag tag-warn">{t.unverifiedTag}</span>
        ) : (
          isOfficial && <span className="tag tag-official">✓ {t.srcOfficial}</span>
        )}
        {c.section && <span className="tag">{c.section}</span>}
        {typeof c.page_number === "number" && <span className="tag">p.{c.page_number}</span>}
      </div>

      {c.excerpt && (
        <div className={`excerpt ${expanded ? "expanded" : "clamped"}`}>{c.excerpt}</div>
      )}

      {c.source_url && (
        <a
          className="src-open"
          href={c.source_url}
          target="_blank"
          rel="noreferrer"
          title={c.source_url}
        >
          <svg viewBox="0 0 24 24" width="12" height="12" aria-hidden="true"
            fill="none" stroke="currentColor" strokeWidth="2"
            strokeLinecap="round" strokeLinejoin="round">
            <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
            <path d="M15 3h6v6M10 14 21 3" />
          </svg>
          {t.srcOpen} · {host}
        </a>
      )}
    </div>
  );
}
