"use client";

import { useAuth } from "@/lib/auth";
import { usePortal } from "@/lib/portalI18n";
import { initials } from "@/lib/format";
import { RoleBadge } from "./RoleBadge";

// Sidebar footer: avatar + name + role + program/department + sign-out.
export function UserProfileCard() {
  const { user, logout } = useAuth();
  const { p } = usePortal();
  if (!user) return null;

  const detail =
    user.role === "admin"
      ? user.department
      : `${user.program ?? ""}${user.year ? ` · Year ${user.year}` : ""}`;

  return (
    <div className="sidebar-profile">
      <span className="profile-avatar">{initials(user.name)}</span>
      <span className="profile-text">
        <span className="profile-name">{user.name}</span>
        <span className="profile-sub" title={detail}>
          {detail}
        </span>
        <span style={{ marginTop: 4 }}>
          <RoleBadge role={user.role} size="sm" />
        </span>
      </span>
      <button className="profile-logout" onClick={logout} title={p.signOut} aria-label={p.signOut}>
        <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor"
          strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9" />
        </svg>
      </button>
    </div>
  );
}
