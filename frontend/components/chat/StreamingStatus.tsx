"use client";

import { useI18n } from "@/lib/i18n";

// Honest pre-reveal placeholder shown while the verified answer is still being computed
// (no delta has arrived yet). With today's backend this is ONE calm line, not a fabricated
// multi-step checklist — the backend emits nothing until verify completes. If/when it emits
// `event: status`, `statusStep` carries the real step and we show that instead.
export function StreamingStatus({ statusStep }: { statusStep?: string }) {
  const { t } = useI18n();
  const label = statusStep || t.retrieving;
  return (
    <div className="stream-status" role="status" aria-label={label}>
      <span className="thinking" aria-hidden="true">
        <span className="tdot" />
        <span className="tdot" />
        <span className="tdot" />
      </span>
      <span className="stream-status-label">{label}</span>
    </div>
  );
}
