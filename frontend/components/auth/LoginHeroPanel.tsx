"use client";

import { usePortal } from "@/lib/portalI18n";
import {
  IconCap,
  IconBell,
  IconCalendar,
  IconTicket,
  IconChat,
} from "@/components/shell/icons";
import { LogoCopilot } from "@/components/shell/Logos";

// Presentational LEFT panel for the split-screen login: a general, non-personalized intro to
// the VinUni Student Copilot. NO user-specific data (the visitor isn't authenticated yet) — only
// static, marketing-style copy describing what the product does. Bilingual via the active UI
// language (same local-STR pattern used elsewhere in the shell). Contains no auth logic.
const STR = {
  en: {
    label: "About VinUni Student Copilot",
    brandName: "Student Copilot",
    brandSub: "VinUni Academic Assistant",
    title: "Welcome to VinUni Student Copilot",
    subtitle:
      "Your personalized academic companion for schedules, announcements, support requests, and smart guidance from Vinnie — in one secure student portal.",
    features: [
      { title: "Academic guidance", desc: "Curriculum progress, course eligibility, and what to do next." },
      { title: "Campus announcements", desc: "Deadlines, scholarships, exams, and important updates." },
      { title: "Smart schedule tools", desc: "Classes, meetings, and academic events at a glance." },
      { title: "Student support", desc: "Create and track support tickets with a smoother flow." },
    ],
    highlight: "Scholarships, events, and academic deadlines — all in one place.",
    floats: ["Campus updates", "Academic support", "Ask Vinnie anytime"],
  },
  vi: {
    label: "Giới thiệu VinUni Student Copilot",
    brandName: "Student Copilot",
    brandSub: "Trợ lý học tập VinUni",
    title: "Chào mừng đến với VinUni Student Copilot",
    subtitle:
      "Người bạn đồng hành học tập cho lịch học, thông báo, yêu cầu hỗ trợ và hướng dẫn thông minh từ Vinnie — trong một cổng sinh viên an toàn.",
    features: [
      { title: "Hướng dẫn học vụ", desc: "Tiến độ chương trình, điều kiện môn học và bước tiếp theo." },
      { title: "Thông báo toàn trường", desc: "Hạn chót, học bổng, lịch thi và cập nhật quan trọng." },
      { title: "Công cụ lịch thông minh", desc: "Lớp học, lịch hẹn và sự kiện học vụ trong tầm tay." },
      { title: "Hỗ trợ sinh viên", desc: "Tạo và theo dõi phiếu hỗ trợ mượt mà hơn." },
    ],
    highlight: "Học bổng, sự kiện và hạn chót học vụ — tất cả ở một nơi.",
    floats: ["Cập nhật toàn trường", "Hỗ trợ học vụ", "Hỏi Vinnie mọi lúc"],
  },
} as const;

const FEATURE_ICONS = [
  <IconCap size={18} key="cap" />,
  <IconBell size={18} key="bell" />,
  <IconCalendar size={18} key="cal" />,
  <IconTicket size={18} key="ticket" />,
];
const FLOAT_ICONS = [
  <IconBell size={14} key="f-bell" />,
  <IconCap size={14} key="f-cap" />,
  <IconChat size={14} key="f-chat" />,
];

export function LoginHeroPanel() {
  const { lang } = usePortal();
  const s = STR[lang];

  return (
    <aside className="login-hero-panel" aria-label={s.label}>
      {/* Decorative ambient background (gradient + drifting glow blobs). */}
      <span className="login-hero-bg" aria-hidden="true" />

      <div className="login-hero-content">
        <div className="login-brand-block">
          <span className="login-brand-badge brand-logo-tile" aria-hidden="true">
            <LogoCopilot size={42} />
          </span>
          <div>
            <div className="login-brand-name">{s.brandName}</div>
            <div className="login-brand-sub">{s.brandSub}</div>
          </div>
        </div>

        <h2 className="login-hero-title">{s.title}</h2>
        <p className="login-hero-sub">{s.subtitle}</p>

        <div className="login-feature-grid">
          {s.features.map((f, i) => (
            <div className="login-feature-card" key={f.title}>
              <span className="login-feature-icon" aria-hidden="true">
                {FEATURE_ICONS[i]}
              </span>
              <div className="login-feature-text">
                <div className="login-feature-title">{f.title}</div>
                <div className="login-feature-desc">{f.desc}</div>
              </div>
            </div>
          ))}
        </div>

        <div className="login-highlight-card">
          <span className="login-highlight-icon" aria-hidden="true">
            <IconBell size={18} />
          </span>
          <p className="login-highlight-text">{s.highlight}</p>
        </div>
      </div>

      {/* Decorative, generic floating chips — non-personalized, hidden from assistive tech. */}
      {s.floats.map((label, i) => (
        <span className={`login-floating-card login-floating-card--${i + 1}`} key={label} aria-hidden="true">
          <span className="login-float-icon">{FLOAT_ICONS[i]}</span>
          {label}
        </span>
      ))}
    </aside>
  );
}
