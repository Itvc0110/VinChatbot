"use client";

import { useState } from "react";
import { usePathname } from "next/navigation";
import { AdminSidebar } from "@/components/shell/AdminSidebar";
import { AdminHeader } from "@/components/shell/AdminHeader";
import { usePortal } from "@/lib/portalI18n";
import { IconAlert } from "@/components/shell/icons";

// Academic Horizon admin shell: left sidebar + top admin header (DESIGN.md §12), scoped to `.ah-ui`
// so admin pages adopt the AH tokens. Preserves the RoleShell admin behavior: the per-route header
// title and the persistent "authorized staff only" banner so the admin console never looks like the
// student portal. No API / auth logic changes — ProtectedRoute still wraps this (see AdminLayout).

const TITLES: Record<string, { title: string; sub?: string }> = {
  "/admin/dashboard": { title: "Dashboard", sub: "Operational control center" },
  "/admin/tickets": { title: "Support Tickets", sub: "Manage and respond to student requests" },
  "/admin/sources/upload": { title: "Upload Source", sub: "Add a source to the knowledge base" },
  "/admin/sources/unanswered": { title: "Review Queue", sub: "Questions Vinnie could not verify" },
  "/admin/sources/context": { title: "Context" },
  "/admin/sources": { title: "Knowledge Base", sub: "Sources Vinnie can cite" },
  "/admin/upload": { title: "Upload Source", sub: "Add a source to the knowledge base" },
  "/admin/unanswered": { title: "Review Queue", sub: "Questions Vinnie could not verify" },
  "/admin/notifications": { title: "Notification Management", sub: "Announcements & suggested questions" },
  "/admin/analytics": { title: "Vinnie AI Monitoring", sub: "Quality, coverage & usage" },
  "/admin/logs": { title: "Logs" },
  "/admin/settings": { title: "Settings" },
  "/admin/context": { title: "Context" },
  "/admin/events": { title: "Events" },
};

export function AdminShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { p, lang } = usePortal();
  const [open, setOpen] = useState(false);

  const key = Object.keys(TITLES)
    .sort((a, b) => b.length - a.length)
    .find((k) => pathname.startsWith(k));
  const meta = key ? TITLES[key] : { title: "Admin Console", sub: undefined };

  return (
    <div className="ah-ui">
      <a className="skip-link" href="#main-content">
        {lang === "vi" ? "Bỏ qua tới nội dung chính" : "Skip to main content"}
      </a>
      <div className="ah-adminshell">
        <AdminSidebar open={open} onNavigate={() => setOpen(false)} />
        {open && (
          <div className="ah-sidebar-scrim" onClick={() => setOpen(false)} aria-hidden />
        )}
        <div className="ah-adminmain">
          <AdminHeader title={meta.title} subtitle={meta.sub} onMenu={() => setOpen(true)} />
          <div className="ah-admin-banner" role="note">
            <IconAlert size={14} />
            {p.adminWarning}
          </div>
          <main id="main-content" className="ah-admin-content">{children}</main>
        </div>
      </div>
    </div>
  );
}
