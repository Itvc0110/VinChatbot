import { useState } from "react";
import { useI18n } from "@/lib/i18n";

export function Composer({
  onSend,
  onStop,
  busy,
  showChips = true,
}: {
  onSend: (text: string) => void;
  onStop: () => void;
  busy: boolean;
  showChips?: boolean;
}) {
  const { t } = useI18n();
  const [value, setValue] = useState("");
  const trimmed = value.trim();
  // Inline validation, warn-don't-block style. Backend enforces 1..4000.
  const tooLong = value.length > 4000;
  const canSend = trimmed.length > 0 && !tooLong && !busy;

  const submit = () => {
    if (!canSend) return;
    onSend(trimmed);
    setValue("");
  };

  return (
    <div className="composer">
      {showChips && (
        <div className="chips">
          {t.quickPrompts.map((p) => (
            <button
              key={p}
              className="prompt-chip"
              disabled={busy}
              onClick={() => onSend(p)}
            >
              {p}
            </button>
          ))}
        </div>
      )}
      <div className="composer-row">
        <textarea
          rows={2}
          placeholder={t.placeholder}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              submit();
            }
          }}
        />
        {busy ? (
          <button className="stop-btn" onClick={onStop} title={t.stop}>
            ◼ {t.stop}
          </button>
        ) : (
          <button className="send-btn" onClick={submit} disabled={!canSend}>
            {t.send}
          </button>
        )}
      </div>
      {tooLong && <div className="input-warn">{t.tooLong(value.length)}</div>}
    </div>
  );
}
