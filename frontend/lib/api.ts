import type { ChatRequest, ChatResponse, SourceSummary } from "./types";
import type {
  AdminStats,
  AnalyticsOverview,
  CalendarEvent,
  ClassSession,
  Deadline,
  DeadlineKind,
  KnowledgeSource,
  Notification,
  NotificationType,
  ResolveQuestionPayload,
  ScheduleDay,
  SourceCategory,
  StudentProfile,
  SuggestedQuestion,
  SupportTicket,
  TicketDraft,
  TicketStatus,
  TuitionStatus,
  UnansweredQuestion,
} from "./portalTypes";
import { generate as generateQuestions } from "./suggestedQuestions";
import type { Lang } from "./i18n";
import {
  MOCK_ADMIN_STATS,
  MOCK_ANALYTICS,
  MOCK_NOTIFICATIONS,
  MOCK_PROFILE,
  MOCK_SOURCES,
  MOCK_TICKETS,
  MOCK_TUITION,
  MOCK_UNANSWERED,
  delay,
} from "./mock";

export const AUTH_TOKEN_STORAGE_KEY = "vinuni-copilot-access-token";

export type BackendRole = "student" | "institute_admin" | "global_admin" | "staff" | string;

export interface BackendInstitute {
  id: string;
  code: string;
  name_vi: string;
  name_en: string;
}

export interface BackendStudentProfile {
  id: string;
  student_id: string;
  program?: string | null;
  major?: string | null;
  cohort?: number | null;
  academic_year?: number | null;
  student_status: string;
  preferred_language: string;
  advisor_name?: string | null;
  advisor_email?: string | null;
  ai_personalization_enabled: boolean;
}

export interface BackendAcademicSummary {
  gpa?: string | number | null;
  credits_earned: number;
  credits_required: number;
  current_semester?: string | null;
  academic_status: string;
  updated_at?: string | null;
}

export interface BackendStudentMe extends BackendStudentProfile {
  institute: BackendInstitute;
  academic_summary?: BackendAcademicSummary | null;
}

export interface BackendCourse {
  id: string;
  course_code: string;
  course_title: string;
  credits: number;
  semester?: string | null;
  academic_year?: string | null;
  instructor?: string | null;
  institute?: BackendInstitute | null;
}

export interface BackendScheduleItem {
  id: string;
  course_id?: string | null;
  course_code?: string | null;
  course_title?: string | null;
  title: string;
  schedule_type: string;
  start_time: string;
  end_time: string;
  location?: string | null;
  building?: string | null;
  room?: string | null;
  instructor?: string | null;
  recurrence_rule?: string | null;
}

export interface BackendDeadline {
  id: string;
  course_id?: string | null;
  course_code?: string | null;
  course_title?: string | null;
  title: string;
  kind?: string | null;
  due_at: string;
  source_title?: string | null;
  source_url?: string | null;
}

export interface BackendNotification {
  id: string;
  type: string;
  title: string;
  message: string;
  priority: string;
  status: string;
  target_scope: string;
  institute_id?: string | null;
  institute_code?: string | null;
  course_id?: string | null;
  course_code?: string | null;
  cohort?: number | null;
  deadline?: string | null;
  event_date?: string | null;
  start_date?: string | null;
  end_date?: string | null;
  source_title?: string | null;
  source_url?: string | null;
  created_at: string;
  updated_at: string;
  is_read: boolean;
  important: boolean;
  archived: boolean;
}

export interface BackendSuggestedQuestion {
  id: string;
  question_text: string;
  source_type: string;
  source_id?: string | null;
  notification_id?: string | null;
  topic?: string | null;
  intent?: string | null;
  category?: string | null;
  trigger_phase?: string | null;
  institute_id?: string | null;
  institute_code?: string | null;
  course_id?: string | null;
  course_code?: string | null;
  cohort?: number | null;
  score: string | number;
  priority: number;
  created_by_ai: boolean;
  approved_by_admin: boolean;
  is_active: boolean;
  valid_from?: string | null;
  valid_until?: string | null;
}

export interface BackendSuggestedQuestionGroups {
  for_you: BackendSuggestedQuestion[];
  trending_now: BackendSuggestedQuestion[];
  from_announcements: BackendSuggestedQuestion[];
  from_events: BackendSuggestedQuestion[];
}

