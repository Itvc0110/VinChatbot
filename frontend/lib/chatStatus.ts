// Derives a single status for an assistant message from the existing boolean flags. We keep
// the flags (least churn, ~10 read sites) and derive this only where the status UI needs it.
//
// Note: there is NO honest `retrieving` vs `pending` distinction today — the backend sends
// nothing until the verified answer is ready (verify-then-reveal), so "pending" covers the
// whole pre-`delta` wait. Don't add a fake `retrieving` step unless the backend emits one.

import type { ChatMessage } from "./types";

export type ChatStatus = "pending" | "streaming" | "done" | "error" | "stopped";

export function statusOf(m: ChatMessage): ChatStatus {
  if (m.error) return "error";
  if (m.cancelled) return "stopped";
  if (m.streaming) return m.text ? "streaming" : "pending";
  return "done";
}
