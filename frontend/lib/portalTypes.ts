// Domain types for the VinUni Student Copilot portal (student + admin).
//
// These mirror the *expected* backend contracts. Where a real FastAPI endpoint already
// exists (chat, sources, ingest) the api.ts layer maps to it; everything else is served
// by the mock adapter in mock.ts until the backend grows the endpoint. Each section of
// api.ts documents the precise contract with a TODO so the swap is mechanical.

export type ChatMode = "general" | "personal";

// ---- Student ----------------------------------------------------------------

export interface StudentProfile {
  student_id: string;
  full_name: string;
  preferred_name: string;
  program: string; // e.g. "BS Computer Science"
  college: string; // e.g. "College of Engineering & Computer Science"
  year: number; // academic year of study
  intake: string; // e.g. "Fall 2024"
  email: string;
  advisor: string;
  gpa: number;
  credits_earned: number;
  credits_required: number;
}

export type ScheduleDay =
  | "Mon"
  | "Tue"
  | "Wed"
  | "Thu"
  | "Fri"
  | "Sat"
  | "Sun";

export interface ClassSession {
  id: string;
  course_code: string;
  course_title: string;
  day: ScheduleDay;
  start: string; // "09:00"
  end: string; // "10:30"
  room: string;
  building: string;
  instructor: string;
}

export type DeadlineKind =
  | "assignment"
  | "exam"
  | "registration"
  | "tuition"
  | "administrative";

export interface Deadline {
  id: string;
  title: string;
  course_code?: string;
  kind: DeadlineKind;
  due_at: string; // ISO datetime
  source_title?: string; // official source backing this deadline
  source_url?: string;
}

export type TuitionItemStatus = "paid" | "due" | "overdue" | "upcoming";

export interface TuitionLineItem {
  id: string;
  label: string;
  term: string;
  amount_vnd: number;
  status: TuitionItemStatus;
  due_at?: string;
  paid_at?: string;
}

export interface TuitionStatus {
  currency: "VND";
  total_charged_vnd: number;
  total_paid_vnd: number;
  balance_vnd: number;
  next_due_at?: string;
  next_due_amount_vnd?: number;
  items: TuitionLineItem[];
}

// PLAN22.6 ticket lifecycle. `draft` is the pre-submit state Vinnie prepares and the
// student reviews; it is NEVER visible to admin. A ticket only becomes admin-visible once
// the student explicitly submits it (status `submitted` + confirmed_by_user === true).
export type TicketStatus =
  | "draft"
  | "submitted"
  | "open"
  | "in_review"
  | "in_progress"
  | "waiting_for_student"
  | "waiting_on_student"
  | "resolved"
  | "closed";
export type TicketPriority = "low" | "medium" | "high" | "urgent";
export type TicketCategory =
  | "academic"
  | "schedule"
  | "student_services"
  | "technical"
  | "other";

// One entry in a ticket's conversation thread (student question / admin reply / system note).
export interface TicketMessage {
  id: string;
  author: "student" | "admin" | "system";
  body: string;
  created_at: string;
  sender_user_id?: string;
  sender_email?: string;
  sender_full_name?: string;
}

