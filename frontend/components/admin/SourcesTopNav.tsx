"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { usePortal } from "@/lib/portalI18n";
import {
  IconDatabase,
  IconInbox,
  IconSliders,
  IconUpload,
} from "@/components/shell/icons";

const STR = {
  en: {
    label: "Knowledge source sections",
    sources: "Sources",
    upload: "Upload",
    unanswered: "Review queue",
    context: "Context",
  },
  vi: {
    label: "Các mục nguồn tri thức",
    sources: "Nguồn tri thức",
    upload: "Upload",
    unanswered: "Hàng đợi duyệt",
    context: "Ngữ cảnh",
  },
} as const;

function isActive(pathname: string, href: string) {
  if (href === "/admin/sources") return pathname === href;
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function SourcesTopNav() {
  const pathname = usePathname();
  const { lang } = usePortal();
  const s = STR[lang];
  const items = [
    { href: "/admin/sources", label: s.sources, icon: <IconDatabase size={15} /> },
    { href: "/admin/sources/upload", label: s.upload, icon: <IconUpload size={15} /> },
    { href: "/admin/sources/unanswered", label: s.unanswered, icon: <IconInbox size={15} /> },
    { href: "/admin/sources/context", label: s.context, icon: <IconSliders size={15} /> },
  ];

  return (
    <nav className="asrc-topnav" aria-label={s.label}>
      {items.map((item) => {
        const active = isActive(pathname, item.href);
        return (
          <Link
            key={item.href}
            href={item.href}
            className={`asrc-tab ${active ? "active" : ""}`}
            aria-current={active ? "page" : undefined}
          >
            <span className="asrc-tab-icon" aria-hidden>
              {item.icon}
            </span>
            <span>{item.label}</span>
          </Link>
        );
      })}
    </nav>
  );
}
