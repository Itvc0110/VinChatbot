import { useI18n, type Lang } from "@/lib/i18n";

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
        <div className="lang-toggle" role="group" aria-label="Language">
          {(["en", "vi"] as Lang[]).map((l) => (
            <button
              key={l}
              className={`lang-opt ${lang === l ? "active" : ""}`}
              aria-pressed={lang === l}
              onClick={() => onSetLang(l)}
            >
              {t.langName[l]}
            </button>
          ))}
        </div>
        <button className="login-btn" title="Authentication is out of scope (visual only)">
          {t.login}
        </button>
      </div>
    </header>
  );
}
