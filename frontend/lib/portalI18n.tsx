"use client";

// Portal chrome strings (nav, page titles, common labels) kept separate from the chat
// i18n dictionary so the existing chat strings stay untouched. Detailed screen body
// copy stays English; nav + key CTAs are bilingual to match the EN/VI toggle.

import { useI18n, type Lang } from "./i18n";

export interface PortalStrings {
  productName: string;
  productTagline: string;
  studentPortal: string;
  adminPortal: string;

  nav: {
    dashboard: string;
    chat: string;
    schedule: string;
    tuition: string;
    tickets: string;
    adminDashboard: string;
    sources: string;
    upload: string;
    questions: string;
    analytics: string;
    logs: string;
  };

  // role + auth chrome
  roleStudent: string;
  roleAdmin: string;
  signOut: string;
  adminConsole: string;
  adminConsoleSub: string;
  adminWarning: string;
  studentChatNote: string;

  login: {
    title: string;
    subtitle: string;
    continueStudent: string;
    continueAdmin: string;
    sso: string;
    securityNote: string;
    demoStudent: string;
    demoAdmin: string;
    or: string;
  };

  access: {
    title: string;
    message: string;
    backToDashboard: string;
    signOut: string;
  };

  // common
  viewAll: string;
  openSource: string;
  loading: string;
  empty: string;
  retry: string;
  errorGeneric: string;
  daysLeft: (n: number) => string;
  dueToday: string;
  overdue: string;

  // chat mode toggle
  modeGeneral: string;
  modePersonal: string;
  modeHint: string;

  // answer actions
  actViewSource: string;
  actAddCalendar: string;
  actSetReminder: string;
  actForward: string;
  actReport: string;

  // dashboard
  greetingMorning: string;
  todaySchedule: string;
  upcomingDeadlines: string;
  tuitionStatus: string;
  suggestedQuestions: string;
  askAnything: string;
  askCta: string;
}

const en: PortalStrings = {
  productName: "Student Copilot",
  productTagline: "VinUni · 24/7 AI student support",
  studentPortal: "Student",
  adminPortal: "Admin",
  nav: {
    dashboard: "Dashboard",
    chat: "Ask AI",
    schedule: "My Schedule",
    tuition: "Tuition & Fees",
    tickets: "Support Tickets",
    adminDashboard: "Admin Dashboard",
    sources: "Knowledge Sources",
    upload: "Upload Document",
    questions: "Unanswered Questions",
    analytics: "Analytics",
    logs: "System Logs",
  },
  roleStudent: "Student",
  roleAdmin: "Admin",
  signOut: "Sign out",
  adminConsole: "Admin Console",
  adminConsoleSub: "Manage official sources, unresolved questions, and chatbot quality.",
  adminWarning:
    "Only authorized staff can upload sources, approve answers, and review unresolved student questions.",
  studentChatNote:
    "You are viewing this as a Student. Personalized answers use your own schedule, tuition status, and deadlines.",
  login: {
    title: "Sign in to VinUni Student Copilot",
    subtitle: "24/7 verified student support powered by official VinUni sources",
    continueStudent: "Continue as Student",
    continueAdmin: "Continue as Admin",
    sso: "Continue with VinUni SSO",
    securityNote: "Your access is based on your VinUni role and permissions.",
    demoStudent: "Student demo account",
    demoAdmin: "Admin demo account",
    or: "or",
  },
  access: {
    title: "Access denied",
    message: "You do not have permission to view this area.",
    backToDashboard: "Back to my dashboard",
    signOut: "Sign out",
  },
  viewAll: "View all",
  openSource: "Open source",
  loading: "Loading…",
  empty: "Nothing here yet.",
  retry: "Retry",
  errorGeneric: "Couldn't load this. Try again.",
  daysLeft: (n) => (n === 1 ? "1 day left" : `${n} days left`),
  dueToday: "Due today",
  overdue: "Overdue",
  modeGeneral: "General VinUni Info",
  modePersonal: "My Student Info",
  modeHint: "Personalized answers use your program, schedule, deadlines and tuition.",
  actViewSource: "View source",
  actAddCalendar: "Add to calendar",
  actSetReminder: "Set reminder",
  actForward: "Forward to admin",
  actReport: "Report issue",
  greetingMorning: "Welcome back",
  todaySchedule: "Today's schedule",
  upcomingDeadlines: "Upcoming deadlines",
  tuitionStatus: "Tuition status",
  suggestedQuestions: "Suggested questions",
  askAnything: "Ask about deadlines, tuition, policies, services…",
  askCta: "Ask AI",
};

