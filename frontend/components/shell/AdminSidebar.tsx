"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { UserProfileCard } from "@/components/auth/UserProfileCard";
import {
  IconShield,
  IconTicket,
  IconDatabase,
  IconCalendar,
  IconBell,
  IconChart,
  IconCog,
  IconUpload,
  IconInbox,
  IconSliders,
} from "./icons";

// Academic Horizon admin chrome: a left sidebar (DESIGN.md §12). Admin is NOT forced into the
// student horizontal nav. Links use the Stitch screen names over the EXISTING routes (ROUTES.md);
// the active item gets a brand-red indicator (.ah-sidebar-link.active::before). Standalone for
// now; wired into AdminLayout in Phase 3.

interface NavItem {
  href: string;
  label: string;
  icon: React.ReactNode;
}

const ADMIN_PRIMARY: NavItem[] = [
  { href: "/admin/dashboard", label: "Dashboard", icon: <IconShield /> },
  { href: "/admin/tickets", label: "Tickets", icon: <IconTicket /> },
  { href: "/admin/sources", label: "Knowledge Base", icon: <IconDatabase /> },
  { href: "/admin/events", label: "Events", icon: <IconCalendar /> },
  { href: "/admin/notifications", label: "Notifications", icon: <IconBell /> },
  { href: "/admin/analytics", label: "Monitoring", icon: <IconChart /> },
  { href: "/admin/settings", label: "Settings", icon: <IconCog /> },
];

const ADMIN_SECONDARY: NavItem[] = [
  { href: "/admin/upload", label: "Upload Source", icon: <IconUpload /> },
  { href: "/admin/unanswered", label: "Review Queue", icon: <IconInbox /> },
  { href: "/admin/context", label: "Context", icon: <IconSliders /> },
];

function isActive(pathname: string, href: string): boolean {
  return pathname === href || pathname.startsWith(href + "/");
}

export function AdminSidebar({
  open = false,
  onNavigate,
}: {
  open?: boolean;
  onNavigate?: () => void;
}) {
  const pathname = usePathname();

  const renderItem = (item: NavItem) => {
    const active = isActive(pathname, item.href);
    return (
      <li key={item.href}>
        <Link
          href={item.href}
          className={`ah-sidebar-link ${active ? "active" : ""}`}
          aria-current={active ? "page" : undefined}
          onClick={onNavigate}
        >
          <span aria-hidden>{item.icon}</span>
          {item.label}
        </Link>
      </li>
    );
  };

  return (
    <aside className={`ah-sidebar ${open ? "open" : ""}`}>
      <div className="ah-sidebar-brand">
        <span className="ah-sidebar-badge">
          <IconShield size={20} />
        </span>
        Admin Console
      </div>
      <nav className="ah-sidebar-nav" aria-label="Admin">
        <ul>{ADMIN_PRIMARY.map(renderItem)}</ul>
        <div className="ah-sidebar-group">Knowledge</div>
        <ul>{ADMIN_SECONDARY.map(renderItem)}</ul>
      </nav>
      <UserProfileCard />
    </aside>
  );
}
