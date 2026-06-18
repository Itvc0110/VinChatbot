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
  const { user, hydrated } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!hydrated) return;
    if (!user) {
      router.replace("/login");
    } else if (user.role !== role) {
      router.replace("/403");
    }
  }, [hydrated, user, role, router]);

  if (!hydrated || !user || user.role !== role) {
    return (
      <div className="route-guard" role="status" aria-busy="true">
        <span className="guard-spinner" />
      </div>
    );
  }

  return <>{children}</>;
}
