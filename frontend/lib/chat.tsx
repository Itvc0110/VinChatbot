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
  TicketDraft,
  TuitionStatus,
} from "@/lib/portalTypes";
import {
  postChat,
  postChatStream,
  getStudentProfile,
  getStudentSchedule,
  getStudentDeadlines,
  getTuitionStatus,
  submitTicket,
  saveTicketDraft,
} from "@/lib/api";
import { DEPARTMENTS } from "@/lib/portalI18n";
import { usePortal } from "@/lib/portalI18n";
import { friendlyError } from "@/lib/chatErrors";
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

// Privacy-safe context for a support ticket: ONLY the triggering question + Vinnie's
// answer, trimmed. Deliberately excludes buildPersonalContext() (name/GPA/tuition/schedule)
// so no profile PII can leak into a ticket. Shown in the Review drawer and attached only if
// the student keeps "include chat context" ticked.
function shortSummary(question: string, answer: string): string {
  const q = question.replace(/\s+/g, " ").trim().slice(0, 300);
  const a = answer.replace(/\s+/g, " ").trim().slice(0, 600);
  return `Question: ${q}\n\nVinnie's answer: ${a}`;
}

let draftCounter = 0;
const nextDraftId = () => `draft-${Date.now()}-${draftCounter++}`;

let convCounter = 0;
const nextConvId = () => `c${Date.now()}-${convCounter++}`;
const newThreadId = () => `web-${Math.random().toString(36).slice(2)}`;

// A short topic title from the first user message (PLAN22.6.2 §2) — never a generic name.
function titleOf(msgs: ChatMessage[]): string | null {
  const firstUser = msgs.find((m) => m.role === "user");
  if (!firstUser) return null;
  const text = firstUser.text.replace(/\s+/g, " ").trim();
  return text.length > 44 ? `${text.slice(0, 44)}…` : text;
}

interface ArchivedConversation {
  id: string;
  conversationId: string;
  title: string | null;
  messages: ChatMessage[];
}

export interface SourceFocus {
  idx: number;
  nonce: number;
}

// One item in the conversation-history list shown on the full chat page.
export interface ConversationSummary {
  id: string;
  title: string | null; // null until the first user message gives it a topic
  active: boolean;
  empty: boolean;
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
  // Conversation history (PLAN22.6.2 §2). In-memory only — conversations are NOT persisted
  // to storage, so sensitive student data never lingers across sessions.
  conversations: ConversationSummary[];
  activeConversationId: string;
  newConversation: () => void;
  switchConversation: (id: string) => void;
  // "Ask follow-up": seeds + focuses the composer (shared across both chat surfaces).
  composerSeed: { text: string; nonce: number } | null;
  seedComposer: (text: string) => void;
  // shared source drawer (full page + floating widget point at the same one)
  sourceMessage: ChatMessage | null;
  sourceFocus: SourceFocus | null;
  openSources: (messageId: string, focusIdx?: number) => void;
  closeSources: () => void;
  // transient toast
  toast: string | null;
  setToast: (msg: string | null) => void;
  // Smart ticket draft (PLAN22.6): Vinnie prepares a draft → student reviews → sends. The
  // draft lives here in React state only (never persisted) until the student submits.
  ticketDraft: TicketDraft | null;
  prepareDraftFromAnswer: (question: string, response: ChatResponse) => void;
  prepareBlankDraft: (seed?: Partial<TicketDraft>) => void;
  updateDraft: (patch: Partial<TicketDraft>) => void;
  cancelDraft: () => void;
  saveDraft: () => Promise<void>;
  submitDraft: () => Promise<void>;
  draftBusy: boolean;
  // Bumps each time a ticket is successfully sent to admin (the single submit path), so any
  // open ticket list (e.g. the support page) can refresh without a hard reload.
  ticketsRevision: number;
  // floating-bubble unread badge: answers that arrived while no surface was open
  unread: number;
  registerViewer: () => () => void;
}

const ChatContext = createContext<ChatContextValue | null>(null);

