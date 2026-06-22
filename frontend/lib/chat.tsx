"use client";

// Global chat state for the student portal. Lifts the conversation out of the chat page
// so the full "Ask Vinnie" page AND the floating chat bubble share ONE conversation that
// survives route changes. Mounted once in RoleShell for students (see RoleShell.tsx).
//
// The general/personal toggle is gone: the student is signed in, so every question is sent
// with their profile/schedule/deadlines/tuition context attached and the backend agent
// decides what it actually needs. Sources are no longer shown by default — each answer
// carries its own citations and a "Sources" button that opens the shared source drawer.

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import type { ChatMessage, ChatResponse } from "@/lib/types";
import type {
  ClassSession,
  Deadline,
  StudentProfile,
  TuitionStatus,
} from "@/lib/portalTypes";
import {
  postChat,
  postChatStream,
  getStudentProfile,
  getStudentSchedule,
  getStudentDeadlines,
  getTuitionStatus,
  forwardToAdmin,
} from "@/lib/api";
import { usePortal } from "@/lib/portalI18n";
import { formatVnd, formatDate } from "@/lib/format";

let counter = 0;
const nextId = () => `m${Date.now()}-${counter++}`;

// Compact, plain-text snapshot of the student's context, prepended to the question so the
// agent can personalize ("when is my next class?") without the user choosing a mode.
function buildPersonalContext(
  profile: StudentProfile | null,
  schedule: ClassSession[],
  deadlines: Deadline[],
  tuition: TuitionStatus | null
): string {
  const lines: string[] = ["[Student context — personalize the answer using this when relevant]"];
  if (profile) {
    lines.push(
      `Name: ${profile.full_name}; Program: ${profile.program}; Year ${profile.year}; Student ID ${profile.student_id}; GPA ${profile.gpa}; Credits ${profile.credits_earned}/${profile.credits_required}.`
    );
  }
  if (tuition) {
    lines.push(
      `Tuition: paid ${formatVnd(tuition.total_paid_vnd)} of ${formatVnd(
        tuition.total_charged_vnd
      )}, balance ${formatVnd(tuition.balance_vnd)}${
        tuition.next_due_at
          ? `, next installment ${formatVnd(
              tuition.next_due_amount_vnd ?? 0
            )} due ${formatDate(tuition.next_due_at)}`
          : ""
      }.`
    );
  }
  if (deadlines.length) {
    lines.push(
      "Upcoming deadlines: " +
        deadlines.slice(0, 5).map((d) => `${d.title} (${formatDate(d.due_at)})`).join("; ") +
        "."
    );
  }
  if (schedule.length) {
    lines.push(
      "Weekly classes: " +
        schedule
          .map((s) => `${s.day} ${s.start}-${s.end} ${s.course_title} (${s.room})`)
          .join("; ") +
        "."
    );
  }
  return lines.join("\n");
}

export interface SourceFocus {
  idx: number;
  nonce: number;
}

interface ChatContextValue {
  messages: ChatMessage[];
  busy: boolean;
  conversationId: string;
  latestAssistantId: string | null;
  lastUserId: string | null;
  send: (text: string) => void;
  stop: () => void;
  retry: (errorId: string) => void;
  editLast: (text: string) => void;
  questionFor: (assistantId: string) => string;
  // shared source drawer (full page + floating widget point at the same one)
  sourceMessage: ChatMessage | null;
  sourceFocus: SourceFocus | null;
  openSources: (messageId: string, focusIdx?: number) => void;
  closeSources: () => void;
  // forward-to-admin + transient toast
  toast: string | null;
  setToast: (msg: string | null) => void;
  forward: (question: string, response: ChatResponse) => Promise<void>;
  // floating-bubble unread badge: answers that arrived while no surface was open
  unread: number;
  registerViewer: () => () => void;
}

const ChatContext = createContext<ChatContextValue | null>(null);