export interface BackendCurrentUser {
  id: string;
  email: string;
  full_name: string;
  preferred_name?: string | null;
  roles: BackendRole[];
  student_profile?: BackendStudentProfile | null;
  institute?: BackendInstitute | null;
}

export interface LoginResponse {
  access_token: string;
  token_type: "bearer" | string;
  user: BackendCurrentUser;
}

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

function browserStorage(): Storage | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

export function getStoredAccessToken(): string | null {
  return browserStorage()?.getItem(AUTH_TOKEN_STORAGE_KEY) ?? null;
}

export function setStoredAccessToken(token: string): void {
  browserStorage()?.setItem(AUTH_TOKEN_STORAGE_KEY, token);
}

export function clearStoredAccessToken(): void {
  browserStorage()?.removeItem(AUTH_TOKEN_STORAGE_KEY);
}

export function authenticatedHeaders(
  headers?: HeadersInit,
  token: string | null = getStoredAccessToken()
): Headers {
  const next = new Headers(headers);
  if (token) next.set("Authorization", `Bearer ${token}`);
  return next;
}

async function responseError(res: Response, fallback: string): Promise<ApiError> {
  let detail = fallback;
  try {
    const body = await res.json();
    if (typeof body?.detail === "string") detail = body.detail;
  } catch {
    /* keep fallback */
  }
  return new ApiError(detail, res.status);
}

export async function apiRequest<T>(
  url: string,
  init: RequestInit & { token?: string | null } = {}
): Promise<T> {
  const { token = getStoredAccessToken(), headers, ...rest } = init;
  const res = await fetch(url, {
    ...rest,
    headers: authenticatedHeaders(headers, token),
  });
  if (!res.ok) {
    throw await responseError(res, `Request failed (${res.status}) for ${url}`);
  }
  return (await res.json()) as T;
}

export async function login(email: string, password: string): Promise<LoginResponse> {
  const res = await fetch("/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) {
    throw await responseError(res, "Invalid email or password.");
  }
  return (await res.json()) as LoginResponse;
}

export async function getMe(token: string = getStoredAccessToken() ?? ""): Promise<BackendCurrentUser> {
  return apiRequest<BackendCurrentUser>("/api/auth/me", {
    method: "GET",
    token,
    headers: { Accept: "application/json" },
  });
}

