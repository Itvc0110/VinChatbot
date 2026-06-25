"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { useTheme } from "@/lib/theme";
import { useI18n, type Lang } from "@/lib/i18n";
import { initials } from "@/lib/format";
import {
  IconGrid,
  IconChat,
  IconCalendar,
  IconTicket,
  IconCap,
} from "./icons";
import { NotificationBell } from "@/components/notifications/NotificationBell";

// Academic Horizon student chrome: a fixed horizontal top navigation bar (DESIGN.md §11.2).
// Links use the Stitch screen names over the EXISTING routes (see ROUTES.md) — no route renames.
// The active link gets a 2px brand-red underline. The language + theme toggles and sign-out that
// previously lived in the shared TopBar are carried here, so retiring the sidebar shell for
// students loses no functionality.

interface NavItem {
  href: string;
  label: string;
  icon: React.ReactNode;
}

const STR = {
  en: {
    primary: "Primary",
    language: "Language",
    notifications: "Notifications",
    signOut: "Sign out",
    dashboard: "Dashboard",
    vinnieAi: "Vinnie AI",
    calendar: "Calendar",
    events: "Events",
    tickets: "Tickets",
  },
  vi: {
    primary: "Điều hướng chính",
    language: "Ngôn ngữ",
    notifications: "Thông báo",
    signOut: "Đăng xuất",
    dashboard: "Bảng điều khiển",
    vinnieAi: "Vinnie AI",
    calendar: "Lịch",
    events: "Sự kiện",
    tickets: "Yêu cầu hỗ trợ",
  },
} as const;

function isActive(pathname: string, href: string): boolean {
  return pathname === href || pathname.startsWith(href + "/");
}

function SunIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      width="17"
      height="17"
      aria-hidden="true"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
    >
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M19.1 4.9l-1.4 1.4M6.3 17.7l-1.4 1.4" />
    </svg>
  );
}

function MoonIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      width="17"
      height="17"
      aria-hidden="true"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z" />
    </svg>
  );
}

function LogoutIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      width="16"
      height="16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9" />
    </svg>
  );
}

export function StudentTopNav() {
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const { theme, toggle } = useTheme();
  const { lang, setLang, t } = useI18n();
  const s = STR[lang];
  const nextTheme = theme === "dark" ? t.themeLight : t.themeDark;

  const STUDENT_NAV: NavItem[] = [
    { href: "/student/dashboard", label: s.dashboard, icon: <IconGrid /> },
    { href: "/student/chat", label: s.vinnieAi, icon: <IconChat /> },
    { href: "/student/schedule", label: s.calendar, icon: <IconCalendar /> },
    { href: "/student/events", label: s.events, icon: <IconCalendar /> },
    { href: "/student/support", label: s.tickets, icon: <IconTicket /> },
  ];

  return (
    <header className="ah-topnav">
      <Link href="/student/dashboard" className="ah-topnav-brand">
        <span className="ah-topnav-badge">
          <IconCap size={18} />
        </span>
        VinUni
      </Link>

      <nav aria-label={s.primary}>
        <ul className="ah-topnav-links">
          {STUDENT_NAV.map((item) => {
            const active = isActive(pathname, item.href);
            return (
              <li key={item.href}>
                <Link
                  href={item.href}
                  className={`ah-topnav-link ${active ? "active" : ""}`}
                  aria-current={active ? "page" : undefined}
                >
                  <span aria-hidden>{item.icon}</span>
                  {item.label}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>

      <div className="ah-topnav-actions">
        <div className="seg" role="group" aria-label={s.language}>
          {(["en", "vi"] as Lang[]).map((l) => (
            <button
              key={l}
              className={`seg-opt ${lang === l ? "active" : ""}`}
              aria-pressed={lang === l}
              onClick={() => setLang(l)}
            >
              {t.langName[l]}
            </button>
          ))}
        </div>
        <button
          className="icon-btn"
          onClick={toggle}
          aria-label={nextTheme}
          title={nextTheme}
        >
          {theme === "dark" ? <SunIcon /> : <MoonIcon />}
        </button>
        <NotificationBell ariaLabel={s.notifications} />
        <span className="ah-profile" title={user?.name}>
          <span className="ah-avatar">{user ? initials(user.name) : "?"}</span>
          {user && <span className="ah-profile-name">{user.name}</span>}
        </span>
        <button
          className="ah-iconbtn"
          onClick={logout}
          aria-label={s.signOut}
          title={s.signOut}
        >
          <LogoutIcon />
        </button>
      </div>
    </header>
  );
}
