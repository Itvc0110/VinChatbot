"use client";

import { useState } from "react";
import { usePathname } from "next/navigation";
import { Sidebar } from "@/components/shell/Sidebar";
import { TopBar } from "@/components/shell/TopBar";
import { ChatProvider } from "@/lib/chat";
import { FloatingVinnieButton } from "@/components/chat/FloatingVinnieButton";
import { StudentChatOverlays } from "@/components/chat/StudentChatOverlays";
import { usePortal } from "@/lib/portalI18n";
import type { Role } from "@/lib/auth";

// Derives the top-bar title/subtitle for the current route + role.
function usePageMeta(role: Role): { title: string; subtitle: string } {
  const pathname = usePathname();
  const { p } = usePortal();

  if (role === "admin") {
    const map: Record<string, string> = {
      "/admin/dashboard": p.nav.adminDashboard,
      "/admin/tickets": p.nav.adminTickets,
      "/admin/notifications": p.nav.adminNotifications,
      "/admin/sources": p.nav.sources,
      "/admin/upload": p.nav.upload,
      "/admin/unanswered": p.nav.questions,
      "/admin/analytics": p.nav.analytics,
      "/admin/logs": p.nav.logs,
    };
    const key = Object.keys(map).find((k) => pathname.startsWith(k));
    return { title: key ? map[key] : p.adminConsole, subtitle: p.adminConsoleSub };
  }

  const map: Record<string, string> = {
    "/student/dashboard": p.nav.dashboard,
    "/student/chat": p.nav.chat,
    "/student/schedule": p.nav.schedule,
    "/student/notifications": p.nav.notifications,
    "/student/tuition": p.nav.tuition,
    "/student/support": p.nav.tickets,
  };
  const key = Object.keys(map).find((k) => pathname.startsWith(k));
  return { title: key ? map[key] : p.productName, subtitle: p.productTagline };
}

// The shared portal frame, themed per role. Admin gets a distinct accent + a persistent
// "authorized staff only" helper banner so the two consoles never look interchangeable.
export function RoleShell({ role, children }: { role: Role; children: React.ReactNode }) {
  const [mobileOpen, setMobileOpen] = useState(false);
  const pathname = usePathname();
  const { p } = usePortal();
  const { title, subtitle } = usePageMeta(role);

  // The chat screen manages its own full-height layout.
  const flush = pathname.startsWith("/student/chat");
  // Floating Vinnie bubble: across student pages, but NOT on the full chat page itself.
  const showFloatingVinnie = role === "student" && !flush;

  const shell = (
    <div className={`shell shell-${role}`}>
      <div className={`sidebar-wrap ${mobileOpen ? "open" : ""}`}>
        <Sidebar role={role} onNavigate={() => setMobileOpen(false)} />
      </div>
      {mobileOpen && (
        <div className="sidebar-scrim" onClick={() => setMobileOpen(false)} aria-hidden />
      )}

      <div className="shell-main">
        <TopBar title={title} subtitle={subtitle} role={role} onMenu={() => setMobileOpen(true)} />
        {role === "admin" && (
          <div className="admin-banner" role="note">
            <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor"
              strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M12 9v4M12 17h.01M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z" />
            </svg>
            {p.adminWarning}
          </div>
        )}
        <main className={`shell-content ${flush ? "flush" : ""}`}>{children}</main>
      </div>
    </div>
  );

  // Students get the shared ChatProvider so the full page + floating bubble are one
  // conversation that survives route changes. Admin pages don't mount it.
  if (role === "student") {
    return (
      <ChatProvider>
        {shell}
        {showFloatingVinnie && <FloatingVinnieButton />}
        <StudentChatOverlays />
      </ChatProvider>
    );
  }
  return shell;
}
