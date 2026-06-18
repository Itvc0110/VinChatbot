"use client";

import { ProtectedRoute } from "@/components/auth/ProtectedRoute";
import { RoleShell } from "./RoleShell";

// Student portal frame: role guard + student-only navigation chrome.
export function StudentLayout({ children }: { children: React.ReactNode }) {
  return (
    <ProtectedRoute role="student">
      <RoleShell role="student">{children}</RoleShell>
    </ProtectedRoute>
  );
}
