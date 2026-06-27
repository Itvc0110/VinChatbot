# ROUTES.md — Stitch screens → app routes & component files

> **Stitch project:** "Remix of Remix of Modern Dashboard Interface Redesign"
> (`projects/6914088917729920463`). The 16 screen labels below are taken verbatim from the project's
> `screenInstances[].label` (authoritative). Component/route paths are from the completed repo
> inspection (Next.js 14 App Router, `@/*` → `frontend/`).
>
> **Routing decision (applied):** **Keep existing repo routes** for safety — they are wired to nav,
> auth guards, mock API, and i18n. **UI / nav labels must match the Stitch screen names**; the Stitch
> label is a **display alias over the existing route**, not a URL rename. Examples: nav label
> **"Tickets" → `/student/support`**, **"Calendar" → `/student/schedule`**, **"Knowledge Base" →
> `/admin/sources`**, "Vinnie AI" → `/student/chat`, "Review Queue" → `/admin/unanswered`,
> "Monitoring" → `/admin/analytics`. **Do not rename working routes** unless redirects are explicitly
> added later. New routes are created only for screens that have **no** existing page.

Legend: ✅ exists · 🟡 partial (exists but not a dedicated page) · ➕ new route to create

---

## Student screens (6)

| # | Stitch screen (label) | Stitch screen ID | Route | Page file | Status | Key components |
|---|---|---|---|---|---|---|
| 1 | **Login** | `4476b2f41cc24c02a9a36aea6a53000d` | `/login` | `frontend/app/login/page.tsx` | ✅ | `auth/LoginCard`, `layouts/AuthLayout`, `ui/primitives` (Card, Button, Input) |
| 2 | **Student Dashboard** | `2cf0bdf5793248d5ad9065f7c6748353` | `/student/dashboard` | `frontend/app/student/dashboard/page.tsx` | ✅ | `layouts/StudentLayout`, `ui/primitives` (PageHeader, StatCard, Card), `portal/rows` (ClassSessionRow, DeadlineRow), `chat/FloatingVinnieButton` |
| 3 | **Student Tickets** | `a71c00c9470c4f72aa15c0e610705c08` | `/student/support` *(alias: Tickets)* | `frontend/app/student/support/page.tsx` | ✅ | `tickets/TicketList`, `tickets/TicketCard`, `tickets/TicketBadge`, `tickets/CreateTicketModal`, `tickets/TicketDetailDrawer`, `tickets/TicketFilters` |
| 4 | **Student Calendar** | `ef5d73630ded4eb7b015feb924db4f13` | `/student/schedule` *(alias: Calendar)* | `frontend/app/student/schedule/page.tsx` | ✅ | `calendar/CalendarView`, `calendar/CalendarEventCard`, `calendar/EventDetailDrawer` |
| 5 | **Student Events** | `b21e4dbbb3544e9d9b955b3ac516470e` | `/student/events` | `frontend/app/student/events/page.tsx` | ➕ (today partial inside `schedule`) | new `EventsGrid` / reuse `calendar/CalendarEventCard`, `calendar/EventDetailDrawer`, `ui/primitives` |
| 6 | **Student Vinnie AI** | `0ba36c1be6634ebe8f47f581250b93b1` | `/student/chat` *(alias: Vinnie AI)* | `frontend/app/student/chat/page.tsx` | ✅ | `ChatColumn`, `MessageBubble`, `Composer`, `SourceDrawer`, `ChatCitationList`, `chat/ConversationRail`, `chat/FollowUpSuggestions`, `chat/StreamingStatus`, `chat/StudentChatOverlays` |

---

## Admin screens (10)

| # | Stitch screen (label) | Stitch screen ID | Route | Page file | Status | Key components |
|---|---|---|---|---|---|---|
| 7 | **Admin Dashboard** | `f632dd65ef3e4b5d87d5532be1e72618` | `/admin/dashboard` | `frontend/app/admin/dashboard/page.tsx` | ✅ | `layouts/AdminLayout`, `ui/primitives` (StatCard, Card, PageHeader, EmptyState), `portal/rows` |
| 8 | **Admin Tickets** | `d98f73cef9154f978f14793029df71e9` | `/admin/tickets` | `frontend/app/admin/tickets/page.tsx` | ✅ | `tickets/TicketBoard`, `tickets/TicketColumn`, `tickets/TicketCard`, `tickets/ReviewTicketDrawer`, `tickets/TicketFilters` |
| 9 | **Admin Knowledge Base** | `a40108e51c0a41088389bfbef49defc5` | `/admin/sources` *(alias: Knowledge Base)* | `frontend/app/admin/sources/page.tsx` | ✅ | `SourceCard`, `SourceDrawer`, `ui/primitives` (PageHeader, Card, Badge), table (§10 of DESIGN.md) |
| 10 | **Admin Upload Source** | `fe65bf545f684475a1e3ddc2268bc7d0` | `/admin/upload` | `frontend/app/admin/upload/page.tsx` | ✅ | `ui/primitives` (Card, Input, Button, AsyncBoundary, Toast); calls `/api/ingest/run` |
| 11 | **Admin Review Queue** | `084fd6a270eb49f7a9d8767040fc735f` | `/admin/unanswered` (+ `/admin/unanswered/[id]`) *(alias: Review Queue)* | `frontend/app/admin/unanswered/page.tsx`, `.../[id]/page.tsx` | ✅ | `StateChip`, `FlagForm`, `portal/AnswerActions`, `ui/primitives`, table (§10) |
| 12 | **Admin Context** | `1f8a4f0130fb4b51a26e5706255405fa` | `/admin/context` | `frontend/app/admin/context/page.tsx` | ➕ | new `ContextManager` (personalization rules editor), `ui/primitives` (Card, Input, Badge, Button) |
| 13 | **Admin Events** | `12ecde1437fb4017ac96891c2dd8ce8b` | `/admin/events` | `frontend/app/admin/events/page.tsx` | ➕ | new `EventsManager` (CRUD table + form), reuse `calendar/*`, `ui/primitives`, table (§10) |
| 14 | **Admin Notifications** | `ec3b82774b0f4d0c9322caf22ad4ffb8` | `/admin/notifications` | `frontend/app/admin/notifications/page.tsx` | ✅ | `notifications/NotificationList`, `notifications/NotificationFilters`, slide-out panel + status stripe (DESIGN.md §12), `ui/primitives` |
| 15 | **Admin Vinnie AI Monitoring** | `a3b4396899804d528e0d9c92359115f8` | `/admin/analytics` *(alias: Monitoring)* | `frontend/app/admin/analytics/page.tsx` | ✅ | `ui/primitives` (StatCard, Card), charts/metrics (cost, latency, coverage, errors), table (§10) |
| 16 | **Admin Settings** | `8c2ae3bffb314a33a1b604999d8533dd` | `/admin/settings` | `frontend/app/admin/settings/page.tsx` | ➕ | new `SettingsPanel` (sectioned form), `ui/primitives` (Card, Input, Button, Badge) |

