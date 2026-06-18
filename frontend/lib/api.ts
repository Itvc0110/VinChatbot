import type { ChatRequest, ChatResponse, SourceSummary } from "./types";
import type {
  AdminStats,
  AnalyticsOverview,
  ClassSession,
  Deadline,
  KnowledgeSource,
  ResolveQuestionPayload,
  SourceCategory,
  StudentProfile,
  SupportTicket,
  TuitionStatus,
  UnansweredQuestion,
} from "./portalTypes";
import {
  MOCK_ADMIN_STATS,
  MOCK_ANALYTICS,
  MOCK_DEADLINES,
  MOCK_PROFILE,
  MOCK_SCHEDULE,
  MOCK_SOURCES,
  MOCK_TICKETS,
  MOCK_TUITION,
  MOCK_UNANSWERED,
  delay,
} from "./mock";

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

// Streaming variant. The backend runs every safety gate FIRST, then reveals the verified
// answer token-by-token (verify-then-reveal) — so deltas are never retracted. `onDelta`
// fires with each text chunk as it arrives; the resolved ChatResponse carries the full
// answer + citations + meta. Falls back to nothing here — the caller handles fallback.
export async function postChatStream(
  req: ChatRequest,
  opts: { onDelta: (text: string) => void; signal?: AbortSignal }
): Promise<ChatResponse> {
  const res = await fetch("/api/chat/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
    signal: opts.signal,
  });

  if (!res.ok || !res.body) {
    let detail = `Request failed (${res.status}).`;
    try {
      const body = await res.json();
      if (typeof body?.detail === "string") detail = body.detail;
    } catch {
      /* keep generic detail */
    }
    throw new Error(detail);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let final: ChatResponse | null = null;

  // Parse the SSE framing: events are separated by a blank line; each has an
  // `event:` line and a `data:` line.
  const handleEvent = (raw: string) => {
    let event = "message";
    const dataLines: string[] = [];
    for (const line of raw.split("\n")) {
      if (line.startsWith("event:")) event = line.slice(6).trim();
      else if (line.startsWith("data:")) dataLines.push(line.slice(5).trimStart());
    }
    if (dataLines.length === 0) return;
    const data = JSON.parse(dataLines.join("\n"));
    if (event === "delta") opts.onDelta(data.text as string);
    else if (event === "done") final = data as ChatResponse;
    else if (event === "error") throw new Error(data.detail || "Stream error.");
  };

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let sep: number;
    while ((sep = buffer.indexOf("\n\n")) !== -1) {
      const raw = buffer.slice(0, sep);
      buffer = buffer.slice(sep + 2);
      if (raw.trim()) handleEvent(raw);
    }
  }
  if (buffer.trim()) handleEvent(buffer);

  if (!final) throw new Error("Stream ended without a final response.");
  return final;
}

// =============================================================================
// Portal API layer
// -----------------------------------------------------------------------------
// One named function per data need the portal screens use. Functions that map to a
// REAL FastAPI route are marked [LIVE]; the rest return realistic demo data and are
// marked [MOCK] with the exact backend contract they expect, so swapping them for a
// real fetch() later is mechanical (the return shapes already match portalTypes.ts).
//
// The browser talks to the Next proxy (/api/*), which next.config.js rewrites to
// FastAPI — so no CORS change and no LLM SDK ever reaches the client.
// =============================================================================

async function getJSON<T>(url: string, signal?: AbortSignal): Promise<T> {
  const res = await fetch(url, { signal, headers: { Accept: "application/json" } });
  if (!res.ok) throw new Error(`Request failed (${res.status}) for ${url}`);
  return (await res.json()) as T;
}

// ---- Student profile --------------------------------------------------------
// [MOCK] TODO backend contract: GET /students/me -> StudentProfile
// (auth via session cookie / bearer; the signed-in student is resolved server-side).
export async function getStudentProfile(): Promise<StudentProfile> {
  return delay(MOCK_PROFILE);
}

