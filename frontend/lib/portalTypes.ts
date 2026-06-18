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

export type TicketStatus = "open" | "in_progress" | "answered" | "closed";
export type TicketPriority = "low" | "normal" | "high";

export interface SupportTicket {
  id: string;
  subject: string;
  body: string;
  department: string;
  status: TicketStatus;
  priority: TicketPriority;
  created_at: string;
  updated_at: string;
  // Set when the ticket was forwarded from a chat answer the bot couldn't verify.
  origin_question?: string;
  resolution?: string;
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

// A generic async-state envelope the views use for loading/error/empty/success.
export type AsyncState<T> =
  | { status: "loading" }
  | { status: "error"; error: string }
  | { status: "success"; data: T };
