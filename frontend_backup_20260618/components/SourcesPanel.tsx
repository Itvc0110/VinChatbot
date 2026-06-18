import { useEffect, useRef, useState } from "react";
import type { ChatMessage } from "@/lib/types";
import { deriveState, refusalReasonKey } from "@/lib/responseState";
import { splitOfficialSources, type OfficialRoute } from "@/lib/officialSources";
import { useI18n } from "@/lib/i18n";
import { SourceCard } from "./SourceCard";

// A click on an inline [n] marker bumps `nonce` so the panel re-runs the scroll even
// when the same marker is clicked twice.
export interface CiteFocus {
  idx: number;
  nonce: number;
}

function RouteList({ routes }: { routes: OfficialRoute[] }) {
  if (routes.length === 0) return null;
  return (
    <ul className="route-list">
      {routes.map((r) => (
        <li key={r.url}>
          <a href={r.url} target="_blank" rel="noreferrer">
            {r.title}
          </a>
        </li>
      ))}
    </ul>
  );
}

function SourceSkeleton() {
  return (
    <div className="src-skeleton" aria-hidden="true">
      <div className="skel-line w-70" />
      <div className="skel-line w-90" />
      <div className="skel-line w-40" />
    </div>
  );
}

export function SourcesPanel({
  latest,
  citeFocus,
  busy = false,
}: {
  latest: ChatMessage | null;
  citeFocus: CiteFocus | null;
  busy?: boolean;
}) {
  const { t } = useI18n();
  const cardRefs = useRef<Array<HTMLDivElement | null>>([]);
  const [highlightIdx, setHighlightIdx] = useState<number | null>(null);

  // Inline citation click → scroll the matching card into view + transient highlight.
  useEffect(() => {
    if (!citeFocus) return;
    const el = cardRefs.current[citeFocus.idx];
    if (!el) return;
    el.scrollIntoView({ behavior: "smooth", block: "nearest" });
    setHighlightIdx(citeFocus.idx);
    const timer = setTimeout(() => setHighlightIdx(null), 1500);
    return () => clearTimeout(timer);
  }, [citeFocus]);

  let inner: React.ReactNode;

  // While a request is in flight, show what we're doing: retrieving sources.
  if (busy) {
    inner = (
      <div role="status" aria-label={t.retrieving}>
        <div className="panel-count">{t.retrieving}</div>
        <SourceSkeleton />
        <SourceSkeleton />
        <SourceSkeleton />
      </div>
    );
  } else if (!latest) {
    inner = (
      <div className="panel-empty">
        <span className="panel-empty-illo" aria-hidden="true">
          🔎
        </span>
        {t.emptyHint}
      </div>
    );
  } else if (latest.error) {
    inner = <div className="panel-note">{t.errorNote}</div>;
  } else if (latest.cancelled) {
    inner = <div className="panel-note">{t.cancelledNote}</div>;
  } else if (!latest.response) {
    inner = <div className="panel-empty">{t.waiting}</div>;
  } else {
    const resp = latest.response;
    const state = deriveState(resp);
    const { routes } = splitOfficialSources(resp.answer);
    cardRefs.current = [];

    if (state === "grounded") {
      inner = (
        <>
          <div className="panel-count">{t.sourceCount(resp.citations.length)}</div>
          {resp.citations.map((c, i) => (
            <SourceCard
              key={`${c.source_url}-${i}`}
              c={c}
              index={i}
              variant="grounded"
              highlighted={highlightIdx === i}
              cardRef={(el) => (cardRefs.current[i] = el)}
            />
          ))}
        </>
      );
    } else if (state === "conversational") {
      inner = <div className="panel-note">{t.conversationalNote}</div>;
    } else if (state === "refusal") {
      inner = (
        <div className="route-card">
          <h3>{t.refusalTitle}</h3>
          <p>
            {t[`reason${capitalize(refusalReasonKey(resp))}` as keyof typeof t] as string}
            . {t.refusalNoCite}
          </p>
          {routes.length > 0 && (
            <>
              <p>{t.refusalUseChannel}</p>
              <RouteList routes={routes} />
            </>
          )}
        </div>
      );
    } else {
      // degraded — may carry citations the backend judged insufficient to ground on.
      inner = (
        <>
          <div className="route-card">
            <h3>{t.degradedTitle}</h3>
            <p>{t.degradedBody}</p>
            {routes.length > 0 && (
              <>
                <p>{t.degradedCheck}</p>
                <RouteList routes={routes} />
              </>
            )}
          </div>
          {resp.citations.length > 0 && (
            <div className="unverified-block">
              <div className="panel-count unverified-head">
                {t.relatedUnverified(resp.citations.length)}
              </div>
              <p className="unverified-note">{t.unverifiedNote}</p>
              {resp.citations.map((c, i) => (
                <SourceCard
                  key={`${c.source_url}-${i}`}
                  c={c}
                  index={i}
                  variant="unverified"
                />
              ))}
            </div>
          )}
        </>
      );
    }
  }

  return (
    <div className="pane sources">
      <div className="pane-head">
        <span className="trust-mark" aria-hidden="true">
          ✓
        </span>
        {t.paneSources}
      </div>
      <div className="panel-body">{inner}</div>
    </div>
  );
}

function capitalize(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1);
}
