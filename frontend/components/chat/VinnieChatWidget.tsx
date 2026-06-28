"use client";

import { useEffect } from "react";
import Link from "next/link";
import { ChatColumn } from "@/components/ChatColumn";
import { SourceDrawer } from "@/components/SourceDrawer";
import { ConnectedAnswerActions } from "./ConnectedAnswerActions";
import { useChat } from "@/lib/chat";
import { usePortal } from "@/lib/portalI18n";
import { useI18n } from "@/lib/i18n";
import { useAuth } from "@/lib/auth";
import { useAsync } from "@/lib/useAsync";
import { getActiveSuggestedQuestions } from "@/lib/api";
import { IconChat } from "@/components/shell/icons";

// Compact chat panel that opens next to the floating bubble — anchored bottom-right by default,
// or at the dragged bubble's position via `style` (full-screen sheet on mobile, where `style`
// is omitted). Shares the same conversation + source drawer as the full Ask Vinnie page via
// useChat().
export function VinnieChatWidget({
  onClose,
  style,
}: {
  onClose: () => void;
  style?: React.CSSProperties;
}) {
  const { p, lang } = usePortal();
  const { t } = useI18n();
  const { token } = useAuth();
  const chat = useChat();

  // Mark the widget as an open surface (clears the unread badge while it's visible).
  useEffect(() => chat.registerViewer(), []); // eslint-disable-line react-hooks/exhaustive-deps

  // Notification-driven suggested prompts (top 3), localized, falling back to the static set.
  const suggested = useAsync(() => getActiveSuggestedQuestions(lang), [lang, token]);
  const chips =
    suggested.status === "success" && suggested.data.length > 0
      ? suggested.data.map((q) => q.question_text)
      : p.chatSuggested;

  return (
    <div className="vinnie-widget" role="dialog" aria-label="Vinnie" style={style}>
      <div className="vinnie-widget-head">
        <span className="vinnie-widget-brand">
          <span className="vinnie-avatar" aria-hidden="true">
            <IconChat size={15} />
          </span>
          Vinnie
        </span>
        <div className="vinnie-widget-tools">
          <Link
            className="vinnie-tool"
            href="/student/chat"
            title={p.nav.chat}
            onClick={onClose}
            aria-label={p.nav.chat}
          >
            <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor"
              strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M15 3h6v6M21 3l-9 9M9 21H3v-6M3 21l9-9" />
            </svg>
          </Link>
          <button
            className="vinnie-tool"
            onClick={onClose}
            aria-label={t.srcClose}
            title={t.srcClose}
          >
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor"
              strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M6 9l6 6 6-6" />
            </svg>
          </button>
        </div>
      </div>

      <ChatColumn
        messages={chat.messages}
        busy={chat.busy}
        conversationId={chat.conversationId}
        lastUserId={chat.lastUserId}
        onSend={chat.send}
        onStop={chat.stop}
        onRetry={chat.retry}
        onEditLast={chat.editLast}
        onOpenSources={chat.openSources}
        renderActions={(m) => <ConnectedAnswerActions message={m} />}
        composerChips={chips.slice(0, 3)}
        note={t.privacyNote}
        showHead={false}
        composerSeedText={chat.composerSeed?.text}
        composerSeedNonce={chat.composerSeed?.nonce}
      />

      <SourceDrawer
        message={chat.sourceMessage}
        focus={chat.sourceFocus}
        onClose={chat.closeSources}
      />
    </div>
  );
}
