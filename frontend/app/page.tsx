"use client";

import { useMemo, useRef, useState } from "react";
import type { ChatMessage } from "@/lib/types";
import { postChat } from "@/lib/api";
import { LanguageProvider, type Lang } from "@/lib/i18n";
import { Header } from "@/components/Header";
import { WelcomeState } from "@/components/WelcomeState";
import { ChatColumn } from "@/components/ChatColumn";
import { SourcesPanel, type CiteFocus } from "@/components/SourcesPanel";

let counter = 0;
const nextId = () => `m${Date.now()}-${counter++}`;

export default function Page() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [busy, setBusy] = useState(false);
  const [lang, setLang] = useState<Lang>("en");
  const [citeFocus, setCiteFocus] = useState<CiteFocus | null>(null);
  const focusNonce = useRef(0);

  // One conversation per browser session — the backend's short-term memory key.
  // Reused on every call (send / retry / edit) so context is preserved.
  const conversationId = useRef<string>(
    `web-${Math.random().toString(36).slice(2)}`
  ).current;

  // Lets the Stop button cancel an in-flight /chat fetch.
  const abortRef = useRef<AbortController | null>(null);

  const latestAssistant = useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].role === "assistant") return messages[i];
    }
    return null;
  }, [messages]);

  const lastUserId = useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].role === "user") return messages[i].id;
    }
    return null;
  }, [messages]);

  async function ask(text: string) {
    const controller = new AbortController();
    abortRef.current = controller;
    setBusy(true);
    try {
      const resp = await postChat(
        { message: text, conversation_id: conversationId },
        controller.signal
      );
      setMessages((prev) => [
        ...prev,
        { id: nextId(), role: "assistant", text: resp.answer, response: resp },
      ]);
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") {
        // User stopped it — neutral placeholder, not an error.
        setMessages((prev) => [
          ...prev,
          { id: nextId(), role: "assistant", text: "", cancelled: true },
        ]);
      } else {
        const msg = err instanceof Error ? err.message : "Something went wrong.";
        setMessages((prev) => [
          ...prev,
          { id: nextId(), role: "assistant", text: "", error: msg },
        ]);
      }
    } finally {
      abortRef.current = null;
      setBusy(false);
    }
  }

  function handleSend(text: string) {
    if (busy) return;
    setMessages((prev) => [...prev, { id: nextId(), role: "user", text }]);
    void ask(text);
  }

  function handleStop() {
    abortRef.current?.abort();
  }

  // Retry: drop the failed assistant bubble, re-ask the preceding user message
  // (same conversation_id).
  function handleRetry(errorId: string) {
    if (busy) return;
    setMessages((prev) => {
      const idx = prev.findIndex((m) => m.id === errorId);
      if (idx < 0) return prev;
      let userText = "";
      for (let i = idx - 1; i >= 0; i--) {
        if (prev[i].role === "user") {
          userText = prev[i].text;
          break;
        }
      }
      if (userText) void ask(userText);
      return prev.filter((m) => m.id !== errorId);
    });
  }

  // Edit-last-message: replace the last user turn (and drop anything after it),
  // then resend on the same conversation_id.
  function handleEditLast(text: string) {
    if (busy || !lastUserId) return;
    setMessages((prev) => {
      const idx = prev.findIndex((m) => m.id === lastUserId);
      if (idx < 0) return prev;
      const kept = prev.slice(0, idx);
      void ask(text);
      return [...kept, { id: nextId(), role: "user", text }];
    });
  }

  function handleCiteClick(idx: number) {
    focusNonce.current += 1;
    setCiteFocus({ idx, nonce: focusNonce.current });
  }

  const started = messages.length > 0;

  return (
    <LanguageProvider lang={lang}>
      <div className="app">
        <Header lang={lang} onSetLang={setLang} />
        {!started ? (
          <WelcomeState onSend={handleSend} />
        ) : (
          <div className="split">
            <ChatColumn
              messages={messages}
              busy={busy}
              conversationId={conversationId}
              latestAssistantId={latestAssistant?.id ?? null}
              lastUserId={lastUserId}
              onSend={handleSend}
              onStop={handleStop}
              onRetry={handleRetry}
              onEditLast={handleEditLast}
              onCiteClick={handleCiteClick}
            />
            <SourcesPanel latest={latestAssistant} citeFocus={citeFocus} />
          </div>
        )}
      </div>
    </LanguageProvider>
  );
}