// [MOCK] TODO backend contract: GET /students/me/schedule -> ClassSession[]
export async function getStudentSchedule(): Promise<ClassSession[]> {
  return delay(MOCK_SCHEDULE);
}

// [MOCK] TODO backend contract: GET /students/me/deadlines -> Deadline[]
export async function getStudentDeadlines(): Promise<Deadline[]> {
  return delay([...MOCK_DEADLINES].sort((a, b) => a.due_at.localeCompare(b.due_at)));
}

// [MOCK] TODO backend contract: GET /students/me/tuition -> TuitionStatus
export async function getTuitionStatus(): Promise<TuitionStatus> {
  return delay(MOCK_TUITION);
}

// ---- Support tickets --------------------------------------------------------
// [MOCK] TODO backend contract: GET /students/me/tickets -> SupportTicket[]
export async function getSupportTickets(): Promise<SupportTicket[]> {
  return delay([...MOCK_TICKETS]);
}

// [MOCK] TODO backend contract: POST /tickets
//   body: { subject, body, department, origin_question? } -> SupportTicket
// Used by the "Forward to admin" action on a chat answer and the New Ticket form.
export async function forwardToAdmin(input: {
  subject: string;
  body: string;
  department?: string;
  origin_question?: string;
}): Promise<SupportTicket> {
  const now = new Date().toISOString();
  const ticket: SupportTicket = {
    id: `TKT-${Math.floor(1000 + Math.random() * 9000)}`,
    subject: input.subject,
    body: input.body,
    department: input.department ?? "Student Services",
    status: "open",
    priority: "normal",
    created_at: now,
    updated_at: now,
    origin_question: input.origin_question,
  };
  return delay(ticket, 400);
}

// ---- Knowledge sources (admin) ---------------------------------------------
// [LIVE] GET /api/sources -> SourceSummary[]  (FastAPI GET /sources)
// Mapped onto the richer KnowledgeSource shape the admin table renders. Falls back
// to demo data if the backend is unreachable so the admin screens stay demoable.
function inferCategory(title: string): SourceCategory {
  const t = title.toLowerCase();
  if (/(tuition|fee|payment|financial)/.test(t)) return "Tuition";
  if (/(event|festival|club)/.test(t)) return "Events";
  if (/(service|health|counsel|housing|library)/.test(t)) return "Student Services";
  if (/(schedule|timetable|calendar)/.test(t)) return "Schedule";
  return "Academic";
}

function mapSummaryToSource(s: SourceSummary, i: number): KnowledgeSource {
  const type = s.document_type?.includes("pdf")
    ? "pdf"
    : s.document_type === "spreadsheet" || s.document_type === "csv"
    ? "database"
    : "url";
  return {
    id: s.content_hash?.slice(0, 12) || `src-${i}`,
    name: s.document_title || s.source_url,
    url: s.source_url,
    type,
    category: inferCategory(s.document_title || s.source_url),
    status: s.chunk_count > 0 ? "indexed" : "pending",
    chunk_count: s.chunk_count,
    last_crawled_at: s.crawled_at,
    last_indexed_at: s.chunk_count > 0 ? s.crawled_at : undefined,
    is_official: /vinuni\.edu\.vn/.test(s.source_url),
  };
}

export async function getKnowledgeSources(): Promise<KnowledgeSource[]> {
  try {
    const summaries = await getJSON<SourceSummary[]>("/api/sources");
    if (!Array.isArray(summaries) || summaries.length === 0) return MOCK_SOURCES;
    return summaries.map(mapSummaryToSource);
  } catch {
    // Backend not running / no corpus yet — keep the admin table demoable.
    return MOCK_SOURCES;
  }
}

