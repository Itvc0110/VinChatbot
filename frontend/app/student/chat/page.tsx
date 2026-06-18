"use client";

import { Suspense, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import type { ChatMessage } from "@/lib/types";
import type {
  ChatMode,
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
import { ChatColumn } from "@/components/ChatColumn";
import { SourcesPanel, type CiteFocus } from "@/components/SourcesPanel";
import { AnswerActions } from "@/components/portal/AnswerActions";
import { Toast } from "@/components/ui/primitives";
import { usePortal } from "@/lib/portalI18n";
import { formatVnd, formatDate } from "@/lib/format";

let counter = 0;
const nextId = () => `m${Date.now()}-${counter++}`;

function buildPersonalContext(
  profile: StudentProfile | null,
  schedule: ClassSession[],
  deadlines: Deadline[],
  tuition: TuitionStatus | null
): string {
  const lines: string[] = ["[Student context — personalize the answer using this]"];
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

function ChatView() {
  const { p } = usePortal();
  const searchParams = useSearchParams();

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [busy, setBusy] = useState(false);
  const [mode, setMode] = useState<ChatMode>("general");
  const [citeFocus, setCiteFocus] = useState<CiteFocus | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const focusNonce = useRef(0);

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

  function patchMessage(id: string, patch: Partial<ChatMessage>) {
    setMessages((prev) => prev.map((m) => (m.id === id ? { ...m, ...patch } : m)));
  }

  async function ask(text: string, personal: boolean) {
    const controller = new AbortController();
    abortRef.current = controller;
    setBusy(true);

    const assistantId = nextId();
    setMessages((prev) => [
      ...prev,
      { id: assistantId, role: "assistant", text: "", streaming: true, personalized: personal },
    ]);
    let streamed = false;

    const sent = personal
      ? `${buildPersonalContext(
          personalData.current.profile,
          personalData.current.schedule,
          personalData.current.deadlines,
          personalData.current.tuition
        )}\n\nQuestion: ${text}`
      : text;

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
      patchMessage(assistantId, { text: resp.answer, response: resp, streaming: false });
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") {
        patchMessage(assistantId, { text: "", cancelled: true, streaming: false });
      } else if (!streamed) {
        try {
          const resp = await postChat(
            { message: sent, conversation_id: conversationId },
            controller.signal
          );
          patchMessage(assistantId, { text: resp.answer, response: resp, streaming: false });
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
  }

  function handleSend(text: string) {
    if (busy) return;
    setMessages((prev) => [...prev, { id: nextId(), role: "user", text }]);
    void ask(text, mode === "personal");
  }
  function handleStop() {
    abortRef.current?.abort();
  }
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
      if (userText) void ask(userText, mode === "personal");
      return prev.filter((m) => m.id !== errorId);
    });
  }
  function handleEditLast(text: string) {
    if (busy || !lastUserId) return;
    setMessages((prev) => {
      const idx = prev.findIndex((m) => m.id === lastUserId);
      if (idx < 0) return prev;
      const kept = prev.slice(0, idx);
      void ask(text, mode === "personal");
      return [...kept, { id: nextId(), role: "user", text }];
    });
  }
  function handleCiteClick(idx: number) {
    focusNonce.current += 1;
    setCiteFocus({ idx, nonce: focusNonce.current });
  }

  const sentInitial = useRef(false);
  useEffect(() => {
    if (sentInitial.current) return;
    const q = searchParams.get("q");
    if (q && q.trim()) {
      sentInitial.current = true;
      handleSend(q.trim());
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams]);

  function questionFor(assistantId: string): string {
    const idx = messages.findIndex((m) => m.id === assistantId);
    for (let i = idx - 1; i >= 0; i--) {
      if (messages[i].role === "user") return messages[i].text;
    }
    return "";
  }

  const renderActions = (m: ChatMessage) => {
    if (m.role !== "assistant" || !m.response || m.streaming || m.error || m.cancelled)
      return null;
    const question = questionFor(m.id);
    return (
      <>
        {m.personalized && (
          <div style={{ marginTop: 8 }}>
            <span className="personal-tag">✦ {p.personalizedAnswer}</span>
          </div>
        )}
        <AnswerActions
          question={question}
          response={m.response}
          onViewSource={() => handleCiteClick(0)}
          onForward={async () => {
            try {
              const ticket = await forwardToAdmin({
                subject: question.slice(0, 80) || "Forwarded question",
                body: m.response!.answer,
                origin_question: question,
              });
              setToast(p.forwardedOk(ticket.id));
            } catch {
              setToast(p.forwardFailed);
            }
          }}
          onToast={setToast}
        />
      </>
    );
  };

  return (
    <div className="chat-shell">
      <div className="chat-modebar">
        <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
          <div className="seg" role="group" aria-label="Answer mode">
            <button
              className={`seg-opt ${mode === "general" ? "active" : ""}`}
              aria-pressed={mode === "general"}
              onClick={() => setMode("general")}
            >
              {p.modeGeneral}
            </button>
            <button
              className={`seg-opt ${mode === "personal" ? "active" : ""}`}
              aria-pressed={mode === "personal"}
              onClick={() => setMode("personal")}
            >
              {p.modePersonal}
            </button>
          </div>
        </div>
        <span className="mode-hint">{p.studentChatNote}</span>
      </div>

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
          renderActions={renderActions}
          composerChips={p.chatSuggested}
        />
        <SourcesPanel latest={latestAssistant} citeFocus={citeFocus} busy={busy} />
      </div>

      {toast && <Toast message={toast} onClose={() => setToast(null)} />}
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
