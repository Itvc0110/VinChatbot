"use client";

import type { ChatMessage } from "@/lib/types";
import { useChat } from "@/lib/chat";
import { AnswerActions } from "@/components/portal/AnswerActions";

// The per-answer action row (Add to calendar / Set reminder / Forward), wired to the
// shared chat state so it behaves identically on the full page and in the floating widget.
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
    <AnswerActions
      question={question}
      response={message.response}
      onForward={() => void chat.forward(question, message.response!)}
      onToast={chat.setToast}
    />
  );
}
