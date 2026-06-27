# IMPLEMENTATION_PLAN.md — Academic Horizon rollout

> **Goal:** restyle the existing VinChatbot frontend to the Stitch **Academic Horizon** design system
> (`DESIGN.md`) and fill the 4 missing screens (`ROUTES.md`), without breaking the working app
> (auth, chat streaming, mock API, i18n, dark mode).
>
> **Scope of THIS document:** ordering and dependencies only. No UI is implemented and no existing
> page is modified in this phase — that begins after the open decisions in §1 are resolved.
>
> **Stack recap:** Next.js 14.2.35 (App Router), React 18.3.1, TypeScript (strict), **pure CSS
> design tokens** (`frontend/app/globals.css` + `portal.css`) — *no Tailwind*. Path alias `@/*` →
> `frontend/`. Fonts via `next/font` (Inter + JetBrains Mono today).

---

## Implementation control rules (must follow)

- **Stop after each phase for review.** Do **not** implement all 16 screens in one batch. Build
  **phase by phase** (Phase 0.0 → 0 → 1 → 2 → 3 → 4 → 5) and **pause for review at the end of each
  phase** before starting the next.
- **No bulk Stitch fetching.** Do **not** bulk-fetch screens. Call `get_screen` **one screen at a
  time, immediately before implementing that specific screen** (screen IDs are in ROUTES.md). The only
  pre-fetch is the shared table style, verified against **Admin Tickets** just before Phase 1.6.

---

## Guiding principles

1. **Token-first.** Introduce Academic Horizon as CSS variables; restyle by swapping class values, not
   rewriting component logic. The app's behavior (streaming, guards, mock data) stays intact.
2. **Additive, not destructive.** Add `--ah-*` tokens and a Hanken Grotesk font next to existing
   tokens first; flip components over incrementally. Keep dark mode as an extension.
3. **One screen verified at a time.** Because we deliberately did **not** deep-fetch all screens, each
   screen's pixel specifics (tables, exact nav contents, spacing) are confirmed with a **single**
   `get_screen` immediately before that screen is built — never a bulk fetch.
4. **Don't rename working routes.** Use Stitch labels as display aliases (see ROUTES.md).

---

## §1. Open decisions to resolve BEFORE coding

These change the shape of the work; surfaced here rather than guessed.

- **§1.A — Navigation paradigm — ✅ RESOLVED (role-specific).**
  - **Login:** centered shared **auth layout** (`layouts/AuthLayout`) — no portal nav.
  - **Student portal:** Stitch-style **horizontal top navigation** (`shell/StudentTopNav`).
  - **Admin portal:** **left sidebar + top admin header** (`shell/AdminSidebar` + `shell/AdminHeader`),
    matching the current admin Stitch screens. **Do not** force admin pages into the student layout.
  - Build the student and admin shells **separately**; refactor/retire the shared `RoleShell`.
    Academic Horizon tokens/type/spacing apply to all three.
- **§1.B — Primary red.** Align repo `--primary #b0182c` → Academic Horizon brand **`#B92026`**
  (action/dark `#950013`). Recommended: yes.
- **§1.C — Radius.** Tighten card/button radius from 10–14px → **8px/4px**. Recommended: yes.
- **§1.D — Breakpoints.** Move from the single 720px breakpoint → **768 / 1024 / 1280**. Recommended: yes.
- **§1.E — Dark mode.** Academic Horizon is light-only. Keep the existing dark theme as an
  extension (derive dark `--ah-*` values), or descope dark for the restyle. Recommended: keep.
- **§1.F — Route policy — ✅ APPLIED.** Keep existing repo routes; **UI / nav labels = Stitch screen
  names** (display alias over the route, e.g. "Tickets" → `/student/support`, "Calendar" →
  `/student/schedule`, "Knowledge Base" → `/admin/sources`). **No route renames** unless redirects are
  added later. Full mapping in **ROUTES.md**.

> §1.A and §1.F are resolved, so Phase 1 (incl. the shells) can proceed. §1.B–§1.E are adopted as the
> recommended defaults unless you say otherwise.

---

## §2. Implementation order

### Phase 0.0 — Backup & branching (run FIRST; no UI code yet)
Goal: preserve the current UI state on a backup branch, then do all redesign work on a feature branch.
Commit **source only** — never secrets, `.env*`, `node_modules/`, build output (`.next/`, `out/`,
`dist/`), or temp/scratch files.

