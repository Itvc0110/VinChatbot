"use client";

import { AuthLayout } from "@/components/layouts/AuthLayout";
import { AccessDenied } from "@/components/auth/AccessDenied";

export default function ForbiddenPage() {
  return (
    <AuthLayout>
      <AccessDenied />
    </AuthLayout>
  );
}
