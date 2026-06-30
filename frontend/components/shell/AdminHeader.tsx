"use client";

import { useEffect, useRef, useState } from "react";
import { useAuth } from "@/lib/auth";
import { useTheme } from "@/lib/theme";
import { useI18n, type Lang } from "@/lib/i18n";
import { initials } from "@/lib/format";
import { IconCog } from "./icons";
import { AdminNotificationBell } from "@/components/notifications/AdminNotificationBell";
import Link from "next/link";

// Academic Horizon admin top header (DESIGN.md §12): page title + global actions + language /
// theme toggles + notification bell + profile. Pairs with AdminSidebar inside the admin shell.
// The mobile menu button toggles the sidebar via onMenu. Account actions live in the avatar menu.

function MenuIcon() {
  return (
    <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true" fill="none"
      stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
      <path d="M4 7h16M4 12h16M4 17h16" />
    </svg>
  );
}
function SunIcon() {
  return (
    <svg viewBox="0 0 24 24" width="17" height="17" aria-hidden="true" fill="none"
      stroke="currentColor" strokeWidth="2" strokeLinecap="round">
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M19.1 4.9l-1.4 1.4M6.3 17.7l-1.4 1.4" />
    </svg>
  );
}
function MoonIcon() {
  return (
    <svg viewBox="0 0 24 24" width="17" height="17" aria-hidden="true" fill="none"
      stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z" />
    </svg>
  );
}
function SignOutIcon() {
  return (
    <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor"
      strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9" />
    </svg>
  );
}

const STR = {
  en: {
    openMenu: "Open menu",
    language: "Language",
    notifications: "Notification management",
    account: "Admin account",
    role: "Role",
    department: "Department",
    adminRole: "Administrator",
    adminFallback: "VinUni administration",
    settings: "Settings",
    signOut: "Sign out",
  },
  vi: {
    openMenu: "Mở menu",
    language: "Ngôn ngữ",
    notifications: "Quản lý thông báo",
    account: "Tài khoản quản trị",
    role: "Vai trò",
    department: "Phòng ban",
    adminRole: "Quản trị viên",
    adminFallback: "Quản trị VinUni",
    settings: "Cài đặt",
    signOut: "Đăng xuất",
  },
} as const;

export function AdminHeader({
  title,
  subtitle,
  actions,
  onMenu,
}: {
  title: string;
  subtitle?: string;
  actions?: React.ReactNode;
  onMenu?: () => void;
}) {
  const { user, logout } = useAuth();
  const { theme, toggle } = useTheme();
  const { lang, setLang, t } = useI18n();
  const [accountOpen, setAccountOpen] = useState(false);
  const accountRef = useRef<HTMLDivElement>(null);
  const s = STR[lang];
  const nextTheme = theme === "dark" ? t.themeLight : t.themeDark;
  const adminDetail = user?.department || s.adminFallback;

  useEffect(() => {
    if (!accountOpen) return;
    function onPointerDown(event: MouseEvent) {
      if (!accountRef.current?.contains(event.target as Node)) {
        setAccountOpen(false);
      }
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") setAccountOpen(false);
    }
    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [accountOpen]);

  return (
    <header className="ah-admin-header">
      <div className="ah-admin-header-left">
        <button
          type="button"
          className="ah-iconbtn ah-menu-btn"
          onClick={onMenu}
          aria-label={s.openMenu}
        >
          <MenuIcon />
        </button>
        <div className="ah-admin-header-titles">
          <h1 className="ah-admin-header-title">{title}</h1>
          {subtitle && <p className="ah-admin-header-sub">{subtitle}</p>}
        </div>
      </div>

      <div className="ah-admin-header-actions">
        {actions}
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
        <button className="icon-btn" onClick={toggle} aria-label={nextTheme} title={nextTheme}>
          {theme === "dark" ? <SunIcon /> : <MoonIcon />}
        </button>
        <AdminNotificationBell />
        <div className="ah-account-menu-wrap" ref={accountRef}>
          <button
            type="button"
            className={`ah-avatar ah-avatar-btn ${accountOpen ? "active" : ""}`}
            title={user?.name}
            aria-label={s.account}
            aria-haspopup="menu"
            aria-expanded={accountOpen}
            onClick={() => setAccountOpen((open) => !open)}
          >
            {user ? initials(user.name) : "?"}
          </button>
          {accountOpen && user && (
            <div className="ah-account-menu" role="menu">
              <div className="ah-account-head">
                <span className="ah-avatar ah-account-avatar" aria-hidden>
                  {initials(user.name)}
                </span>
                <div className="ah-account-id">
                  <span className="ah-account-name">{user.name}</span>
                  <span className="ah-account-email">{user.email}</span>
                </div>
              </div>
              <div className="ah-account-meta">
                <div>
                  <span>{s.role}</span>
                  <strong>{s.adminRole}</strong>
                </div>
                <div>
                  <span>{s.department}</span>
                  <strong>{adminDetail}</strong>
                </div>
              </div>
              <Link
                className="ah-account-action"
                href="/admin/settings"
                role="menuitem"
                onClick={() => setAccountOpen(false)}
              >
                <IconCog size={16} />
                {s.settings}
              </Link>
              <button
                type="button"
                className="ah-account-action danger"
                role="menuitem"
                onClick={() => {
                  setAccountOpen(false);
                  void logout();
                }}
              >
                <SignOutIcon />
                {s.signOut}
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
