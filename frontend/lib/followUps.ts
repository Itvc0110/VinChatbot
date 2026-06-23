// Rule-based, bilingual follow-up suggestions shown under a settled answer. Pure and
// frontend-only (mirrors the style of suggestedQuestions.ts). Phase-2-swappable for a backend
// `event: suggestions` without touching callers — see postChatStream's onSuggestions hook.

import type { ChatResponse } from "./types";
import type { Lang } from "./i18n";

// Compact date/deadline/schedule detector (EN + VI) — same intent as the one gating the
// calendar actions in ConnectedAnswerActions.
const DATE_CONTEXT_RE =
  /\b\d{1,2}[/-]\d{1,2}\b|\b\d{1,2}:\d{2}\b|\b(deadline|due|exam|schedule|class|event|register|registration)\b|hạn|lịch|kỳ thi|sự kiện|đăng ký/i;

export function followUpsFor(question: string, response: ChatResponse, lang: Lang): string[] {
  const vi = lang === "vi";
  const text = `${response.answer} ${question}`;
  const out: string[] = [];

  if (DATE_CONTEXT_RE.test(text)) {
    out.push(vi ? "Hạn chót chính xác là khi nào?" : "What's the exact deadline?");
    out.push(vi ? "Tôi cần làm gì để hoàn tất?" : "What do I need to do to complete this?");
  }
  if (response.citations.length > 0) {
    out.push(
      vi ? "Tôi đọc chính sách chính thức ở đâu?" : "Where can I read the official policy?"
    );
  }
  // Generic deepeners, always available as a fallback.
  out.push(vi ? "Tôi nên liên hệ phòng ban nào?" : "Which office should I contact?");
  out.push(vi ? "Có ngoại lệ nào không?" : "Are there any exceptions?");

  return Array.from(new Set(out)).slice(0, 3);
}
