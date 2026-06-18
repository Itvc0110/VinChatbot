"use client";

// Centered, branded frame for unauthenticated surfaces (login, 403). No sidebar/top bar.
export function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="auth-shell">
      <div className="auth-content">{children}</div>
      <footer className="auth-footer">
        VinUni Student Copilot · 24/7 verified student support
      </footer>
    </div>
  );
}
