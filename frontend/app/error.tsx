"use client";

import Link from "next/link";
import { AuthLayout } from "@/components/layouts/AuthLayout";
import { usePortal } from "@/lib/portalI18n";
import { IconAlert } from "@/components/shell/icons";

// Root error boundary (App Router). Must be a Client Component; receives the thrown error and a
// `reset()` to retry the failed segment. Branded to match the 404 / auth frame. Bilingual.
const STR = {
  en: {
    title: "Something went wrong",
    desc: "We couldn't load this page. Please try again — if it keeps happening, head back to your dashboard.",
    retry: "Try again",
    home: "Go to dashboard",
  },
  vi: {
    title: "Đã có lỗi xảy ra",
    desc: "Chúng tôi không tải được trang này. Vui lòng thử lại — nếu vẫn lỗi, hãy quay về trang chính.",
    retry: "Thử lại",
    home: "Về trang chính",
  },
} as const;

export default function GlobalError({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  const { lang } = usePortal();
  const s = STR[lang];
  return (
    <AuthLayout>
      <div className="errpage" role="alert">
        <span className="errpage-badge danger" aria-hidden="true">
          <IconAlert size={26} />
        </span>
        <h1 className="errpage-title">{s.title}</h1>
        <p className="errpage-desc">{s.desc}</p>
        <div className="errpage-actions">
          <button type="button" className="ah-btn-primary-full errpage-btn" onClick={() => reset()}>
            {s.retry}
          </button>
          <Link className="ah-btn-outline-full errpage-btn" href="/">
            {s.home}
          </Link>
        </div>
      </div>
    </AuthLayout>
  );
}
