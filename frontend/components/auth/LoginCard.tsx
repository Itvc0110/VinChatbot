"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth, type Role } from "@/lib/auth";
import { usePortal } from "@/lib/portalI18n";
import { IconCap, IconShield } from "@/components/shell/icons";

// Academic Horizon login (Stitch "Student Copilot" login): centered card, brand, title/subtitle,
// university email + password inputs with leading icons, a primary sign-in button, a VinUni SSO
// button, and quick demo-account access. Auth is still the demo session (no backend auth endpoint),
// so submitting signs in as the student demo and the demo buttons cover both roles — behavior is
// preserved; only the presentation is rebuilt.
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

  const signIn = (role: Role) => {
    login(role);
    router.replace(role === "admin" ? "/admin/dashboard" : "/student/dashboard");
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
          onSubmit={(e) => {
            e.preventDefault();
            signIn("student");
          }}
        >
          <div className="ah-field">
            <label className="ah-field-label" htmlFor="login-email">
              University email
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
              />
            </div>
          </div>

          <div className="ah-field">
            <label className="ah-field-label" htmlFor="login-password">
              Password
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
              />
            </div>
          </div>

          <button type="submit" className="ah-btn-primary-full">
            Sign in
          </button>
        </form>

        <div className="ah-login-divider">
          <span>{p.login.or}</span>
        </div>

        <button
          type="button"
          className="ah-btn-outline-full"
          onClick={() => signIn("student")}
          title={p.login.ssoHint}
        >
          <LockIcon />
          {p.login.sso}
        </button>

        <div className="ah-login-demo">
          <button
            type="button"
            className="ah-login-demo-btn"
            onClick={() => signIn("student")}
          >
            <IconCap size={15} /> {p.login.continueStudent}
          </button>
          <button
            type="button"
            className="ah-login-demo-btn"
            onClick={() => signIn("admin")}
          >
            <IconShield size={15} /> {p.login.continueAdmin}
          </button>
        </div>

        <p className="ah-login-foot">🔒 {p.login.securityNote}</p>
      </div>
    </div>
  );
}
