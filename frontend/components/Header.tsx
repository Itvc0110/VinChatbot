import { useI18n, type Lang } from "@/lib/i18n";
import { useTheme } from "@/lib/theme";

function GradCap() {
  return (
    <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true">
      <path
        fill="currentColor"
        d="M12 3 1 8l11 5 9-4.09V14h2V8L12 3zM5 13.18v3.2L12 20l7-3.62v-3.2l-7 3.2-7-3.4z"
      />
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

function ThemeToggle() {
  const { theme, toggle } = useTheme();
  const { t } = useI18n();
  const next = theme === "dark" ? t.themeLight : t.themeDark;
  return (
    <button
      className="icon-btn"
      onClick={toggle}
      aria-label={next}
      title={next}
    >
      {theme === "dark" ? <SunIcon /> : <MoonIcon />}
    </button>
  );
}

export function Header({
  lang,
  onSetLang,
}: {
  lang: Lang;
  onSetLang: (l: Lang) => void;
}) {
  const { t } = useI18n();
  return (
    <header className="topbar">
      <div className="brand">
        <span className="brand-badge">
          <GradCap />
        </span>
        <span className="brand-text">
          <span className="brand-name">
            VinChatbot <span className="brand-by">· VinUni</span>
          </span>
          <span className="brand-sub">{t.assistantLabel}</span>
        </span>
        <span className="status" title={t.statusReady}>
          <span className="status-dot" />
          {t.statusReady}
        </span>
      </div>

      <div className="topbar-actions">
        <div className="seg" role="group" aria-label="Language">
          {(["en", "vi"] as Lang[]).map((l) => (
            <button
              key={l}
              className={`seg-opt ${lang === l ? "active" : ""}`}
              aria-pressed={lang === l}
              onClick={() => onSetLang(l)}
            >
              {t.langName[l]}
            </button>
          ))}
        </div>
        <ThemeToggle />
        <button
          className="login-btn"
          title="Authentication is out of scope (visual only)"
        >
          {t.login}
        </button>
      </div>
    </header>
  );
}
