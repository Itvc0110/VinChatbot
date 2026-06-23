// Notification-to-Question engine (PLAN22.6) — rule-based for the MVP.
//
// Maps a notification's category (its `type`) + its deadline/event date relative to "now"
// into a `trigger_phase`, then emits a ranked list of template questions for that phase.
// Pure, framework-free, and unit-testable. Phase 2 can swap `generate()` for an AI call
// without touching any caller (everything goes through lib/api.ts).

import type { Lang } from "./i18n";
import type {
  Notification,
  NotificationType,
  SuggestedQuestion,
  SuggestedQuestionPhase,
} from "./portalTypes";

const DAY_MS = 24 * 60 * 60 * 1000;
// A deadline is "near" once it is within this many days; "early" before that.
const NEAR_WINDOW_DAYS = 7;

// How strongly each phase is preferred when ranking for the current moment. Questions whose
// phase matches the notification's current phase float to the top.
const PHASE_WEIGHT: Record<SuggestedQuestionPhase, number> = {
  near_deadline: 3,
  overdue: 3,
  active: 2,
  early: 1,
};

type PhaseTemplates = Partial<Record<SuggestedQuestionPhase, string[]>>;
type CategoryTemplates = Record<NotificationType, PhaseTemplates>;

// Template questions keyed by language → category → phase. Discovery questions for "early",
// action questions for "near_deadline", recovery questions for "overdue", and general
// questions for date-less notifications ("active"). Bilingual so suggestions always match
// the selected UI language (PLAN22.6.2 §5).
const TEMPLATES: Record<Lang, CategoryTemplates> = {
  en: {
    deadline: {
      early: [
        "What is this deadline about?",
        "Am I affected by this deadline?",
        "What do I need to prepare for it?",
      ],
      near_deadline: [
        "How do I drop a course before the deadline?",
        "Will this put a W on my transcript?",
        "Who do I contact if I have an issue before the deadline?",
      ],
      overdue: [
        "Can I still submit after the deadline?",
        "Who do I contact now that the deadline has passed?",
        "What should I do if I missed this deadline?",
      ],
      active: ["What is this deadline about?", "What are the requirements?"],
    },
    academic: {
      early: [
        "What does this academic update mean for me?",
        "Which of my courses does this affect?",
      ],
      near_deadline: [
        "What action do I need to take for this academic update?",
        "How do I respond before the deadline?",
      ],
      overdue: [
        "What should I do if I missed this academic update?",
        "Who do I contact about this academic issue?",
      ],
      active: [
        "Can you explain this academic update?",
        "How does this affect my degree progress?",
      ],
    },
    schedule: {
      near_deadline: [
        "What changed in my schedule?",
        "Where is my class now?",
        "When does this take effect?",
      ],
      active: [
        "What changed in my schedule?",
        "When is my next class?",
        "Where is my class located?",
      ],
    },
    event: {
      early: ["What is this event about?", "Do I need to register for this event?"],
      near_deadline: [
        "Which companies are attending this event?",
        "Do I need to register for this event?",
        "Where and when is this event?",
      ],
      overdue: ["Did I miss this event?", "Will this event be held again?"],
      active: [
        "Which companies are attending this event?",
        "Do I need to register for this event?",
        "What should I bring?",
      ],
    },
    student_services: {
      active: [
        "How do I access this service?",
        "Where do I go for this?",
        "Who do I contact about this?",
      ],
    },
    system: {
      active: ["What does this system notice mean for me?", "Will this affect my access?"],
    },
  },
  vi: {
    deadline: {
      early: [
        "Hạn này là về việc gì?",
        "Hạn này có ảnh hưởng đến tôi không?",
        "Tôi cần chuẩn bị những gì?",
      ],
      near_deadline: [
        "Làm sao để rút học phần trước hạn?",
        "Rút học phần có bị ghi W trên bảng điểm không?",
        "Tôi liên hệ ai nếu gặp vấn đề trước hạn?",
      ],
      overdue: [
        "Tôi có thể nộp sau hạn không?",
        "Tôi liên hệ ai khi đã quá hạn?",
        "Tôi nên làm gì nếu lỡ hạn này?",
      ],
      active: ["Hạn này là về việc gì?", "Yêu cầu gồm những gì?"],
    },
    academic: {
      early: [
        "Cập nhật học vụ này nghĩa là gì với tôi?",
        "Việc này ảnh hưởng đến học phần nào của tôi?",
      ],
      near_deadline: [
        "Tôi cần làm gì cho cập nhật học vụ này?",
        "Tôi phản hồi trước hạn bằng cách nào?",
      ],
      overdue: [
        "Tôi nên làm gì nếu đã lỡ cập nhật học vụ này?",
        "Tôi liên hệ ai về vấn đề học vụ này?",
      ],
      active: [
        "Giải thích giúp tôi cập nhật học vụ này?",
        "Việc này ảnh hưởng đến tiến độ học của tôi thế nào?",
      ],
    },
    schedule: {
      near_deadline: [
        "Lịch của tôi thay đổi gì?",
        "Lớp của tôi giờ ở đâu?",
        "Thay đổi này áp dụng từ khi nào?",
      ],
      active: [
        "Lịch của tôi thay đổi gì?",
        "Lớp tiếp theo của tôi là khi nào?",
        "Lớp của tôi ở phòng nào?",
      ],
    },
    event: {
      early: ["Sự kiện này là về việc gì?", "Tôi có cần đăng ký sự kiện này không?"],
      near_deadline: [
        "Có những công ty nào tham dự sự kiện này?",
        "Có cần đăng ký trước cho sự kiện này không?",
        "Sự kiện diễn ra ở đâu và khi nào?",
      ],
      overdue: ["Tôi có lỡ sự kiện này không?", "Sự kiện này có tổ chức lại không?"],
      active: [
        "Có những công ty nào tham dự sự kiện này?",
        "Có cần đăng ký trước cho sự kiện này không?",
        "Tôi nên mang theo gì?",
      ],
    },
    student_services: {
      active: [
        "Tôi sử dụng dịch vụ này bằng cách nào?",
        "Tôi đến đâu để làm việc này?",
        "Tôi liên hệ ai về việc này?",
      ],
    },
    system: {
      active: ["Thông báo hệ thống này nghĩa là gì với tôi?", "Việc này có ảnh hưởng đến truy cập của tôi không?"],
    },
  },
};

