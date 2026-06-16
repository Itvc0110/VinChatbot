import type { ChatResponse, ToolTraceEntry } from "./types";

// The backend encodes the *kind* of reply in tool_trace + citations + needs_human_review,
// not in the HTTP status. The sources panel must distinguish these so it never renders a
// fake citation. See vinchatbot/app/agents/guardrails.py.
export type ResponseState =
  | "grounded" // real citations from the corpus
  | "conversational" // greeting / smalltalk / capability — no sources needed
  | "refusal" // out-of-scope / injection / restricted / abuse — route to office
  | "degraded"; // could not ground an answer (needs_human_review)

const REFUSAL_ACTIONS = new Set([
  "out_of_scope",
  "prompt_injection",
  "restricted_data",
  "abusive_language",
]);

const CONVERSATIONAL_ACTIONS = new Set(["greeting", "smalltalk", "capability"]);

function guardrailAction(trace: ToolTraceEntry[]): string | undefined {
  const entry = trace.find((t) => t.type === "guardrail" && t.action);
  return entry?.action;
}

export function deriveState(resp: ChatResponse): ResponseState {
  const action = guardrailAction(resp.tool_trace ?? []);

  if (action && REFUSAL_ACTIONS.has(action)) return "refusal";
  if (action && CONVERSATIONAL_ACTIONS.has(action)) return "conversational";

  // Genuine couldn't-ground: the backend's graceful-degradation path returns a canned
  // "I don't know" answer (confidence 0). This — NOT needs_human_review — is the signal
  // for the degraded state. A real, cited answer can ALSO carry needs_human_review (it's
  // just a faithfulness review flag), and must still count as grounded.
  if (action === "graceful_degradation") return "degraded";

  if (resp.citations && resp.citations.length > 0) return "grounded";

  // An answer with no citations and no guardrail flag has nothing to ground on.
  return "degraded";
}

// A grounded answer the backend still flagged for human review (e.g. faithfulness
// uncertain). Surfaced as a subtle, separate marker — it does NOT make the answer
// "ungrounded", so it never turns the state red.
export function isReviewFlagged(resp: ChatResponse): boolean {
  return resp.needs_human_review === true && deriveState(resp) === "grounded";
}

// Confidence traffic-light band. Thresholds: green >0.8, yellow 0.5–0.8, red <0.5.
export type ConfidenceBand = "high" | "medium" | "low";

export function confidenceBand(confidence: number): ConfidenceBand {
  if (confidence > 0.8) return "high";
  if (confidence >= 0.5) return "medium";
  return "low";
}

// Confidence is only a meaningful signal for a grounded answer. Canned guardrail replies
// (refusal / conversational) hard-code 1.0, and the degraded path hard-codes 0.0 — showing
// a pill there is misleading. Gating to "grounded" also guarantees the red "No grounded
// answer" badge and a confidence pill can never co-occur.
export function showsConfidence(state: ResponseState): boolean {
  return state === "grounded";
}

// Localizable key for the guardrail refusal reason; mapped to copy in the i18n dict.
export type RefusalReasonKey =
  | "outOfScope"
  | "injection"
  | "restricted"
  | "abuse"
  | "default";

export function refusalReasonKey(resp: ChatResponse): RefusalReasonKey {
  const action = guardrailAction(resp.tool_trace ?? []);
  switch (action) {
    case "out_of_scope":
      return "outOfScope";
    case "prompt_injection":
      return "injection";
    case "restricted_data":
      return "restricted";
    case "abusive_language":
      return "abuse";
    default:
      return "default";
  }
}
