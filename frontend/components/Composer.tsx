import { useEffect, useRef, useState } from "react";
import { useI18n } from "@/lib/i18n";

export function Composer({
  onSend,
  onStop,
  busy,
  showChips = true,
  chips,
  note,
  seedText,
  seedNonce,
}: {
  onSend: (text: string) => void;
  onStop: () => void;
  busy: boolean;
  showChips?: boolean;
  // Optional override for the quick-prompt chips (defaults to the i18n quickPrompts).
  chips?: string[];
  // Subtle helper text shown under the field (privacy note).
  note?: string;
  // "Ask follow-up": when seedNonce changes, set the field to seedText and focus it.
  seedText?: string;
  seedNonce?: number;
}) {
  const { t } = useI18n();
  const promptChips = chips ?? t.quickPrompts;
  const [value, setValue] = useState("");
  const taRef = useRef<HTMLTextAreaElement>(null);
  const trimmed = value.trim();

  // Apply a follow-up seed (and focus) whenever the nonce changes.
  useEffect(() => {
    if (seedNonce === undefined) return;
    setValue(seedText ?? "");
    const ta = taRef.current;
    if (ta) {
      ta.focus();
      ta.style.height = "auto";
      ta.style.height = `${ta.scrollHeight}px`;
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [seedNonce]);

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
          {promptChips.map((p) => (
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
      {note && <p className="composer-note">{note}</p>}
    </div>
  );
}
