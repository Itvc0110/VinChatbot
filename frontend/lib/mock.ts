// Realistic demo data for the VinUni Student Copilot portal. This is the FALLBACK layer:
// api.ts uses real FastAPI endpoints where they exist (chat, sources, ingest) and falls
// back to these fixtures for the portal screens the Python backend does not yet serve.
//
// Everything here is plausible-but-fake. Replace each consumer in api.ts with a real
// fetch() once the matching endpoint ships — the shapes already match portalTypes.ts.

import type {
  AdminStats,
  AnalyticsOverview,
  ClassSession,
  Deadline,
  KnowledgeSource,
  StudentProfile,
  SupportTicket,
  TuitionStatus,
  UnansweredQuestion,
} from "./portalTypes";

// Anchored "now" for deterministic relative dates in the demo (matches PRD timeframe).
// Using a fixed base keeps "days left" badges stable across renders/builds.
const NOW = new Date("2026-06-18T08:00:00+07:00");

function daysFromNow(days: number, hour = 23, minute = 59): string {
  const d = new Date(NOW);
  d.setDate(d.getDate() + days);
  d.setHours(hour, minute, 0, 0);
  return d.toISOString();
}

export const MOCK_PROFILE: StudentProfile = {
  student_id: "V2024001",
  full_name: "Nguyễn Minh Anh",
  preferred_name: "Minh Anh",
  program: "BS Computer Science",
  college: "College of Engineering & Computer Science",
  year: 2,
  intake: "Fall 2024",
  email: "minh.anh.nguyen@vinuni.edu.vn",
  advisor: "Dr. Trần Quốc Bảo",
  gpa: 3.62,
  credits_earned: 48,
  credits_required: 120,
};

export const MOCK_SCHEDULE: ClassSession[] = [
  {
    id: "cs-301",
    course_code: "COMP3010",
    course_title: "Algorithms & Data Structures",
    day: "Thu",
    start: "09:00",
    end: "10:30",
    room: "G-201",
    building: "Gallery Building",
    instructor: "Dr. Lê Thị Hương",
  },
  {
    id: "cs-302",
    course_code: "COMP3025",
    course_title: "Database Systems",
    day: "Thu",
    start: "11:00",
    end: "12:30",
    room: "G-114",
    building: "Gallery Building",
    instructor: "Dr. Phạm Văn Đức",
  },
  {
    id: "cs-303",
    course_code: "MATH2040",
    course_title: "Probability & Statistics",
    day: "Thu",
    start: "14:00",
    end: "15:30",
    room: "C-305",
    building: "Cohort Building",
    instructor: "Dr. Nguyễn Hải Yến",
  },
  {
    id: "cs-304",
    course_code: "COMP3010",
    course_title: "Algorithms & Data Structures (Lab)",
    day: "Fri",
    start: "09:00",
    end: "11:00",
    room: "Lab-2",
    building: "Gallery Building",
    instructor: "TA Đỗ Anh Khoa",
  },
  {
    id: "cs-305",
    course_code: "WRIT2010",
    course_title: "Technical Writing",
    day: "Fri",
    start: "13:00",
    end: "14:30",
    room: "C-210",
    building: "Cohort Building",
    instructor: "Dr. Sarah Mitchell",
  },
];

export const MOCK_DEADLINES: Deadline[] = [
  {
    id: "d1",
    title: "Problem Set 6 — Dynamic Programming",
    course_code: "COMP3010",
    kind: "assignment",
    due_at: daysFromNow(2),
    source_title: "COMP3010 Syllabus (Spring 2026)",
    source_url: "https://vinuni.edu.vn/academics/comp3010-syllabus",
  },
  {
    id: "d2",
    title: "Course Drop deadline (no W on transcript)",
    kind: "registration",
    due_at: daysFromNow(4),
    source_title: "Academic Calendar 2025–2026",
    source_url: "https://vinuni.edu.vn/academic-calendar",
  },
  {
    id: "d3",
    title: "Database Systems — Midterm Project",
    course_code: "COMP3025",
    kind: "exam",
    due_at: daysFromNow(6),
    source_title: "COMP3025 Syllabus (Spring 2026)",
    source_url: "https://vinuni.edu.vn/academics/comp3025-syllabus",
  },
  {
    id: "d4",
    title: "Tuition installment 2 due",
    kind: "tuition",
    due_at: daysFromNow(12),
    source_title: "Student Financial Services — Payment Schedule",
    source_url: "https://vinuni.edu.vn/tuition-payment-schedule",
  },
  {
    id: "d5",
    title: "Technical Writing — Draft submission",
    course_code: "WRIT2010",
    kind: "assignment",
    due_at: daysFromNow(9),
  },
];