export function ChatProvider({ children }: { children: React.ReactNode }) {
  const { p } = usePortal();

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [busy, setBusy] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const [sourceMessageId, setSourceMessageId] = useState<string | null>(null);
  const [sourceFocus, setSourceFocus] = useState<SourceFocus | null>(null);
  const [unread, setUnread] = useState(0);
  const focusNonce = useRef(0);

  // How many surfaces (full page / open widget) are currently showing the conversation.
  // While >0, completed answers don't bump the unread badge.
  const viewers = useRef(0);

  const personalData = useRef<{
    profile: StudentProfile | null;
    schedule: ClassSession[];
    deadlines: Deadline[];
    tuition: TuitionStatus | null;
  }>({ profile: null, schedule: [], deadlines: [], tuition: null });

  useEffect(() => {
    let alive = true;
    Promise.all([
      getStudentProfile(),
      getStudentSchedule(),
      getStudentDeadlines(),
      getTuitionStatus(),
    ])
      .then(([profile, schedule, deadlines, tuition]) => {
        if (alive) personalData.current = { profile, schedule, deadlines, tuition };
      })
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, []);

  const conversationId = useRef<string>(
    `web-${Math.random().toString(36).slice(2)}`
  ).current;
  const abortRef = useRef<AbortController | null>(null);

  const latestAssistantId = useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].role === "assistant") return messages[i].id;
    }
    return null;
  }, [messages]);

  const lastUserId = useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].role === "user") return messages[i].id;
    }
    return null;
  }, [messages]);

  const patchMessage = useCallback((id: string, patch: Partial<ChatMessage>) => {
    setMessages((prev) => prev.map((m) => (m.id === id ? { ...m, ...patch } : m)));
  }, []);

  // Marks a finished answer: bumps the unread badge if nothing is on screen to read it.
  const settle = useCallback((id: string, patch: Partial<ChatMessage>) => {
    patchMessage(id, patch);
    if (!patch.error && !patch.cancelled && viewers.current === 0) {
      setUnread((u) => u + 1);
    }
  }, [patchMessage]);

  const ask = useCallback(
    async (text: string) => {
      const controller = new AbortController();
      abortRef.current = controller;
      setBusy(true);

      const assistantId = nextId();
      setMessages((prev) => [
        ...prev,
        { id: assistantId, role: "assistant", text: "", streaming: true, personalized: true },
      ]);
      let streamed = false;

      const sent = `${buildPersonalContext(
        personalData.current.profile,
        personalData.current.schedule,
        personalData.current.deadlines,
        personalData.current.tuition
      )}\n\nQuestion: ${text}`;

      try {
        const resp = await postChatStream(
          { message: sent, conversation_id: conversationId },
          {
            signal: controller.signal,
            onDelta: (chunk) => {
              streamed = true;
              setMessages((prev) =>
                prev.map((m) => (m.id === assistantId ? { ...m, text: m.text + chunk } : m))
              );
            },
          }
        );
        settle(assistantId, { text: resp.answer, response: resp, streaming: false });
      } catch (err) {
        if (err instanceof DOMException && err.name === "AbortError") {
          patchMessage(assistantId, { text: "", cancelled: true, streaming: false });
        } else if (!streamed) {
          try {
            const resp = await postChat(
              { message: sent, conversation_id: conversationId },
              controller.signal
            );
            settle(assistantId, { text: resp.answer, response: resp, streaming: false });
          } catch (err2) {
            if (err2 instanceof DOMException && err2.name === "AbortError") {
              patchMessage(assistantId, { text: "", cancelled: true, streaming: false });
            } else {
              const msg = err2 instanceof Error ? err2.message : p.somethingWrong;
              patchMessage(assistantId, { text: "", error: msg, streaming: false });
            }
          }
        } else {
          const msg = err instanceof Error ? err.message : p.somethingWrong;
          patchMessage(assistantId, { text: "", error: msg, streaming: false });
        }
      } finally {
        abortRef.current = null;
        setBusy(false);
      }
    },
    [conversationId, patchMessage, settle, p]
  );

  const send = useCallback(
    (text: string) => {
      if (busy) return;
      setMessages((prev) => [...prev, { id: nextId(), role: "user", text }]);
      void ask(text);
    },
    [busy, ask]
  );

  const stop = useCallback(() => abortRef.current?.abort(), []);

  const retry = useCallback(
    (errorId: string) => {
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
    },
    [busy, ask]
  );

  const editLast = useCallback(
    (text: string) => {
      if (busy || !lastUserId) return;
      setMessages((prev) => {
        const idx = prev.findIndex((m) => m.id === lastUserId);
        if (idx < 0) return prev;
        const kept = prev.slice(0, idx);
        void ask(text);
        return [...kept, { id: nextId(), role: "user", text }];
      });
    },
    [busy, lastUserId, ask]
  );

  const questionFor = useCallback(
    (assistantId: string): string => {
      const idx = messages.findIndex((m) => m.id === assistantId);
      for (let i = idx - 1; i >= 0; i--) {
        if (messages[i].role === "user") return messages[i].text;
      }
      return "";
    },
    [messages]
  );

  const openSources = useCallback((messageId: string, focusIdx = 0) => {
    focusNonce.current += 1;
    setSourceMessageId(messageId);
    setSourceFocus({ idx: focusIdx, nonce: focusNonce.current });
  }, []);

  const closeSources = useCallback(() => {
    setSourceMessageId(null);
    setSourceFocus(null);
  }, []);

  const forward = useCallback(
    async (question: string, response: ChatResponse) => {
      try {
        const ticket = await forwardToAdmin({
          subject: question.slice(0, 80) || "Forwarded question",
          body: response.answer,
          origin_question: question,
        });
        setToast(p.forwardedOk(ticket.id));
      } catch {
        setToast(p.forwardFailed);
      }
    },
    [p]
  );

  const registerViewer = useCallback(() => {
    viewers.current += 1;
    setUnread(0);
    return () => {
      viewers.current = Math.max(0, viewers.current - 1);
    };
  }, []);

  const sourceMessage = useMemo(
    () => messages.find((m) => m.id === sourceMessageId) ?? null,
    [messages, sourceMessageId]
  );

  const value: ChatContextValue = {
    messages,
    busy,
    conversationId,
    latestAssistantId,
    lastUserId,
    send,
    stop,
    retry,
    editLast,
    questionFor,
    sourceMessage,
    sourceFocus,
    openSources,
    closeSources,
    toast,
    setToast,
    forward,
    unread,
    registerViewer,
  };

  return <ChatContext.Provider value={value}>{children}</ChatContext.Provider>;
}

export function useChat(): ChatContextValue {
  const ctx = useContext(ChatContext);
  if (!ctx) throw new Error("useChat must be used within a ChatProvider");
  return ctx;
}
