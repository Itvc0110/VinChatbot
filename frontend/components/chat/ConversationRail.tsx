"use client";

import { useChat } from "@/lib/chat";
import { usePortal } from "@/lib/portalI18n";

// Conversation-history rail on the full Ask Vinnie page (PLAN22.6.2 §2). Lists in-memory
// conversations with short topic titles, a "New chat" button, and highlights the active one.
// Switching restores that conversation's messages; both are disabled while a reply streams.
export function ConversationRail() {
  const { p } = usePortal();
  const chat = useChat();
  const onlyEmptyActive =
    chat.conversations.length === 1 && chat.conversations[0].empty;

  return (
    <aside className="convo-rail" aria-label={p.chatHistory.title}>
      <div className="convo-rail-head">
        <span className="convo-rail-title">{p.chatHistory.title}</span>
        <button
          className="btn btn-primary btn-sm convo-new"
          onClick={chat.newConversation}
          disabled={chat.busy}
        >
          + {p.chatHistory.newChat}
        </button>
      </div>

      {onlyEmptyActive ? (
        <p className="convo-empty">{p.chatHistory.empty}</p>
      ) : (
        <ul className="convo-list">
          {chat.conversations.map((c) => (
            <li key={c.id}>
              <button
                className={`convo-item ${c.active ? "active" : ""}`}
                onClick={() => chat.switchConversation(c.id)}
                disabled={chat.busy || c.active}
                aria-current={c.active ? "true" : undefined}
                title={c.title ?? p.chatHistory.untitled}
              >
                {c.title ?? p.chatHistory.untitled}
              </button>
            </li>
          ))}
        </ul>
      )}
    </aside>
  );
}
