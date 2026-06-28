"use client";

import Link from "next/link";
import { AuthLayout } from "@/components/layouts/AuthLayout";
import { usePortal } from "@/lib/portalI18n";
import { IconCap } from "@/components/shell/icons";

// Branded 404 for any unmatched route. Rendered inside the root layout (Providers available),
// so it reuses the centered Academic Horizon auth frame + tokens. Bilingual via the active UI lang.
const STR = {
  en: {
    title: "Page not found",
    desc: "The page you're looking for doesn't exist or may have moved. Let's get you back on track.",
    home: "Go to dashboard",
    login: "Sign in",
  },
  vi: {
    title: "Không tìm thấy trang",
    desc: "Trang bạn tìm không tồn tại hoặc đã được di chuyển. Hãy quay lại để tiếp tục nhé.",
    home: "Về trang chính",
    login: "Đăng nhập",
  },
} as const;

export default function NotFound() {
  const { lang } = usePortal();
  const s = STR[lang];
  return (
    <AuthLayout>
      <div className="errpage" role="alert">
        <span className="errpage-badge" aria-hidden="true">
          <IconCap size={26} />
        </span>
        <div className="errpage-code">404</div>
        <h1 className="errpage-title">{s.title}</h1>
        <p className="errpage-desc">{s.desc}</p>
        <div className="errpage-actions">
          <Link className="ah-btn-primary-full errpage-btn" href="/">
            {s.home}
          </Link>
          <Link className="ah-btn-outline-full errpage-btn" href="/login">
            {s.login}
          </Link>
        </div>
      </div>
    </AuthLayout>
  );
}
