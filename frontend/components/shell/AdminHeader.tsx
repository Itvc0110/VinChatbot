"use client";

import { useAuth } from "@/lib/auth";
import { initials } from "@/lib/format";
import { IconBell } from "./icons";

// Academic Horizon admin top header (DESIGN.md §12): page title + global actions + notification
// bell + profile. Pairs with AdminSidebar inside the admin shell. The mobile menu button toggles
// the sidebar via onMenu. Standalone for now; wired into AdminLayout in Phase 3.

function MenuIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      width="20"
      height="20"
      aria-hidden="true"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
    >
      <path d="M4 7h16M4 12h16M4 17h16" />
    </svg>
  );
}

export function AdminHeader({
  title,
  subtitle,
  actions,
  onMenu,
}: {
  title: string;
  subtitle?: string;
  actions?: React.ReactNode;
  onMenu?: () => void;
}) {
  const { user } = useAuth();

  return (
    <header className="ah-admin-header">
      <div className="ah-admin-header-left">
        <button
          type="button"
          className="ah-iconbtn ah-menu-btn"
          onClick={onMenu}
          aria-label="Open menu"
        >
          <MenuIcon />
        </button>
        <div className="ah-admin-header-titles">
          <h1 className="ah-admin-header-title">{title}</h1>
          {subtitle && <p className="ah-admin-header-sub">{subtitle}</p>}
        </div>
      </div>

      <div className="ah-admin-header-actions">
        {actions}
        <button type="button" className="ah-iconbtn" aria-label="Notifications">
          <IconBell />
          <span className="ah-iconbtn-dot" aria-hidden />
        </button>
        <span className="ah-avatar" title={user?.name}>
          {user ? initials(user.name) : "?"}
        </span>
      </div>
    </header>
  );
}