// Fallback questions for any (category, phase) the template table doesn't cover.
const GENERIC: Record<Lang, Record<SuggestedQuestionPhase, string[]>> = {
  en: {
    early: ["What is this about?", "Does this apply to me?"],
    near_deadline: ["What do I need to do?", "How do I do this in time?"],
    overdue: ["What should I do now?", "Who do I contact?"],
    active: ["Can you tell me more about this?"],
  },
  vi: {
    early: ["Việc này là về gì?", "Việc này có áp dụng cho tôi không?"],
    near_deadline: ["Tôi cần làm gì?", "Làm sao để kịp hạn?"],
    overdue: ["Bây giờ tôi nên làm gì?", "Tôi liên hệ ai?"],
    active: ["Cho tôi biết thêm về việc này?"],
  },
};

// The reference date a notification carries: prefer an explicit deadline, else event_date.
function referenceDate(n: Notification): Date | null {
  const iso = n.deadline ?? n.event_date ?? null;
  if (!iso) return null;
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? null : d;
}

// Compute the time-aware phase for a notification relative to `now` (default: runtime now).
// No reference date → "active" (general, time-independent suggestions).
export function phaseFor(n: Notification, now: Date = new Date()): SuggestedQuestionPhase {
  const ref = referenceDate(n);
  if (!ref) return "active";
  const diffDays = (ref.getTime() - now.getTime()) / DAY_MS;
  if (diffDays < 0) return "overdue";
  if (diffDays <= NEAR_WINDOW_DAYS) return "near_deadline";
  return "early";
}

// Build candidate questions for a notification at its current phase, in `lang`. Returns
// unsaved SuggestedQuestion objects (created_by_ai: true, approved_by_admin: false) for an
// admin to review/edit/approve. `now` is injectable for deterministic tests.
export function generate(
  n: Notification,
  now: Date = new Date(),
  lang: Lang = "en"
): SuggestedQuestion[] {
  const phase = phaseFor(n, now);
  const byCat = TEMPLATES[lang][n.type] ?? {};
  const texts = byCat[phase] ?? GENERIC[lang][phase];
  const stamp = now.toISOString();
  return texts.map((question_text, i) => ({
    id: `sq-${n.id}-${phase}-${i}`,
    notification_id: n.id,
    question_text,
    category: n.type,
    trigger_phase: phase,
    // Higher first: 0.9, 0.8, 0.7, … so the most relevant template ranks first.
    score: Math.max(0.4, 0.9 - i * 0.1),
    created_by_ai: true,
    approved_by_admin: false,
    is_active: false,
    created_at: stamp,
    updated_at: stamp,
  }));
}

// Rank approved+active questions for display to a student. Questions whose stored phase
// matches their notification's CURRENT phase are preferred (keeps it time-aware even on
// already-approved questions), then by score. `notifById` lets us recompute the live phase.
export function rankForStudent(
  questions: SuggestedQuestion[],
  notifById: Map<string, Notification>,
  now: Date = new Date()
): SuggestedQuestion[] {
  const currentPhase = (q: SuggestedQuestion): SuggestedQuestionPhase | null => {
    const n = notifById.get(q.notification_id);
    return n ? phaseFor(n, now) : null;
  };
  return [...questions]
    .map((q) => {
      const matches = currentPhase(q) === q.trigger_phase;
      return { q, weight: (matches ? 10 : 0) + PHASE_WEIGHT[q.trigger_phase] + q.score };
    })
    .sort((a, b) => b.weight - a.weight)
    .map((x) => x.q);
}
