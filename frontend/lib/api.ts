import type { ChatRequest, ChatResponse } from "./types";

// Single point the UI uses to reach the backend. Calls the Next proxy (/api/chat),
// which rewrites to FastAPI POST /chat. No provider SDK is ever imported here.
// An optional AbortSignal lets the caller cancel an in-flight request (Stop button).
export async function postChat(
  req: ChatRequest,
  signal?: AbortSignal
): Promise<ChatResponse> {
  let res: Response;
  try {
    res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(req),
      signal,
    });
  } catch (err) {
    // Re-throw aborts unchanged so the caller can distinguish cancel from failure.
    if (err instanceof DOMException && err.name === "AbortError") throw err;
    // Network / backend unreachable.
    throw new Error(
      "Can't reach the chat service. Is the backend running on :8000?"
    );
  }

  if (!res.ok) {
    // FastAPI returns 503 { detail } when the agent or an upstream service fails,
    // and 422 { detail } on validation errors.
    let detail = `Request failed (${res.status}).`;
    try {
      const body = await res.json();
      if (typeof body?.detail === "string") detail = body.detail;
    } catch {
      /* keep generic detail */
    }
    throw new Error(detail);
  }

  return (await res.json()) as ChatResponse;
}
