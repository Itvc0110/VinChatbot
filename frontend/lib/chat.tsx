"use client";

// Global chat state for the student portal. Lifts the conversation out of the chat page
// so the full "Ask Vinnie" page AND the floating chat bubble share ONE set of conversations
// that survive route changes. Mounted once in StudentShell (see StudentShell.tsx).
//
// Multi-conversation model: every conversation keeps its OWN messages and its own
// busy/streaming state, so a reply can stream in conversation A while the user reads or asks
// in conversation B — answers always land in the conversation that asked them (each in-flight
// request is keyed by the conversation's UI id). Conversations are ordered by last activity;
// selecting one never reorders, only SENDING a message bumps a conversation to the top.
//
// The general/personal toggle is gone: the student is signed in, so every question is
// personalized. Phase 14A moved personalization to a backend-owned context layer — the chat
// route builds the student's context server-side from authenticated data and attaches it to
// the agent; the frontend sends only the raw question. Sources are no longer shown by default —
// each answer carries its own citations and a "Sources" button that opens the shared drawer.

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
import type { TicketDraft } from "@/lib/portalTypes";
import {
  deleteConversation as deleteBackendConversation,
  getConversationMessages,
  getConversations,
  postChat,
  postChatStream,
  submitTicket,
  suggestTicketDraft,
  saveTicketDraft,
  updateConversation,
  type BackendConversationMessage,
  type BackendConversationSummary,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { DEPARTMENTS } from "@/lib/portalI18n";
import { usePortal } from "@/lib/portalI18n";
import { friendlyError } from "@/lib/chatErrors";

let counter = 0;
const nextId = () => `m${Date.now()}-${counter++}`;

// Activity ordering: backend rows sort by server timestamps; local drafts/sends get a separate
// priority so a newly created active chat stays first even if demo data has future timestamps.
let localOrderSeq = 0;
let stableOrderSeq = 0;
const nextLocalOrder = () => ++localOrderSeq;
const nextStableOrder = () => ++stableOrderSeq;

// Privacy-safe context for a support ticket: ONLY the triggering question + Vinnie's
// answer, trimmed. Deliberately excludes any profile PII (name/GPA/tuition/schedule) so none
// can leak into a ticket. Shown in the Review drawer and attached only if the student keeps
// "include chat context" ticked.
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
const threadIdForDbConversation = (id: string) => `db-${id}`;

// A short topic title from a free-text message (PLAN22.6.2 §2) — never a generic name.
function titleFromText(text: string): string {
  const t = text.replace(/\s+/g, " ").trim();
  return t.length > 44 ? `${t.slice(0, 44)}…` : t;
}

function parseIsoTime(iso?: string | null): number | null {
  if (!iso) return null;
  const parsed = Date.parse(iso);
  return Number.isNaN(parsed) ? null : parsed;
}

function activityFromIso(iso?: string | null): number {
  return parseIsoTime(iso) ?? Date.now();
}

function activityFromSummary(summary: BackendConversationSummary): number {
  return (
    parseIsoTime(summary.last_message_at) ??
    parseIsoTime(summary.updated_at) ??
    parseIsoTime(summary.created_at) ??
    0
  );
}

function displayContentFromStoredUserMessage(content: string): string {
  const marker = "\n\nQuestion:";
  const idx = content.lastIndexOf(marker);
  if (idx === -1) return content;
  return content.slice(idx + marker.length).trimStart();
}

function chatResponseFromStoredMessage(message: BackendConversationMessage): ChatResponse {
  const raw = message.answer_json;
  const answer = typeof raw?.answer === "string" ? raw.answer : message.content;
  return {
    answer,
    citations: Array.isArray(raw?.citations) ? (raw.citations as ChatResponse["citations"]) : [],
    confidence:
      typeof raw?.confidence === "number"
        ? raw.confidence
        : message.confidence ?? 0,
    tool_trace: Array.isArray(raw?.tool_trace)
      ? (raw.tool_trace as ChatResponse["tool_trace"])
      : [],
    needs_human_review:
      typeof raw?.needs_human_review === "boolean"
        ? raw.needs_human_review
        : message.needs_human_review,
    db_conversation_id:
      typeof raw?.db_conversation_id === "string"
        ? raw.db_conversation_id
        : message.conversation_id,
  };
}

// Internal record for one conversation. `title === null` means "untitled" (the UI shows a
// localized temporary label); `titleManual` is set when the student renames it, so later
// auto-titling never overwrites a manual name.
interface Conversation {
  id: string; // stable UI id
  threadId: string; // backend conversation_id (isolated agent memory per conversation)
  dbConversationId: string | null; // Postgres conversation UUID used by Phase 9 persistence
  title: string | null;
  titleManual: boolean;
  messages: ChatMessage[];
  messagesLoaded: boolean;
  messagesLoading: boolean;
  messagesError: string | null;
  busy: boolean; // a reply is in flight for THIS conversation
  lastActivity: number; // backend/server timestamp ordering key (newest first)
  localOrder: number; // local draft/send priority; non-zero sorts above persisted history
  stableOrder: number; // tie-breaker that preserves deterministic ordering
}

function makeConversation(patch: Partial<Conversation> = {}): Conversation {
  return {
    id: nextConvId(),
    threadId: newThreadId(),
    dbConversationId: null,
    title: null,
    titleManual: false,
    messages: [],
    messagesLoaded: true,
    messagesLoading: false,
    messagesError: null,
    busy: false,
    lastActivity: Date.now(),
    localOrder: nextLocalOrder(),
    stableOrder: nextStableOrder(),
    ...patch,
  };
}

function conversationFromSummary(
  summary: BackendConversationSummary,
  stableOrder: number
): Conversation {
  return makeConversation({
    id: summary.id,
    threadId: threadIdForDbConversation(summary.id),
    dbConversationId: summary.id,
    title: summary.title || null,
    titleManual: Boolean(summary.title_manual),
    messages: [],
    messagesLoaded: false,
    lastActivity: activityFromSummary(summary),
    localOrder: 0,
    stableOrder,
  });
}

function sortConversations(a: Conversation, b: Conversation): number {
  if (a.localOrder !== b.localOrder) return b.localOrder - a.localOrder;
  if (a.lastActivity !== b.lastActivity) return b.lastActivity - a.lastActivity;
  return a.stableOrder - b.stableOrder;
}

function chatMessageFromBackend(message: BackendConversationMessage): ChatMessage | null {
  if (message.role === "user") {
    return {
      id: message.id,
      role: "user",
      text: displayContentFromStoredUserMessage(message.content),
    };
  }
  if (message.role === "assistant") {
    const response = chatResponseFromStoredMessage(message);
    return {
      id: message.id,
      role: "assistant",
      text: response.answer,
      response,
      personalized: true,
    };
  }
  return null;
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
  busy: boolean; // still receiving an answer (shows a subtle indicator in the rail)
  persisted: boolean;
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
  // Conversation history. Persisted conversations come from the backend; unsent local drafts
  // remain in memory only and are never stored in localStorage.
  conversations: ConversationSummary[];
  activeConversationId: string;
  historyLoading: boolean;
  historyError: string | null;
  messagesLoading: boolean;
  messagesError: string | null;
  newConversation: () => void;
  // Start a fresh conversation AND immediately send `text` into it (used by the dashboard
  // quick-ask ?q= flow so each quick-ask opens its own new conversation).
  newConversationWithMessage: (text: string) => void;
  switchConversation: (id: string) => void;
  renameConversation: (id: string, title: string) => void;
  deleteConversation: (id: string) => void;
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
  prepareDraftFromAnswer: (question: string, response: ChatResponse) => Promise<void>;
  prepareBlankDraft: (seed?: Partial<TicketDraft>) => void;
  // True while Vinnie's draft suggestion is being fetched (the drawer shows a "drafting…" state).
  draftSuggesting: boolean;
  updateDraft: (patch: Partial<TicketDraft>) => void;
  cancelDraft: () => void;
  // `override` lets a self-contained form (e.g. CreateTicketModal) submit/save a fully-built
  // draft in one step, bypassing the in-state draft used by the Review drawer. Returns whether
  // it succeeded so the caller can decide to close. The single submit path (api.submitTicket)
  // is unchanged either way.
  saveDraft: (override?: TicketDraft) => Promise<boolean>;
  submitDraft: (override?: TicketDraft) => Promise<boolean>;
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
  const { isAuthenticated, isLoading: authLoading, token } = useAuth();

  // All conversations live here; the active one is identified by `activeId`. Each conversation
  // carries its own messages + busy flag, so streaming is naturally per-conversation.
  const [conversations, setConversations] = useState<Conversation[]>(() => [makeConversation()]);
  const [activeId, setActiveId] = useState<string>(() => conversations[0].id);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState<string | null>(null);

  const [toast, setToast] = useState<string | null>(null);
  const [ticketDraft, setTicketDraft] = useState<TicketDraft | null>(null);
  const [draftBusy, setDraftBusy] = useState(false);
  const [draftSuggesting, setDraftSuggesting] = useState(false);
  const [ticketsRevision, setTicketsRevision] = useState(0);
  const [composerSeed, setComposerSeed] = useState<{ text: string; nonce: number } | null>(null);
  const seedNonce = useRef(0);
  const [sourceMessageId, setSourceMessageId] = useState<string | null>(null);
  const [sourceFocus, setSourceFocus] = useState<SourceFocus | null>(null);
  const [unread, setUnread] = useState(0);
  const focusNonce = useRef(0);
  const historyRequestId = useRef(0);
  const historyToken = useRef<string | null>(null);
  const conversationsRef = useRef(conversations);
  const activeIdRef = useRef(activeId);

  // How many surfaces (full page / open widget) are currently showing the conversation.
  // While >0, completed answers don't bump the unread badge.
  const viewers = useRef(0);

  // In-flight requests keyed by conversation UI id, so we can abort/stop a specific one and
  // never confuse two conversations' streams.
  const abortMap = useRef<Map<string, AbortController>>(new Map());

  useEffect(() => {
    conversationsRef.current = conversations;
  }, [conversations]);

  useEffect(() => {
    activeIdRef.current = activeId;
  }, [activeId]);

  useEffect(() => {
    if (authLoading) return;
    if (!isAuthenticated || !token) {
      historyRequestId.current += 1;
      historyToken.current = null;
      const empty = makeConversation();
      conversationsRef.current = [empty];
      activeIdRef.current = empty.id;
      setConversations([empty]);
      setActiveId(empty.id);
      setHistoryLoading(false);
      setHistoryError(null);
      setSourceMessageId(null);
      setSourceFocus(null);
      setTicketDraft(null);
      setUnread(0);
      return;
    }

    const tokenChanged = historyToken.current !== token;
    historyToken.current = token;
    if (tokenChanged) {
      abortMap.current.forEach((controller) => controller.abort());
      abortMap.current.clear();
      const empty = makeConversation();
      conversationsRef.current = [empty];
      activeIdRef.current = empty.id;
      setConversations([empty]);
      setActiveId(empty.id);
      setSourceMessageId(null);
      setSourceFocus(null);
      setTicketDraft(null);
      setUnread(0);
    }

    const requestId = historyRequestId.current + 1;
    historyRequestId.current = requestId;
    setHistoryLoading(true);
    setHistoryError(null);

    getConversations()
      .then((rows) => {
        if (historyRequestId.current !== requestId) return;
        const remote = rows.map((row, index) => conversationFromSummary(row, index));
        const local = conversationsRef.current.filter(
          (c) => !tokenChanged && !c.dbConversationId && (c.messages.length > 0 || c.busy)
        );
        const next = [...local, ...remote];
        const fallback = next.length ? next : [makeConversation()];
        const sortedFallback = [...fallback].sort(sortConversations);
        const nextActiveId =
          sortedFallback.find((c) => c.id === activeIdRef.current)?.id ??
          sortedFallback[0]?.id ??
          null;
        setConversations(fallback);
        if (nextActiveId) setActiveId(nextActiveId);
      })
      .catch((error) => {
        if (historyRequestId.current !== requestId) return;
        setHistoryError(friendlyError(error, lang));
      })
      .finally(() => {
        if (historyRequestId.current === requestId) setHistoryLoading(false);
      });
  }, [authLoading, isAuthenticated, lang, token]);

  // If the active conversation disappears (deleted), fall back to the most-recent remaining one.
  useEffect(() => {
    if (conversations.some((c) => c.id === activeId)) return;
    const top = [...conversations].sort(sortConversations)[0];
    if (top) setActiveId(top.id);
  }, [conversations, activeId]);

  const active = useMemo(
    () => conversations.find((c) => c.id === activeId) ?? conversations[0],
    [conversations, activeId]
  );
  const messages = active?.messages ?? [];
  const busy = active?.busy ?? false;
  const conversationId = active?.threadId ?? "";
  const dbConversationId = active?.dbConversationId ?? undefined;
  const messagesLoading = active?.messagesLoading ?? false;
  const messagesError = active?.messagesError ?? null;

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

  // --- conversation/message mutators (always target a conversation by id) ----
  const patchConversation = useCallback((id: string, patch: Partial<Conversation>) => {
    setConversations((prev) => prev.map((c) => (c.id === id ? { ...c, ...patch } : c)));
  }, []);

  const patchConvMessage = useCallback(
    (convId: string, msgId: string, patch: Partial<ChatMessage>) => {
      setConversations((prev) =>
        prev.map((c) =>
          c.id === convId
            ? { ...c, messages: c.messages.map((m) => (m.id === msgId ? { ...m, ...patch } : m)) }
            : c
        )
      );
    },
    []
  );

  const appendMessage = useCallback((convId: string, msg: ChatMessage) => {
    setConversations((prev) =>
      prev.map((c) => (c.id === convId ? { ...c, messages: [...c.messages, msg] } : c))
    );
  }, []);

  const loadConversationMessages = useCallback(
    async (id: string) => {
      const conv = conversations.find((c) => c.id === id);
      if (
        !conv?.dbConversationId ||
        conv.messagesLoaded ||
        conv.messagesLoading ||
        conv.messagesError ||
        conv.busy
      ) {
        return;
      }

      patchConversation(id, { messagesLoading: true, messagesError: null });
      try {
        const rows = await getConversationMessages(conv.dbConversationId);
        const loadedMessages = rows
          .map(chatMessageFromBackend)
          .filter((message): message is ChatMessage => message !== null);
        setConversations((prev) =>
          prev.map((c) =>
            c.id === id
              ? {
                  ...c,
                  messages: loadedMessages,
                  messagesLoaded: true,
                  messagesLoading: false,
                  messagesError: null,
                }
              : c
          )
        );
      } catch (error) {
        patchConversation(id, {
          messagesLoading: false,
          messagesError: friendlyError(error, lang),
        });
      }
    },
    [conversations, lang, patchConversation]
  );

  useEffect(() => {
    void loadConversationMessages(activeId);
  }, [activeId, loadConversationMessages]);

  // Marks a finished answer: bumps the unread badge if nothing is on screen to read it.
  const settle = useCallback(
    (convId: string, msgId: string, patch: Partial<ChatMessage>) => {
      patchConvMessage(convId, msgId, patch);
      if (!patch.error && !patch.cancelled && viewers.current === 0) {
        setUnread((u) => u + 1);
      }
    },
    [patchConvMessage]
  );

  // Run a question against a SPECIFIC conversation (by UI id + backend thread id). All updates
  // are routed to that conversation, regardless of which one is active when the reply lands.
  const ask = useCallback(
    async (
      convId: string,
      threadId: string,
      dbConversationId: string | null,
      text: string,
      titleHint: string | null,
      titleManual: boolean
    ) => {
      const controller = new AbortController();
      abortMap.current.set(convId, controller);
      patchConversation(convId, { busy: true });

      const assistantId = nextId();
      appendMessage(convId, {
        id: assistantId,
        role: "assistant",
        text: "",
        streaming: true,
        personalized: true,
      });
      // True once the stream has produced ANY event (status or delta) — i.e. the /chat/stream
      // endpoint opened successfully. We only fall back to the non-streaming /chat (a full,
      // expensive agent re-run) when the stream never opened at all; a failure AFTER it opened
      // is shown as an error, not retried.
      let received = false;

      // Phase 14A: send ONLY the student's actual question. Personalization is now owned by the
      // backend — the chat route builds the student's context server-side from authenticated data
      // and attaches it to the agent input. The frontend no longer prepends any hidden profile/
      // schedule/deadline/tuition block, so the persisted user message is the real question.
      const request = {
        message: text,
        conversation_id: threadId,
        db_conversation_id: dbConversationId,
      };
      const adoptDbConversation = (resp: ChatResponse) => {
        const nextDbConversationId = resp.db_conversation_id ?? dbConversationId;
        if (!nextDbConversationId) return;

        patchConversation(convId, {
          dbConversationId: nextDbConversationId,
          messagesLoaded: true,
          lastActivity: Date.now(),
        });

        if (!dbConversationId && titleHint) {
          void updateConversation(nextDbConversationId, {
            title: titleHint,
            title_manual: titleManual,
          })
            .then((updated) => {
              patchConversation(convId, {
                title: updated.title || titleHint,
                titleManual: Boolean(updated.title_manual),
                lastActivity: activityFromIso(
                  updated.last_message_at ?? updated.updated_at
                ),
              });
            })
            .catch(() => {
              /* The chat is already persisted; title sync can be retried by manual rename. */
            });
        }
      };

      try {
        const resp = await postChatStream(
          request,
          {
            signal: controller.signal,
            onDelta: (chunk) => {
              received = true;
              setConversations((prev) =>
                prev.map((c) =>
                  c.id === convId
                    ? {
                        ...c,
                        messages: c.messages.map((m) =>
                          m.id === assistantId ? { ...m, text: m.text + chunk } : m
                        ),
                      }
                    : c
                )
              );
            },
            // Fires on the stream's opening `status` event (and any later real step). Marks the
            // stream as opened, and shows the step text when present (else the localized
            // "Searching…" placeholder).
            onStatus: (step) => {
              received = true;
              patchConvMessage(convId, assistantId, { statusStep: step });
            },
          }
        );
        adoptDbConversation(resp);
        settle(convId, assistantId, { text: resp.answer, response: resp, streaming: false });
      } catch (err) {
        if (err instanceof DOMException && err.name === "AbortError") {
          patchConvMessage(convId, assistantId, { text: "", cancelled: true, streaming: false });
        } else if (!received) {
          try {
            const resp = await postChat(request, controller.signal);
            adoptDbConversation(resp);
            settle(convId, assistantId, { text: resp.answer, response: resp, streaming: false });
          } catch (err2) {
            if (err2 instanceof DOMException && err2.name === "AbortError") {
              patchConvMessage(convId, assistantId, {
                text: "",
                cancelled: true,
                streaming: false,
              });
            } else {
              patchConvMessage(convId, assistantId, {
                text: "",
                error: friendlyError(err2, lang),
                streaming: false,
              });
            }
          }
        } else {
          patchConvMessage(convId, assistantId, {
            text: "",
            error: friendlyError(err, lang),
            streaming: false,
          });
        }
      } finally {
        abortMap.current.delete(convId);
        patchConversation(convId, { busy: false });
      }
    },
    [patchConversation, appendMessage, patchConvMessage, settle, lang]
  );

  // Send a message to the ACTIVE conversation: append the user turn, auto-title it from the
  // first message (unless manually renamed), bump it to the top, then kick off the request.
  const send = useCallback(
    (text: string) => {
      const conv = conversations.find((c) => c.id === activeId);
      if (!conv || conv.busy) return; // one in-flight reply per conversation
      const userId = nextId();
      setConversations((prev) =>
        prev.map((c) => {
          if (c.id !== conv.id) return c;
          const nextTitle = c.titleManual ? c.title : c.title ?? titleFromText(text);
          return {
            ...c,
            title: nextTitle,
            messages: [...c.messages, { id: userId, role: "user", text }],
            lastActivity: Date.now(),
            localOrder: nextLocalOrder(),
          };
        })
      );
      const titleHint = conv.titleManual ? conv.title : conv.title ?? titleFromText(text);
      void ask(
        conv.id,
        conv.threadId,
        conv.dbConversationId,
        text,
        titleHint,
        conv.titleManual
      );
    },
    [conversations, activeId, ask]
  );

  // Stop the ACTIVE conversation's in-flight reply.
  const stop = useCallback(() => {
    abortMap.current.get(activeId)?.abort();
  }, [activeId]);

  const retry = useCallback(
    (errorId: string) => {
      const conv = conversations.find((c) => c.id === activeId);
      if (!conv || conv.busy) return;
      const idx = conv.messages.findIndex((m) => m.id === errorId);
      if (idx < 0) return;
      let userText = "";
      for (let i = idx - 1; i >= 0; i--) {
        if (conv.messages[i].role === "user") {
          userText = conv.messages[i].text;
          break;
        }
      }
      setConversations((prev) =>
        prev.map((c) =>
          c.id === conv.id ? { ...c, messages: c.messages.filter((m) => m.id !== errorId) } : c
        )
      );
      if (userText) {
        void ask(
          conv.id,
          conv.threadId,
          conv.dbConversationId,
          userText,
          conv.title,
          conv.titleManual
        );
      }
    },
    [conversations, activeId, ask]
  );

  const editLast = useCallback(
    (text: string) => {
      const conv = conversations.find((c) => c.id === activeId);
      if (!conv || conv.busy) return;
      let lastUserMsgId: string | null = null;
      for (let i = conv.messages.length - 1; i >= 0; i--) {
        if (conv.messages[i].role === "user") {
          lastUserMsgId = conv.messages[i].id;
          break;
        }
      }
      if (!lastUserMsgId) return;
      setConversations((prev) =>
        prev.map((c) => {
          if (c.id !== conv.id) return c;
          const idx = c.messages.findIndex((m) => m.id === lastUserMsgId);
          if (idx < 0) return c;
          const kept = c.messages.slice(0, idx);
          return {
            ...c,
            messages: [...kept, { id: nextId(), role: "user", text }],
            lastActivity: Date.now(),
            localOrder: nextLocalOrder(),
          };
        })
      );
      void ask(
        conv.id,
        conv.threadId,
        conv.dbConversationId,
        text,
        conv.title ?? titleFromText(text),
        conv.titleManual
      );
    },
    [conversations, activeId, ask]
  );

  const questionFor = useCallback(
    (assistantId: string): string => {
      for (const c of conversations) {
        const idx = c.messages.findIndex((m) => m.id === assistantId);
        if (idx < 0) continue;
        for (let i = idx - 1; i >= 0; i--) {
          if (c.messages[i].role === "user") return c.messages[i].text;
        }
        return "";
      }
      return "";
    },
    [conversations]
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
    async (question: string, response: ChatResponse) => {
      const draftId = nextDraftId();
      // Open the drawer immediately with a heuristic draft (feels instant), then let Vinnie refine it.
      setTicketDraft({
        id: draftId,
        subject: question.trim().slice(0, 80) || "Support request",
        body: response.answer,
        department: DEPARTMENTS[0],
        category: "other",
        priority: "medium",
        include_chat_context: false,
        source_conversation_id: dbConversationId,
        origin_question: question,
        context_preview: shortSummary(question, response.answer),
        created_by_ai: false,
      });
      // Ask Vinnie (small/fast model) for a proper summary/description/category. Fields are locked in
      // the drawer while this runs, so overwriting is safe. Only apply if THIS draft is still open
      // (the student may have cancelled). On failure we keep the heuristic draft.
      setDraftSuggesting(true);
      try {
        const s = await suggestTicketDraft({
          origin_question: question,
          answer: response.answer,
        });
        setTicketDraft((cur) =>
          cur && cur.id === draftId
            ? { ...cur, subject: s.subject, body: s.body, category: s.category, created_by_ai: true }
            : cur
        );
      } catch {
        // keep the heuristic draft (created_by_ai stays false)
      } finally {
        setDraftSuggesting(false);
      }
    },
    [dbConversationId]
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
        source_conversation_id: dbConversationId,
        context_preview: "",
        ...seed,
      });
    },
    [dbConversationId]
  );

  const updateDraft = useCallback((patch: Partial<TicketDraft>) => {
    setTicketDraft((cur) => (cur ? { ...cur, ...patch } : cur));
  }, []);

  const cancelDraft = useCallback(() => {
    setTicketDraft(null);
    setDraftBusy(false);
    setDraftSuggesting(false);
  }, []);

  const saveDraft = useCallback(
    async (override?: TicketDraft): Promise<boolean> => {
      const draft = override ?? ticketDraft;
      if (!draft) return false;
      // No network in MVP — the draft already lives in state; this just confirms to the user.
      try {
        await saveTicketDraft(draft);
        setTicketDraft(null);
        setToast(p.review.draftSaved);
        return true;
      } catch {
        setToast(p.review.submitFailed);
        return false;
      }
    },
    [ticketDraft, p]
  );

  const submitDraft = useCallback(
    async (override?: TicketDraft): Promise<boolean> => {
      const draft = override ?? ticketDraft;
      if (!draft || draftBusy) return false;
      setDraftBusy(true);
      try {
        const ticket = await submitTicket(draft);
        setTicketDraft(null);
        setTicketsRevision((r) => r + 1);
        setToast(p.review.submitted(ticket.id));
        return true;
      } catch {
        setToast(p.review.submitFailed);
        return false;
      } finally {
        setDraftBusy(false);
      }
    },
    [ticketDraft, draftBusy, p]
  );

  const seedComposer = useCallback((text: string) => {
    seedNonce.current += 1;
    setComposerSeed({ text, nonce: seedNonce.current });
  }, []);

  // --- Conversation history -------------------------------------------------
  // Start a fresh conversation and make it active. If the active conversation is already an
  // empty new chat, stay there (no point stacking empties).
  const newConversation = useCallback(() => {
    const cur = conversations.find((c) => c.id === activeId);
    if (cur && !cur.dbConversationId && cur.messages.length === 0) return;
    const conv = makeConversation();
    setConversations((prev) => [...prev, conv]);
    setActiveId(conv.id);
    closeSources();
  }, [conversations, activeId, closeSources]);

  // Open a brand-new conversation and send the first message into it in one step. Builds the
  // conversation object up-front (with the user turn already in it) so `ask` targets it directly
  // and never races the async activeId update.
  const newConversationWithMessage = useCallback(
    (text: string) => {
      const title = titleFromText(text);
      const conv = makeConversation({
        title,
        messages: [{ id: nextId(), role: "user", text }],
        lastActivity: Date.now(),
        localOrder: nextLocalOrder(),
      });
      setConversations((prev) => [...prev, conv]);
      setActiveId(conv.id);
      closeSources();
      void ask(conv.id, conv.threadId, conv.dbConversationId, text, title, false);
    },
    [ask, closeSources]
  );

  // Switch the active conversation. Allowed even while another conversation streams — the
  // in-flight reply keeps running in the background and lands in its own conversation.
  const switchConversation = useCallback(
    (id: string) => {
      if (id === activeId) return;
      patchConversation(id, { messagesError: null });
      setActiveId(id);
      closeSources();
    },
    [activeId, closeSources, patchConversation]
  );

  // Rename. A non-empty title is treated as a manual name (never auto-overwritten); clearing
  // it reverts to auto-titling from the first user message.
  const renameConversation = useCallback(
    (id: string, title: string) => {
      const conv = conversations.find((c) => c.id === id);
      if (!conv) return;
      const trimmed = title.trim();
      const firstUser = conv.messages.find((m) => m.role === "user");
      const nextTitle = trimmed || (firstUser ? titleFromText(firstUser.text) : null);
      const titleManual = Boolean(trimmed);

      setConversations((prev) =>
        prev.map((c) =>
          c.id === id ? { ...c, title: nextTitle, titleManual } : c
        )
      );

      if (conv.dbConversationId && nextTitle) {
        void updateConversation(conv.dbConversationId, {
          title: nextTitle,
          title_manual: titleManual,
        })
          .then((updated) => {
            patchConversation(id, {
              title: updated.title || nextTitle,
              titleManual: Boolean(updated.title_manual),
              lastActivity: activityFromIso(updated.last_message_at ?? updated.updated_at),
            });
          })
          .catch((error) => setToast(friendlyError(error, lang)));
      }
    },
    [conversations, lang, patchConversation]
  );

  // Delete a conversation (aborting its in-flight reply if any). Never leaves the list empty —
  // an empty list is replaced with a fresh conversation; the active-id effect re-points.
  const deleteConversation = useCallback(
    (id: string) => {
      const conv = conversations.find((c) => c.id === id);
      abortMap.current.get(id)?.abort();
      abortMap.current.delete(id);
      setConversations((prev) => {
        const remaining = prev.filter((c) => c.id !== id);
        return remaining.length ? remaining : [makeConversation()];
      });
      setSourceMessageId(null);
      setSourceFocus(null);

      if (conv?.dbConversationId) {
        void deleteBackendConversation(conv.dbConversationId).catch((error) =>
          setToast(friendlyError(error, lang))
        );
      }
    },
    [conversations, lang]
  );

  const conversationsView = useMemo<ConversationSummary[]>(
    () =>
      [...conversations]
        .filter((c) => c.dbConversationId || c.messages.length > 0 || c.busy)
        .sort(sortConversations)
        .map((c) => ({
          id: c.id,
          title: c.title,
          active: c.id === activeId,
          empty: c.messages.length === 0,
          busy: c.busy,
          persisted: Boolean(c.dbConversationId),
        })),
    [conversations, activeId]
  );

  const registerViewer = useCallback(() => {
    viewers.current += 1;
    setUnread(0);
    return () => {
      viewers.current = Math.max(0, viewers.current - 1);
    };
  }, []);

  const sourceMessage = useMemo(() => {
    if (!sourceMessageId) return null;
    for (const c of conversations) {
      const m = c.messages.find((mm) => mm.id === sourceMessageId);
      if (m) return m;
    }
    return null;
  }, [conversations, sourceMessageId]);

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
    conversations: conversationsView,
    activeConversationId: activeId,
    historyLoading,
    historyError,
    messagesLoading,
    messagesError,
    newConversation,
    newConversationWithMessage,
    switchConversation,
    renameConversation,
    deleteConversation,
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
    draftSuggesting,
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
