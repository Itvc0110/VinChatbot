import type { ResponseState } from "@/lib/responseState";
import { useI18n } from "@/lib/i18n";

// Color paired with a text label (never color alone) — accessible by design.
export function StateChip({ state }: { state: ResponseState }) {
  const { t } = useI18n();
  return (
    <span className={`chip ${state}`}>
      <span className="dot" />
      {t.chip[state]}
    </span>
  );
}
