"use client";

import { Suspense, useEffect, useRef } from "react";
import { useSearchParams } from "next/navigation";
import { ChatColumn } from "@/components/ChatColumn";
import { SourceDrawer } from "@/components/SourceDrawer";
import { ConnectedAnswerActions } from "@/components/chat/ConnectedAnswerActions";
import { Toast } from "@/components/ui/primitives";
import { useChat } from "@/lib/chat";
import { usePortal } from "@/lib/portalI18n";
import { useI18n } from "@/lib/i18n";

// Full "Ask Vinnie" page. The chat state lives in the shared ChatProvider (mounted in
// RoleShell), so this page and the floating bubble are the SAME conversation. Sources are
// hidden by default and open only when the user clicks an answer's Sources button / chip.
function ChatView() {
  const { p } = usePortal();
  const { t } = useI18n();
  const chat = useChat();
  const searchParams = useSearchParams();

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

  return (
    <div className="chat-shell">
      {/* When a source is open the page splits in two: conversation + source panel.
          Closing the panel returns the conversation to full width. */}
      <div className="chat-body">
        <div className="chat-full">
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
            composerChips={p.chatSuggested}
            note={t.privacyNote}
          />
        </div>

        <SourceDrawer
          variant="inline"
          message={chat.sourceMessage}
          focus={chat.sourceFocus}
          onClose={chat.closeSources}
        />
      </div>

      {chat.toast && <Toast message={chat.toast} onClose={() => chat.setToast(null)} />}
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
