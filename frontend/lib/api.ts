import type { ChatRequest, ChatResponse, SourceSummary } from "./types";
import type {
  AdminStats,
  AnalyticsOverview,
  AdminDashboard,
  CalendarEvent,
  ClassSession,
  Deadline,
  DeadlineKind,
  ForumAttachment,
  ForumCategory,
  ForumComment,
  ForumMember,
  ForumSort,
  ForumTopic,
  ForumVoteResult,
  ForumVoteTarget,
  ForumVoteValue,
  KnowledgeSource,
  Notification,
  NotificationType,
  ResolveQuestionPayload,
  ScheduleDay,
  SourceCategory,
  StudentProfile,
  SuggestedQuestion,
  SupportTicket,
  TicketCategory,
  TicketDraft,
  TicketMessage,
  TicketPriority,
  TicketStatus,
  TicketStatusHistory,
  TuitionStatus,
  UnansweredQuestion,
} from "./portalTypes";
import { generate as generateQuestions } from "./suggestedQuestions";
import type { Lang } from "./i18n";
import {
  MOCK_ADMIN_STATS,
  MOCK_ANALYTICS,
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
  recipient_user_id?: string | null;
  forum_topic_id?: string | null;
  forum_comment_id?: string | null;
  created_at: string;
  updated_at: string;
  is_read: boolean;
  important: boolean;
  archived: boolean;
}

export interface BackendAdminNotification {
  id: string;
  type: string;
  title: string;
  message: string;
  title_vi?: string | null;
  title_en?: string | null;
  message_vi?: string | null;
  message_en?: string | null;
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
  forum_topic_id?: string | null;
  forum_comment_id?: string | null;
  created_by?: string | null;
  created_by_email?: string | null;
  created_by_name?: string | null;
  created_at: string;
  updated_at: string;
}

export interface BackendAdminNotificationTarget {
  id: string;
  code: string;
  name_vi: string;
  name_en: string;
}

export interface AdminNotificationPayload {
  type?: NotificationType | string;
  title?: string;
  message?: string;
  title_vi?: string | null;
  title_en?: string | null;
  message_vi?: string | null;
  message_en?: string | null;
  priority?: Notification["priority"];
  status?: Notification["status"];
  target_scope?: "all" | "institute" | "cohort";
  institute_id?: string | null;
  cohort?: number | null;
  deadline?: string | null;
  event_date?: string | null;
  start_date?: string | null;
  end_date?: string | null;
  source_title?: string | null;
  source_url?: string | null;
  forum_topic_id?: string | null;
  forum_comment_id?: string | null;
}

export type AdminNotificationCreatePayload = AdminNotificationPayload & {
  title: string;
  message: string;
  type: NotificationType | string;
};

export interface BackendNotificationReadState {
  notification_id: string;
  is_read: boolean;
}

