"use client";

import { usePortal } from "@/lib/portalI18n";

// Centered, branded frame for unauthenticated surfaces (login, 403). No sidebar/top bar.
export function AuthLayout({ children }: { children: React.ReactNode }) {
  const { p } = usePortal();
  return (
    <div className="auth-shell">
      <div className="auth-content">{children}</div>
      <footer className="auth-footer">{p.authFooter}</footer>
    </div>
  );
}
