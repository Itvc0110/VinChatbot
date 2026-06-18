import { useI18n } from "@/lib/i18n";
import { Composer } from "./Composer";

function AssistantAvatar() {
  return (
    <div className="welcome-avatar" aria-hidden="true">
      <svg viewBox="0 0 24 24" width="34" height="34">
        <path
          fill="#fff"
          d="M12 3 1 8l11 5 9-4.09V14h2V8L12 3zM5 13.18v3.2L12 20l7-3.62v-3.2l-7 3.2-7-3.4z"
        />
      </svg>
    </div>
  );
}

export function WelcomeState({ onSend }: { onSend: (text: string) => void }) {
  const { t } = useI18n();
  return (
    <div className="welcome">
      <div className="welcome-inner">
        <AssistantAvatar />
        <h2 className="welcome-greeting">{t.welcomeGreeting}</h2>
        <p className="welcome-intro">{t.welcomeIntro}</p>

        <ul className="welcome-categories">
          {t.categories.map((c) => (
            <li key={c.label}>
              <span className="cat-icon">{c.icon}</span>
              {c.label}
            </li>
          ))}
        </ul>

        <div className="welcome-hint">{t.welcomeHint}</div>
        <div className="welcome-chips">
          {t.quickPrompts.map((p) => (
            <button key={p} className="welcome-chip" onClick={() => onSend(p)}>
              {p}
            </button>
          ))}
        </div>
      </div>

      <div className="welcome-composer">
        <Composer onSend={onSend} onStop={() => {}} busy={false} showChips={false} />
      </div>
    </div>
  );
}