export interface BackendMarkAllNotificationsReadResponse {
  updated_count: number;
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

export interface BackendConversationMessage {
  id: string;
  conversation_id: string;
  role: "user" | "assistant" | "system" | "tool" | string;
  content: string;
  answer_json?: Record<string, unknown> | null;
  intent?: string | null;
  topic?: string | null;
  confidence?: number | null;
  needs_human_review: boolean;
  created_at: string;
}

export interface BackendConversationSummary {
  id: string;
  title?: string | null;
  title_manual?: boolean;
  topic?: string | null;
  created_at: string;
  updated_at: string;
  last_message_at?: string | null;
}

export interface BackendConversationDetail extends BackendConversationSummary {
  messages: BackendConversationMessage[];
}

export interface CreateConversationPayload {
  title?: string;
  topic?: string;
  initial_message?: string;
}

export interface UpdateConversationPayload {
  title?: string;
  topic?: string | null;
  title_manual?: boolean;
}

export interface DeleteConversationResponse {
  deleted: boolean;
}

export interface BackendTicketMessage {
  id: string;
  ticket_id: string;
  sender_user_id?: string | null;
  sender_email?: string | null;
  sender_full_name?: string | null;
  author_type: string;
  body: string;
  created_at: string;
}

export interface BackendTicketStatusHistory {
  id: string;
  old_status?: string | null;
  new_status: string;
  changed_by?: string | null;
  changed_by_email?: string | null;
  changed_by_full_name?: string | null;
  changed_at: string;
}

export interface BackendTicketSummary {
  id: string;
  student_profile_id: string;
  student_id?: string | null;
  student_name?: string | null;
  institute_id?: string | null;
  institute_code?: string | null;
  subject: string;
  body: string;
  department?: string | null;
  category?: string | null;
  priority: string;
  status: string;
  confirmed_by_user: boolean;
  created_by_ai: boolean;
  include_chat_context: boolean;
  source_conversation_id?: string | null;
  origin_question?: string | null;
  assigned_admin_id?: string | null;
  assignee?: string | null;
  submitted_at?: string | null;
  due_at?: string | null;
  sla_hours?: number | null;
  resolution?: string | null;
  archived: boolean;
  deleted: boolean;
  created_at: string;
  updated_at: string;
}

export interface BackendTicketDetail extends BackendTicketSummary {
  included_context?: string | null;
  messages: BackendTicketMessage[];
  status_history: BackendTicketStatusHistory[];
}

export interface CreateTicketPayload {
  subject?: string;
  body?: string;
  title?: string;
  description?: string;
  department?: string | null;
  category?: TicketCategory | string | null;
  priority?: TicketPriority | string;
  include_chat_context?: boolean;
  included_context?: string | null;
  source_conversation_id?: string | null;
  origin_question?: string | null;
  created_by_ai?: boolean;
}

export interface AddTicketMessagePayload {
  body: string;
}

export interface AdminTicketFilters {
  status?: TicketStatus | "all";
  priority?: TicketPriority | "all";
  include_archived?: boolean;
}

export interface AdminUpdateTicketPayload {
  status?: TicketStatus;
  priority?: TicketPriority;
  assigned_admin_id?: string | null;
  resolution?: string | null;
  archived?: boolean;
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

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function normalizeConversationSummary(value: unknown): BackendConversationSummary | null {
  if (!isRecord(value) || typeof value.id !== "string") return null;
  const createdAt = typeof value.created_at === "string" ? value.created_at : "";
  const updatedAt =
    typeof value.updated_at === "string" ? value.updated_at : createdAt || new Date(0).toISOString();
  return {
    id: value.id,
    title: typeof value.title === "string" ? value.title : "New conversation",
    title_manual: typeof value.title_manual === "boolean" ? value.title_manual : false,
    topic: typeof value.topic === "string" ? value.topic : null,
    created_at: createdAt || updatedAt,
    updated_at: updatedAt,
    last_message_at: typeof value.last_message_at === "string" ? value.last_message_at : null,
  };
}

export async function getConversations(): Promise<BackendConversationSummary[]> {
  const body = await apiRequest<unknown>("/api/conversations", {
    method: "GET",
    headers: { Accept: "application/json" },
  });
  if (!Array.isArray(body)) return [];
  return body
    .map(normalizeConversationSummary)
    .filter((conversation): conversation is BackendConversationSummary => conversation !== null);
}

export async function createConversation(
  payload: CreateConversationPayload = {}
): Promise<BackendConversationDetail> {
  return apiRequest<BackendConversationDetail>("/api/conversations", {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function getConversation(
  conversationId: string
): Promise<BackendConversationDetail> {
  return apiRequest<BackendConversationDetail>(`/api/conversations/${conversationId}`, {
    method: "GET",
    headers: { Accept: "application/json" },
  });
}

export async function getConversationMessages(
  conversationId: string
): Promise<BackendConversationMessage[]> {
  return apiRequest<BackendConversationMessage[]>(
    `/api/conversations/${conversationId}/messages`,
    {
      method: "GET",
      headers: { Accept: "application/json" },
    }
  );
}

export async function updateConversation(
  conversationId: string,
  payload: UpdateConversationPayload
): Promise<BackendConversationDetail> {
  return apiRequest<BackendConversationDetail>(`/api/conversations/${conversationId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function deleteConversation(
  conversationId: string
): Promise<DeleteConversationResponse> {
  return apiRequest<DeleteConversationResponse>(`/api/conversations/${conversationId}`, {
    method: "DELETE",
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
  "forum",
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
  // Forum mention/reply notifications deep-link to the discussion they point at.
  const forumHref = notification.forum_topic_id
    ? `/student/forum/topics/${notification.forum_topic_id}`
    : undefined;
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
    action_href: forumHref,
    priority: notification.priority as Notification["priority"],
    target_audience: [notification.target_scope],
    deadline: notification.deadline ?? undefined,
    event_date: notification.event_date ?? undefined,
    start_date: notification.start_date ?? undefined,
    end_date: notification.end_date ?? undefined,
    status: notification.status as Notification["status"],
    updated_at: notification.updated_at,
    forum_topic_id: notification.forum_topic_id ?? undefined,
    forum_comment_id: notification.forum_comment_id ?? undefined,
  };
}

function mapAdminNotification(notification: BackendAdminNotification): Notification {
  const forumHref = notification.forum_topic_id
    ? `/student/forum/topics/${notification.forum_topic_id}`
    : undefined;
  const targetAudience =
    notification.target_scope === "institute" && notification.institute_code
      ? [notification.institute_code]
      : notification.target_scope === "cohort" && notification.cohort
        ? [`Cohort ${notification.cohort}`]
        : [notification.target_scope];
  return {
    id: notification.id,
    type: safeNotificationType(notification.type),
    title: notification.title,
    message: notification.message,
    title_vi: notification.title_vi ?? undefined,
    title_en: notification.title_en ?? undefined,
    message_vi: notification.message_vi ?? undefined,
    message_en: notification.message_en ?? undefined,
    created_at: notification.created_at,
    read: false,
    important:
      notification.priority === "high" || notification.priority === "urgent",
    archived: notification.status === "archived",
    source_title: notification.source_title ?? undefined,
    source_url: notification.source_url ?? undefined,
    action_href: forumHref,
    priority: notification.priority as Notification["priority"],
    target_audience: targetAudience,
    deadline: notification.deadline ?? undefined,
    event_date: notification.event_date ?? undefined,
    start_date: notification.start_date ?? undefined,
    end_date: notification.end_date ?? undefined,
    status: notification.status as Notification["status"],
    created_by:
      notification.created_by_name ??
      notification.created_by_email ??
      notification.created_by ??
      undefined,
    updated_at: notification.updated_at,
    forum_topic_id: notification.forum_topic_id ?? undefined,
    forum_comment_id: notification.forum_comment_id ?? undefined,
  };
}

function mapSuggestedQuestion(question: BackendSuggestedQuestion): SuggestedQuestion {
  const category = safeNotificationType(question.category ?? question.source_type);
  const timestamp = question.valid_from ?? question.valid_until ?? new Date(0).toISOString();
  return {
    id: question.id,
    notification_id: question.notification_id ?? question.source_id ?? "",
    source_type: question.source_type,
    source_id: question.source_id ?? undefined,
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

// [MOCK] TODO future backend contract: GET /students/me/tuition -> TuitionStatus
export async function getTuitionStatus(): Promise<TuitionStatus> {
  return delay(MOCK_TUITION);
}

// ---- Support tickets --------------------------------------------------------
const TICKET_STATUSES: TicketStatus[] = [
  "draft",
  "submitted",
  "open",
  "in_review",
  "in_progress",
  "waiting_for_student",
  "waiting_on_student",
  "resolved",
  "closed",
];
const TICKET_PRIORITIES: TicketPriority[] = ["low", "medium", "high", "urgent"];
const TICKET_CATEGORIES: TicketCategory[] = [
  "academic",
  "schedule",
  "student_services",
  "technical",
  "other",
];
const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

function safeTicketStatus(status?: string | null): TicketStatus {
  return TICKET_STATUSES.includes(status as TicketStatus)
    ? (status as TicketStatus)
    : "submitted";
}

function backendTicketStatus(status?: TicketStatus): string | undefined {
  if (!status) return undefined;
  if (status === "in_review") return "in_progress";
  if (status === "waiting_for_student") return "waiting_on_student";
  if (status === "draft") return undefined;
  return status;
}

function safeTicketPriority(priority?: string | null): TicketPriority {
  return TICKET_PRIORITIES.includes(priority as TicketPriority)
    ? (priority as TicketPriority)
    : "medium";
}

function safeTicketCategory(category?: string | null): TicketCategory {
  return TICKET_CATEGORIES.includes(category as TicketCategory)
    ? (category as TicketCategory)
    : "other";
}

function mapTicketMessage(message: BackendTicketMessage): TicketMessage {
  const author =
    message.author_type === "admin" || message.author_type === "system"
      ? message.author_type
      : "student";
  return {
    id: message.id,
    author,
    body: message.body,
    created_at: message.created_at,
    sender_user_id: message.sender_user_id ?? undefined,
    sender_email: message.sender_email ?? undefined,
    sender_full_name: message.sender_full_name ?? undefined,
  };
}

function mapTicketStatusHistory(row: BackendTicketStatusHistory): TicketStatusHistory {
  return {
    id: row.id,
    old_status: row.old_status ? safeTicketStatus(row.old_status) : undefined,
    new_status: safeTicketStatus(row.new_status),
    changed_by: row.changed_by ?? undefined,
    changed_by_email: row.changed_by_email ?? undefined,
    changed_by_full_name: row.changed_by_full_name ?? undefined,
    changed_at: row.changed_at,
  };
}

function mapTicket(ticket: BackendTicketSummary | BackendTicketDetail): SupportTicket {
  const messages =
    "messages" in ticket && Array.isArray(ticket.messages)
      ? ticket.messages.map(mapTicketMessage)
      : undefined;
  return {
    id: ticket.id,
    subject: ticket.subject,
    body: ticket.body,
    department: ticket.department ?? "Student Support",
    category: safeTicketCategory(ticket.category),
    status: safeTicketStatus(ticket.status),
    priority: safeTicketPriority(ticket.priority),
    created_at: ticket.created_at,
    updated_at: ticket.updated_at,
    confirmed_by_user: ticket.confirmed_by_user,
    created_by_ai: ticket.created_by_ai,
    include_chat_context: ticket.include_chat_context,
    included_context:
      "included_context" in ticket ? ticket.included_context ?? undefined : undefined,
    source_conversation_id: ticket.source_conversation_id ?? undefined,
    origin_question: ticket.origin_question ?? undefined,
    submitted_at: ticket.submitted_at ?? undefined,
    student_id: ticket.student_id ?? undefined,
    due_at: ticket.due_at ?? undefined,
    sla_hours: ticket.sla_hours ?? undefined,
    assignee: ticket.assignee ?? undefined,
    student_name: ticket.student_name ?? undefined,
    resolution: ticket.resolution ?? undefined,
    archived: ticket.archived,
    deleted: ticket.deleted,
    messages,
    status_history:
      "status_history" in ticket && Array.isArray(ticket.status_history)
        ? ticket.status_history.map(mapTicketStatusHistory)
        : undefined,
  };
}

function ticketCreatePayload(payload: CreateTicketPayload): Record<string, unknown> {
  const subject = (payload.subject ?? payload.title ?? "").trim();
  const body = (payload.body ?? payload.description ?? "").trim();
  const sourceConversationId =
    payload.source_conversation_id && UUID_RE.test(payload.source_conversation_id)
      ? payload.source_conversation_id
      : undefined;
  return {
    subject: subject || "Support request",
    body: body || subject || "Support request",
    department: payload.department ?? undefined,
    category: payload.category ?? undefined,
    priority: payload.priority ?? "medium",
    include_chat_context: payload.include_chat_context ?? false,
    included_context:
      payload.include_chat_context && payload.included_context
        ? payload.included_context
        : undefined,
    source_conversation_id: sourceConversationId,
    origin_question: payload.origin_question ?? undefined,
    created_by_ai: payload.created_by_ai ?? false,
  };
}

// [LIVE] GET /tickets/me -> SupportTicket[]
export async function getSupportTickets(): Promise<SupportTicket[]> {
  const rows = await getJSON<BackendTicketSummary[]>("/api/tickets/me");
  return rows.map(mapTicket);
}

// PLAN22.6 — Vinnie NEVER auto-submits. The only path that creates an admin-visible ticket
// is submitTicket(), reachable only from the explicit "Send to Admin" button after the
// student has reviewed the draft. A draft is built in memory by chat.tsx and is never sent
// here until submit, so there is no "create-on-forward" function anymore.
export async function submitTicket(draft: TicketDraft): Promise<SupportTicket> {
  return createTicket({
    subject: draft.subject,
    body: draft.body,
    department: draft.department,
    category: draft.category,
    priority: draft.priority,
    include_chat_context: draft.include_chat_context,
    included_context: draft.context_preview,
    source_conversation_id: draft.source_conversation_id,
    origin_question: draft.origin_question,
    created_by_ai: draft.created_by_ai ?? false,
  });
}

// [LIVE] POST /tickets/suggest -> Vinnie's drafted {subject, body, category} for review-before-send.
// Advisory only (nothing is persisted); the backend fails open to a heuristic so this always resolves.
export async function suggestTicketDraft(payload: {
  origin_question: string;
  answer?: string | null;
  context?: string | null;
}): Promise<{ subject: string; body: string; category: TicketCategory }> {
  const row = await apiRequest<{ subject: string; body: string; category: string }>(
    "/api/tickets/suggest",
    {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({
        origin_question: payload.origin_question,
        answer: payload.answer ?? undefined,
        context: payload.context ?? undefined,
      }),
    }
  );
  return {
    subject: row.subject,
    body: row.body,
    category: safeTicketCategory(row.category),
  };
}

export async function createTicket(payload: CreateTicketPayload): Promise<SupportTicket> {
  const row = await apiRequest<BackendTicketDetail>("/api/tickets", {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify(ticketCreatePayload(payload)),
  });
  return mapTicket(row);
}

export async function getTicket(ticketId: string): Promise<SupportTicket> {
  const row = await getJSON<BackendTicketDetail>(`/api/tickets/${ticketId}`);
  return mapTicket(row);
}

export async function addTicketMessage(
  ticketId: string,
  payload: AddTicketMessagePayload
): Promise<TicketMessage> {
  const row = await apiRequest<BackendTicketMessage>(`/api/tickets/${ticketId}/messages`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify(payload),
  });
  return mapTicketMessage(row);
}

// [MOCK] No network in MVP — drafts live in ChatProvider React state only (privacy: an
// unconfirmed, possibly sensitive draft must never be persisted to a DB or localStorage).
// TODO future backend contract: POST /tickets { status: "draft" } scoped to the student
// (admin queries MUST never return drafts).
export async function saveTicketDraft(draft: TicketDraft): Promise<TicketDraft> {
  return delay({ ...draft }, 150);
}

// [LIVE] GET /admin/tickets -> SupportTicket[]
export async function getAdminTickets(filters: AdminTicketFilters = {}): Promise<SupportTicket[]> {
  const params = new URLSearchParams();
  const status = backendTicketStatus(filters.status === "all" ? undefined : filters.status);
  if (status) params.set("status", status);
  if (filters.priority && filters.priority !== "all") params.set("priority", filters.priority);
  if (filters.include_archived) params.set("include_archived", "true");
  const query = params.toString();
  const rows = await getJSON<BackendTicketSummary[]>(`/api/admin/tickets${query ? `?${query}` : ""}`);
  return rows.map(mapTicket);
}

export async function getAdminTicket(ticketId: string): Promise<SupportTicket> {
  const row = await getJSON<BackendTicketDetail>(`/api/admin/tickets/${ticketId}`);
  return mapTicket(row);
}

export async function getAdminTicketDetail(ticketId: string): Promise<SupportTicket> {
  return getAdminTicket(ticketId);
}

export async function updateAdminTicket(
  ticketId: string,
  payload: AdminUpdateTicketPayload
): Promise<SupportTicket> {
  const row = await apiRequest<BackendTicketDetail>(`/api/admin/tickets/${ticketId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify({
      ...payload,
      status: backendTicketStatus(payload.status),
    }),
  });
  return mapTicket(row);
}

export async function updateTicketStatus(
  ticketId: string,
  status: TicketStatus
): Promise<SupportTicket> {
  return updateAdminTicket(ticketId, { status });
}

export async function addAdminTicketMessage(
  ticketId: string,
  payload: AddTicketMessagePayload
): Promise<TicketMessage> {
  const row = await apiRequest<BackendTicketMessage>(`/api/admin/tickets/${ticketId}/messages`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify(payload),
  });
  return mapTicketMessage(row);
}

export async function respondToTicket(ticketId: string, body: string): Promise<SupportTicket> {
  await addAdminTicketMessage(ticketId, { body });
  return getAdminTicket(ticketId);
}

export async function getSupportTicketDetail(ticketId: string): Promise<SupportTicket> {
  return getTicket(ticketId);
}

// Legacy student ticket visibility adapters. Phase 10D backend supports create/reply/detail,
// but not student archive/delete mutations; active student pages keep visibility local in
// component state. Keep these isolated until Phase 11 adds real mutation endpoints.
// [MOCK] TODO Phase 11 backend contract: PATCH /tickets/{id} { archived } -> SupportTicket
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

// [MOCK] TODO Phase 11 backend contract: DELETE /tickets/{id} -> { ok: true }
// No permanent delete exists; modelled as a "deleted" visibility state instead.
export async function deleteSupportTicket(ticketId: string): Promise<SupportTicket> {
  return delay(patchTicket(ticketId, { deleted: true }), 250);
}

// ---- Notifications ----------------------------------------------------------
// [LIVE] GET /students/me/notifications -> Notification[]
// `lang` selects the VI/EN variant of each notification's title/message (default VI).
export async function getStudentNotifications(lang: Lang = "vi"): Promise<Notification[]> {
  const rows = await getJSON<BackendNotification[]>(
    `/api/students/me/notifications?lang=${encodeURIComponent(lang)}`
  );
  return rows.map(mapNotification);
}

// [LIVE] POST /students/me/notifications/{id}/read|unread -> read state
export async function markNotificationRead(id: string, read = true): Promise<Notification> {
  const action = read ? "read" : "unread";
  const state = await apiRequest<BackendNotificationReadState>(
    `/api/students/me/notifications/${id}/${action}`,
    {
      method: "POST",
      headers: { Accept: "application/json" },
    }
  );
  return { id: state.notification_id, read: state.is_read } as Notification;
}

// [LIVE] POST /students/me/notifications/mark-all-read -> update count
export async function markAllNotificationsRead(): Promise<BackendMarkAllNotificationsReadResponse> {
  return apiRequest<BackendMarkAllNotificationsReadResponse>(
    "/api/students/me/notifications/mark-all-read",
    {
      method: "POST",
      headers: { Accept: "application/json" },
    }
  );
}

// ---- Admin notifications + suggested questions (PLAN22.6) -------------------
// [LIVE] GET /admin/notifications -> Notification[] (all statuses)
export async function getAdminNotifications(): Promise<Notification[]> {
  const rows = await getJSON<BackendAdminNotification[]>("/api/admin/notifications");
  return rows.map(mapAdminNotification);
}

// [LIVE] GET /admin/notifications/targets -> institutes the admin may target
export async function getAdminNotificationTargets(): Promise<BackendAdminNotificationTarget[]> {
  return getJSON<BackendAdminNotificationTarget[]>("/api/admin/notifications/targets");
}

// [LIVE] POST /admin/notifications { ... } -> Notification
export async function createNotification(input: {
  title: string;
  message: string;
  type: NotificationType | string;
  priority?: Notification["priority"];
  target_audience?: string[];
  target_scope?: "all" | "institute" | "cohort";
  institute_id?: string | null;
  cohort?: number | null;
  deadline?: string | null;
  event_date?: string | null;
  start_date?: string | null;
  end_date?: string | null;
  status?: Notification["status"];
  suggested_questions?: SuggestedQuestion[];
  source_title?: string | null;
  source_url?: string | null;
  forum_topic_id?: string | null;
  forum_comment_id?: string | null;
  title_vi?: string | null;
  title_en?: string | null;
  message_vi?: string | null;
  message_en?: string | null;
}): Promise<Notification> {
  const row = await apiRequest<BackendAdminNotification>("/api/admin/notifications", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      type: input.type,
      title: input.title.trim(),
      message: input.message.trim(),
      title_vi: input.title_vi ?? null,
      title_en: input.title_en ?? null,
      message_vi: input.message_vi ?? null,
      message_en: input.message_en ?? null,
      priority: input.priority ?? "medium",
      status: input.status ?? "draft",
      target_scope: input.target_scope ?? "all",
      institute_id: input.institute_id ?? null,
      cohort: input.cohort ?? null,
      deadline: input.deadline || null,
      event_date: input.event_date || null,
      start_date: input.start_date || null,
      end_date: input.end_date || null,
      source_title: input.source_title ?? null,
      source_url: input.source_url ?? null,
      forum_topic_id: input.forum_topic_id ?? null,
      forum_comment_id: input.forum_comment_id ?? null,
    }),
  });
  return mapAdminNotification(row);
}

// [LIVE] PATCH /admin/notifications/{id} { ... } -> Notification
export async function updateNotification(
  id: string,
  patch: AdminNotificationPayload
): Promise<Notification> {
  const row = await apiRequest<BackendAdminNotification>(`/api/admin/notifications/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      type: patch.type,
      title: patch.title,
      message: patch.message,
      title_vi: patch.title_vi,
      title_en: patch.title_en,
      message_vi: patch.message_vi,
      message_en: patch.message_en,
      priority: patch.priority,
      target_scope: patch.target_scope,
      institute_id: patch.institute_id,
      cohort: patch.cohort,
      deadline: patch.deadline,
      event_date: patch.event_date,
      start_date: patch.start_date,
      end_date: patch.end_date,
      source_title: patch.source_title,
      source_url: patch.source_url,
      forum_topic_id: patch.forum_topic_id,
      forum_comment_id: patch.forum_comment_id,
    }),
  });
  return mapAdminNotification(row);
}

// [LIVE] POST /admin/notifications/{id}/publish -> Notification
export async function publishNotification(id: string): Promise<Notification> {
  const row = await apiRequest<BackendAdminNotification>(
    `/api/admin/notifications/${id}/publish`,
    {
      method: "POST",
      headers: { Accept: "application/json" },
    }
  );
  return mapAdminNotification(row);
}

// [LIVE] POST /admin/notifications/{id}/schedule -> Notification
export async function scheduleNotification(
  id: string,
  publishAt: string,
  endDate?: string | null
): Promise<Notification> {
  const row = await apiRequest<BackendAdminNotification>(
    `/api/admin/notifications/${id}/schedule`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ publish_at: publishAt, end_date: endDate || null }),
    }
  );
  return mapAdminNotification(row);
}

// [LIVE] POST /admin/notifications/{id}/archive -> Notification
export async function archiveAdminNotification(id: string): Promise<Notification> {
  const row = await apiRequest<BackendAdminNotification>(
    `/api/admin/notifications/${id}/archive`,
    {
      method: "POST",
      headers: { Accept: "application/json" },
    }
  );
  return mapAdminNotification(row);
}

// [MOCK] Rule-based for MVP — runs the lib/suggestedQuestions.ts template engine for the
// notification's current deadline phase. Returns UNSAVED candidates for the admin to
// review/edit/approve before publishing.
// TODO Phase 11 backend contract: POST /admin/notifications/{id}/suggested-questions/generate (AI).
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
// `lang` selects the VI/EN variant of each question's text (default VI).
export async function getSuggestedQuestions(
  lang: Lang = "vi"
): Promise<BackendSuggestedQuestionGroups> {
  return getJSON<BackendSuggestedQuestionGroups>(
    `/api/suggestions/me?lang=${encodeURIComponent(lang)}`
  );
}

export async function getActiveSuggestedQuestions(
  lang: Lang = "vi"
): Promise<SuggestedQuestion[]> {
  const groups = await getSuggestedQuestions(lang);
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

// ---- Academic read APIs (Phase 13B/13C) ------------------------------------
// All student-facing and resolved through the authenticated session on the backend
// (current_user.id -> student_profiles.user_id). The client never sends a student_id.
// JSON shapes mirror the FastAPI response models 1:1; Decimal fields arrive as strings.

export type AcademicMeetingType =
  | "lecture"
  | "lab"
  | "tutorial"
  | "seminar"
  | "exam"
  | "office_hour"
  | "deadline";
export type AcademicEnrollmentStatus =
  | "planned"
  | "enrolled"
  | "completed"
  | "failed"
  | "withdrawn"
  | "retaking"
  | "improvement";
export type CurriculumProgressStatus = "completed" | "in_progress" | "failed" | "remaining";
export type AcademicCurriculumCategory =
  | "general_education"
  | "foundation"
  | "major_core"
  | "major_elective"
  | "physical_education"
  | "capstone";
export type AcademicRequisiteType = "prerequisite" | "corequisite";

export interface AcademicFaculty {
  id: string;
  code: string;
  name: string;
}

export interface AcademicProgram {
  id: string;
  faculty_id: string;
  code: string;
  name: string;
  degree_level: string;
  curriculum_year: number;
  total_required_credits: number;
}

export interface AcademicTerm {
  id: string;
  code: string;
  name: string;
  start_date: string;
  end_date: string;
  academic_year: number;
  term_order: number;
}

export interface AcademicCourse {
  id: string;
  code: string;
  name: string;
  credits: number;
  course_level?: number | null;
  department_code?: string | null;
  is_general_education?: boolean;
  description?: string | null;
}

export interface AcademicProfile {
  id: string;
  student_code?: string | null;
  full_name?: string | null;
  current_year?: number | null;
  cohort_year?: number | null;
  status?: string | null;
  faculty?: AcademicFaculty | null;
  program?: AcademicProgram | null;
}

export interface AcademicProgressSummary {
  earned_credits: number;
  required_credits: number;
  completed_required_courses: number;
  remaining_required_courses: number;
  progress_percent: string;
}

export interface AcademicScheduleEvent {
  id: string;
  course_code: string;
  course_name: string;
  section_code?: string | null;
  instructor_name?: string | null;
  meeting_type: AcademicMeetingType;
  title: string;
  start_at: string;
  end_at: string;
  room_name?: string | null;
  building?: string | null;
  note?: string | null;
}

export interface AcademicOverview {
  profile: AcademicProfile;
  current_term: AcademicTerm | null;
  current_gpa: string | null;
  cumulative_cpa: string | null;
  earned_credits: number;
  required_credits: number;
  failed_courses: AcademicCourse[];
  enrolled_courses: AcademicCourse[];
  upcoming_meetings: AcademicScheduleEvent[];
  summary: AcademicProgressSummary;
}

export interface AcademicEnrollment {
  id: string;
  student_id: string;
  course: AcademicCourse;
  term: AcademicTerm;
  section_id?: string | null;
  status: AcademicEnrollmentStatus;
  attempt_no: number;
  is_improvement: boolean;
  retake_of_enrollment_id?: string | null;
  grade_10?: string | null;
  grade_4?: string | null;
  letter_grade?: string | null;
  passed: boolean;
  earned_credits: number;
  is_gpa_counted: boolean;
  completed_at?: string | null;
}

export interface AcademicTranscriptTerm {
  term: AcademicTerm;
  enrollments: AcademicEnrollment[];
  term_gpa: string | null;
  cumulative_cpa: string | null;
}

export interface AcademicTranscriptSummary {
  student_id: string;
  attempted_credits: number;
  earned_credits: number;
  gpa_credits: number;
  gpa: string | null;
  counted_enrollment_ids: string[];
}

export interface AcademicTranscript {
  student_id: string;
  terms: AcademicTranscriptTerm[];
  summary: AcademicTranscriptSummary;
}

export interface CurriculumProgressCourse {
  course: AcademicCourse;
  category: AcademicCurriculumCategory;
  is_required: boolean;
  suggested_year?: number | null;
  suggested_term?: number | null;
  status: CurriculumProgressStatus;
  grade_4?: string | null;
}

export interface AcademicCurriculumProgress {
  program: AcademicProgram | null;
  completed: CurriculumProgressCourse[];
  in_progress: CurriculumProgressCourse[];
  failed: CurriculumProgressCourse[];
  remaining_required: CurriculumProgressCourse[];
  remaining_zero_credit: CurriculumProgressCourse[];
  summary: AcademicProgressSummary;
}

export interface AcademicRequisiteExplanation {
  requisite_type: AcademicRequisiteType;
  required_course: AcademicCourse;
  min_grade_4?: string | null;
  satisfied: boolean;
  reason: string;
}

export interface EligibleCourse {
  course: AcademicCourse;
  category?: AcademicCurriculumCategory | null;
  is_required: boolean;
  eligible: boolean;
  already_completed: boolean;
  currently_enrolled: boolean;
  can_retake_or_improve: boolean;
  blocking_reasons: string[];
  prerequisites: AcademicRequisiteExplanation[];
  corequisites: AcademicRequisiteExplanation[];
}

export interface AcademicEligibility {
  term: AcademicTerm | null;
  eligible: EligibleCourse[];
  blocked: EligibleCourse[];
}

const ACADEMIC_MONTH_RE = /^\d{4}-(0[1-9]|1[0-2])$/;

export async function getAcademicOverview(): Promise<AcademicOverview> {
  return getJSON<AcademicOverview>("/api/academic/me");
}

export async function getAcademicTranscript(): Promise<AcademicTranscript> {
  return getJSON<AcademicTranscript>("/api/academic/me/transcript");
}

export async function getAcademicCurriculum(): Promise<AcademicCurriculumProgress> {
  return getJSON<AcademicCurriculumProgress>("/api/academic/me/curriculum");
}

export async function getEligibleCourses(): Promise<AcademicEligibility> {
  return getJSON<AcademicEligibility>("/api/academic/me/courses/eligible");
}

// month: "YYYY-MM". Validated client-side so an invalid value never reaches the API (the
// backend would answer 422); the page derives `month` from the calendar cursor, so this is a guard.
export async function getMonthlySchedule(month: string): Promise<AcademicScheduleEvent[]> {
  if (!ACADEMIC_MONTH_RE.test(month)) {
    throw new ApiError("month must be in YYYY-MM format.", 422);
  }
  return getJSON<AcademicScheduleEvent[]>(`/api/schedule/me?month=${encodeURIComponent(month)}`);
}

// ---- Knowledge sources (admin) ---------------------------------------------
// [LIVE] GET /api/sources -> SourceSummary[]  (FastAPI GET /sources)
// Mapped onto the richer KnowledgeSource shape the admin table renders. If the
// backend is unreachable, the page should show its normal error/retry state.
function inferCategory(title: string): SourceCategory {
  const t = title.toLowerCase();
  if (/(tuition|fee|payment|financial)/.test(t)) return "Tuition";
  if (/(event|festival|club)/.test(t)) return "Events";
  if (/(service|health|counsel|housing|library)/.test(t)) return "Student Services";
  if (/(schedule|timetable|calendar)/.test(t)) return "Schedule";
  return "Academic";
}

function mapSummaryToSource(s: SourceSummary, i: number): KnowledgeSource {
  const url = s.source_url || "";
  const type =
    s.document_type?.includes("pdf") || /\.pdf(\?|$)/i.test(url)
      ? "pdf"
      : /\.docx(\?|$)/i.test(url)
      ? "docx"
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
  const summaries = await getJSON<SourceSummary[]>("/api/sources");
  return Array.isArray(summaries) ? summaries.map(mapSummaryToSource) : [];
}

// [LIVE] Knowledge Base ingestion (admin-only). URL crawl → POST /api/ingest/run; file upload
// (PDF/DOCX from device) → POST /api/ingest/upload (multipart). Both run the real pipeline
// (parse → chunk → embed → upsert to the vector DB) and return IngestRunResponse. All calls go
// through apiRequest, which attaches the Bearer token the backend now requires.
export interface IngestRunResponse {
  crawled_documents: number;
  indexed_chunks: number;
  skipped_documents: number;
  sources: string[];
}

// Real extracted-text preview for the admin review step (FastAPI POST /ingest/preview).
// Parses the file/URL and returns the actual text — no embedding/indexing happens yet.
export interface IngestPreview {
  title: string;
  document_type: string;
  char_count: number;
  estimated_chunks: number;
  preview_text: string;
  truncated: boolean;
}

export async function previewKnowledgeSource(input: {
  url?: string;
  file?: File | null;
  title?: string;
}): Promise<IngestPreview> {
  const form = new FormData();
  if (input.file) form.append("file", input.file);
  if (input.url) form.append("url", input.url);
  if (input.title) form.append("title", input.title);
  // Multipart: no Content-Type header (browser sets the boundary); apiRequest adds the token.
  return apiRequest<IngestPreview>("/api/ingest/preview", { method: "POST", body: form });
}

export async function uploadKnowledgeSource(input: {
  url?: string;
  file?: File | null;
  category: SourceCategory;
  // Title is honored by the upload route; the URL crawl derives its own title from the page.
  title?: string;
  source_type?: "pdf" | "docx" | "url";
}): Promise<IngestRunResponse> {
  if (input.url) {
    return apiRequest<IngestRunResponse>("/api/ingest/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ urls: [input.url], force: true }),
    });
  }
  if (input.file) {
    // Multipart: do NOT set Content-Type — the browser adds the boundary. apiRequest still
    // attaches the Authorization header.
    const form = new FormData();
    form.append("file", input.file);
    if (input.category) form.append("category", input.category);
    if (input.title) form.append("title", input.title);
    return apiRequest<IngestRunResponse>("/api/ingest/upload", {
      method: "POST",
      body: form,
    });
  }
  throw new ApiError("Provide a URL or a file to upload.", 400);
}

// [LIVE] Re-crawl a source by URL through POST /ingest/run (force=true).
export async function recrawlSource(sourceUrl: string): Promise<IngestRunResponse> {
  return apiRequest<IngestRunResponse>("/api/ingest/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ urls: [sourceUrl], force: true }),
  });
}

// [MOCK] TODO future backend contract: POST /sources/{id}/disable -> { ok: true }
export async function disableSource(sourceId: string): Promise<{ ok: true }> {
  return delay({ ok: true } as const, 300);
}

// ---- Unanswered questions (admin) ------------------------------------------
// [MOCK] TODO future backend contract: GET /admin/unanswered -> UnansweredQuestion[]
//   (populated from chat turns where deriveState == "degraded"/"refusal").
export async function getUnansweredQuestions(): Promise<UnansweredQuestion[]> {
  return delay([...MOCK_UNANSWERED]);
}

// [MOCK] TODO future backend contract: POST /admin/unanswered/{id}/resolve
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
// [LIVE] GET /admin/dashboard -> AdminDashboard
export async function getAdminDashboard(): Promise<AdminDashboard> {
  return getJSON<AdminDashboard>("/api/admin/dashboard");
}

// [MOCK] TODO future backend contract: GET /admin/stats -> AdminStats
export async function getAdminStats(): Promise<AdminStats> {
  return delay(MOCK_ADMIN_STATS);
}

// [MOCK] TODO future backend contract: GET /admin/analytics -> AnalyticsOverview
export async function getAnalytics(): Promise<AnalyticsOverview> {
  return delay(MOCK_ANALYTICS);
}

// ---- Forum / Discussion Hub -------------------------------------------------
// [LIVE] FastAPI /forum/* (proxied through /api/forum/*). Public peer discussion,
// separate from private tickets. @mentions + replies create 'forum' notifications that
// surface through the existing notification bell (see mapNotification above).

export interface BackendForumCategory {
  id: string;
  slug: string;
  name_en: string;
  name_vi: string;
  description_en?: string | null;
  description_vi?: string | null;
  color: string;
  sort_order: number;
  is_active: boolean;
  topic_count: number;
}

export interface BackendForumComment {
  id: string;
  topic_id: string;
  parent_comment_id?: string | null;
  author_user_id?: string | null;
  author_name?: string | null;
  author_roles?: string[] | null;
  content: string;
  is_official: boolean;
  deleted: boolean;
  score: number;
  my_vote: number;
  created_at: string;
  updated_at: string;
  replies: BackendForumComment[];
}

export interface BackendForumTopic {
  id: string;
  category_id: string;
  category_slug?: string | null;
  category_name_en?: string | null;
  category_name_vi?: string | null;
  author_user_id?: string | null;
  author_name?: string | null;
  author_roles?: string[] | null;
  title: string;
  excerpt?: string | null;
  tags: string[];
  is_pinned: boolean;
  is_locked: boolean;
  deleted?: boolean;
  has_official_answer: boolean;
  view_count: number;
  comment_count: number;
  score: number;
  my_vote: number;
  created_at: string;
  updated_at: string;
  last_activity_at: string;
  content?: string | null;
  attachments?: ForumAttachment[] | null;
  official_comment_id?: string | null;
  comments?: BackendForumComment[] | null;
}

export interface BackendForumMember {
  id: string;
  full_name: string;
  preferred_name?: string | null;
  email?: string | null;
}

export interface BackendForumVote {
  target_type: ForumVoteTarget;
  target_id: string;
  score: number;
  my_vote: number;
}

export interface CreateForumTopicPayload {
  title: string;
  content: string;
  category_id?: string;
  category_slug?: string;
  tags?: string[];
  attachments?: ForumAttachment[];
  mentioned_user_ids?: string[];
}

export interface AddForumCommentPayload {
  content: string;
  parent_comment_id?: string;
  mentioned_user_ids?: string[];
}

export interface UpdateForumTopicPayload {
  title?: string;
  content?: string;
  category_id?: string;
  category_slug?: string;
  tags?: string[];
  attachments?: ForumAttachment[];
}

export interface UpdateForumCommentPayload {
  content?: string;
}

export interface ForumTopicNotificationPayload {
  title?: string;
  message?: string;
  priority?: Notification["priority"];
  target_scope?: "all" | "institute";
  institute_id?: string | null;
  publish?: boolean;
}

export interface ForumTopicFilters {
  category?: string;
  category_id?: string;
  sort?: ForumSort;
  q?: string;
  search?: string;
  status?: "active" | "archived" | "all";
}

function clampVote(value: number): ForumVoteValue {
  return value > 0 ? 1 : value < 0 ? -1 : 0;
}

function mapForumCategory(c: BackendForumCategory): ForumCategory {
  return {
    ...c,
    description_en: c.description_en ?? undefined,
    description_vi: c.description_vi ?? undefined,
  };
}

function mapForumMember(m: BackendForumMember): ForumMember {
  return {
    id: m.id,
    full_name: m.full_name,
    preferred_name: m.preferred_name ?? undefined,
    email: m.email ?? undefined,
  };
}

function mapForumComment(c: BackendForumComment): ForumComment {
  return {
    id: c.id,
    topic_id: c.topic_id,
    parent_comment_id: c.parent_comment_id ?? undefined,
    author_user_id: c.author_user_id ?? undefined,
    author_name: c.author_name ?? undefined,
    author_roles: c.author_roles ?? [],
    content: c.content,
    is_official: c.is_official,
    deleted: c.deleted,
    score: c.score,
    my_vote: clampVote(c.my_vote),
    created_at: c.created_at,
    updated_at: c.updated_at,
    replies: (c.replies ?? []).map(mapForumComment),
  };
}

function mapForumTopic(t: BackendForumTopic): ForumTopic {
  return {
    id: t.id,
    category_id: t.category_id,
    category_slug: t.category_slug ?? undefined,
    category_name_en: t.category_name_en ?? undefined,
    category_name_vi: t.category_name_vi ?? undefined,
    author_user_id: t.author_user_id ?? undefined,
    author_name: t.author_name ?? undefined,
    author_roles: t.author_roles ?? [],
    title: t.title,
    excerpt: t.excerpt ?? undefined,
    tags: t.tags ?? [],
    is_pinned: t.is_pinned,
    is_locked: t.is_locked,
    deleted: t.deleted ?? false,
    has_official_answer: t.has_official_answer,
    view_count: t.view_count,
    comment_count: t.comment_count,
    score: t.score,
    my_vote: clampVote(t.my_vote),
    created_at: t.created_at,
    updated_at: t.updated_at,
    last_activity_at: t.last_activity_at,
    content: t.content ?? undefined,
    attachments: t.attachments ?? undefined,
    official_comment_id: t.official_comment_id ?? undefined,
    comments: t.comments ? t.comments.map(mapForumComment) : undefined,
  };
}

function mapForumVote(v: BackendForumVote): ForumVoteResult {
  return {
    target_type: v.target_type,
    target_id: v.target_id,
    score: v.score,
    my_vote: clampVote(v.my_vote),
  };
}

export async function getForumCategories(): Promise<ForumCategory[]> {
  const rows = await getJSON<BackendForumCategory[]>("/api/forum/categories");
  return rows.map(mapForumCategory);
}

export async function getForumTopics(filters: ForumTopicFilters = {}): Promise<ForumTopic[]> {
  const params = new URLSearchParams();
  if (filters.category && filters.category !== "all") params.set("category", filters.category);
  if (filters.category_id) params.set("category_id", filters.category_id);
  if (filters.sort) params.set("sort", filters.sort);
  if (filters.q && filters.q.trim()) params.set("q", filters.q.trim());
  if (filters.search && filters.search.trim()) params.set("search", filters.search.trim());
  if (filters.status && filters.status !== "active") params.set("status", filters.status);
  const query = params.toString();
  const rows = await getJSON<BackendForumTopic[]>(`/api/forum/topics${query ? `?${query}` : ""}`);
  return rows.map(mapForumTopic);
}

export async function getForumTopic(topicId: string): Promise<ForumTopic> {
  return mapForumTopic(await getJSON<BackendForumTopic>(`/api/forum/topics/${topicId}`));
}

export async function getForumComments(topicId: string): Promise<ForumComment[]> {
  const rows = await getJSON<BackendForumComment[]>(`/api/forum/topics/${topicId}/comments`);
  return rows.map(mapForumComment);
}

export async function createForumTopic(payload: CreateForumTopicPayload): Promise<ForumTopic> {
  const row = await apiRequest<BackendForumTopic>("/api/forum/topics", {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify(payload),
  });
  return mapForumTopic(row);
}

export async function updateForumTopic(
  topicId: string,
  payload: UpdateForumTopicPayload
): Promise<ForumTopic> {
  const row = await apiRequest<BackendForumTopic>(`/api/forum/topics/${topicId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify(payload),
  });
  return mapForumTopic(row);
}

export async function deleteForumTopic(topicId: string): Promise<void> {
  await apiRequest(`/api/forum/topics/${topicId}`, {
    method: "DELETE",
    headers: { Accept: "application/json" },
  });
}

export async function addForumComment(
  topicId: string,
  payload: AddForumCommentPayload
): Promise<ForumComment> {
  const row = await apiRequest<BackendForumComment>(`/api/forum/topics/${topicId}/comments`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify(payload),
  });
  return mapForumComment(row);
}

