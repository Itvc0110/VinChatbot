"use client";

import type { ChatMessage } from "@/lib/types";
import { useChat } from "@/lib/chat";
import { AnswerActions } from "@/components/portal/AnswerActions";
import { FollowUpSuggestions } from "@/components/chat/FollowUpSuggestions";

// Heuristic (EN + VI): does this answer talk about a date / deadline / event / schedule?
// Gates the contextual "Add to calendar" / "Set reminder" actions so they don't appear on
// plain or couldn't-answer replies. Matches numeric dates, times, weekdays, and keywords.
const DATE_CONTEXT_RE =
  /\b\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?\b|\b\d{1,2}:\d{2}\b|\b(mon|tue|wed|thu|fri|sat|sun)(day)?\b|\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*\b|\b(deadline|due|exam|schedule|class|event|reminder|appointment|register|registration)\b|hạn|hạn chót|lịch|lịch học|kỳ thi|thi\b|sự kiện|nhắc|đăng ký|thứ\s?[2-7]|chủ nhật|tiết học/i;

function hasDateContext(text: string): boolean {
  return DATE_CONTEXT_RE.test(text);
}

// The per-answer action row, wired to the shared chat state so it behaves identically on the
// full page and in the floating widget. "Prepare support ticket" opens the Review drawer via
// the shared draft state — nothing is ever sent to admin without the student confirming.
export function ConnectedAnswerActions({ message }: { message: ChatMessage }) {
  const chat = useChat();

  if (
    message.role !== "assistant" ||
    !message.response ||
    message.streaming ||
    message.error ||
    message.cancelled
  ) {
    return null;
  }

  const question = chat.questionFor(message.id);
  const hasCitations = message.response.citations.length > 0;
  return (
    <>
      <AnswerActions
        question={question}
        response={message.response}
        hasDateContext={hasDateContext(`${message.response.answer} ${question}`)}
        onPrepareTicket={() => chat.prepareDraftFromAnswer(question, message.response!)}
        onAskFollowUp={() => chat.seedComposer("")}
        onOpenPolicy={hasCitations ? () => chat.openSources(message.id, 0) : undefined}
        onToast={chat.setToast}
      />
      <FollowUpSuggestions
        question={question}
        response={message.response}
        onPick={(q) => chat.send(q)}
      />
    </>
  );
}