const vi: PortalStrings = {
  productName: "Student Copilot",
  productTagline: "VinUni · Hỗ trợ sinh viên AI 24/7",
  studentPortal: "Sinh viên",
  adminPortal: "Quản trị",
  nav: {
    dashboard: "Tổng quan",
    chat: "Hỏi AI",
    schedule: "Lịch học",
    tuition: "Học phí",
    tickets: "Yêu cầu hỗ trợ",
    adminDashboard: "Bảng quản trị",
    sources: "Nguồn tri thức",
    upload: "Tải tài liệu",
    questions: "Câu hỏi chưa trả lời",
    analytics: "Phân tích",
    logs: "Nhật ký hệ thống",
  },
  roleStudent: "Sinh viên",
  roleAdmin: "Quản trị",
  signOut: "Đăng xuất",
  adminConsole: "Admin Console",
  adminConsoleSub: "Quản lý nguồn chính thức, câu hỏi chưa giải quyết và chất lượng chatbot.",
  adminWarning:
    "Chỉ nhân viên được ủy quyền mới có thể tải nguồn, duyệt câu trả lời và xem xét câu hỏi chưa giải quyết của sinh viên.",
  studentChatNote:
    "Bạn đang xem với vai trò Sinh viên. Câu trả lời cá nhân hóa dùng lịch học, tình trạng học phí và hạn chót của bạn.",
  login: {
    title: "Đăng nhập VinUni Student Copilot",
    subtitle: "Hỗ trợ sinh viên 24/7 với câu trả lời đã xác minh từ nguồn chính thức VinUni",
    continueStudent: "Tiếp tục với vai trò Sinh viên",
    continueAdmin: "Tiếp tục với vai trò Quản trị",
    sso: "Tiếp tục với VinUni SSO",
    securityNote: "Quyền truy cập dựa trên vai trò và quyền hạn VinUni của bạn.",
    demoStudent: "Tài khoản demo Sinh viên",
    demoAdmin: "Tài khoản demo Quản trị",
    or: "hoặc",
  },
  access: {
    title: "Truy cập bị từ chối",
    message: "Bạn không có quyền xem khu vực này.",
    backToDashboard: "Về trang của tôi",
    signOut: "Đăng xuất",
  },
  viewAll: "Xem tất cả",
  openSource: "Mở nguồn",
  loading: "Đang tải…",
  empty: "Chưa có gì ở đây.",
  retry: "Thử lại",
  errorGeneric: "Không tải được. Thử lại nhé.",
  daysLeft: (n) => (n === 1 ? "còn 1 ngày" : `còn ${n} ngày`),
  dueToday: "Hạn hôm nay",
  overdue: "Quá hạn",
  modeGeneral: "Thông tin chung VinUni",
  modePersonal: "Thông tin của tôi",
  modeHint: "Câu trả lời cá nhân hóa dùng chương trình, lịch học, hạn chót và học phí của bạn.",
  actViewSource: "Xem nguồn",
  actAddCalendar: "Thêm vào lịch",
  actSetReminder: "Đặt nhắc nhở",
  actForward: "Chuyển cho quản trị",
  actReport: "Báo lỗi",
  greetingMorning: "Chào mừng trở lại",
  todaySchedule: "Lịch học hôm nay",
  upcomingDeadlines: "Hạn chót sắp tới",
  tuitionStatus: "Tình trạng học phí",
  suggestedQuestions: "Câu hỏi gợi ý",
  askAnything: "Hỏi về hạn chót, học phí, chính sách, dịch vụ…",
  askCta: "Hỏi AI",
};

export const PORTAL_STRINGS: Record<Lang, PortalStrings> = { en, vi };

export function usePortal(): { p: PortalStrings; lang: Lang } {
  const { lang } = useI18n();
  return { p: PORTAL_STRINGS[lang], lang };
}
