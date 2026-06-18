"use client";

import { useRouter } from "next/navigation";
import { useAuth, DEMO_STUDENT, DEMO_ADMIN, type Role } from "@/lib/auth";
import { usePortal } from "@/lib/portalI18n";
import { RoleBadge } from "./RoleBadge";
import { initials } from "@/lib/format";
import { IconCap, IconShield, IconArrow } from "@/components/shell/icons";

// The login surface. Two demo accounts + an SSO-style button. Picking a role stores the
// demo session and redirects to that role's dashboard.
export function LoginCard() {
  const router = useRouter();
  const { login } = useAuth();
  const { p } = usePortal();

  const signIn = (role: Role) => {
    login(role);
    router.replace(role === "admin" ? "/admin/dashboard" : "/student/dashboard");
  };

  return (
    <div className="login-card">
      <div className="login-brand">
        <span className="login-badge">
          <IconCap size={26} />
        </span>
        <div>
          <div className="login-product">VinUni Student Copilot</div>
          <div className="login-product-sub">VinUniversity</div>
        </div>
      </div>

      <h1 className="login-title">{p.login.title}</h1>
      <p className="login-subtitle">{p.login.subtitle}</p>

      <div className="login-accounts">
        {/* Student */}
        <button className="account-card account-student" onClick={() => signIn("student")}>
          <div className="account-top">
            <span className="account-avatar">{initials(DEMO_STUDENT.name)}</span>
            <RoleBadge role="student" size="sm" />
          </div>
          <div className="account-name">{DEMO_STUDENT.name}</div>
          <div className="account-meta">
            {DEMO_STUDENT.program} · Year {DEMO_STUDENT.year}
          </div>
          <span className="account-cta">
            <IconCap size={15} /> {p.login.continueStudent} <IconArrow size={14} />
          </span>
        </button>

        {/* Admin */}
        <button className="account-card account-admin" onClick={() => signIn("admin")}>
          <div className="account-top">
            <span className="account-avatar admin">{initials(DEMO_ADMIN.name)}</span>
            <RoleBadge role="admin" size="sm" />
          </div>
          <div className="account-name">{DEMO_ADMIN.name}</div>
          <div className="account-meta">{DEMO_ADMIN.department}</div>
          <span className="account-cta">
            <IconShield size={15} /> {p.login.continueAdmin} <IconArrow size={14} />
          </span>
        </button>
      </div>

      <div className="login-divider">
        <span>{p.login.or}</span>
      </div>

      <button
        className="btn btn-outline login-sso"
        onClick={() => signIn("student")}
        title={p.login.ssoHint}
      >
        <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor"
          strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <rect x="3" y="11" width="18" height="10" rx="2" />
          <path d="M7 11V7a5 5 0 0 1 10 0v4" />
        </svg>
        {p.login.sso}
      </button>

      <p className="login-note">🔒 {p.login.securityNote}</p>
    </div>
  );
}