export interface SupportTicket {
  id: string;
  subject: string;
  body: string;
  // PLAN22.6: `department` doubles as the "assigned office".
  department: string;
  category: TicketCategory;
  status: TicketStatus;
  priority: TicketPriority;
  created_at: string;
  updated_at: string;
  // PLAN22.6 privacy/routing fields ---------------------------------------------------
  // True ONLY once the student clicks "Send to Admin". Admin views filter on this so a
  // draft (confirmed_by_user === false) can never be seen by staff.
  confirmed_by_user: boolean;
  // True when Vinnie prepared the draft from a chat answer (vs. the manual request form).
  created_by_ai: boolean;
  // The student's opt-in choice to attach a short chat-context summary.
  include_chat_context: boolean;
  // Links a submitted ticket back to the chat conversation it came from.
  source_conversation_id?: string;
  // The short relevant summary actually attached — present ONLY when include_chat_context
  // was true at submit time. Never the full transcript, never profile/GPA/tuition.
  included_context?: string;
  // ISO timestamp set when the student submits the ticket to admin.
  submitted_at?: string;
  // Owner of the ticket (admin attribution).
  student_id?: string;
  // Set when the ticket was forwarded from a chat answer the bot couldn't verify.
  origin_question?: string;
  // PLAN23.6.01 SLA + assignment (all optional → a real backend omitting them degrades
  // gracefully: no SLA icon, no admin meta line).
  due_at?: string; // ISO first-response/resolution deadline → drives the overdue / due-soon icon
  sla_hours?: number; // optional SLA window (hours from created_at)
  assignee?: string; // assigned admin/staff display name (admin board/card/drawer)
  student_name?: string; // ticket owner display name (admin board/card); student_id already exists
  resolution?: string;
  // Conversation history (student question + admin responses), if any.
  messages?: TicketMessage[];
  status_history?: TicketStatusHistory[];
  // A source/citation attached to the ticket by an admin, if any.
  source_title?: string;
  source_url?: string;
  // Frontend-only visibility flags. The backend has no permanent-delete endpoint, so
  // "archive" and "delete" are modelled as state the UI filters on (see lib/api.ts).
  archived?: boolean;
  deleted?: boolean;
}

export interface TicketStatusHistory {
  id: string;
  old_status?: TicketStatus;
  new_status: TicketStatus;
  changed_by?: string;
  changed_by_email?: string;
  changed_by_full_name?: string;
  changed_at: string;
}

// How the ticket board orders tickets within each status column (PLAN23.6.01 filters panel).
export type TicketSort = "updated_desc" | "created_desc" | "priority_desc" | "sla_asc";

// SLA health of a ticket relative to its due_at — drives the warning icon + color.
export type SlaState = "ok" | "due_soon" | "overdue";

// Frontend-only editable buffer the Review Ticket drawer binds to. It is held in
// ChatProvider React state and NEVER persisted (no DB, no localStorage) until the student
// explicitly submits — at which point api.submitTicket turns it into a SupportTicket.
export interface TicketDraft {
  id: string;
  subject: string;
  body: string;
  department: string;
  category: TicketCategory;
  priority: TicketPriority;
  include_chat_context: boolean;
  source_conversation_id?: string;
  origin_question?: string;
  // A short, reviewable summary (question + answer) shown in the drawer and attached only
  // if the student keeps "include chat context" ticked. Built by shortSummary() in chat.tsx.
  context_preview: string;
  // True once Vinnie's suggestion populated this draft (Part B). Drives the "AI-drafted" disclaimer
  // and is persisted on the created ticket (created_by_ai) when the student confirms + sends.
  created_by_ai?: boolean;
}

// ---- Notifications ----------------------------------------------------------

export type NotificationType =
  | "academic"
  | "schedule"
  | "deadline"
  | "event"
  | "student_services"
  | "system"
  | "forum";

export type NotificationPriority = "low" | "medium" | "high" | "urgent";
export type NotificationStatus = "draft" | "scheduled" | "published" | "archived";

export interface Notification {
  id: string;
  // `type` doubles as the PLAN22.6 "category" (academic|schedule|deadline|event|…).
  type: NotificationType;
  title: string;
  message: string;
  // Optional per-language variants (admin authoring). Student reads already arrive
  // resolved to the active language in `title`/`message`.
  title_vi?: string;
  title_en?: string;
  message_vi?: string;
  message_en?: string;
  created_at: string; // ISO datetime
  read: boolean;
  important: boolean;
  archived?: boolean;
  // Optional related official source or an in-app action.
  source_title?: string;
  source_url?: string;
  action_label?: string;
  action_href?: string;
  // PLAN22.6 admin-authored fields (all optional so existing rows keep compiling) -------
  priority?: NotificationPriority;
  target_audience?: string[];
  deadline?: string; // ISO — drives time-aware suggested-question phase
  event_date?: string; // ISO
  start_date?: string; // ISO
  end_date?: string; // ISO
  status?: NotificationStatus;
  created_by?: string;
  updated_at?: string;
  // Admin-approved suggested questions generated for this notification.
  suggested_questions?: SuggestedQuestion[];
  // Forum mention/reply notifications carry the discussion they point at, so the UI can
  // build an in-app deep link to the topic.
  forum_topic_id?: string;
  forum_comment_id?: string;
}

