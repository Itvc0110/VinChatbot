"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useI18n } from "@/lib/i18n";
import {
  IconShield,
  IconTicket,
  IconDatabase,
  IconCalendar,
  IconBell,
  IconChart,
} from "./icons";

// Academic Horizon admin chrome: a left sidebar (DESIGN.md §12). Admin is NOT forced into the
// student horizontal nav. Links use the Stitch screen names over the EXISTING routes (ROUTES.md);
// the active item gets a brand-red indicator (.ah-sidebar-link.active::before). Standalone for
// now; wired into AdminLayout in Phase 3.

interface NavItem {
  href: string;
  label: string;
  icon: React.ReactNode;
}

const STR = {
  en: {
    adminConsole: "Admin Console",
    admin: "Admin",
    dashboard: "Dashboard",
    tickets: "Tickets",
    knowledgeBase: "Knowledge Base",
    events: "Events",
    notifications: "Notification Management",
    monitoring: "Monitoring",
  },
  vi: {
    adminConsole: "Trang quản trị",
    admin: "Quản trị",
    dashboard: "Bảng điều khiển",
    tickets: "Yêu cầu hỗ trợ",
    knowledgeBase: "Cơ sở tri thức",
    events: "Sự kiện",
    notifications: "Quản lý thông báo",
    monitoring: "Giám sát",
  },
} as const;

function isActive(pathname: string, href: string): boolean {
  return pathname === href || pathname.startsWith(href + "/");
}

export function AdminSidebar({
  open = false,
  onNavigate,
}: {
  open?: boolean;
  onNavigate?: () => void;
}) {
  const pathname = usePathname();
  const { lang } = useI18n();
  const s = STR[lang];

  const ADMIN_PRIMARY: NavItem[] = [
    { href: "/admin/dashboard", label: s.dashboard, icon: <IconShield /> },
    { href: "/admin/tickets", label: s.tickets, icon: <IconTicket /> },
    { href: "/admin/sources", label: s.knowledgeBase, icon: <IconDatabase /> },
    { href: "/admin/events", label: s.events, icon: <IconCalendar /> },
    { href: "/admin/notifications", label: s.notifications, icon: <IconBell /> },
    { href: "/admin/analytics", label: s.monitoring, icon: <IconChart /> },
  ];

  const renderItem = (item: NavItem) => {
    const active = isActive(pathname, item.href);
    return (
      <li key={item.href}>
        <Link
          href={item.href}
          className={`ah-sidebar-link ${active ? "active" : ""}`}
          aria-current={active ? "page" : undefined}
          onClick={onNavigate}
        >
          <span aria-hidden>{item.icon}</span>
          {item.label}
        </Link>
      </li>
    );
  };

  return (
    <aside className={`ah-sidebar ${open ? "open" : ""}`}>
      <div className="ah-sidebar-brand">
        <span className="ah-sidebar-badge">
          <IconShield size={20} />
        </span>
        {s.adminConsole}
      </div>
      <nav className="ah-sidebar-nav" aria-label={s.admin}>
        <ul>{ADMIN_PRIMARY.map(renderItem)}</ul>
      </nav>
    </aside>
  );
}
