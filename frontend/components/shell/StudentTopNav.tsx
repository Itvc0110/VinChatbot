"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { initials } from "@/lib/format";
import {
  IconGrid,
  IconChat,
  IconCalendar,
  IconTicket,
  IconBell,
  IconCap,
} from "./icons";

// Academic Horizon student chrome: a fixed horizontal top navigation bar (DESIGN.md §11.2).
// Links use the Stitch screen names and point at the EXISTING routes (see ROUTES.md) — no
// route renames. The active link gets a 2px brand-red underline (.ah-topnav-link.active).
// Standalone for now; wired into StudentLayout in Phase 2.

interface NavItem {
  href: string;
  label: string;
  icon: React.ReactNode;
}

const STUDENT_NAV: NavItem[] = [
  { href: "/student/dashboard", label: "Dashboard", icon: <IconGrid /> },
  { href: "/student/chat", label: "Vinnie AI", icon: <IconChat /> },
  { href: "/student/schedule", label: "Calendar", icon: <IconCalendar /> },
  { href: "/student/events", label: "Events", icon: <IconCalendar /> },
  { href: "/student/support", label: "Tickets", icon: <IconTicket /> },
];

function isActive(pathname: string, href: string): boolean {
  return pathname === href || pathname.startsWith(href + "/");
}

export function StudentTopNav() {
  const pathname = usePathname();
  const { user } = useAuth();

  return (
    <header className="ah-topnav">
      <Link href="/student/dashboard" className="ah-topnav-brand">
        <span className="ah-topnav-badge">
          <IconCap size={18} />
        </span>
        VinUni
      </Link>

      <nav aria-label="Primary">
        <ul className="ah-topnav-links">
          {STUDENT_NAV.map((item) => {
            const active = isActive(pathname, item.href);
            return (
              <li key={item.href}>
                <Link
                  href={item.href}
                  className={`ah-topnav-link ${active ? "active" : ""}`}
                  aria-current={active ? "page" : undefined}
                >
                  <span aria-hidden>{item.icon}</span>
                  {item.label}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>

      <div className="ah-topnav-actions">
        <Link
          href="/student/notifications"
          className="ah-iconbtn"
          aria-label="Notifications"
        >
          <IconBell />
          <span className="ah-iconbtn-dot" aria-hidden />
        </Link>
        <button type="button" className="ah-profile" aria-label="Profile">
          <span className="ah-avatar">{user ? initials(user.name) : "?"}</span>
          {user && <span className="ah-profile-name">{user.name}</span>}
        </button>
      </div>
    </header>
  );
}
