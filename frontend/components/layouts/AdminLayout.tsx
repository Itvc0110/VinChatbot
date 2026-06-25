"use client";

import { ProtectedRoute } from "@/components/auth/ProtectedRoute";
import { AdminShell } from "./AdminShell";

// Admin console frame: role guard + the Academic Horizon admin shell (left sidebar + top header).
// Students use StudentShell (horizontal top nav) — the two consoles stay distinct.
export function AdminLayout({ children }: { children: React.ReactNode }) {
  return (
    <ProtectedRoute role="admin">
      <AdminShell>{children}</AdminShell>
    </ProtectedRoute>
  );
}
