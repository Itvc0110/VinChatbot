"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { usePortal } from "@/lib/portalI18n";
import type { Role } from "@/lib/auth";
import { UserProfileCard } from "@/components/auth/UserProfileCard";
import {
  IconGrid,
  IconChat,
  IconCalendar,
  IconWallet,
  IconTicket,
  IconShield,
  IconDatabase,
  IconUpload,
  IconInbox,
  IconChart,
  IconClock,
  IconCap,
} from "./icons";

interface NavItem {
  href: string;
  label: string;
  icon: React.ReactNode;
}

function isActive(pathname: string, href: string): boolean {
  return pathname === href || pathname.startsWith(href + "/");
}

export function Sidebar({ role, onNavigate }: { role: Role; onNavigate?: () => void }) {
  const pathname = usePathname();
  const { p } = usePortal();

  // Each role sees ONLY its own navigation — no mixing of student + admin items.
  const studentNav: NavItem[] = [
    { href: "/student/dashboard", label: p.nav.dashboard, icon: <IconGrid /> },
    { href: "/student/chat", label: p.nav.chat, icon: <IconChat /> },
    { href: "/student/schedule", label: p.nav.schedule, icon: <IconCalendar /> },
    { href: "/student/tuition", label: p.nav.tuition, icon: <IconWallet /> },
    { href: "/student/support", label: p.nav.tickets, icon: <IconTicket /> },
  ];

  const adminNav: NavItem[] = [
    { href: "/admin/dashboard", label: p.nav.adminDashboard, icon: <IconShield /> },
    { href: "/admin/sources", label: p.nav.sources, icon: <IconDatabase /> },
    { href: "/admin/upload", label: p.nav.upload, icon: <IconUpload /> },
    { href: "/admin/unanswered", label: p.nav.questions, icon: <IconInbox /> },
    { href: "/admin/analytics", label: p.nav.analytics, icon: <IconChart /> },
    { href: "/admin/logs", label: p.nav.logs, icon: <IconClock /> },
  ];

  const items = role === "admin" ? adminNav : studentNav;
  const brandName = role === "admin" ? p.adminConsole : p.productName;
  const groupLabel = role === "admin" ? p.adminPortal : p.studentPortal;

  return (
    <aside className={`sidebar sidebar-${role}`}>
      <div className="sidebar-brand">
        <span className="sidebar-badge">
          {role === "admin" ? <IconShield size={20} /> : <IconCap size={20} />}
        </span>
        <span className="sidebar-brand-text">
          <span className="sidebar-brand-name">{brandName}</span>
          <span className="sidebar-brand-sub">VinUni</span>
        </span>
      </div>

      <nav className="sidebar-nav" aria-label="Primary">
        <div className="nav-group-label">{groupLabel}</div>
        <ul>
          {items.map((item) => (
            <li key={item.href}>
              <Link
                href={item.href}
                className={`nav-item ${isActive(pathname, item.href) ? "active" : ""}`}
                aria-current={isActive(pathname, item.href) ? "page" : undefined}
                onClick={onNavigate}
              >
                <span className="nav-icon">{item.icon}</span>
                <span className="nav-label">{item.label}</span>
              </Link>
            </li>
          ))}
        </ul>
      </nav>

      <UserProfileCard />
    </aside>
  );
}