export async function updateForumComment(
  commentId: string,
  payload: UpdateForumCommentPayload
): Promise<ForumComment> {
  const row = await apiRequest<BackendForumComment>(`/api/forum/comments/${commentId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify(payload),
  });
  return mapForumComment(row);
}

export async function deleteForumComment(commentId: string): Promise<void> {
  await apiRequest(`/api/forum/comments/${commentId}`, {
    method: "DELETE",
    headers: { Accept: "application/json" },
  });
}

export async function voteForumTopic(
  topicId: string,
  value: ForumVoteValue
): Promise<ForumVoteResult> {
  const row = await apiRequest<BackendForumVote>(`/api/forum/topics/${topicId}/vote`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify({ value }),
  });
  return mapForumVote(row);
}

export async function voteForumComment(
  commentId: string,
  value: ForumVoteValue
): Promise<ForumVoteResult> {
  const row = await apiRequest<BackendForumVote>(`/api/forum/comments/${commentId}/vote`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify({ value }),
  });
  return mapForumVote(row);
}

export async function reportForumContent(payload: {
  target_type: ForumVoteTarget;
  target_id: string;
  reason: string;
}): Promise<void> {
  await apiRequest(`/api/forum/reports`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function searchForumMembers(q: string): Promise<ForumMember[]> {
  if (!q.trim()) return [];
  const rows = await getJSON<BackendForumMember[]>(
    `/api/forum/members?q=${encodeURIComponent(q.trim())}`
  );
  return rows.map(mapForumMember);
}

export async function moderateForumTopic(
  topicId: string,
  patch: {
    is_pinned?: boolean;
    is_locked?: boolean;
    deleted?: boolean;
    official_comment_id?: string | null;
  }
): Promise<ForumTopic> {
  const row = await apiRequest<BackendForumTopic>(`/api/forum/topics/${topicId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify(patch),
  });
  return mapForumTopic(row);
}

