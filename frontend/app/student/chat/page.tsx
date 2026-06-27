"use client";

import { Suspense, useEffect, useRef } from "react";
import { useSearchParams } from "next/navigation";
import { ChatColumn } from "@/components/ChatColumn";
import { Composer } from "@/components/Composer";
import { SourceDrawer } from "@/components/SourceDrawer";
import { ConversationRail } from "@/components/chat/ConversationRail";
import { ConnectedAnswerActions } from "@/components/chat/ConnectedAnswerActions";
import { useChat } from "@/lib/chat";
import { usePortal } from "@/lib/portalI18n";
import { useAuth } from "@/lib/auth";
import { useAsync } from "@/lib/useAsync";
import { getActiveSuggestedQuestions } from "@/lib/api";
import { IconClock, IconBell, IconTicket, IconCalendar, IconChat } from "@/components/shell/icons";

const SUGG_ICONS = [IconClock, IconBell, IconTicket, IconCalendar];

// Full "Ask Vinnie" page. The chat state lives in the shared ChatProvider (mounted in the
// student shell), so this page and the floating bubble are the SAME conversation. Layout only:
// a conversation sidebar (ConversationRail), the center area (an Academic-Horizon welcome state
// when the conversation is empty, otherwise the streaming ChatColumn), and the inline sources
// panel. The streaming/SSE logic in lib/chat + ChatColumn is unchanged.
function ChatView() {
  const { p, lang } = usePortal();
  const { user } = useAuth();
  const chat = useChat();
  const searchParams = useSearchParams();

  const suggested = useAsync(() => getActiveSuggestedQuestions(lang), [lang]);
  const chips =
    suggested.status === "success" && suggested.data.length > 0
      ? suggested.data.map((q) => q.question_text)
      : p.chatSuggested;

  // Register this surface so completed answers don't bump the floating-bubble unread badge.
  useEffect(() => chat.registerViewer(), []); // eslint-disable-line react-hooks/exhaustive-deps

  // Initial question passed via ?q= (from dashboard quick-ask / suggested chips).
  const sentInitial = useRef(false);
  useEffect(() => {
    if (sentInitial.current) return;
    const q = searchParams.get("q");
    if (q && q.trim()) {
      sentInitial.current = true;
      chat.send(q.trim());
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams]);

  // Initial welcome + suggestion cards show only for an empty conversation; once the first
  // message is sent (or an existing conversation with messages is opened) the streaming
  // ChatColumn takes over and these are gone.
  const empty = chat.messages.length === 0;
  const firstName = (user?.name ?? "").split(" ").slice(-1)[0] || user?.name || "";
  const suggestionCards = chips.slice(0, 4);

  return (
    <div className="chat-shell">
      <div className="chat-body">
        <ConversationRail />

        <div className="chat-full">
          {chat.messagesLoading ? (
            <div className="vinnie-welcome-wrap">
              <div className="vinnie-welcome" role="status" aria-busy="true">
                <span className="guard-spinner" />
                <p className="vinnie-welcome-sub">Loading conversation...</p>
              </div>
            </div>
          ) : chat.messagesError ? (
            <div className="vinnie-welcome-wrap">
              <div className="vinnie-welcome" role="alert">
                <p className="vinnie-welcome-sub">{chat.messagesError}</p>
              </div>
            </div>
          ) : empty ? (
            <div className="vinnie-welcome-wrap">
              <div className="vinnie-welcome">
                <span className="vinnie-avatar-lg">
                  <IconChat size={30} />
                </span>
                <h1 className="vinnie-welcome-title">{p.chatWelcomeTitle(firstName)}</h1>
                <p className="vinnie-welcome-sub">{p.chatWelcomeSub}</p>
                <div className="vinnie-sugg-grid">
                  {suggestionCards.map((q, i) => {
                    const Ic = SUGG_ICONS[i % SUGG_ICONS.length];
                    return (
                      <button
                        key={q}
                        className="vinnie-sugg-card"
                        disabled={chat.busy}
                        onClick={() => chat.send(q)}
                      >
                        <span className="vinnie-sugg-icon">
                          <Ic size={18} />
                        </span>
                        <span className="vinnie-sugg-text">{q}</span>
                      </button>
                    );
                  })}
                </div>
              </div>
              <Composer
                onSend={chat.send}
                onStop={chat.stop}
                busy={chat.busy}
                showChips={false}
                note={p.chatTrustNote}
              />
            </div>
          ) : (
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
              composerChips={chips}
              note={p.chatTrustNote}
              composerSeedText={chat.composerSeed?.text}
              composerSeedNonce={chat.composerSeed?.nonce}
            />
          )}
        </div>

        <SourceDrawer
          variant="inline"
          message={chat.sourceMessage}
          focus={chat.sourceFocus}
          onClose={chat.closeSources}
        />
      </div>
    </div>
  );
}

export default function StudentChatPage() {
  return (
    <Suspense fallback={null}>
      <ChatView />
    </Suspense>
  );
}