export function ChatProvider({ children }: { children: React.ReactNode }) {
  const { p, lang } = usePortal();

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [busy, setBusy] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const [ticketDraft, setTicketDraft] = useState<TicketDraft | null>(null);
  const [draftBusy, setDraftBusy] = useState(false);
  const [ticketsRevision, setTicketsRevision] = useState(0);
  const [composerSeed, setComposerSeed] = useState<{ text: string; nonce: number } | null>(null);
  const seedNonce = useRef(0);
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

  // Active conversation: its messages live in `messages` above; past conversations are kept
  // in `archived` (in-memory only). `conversationId` is the backend thread id of the active
  // conversation, so each conversation has isolated agent memory.
  const [conversationId, setConversationId] = useState<string>(() => newThreadId());
  const [activeConvId, setActiveConvId] = useState<string>(() => nextConvId());
  const [archived, setArchived] = useState<ArchivedConversation[]>([]);
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
      // True once the stream has produced ANY event (status or delta) — i.e. the /chat/stream
      // endpoint opened successfully. We only fall back to the non-streaming /chat (a full,
      // expensive agent re-run) when the stream never opened at all; a failure AFTER it opened
      // is shown as an error, not retried.
      let received = false;

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
              received = true;
              setMessages((prev) =>
                prev.map((m) => (m.id === assistantId ? { ...m, text: m.text + chunk } : m))
              );
            },
            // Fires on the stream's opening `status` event (and any later real step). Marks the
            // stream as opened, and shows the step text when present (else the localized
            // "Searching…" placeholder).
            onStatus: (step) => {
              received = true;
              patchMessage(assistantId, { statusStep: step });
            },
          }
        );
        settle(assistantId, { text: resp.answer, response: resp, streaming: false });
      } catch (err) {
        if (err instanceof DOMException && err.name === "AbortError") {
          patchMessage(assistantId, { text: "", cancelled: true, streaming: false });
        } else if (!received) {
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
              patchMessage(assistantId, {
                text: "",
                error: friendlyError(err2, lang),
                streaming: false,
              });
            }
          }
        } else {
          patchMessage(assistantId, {
            text: "",
            error: friendlyError(err, lang),
            streaming: false,
          });
        }
      } finally {
        abortRef.current = null;
        setBusy(false);
      }
    },
    [conversationId, patchMessage, settle, lang]
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

  // --- Smart ticket draft (review-before-send) -------------------------------
  const prepareDraftFromAnswer = useCallback(
    (question: string, response: ChatResponse) => {
      setTicketDraft({
        id: nextDraftId(),
        subject: (question.trim().slice(0, 80) || "Support request"),
        body: response.answer,
        department: DEPARTMENTS[0],
        category: "other",
        priority: "medium",
        include_chat_context: false,
        source_conversation_id: conversationId,
        origin_question: question,
        context_preview: shortSummary(question, response.answer),
      });
    },
    [conversationId]
  );

  // `seed` lets a manual entry point (CreateTicketModal) pre-fill the draft before it hands
  // off to the ReviewTicketDrawer — creation still flows through the single submit path.
  const prepareBlankDraft = useCallback(
    (seed?: Partial<TicketDraft>) => {
      setTicketDraft({
        id: nextDraftId(),
        subject: "",
        body: "",
        department: DEPARTMENTS[0],
        category: "academic",
        priority: "medium",
        include_chat_context: false,
        source_conversation_id: conversationId,
        context_preview: "",
        ...seed,
      });
    },
    [conversationId]
  );

  const updateDraft = useCallback((patch: Partial<TicketDraft>) => {
    setTicketDraft((cur) => (cur ? { ...cur, ...patch } : cur));
  }, []);

  const cancelDraft = useCallback(() => {
    setTicketDraft(null);
    setDraftBusy(false);
  }, []);

  const saveDraft = useCallback(async () => {
    if (!ticketDraft) return;
    // No network in MVP — the draft already lives in state; this just confirms to the user.
    await saveTicketDraft(ticketDraft);
    setTicketDraft(null);
    setToast(p.review.draftSaved);
  }, [ticketDraft, p]);

  const submitDraft = useCallback(async () => {
    if (!ticketDraft || draftBusy) return;
    setDraftBusy(true);
    try {
      const ticket = await submitTicket(ticketDraft);
      setTicketDraft(null);
      setTicketsRevision((r) => r + 1);
      setToast(p.review.submitted(ticket.id));
    } catch {
      setToast(p.review.submitFailed);
    } finally {
      setDraftBusy(false);
    }
  }, [ticketDraft, draftBusy, p]);

  const seedComposer = useCallback((text: string) => {
    seedNonce.current += 1;
    setComposerSeed({ text, nonce: seedNonce.current });
  }, []);

  // --- Conversation history -------------------------------------------------
  // Archive the active conversation (only if it has messages) and reset to a fresh one.
  const newConversation = useCallback(() => {
    if (busy) return;
    if (messages.length) {
      setArchived((prev) => [
        { id: activeConvId, conversationId, title: titleOf(messages), messages },
        ...prev,
      ]);
    }
    setMessages([]);
    setConversationId(newThreadId());
    setActiveConvId(nextConvId());
    setSourceMessageId(null);
    setSourceFocus(null);
  }, [busy, messages, activeConvId, conversationId]);

  // Restore an archived conversation, archiving the current one in its place.
  const switchConversation = useCallback(
    (id: string) => {
      if (busy || id === activeConvId) return;
      const target = archived.find((c) => c.id === id);
      if (!target) return;
      setArchived((prev) => {
        const without = prev.filter((c) => c.id !== id);
        return messages.length
          ? [
              { id: activeConvId, conversationId, title: titleOf(messages), messages },
              ...without,
            ]
          : without;
      });
      setMessages(target.messages);
      setConversationId(target.conversationId);
      setActiveConvId(target.id);
      setSourceMessageId(null);
      setSourceFocus(null);
    },
    [busy, activeConvId, archived, messages, conversationId]
  );

  const conversations = useMemo<ConversationSummary[]>(
    () => [
      { id: activeConvId, title: titleOf(messages), active: true, empty: messages.length === 0 },
      ...archived.map((c) => ({
        id: c.id,
        title: c.title,
        active: false,
        empty: c.messages.length === 0,
      })),
    ],
    [activeConvId, messages, archived]
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
    conversations,
    activeConversationId: activeConvId,
    newConversation,
    switchConversation,
    composerSeed,
    seedComposer,
    sourceMessage,
    sourceFocus,
    openSources,
    closeSources,
    toast,
    setToast,
    ticketDraft,
    prepareDraftFromAnswer,
    prepareBlankDraft,
    updateDraft,
    cancelDraft,
    saveDraft,
    submitDraft,
    draftBusy,
    ticketsRevision,
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