0.0.1 **Review:** `git status` (the working tree currently has uncommitted changes across `frontend/`
      and `vinchatbot/`). Confirm `.gitignore` already excludes env/deps/build/temp; if anything
      sensitive is untracked, do **not** stage it.
0.0.2 **Preserve current UI state on a backup branch:**
      `git switch -c backup/before-stitch-ui-redesign`
0.0.3 **Commit the current UI state** on the backup branch (stage source files only):
      `git add <source paths>` → `git commit -m "chore: snapshot UI before Stitch Academic Horizon redesign"`
0.0.4 **Create + switch to the feature branch** (branches from the snapshot so the redesign builds on it):
      `git switch -c feature/stitch-academic-horizon-ui`
0.0.5 **Verify:** `git status` shows you are on `feature/stitch-academic-horizon-ui`.

> Sequencing note: branching the backup first, committing, then branching the feature from it
> guarantees `backup/before-stitch-ui-redesign` holds the exact pre-redesign UI. If you prefer to keep
> `dholmes` unchanged, instead commit the snapshot on `dholmes`, then `git branch
> backup/before-stitch-ui-redesign` and `git switch -c feature/stitch-academic-horizon-ui`.

### Phase 0 — Verification & setup (no UI yet)
0.1 Confirm decisions in §1 are settled (§1.A and §1.F are resolved).
0.2 Add **Hanken Grotesk** via `next/font` in `frontend/app/layout.tsx`; expose as `--ah-font-head`.
0.3 Add the `--ah-*` token block (DESIGN.md §15) to `globals.css` (additive; nothing consumes it yet).
0.4 Establish a tiny visual proof on a throwaway/storybook-style scratch (optional) — verify red,
    radius, fonts render before touching real pages.

### Phase 1 — Foundations (shared; build in THIS order)
1.1 **Tokens** — finalize `--ah-*` light values in `globals.css`; derive dark values if §1.E = keep.
1.2 **Primitives** (`ui/primitives.tsx`) — bring `Card`, `Button`, `Badge`/chip, `Input`, `StatCard`,
    `PageHeader`, `SectionHeader`, `EmptyState`, `Toast` to Academic Horizon (color/radius/border/type).
1.3 **Auth layout** (`layouts/AuthLayout`) — centered card frame for Login (DESIGN.md §11.1).
1.4 **StudentTopNav** (`shell/StudentTopNav.tsx`) — horizontal top nav (logo · Stitch-labeled links ·
    bell · profile; 2px red active underline; mobile hamburger/scroll-chips, DESIGN.md §13). Wire into
    `layouts/StudentLayout`.
1.5 **AdminSidebar + AdminHeader** (`shell/AdminSidebar.tsx`, `shell/AdminHeader.tsx`) — left sidebar +
    top header, built **separately** from the student nav. Wire into `layouts/AdminLayout`.
    Refactor/retire `RoleShell`.
1.6 **Table style** (DESIGN.md §10) — shared table style/component; verify first against
    **Admin Tickets** (single `get_screen d98f73cef9154f978f14793029df71e9`).

> Phases 2–3 restyle existing pages (low risk; structure already correct). Phase 4 builds the 4 new
> pages. Order within each phase is "simplest / most isolated first → validates the system early."

### Phase 2 — Login + Student portal (existing pages; uses `StudentTopNav`)
2.1 **Login** (`/login`) — uses the centered `AuthLayout` (no nav); validates tokens, inputs, buttons.
2.2 **Student Dashboard** (`/student/dashboard`) — exercises StatCard/Card/rows under `StudentTopNav`.
2.3 **Student Vinnie AI** (`/student/chat`) — highest-value screen; restyle chat/sources/composer to
    Academic Horizon while preserving streaming (verify-then-reveal) behavior. **Do not touch logic.**
2.4 **Student Calendar** (`/student/schedule`) — calendar grid + left-accent "today/urgent" bar (§6).
2.5 **Student Tickets** (`/student/support`) — list/card/badge/drawer + chips (§8).

### Phase 3 — Admin portal (existing pages; uses `AdminSidebar` + `AdminHeader`)
3.1 **Admin Dashboard** (`/admin/dashboard`) — stat cards, data density.
3.2 **Admin Tickets** (`/admin/tickets`) — Kanban board + review drawer + table style.
3.3 **Admin Knowledge Base** (`/admin/sources`) — source cards/table + drawer.
3.4 **Admin Upload Source** (`/admin/upload`) — form + async/toast states (live `/api/ingest/run`).
3.5 **Admin Review Queue** (`/admin/unanswered` + `[id]`) — StateChip, FlagForm, answer actions.
3.6 **Admin Notifications** (`/admin/notifications`) — slide-out panel + left status stripe (§12).
3.7 **Admin Vinnie AI Monitoring** (`/admin/analytics`) — metric cards + charts/tables.

