"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import type { CSSProperties } from "react";
import Link from "next/link";
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
import { IconClock, IconBell, IconTicket, IconCalendar } from "@/components/shell/icons";
import { LogoVinnie } from "@/components/shell/Logos";

const SUGG_ICONS = [IconClock, IconBell, IconTicket, IconCalendar];
const RAIL_MIN = 76;
const RAIL_DEFAULT = 282;
const RAIL_MAX = 380;
const SOURCE_MIN = 292;
const SOURCE_DEFAULT = 360;
const SOURCE_MAX = 560;

interface SuggestionItem {
  text: string;
  relatedHref?: string;
}

// Full "Ask Vinnie" page. The chat state lives in the shared ChatProvider (mounted in the
// student shell), so this page and the floating bubble are the SAME conversation. Layout only:
// a conversation sidebar (ConversationRail), the center area (an Academic-Horizon welcome state
// when the conversation is empty, otherwise the streaming ChatColumn), and the inline sources
// panel. The streaming/SSE logic in lib/chat + ChatColumn is unchanged.
function ChatView() {
  const { p, lang } = usePortal();
  const { user, token } = useAuth();
  const chat = useChat();
  const searchParams = useSearchParams();
  const [railWidth, setRailWidth] = useState(RAIL_DEFAULT);
  const [sourceWidth, setSourceWidth] = useState(SOURCE_DEFAULT);
  const railCompact = railWidth <= 132;
  const sourceOpen = Boolean(chat.sourceMessage?.response?.citations.length);
  const paneStyle = {
    "--chat-rail-width": `${railWidth}px`,
    "--chat-source-width": `${sourceWidth}px`,
  } as CSSProperties;

  const suggested = useAsync(() => getActiveSuggestedQuestions(lang), [lang, token]);
  const chips =
    suggested.status === "success" && suggested.data.length > 0
      ? suggested.data.map((q) => q.question_text)
      : p.chatSuggested;

  // Register this surface so completed answers don't bump the floating-bubble unread badge.
  useEffect(() => chat.registerViewer(), []); // eslint-disable-line react-hooks/exhaustive-deps

  // Entering the Vinnie AI tab always lands on a fresh conversation (the welcome state) rather
  // than restoring whichever conversation happened to be active — past chats stay available in
  // the rail. A ?q= (dashboard quick-ask / suggested chip) opens its own new conversation and
  // sends the question. Runs once per mount; route changes re-mount and re-run.
  const didInit = useRef(false);
  useEffect(() => {
    if (didInit.current) return;
    // Wait for history to settle: on a direct load the async conversation list reconciles the
    // active conversation, and resetting before that would just get overridden.
    if (chat.historyLoading) return;
    didInit.current = true;
    const q = searchParams.get("q");
    if (q && q.trim()) {
      chat.newConversationWithMessage(q.trim());
    } else {
      chat.newConversation();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chat.historyLoading]);

  // Initial welcome + suggestion cards show only for an empty conversation; once the first
  // message is sent (or an existing conversation with messages is opened) the streaming
  // ChatColumn takes over and these are gone.
  const empty = chat.messages.length === 0;
  const firstName = (user?.name ?? "").split(" ").slice(-1)[0] || user?.name || "";
  const suggestionItems: SuggestionItem[] =
    suggested.status === "success" && suggested.data.length > 0
      ? suggested.data.slice(0, 4).map((question) => ({
          text: question.question_text,
          relatedHref:
            question.source_type === "forum_topic" && question.source_id
              ? `/student/forum/topics/${question.source_id}`
              : undefined,
        }))
      : p.chatSuggested.slice(0, 4).map((text) => ({ text }));

  const beginResize = (
    pane: "rail" | "source",
    event: React.PointerEvent<HTMLButtonElement>
  ) => {
    event.preventDefault();
    const startX = event.clientX;
    const startWidth = pane === "rail" ? railWidth : sourceWidth;
    const min = pane === "rail" ? RAIL_MIN : SOURCE_MIN;
    const max = pane === "rail" ? RAIL_MAX : SOURCE_MAX;

    document.documentElement.classList.add("chat-is-resizing");

    const onMove = (moveEvent: PointerEvent) => {
      const delta = moveEvent.clientX - startX;
      const next =
        pane === "rail" ? startWidth + delta : startWidth - delta;
      const clamped = Math.max(min, Math.min(max, Math.round(next)));
      if (pane === "rail") setRailWidth(clamped);
      else setSourceWidth(clamped);
    };

    const onUp = () => {
      document.documentElement.classList.remove("chat-is-resizing");
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
    };

    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
  };

  const resizeWithKeyboard = (
    pane: "rail" | "source",
    event: React.KeyboardEvent<HTMLButtonElement>
  ) => {
    const key = event.key;
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(key)) return;
    event.preventDefault();

    const setter = pane === "rail" ? setRailWidth : setSourceWidth;
    const min = pane === "rail" ? RAIL_MIN : SOURCE_MIN;
    const max = pane === "rail" ? RAIL_MAX : SOURCE_MAX;
    const dir = pane === "rail" ? 1 : -1;

    if (key === "Home") setter(min);
    if (key === "End") setter(max);
    if (key === "ArrowLeft") {
      setter((w) => Math.max(min, Math.min(max, w - 16 * dir)));
    }
    if (key === "ArrowRight") {
      setter((w) => Math.max(min, Math.min(max, w + 16 * dir)));
    }
  };

  const toggleRail = () => {
    setRailWidth((width) => (width <= 132 ? RAIL_DEFAULT : RAIL_MIN));
  };

  const conversationHead = (
    <div className="pane-head chat-page-head">
      <span>{lang === "vi" ? "Hội thoại" : "Conversation"}</span>
    </div>
  );

  return (
    <div className="chat-shell">
      <div
        className={`chat-body ${railCompact ? "rail-collapsed" : ""} ${
          sourceOpen ? "source-open" : ""
        }`}
        style={paneStyle}
      >
        <div className="chat-side-shell">
          <ConversationRail compact={railCompact} onToggleCompact={toggleRail} />
          <button
            className="chat-resize-handle rail"
            type="button"
            role="separator"
            aria-orientation="vertical"
            aria-label="Resize conversation sidebar"
            aria-valuemin={RAIL_MIN}
            aria-valuemax={RAIL_MAX}
            aria-valuenow={railWidth}
            onPointerDown={(event) => beginResize("rail", event)}
            onKeyDown={(event) => resizeWithKeyboard("rail", event)}
          />
        </div>

        <div className="chat-full">
          {conversationHead}
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
                <span className="vinnie-avatar-lg brand-logo-tile">
                  <LogoVinnie size={62} />
                </span>
                <h1 className="vinnie-welcome-title">{p.chatWelcomeTitle(firstName)}</h1>
                <p className="vinnie-welcome-sub">{p.chatWelcomeSub}</p>
                <div className="vinnie-sugg-grid">
                  {suggestionItems.map((item, i) => {
                    const Ic = SUGG_ICONS[i % SUGG_ICONS.length];
                    return (
                      <div key={item.text} className="vinnie-sugg-wrap">
                        <button
                          className="vinnie-sugg-card"
                          disabled={chat.busy}
                          onClick={() => chat.send(item.text)}
                        >
                          <span className="vinnie-sugg-icon">
                            <Ic size={18} />
                          </span>
                          <span className="vinnie-sugg-text">{item.text}</span>
                        </button>
                        {item.relatedHref && (
                          <Link className="vinnie-sugg-related" href={item.relatedHref}>
                            {p.forum.relatedForumTopic}
                          </Link>
                        )}
                      </div>
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
              showHead={false}
              composerSeedText={chat.composerSeed?.text}
              composerSeedNonce={chat.composerSeed?.nonce}
            />
          )}
        </div>

        {sourceOpen && (
          <button
            className="chat-resize-handle source"
            type="button"
            role="separator"
            aria-orientation="vertical"
            aria-label="Resize sources panel"
            aria-valuemin={SOURCE_MIN}
            aria-valuemax={SOURCE_MAX}
            aria-valuenow={sourceWidth}
            onPointerDown={(event) => beginResize("source", event)}
            onKeyDown={(event) => resizeWithKeyboard("source", event)}
          />
        )}
        <SourceDrawer
          variant="inline"
          width={sourceWidth}
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
