"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { LoginCard } from "@/components/auth/LoginCard";
import { LoginHeroPanel } from "@/components/auth/LoginHeroPanel";
import { useAuth } from "@/lib/auth";
import { usePortal } from "@/lib/portalI18n";

// Premium split-screen login: a general (non-personalized) VinUni Student Copilot intro on the
// LEFT and the existing LoginCard on the RIGHT. The auth logic lives entirely in LoginCard and is
// untouched here; this page only owns layout + the already-signed-in redirect.
//
// DOM order is form-first (so keyboard/screen-reader users reach the form before the marketing
// panel); CSS `order` places the hero on the left and the form on the right at desktop widths.
export default function LoginPage() {
  const { user, hydrated } = useAuth();
  const { p } = usePortal();
  const router = useRouter();

  // Already signed in? Skip the login screen and go to the right dashboard.
  useEffect(() => {
    if (hydrated && user) {
      router.replace(user.role === "admin" ? "/admin/dashboard" : "/student/dashboard");
    }
  }, [hydrated, user, router]);

  return (
    <div className="login-shell ah-ui">
      <div className="login-form-panel">
        <div className="login-form-inner">
          <LoginCard />
          <footer className="login-form-footer">{p.authFooter}</footer>
        </div>
      </div>
      <LoginHeroPanel />
    </div>
  );
}
