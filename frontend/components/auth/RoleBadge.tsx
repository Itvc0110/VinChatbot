"use client";

import type { Role } from "@/lib/auth";
import { usePortal } from "@/lib/portalI18n";
import { IconCap, IconShield } from "@/components/shell/icons";

// Visible role indicator (top bar + login cards). Student = crimson/info, Admin = gold —
// so the two modes read as clearly distinct at a glance.
export function RoleBadge({ role, size = "md" }: { role: Role; size?: "sm" | "md" }) {
  const { p } = usePortal();
  const isAdmin = role === "admin";
  return (
    <span className={`role-badge role-${role} ${size === "sm" ? "role-badge-sm" : ""}`}>
      {isAdmin ? <IconShield size={13} /> : <IconCap size={13} />}
      {isAdmin ? p.roleAdmin : p.roleStudent}
    </span>
  );
}
