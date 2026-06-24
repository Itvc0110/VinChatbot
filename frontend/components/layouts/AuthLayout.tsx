"use client";

import { usePortal } from "@/lib/portalI18n";

// Centered, branded frame for unauthenticated surfaces (login, 403) — the Academic Horizon
// centered auth layout (DESIGN.md §11.1). No top nav / sidebar. This owns only the centered
// frame; the login page content (LoginCard) is restyled separately in Phase 2.1.
export function AuthLayout({ children }: { children: React.ReactNode }) {
  const { p } = usePortal();
  return (
    <div className="ah-authframe">
      <div className="auth-content">{children}</div>
      <footer className="auth-footer">{p.authFooter}</footer>
    </div>
  );
}
