"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";

// Root entry: route to the correct place based on the demo session.
//  - no session  -> /login
//  - student     -> /student/dashboard
//  - admin       -> /admin/dashboard
export default function RootPage() {
  const { user, hydrated } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!hydrated) return;
    if (!user) router.replace("/login");
    else router.replace(user.role === "admin" ? "/admin/dashboard" : "/student/dashboard");
  }, [hydrated, user, router]);

  return (
    <div className="route-guard" role="status" aria-busy="true">
      <span className="guard-spinner" />
    </div>
  );
}
