// Maps raw backend / network failures to calm, student-facing copy (bilingual). Self-contained
// so it needs no i18n keys. Covers the documented cases: overload (503), validation (422),
// network drop, and a mid-stream cutoff ("Stream ended without a final response.").

import type { Lang } from "./i18n";

export function friendlyError(raw: unknown, lang: Lang): string {
  const msg = raw instanceof Error ? raw.message : typeof raw === "string" ? raw : "";
  const m = msg.toLowerCase();
  const vi = lang === "vi";

  // Overloaded / temporarily unavailable.
  if (m.includes("503") || m.includes("busy") || m.includes("overload") || m.includes("unavailable")) {
    return vi
      ? "Vinnie đang bận. Vui lòng thử lại sau giây lát."
      : "Vinnie is busy right now. Please try again in a moment.";
  }
  // Bad request / validation.
  if (m.includes("422") || m.includes("validation")) {
    return vi
      ? "Chưa xử lý được câu hỏi này. Thử diễn đạt lại nhé."
      : "That question couldn't be processed. Try rephrasing it.";
  }
  // Network unreachable or the stream dropped mid-flight.
  if (
    m.includes("reach the chat service") ||
    m.includes("failed to fetch") ||
    m.includes("network") ||
    m.includes("stream ended") ||
    m.includes("stream error")
  ) {
    return vi
      ? "Kết nối bị gián đoạn. Kiểm tra mạng và thử lại."
      : "Connection interrupted. Check your network and try again.";
  }
  // Fallback.
  return vi ? "Đã có lỗi xảy ra. Thử lại nhé." : "Something went wrong. Please try again.";
}
