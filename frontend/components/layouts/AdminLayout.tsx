"use client";

import { ProtectedRoute } from "@/components/auth/ProtectedRoute";
import { RoleShell } from "./RoleShell";

// Admin console frame: role guard + admin-only navigation chrome.
export function AdminLayout({ children }: { children: React.ReactNode }) {
  return (
    <ProtectedRoute role="admin">
      <RoleShell role="admin">{children}</RoleShell>
    </ProtectedRoute>
  );
}
