"use client";

import { createContext, useContext, useEffect, useState } from "react";

export type Lang = "en" | "vi";

const LANG_STORAGE_KEY = "vinchatbot-lang";

// UI chrome strings only. The *answer* language is auto-detected by the backend from the
// user's message text (guardrails.answer_language) — this toggle does not change that.
export interface Strings {
  assistantLabel: string;
  statusReady: string;
  login: string;
  langName: { en: string; vi: string };
  themeLight: string;
  themeDark: string;
  retrieving: string;

  welcomeGreeting: string;
  welcomeIntro: string;
  categories: { icon: string; label: string }[];
  welcomeHint: string;

  paneConversation: string;
  paneSources: string;
  sourcesLabel: string;

  placeholder: string;
  send: string;
  stop: string;
  tooLong: (n: number) => string;
  quickPrompts: string[];

  // panel states
  emptyHint: string;
  cancelledNote: string;
  errorNote: string;
  waiting: string;
  sourceCount: (n: number) => string;
  conversationalNote: string;
  refusalTitle: string;
  refusalNoCite: string;
  refusalUseChannel: string;
  degradedTitle: string;
  degradedBody: string;
  degradedCheck: string;
  relatedUnverified: (n: number) => string;
  unverifiedNote: string;
  unverifiedTag: string;
  showPassage: string;
  untitledSource: string;

  // state chip
  chip: { grounded: string; conversational: string; refusal: string; degraded: string };
  // confidence
  confHigh: string;
  confMedium: string;
  confLow: string;
  confTitle: (v: string, band: string) => string;
  reviewFlagged: string;
  reviewFlaggedTitle: string;
  why: string;

  // controls
  flag: string;
  flagSendFail: string;
  flagPlaceholder: string;
  flagSubmit: string;
  flagSending: string;
  cancel: string;
  reported: string;
  edit: string;
  resend: string;
  cancelledShort: string;

  // refusal reasons
  reasonOutOfScope: string;
  reasonInjection: string;
  reasonRestricted: string;
  reasonAbuse: string;
  reasonDefault: string;
}

const en: Strings = {
  assistantLabel: "AI Academic Assistant",
  statusReady: "Ready to help",
  login: "Log in",
  langName: { en: "EN", vi: "VI" },
  themeLight: "Switch to light mode",
  themeDark: "Switch to dark mode",
  retrieving: "Searching official sources…",

  welcomeGreeting: "Hi! I'm VinChatbot",
  welcomeIntro:
    "Ask me anything about VinUni academics and student services. I answer from official sources, cite them, and tell you honestly when I can't.",
  categories: [
    { icon: "📅", label: "Academic calendar & deadlines" },
    { icon: "📋", label: "Policies & procedures" },
    { icon: "💳", label: "Tuition & fees" },
    { icon: "🎓", label: "Student services & campus life" },
  ],
  welcomeHint: "Try one of these to start:",

  paneConversation: "Conversation",
  paneSources: "Sources & grounding",
  sourcesLabel: "Sources:",

  placeholder: "Ask about academics, deadlines, fees, services… (EN or VI)",
  send: "Send",
  stop: "Stop",
  tooLong: (n) => `Message is ${n} characters — keep it under 4000.`,
  quickPrompts: [
    "When is the Course Drop deadline this term?",
    "How do I apply for a Leave of Absence?",
    "What are the tuition payment deadlines?",
  ],

  emptyHint:
    "Ask a question and the official sources behind each answer appear here. VinChatbot only answers from VinUni sources — and tells you when it can't.",
  cancelledNote: "Request cancelled. Ask again when you're ready.",
  errorNote: "No answer to ground. The last request didn't complete. Retry it from the chat.",
  waiting: "Waiting for the answer…",
  sourceCount: (n) => `${n} source${n === 1 ? "" : "s"} · latest answer`,
  conversationalNote:
    "No sources needed. That was a conversational reply, not a factual claim — so there's nothing to cite.",
  refusalTitle: "Not answered from sources",
  refusalNoCite:
    "No citation is shown because there is no official source to back an answer here.",
  refusalUseChannel: "For an authoritative answer, use the official channel:",
  degradedTitle: "Couldn't ground an answer",
  degradedBody:
    "VinChatbot didn't find official VinUni text strong enough to support a confident answer, so it declined rather than guess. Flagged for review.",
  degradedCheck: "Check the official source directly:",
  relatedUnverified: (n) => `Related — unverified (${n})`,
  unverifiedNote:
    "Retrieved but not confirmed to support an answer. Treat as leads, not facts.",
  unverifiedTag: "unverified",
  showPassage: "Show the full passage",
  untitledSource: "Untitled source",

  chip: {
    grounded: "Grounded in sources",
    conversational: "Conversational",
    refusal: "Refused — see sources",
    degraded: "No grounded answer",
  },
  confHigh: "High",
  confMedium: "Medium",
  confLow: "Low",
  confTitle: (v, band) => `Answer confidence: ${v} (${band})`,
  reviewFlagged: "Flagged for review",
  reviewFlaggedTitle:
    "Answer is grounded in sources, but the backend flagged it for human review (e.g. faithfulness not fully verified).",
  why: "Why this answer",

  flag: "⚑ Flag answer",
  flagSendFail: " · couldn't send, try again",
  flagPlaceholder: "What was wrong? (e.g. ungrounded, wrong deadline, missing source)",
  flagSubmit: "Submit report",
  flagSending: "Sending…",
  cancel: "Cancel",
  reported: "✓ Reported",
  edit: "✎ Edit",
  resend: "Resend",
  cancelledShort: "Request cancelled.",

  reasonOutOfScope: "Outside VinUni academic/service scope",
  reasonInjection: "Blocked a prompt-injection attempt",
  reasonRestricted: "Restricted / private data request",
  reasonAbuse: "Abusive language",
  reasonDefault: "Not answerable from official sources",
};

