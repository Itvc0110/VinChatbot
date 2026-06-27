"use client";

import { ProtectedRoute } from "@/components/auth/ProtectedRoute";
import { StudentShell } from "./StudentShell";

// Student portal frame: role guard + the Academic Horizon student shell (horizontal top nav).
// Admin continues to use RoleShell (sidebar) — see AdminLayout — so the two consoles stay distinct.
export function StudentLayout({ children }: { children: React.ReactNode }) {
  return (
    <ProtectedRoute role="student">
      <StudentShell>{children}</StudentShell>
    </ProtectedRoute>
  );
}
