import React, { useState } from "react";
import type { ChatMessage } from "@/lib/types";
import { deriveState } from "@/lib/responseState";
import { splitOfficialSources } from "@/lib/officialSources";
import { useI18n } from "@/lib/i18n";
import { AssistantMeta } from "./AssistantMeta";
import { FlagForm } from "./FlagForm";

function BotAvatar() {
  return (
    <span className="bot-avatar" aria-hidden="true">
      <svg viewBox="0 0 24 24" width="13" height="13">
        <path
          fill="#fff"
          d="M12 3 1 8l11 5 9-4.09V14h2V8L12 3zM5 13.18v3.2L12 20l7-3.62v-3.2l-7 3.2-7-3.4z"
        />
      </svg>
    </span>
  );
}

// Minimal, safe inline formatter: turns [text](url) into links and **x** into bold.
// No dangerouslySetInnerHTML. Good enough for baseline; a full markdown lib is deferred.
function renderInline(text: string, keyPrefix: string): React.ReactNode[] {
  const nodes: React.ReactNode[] = [];
  const linkRe = /\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)|\*\*([^*]+)\*\*/g;
  let last = 0;
  let m: RegExpExecArray | null;
  let i = 0;
  while ((m = linkRe.exec(text)) !== null) {
    if (m.index > last) nodes.push(text.slice(last, m.index));
    if (m[1] && m[2]) {
      nodes.push(
        <a key={`${keyPrefix}-l${i}`} href={m[2]} target="_blank" rel="noreferrer">
          {m[1]}
        </a>
      );
    } else if (m[3]) {
      nodes.push(<strong key={`${keyPrefix}-b${i}`}>{m[3]}</strong>);
    }
    last = m.index + m[0].length;
    i++;
  }
  if (last < text.length) nodes.push(text.slice(last));
  return nodes;
}

function FormattedBody({ text }: { text: string }) {
  const lines = text.split("\n");
  return (
    <div className="body">
      {lines.map((line, idx) => (
        <React.Fragment key={idx}>
          {renderInline(line, `ln${idx}`)}
          {idx < lines.length - 1 ? "\n" : null}
        </React.Fragment>
      ))}
    </div>
  );
}

function UserBubble({
  message,
  isLast,
  onEdit,
}: {
  message: ChatMessage;
  isLast: boolean;
  onEdit?: (text: string) => void;
}) {
  const { t } = useI18n();
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(message.text);

  if (editing) {
    return (
      <div className="msg user editing">
        <div className="role">You</div>
        <textarea
          className="edit-area"
          rows={2}
          value={draft}
          autoFocus
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              if (draft.trim()) onEdit?.(draft.trim());
            }
            if (e.key === "Escape") {
              setDraft(message.text);
              setEditing(false);
            }
          }}
        />
        <div className="edit-actions">
          <button
            className="flag-submit"
            disabled={!draft.trim()}
            onClick={() => draft.trim() && onEdit?.(draft.trim())}
          >
            {t.resend}
          </button>
          <button
            className="flag-cancel"
            onClick={() => {
              setDraft(message.text);
              setEditing(false);
            }}
          >
            {t.cancel}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="msg user">
      <FormattedBody text={message.text} />
      {isLast && onEdit && (
        <button
          className="edit-link"
          title={t.edit}
          onClick={() => {
            setDraft(message.text);
            setEditing(true);
          }}
        >
          {t.edit}
        </button>
      )}
    </div>
  );
}

export function MessageBubble({
  message,
  conversationId,
  isLatestAssistant,
  isLastUser,
  onRetry,
  onEdit,
  onCiteClick,
}: {
  message: ChatMessage;
  conversationId: string;
  isLatestAssistant: boolean;
  isLastUser: boolean;
  onRetry?: () => void;
  onEdit?: (text: string) => void;
  onCiteClick?: (idx: number) => void;
}) {
  const { t } = useI18n();

  if (message.role === "user") {
    return <UserBubble message={message} isLast={isLastUser} onEdit={onEdit} />;
  }

  if (message.error) {
    return (
      <div className="msg assistant error">
        <div className="role">
          <BotAvatar /> VinChatbot
        </div>
        <div className="body">{message.error}</div>
        {onRetry && (
          <button className="retry-btn" onClick={onRetry}>
            Retry
          </button>
        )}
      </div>
    );
  }

  if (message.cancelled) {
    return (
      <div className="msg assistant cancelled">
        <div className="role">
          <BotAvatar /> VinChatbot
        </div>
        <div className="body muted">{t.cancelledShort}</div>
      </div>
    );
  }

  // Streaming placeholder: thinking dots until the first token, then the live answer
  // with a blinking caret. The verified ChatResponse (meta + citations) lands on `done`.
  if (message.streaming) {
    return (
      <div className="msg assistant">
        <div className="role">
          <BotAvatar /> VinChatbot
        </div>
        {message.text ? (
          <div className="body">
            {renderInline(message.text, "stream")}
            <span className="stream-caret" aria-hidden="true" />
          </div>
        ) : (
          <div className="thinking" role="status" aria-label={t.retrieving}>
            <span className="tdot" />
            <span className="tdot" />
            <span className="tdot" />
          </div>
        )}
      </div>
    );
  }

  const resp = message.response;
  const state = resp ? deriveState(resp) : null;
  const { body } = resp
    ? splitOfficialSources(resp.answer)
    : { body: message.text };

  // Inline citation markers only on the LATEST grounded answer — that's the one the
  // panel currently reflects, so the scroll target exists.
  const showCites =
    isLatestAssistant &&
    state === "grounded" &&
    resp !== undefined &&
    resp.citations.length > 0;

  return (
    <div className="msg assistant">
      <div className="role">
        <BotAvatar /> VinChatbot
      </div>
      <FormattedBody text={body} />
      {showCites && (
        <div className="cite-markers">
          <span className="cite-markers-label">{t.sourcesLabel}</span>
          {resp!.citations.map((_, i) => (
            <button
              key={i}
              className="cite-marker"
              title={`Jump to source ${i + 1}`}
              onClick={() => onCiteClick?.(i)}
            >
              [{i + 1}]
            </button>
          ))}
        </div>
      )}
      {resp && <AssistantMeta response={resp} />}
      {resp && (
        <div className="bubble-actions">
          <FlagForm
            conversationId={conversationId}
            messageId={message.id}
            answerExcerpt={body.slice(0, 300)}
          />
        </div>
      )}
    </div>
  );
}