> ⚠️ The repo inspection had tentatively treated `/admin/logs` as a "settings proxy." That is **not**
> the Stitch "Admin System Settings" screen — Settings is a distinct page (➕ above). Keep
> `/admin/logs` as-is; it is outside the 16-screen set.

---

## Shells (role-specific — decision applied)

Login uses a **centered auth layout** (no nav). Student uses a **horizontal top nav**. Admin uses a
**left sidebar + top admin header**. Build the student and admin shells as **separate** components —
do **not** force admin pages into the student layout.

| Concern | Component file | Status | Notes |
|---|---|---|---|
| Auth layout (Login) | `frontend/components/layouts/AuthLayout.tsx` | ✅ exists | centered card frame; no nav |
| Student shell wrapper | `frontend/components/layouts/StudentLayout.tsx` | ✅ exists | composes `StudentTopNav` + centered content container |
| **Student top nav** | `frontend/components/shell/StudentTopNav.tsx` | ➕ new (extract from `TopBar`/`Sidebar`) | horizontal bar: logo · Stitch-labeled links · bell · profile; 2px red active underline; mobile hamburger/scroll-chips |
| Admin shell wrapper | `frontend/components/layouts/AdminLayout.tsx` | ✅ exists | composes `AdminSidebar` + `AdminHeader` + content |
| **Admin sidebar** | `frontend/components/shell/AdminSidebar.tsx` | ➕ new (extract from `Sidebar`) | left vertical nav; brand-red active indicator |
| **Admin header** | `frontend/components/shell/AdminHeader.tsx` | ➕ new (extract from `TopBar`) | top header: page title, global actions, bell, profile |
| (existing) RoleShell | `frontend/components/layouts/RoleShell.tsx` | ♻️ refactor/retire | split into the role-specific shells above |
| (existing) Sidebar / TopBar | `frontend/components/shell/Sidebar.tsx`, `TopBar.tsx` | ♻️ source | reuse logic when extracting the new shells |
| Icons | `frontend/components/shell/icons.tsx` | ✅ exists | icon set |
| Auth guard | `frontend/components/auth/ProtectedRoute.tsx` | ✅ exists | role-based redirect; applied in `student/layout.tsx` & `admin/layout.tsx` |
| Primitives | `frontend/components/ui/primitives.tsx` | ✅ exists | PageHeader, SectionHeader, Card, StatCard, Badge, EmptyState, Toast, AsyncBoundary |

---

## Routes that exist but are **outside** the 16-screen scope (leave untouched)

| Route | Page file | Note |
|---|---|---|
| `/` | `frontend/app/page.tsx` | role-based redirect entry |
| `/403` | `frontend/app/403/page.tsx` | forbidden |
| `/student/notifications` | `frontend/app/student/notifications/page.tsx` | student inbox (not in the 16) |
| `/student/tuition` | `frontend/app/student/tuition/page.tsx` | tuition/fees (not in the 16) |
| `/admin/logs` | `frontend/app/admin/logs/page.tsx` | structured logs viewer (not in the 16) |

---

## Summary

- **16 Stitch screens** → **12 existing routes** (some via alias) + **4 new routes** to create:
  `/student/events`, `/admin/context`, `/admin/events`, `/admin/settings`.
- **Alias-only (no rename):** `support`=Tickets, `schedule`=Calendar, `chat`=Vinnie AI,
  `sources`=Knowledge Base, `unanswered`=Review Queue, `analytics`=Monitoring.
- **Shells:** Login → `AuthLayout` (centered); Student screens → `StudentTopNav`; Admin screens →
  `AdminSidebar` + `AdminHeader` (built separately — admin is **not** forced into the student nav).
