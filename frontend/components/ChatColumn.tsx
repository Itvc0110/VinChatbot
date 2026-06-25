import { useEffect, useRef } from "react";
import type { ChatMessage } from "@/lib/types";
import { useI18n } from "@/lib/i18n";
import { MessageBubble } from "./MessageBubble";
import { Composer } from "./Composer";

export function ChatColumn({
  messages,
  busy,
  conversationId,
  lastUserId,
  onSend,
  onStop,
  onRetry,
  onEditLast,
  onOpenSources,
  renderActions,
  composerChips,
  note,
  showHead = true,
  composerSeedText,
  composerSeedNonce,
}: {
  messages: ChatMessage[];
  busy: boolean;
  conversationId: string;
  lastUserId: string | null;
  onSend: (text: string) => void;
  onStop: () => void;
  onRetry: (messageId: string) => void;
  onEditLast: (text: string) => void;
  // Open the shared source drawer for message `messageId`, focused on citation `idx`.
  onOpenSources: (messageId: string, idx: number) => void;
  // Portal-only: builds the per-answer action row (calendar/reminder/prepare-ticket/…).
  renderActions?: (m: ChatMessage) => React.ReactNode;
  composerChips?: string[];
  // Subtle helper text shown under the composer (e.g. the privacy note).
  note?: string;
  showHead?: boolean;
  // "Ask follow-up" seed forwarded to the Composer.
  composerSeedText?: string;
  composerSeedNonce?: number;
}) {
  const { t } = useI18n();
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, busy]);

  return (
    <div className="pane chat">
      {showHead && <div className="pane-head">{t.paneConversation}</div>}
      <div className="messages">
        {messages.map((m) => (
          <MessageBubble
            key={m.id}
            message={m}
            conversationId={conversationId}
            isLastUser={m.id === lastUserId}
            onRetry={m.error || m.cancelled ? () => onRetry(m.id) : undefined}
            onEdit={m.id === lastUserId ? onEditLast : undefined}
            onOpenSources={(idx) => onOpenSources(m.id, idx)}
            extraActions={renderActions?.(m)}
          />
        ))}
        <div ref={endRef} />
      </div>
      <Composer
        onSend={onSend}
        onStop={onStop}
        busy={busy}
        chips={composerChips}
        // Initial suggestion chips belong to the empty state only. Once the conversation has
        // messages they're hidden, so they never linger after the first question — contextual
        // per-answer follow-ups take over (see ConnectedAnswerActions / FollowUpSuggestions).
        showChips={messages.length === 0}
        note={note}
        seedText={composerSeedText}
        seedNonce={composerSeedNonce}
      />
    </div>
  );
}
