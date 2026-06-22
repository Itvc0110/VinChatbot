"use client";

import { useEffect, useRef, useState } from "react";
import type { ChatMessage } from "@/lib/types";
import type { SourceFocus } from "@/lib/chat";
import { deriveState } from "@/lib/responseState";
import { useI18n } from "@/lib/i18n";
import { SourceCard } from "./SourceCard";

// Source panel for ONE selected answer. Hidden by default — opened only when the user
// clicks an answer's "Sources" button, a citation chip, or an inline [n] marker.
//   variant="inline"  → a side column that splits the full chat page in two (collapses to
//                        a slide-over on small screens).
//   variant="overlay" → a fixed slide-over (used by the compact floating widget).
// Esc / scrim closes it.
export function SourceDrawer({
  message,
  focus,
  onClose,
  variant = "overlay",
}: {
  message: ChatMessage | null;
  focus: SourceFocus | null;
  onClose: () => void;
  variant?: "overlay" | "inline";
}) {
  const { t } = useI18n();
  const cardRefs = useRef<Array<HTMLDivElement | null>>([]);
  const [highlightIdx, setHighlightIdx] = useState<number | null>(null);

  const resp = message?.response ?? null;
  const open = !!resp && resp.citations.length > 0;

  // Citation click → scroll the matching card into view + transient highlight.
  useEffect(() => {
    if (!focus || !open) return;
    const el = cardRefs.current[focus.idx];
    if (!el) return;
    el.scrollIntoView({ behavior: "smooth", block: "nearest" });
    setHighlightIdx(focus.idx);
    const timer = setTimeout(() => setHighlightIdx(null), 1500);
    return () => clearTimeout(timer);
  }, [focus, open]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  const cardVariant = resp && deriveState(resp) === "grounded" ? "grounded" : "unverified";
  cardRefs.current = [];

  return (
    <>
      <div
        className={`source-scrim ${variant === "inline" ? "for-inline" : ""} ${
          open ? "open" : ""
        }`}
        onClick={onClose}
        aria-hidden="true"
      />
      <aside
        className={`source-drawer ${variant} ${open ? "open" : ""}`}
        aria-hidden={!open}
        aria-label={t.drawerTitle}
      >
        <div className="source-drawer-head">
          <span className="trust-mark" aria-hidden="true">
            ✓
          </span>
          <span className="source-drawer-title">{t.drawerTitle}</span>
          <button
            className="source-drawer-close"
            onClick={onClose}
            aria-label={t.srcClose}
            title={t.srcClose}
          >
            ✕
          </button>
        </div>
        <div className="source-drawer-body">
          {resp && resp.citations.length > 0 ? (
            resp.citations.map((c, i) => (
              <SourceCard
                key={`${c.source_url}-${i}`}
                c={c}
                index={i}
                variant={cardVariant}
                highlighted={highlightIdx === i}
                cardRef={(el) => (cardRefs.current[i] = el)}
              />
            ))
          ) : (
            <div className="panel-empty">{t.emptyHint}</div>
          )}
        </div>
      </aside>
    </>
  );
}
