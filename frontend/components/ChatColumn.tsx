import { useEffect, useRef } from "react";
import type { ChatMessage } from "@/lib/types";
import { useI18n } from "@/lib/i18n";
import { MessageBubble } from "./MessageBubble";
import { Composer } from "./Composer";

export function ChatColumn({
  messages,
  busy,
  conversationId,
  latestAssistantId,
  lastUserId,
  onSend,
  onStop,
  onRetry,
  onEditLast,
  onCiteClick,
}: {
  messages: ChatMessage[];
  busy: boolean;
  conversationId: string;
  latestAssistantId: string | null;
  lastUserId: string | null;
  onSend: (text: string) => void;
  onStop: () => void;
  onRetry: (messageId: string) => void;
  onEditLast: (text: string) => void;
  onCiteClick: (idx: number) => void;
}) {
  const { t } = useI18n();
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, busy]);

  return (
    <div className="pane chat">
      <div className="pane-head">{t.paneConversation}</div>
      <div className="messages">
        {messages.map((m) => (
          <MessageBubble
            key={m.id}
            message={m}
            conversationId={conversationId}
            isLatestAssistant={m.id === latestAssistantId}
            isLastUser={m.id === lastUserId}
            onRetry={m.error ? () => onRetry(m.id) : undefined}
            onEdit={m.id === lastUserId ? onEditLast : undefined}
            onCiteClick={onCiteClick}
          />
        ))}
        {busy && (
          <div className="msg assistant">
            <div className="role">VinChatbot</div>
            <div className="thinking">Thinking…</div>
          </div>
        )}
        <div ref={endRef} />
      </div>
      <Composer onSend={onSend} onStop={onStop} busy={busy} />
    </div>
  );
}
