import { useState } from "react";
import type { Citation } from "@/lib/types";

export type SourceVariant = "grounded" | "unverified";

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
  const [expanded, setExpanded] = useState(false);
  let host = c.source_url;
  try {
    host = new URL(c.source_url).host;
  } catch {
    /* leave raw if not a valid URL */
  }

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
        title="Show the full passage"
      >
        <span className="title">
          {index + 1}. {c.title || host || "Untitled source"}
        </span>
        <span className="src-caret">{expanded ? "▾" : "▸"}</span>
      </button>
      {c.source_url && (
        <a className="url" href={c.source_url} target="_blank" rel="noreferrer">
          {c.source_url}
        </a>
      )}
      {c.excerpt && (
        <div className={`excerpt ${expanded ? "expanded" : "clamped"}`}>
          {c.excerpt}
        </div>
      )}
      <div className="src-meta">
        {variant === "unverified" && (
          <span className="tag tag-warn">unverified</span>
        )}
        {c.section && <span className="tag">{c.section}</span>}
        {typeof c.page_number === "number" && (
          <span className="tag">p.{c.page_number}</span>
        )}
        {/* Backend `score` is a rerank/hybrid score (can exceed 1.0) — not a 0–1 scale,
            so it's hidden rather than shown as if it were a confidence. */}
      </div>
    </div>
  );
}
