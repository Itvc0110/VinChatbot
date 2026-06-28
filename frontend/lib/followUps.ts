// Contextual, bilingual follow-up suggestions shown under a settled answer. Pure and
// frontend-only (mirrors the style of suggestedQuestions.ts). The suggestions adapt to the
// CURRENT turn — the latest user question + the latest assistant answer — instead of a single
// hard-coded set, so a question about a professor never gets event/deadline prompts.
//
// Phase-2-swappable: if the backend ever returns follow-up suggestions on the ChatResponse
// (e.g. a `suggested_follow_ups` field), followUpsFor() renders those verbatim without
// touching callers — see postChatStream's future onSuggestions hook.

import type { ChatResponse } from "./types";
import type { Lang } from "./i18n";

export interface FollowUpInput {
  userQuestion: string;
  assistantAnswer: string;
  language: Lang;
  // Optional grounding signals used only to detect a low-confidence / weak-sources turn.
  confidence?: number;
  citationCount?: number;
  needsReview?: boolean;
}

// Topic detectors (EN + VI), case-insensitive. Each looks across the combined question+answer
// text so a topic is caught whether the student named it or Vinnie did.
const RE_PERSON =
  /\b(professor|prof\.?|lecturer|teacher|dean|faculty|staff|instructor|advis(?:o|e)r|dr\.?|ph\.?\s?d)\b|giáo sư|giảng viên|giảng dạy|trưởng khoa|cán bộ|nhân viên|\bthầy\b|\bcô\b|là ai\b/i;
const RE_TUITION =
  /\b(tuition|fees?|payment|invoice|scholarship|financial aid|refund|installment|bursar)\b|học phí|lệ phí|thanh toán|học bổng|hỗ trợ tài chính|hoàn phí|trả góp/i;
const RE_SCHEDULE =
  /\b(schedule|timetable|class(?:es)?|exams?|midterm|final|room|lecture|session)\b|lịch học|lịch thi|thời khóa biểu|kỳ thi|tiết học|phòng học|buổi học/i;
const RE_POLICY =
  /\b(policy|policies|regulation|procedure|rule|document|forms?|guideline|requirement|deadline|withdraw|leave of absence)\b|chính sách|quy định|quy chế|quy trình|tài liệu|biểu mẫu|mẫu đơn|hướng dẫn|hạn chót|rút môn|bảo lưu/i;

// Per-topic templates, bilingual so suggestions always match the selected UI language.
const T = {
  person: {
    en: [
      "View their official faculty profile",
      "Which department are they in?",
      "How can I contact this person or their office?",
    ],
    vi: [
      "Xem hồ sơ giảng viên chính thức",
      "Họ thuộc khoa/phòng ban nào?",
      "Làm sao để liên hệ người này hoặc văn phòng phụ trách?",
    ],
  },
  tuition: {
    en: [
      "What's the payment deadline?",
      "Which office handles tuition and fees?",
      "Prepare a support ticket about this",
    ],
    vi: [
      "Hạn thanh toán là khi nào?",
      "Phòng ban nào phụ trách học phí và lệ phí?",
      "Soạn phiếu hỗ trợ về việc này",
    ],
  },
  schedule: {
    en: [
      "When is my next class?",
      "Where does it take place?",
      "Add this to my calendar",
    ],
    vi: [
      "Lớp học tiếp theo của tôi khi nào?",
      "Diễn ra ở đâu?",
      "Thêm việc này vào lịch của tôi",
    ],
  },
  policy: {
    en: [
      "Are there any exceptions?",
      "Prepare a support ticket",
      "Which office should I contact?",
    ],
    vi: [
      "Có ngoại lệ nào không?",
      "Soạn phiếu hỗ trợ",
      "Tôi nên liên hệ phòng ban nào?",
    ],
  },
  // Low confidence / no usable sources → steer to a human channel.
  lowConfidence: {
    en: ["Which office should I contact?", "Prepare a support ticket for staff"],
    vi: ["Tôi nên liên hệ phòng ban nào?", "Soạn phiếu hỗ trợ để cán bộ xử lý"],
  },
  // Always-useful deepeners, used to top up to at least three.
  fallback: {
    en: [
      "Can you explain more?",
      "Which office should I contact?",
      "Prepare a support ticket",
    ],
    vi: [
      "Giải thích thêm giúp tôi?",
      "Tôi nên liên hệ phòng ban nào?",
      "Soạn phiếu hỗ trợ",
    ],
  },
} as const;

// Derive 3–5 relevant suggestions from the current turn using safe deterministic rules.
export function generateFollowUpSuggestions(input: FollowUpInput): string[] {
  const { userQuestion, assistantAnswer, language } = input;
  const text = `${assistantAnswer}\n${userQuestion}`;
  const weak =
    (typeof input.confidence === "number" && input.confidence < 0.5) ||
    input.citationCount === 0 ||
    input.needsReview === true;

  const out: string[] = [];
  const push = (arr: readonly string[]) => arr.forEach((q) => out.push(q));

  // A weak-grounding turn leads with the human-channel prompts.
  if (weak) push(T.lowConfidence[language]);

  // Topic-specific suggestions, in detection order (most specific first).
  if (RE_PERSON.test(text)) push(T.person[language]);
  if (RE_TUITION.test(text)) push(T.tuition[language]);
  if (RE_SCHEDULE.test(text)) push(T.schedule[language]);
  if (RE_POLICY.test(text)) push(T.policy[language]);

  // Top up with generic deepeners so there are always at least three.
  push(T.fallback[language]);

  // De-dupe (preserving order) and keep 3–5.
  const unique = Array.from(new Set(out.map((q) => q.trim())));
  return unique.slice(0, 5);
}

// Render-time entry point used by the FollowUpSuggestions component. Prefers backend-provided
// suggestions when present, otherwise derives them client-side from the current turn.
export function followUpsFor(
  question: string,
  response: ChatResponse,
  lang: Lang
): string[] {
  const fromBackend = backendSuggestions(response);
  if (fromBackend.length) return removeSourceOpenSuggestions(fromBackend).slice(0, 5);

  return removeSourceOpenSuggestions(
    generateFollowUpSuggestions({
      userQuestion: question,
      assistantAnswer: response.answer,
      language: lang,
      confidence: response.confidence,
      citationCount: response.citations.length,
      needsReview: response.needs_human_review,
    })
  );
}

function removeSourceOpenSuggestions(items: string[]): string[] {
  return items.filter((q) => {
    const text = q.trim();
    return !/\b(open|view|read)\b.*\b(source|policy)\b|\bsource\b|mở\s+nguồn|nguồn\s+chính\s+thức|chính\s+sách\s+chính\s+thức/i.test(
      text
    );
  });
}

// Forward-compatible read of optional follow-up metadata the backend may add later. Accepts a
// few likely field names; ignores anything that isn't a non-empty array of strings.
function backendSuggestions(response: ChatResponse): string[] {
  const r = response as unknown as Record<string, unknown>;
  const candidate =
    r.suggested_follow_ups ?? r.follow_ups ?? r.suggestions ?? r.followups;
  if (!Array.isArray(candidate)) return [];
  return candidate.filter((q): q is string => typeof q === "string" && q.trim().length > 0);
}