export const MOCK_TUITION: TuitionStatus = {
  currency: "VND",
  total_charged_vnd: 320_000_000,
  total_paid_vnd: 240_000_000,
  balance_vnd: 80_000_000,
  next_due_at: daysFromNow(12),
  next_due_amount_vnd: 40_000_000,
  items: [
    {
      id: "t1",
      label: "Spring 2026 — Installment 1",
      term: "Spring 2026",
      amount_vnd: 160_000_000,
      status: "paid",
      paid_at: daysFromNow(-40),
    },
    {
      id: "t2",
      label: "Spring 2026 — Installment 2",
      term: "Spring 2026",
      amount_vnd: 40_000_000,
      status: "due",
      due_at: daysFromNow(12),
    },
    {
      id: "t3",
      label: "Spring 2026 — Installment 3",
      term: "Spring 2026",
      amount_vnd: 40_000_000,
      status: "upcoming",
      due_at: daysFromNow(45),
    },
    {
      id: "t4",
      label: "Student Services & Health Insurance Fee",
      term: "Spring 2026",
      amount_vnd: 80_000_000,
      status: "paid",
      paid_at: daysFromNow(-40),
    },
  ],
};

export const MOCK_TICKETS: SupportTicket[] = [
  {
    id: "TKT-2041",
    subject: "Scholarship renewal criteria for Year 3",
    body: "I couldn't find a verified answer on whether my merit scholarship auto-renews if my GPA stays above 3.5.",
    department: "Office of Financial Aid",
    status: "in_progress",
    priority: "high",
    created_at: daysFromNow(-2, 10, 12),
    updated_at: daysFromNow(-1, 16, 30),
    origin_question: "Does my merit scholarship renew automatically for Year 3?",
  },
  {
    id: "TKT-2038",
    subject: "Exchange semester credit transfer",
    body: "Question forwarded from the assistant: how do credits from a partner university map back to my degree audit?",
    department: "Office of the Registrar",
    status: "answered",
    priority: "normal",
    created_at: daysFromNow(-9, 9, 5),
    updated_at: daysFromNow(-5, 11, 20),
    origin_question: "How do exchange-semester credits transfer back to my CS degree?",
    resolution:
      "Credits transfer as electives once the Registrar receives the partner transcript; pre-approval via the Study Abroad form is required.",
  },
  {
    id: "TKT-2025",
    subject: "Locker assignment for Gallery Building",
    body: "Requesting a locker near the CS labs for the Spring term.",
    department: "Student Affairs",
    status: "closed",
    priority: "low",
    created_at: daysFromNow(-21, 14, 0),
    updated_at: daysFromNow(-18, 15, 0),
    resolution: "Locker G2-117 assigned for Spring 2026.",
  },
];