const vi: Strings = {
  assistantLabel: "Trợ lý học vụ AI",
  statusReady: "Sẵn sàng hỗ trợ",
  login: "Đăng nhập",
  langName: { en: "EN", vi: "VI" },
  themeLight: "Chuyển sang nền sáng",
  themeDark: "Chuyển sang nền tối",
  retrieving: "Đang tìm trong nguồn chính thức…",

  welcomeGreeting: "Xin chào! Mình là VinChatbot",
  welcomeIntro:
    "Hỏi mình bất cứ điều gì về học vụ và dịch vụ sinh viên VinUni. Mình trả lời dựa trên nguồn chính thức, có trích dẫn, và nói thẳng khi không chắc.",
  categories: [
    { icon: "📅", label: "Lịch học & hạn chót" },
    { icon: "📋", label: "Chính sách & quy trình" },
    { icon: "💳", label: "Học phí & lệ phí" },
    { icon: "🎓", label: "Dịch vụ sinh viên & đời sống" },
  ],
  welcomeHint: "Thử một trong các câu sau:",

  paneConversation: "Hội thoại",
  paneSources: "Nguồn & căn cứ",
  sourcesLabel: "Nguồn:",

  placeholder: "Hỏi về học vụ, hạn chót, học phí, dịch vụ… (Anh hoặc Việt)",
  send: "Gửi",
  stop: "Dừng",
  tooLong: (n) => `Tin nhắn dài ${n} ký tự — giữ dưới 4000.`,
  quickPrompts: [
    "Hạn chót rút môn học kỳ này là khi nào?",
    "Làm sao để xin bảo lưu (Leave of Absence)?",
    "Các hạn nộp học phí là khi nào?",
  ],

  emptyHint:
    "Đặt câu hỏi và các nguồn chính thức cho mỗi câu trả lời sẽ hiện ở đây. VinChatbot chỉ trả lời từ nguồn VinUni — và sẽ báo khi không thể.",
  cancelledNote: "Đã hủy yêu cầu. Hỏi lại khi bạn sẵn sàng.",
  errorNote: "Không có câu trả lời để đối chiếu. Yêu cầu trước chưa hoàn tất. Thử lại từ khung chat.",
  waiting: "Đang chờ câu trả lời…",
  sourceCount: (n) => `${n} nguồn · câu trả lời mới nhất`,
  conversationalNote:
    "Không cần nguồn. Đây là câu trả lời giao tiếp, không phải khẳng định dữ kiện — nên không có gì để trích dẫn.",
  refusalTitle: "Không trả lời từ nguồn",
  refusalNoCite:
    "Không hiển thị trích dẫn vì không có nguồn chính thức nào để làm căn cứ ở đây.",
  refusalUseChannel: "Để có câu trả lời chính thức, hãy dùng kênh chính thức:",
  degradedTitle: "Chưa thể đối chiếu câu trả lời",
  degradedBody:
    "VinChatbot không tìm thấy tài liệu VinUni chính thức đủ mạnh để trả lời chắc chắn, nên đã từ chối thay vì đoán. Đã đánh dấu để rà soát.",
  degradedCheck: "Kiểm tra trực tiếp nguồn chính thức:",
  relatedUnverified: (n) => `Liên quan — chưa xác minh (${n})`,
  unverifiedNote:
    "Được truy xuất nhưng chưa xác nhận là căn cứ cho câu trả lời. Xem như gợi ý, không phải dữ kiện.",
  unverifiedTag: "chưa xác minh",
  showPassage: "Xem toàn bộ đoạn trích",
  untitledSource: "Nguồn chưa có tiêu đề",

  chip: {
    grounded: "Có căn cứ nguồn",
    conversational: "Giao tiếp",
    refusal: "Từ chối — xem nguồn",
    degraded: "Không có căn cứ",
  },
  confHigh: "Cao",
  confMedium: "Trung bình",
  confLow: "Thấp",
  confTitle: (v, band) => `Độ tin cậy: ${v} (${band})`,
  reviewFlagged: "Đã đánh dấu rà soát",
  reviewFlaggedTitle:
    "Câu trả lời có căn cứ nguồn, nhưng hệ thống đã đánh dấu để người rà soát (vd: chưa xác minh đầy đủ độ trung thực).",
  why: "Vì sao có câu trả lời này",

  flag: "⚑ Báo lỗi câu trả lời",
  flagSendFail: " · gửi không được, thử lại",
  flagPlaceholder: "Sai ở đâu? (vd: thiếu căn cứ, sai hạn chót, thiếu nguồn)",
  flagSubmit: "Gửi báo cáo",
  flagSending: "Đang gửi…",
  cancel: "Hủy",
  reported: "✓ Đã báo",
  edit: "✎ Sửa",
  resend: "Gửi lại",
  cancelledShort: "Đã hủy yêu cầu.",

  reasonOutOfScope: "Ngoài phạm vi học vụ/dịch vụ VinUni",
  reasonInjection: "Đã chặn ý đồ tiêm nhiễm lệnh (prompt injection)",
  reasonRestricted: "Yêu cầu dữ liệu riêng tư/hạn chế",
  reasonAbuse: "Ngôn từ thiếu tôn trọng",
  reasonDefault: "Không thể trả lời từ nguồn chính thức",
};

export const STRINGS: Record<Lang, Strings> = { en, vi };

const I18nContext = createContext<{
  lang: Lang;
  t: Strings;
  setLang: (l: Lang) => void;
}>({
  lang: "en",
  t: en,
  setLang: () => {},
});

// App-wide language provider. Self-managed (persists to localStorage) so the toggle in
// the top bar switches UI chrome across every portal screen, not just one page.
export function LanguageProvider({
  initialLang = "en",
  children,
}: {
  initialLang?: Lang;
  children: React.ReactNode;
}) {
  const [lang, setLangState] = useState<Lang>(initialLang);

  useEffect(() => {
    try {
      const saved = localStorage.getItem(LANG_STORAGE_KEY);
      if (saved === "en" || saved === "vi") setLangState(saved);
    } catch {
      /* storage blocked — keep default */
    }
  }, []);

  const setLang = (l: Lang) => {
    setLangState(l);
    try {
      localStorage.setItem(LANG_STORAGE_KEY, l);
    } catch {
      /* ignore */
    }
  };

  return (
    <I18nContext.Provider value={{ lang, t: STRINGS[lang], setLang }}>
      {children}
    </I18nContext.Provider>
  );
}

export function useI18n() {
  return useContext(I18nContext);
}
