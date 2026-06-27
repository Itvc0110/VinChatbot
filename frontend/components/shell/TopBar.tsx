"use client";

import { useTheme } from "@/lib/theme";
import { useI18n, type Lang } from "@/lib/i18n";
import { usePortal } from "@/lib/portalI18n";
import type { Role } from "@/lib/auth";
import { RoleBadge } from "@/components/auth/RoleBadge";

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

function MenuIcon() {
  return (
    <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true" fill="none"
      stroke="currentColor" strokeWidth="2" strokeLinecap="round">
      <path d="M4 7h16M4 12h16M4 17h16" />
    </svg>
  );
}

const STR = {
  en: { openMenu: "Open menu", language: "Language" },
  vi: { openMenu: "Mở menu", language: "Ngôn ngữ" },
} as const;

export function TopBar({
  title,
  subtitle,
  role,
  onMenu,
}: {
  title: string;
  subtitle?: string;
  role?: Role;
  onMenu?: () => void;
}) {
  const { theme, toggle } = useTheme();
  const { lang, setLang, t } = useI18n();
  const { p } = usePortal();
  const s = STR[lang];
  const nextTheme = theme === "dark" ? t.themeLight : t.themeDark;

  return (
    <header className="ptop">
      <div className="ptop-left">
        <button className="ptop-menu" onClick={onMenu} aria-label={s.openMenu}>
          <MenuIcon />
        </button>
        <div className="ptop-titles">
          <h1 className="ptop-title">{title}</h1>
          {subtitle && <p className="ptop-sub">{subtitle}</p>}
        </div>
      </div>

      <div className="ptop-actions">
        {role && <RoleBadge role={role} />}
        <span className="ptop-status" title={p.productTagline}>
          <span className="status-dot" />
          {t.statusReady}
        </span>
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
      </div>
    </header>
  );
}