export const MOCK_SOURCES: KnowledgeSource[] = [
  {
    id: "src-1",
    name: "Academic Calendar 2025–2026",
    url: "https://vinuni.edu.vn/academic-calendar",
    type: "url",
    category: "Academic",
    status: "indexed",
    chunk_count: 42,
    last_crawled_at: daysFromNow(-1, 3, 0),
    last_indexed_at: daysFromNow(-1, 3, 12),
    is_official: true,
  },
  {
    id: "src-2",
    name: "Undergraduate Student Handbook 2025",
    url: "https://vinuni.edu.vn/handbook-2025.pdf",
    type: "pdf",
    category: "Academic",
    status: "indexed",
    chunk_count: 318,
    last_crawled_at: daysFromNow(-3, 2, 0),
    last_indexed_at: daysFromNow(-3, 2, 40),
    is_official: true,
  },
  {
    id: "src-3",
    name: "Tuition & Payment Schedule",
    url: "https://vinuni.edu.vn/tuition-payment-schedule",
    type: "url",
    category: "Tuition",
    status: "indexed",
    chunk_count: 27,
    last_crawled_at: daysFromNow(0, 3, 0),
    last_indexed_at: daysFromNow(0, 3, 8),
    is_official: true,
  },
  {
    id: "src-4",
    name: "Course Withdrawal & Leave of Absence Policy",
    url: "https://vinuni.edu.vn/policies/withdrawal.pdf",
    type: "pdf",
    category: "Academic",
    status: "indexed",
    chunk_count: 16,
    last_crawled_at: daysFromNow(-2, 4, 0),
    last_indexed_at: daysFromNow(-2, 4, 18),
    is_official: true,
  },
  {
    id: "src-5",
    name: "Student Events Calendar (Spring 2026)",
    url: "https://vinuni.edu.vn/events",
    type: "url",
    category: "Events",
    status: "crawling",
    chunk_count: 0,
    last_crawled_at: daysFromNow(0, 3, 0),
    is_official: true,
  },
  {
    id: "src-6",
    name: "Health & Counseling Services",
    url: "https://vinuni.edu.vn/student-services/health",
    type: "url",
    category: "Student Services",
    status: "failed",
    chunk_count: 0,
    last_crawled_at: daysFromNow(0, 2, 30),
    is_official: true,
  },
  {
    id: "src-7",
    name: "Legacy FAQ export (2023)",
    url: "https://drive.vinuni.edu.vn/legacy-faq",
    type: "database",
    category: "Student Services",
    status: "disabled",
    chunk_count: 88,
    last_crawled_at: daysFromNow(-120, 1, 0),
    last_indexed_at: daysFromNow(-120, 1, 30),
    is_official: false,
  },
];

export const MOCK_UNANSWERED: UnansweredQuestion[] = [
  {
    id: "q-501",
    question: "Can I defer my tuition installment if my scholarship disbursement is late?",
    reason: "no_verified_source",
    student_context: "Year 2 · CECS · merit scholarship holder",
    suggested_department: "Student Financial Services",
    priority: "high",
    status: "new",
    created_at: daysFromNow(0, 7, 40),
    asked_count: 6,
  },
  {
    id: "q-502",
    question: "What is the exact GPA cutoff for the Dean's List this semester?",
    reason: "low_confidence",
    student_context: "Year 3 · College of Business",
    suggested_department: "Office of the Registrar",
    priority: "medium",
    status: "new",
    created_at: daysFromNow(-1, 13, 12),
    asked_count: 3,
  },
  {
    id: "q-503",
    question: "Is there a shuttle bus schedule between the dorms and the main campus on weekends?",
    reason: "no_verified_source",
    student_context: "Year 1 · resident student",
    suggested_department: "Student Affairs",
    priority: "medium",
    status: "in_review",
    created_at: daysFromNow(-2, 9, 0),
    asked_count: 11,
  },
  {
    id: "q-504",
    question: "How do I appeal a final grade in a core engineering course?",
    reason: "ambiguous",
    student_context: "Year 2 · CECS",
    suggested_department: "Office of the Registrar",
    priority: "low",
    status: "forwarded",
    created_at: daysFromNow(-4, 10, 30),
    asked_count: 2,
  },
];

export const MOCK_ADMIN_STATS: AdminStats = {
  indexed_documents: 1284,
  sources_crawled_today: 9,
  failed_crawls: 1,
  unanswered_questions: 4,
  verified_answer_rate: 0.91,
  low_confidence_responses: 12,
};

export const MOCK_ANALYTICS: AnalyticsOverview = {
  questions_per_day: [
    { label: "Mon", total: 142, verified: 129, unanswered: 5 },
    { label: "Tue", total: 168, verified: 151, unanswered: 7 },
    { label: "Wed", total: 155, verified: 142, unanswered: 4 },
    { label: "Thu", total: 191, verified: 173, unanswered: 9 },
    { label: "Fri", total: 176, verified: 160, unanswered: 6 },
    { label: "Sat", total: 88, verified: 80, unanswered: 3 },
    { label: "Sun", total: 71, verified: 65, unanswered: 2 },
  ],
  top_topics: [
    { topic: "Tuition & payments", count: 248 },
    { topic: "Deadlines & calendar", count: 213 },
    { topic: "Course registration", count: 187 },
    { topic: "Student services", count: 121 },
    { topic: "Events", count: 76 },
  ],
  avg_confidence: 0.83,
  verified_rate: 0.91,
  total_questions: 991,
};

// Small helper so api.ts can simulate network latency uniformly for the mock path.
export function delay<T>(value: T, ms = 280): Promise<T> {
  return new Promise((resolve) => setTimeout(() => resolve(value), ms));
}
