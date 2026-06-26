"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth, type Role } from "@/lib/auth";

// Client-side role guard:
//  - not hydrated yet  -> render a neutral placeholder (no flash, no premature redirect)
//  - no session        -> redirect to /login
//  - wrong role        -> redirect to /403
//  - correct role      -> render children
export function ProtectedRoute({
  role,
  children,
}: {
  role: Role;
  children: React.ReactNode;
}) {
  const { user, hydrated, hasRole } = useAuth();
  const router = useRouter();
  const allowed =
    role === "student"
      ? hasRole("student")
      : hasRole("global_admin") || hasRole("institute_admin") || hasRole("staff");

  useEffect(() => {
    if (!hydrated) return;
    if (!user) {
      router.replace("/login");
    } else if (!allowed) {
      router.replace("/403");
    }
  }, [allowed, hydrated, user, router]);

  if (!hydrated || !user || !allowed) {
    return (
      <div className="route-guard" role="status" aria-busy="true">
        <span className="guard-spinner" />
      </div>
    );
  }

  return <>{children}</>;
}