// Which "deadline phase" a notification is in relative to today — drives whether Vinnie
// suggests discovery, action, or recovery questions. See lib/suggestedQuestions.ts.
export type SuggestedQuestionPhase = "early" | "near_deadline" | "overdue" | "active";

// A timely question Vinnie can suggest, generated (rule-based for MVP) from a notification
// and approved by an admin before it reaches students.
export interface SuggestedQuestion {
  id: string;
  notification_id: string;
  source_type?: string;
  source_id?: string;
  question_text: string;
  category: NotificationType;
  trigger_phase: SuggestedQuestionPhase;
  score: number;
  created_by_ai: boolean;
  approved_by_admin: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

// ---- Calendar ---------------------------------------------------------------

export type CalendarEventType =
  | "class"
  | "deadline"
  | "exam"
  | "event"
  | "reminder";

export interface CalendarEvent {
  id: string;
  type: CalendarEventType;
  title: string;
  start: string; // ISO datetime
  end?: string; // ISO datetime
  all_day?: boolean;
  location?: string;
  course?: string; // course code / title
  category?: string; // free-text category label
  description?: string;
  source_title?: string;
  source_url?: string;
}

// ---- Admin ------------------------------------------------------------------

export type SourceType = "pdf" | "url" | "database" | "docx";
export type SourceStatus = "indexed" | "crawling" | "failed" | "disabled" | "pending";
export type SourceCategory =
  | "Academic"
  | "Tuition"
  | "Events"
  | "Student Services"
  | "Schedule";

export interface KnowledgeSource {
  id: string;
  name: string;
  url: string;
  type: SourceType;
  category: SourceCategory;
  status: SourceStatus;
  chunk_count: number;
  last_crawled_at?: string;
  last_indexed_at?: string;
  is_official: boolean;
}

export type QuestionFailureReason =
  | "no_verified_source"
  | "low_confidence"
  | "out_of_scope"
  | "ambiguous";

export type QuestionPriority = "low" | "medium" | "high";
export type QuestionStatus = "new" | "in_review" | "forwarded" | "resolved";

export interface UnansweredQuestion {
  id: string;
  question: string;
  reason: QuestionFailureReason;
  student_context: string; // anonymized
  suggested_department: string;
  priority: QuestionPriority;
  status: QuestionStatus;
  created_at: string;
  asked_count: number; // how many students hit the same gap
}

export interface ResolveQuestionPayload {
  action: "official_answer" | "forward" | "attach_source" | "mark_resolved";
  answer?: string;
  department?: string;
  source_url?: string;
  add_to_knowledge_base?: boolean;
}

export interface AdminStats {
  indexed_documents: number;
  sources_crawled_today: number;
  failed_crawls: number;
  unanswered_questions: number;
  verified_answer_rate: number; // 0..1
  low_confidence_responses: number;
}

export interface AnalyticsPoint {
  label: string; // e.g. day or week label
  total: number;
  verified: number;
  unanswered: number;
}

export interface AnalyticsOverview {
  questions_per_day: AnalyticsPoint[];
  top_topics: { topic: string; count: number }[];
  avg_confidence: number;
  verified_rate: number;
  total_questions: number;
}

export interface AdminDashboardScope {
  kind: "global" | "institute" | "none" | string;
  institute_id?: string | null;
  institute_code?: string | null;
}

export interface AdminDashboardOverview {
  total_users: number;
  total_students: number;
  total_institutes: number;
  total_tickets: number;
  open_tickets: number;
  need_admin_response: number;
  urgent_tickets: number;
  upcoming_deadlines: number;
  upcoming_schedules: number;
  upcoming_events: number;
  published_notifications: number;
}

export interface AdminDashboardCount {
  key: string;
  count: number;
}

export interface AdminDashboardInstituteCount {
  institute_id: string;
  institute_code: string;
  institute_name_en: string;
  institute_name_vi: string;
  student_count: number;
}

export interface AdminDashboardRecentTicket {
  id: string;
  subject: string;
  status: TicketStatus | string;
  priority: TicketPriority | string;
  student_id?: string | null;
  student_name?: string | null;
  institute_id?: string | null;
  institute_code?: string | null;
  due_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface AdminDashboardUpcomingItem {
  id: string;
  item_type: "deadline" | "schedule" | "event" | "notification" | string;
  title: string;
  starts_at: string;
  ends_at?: string | null;
  course_code?: string | null;
  institute_id?: string | null;
  institute_code?: string | null;
  source_title?: string | null;
  source_url?: string | null;
}

export interface AdminDashboard {
  scope: AdminDashboardScope;
  overview: AdminDashboardOverview;
  ticket_counts_by_status: AdminDashboardCount[];
  ticket_counts_by_priority: AdminDashboardCount[];
  student_counts_by_institute: AdminDashboardInstituteCount[];
  recent_tickets: AdminDashboardRecentTicket[];
  upcoming_items: AdminDashboardUpcomingItem[];
}

// ---- Forum / Discussion Hub -------------------------------------------------
// Public peer discussion, deliberately separate from private support tickets.

export type ForumSort = "active" | "pinned" | "newest_activity" | "most_commented" | "new" | "top";
export type ForumVoteValue = -1 | 0 | 1;
export type ForumVoteTarget = "topic" | "comment";

export interface ForumCategory {
  id: string;
  slug: string;
  name_en: string;
  name_vi: string;
  description_en?: string;
  description_vi?: string;
  color: string;
  sort_order: number;
  is_active: boolean;
  topic_count: number;
}

export interface ForumAttachment {
  url: string;
  label?: string;
}

// A person who can be @mentioned (used by the mention autocomplete).
export interface ForumMember {
  id: string;
  full_name: string;
  preferred_name?: string;
  email?: string;
}

export interface ForumComment {
  id: string;
  topic_id: string;
  parent_comment_id?: string;
  author_user_id?: string;
  author_name?: string;
  author_roles: string[];
  content: string;
  is_official: boolean;
  deleted: boolean;
  score: number;
  my_vote: ForumVoteValue;
  created_at: string;
  updated_at: string;
  replies: ForumComment[];
}

export interface ForumTopic {
  id: string;
  category_id: string;
  category_slug?: string;
  category_name_en?: string;
  category_name_vi?: string;
  author_user_id?: string;
  author_name?: string;
  author_roles: string[];
  title: string;
  excerpt?: string;
  tags: string[];
  is_pinned: boolean;
  is_locked: boolean;
  deleted: boolean;
  has_official_answer: boolean;
  view_count: number;
  comment_count: number;
  score: number;
  my_vote: ForumVoteValue;
  created_at: string;
  updated_at: string;
  last_activity_at: string;
  // Detail-only fields (absent on list summaries).
  content?: string;
  attachments?: ForumAttachment[];
  official_comment_id?: string;
  comments?: ForumComment[];
}

export interface ForumVoteResult {
  target_type: ForumVoteTarget;
  target_id: string;
  score: number;
  my_vote: ForumVoteValue;
}

// A generic async-state envelope the views use for loading/error/empty/success.
export type AsyncState<T> =
  | { status: "loading" }
  | { status: "error"; error: string }
  | { status: "success"; data: T };
