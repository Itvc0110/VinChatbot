"use client";

import { useAuth } from "@/lib/auth";
import { useTheme } from "@/lib/theme";
import { useI18n, type Lang } from "@/lib/i18n";
import { initials } from "@/lib/format";
import { IconBell } from "./icons";

// Academic Horizon admin top header (DESIGN.md §12): page title + global actions + language /
// theme toggles + notification bell + profile. Pairs with AdminSidebar inside the admin shell.
// The mobile menu button toggles the sidebar via onMenu. Sign-out lives in the sidebar footer.

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
  const { user } = useAuth();
  const { theme, toggle } = useTheme();
  const { lang, setLang, t } = useI18n();
  const nextTheme = theme === "dark" ? t.themeLight : t.themeDark;

  return (
    <header className="ah-admin-header">
      <div className="ah-admin-header-left">
        <button
          type="button"
          className="ah-iconbtn ah-menu-btn"
          onClick={onMenu}
          aria-label="Open menu"
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
        <div className="seg" role="group" aria-label="Language">
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
        <button type="button" className="ah-iconbtn" aria-label="Notifications">
          <IconBell />
          <span className="ah-iconbtn-dot" aria-hidden />
        </button>
        <span className="ah-avatar" title={user?.name}>
          {user ? initials(user.name) : "?"}
        </span>
      </div>
    </header>
  );
}
