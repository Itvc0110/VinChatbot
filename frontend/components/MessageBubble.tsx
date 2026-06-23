import React, { useState } from "react";
import type { ChatMessage } from "@/lib/types";
import { deriveState } from "@/lib/responseState";
import { useI18n } from "@/lib/i18n";
import { ChatCitationList } from "./ChatCitationList";
import { FlagForm } from "./FlagForm";
import { StreamingStatus } from "./chat/StreamingStatus";

// Optional inline-citation wiring: turns [1], [2]… in the answer text into clickable
// markers that open the source panel for that exact source.
interface CiteOpts {
  count: number;
  onCite: (idx: number) => void;
}

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

// Minimal, safe inline formatter: turns [text](url) into links, **x** into bold, and a
// bare [n] into a clickable citation marker (when `cite` is provided and n is in range).
// No dangerouslySetInnerHTML. Good enough for baseline; a full markdown lib is deferred.
function renderInline(
  text: string,
  keyPrefix: string,
  cite?: CiteOpts
): React.ReactNode[] {
  const nodes: React.ReactNode[] = [];
  const re = /\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)|\*\*([^*]+)\*\*|\[(\d{1,3})\]/g;
  let last = 0;
  let m: RegExpExecArray | null;
  let i = 0;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) nodes.push(text.slice(last, m.index));
    if (m[1] && m[2]) {
      nodes.push(
        <a key={`${keyPrefix}-l${i}`} href={m[2]} target="_blank" rel="noreferrer">
          {m[1]}
        </a>
      );
    } else if (m[3]) {
      nodes.push(<strong key={`${keyPrefix}-b${i}`}>{m[3]}</strong>);
    } else if (m[4]) {
      const n = parseInt(m[4], 10);
      if (cite && n >= 1 && n <= cite.count) {
        nodes.push(
          <button
            key={`${keyPrefix}-c${i}`}
            className="inline-cite"
            title={`Source ${n}`}
            onClick={() => cite.onCite(n - 1)}
          >
            [{n}]
          </button>
        );
      } else {
        nodes.push(m[0]);
      }
    }
    last = m.index + m[0].length;
    i++;
  }
  if (last < text.length) nodes.push(text.slice(last));
  return nodes;
}

function FormattedBody({ text, cite }: { text: string; cite?: CiteOpts }) {
  const lines = text.split("\n");
  return (
    <div className="body">
      {lines.map((line, idx) => (
        <React.Fragment key={idx}>
          {renderInline(line, `ln${idx}`, cite)}
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
  isLastUser,
  onRetry,
  onEdit,
  onOpenSources,
  extraActions,
}: {
  message: ChatMessage;
  conversationId: string;
  isLastUser: boolean;
  onRetry?: () => void;
  onEdit?: (text: string) => void;
  // Open the shared source drawer for this answer, focused on citation `idx`.
  onOpenSources?: (idx: number) => void;
  // Portal-only: action buttons (Add to calendar / Set reminder / Forward to admin…)
  // rendered under a completed assistant answer. Built by the chat page per message.
  extraActions?: React.ReactNode;
}) {
  const { t } = useI18n();

  if (message.role === "user") {
    return <UserBubble message={message} isLast={isLastUser} onEdit={onEdit} />;
  }

  if (message.error) {
    return (
      <div className="msg assistant error">
        <div className="role">
          <BotAvatar /> Vinnie
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
          <BotAvatar /> Vinnie
        </div>
        <div className="body muted">{t.cancelledShort}</div>
        {onRetry && (
          <button className="retry-btn" onClick={onRetry}>
            {t.regenerate}
          </button>
        )}
      </div>
    );
  }

  // Streaming placeholder: thinking dots until the first token, then the live answer
  // with a blinking caret. The verified ChatResponse (meta + citations) lands on `done`.
  if (message.streaming) {
    return (
      <div className="msg assistant">
        <div className="role">
          <BotAvatar /> Vinnie
        </div>
        {message.text ? (
          <div className="body">
            {renderInline(message.text, "stream")}
            <span className="stream-caret" aria-hidden="true" />
          </div>
        ) : (
          <StreamingStatus statusStep={message.statusStep} />
        )}
      </div>
    );
  }

  const resp = message.response;
  const state = resp ? deriveState(resp) : null;
  const text = resp ? resp.answer : message.text;

  const hasCites = !!resp && resp.citations.length > 0;
  const cite: CiteOpts | undefined = hasCites
    ? { count: resp!.citations.length, onCite: (idx) => onOpenSources?.(idx) }
    : undefined;

  return (
    <div className="msg assistant">
      <div className="role">
        <BotAvatar /> Vinnie
      </div>
      {/* Answer text with inline clickable [n] citations. A refusal simply reads as the
          answer itself — no extra "declined" box. */}
      <FormattedBody text={text} cite={cite} />

      {/* Citations attached directly under the answer they support (every answer). */}
      {hasCites && (
        <ChatCitationList
          citations={resp!.citations}
          unverified={state !== "grounded"}
          onOpen={(idx) => onOpenSources?.(idx)}
        />
      )}

      {extraActions}
      {resp && (
        <div className="bubble-actions">
          <FlagForm
            conversationId={conversationId}
            messageId={message.id}
            answerExcerpt={text.slice(0, 300)}
          />
        </div>
      )}
    </div>
  );
}
