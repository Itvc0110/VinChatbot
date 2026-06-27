"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { AuthLayout } from "@/components/layouts/AuthLayout";
import { LoginCard } from "@/components/auth/LoginCard";
import { useAuth } from "@/lib/auth";

export default function LoginPage() {
  const { user, hydrated } = useAuth();
  const router = useRouter();

  // Already signed in? Skip the login screen and go to the right dashboard.
  useEffect(() => {
    if (hydrated && user) {
      router.replace(user.role === "admin" ? "/admin/dashboard" : "/student/dashboard");
    }
  }, [hydrated, user, router]);

  return (
    <AuthLayout>
      <LoginCard />
    </AuthLayout>
  );
}