### Phase 4 — New screens (no existing page; build last)
4.1 **Student Events** (`/student/events`) — currently partial inside schedule; promote to its own
    page (events grid + detail drawer). Verify against `b21e4dbbb3544e9d9b955b3ac516470e`.
4.2 **Admin Events** (`/admin/events`) — CRUD table + form. Verify `12ecde1437fb4017ac96891c2dd8ce8b`.
4.3 **Admin Context** (`/admin/context`) — personalization rules editor. Verify `1f8a4f0130fb4b51a26e5706255405fa`.
4.4 **Admin Settings** (`/admin/settings`) — sectioned settings form. Verify `8c2ae3bffb314a33a1b604999d8533dd`.
    (Add nav entries for the 4 new routes in the shell as each lands.)

### Phase 5 — Polish & QA
5.1 Responsive pass at 1280 / 1024 / 768 / mobile (DESIGN.md §13).
5.2 Cross-screen consistency audit (chips, table headers, focus states, hover shadow).
5.3 Dark-mode pass (if §1.E = keep).
5.4 Accessibility: focus-visible (red glow), contrast on tints, keyboard nav for drawers/panels.
5.5 Regression check: auth guards, chat streaming, mock API, i18n (vi/en) all still work.

---

## §3. Dependency graph (what blocks what)

```
Phase 0.0 (backup + feature branch)
  └► §1 decisions ──► Phase 0 (Hanken font + --ah-* tokens)
       └► 1.1 tokens ──► 1.2 primitives ──┬► 1.3 AuthLayout ─────────► 2.1 Login
                                          ├► 1.4 StudentTopNav ──────► 2.2–2.5 Student pages
                                          ├► 1.5 AdminSidebar+Header ► Phase 3 Admin pages
                                          └► 1.6 table style ◄── get_screen(Admin Tickets)
                                                 │
       Phase 2 (Login + Student) ──► Phase 3 (Admin) ──► Phase 4 (4 new) ──► Phase 5 (QA)
```

- **Phase 0.0 must run first** — backup branch + feature branch before any code changes.
- **Login (2.1)** depends on tokens (1.1) + primitives (1.2) + `AuthLayout` (1.3) only — no portal nav.
- **Student pages** depend on `StudentTopNav` (1.4); **Admin pages** depend on `AdminSidebar` +
  `AdminHeader` (1.5). The two shells are independent and can be built in parallel.
- New pages (Phase 4) additionally depend on a per-screen `get_screen` verification.

---

## §4. Risk register

| Risk | Mitigation |
|---|---|
| Nav rework touches every page | §1.A resolved into **two independent shells** (`StudentTopNav`, `AdminSidebar`+`AdminHeader`); changes isolated to those + the role layout wrappers. |
| Committing secrets/deps/build during Phase 0.0 | Stage **source only**; rely on `.gitignore` for `.env*`, `node_modules/`, `.next/`/`out/`/`dist/`, temp/scratch; snapshot lives on `backup/before-stitch-ui-redesign`. |
| Breaking chat streaming while restyling 2.3 | Restyle markup/classes only; never touch `lib/chat.tsx` / SSE logic. Regression-test after. |
| Table specifics unknown (DESIGN.md §10 is derived) | `get_screen` Admin Tickets before 1.6; reuse style everywhere. |
| Token swap regresses dark mode | Derive `--ah-*` dark values; QA in Phase 5.3. |
| Route-name confusion (Stitch label vs repo path) | Follow ROUTES.md aliases; don't rename. |
| Hanken Grotesk load/FOUT | `next/font` with `display: swap`; preload head font. |
| Scope creep into out-of-16 pages (tuition, logs, student notifications) | Explicitly left untouched (ROUTES.md). |

---

## §5. Definition of done (per screen)

- Matches the Academic Horizon tokens (color/type/spacing/radius/elevation) from `DESIGN.md`.
- Verified against its Stitch screen via a single `get_screen` (id in ROUTES.md).
- Responsive at 1280/1024/768/mobile.
- No behavior regressions (auth, streaming, mock API, i18n, theme).
- Uses shared primitives/shell — no one-off color/radius literals.