// [LIVE-ish] POST /api/ingest/run  (FastAPI POST /ingest/run)
//   body: { urls: string[], force: boolean } -> IngestRunResponse
// URL sources crawl + index through the real pipeline. File uploads (PDF/DOCX) have no
// backend endpoint yet, so they resolve through the mock path below.
export interface IngestRunResponse {
  crawled_documents: number;
  indexed_chunks: number;
  skipped_documents: number;
  sources: string[];
}

export async function uploadKnowledgeSource(input: {
  url?: string;
  file?: File | null;
  category: SourceCategory;
  // Optional metadata captured by the upload form. The live /ingest/run pipeline derives
  // its own title; these are forwarded as the contract for a future /ingest/upload route.
  title?: string;
  source_type?: "pdf" | "docx" | "url";
}): Promise<IngestRunResponse> {
  if (input.url) {
    try {
      const res = await fetch("/api/ingest/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ urls: [input.url], force: true }),
      });
      if (!res.ok) throw new Error(`Ingest failed (${res.status})`);
      return (await res.json()) as IngestRunResponse;
    } catch {
      // Fall through to a simulated result so the upload flow stays demoable offline.
      return delay(
        { crawled_documents: 1, indexed_chunks: 14, skipped_documents: 0, sources: [input.url] },
        900
      );
    }
  }
  // [MOCK] TODO backend contract: POST /ingest/upload (multipart: file, category)
  //   -> IngestRunResponse. No FastAPI route exists for binary uploads yet.
  return delay(
    {
      crawled_documents: 1,
      indexed_chunks: input.file ? Math.max(8, Math.round(input.file.size / 4000)) : 10,
      skipped_documents: 0,
      sources: [input.file?.name ?? "uploaded-document"],
    },
    1100
  );
}

// [LIVE-ish] Re-crawl a source by URL through POST /ingest/run (force=true).
export async function recrawlSource(sourceUrl: string): Promise<IngestRunResponse> {
  try {
    const res = await fetch("/api/ingest/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ urls: [sourceUrl], force: true }),
    });
    if (!res.ok) throw new Error(`Re-crawl failed (${res.status})`);
    return (await res.json()) as IngestRunResponse;
  } catch {
    return delay({ crawled_documents: 1, indexed_chunks: 12, skipped_documents: 0, sources: [sourceUrl] }, 800);
  }
}

// [MOCK] TODO backend contract: POST /sources/{id}/disable -> { ok: true }
export async function disableSource(sourceId: string): Promise<{ ok: true }> {
  return delay({ ok: true } as const, 300);
}

// ---- Unanswered questions (admin) ------------------------------------------
// [MOCK] TODO backend contract: GET /admin/unanswered -> UnansweredQuestion[]
//   (populated from chat turns where deriveState == "degraded"/"refusal").
export async function getUnansweredQuestions(): Promise<UnansweredQuestion[]> {
  return delay([...MOCK_UNANSWERED]);
}

// [MOCK] TODO backend contract: POST /admin/unanswered/{id}/resolve
//   body: ResolveQuestionPayload -> UnansweredQuestion (updated)
export async function resolveUnansweredQuestion(
  questionId: string,
  payload: ResolveQuestionPayload
): Promise<UnansweredQuestion> {
  const found = MOCK_UNANSWERED.find((q) => q.id === questionId) ?? MOCK_UNANSWERED[0];
  const status =
    payload.action === "forward"
      ? "forwarded"
      : payload.action === "mark_resolved" || payload.action === "official_answer"
      ? "resolved"
      : "in_review";
  return delay({ ...found, status }, 500);
}

// ---- Admin dashboard + analytics -------------------------------------------
// [MOCK] TODO backend contract: GET /admin/stats -> AdminStats
export async function getAdminStats(): Promise<AdminStats> {
  return delay(MOCK_ADMIN_STATS);
}

// [MOCK] TODO backend contract: GET /admin/analytics -> AnalyticsOverview
export async function getAnalytics(): Promise<AnalyticsOverview> {
  return delay(MOCK_ANALYTICS);
}
