// Mirrors vinchatbot/app/schemas/chat.py — keep in sync with the backend contract.

export interface Citation {
  source_url: string;
  title: string;
  section?: string | null;
  page_number?: number | null;
  excerpt: string;
  score?: number | null;
}

export interface ToolTraceEntry {
  type: string;
  action?: string;
  reason?: string;
  [key: string]: unknown;
}

export interface ChatRequest {
  message: string;
  conversation_id: string;
  db_conversation_id?: string | null;
  filters?: null;
}

export interface ChatResponse {
  answer: string;
  citations: Citation[];
  confidence: number;
  tool_trace: ToolTraceEntry[];
  needs_human_review: boolean;
  db_conversation_id?: string | null;
}

// Mirrors vinchatbot/app/schemas/document.py SourceSummary — returned by GET /sources.
export interface SourceSummary {
  source_url: string;
  document_title: string;
  document_type: string;
  content_hash: string;
  crawled_at: string;
  chunk_count: number;
}

// UI-side message model.
export type Role = "user" | "assistant";

export interface ChatMessage {
  id: string;
  role: Role;
  text: string;
  // assistant-only: the full backend response, used to drive the sources panel.
  response?: ChatResponse;
  // assistant-only: set when the /chat call failed (503 / network).
  error?: string;
  // assistant-only: the user stopped the request mid-flight (neutral, not an error).
  cancelled?: boolean;
  // assistant-only: answer is currently being revealed token-by-token (verify-then-reveal).
  streaming?: boolean;
  // assistant-only: a human-readable pre-reveal status step (e.g. "Generating verified
  // answer…"). Only set if the backend emits `event: status`; today it stays undefined and
  // the UI shows one honest "Searching official VinUni sources…" placeholder.
  statusStep?: string;
  // assistant-only: answer was produced in "My Student Info" mode (personalized with the
  // student's profile/schedule/deadlines/tuition context).
  personalized?: boolean;
}
