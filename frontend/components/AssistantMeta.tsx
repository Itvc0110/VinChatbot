import type { ChatResponse } from "@/lib/types";
import {
  deriveState,
  confidenceBand,
  showsConfidence,
  isReviewFlagged,
} from "@/lib/responseState";
import { useI18n } from "@/lib/i18n";
import { StateChip } from "./StateChip";

function ConfidencePill({ confidence }: { confidence: number }) {
  const { t } = useI18n();
  const band = confidenceBand(confidence);
  const label =
    band === "high" ? t.confHigh : band === "medium" ? t.confMedium : t.confLow;
  return (
    <span
      className={`chip conf-${band}`}
      title={t.confTitle(confidence.toFixed(2), label)}
    >
      <span className="dot" />
      {label} · {confidence.toFixed(2)}
    </span>
  );
}

// Collapsible "why this answer" — exposes the backend tool_trace (guardrail actions,
// reasons) on demand, so the default view stays clean. Native <details>, no JS state.
function WhyThisAnswer({ trace }: { trace: ChatResponse["tool_trace"] }) {
  const { t } = useI18n();
  if (!trace || trace.length === 0) return null;
  return (
    <details className="why">
      <summary>{t.why}</summary>
      <ul>
        {trace.map((entry, i) => (
          <li key={i}>
            <span className="why-type">{entry.type}</span>
            {entry.action ? <span className="why-action">{entry.action}</span> : null}
            {entry.reason ? <span className="why-reason">{entry.reason}</span> : null}
          </li>
        ))}
      </ul>
    </details>
  );
}

function ReviewChip() {
  const { t } = useI18n();
  return (
    <span className="chip review" title={t.reviewFlaggedTitle}>
      <span className="dot" />
      {t.reviewFlagged}
    </span>
  );
}

export function AssistantMeta({ response }: { response: ChatResponse }) {
  const state = deriveState(response);
  return (
    <div className="meta">
      <StateChip state={state} />
      {showsConfidence(state) && (
        <ConfidencePill confidence={response.confidence} />
      )}
      {isReviewFlagged(response) && <ReviewChip />}
      <WhyThisAnswer trace={response.tool_trace} />
    </div>
  );
}
