"use client";

import type { ChatMessage } from "@/lib/types";
import { useChat } from "@/lib/chat";
import { AnswerActions } from "@/components/portal/AnswerActions";
import { FollowUpSuggestions } from "@/components/chat/FollowUpSuggestions";

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
  return (
    <>
      <AnswerActions
        response={message.response}
        onPrepareTicket={() => chat.prepareDraftFromAnswer(question, message.response!)}
        onAskFollowUp={() => chat.seedComposer("")}
      />
      <FollowUpSuggestions
        question={question}
        response={message.response}
        onPick={(q) => chat.send(q)}
      />
    </>
  );
}
