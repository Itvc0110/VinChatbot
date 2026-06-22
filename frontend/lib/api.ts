import type { ChatRequest, ChatResponse, SourceSummary } from "./types";
import type {
  AdminStats,
  AnalyticsOverview,
  CalendarEvent,
  ClassSession,
  Deadline,
  KnowledgeSource,
  Notification,
  ResolveQuestionPayload,
  ScheduleDay,
  SourceCategory,
  StudentProfile,
  SupportTicket,
  TicketCategory,
  TuitionStatus,
  UnansweredQuestion,
} from "./portalTypes";
import {
  MOCK_ADMIN_STATS,
  MOCK_ANALYTICS,
  MOCK_DEADLINES,
  MOCK_EVENTS,
  MOCK_NOTIFICATIONS,
  MOCK_PROFILE,
  MOCK_REMINDERS,
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
  category?: TicketCategory;
  origin_question?: string;
}): Promise<SupportTicket> {
  const now = new Date().toISOString();
  const ticket: SupportTicket = {
    id: `TKT-${Math.floor(1000 + Math.random() * 9000)}`,
    subject: input.subject,
    body: input.body,
    department: input.department ?? "Student Services",
    category: input.category ?? "other",
    status: "open",
    priority: "medium",
    created_at: now,
    updated_at: now,
    origin_question: input.origin_question,
    messages: [{ id: "m1", author: "student", body: input.body, created_at: now }],
  };
  // Prepend so the new ticket shows at the top of the list on the next fetch.
  MOCK_TICKETS.unshift(ticket);
  return delay(ticket, 400);
}

// [MOCK] TODO backend contract: GET /tickets/{id} -> SupportTicket
export async function getSupportTicketDetail(ticketId: string): Promise<SupportTicket> {
  const found = MOCK_TICKETS.find((t) => t.id === ticketId);
  if (!found) throw new Error(`Ticket ${ticketId} not found`);
  return delay({ ...found });
}

// Ticket visibility mutations. The backend has no permanent-delete endpoint, so archive
// and delete are modelled as frontend state on the ticket (filtered by the visibility
// control). These mutate the in-memory demo store so the change persists across reloads.
// [MOCK] TODO backend contract: PATCH /tickets/{id} { archived } -> SupportTicket
function patchTicket(ticketId: string, patch: Partial<SupportTicket>): SupportTicket {
  const t = MOCK_TICKETS.find((x) => x.id === ticketId);
  if (!t) throw new Error(`Ticket ${ticketId} not found`);
  Object.assign(t, patch, { updated_at: new Date().toISOString() });
  return { ...t };
}

export async function archiveSupportTicket(ticketId: string): Promise<SupportTicket> {
  return delay(patchTicket(ticketId, { archived: true }), 250);
}

export async function restoreSupportTicket(ticketId: string): Promise<SupportTicket> {
  return delay(patchTicket(ticketId, { archived: false, deleted: false }), 250);
}

// [MOCK] TODO backend contract: DELETE /tickets/{id} -> { ok: true }
// No permanent delete exists; modelled as a "deleted" visibility state instead.
export async function deleteSupportTicket(ticketId: string): Promise<SupportTicket> {
  return delay(patchTicket(ticketId, { deleted: true }), 250);
}

// ---- Notifications ----------------------------------------------------------
// [MOCK] TODO backend contract: GET /students/me/notifications -> Notification[]
export async function getStudentNotifications(): Promise<Notification[]> {
  return delay(MOCK_NOTIFICATIONS.map((n) => ({ ...n })));
}

function patchNotification(id: string, patch: Partial<Notification>): Notification {
  const n = MOCK_NOTIFICATIONS.find((x) => x.id === id);
  if (!n) throw new Error(`Notification ${id} not found`);
  Object.assign(n, patch);
  return { ...n };
}

// [MOCK] TODO backend contract: PATCH /notifications/{id} { read } -> Notification
export async function markNotificationRead(id: string, read = true): Promise<Notification> {
  return delay(patchNotification(id, { read }), 150);
}

// [MOCK] TODO backend contract: PATCH /notifications/{id} { important } -> Notification
export async function markNotificationImportant(
  id: string,
  important: boolean
): Promise<Notification> {
  return delay(patchNotification(id, { important }), 150);
}

// [MOCK] TODO backend contract: PATCH /notifications/{id} { archived: true } -> Notification
export async function archiveNotification(id: string): Promise<Notification> {
  return delay(patchNotification(id, { archived: true }), 150);
}

// [MOCK] TODO backend contract: DELETE /notifications/{id} -> { ok: true }
export async function deleteNotification(id: string): Promise<{ ok: true }> {
  const idx = MOCK_NOTIFICATIONS.findIndex((x) => x.id === id);
  if (idx >= 0) MOCK_NOTIFICATIONS.splice(idx, 1);
  return delay({ ok: true } as const, 150);
}

// ---- Calendar ---------------------------------------------------------------
// [MOCK] TODO backend contract: GET /students/me/calendar?from=&to= -> CalendarEvent[]
// Merges recurring classes (MOCK_SCHEDULE, expanded to dates in [from, to]) with one-off
// deadlines/exams (MOCK_DEADLINES), campus events (MOCK_EVENTS) and personal reminders
// (MOCK_REMINDERS) into a single dated feed the calendar grid renders.
const DAY_INDEX: Record<ScheduleDay, number> = {
  Mon: 1,
  Tue: 2,
  Wed: 3,
  Thu: 4,
  Fri: 5,
  Sat: 6,
  Sun: 0,
};

function expandClass(s: ClassSession, from: Date, to: Date): CalendarEvent[] {
  const out: CalendarEvent[] = [];
  const target = DAY_INDEX[s.day];
  const d = new Date(from);
  d.setHours(0, 0, 0, 0);
  for (; d <= to; d.setDate(d.getDate() + 1)) {
    if (d.getDay() !== target) continue;
    const [sh, sm] = s.start.split(":").map(Number);
    const [eh, em] = s.end.split(":").map(Number);
    const start = new Date(d);
    start.setHours(sh, sm, 0, 0);
    const end = new Date(d);
    end.setHours(eh, em, 0, 0);
    out.push({
      id: `${s.id}-${start.toISOString().slice(0, 10)}`,
      type: "class",
      title: s.course_title,
      start: start.toISOString(),
      end: end.toISOString(),
      location: `${s.room}, ${s.building}`,
      course: s.course_code,
      category: "Class",
      description: `Instructor: ${s.instructor}`,
    });
  }
  return out;
}

export async function getStudentCalendar(
  from?: string,
  to?: string
): Promise<CalendarEvent[]> {
  // Default window: 6 weeks back to 10 weeks ahead, enough for any month/week view.
  const start = from ? new Date(from) : new Date(Date.now() - 42 * 86_400_000);
  const end = to ? new Date(to) : new Date(Date.now() + 70 * 86_400_000);

  const classes = MOCK_SCHEDULE.flatMap((s) => expandClass(s, start, end));
  const deadlines: CalendarEvent[] = MOCK_DEADLINES.map((d) => ({
    id: d.id,
    type: d.kind === "exam" ? "exam" : "deadline",
    title: d.title,
    start: d.due_at,
    course: d.course_code,
    category: d.kind === "exam" ? "Exam" : "Deadline",
    source_title: d.source_title,
    source_url: d.source_url,
  }));
  const events = MOCK_EVENTS.map((e) => ({ ...e }));
  const reminders = MOCK_REMINDERS.map((e) => ({ ...e }));

  return delay([...classes, ...deadlines, ...events, ...reminders]);
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
