"use client";

import { useState } from "react";
import { useChat } from "@/lib/chat";
import { useI18n } from "@/lib/i18n";
import { IconChat } from "@/components/shell/icons";
import { VinnieChatWidget } from "./VinnieChatWidget";

const STR = {
  en: { askVinnie: "Ask Vinnie" },
  vi: { askVinnie: "Hỏi Vinnie" },
} as const;

// Global floating chat bubble (bottom-right) available across student pages. Opens the
// compact Vinnie widget, which shares conversation state with the full Ask Vinnie page.
export function FloatingVinnieButton() {
  const [open, setOpen] = useState(false);
  const chat = useChat();
  const { lang } = useI18n();
  const s = STR[lang];

  return (
    <>
      {open && <VinnieChatWidget onClose={() => setOpen(false)} />}
      <button
        className={`vinnie-fab ${open ? "is-open" : ""}`}
        onClick={() => setOpen((o) => !o)}
        aria-label={s.askVinnie}
        title={s.askVinnie}
        aria-expanded={open}
      >
        {open ? (
          <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor"
            strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M6 9l6 6 6-6" />
          </svg>
        ) : (
          <>
            <IconChat size={24} />
            {chat.unread > 0 && (
              <span className="vinnie-fab-badge" aria-hidden="true">
                {chat.unread > 9 ? "9+" : chat.unread}
              </span>
            )}
          </>
        )}
      </button>
    </>
  );
}
