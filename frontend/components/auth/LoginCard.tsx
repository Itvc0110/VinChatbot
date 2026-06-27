"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth, type SessionUser } from "@/lib/auth";
import { usePortal } from "@/lib/portalI18n";
import { IconCap, IconShield } from "@/components/shell/icons";

const DEMO_PASSWORD = "Demo@123456";
const DEMO_STUDENT_EMAIL = "student.cs.demo@vinuni.edu.vn";
const DEMO_ADMIN_EMAIL = "admin.global.demo@vinuni.edu.vn";

function MailIcon() {
  return (
    <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor"
      strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <rect x="3" y="5" width="18" height="14" rx="2" />
      <path d="m3 7 9 6 9-6" />
    </svg>
  );
}

function LockIcon() {
  return (
    <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor"
      strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <rect x="3" y="11" width="18" height="10" rx="2" />
      <path d="M7 11V7a5 5 0 0 1 10 0v4" />
    </svg>
  );
}

export function LoginCard() {
  const router = useRouter();
  const { login } = useAuth();
  const { p } = usePortal();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const routeAfterLogin = (user: SessionUser) => {
    router.replace(user.role === "admin" ? "/admin/dashboard" : "/student/dashboard");
  };

  const signIn = async (nextEmail = email, nextPassword = password) => {
    setError(null);
    setBusy(true);
    try {
      const user = await login(nextEmail.trim(), nextPassword);
      routeAfterLogin(user);
    } catch {
      setError("Invalid email or password.");
    } finally {
      setBusy(false);
    }
  };

  const signInDemo = async (nextEmail: string) => {
    setEmail(nextEmail);
    setPassword(DEMO_PASSWORD);
    await signIn(nextEmail, DEMO_PASSWORD);
  };

  return (
    <div className="ah-login">
      <div className="ah-login-card">
        <div className="ah-login-brand">
          <span className="ah-login-badge">
            <IconCap size={26} />
          </span>
          <div>
            <div className="ah-login-brand-name">Student Copilot</div>
            <div className="ah-login-brand-sub">VinUniversity</div>
          </div>
        </div>

        <h1 className="ah-login-title">{p.login.title}</h1>
        <p className="ah-login-sub">{p.login.subtitle}</p>

        <form
          onSubmit={async (e) => {
            e.preventDefault();
            await signIn();
          }}
        >
          <div className="ah-field">
            <label className="ah-field-label" htmlFor="login-email">
              {p.login.emailLabel}
            </label>
            <div className="ah-input-wrap">
              <span className="ah-input-icon">
                <MailIcon />
              </span>
              <input
                id="login-email"
                className="ah-input"
                type="email"
                autoComplete="username"
                placeholder="you@vinuni.edu.vn"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                disabled={busy}
                required
              />
            </div>
          </div>

          <div className="ah-field">
            <label className="ah-field-label" htmlFor="login-password">
              {p.login.passwordLabel}
            </label>
            <div className="ah-input-wrap">
              <span className="ah-input-icon">
                <LockIcon />
              </span>
              <input
                id="login-password"
                className="ah-input"
                type="password"
                autoComplete="current-password"
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                disabled={busy}
                required
              />
            </div>
          </div>

          {error && (
            <p className="ah-login-error" role="alert">
              {error}
            </p>
          )}

          <button type="submit" className="ah-btn-primary-full" disabled={busy}>
            {busy ? "Signing in..." : p.login.signIn}
          </button>
        </form>

        <div className="ah-login-divider">
          <span>{p.login.or}</span>
        </div>

        <button
          type="button"
          className="ah-btn-outline-full"
          disabled
          title="VinUni SSO is not configured in this demo environment."
        >
          <LockIcon />
          {p.login.sso}
        </button>

        <div className="ah-login-demo">
          <button
            type="button"
            className="ah-login-demo-btn"
            onClick={() => signInDemo(DEMO_STUDENT_EMAIL)}
            disabled={busy}
          >
            <IconCap size={15} /> {p.login.continueStudent}
          </button>
          <button
            type="button"
            className="ah-login-demo-btn"
            onClick={() => signInDemo(DEMO_ADMIN_EMAIL)}
            disabled={busy}
          >
            <IconShield size={15} /> {p.login.continueAdmin}
          </button>
        </div>

        <div className="ah-login-demo-hint">
          <span>{p.login.demoStudent}: {DEMO_STUDENT_EMAIL}</span>
          <span>{p.login.demoAdmin}: {DEMO_ADMIN_EMAIL}</span>
          <span>Password: {DEMO_PASSWORD}</span>
        </div>

        <p className="ah-login-foot">{p.login.securityNote}</p>
      </div>
    </div>
  );
}
