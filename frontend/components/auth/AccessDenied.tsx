"use client";

import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { usePortal } from "@/lib/portalI18n";
import { IconShield } from "@/components/shell/icons";

// /403 content. "Back to my dashboard" routes to the dashboard for the *current* role
// (so an admin who hit a student route lands back in the admin console, and vice-versa).
export function AccessDenied() {
  const router = useRouter();
  const { user, logout } = useAuth();
  const { p } = usePortal();

  const home = user?.role === "admin" ? "/admin/dashboard" : "/student/dashboard";

  return (
    <div className="denied-card">
      <span className="denied-icon">
        <IconShield size={34} />
      </span>
      <h1 className="denied-title">{p.access.title}</h1>
      <p className="denied-msg">{p.access.message}</p>
      <div className="denied-actions">
        {user && (
          <button className="btn btn-primary" onClick={() => router.replace(home)}>
            {p.access.backToDashboard}
          </button>
        )}
        <button
          className="btn btn-outline"
          onClick={() => {
            logout();
            router.replace("/login");
          }}
        >
          {p.access.signOut}
        </button>
      </div>
    </div>
  );
}
