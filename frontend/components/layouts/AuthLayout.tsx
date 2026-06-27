"use client";

import { usePortal } from "@/lib/portalI18n";

// Centered, branded frame for unauthenticated surfaces (login, 403) — the Academic Horizon
// centered auth layout (DESIGN.md §11.1). The `.ah-ui` scope remaps the design tokens so the
// login card adopts Academic Horizon (brand red, AH radius/borders) without touching LoginCard.
export function AuthLayout({ children }: { children: React.ReactNode }) {
  const { p } = usePortal();
  return (
    <div className="ah-authframe ah-ui">
      <div className="auth-content">{children}</div>
      <footer className="auth-footer">{p.authFooter}</footer>
    </div>
  );
}
