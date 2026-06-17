import { useRef, useState } from "react";
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
  const taRef = useRef<HTMLTextAreaElement>(null);
  const trimmed = value.trim();

  // Auto-grow the textarea up to its CSS max-height, then let it scroll.
  const autoGrow = (el: HTMLTextAreaElement) => {
    el.style.height = "auto";
    el.style.height = `${el.scrollHeight}px`;
  };
  // Inline validation, warn-don't-block style. Backend enforces 1..4000.
  const tooLong = value.length > 4000;
  const canSend = trimmed.length > 0 && !tooLong && !busy;

  const submit = () => {
    if (!canSend) return;
    onSend(trimmed);
    setValue("");
    if (taRef.current) taRef.current.style.height = "auto";
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
      <div className="composer-field">
        <textarea
          ref={taRef}
          rows={1}
          placeholder={t.placeholder}
          value={value}
          onChange={(e) => {
            setValue(e.target.value);
            autoGrow(e.target);
          }}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              submit();
            }
          }}
        />
        {busy ? (
          <button className="stop-btn" onClick={onStop} title={t.stop}>
            <svg viewBox="0 0 24 24" width="13" height="13" aria-hidden="true">
              <rect x="6" y="6" width="12" height="12" rx="2" fill="currentColor" />
            </svg>
            {t.stop}
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