export async function logout(token: string = getStoredAccessToken() ?? ""): Promise<{ success: boolean }> {
  return apiRequest<{ success: boolean }>("/api/auth/logout", {
    method: "POST",
    token,
    headers: { Accept: "application/json" },
  });
}

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
      headers: authenticatedHeaders({ "Content-Type": "application/json" }),
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
  opts: {
    onDelta: (text: string) => void;
    // Forward-compatible: fires for `event: status` (pre-reveal step) and `event: suggestions`
    // (post-answer follow-ups) IF the backend ever emits them. No-ops today — the current
    // backend sends only delta + done — so wiring these now costs nothing and is honest.
    onStatus?: (step: string) => void;
    onSuggestions?: (questions: string[]) => void;
    signal?: AbortSignal;
  }
): Promise<ChatResponse> {
  const res = await fetch("/api/chat/stream", {
    method: "POST",
    headers: authenticatedHeaders({ "Content-Type": "application/json" }),
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
    else if (event === "status") opts.onStatus?.(data.step as string);
    else if (event === "suggestions") opts.onSuggestions?.(data.questions as string[]);
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
  return apiRequest<T>(url, { signal, headers: { Accept: "application/json" } });
}

const SCHEDULE_DAYS: ScheduleDay[] = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const NOTIFICATION_TYPES: NotificationType[] = [
  "academic",
  "schedule",
  "deadline",
  "event",
  "student_services",
  "system",
];
const DEADLINE_KINDS: DeadlineKind[] = [
  "assignment",
  "exam",
  "registration",
  "tuition",
  "administrative",
];

export type StudentCourse = BackendCourse;

function isoTime(iso: string): string {
  const date = new Date(iso);
  return date.toLocaleTimeString("en-GB", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

function safeNotificationType(type: string): NotificationType {
  return NOTIFICATION_TYPES.includes(type as NotificationType)
    ? (type as NotificationType)
    : "system";
}

function safeDeadlineKind(kind?: string | null): DeadlineKind {
  return DEADLINE_KINDS.includes(kind as DeadlineKind)
    ? (kind as DeadlineKind)
    : "administrative";
}

function suggestionPhase(phase?: string | null): SuggestedQuestion["trigger_phase"] {
  if (phase === "early" || phase === "near_deadline" || phase === "overdue") return phase;
  return "active";
}

function mapStudentProfile(profile: BackendStudentMe): StudentProfile {
  const summary = profile.academic_summary;
  const program = profile.program ?? profile.major ?? "Program not set";
  return {
    student_id: profile.student_id,
    full_name: profile.student_id,
    preferred_name: profile.student_id,
    program,
    college: profile.institute.name_en,
    year: profile.academic_year ?? 1,
    intake: summary?.current_semester ?? (profile.cohort ? `Cohort ${profile.cohort}` : "—"),
    email: "",
    advisor: profile.advisor_name ?? profile.advisor_email ?? "—",
    gpa: summary?.gpa == null ? 0 : Number(summary.gpa),
    credits_earned: summary?.credits_earned ?? 0,
    credits_required: summary?.credits_required ?? 0,
  };
}

function mapScheduleItem(item: BackendScheduleItem): ClassSession {
  const start = new Date(item.start_time);
  return {
    id: item.id,
    course_code: item.course_code ?? item.title,
    course_title: item.course_title ?? item.title,
    day: SCHEDULE_DAYS[start.getDay()],
    start: isoTime(item.start_time),
    end: isoTime(item.end_time),
    room: item.room ?? item.location ?? "—",
    building: item.building ?? item.location ?? "—",
    instructor: item.instructor ?? "—",
  };
}

function mapDeadline(deadline: BackendDeadline): Deadline {
  return {
    id: deadline.id,
    title: deadline.title,
    course_code: deadline.course_code ?? undefined,
    kind: safeDeadlineKind(deadline.kind),
    due_at: deadline.due_at,
    source_title: deadline.source_title ?? undefined,
    source_url: deadline.source_url ?? undefined,
  };
}

function mapNotification(notification: BackendNotification): Notification {
  return {
    id: notification.id,
    type: safeNotificationType(notification.type),
    title: notification.title,
    message: notification.message,
    created_at: notification.created_at,
    read: notification.is_read,
    important: notification.important,
    archived: notification.archived,
    source_title: notification.source_title ?? undefined,
    source_url: notification.source_url ?? undefined,
    priority: notification.priority as Notification["priority"],
    target_audience: [notification.target_scope],
    deadline: notification.deadline ?? undefined,
    event_date: notification.event_date ?? undefined,
    start_date: notification.start_date ?? undefined,
    end_date: notification.end_date ?? undefined,
    status: notification.status as Notification["status"],
    updated_at: notification.updated_at,
  };
}

function mapSuggestedQuestion(question: BackendSuggestedQuestion): SuggestedQuestion {
  const category = safeNotificationType(question.category ?? question.source_type);
  const timestamp = question.valid_from ?? question.valid_until ?? new Date(0).toISOString();
  return {
    id: question.id,
    notification_id: question.notification_id ?? question.source_id ?? "",
    question_text: question.question_text,
    category,
    trigger_phase: suggestionPhase(question.trigger_phase),
    score: Number(question.score),
    created_by_ai: question.created_by_ai,
    approved_by_admin: question.approved_by_admin,
    is_active: question.is_active,
    created_at: timestamp,
    updated_at: timestamp,
  };
}

function classEvent(item: BackendScheduleItem): CalendarEvent {
  const code = item.course_code ?? item.title;
  return {
    id: item.id,
    type: "class",
    title: item.course_title ?? item.title,
    start: item.start_time,
    end: item.end_time,
    location: [item.room, item.building].filter(Boolean).join(", ") || item.location || undefined,
    course: code,
    category: item.schedule_type || "Class",
    description: item.instructor ? `Instructor: ${item.instructor}` : undefined,
  };
}

function deadlineEvent(deadline: BackendDeadline): CalendarEvent {
  const kind = safeDeadlineKind(deadline.kind);
  return {
    id: deadline.id,
    type: kind === "exam" ? "exam" : "deadline",
    title: deadline.title,
    start: deadline.due_at,
    course: deadline.course_code ?? deadline.course_title ?? undefined,
    category: kind === "exam" ? "Exam" : "Deadline",
    source_title: deadline.source_title ?? undefined,
    source_url: deadline.source_url ?? undefined,
  };
}

// ---- Student profile --------------------------------------------------------
// [LIVE] GET /students/me -> backend StudentProfileResponse
export async function getStudentMe(): Promise<BackendStudentMe> {
  return getJSON<BackendStudentMe>("/api/students/me");
}

export async function getStudentProfile(): Promise<StudentProfile> {
  return mapStudentProfile(await getStudentMe());
}

// [LIVE] GET /students/me/courses -> backend CourseResponse[]
export async function getStudentCourses(): Promise<StudentCourse[]> {
  return getJSON<StudentCourse[]>("/api/students/me/courses");
}

// [LIVE] GET /students/me/schedule -> ClassSession[]
export async function getStudentSchedule(): Promise<ClassSession[]> {
  const rows = await getJSON<BackendScheduleItem[]>("/api/students/me/schedule");
  return rows.map(mapScheduleItem);
}

// [LIVE] GET /students/me/deadlines -> Deadline[]
export async function getStudentDeadlines(): Promise<Deadline[]> {
  const rows = await getJSON<BackendDeadline[]>("/api/students/me/deadlines");
  return rows.map(mapDeadline).sort((a, b) => a.due_at.localeCompare(b.due_at));
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

// PLAN22.6 — Vinnie NEVER auto-submits. The only path that creates an admin-visible ticket
// is submitTicket(), reachable only from the explicit "Send to Admin" button after the
// student has reviewed the draft. A draft is built in memory by chat.tsx and is never sent
// here until submit, so there is no "create-on-forward" function anymore.
//
// [MOCK] TODO backend contract: POST /tickets
//   body: { subject, body, department, category, priority, source_conversation_id?,
//           include_chat_context, included_context?, created_by_ai } -> SupportTicket
//   The server stores it as status "submitted" + confirmed_by_user true, owns student_name
//   (resolved from the session) and may set due_at/sla_hours from category+priority policy.
export async function submitTicket(draft: TicketDraft): Promise<SupportTicket> {
  const now = new Date().toISOString();
  // Demo SLA window: high → 24h, medium → 72h, low → 168h from submission.
  const slaHours = draft.priority === "high" ? 24 : draft.priority === "medium" ? 72 : 168;
  const ticket: SupportTicket = {
    id: `TKT-${Math.floor(1000 + Math.random() * 9000)}`,
    subject: draft.subject.trim() || "Support request",
    body: draft.body.trim(),
    department: draft.department,
    category: draft.category,
    status: "submitted",
    priority: draft.priority,
    created_at: now,
    updated_at: now,
    submitted_at: now,
    // New PLAN23.6.01 fields — server owns these for real; mocked here.
    student_name: MOCK_PROFILE.full_name,
    sla_hours: slaHours,
    due_at: new Date(Date.now() + slaHours * 3_600_000).toISOString(),
    confirmed_by_user: true,
    created_by_ai: draft.origin_question != null,
    // Privacy: the chat-context summary is attached ONLY when the student opted in.
    include_chat_context: draft.include_chat_context,
    included_context: draft.include_chat_context ? draft.context_preview : undefined,
    source_conversation_id: draft.source_conversation_id,
    origin_question: draft.origin_question,
    messages: [{ id: "m1", author: "student", body: draft.body.trim(), created_at: now }],
  };
  // Prepend so the new ticket shows at the top of the list on the next fetch.
  MOCK_TICKETS.unshift(ticket);
  return delay(ticket, 400);
}

// [MOCK] No network in MVP — drafts live in ChatProvider React state only (privacy: an
// unconfirmed, possibly sensitive draft must never be persisted to a DB or localStorage).
// TODO backend contract (Phase 2): POST /tickets { status: "draft" } scoped to the student
// (admin queries MUST never return drafts).
export async function saveTicketDraft(draft: TicketDraft): Promise<TicketDraft> {
  return delay({ ...draft }, 150);
}

// [MOCK] TODO backend contract: GET /admin/tickets?status&priority&category -> SupportTicket[]
// The backend MUST enforce this draft/unconfirmed exclusion server-side (RBAC); the client
// filter here is defense-in-depth, not the gate.
export async function getAdminTickets(): Promise<SupportTicket[]> {
  const visible = MOCK_TICKETS.filter(
    (t) => t.status !== "draft" && t.confirmed_by_user === true
  ).map((t) => ({ ...t }));
  return delay(visible);
}

// [MOCK] TODO backend contract: GET /admin/tickets/{id} -> SupportTicket
export async function getAdminTicketDetail(ticketId: string): Promise<SupportTicket> {
  const found = MOCK_TICKETS.find(
    (t) => t.id === ticketId && t.status !== "draft" && t.confirmed_by_user === true
  );
  if (!found) throw new Error(`Ticket ${ticketId} not found`);
  return delay({ ...found });
}

// [MOCK] TODO backend contract: PATCH /admin/tickets/{id} { status } -> SupportTicket
export async function updateTicketStatus(
  ticketId: string,
  status: TicketStatus
): Promise<SupportTicket> {
  return delay(patchTicket(ticketId, { status }), 200);
}

// [MOCK] TODO backend contract: POST /admin/tickets/{id}/messages { body } -> SupportTicket
// Appends an admin reply to the ticket thread (visible to the student).
export async function respondToTicket(ticketId: string, body: string): Promise<SupportTicket> {
  const t = MOCK_TICKETS.find((x) => x.id === ticketId);
  if (!t) throw new Error(`Ticket ${ticketId} not found`);
  const now = new Date().toISOString();
  const messages = [
    ...(t.messages ?? []),
    { id: `m${(t.messages?.length ?? 0) + 1}`, author: "admin" as const, body, created_at: now },
  ];
  return delay(patchTicket(ticketId, { messages, status: "waiting_for_student" }), 250);
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
// [LIVE] GET /students/me/notifications -> Notification[]
export async function getStudentNotifications(): Promise<Notification[]> {
  const rows = await getJSON<BackendNotification[]>("/api/students/me/notifications");
  return rows.map(mapNotification);
}

function patchNotification(id: string, patch: Partial<Notification>): Notification {
  const n = MOCK_NOTIFICATIONS.find((x) => x.id === id);
  if (!n) throw new Error(`Notification ${id} not found`);
  Object.assign(n, patch);
  return { ...n };
}

// Local-only until notification mutation endpoints exist.
export async function markNotificationRead(id: string, read = true): Promise<Notification> {
  return delay({ id, read } as Notification, 150);
}

// Local-only until notification mutation endpoints exist.
export async function markNotificationImportant(
  id: string,
  important: boolean
): Promise<Notification> {
  return delay({ id, important } as Notification, 150);
}

// Local-only until notification mutation endpoints exist.
export async function archiveNotification(id: string): Promise<Notification> {
  return delay({ id, archived: true } as Notification, 150);
}

// Local-only until notification mutation endpoints exist.
export async function deleteNotification(_id: string): Promise<{ ok: true }> {
  return delay({ ok: true } as const, 150);
}

// ---- Admin notifications + suggested questions (PLAN22.6) -------------------
// [MOCK] TODO backend contract: GET /admin/notifications -> Notification[] (all statuses)
export async function getAdminNotifications(): Promise<Notification[]> {
  return delay(MOCK_NOTIFICATIONS.map((n) => ({ ...n })));
}

// [MOCK] TODO backend contract: POST /admin/notifications { ... } -> Notification
// Admin authors a notification (optionally with reviewed/approved suggested questions). A
// "published" notification with active questions immediately drives student suggestions.
export async function createNotification(input: {
  title: string;
  message: string;
  type: NotificationType;
  priority?: Notification["priority"];
  target_audience?: string[];
  deadline?: string;
  event_date?: string;
  status?: Notification["status"];
  suggested_questions?: SuggestedQuestion[];
  source_title?: string;
  source_url?: string;
}): Promise<Notification> {
  const now = new Date().toISOString();
  const notification: Notification = {
    id: `n-${Math.floor(1000 + Math.random() * 9000)}`,
    type: input.type,
    title: input.title.trim(),
    message: input.message.trim(),
    created_at: now,
    updated_at: now,
    read: false,
    important: input.priority === "high" || input.priority === "urgent",
    priority: input.priority,
    target_audience: input.target_audience,
    deadline: input.deadline,
    event_date: input.event_date,
    status: input.status ?? "draft",
    created_by: "admin",
    source_title: input.source_title,
    source_url: input.source_url,
    suggested_questions: input.suggested_questions,
  };
  MOCK_NOTIFICATIONS.unshift(notification);
  return delay(notification, 300);
}

// [MOCK] TODO backend contract: PATCH /admin/notifications/{id} { ... } -> Notification
export async function updateNotification(
  id: string,
  patch: Partial<Notification>
): Promise<Notification> {
  return delay(patchNotification(id, { ...patch, updated_at: new Date().toISOString() }), 200);
}

// [MOCK] TODO backend contract: POST /admin/notifications/{id}/publish -> Notification
// Publishes the notification and activates its admin-approved suggested questions.
export async function publishNotification(id: string): Promise<Notification> {
  const n = MOCK_NOTIFICATIONS.find((x) => x.id === id);
  if (!n) throw new Error(`Notification ${id} not found`);
  const questions = (n.suggested_questions ?? []).map((q) => ({
    ...q,
    is_active: q.approved_by_admin,
  }));
  return delay(
    patchNotification(id, {
      status: "published",
      suggested_questions: questions,
      updated_at: new Date().toISOString(),
    }),
    250
  );
}

// [MOCK] Rule-based for MVP — runs the lib/suggestedQuestions.ts template engine for the
// notification's current deadline phase. Returns UNSAVED candidates for the admin to
// review/edit/approve before publishing.
// TODO backend contract (Phase 2): POST /admin/notifications/{id}/suggested-questions/generate (AI).
export async function generateSuggestedQuestions(input: {
  id?: string;
  type: NotificationType;
  title?: string;
  message?: string;
  deadline?: string;
  event_date?: string;
  lang?: Lang;
}): Promise<SuggestedQuestion[]> {
  const draft: Notification = {
    id: input.id ?? `n-preview`,
    type: input.type,
    title: input.title ?? "",
    message: input.message ?? "",
    created_at: new Date().toISOString(),
    read: false,
    important: false,
    deadline: input.deadline,
    event_date: input.event_date,
  };
  return delay(generateQuestions(draft, new Date(), input.lang ?? "en"), 150);
}

// [LIVE] GET /suggestions/me -> grouped suggested questions
export async function getSuggestedQuestions(): Promise<BackendSuggestedQuestionGroups> {
  return getJSON<BackendSuggestedQuestionGroups>("/api/suggestions/me");
}

export async function getActiveSuggestedQuestions(
  _lang: Lang = "en"
): Promise<SuggestedQuestion[]> {
  const groups = await getSuggestedQuestions();
  return [
    ...groups.for_you,
    ...groups.trending_now,
    ...groups.from_announcements,
    ...groups.from_events,
  ]
    .map(mapSuggestedQuestion)
    .sort((a, b) => b.score - a.score);
}

// ---- Calendar ---------------------------------------------------------------
// [LIVE-composed] The backend exposes schedule and deadlines separately in Phase 7.
// Calendar UI gets a combined feed from those real endpoints; campus event data remains
// empty until a dedicated student events endpoint exists.
export async function getStudentCalendar(
  from?: string,
  to?: string
): Promise<CalendarEvent[]> {
  const [schedule, deadlines] = await Promise.all([
    getJSON<BackendScheduleItem[]>("/api/students/me/schedule?upcoming_only=false"),
    getJSON<BackendDeadline[]>("/api/students/me/deadlines?upcoming_only=false"),
  ]);
  const events = [...schedule.map(classEvent), ...deadlines.map(deadlineEvent)];
  if (!from && !to) return events;

  const start = from ? new Date(from).getTime() : Number.NEGATIVE_INFINITY;
  const end = to ? new Date(to).getTime() : Number.POSITIVE_INFINITY;
  return events.filter((event) => {
    const at = new Date(event.start).getTime();
    return at >= start && at <= end;
  });
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