export async function pinForumTopic(topicId: string, pinned: boolean): Promise<ForumTopic> {
  const action = pinned ? "pin" : "unpin";
  const row = await apiRequest<BackendForumTopic>(`/api/forum/topics/${topicId}/${action}`, {
    method: "POST",
    headers: { Accept: "application/json" },
  });
  return mapForumTopic(row);
}

export async function lockForumTopic(topicId: string, locked: boolean): Promise<ForumTopic> {
  const action = locked ? "lock" : "unlock";
  const row = await apiRequest<BackendForumTopic>(`/api/forum/topics/${topicId}/${action}`, {
    method: "POST",
    headers: { Accept: "application/json" },
  });
  return mapForumTopic(row);
}

export async function archiveForumTopic(topicId: string): Promise<ForumTopic> {
  const row = await apiRequest<BackendForumTopic>(`/api/forum/topics/${topicId}/archive`, {
    method: "POST",
    headers: { Accept: "application/json" },
  });
  return mapForumTopic(row);
}

export async function createForumTopicNotification(
  topicId: string,
  payload: ForumTopicNotificationPayload = {}
): Promise<Notification> {
  const row = await apiRequest<BackendAdminNotification>(
    `/api/forum/topics/${topicId}/notification`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(payload),
    }
  );
  return mapAdminNotification(row);
}

export async function moderateForumComment(
  commentId: string,
  patch: { is_official?: boolean; deleted?: boolean }
): Promise<ForumComment> {
  const row = await apiRequest<BackendForumComment>(`/api/forum/comments/${commentId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify(patch),
  });
  return mapForumComment(row);
}

export async function hideForumComment(commentId: string, hidden: boolean): Promise<ForumComment> {
  const action = hidden ? "hide" : "unhide";
  const row = await apiRequest<BackendForumComment>(`/api/forum/comments/${commentId}/${action}`, {
    method: "POST",
    headers: { Accept: "application/json" },
  });
  return mapForumComment(row);
}
