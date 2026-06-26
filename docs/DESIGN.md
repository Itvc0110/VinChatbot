# DESIGN.md — Academic Horizon Design System

> **Source of truth:** Stitch project **"Remix of Remix of Modern Dashboard Interface Redesign"**
> (`projects/6914088917729920463`), design theme **"Academic Horizon"**.
> Extracted from the project `designMd` + theme tokens (`get_project`). Last Stitch update: `2026-06-24T11:41:13Z`.
>
> **Honesty note:** Sections marked **[Stitch spec]** come verbatim from the Academic Horizon
> `designMd`/theme tokens. Sections marked **[Derived]** are reasoned from the design language
> because the Stitch spec does not document them explicitly (e.g. tables). Verify *[Derived]* items
> against the relevant screen (one `get_screen` at a time) before/while implementing that screen.
>
> See **`IMPLEMENTATION_PLAN.md`** for how this maps onto the existing repo (which currently ships a
> *different* token set + sidebar shell) and the open reconciliation decisions.

---

## 0. Brand & personality [Stitch spec]

High-performance university student dashboard that balances the prestige of a traditional academic
institution with the speed/clarity of a modern AI copilot. Personality: **authoritative yet supportive**.
Aesthetic: **Modern Corporate**, "Swiss-style" minimalism — heavy whitespace, crisp 1px borders, a
limited high-impact palette, information density over decoration. **Navigation is role-specific**
(decision applied — see §11/§12): **Login** uses a centered shared auth layout (no nav); the
**Student portal** uses a fixed **horizontal top navigation** bar; the **Admin portal** uses a **left
sidebar + top admin header** matching the admin Stitch screens. Academic Horizon tokens/type/spacing
apply uniformly across all three.

---

## 1. Colors [Stitch spec]

### 1.1 Brand / primary

| Token | Hex | Use |
|---|---|---|
| `primary` | `#950013` | Darkest brand red — primary action text/icon, strongest emphasis |
| `primary-container` / **brand red** | `#B92026` | The signature heritage red — primary buttons, branding, active indicators, critical notifications |
| `on-primary` | `#FFFFFF` | Text/icon on primary |
| `on-primary-container` | `#FFCFCA` | Text on primary-container |
| `surface-tint` | `#B81F25` | Tint overlay |
| `inverse-primary` | `#FFB3AD` | Primary on dark surfaces |
| `primary-fixed` | `#FFDAD7` | Light red tint (chip backgrounds) |
| `on-primary-fixed` | `#410004` | Dark red text (on tint) |
| `on-primary-fixed-variant` | `#930013` | Dark red text variant |

> Prose also calls out **Deep Navy/Black `#111827`** (`overrideSecondaryColor`) for high-contrast
> primary text headings, with slate grays for secondary info.

### 1.2 Surfaces & background

| Token | Hex | Use |
|---|---|---|
| `background` / `surface` | `#FBF9F6` | Page background (warm off-white; prose approximates as `#F7F5F2`) |
| `surface-container-lowest` | `#FFFFFF` | **Card / panel / nav surface** (pure white, layered on the warm bg) |
| `surface-container-low` | `#F5F3F0` | Subtle raised fill |
| `surface-container` | `#EFEEEB` | Section fill |
| `surface-container-high` | `#EAE8E5` | Hover fill |
| `surface-container-highest` | `#E4E2DF` | Strongest neutral fill |
| `surface-dim` | `#DBDAD7` | Dimmed surface |
| `inverse-surface` | `#30312F` | Tooltips / inverse chips |
| `inverse-on-surface` | `#F2F0ED` | Text on inverse |

### 1.3 Text & lines

| Token | Hex | Use |
|---|---|---|
| `on-surface` | `#1B1C1A` | Primary text |
| `on-surface-variant` | `#5B403E` | Secondary text (warm) |
| `text-muted` | `#6B7280` | Muted/metadata text (cool gray) |
| `outline` | `#8F706D` | Default outline |
| `outline-variant` | `#E3BEBB` | Soft outline |
| `border-light` | `#E5E7EB` | **Hairline border for cards / inputs / nav / table rows** |

### 1.4 Secondary / tertiary / status

| Token | Hex | Use |
|---|---|---|
| `secondary` | `#575E70` | Slate accent |
| `secondary-container` | `#D9DFF5` | Slate tint |
| `tertiary` | `#004D6C` | Deep teal accent |
| `tertiary-container` | `#00668E` | Teal mid |
| `error` / `danger` | `#BA1A1A` | Error |
| `error-container` | `#FFDAD6` | Error tint bg |
| `on-error-container` | `#93000A` | Error text on tint |
| `status-info` | `#3B82F6` | Info (notification stripe) |
| `status-success` | `#10B981` | Success (notification stripe) |

---

## 2. Typography [Stitch spec]

**Pairing:** **Hanken Grotesk** for headlines (sharp, contemporary), **Inter** for body/labels
(legible at small sizes). Hierarchy is driven by strict weight differentiation. Labels use slightly
increased letter-spacing (and often uppercase) for metadata/category headers.

| Style | Family | Size | Weight | Line height | Tracking |
|---|---|---|---|---|---|
| `display-lg` | Hanken Grotesk | 48px | 700 | 56px | -0.02em |
| `headline-lg` | Hanken Grotesk | 32px | 600 | 40px | -0.01em |
| `headline-lg-mobile` | Hanken Grotesk | 28px | 600 | 36px | — |
| `headline-md` | Hanken Grotesk | 24px | 600 | 32px | — |
| `headline-sm` | Hanken Grotesk | 20px | 600 | 28px | — |
| `body-lg` | Inter | 18px | 400 | 28px | — |
| `body-md` | Inter | 16px | 400 | 24px | — |
| `body-sm` | Inter | 14px | 400 | 20px | — |
| `label-md` | Inter | 14px | 600 | 20px | 0.02em |
| `label-sm` | Inter | 12px | 500 | 16px | — |

> **Repo gap:** the app currently loads Inter + JetBrains Mono via `next/font` — **Hanken Grotesk is
> not loaded yet**. It must be added (see IMPLEMENTATION_PLAN §1). JetBrains Mono has no Academic
> Horizon equivalent; keep it for code/log/monospace contexts only.

---

## 3. Spacing & grid [Stitch spec]

- **Vertical rhythm:** strict **8px base**.
- **Scale tokens:** `stack-sm` 8px · `stack-md` 16px · `stack-lg` 24px.
- **Container:** `container-max` **1280px**, centered.
- **Gutter:** `gutter` **24px**.
- **Outer margins:** `margin-desktop` **40px** · `margin-mobile` **16px** (tablet 24px — see §10).
- **Grid:** **12-column fixed** grid on desktop; content blocks span 4 / 6 / 12 columns.

---

## 4. Border radius [Stitch spec]

`roundness = ROUND_FOUR`. Shape language is **Soft (4–8px)**.

| Token | Value | Applied to |
|---|---|---|
| `rounded-sm` | 0.125rem (2px) | hairline detail |
| `rounded` (DEFAULT) | 0.25rem (**4px**) | **buttons, inputs, tags/chips** |
| `rounded-md` | 0.375rem (6px) | small containers |
| `rounded-lg` | 0.5rem (**8px**) | **cards, modal containers** |
| `rounded-xl` | 0.75rem (**12px**) | large featured dashboard banners |
| `rounded-full` | 9999px | avatars, toggles, pill chips |

---

## 5. Elevation & shadows [Stitch spec]

Avoids heavy shadows; relies on **tonal layers + low-contrast outlines**.

| Level | Treatment |
|---|---|
| **0 — Background** | Solid `#FBF9F6` (`/F7F5F2`). |
| **1 — Cards / Nav (default)** | White `#FFFFFF` + **1px `#E5E7EB` border, NO shadow**. Flat & organized. |
| **2 — Hover / Active** | Soft ambient shadow `0px 4px 20px rgba(0,0,0,0.04)` on cards/dropdowns. |
| **Overlays** | Modals/notifications dim the page with **8px backdrop blur**. |

---

## 6. Cards [Stitch spec]

- White `#FFFFFF` surface on the warm `#FBF9F6` background ("white-on-gray" contrast strategy).
- **1px `#E5E7EB` border, 8px radius, no default shadow**; soft shadow only on hover/active.
- In-card section headers use **`label-md`** (14/600/0.02em), often uppercase, for categorization.
- **Calendar/event cards:** a subtle **left-accent bar in primary red** marks "today" / "urgent" items.
- Padding: multiples of 8px (typically 16px or 24px); internal stacks use `stack-sm/md`.

---

## 7. Buttons [Stitch spec]

| Variant | Spec |
|---|---|
| **Primary** | Solid **brand red `#B92026`** fill, white text, **4px radius**. |
| **Secondary** | Outlined (1px border), transparent/white fill, brand-red or text-colored label. |
| Hover/active | Picks up the Level-2 soft shadow; primary may deepen toward `#950013`. |
| Shape | Clean, sharp 4px corners (precision / academic rigor). |
| Text | `label-md` (14/600). |

---

## 8. Chips & tags [Stitch spec]

- Used for **course codes** and **ticket status**.
- **Desaturated status colors**: light tint background + darker same-hue text
  (e.g. `primary-fixed #FFDAD7` bg + `on-primary-fixed-variant #930013` text for red).
- **4px radius** (tag rule) or pill (`rounded-full`) for status pills — match the source screen.
- Status hue mapping (derive bg/text pairs from §1):
  - urgent/error → red (`#FFDAD7` / `#930013`), info → blue (`status-info #3B82F6`),
    success → green (`status-success #10B981`), neutral → slate (`secondary #575E70`).

---

## 9. Inputs [Stitch spec]

- White background, **1px `#E5E7EB` border, 4px radius**.
- **Focus:** border becomes **1px solid brand red** + a subtle **2px low-opacity red outer glow**.
- Label uses `label-md`; helper/error text uses `body-sm` / `label-sm`.
- Error state: red border + `error`/`on-error-container` messaging.

---

## 10. Tables [Derived — no explicit Stitch spec]

> Not documented in `designMd`. Derive from the card/border/typography language; **verify against
> "Admin Tickets" (`d98f73cef9154f978f14793029df71e9`) and "Admin Knowledge Base"
> (`a40108e51c0a41088389bfbef49defc5`)** with a single `get_screen` when building those screens.

- Wrap the table in a white card (8px radius, 1px `#E5E7EB` border, no shadow).
- **Column headers:** `label-md` (14/600/0.02em), often uppercase, `text-muted #6B7280`, with a 1px
  `#E5E7EB` bottom divider.
- **Rows:** `body-sm`/`body-md`, 1px `#E5E7EB` bottom dividers; row height on the 8px rhythm
  (≈44–56px). Hover row tint = `surface-container-low #F5F3F0`.
- **Status cells:** render via the §8 chip, not raw text.
- **Row actions:** trailing icon buttons (ghost/secondary).
- Dense admin tables: tighter padding but keep 8px multiples.

---

## 11. Login & Student layouts

### 11.1 Login — centered shared auth layout [Decision applied]
Login renders **without** portal navigation: a single **centered card** on the warm `#FBF9F6` canvas
(`layouts/AuthLayout` + `auth/LoginCard`). White card, 8px radius, 1px `#E5E7EB` border, brand-red
primary button, focus-glow inputs (§7/§9). Used by `/login` (and reusable for any future auth pages).

### 11.2 Student portal — horizontal top navigation [Decision applied]
A **fixed horizontal top navigation bar** is the primary anchor: university logo at left → primary
links → right cluster of **notification bell + profile icon**. **Active link = 2px red bottom border.**
Content sits in the centered 12-col, 1280px container.

**[Derived — nav contents]** Student top-nav links inferred from the student screen set, labeled with
their **Stitch names**: **Dashboard · Vinnie AI · Calendar · Events · Tickets** (labels point to the
existing routes — see ROUTES.md). Card-driven experience (greeting, schedule snippet, deadlines,
notifications, quick-ask) over the warm `#FBF9F6` canvas. Confirm exact link order against
"Student Dashboard" (`2cf0bdf5793248d5ad9065f7c6748353`).

---

## 12. Admin layout — left sidebar + top admin header [Decision applied]

The admin portal does **not** use the student horizontal nav. It uses a **left sidebar** (primary
navigation) plus a **top admin header** (page title/breadcrumb, global actions, notification bell,
profile), matching the current admin Stitch screens. Academic Horizon tokens/type/spacing/borders apply
to both: white sidebar/header surfaces, 1px `#E5E7EB` separators, brand-red active indicator,
`label-md` nav text.

- **Sidebar:** fixed-width vertical nav; active item uses a brand-red indicator (left bar or filled
  pill — confirm per screen); links grouped by area.
- **Top admin header:** spans the content area to the right of the sidebar; holds the page header,
  global actions, notification bell, and profile.

**[Derived — nav contents]** Admin sidebar links (labeled with their **Stitch names**):
**Dashboard · Tickets · Knowledge Base · Events · Notifications · Monitoring · Settings**, with
**Upload Source · Review Queue · Context** reached from within Knowledge Base / Dashboard / Settings
(confirm nesting per screen). Admin is **more data-dense**: stat cards (`StatCard`), tables (§10),
Kanban ticket board, and a right **slide-out notification panel** with a left **status stripe**
(red=urgent, blue=info, green=success). Confirm against "Admin Dashboard"
(`f632dd65ef3e4b5d87d5532be1e72618`).

---

## 13. Responsive rules [Stitch spec]

| Breakpoint | Outer margin | Behavior |
|---|---|---|
| **Desktop ≥1280px** | 40px | Full 12-col grid; blocks span 4/6/12; 24px gutters. |
| **Tablet 768–1024px** | 24px | Cards reflow to **2-column**. |
| **Mobile ≤767px** | 16px | Horizontal nav collapses to a **condensed header with hamburger** *or* **scrollable horizontal chips** for sub-nav; headlines use the `-mobile` ramp. |

> **Repo note:** the current app uses a single 720px breakpoint (sidebar collapse / sources panel
> hide). Align to the 768 / 1024 / 1280 system above when restyling (see IMPLEMENTATION_PLAN §1).

---

## 14. Reconciliation with the existing repo tokens

The repo (`frontend/app/globals.css` + `portal.css`) already defines a **different** token set and a
**sidebar** shell. DESIGN.md is the *target*; these are the deltas to resolve (decisions live in
IMPLEMENTATION_PLAN §1):

| Concern | Academic Horizon (target) | Existing repo (current) | Action |
|---|---|---|---|
| Background | `#FBF9F6` | `--bg #faf9f7` | ✅ ~match, keep |
| Card surface | `#FFFFFF` | `--surface #ffffff` | ✅ match |
| Primary red | `#950013` / brand `#B92026` | `--primary #b0182c` | ⚠️ **align to `#B92026`** |
| Body text | `#1B1C1A` / `#111827` | `--foreground #1c1a17` | ✅ ~match |
| Hairline border | `#E5E7EB` | `--border rgba(28,26,23,.10)` | ⚠️ adopt `#E5E7EB` |
| Radius (card/btn) | 8px / 4px | 10–14px / 8px | ⚠️ **tighten to 8/4px** |
| Headline font | Hanken Grotesk | *(not loaded)* | ⚠️ **add `next/font` Hanken Grotesk** |
| Body font | Inter | Inter | ✅ match |
| Mono font | — | JetBrains Mono | keep for code/logs only |
| Nav paradigm | Login: centered auth · Student: horizontal top bar · Admin: sidebar + top header | 256px sidebar + topbar | ✅ **Decided** — `AuthLayout` / `StudentTopNav` / `AdminSidebar`+`AdminHeader` (see §11/§12) |
| Color scheme | Light-only | Light + dark | keep dark as an extension; AH defines light |

---

## 15. Token cross-reference (Stitch → proposed CSS variable)

When implementing, expose Academic Horizon as CSS custom properties alongside the existing ones
(do **not** rip out the current tokens in this planning phase):

```
--ah-bg:            #FBF9F6;   --ah-surface:        #FFFFFF;
--ah-surface-2:     #F5F3F0;   --ah-surface-3:      #EFEEEB;
--ah-primary:       #950013;   --ah-brand:          #B92026;   --ah-on-primary: #FFFFFF;
--ah-primary-tint:  #FFDAD7;   --ah-on-primary-tint:#930013;
--ah-text:          #1B1C1A;   --ah-text-2:         #5B403E;   --ah-muted: #6B7280;
--ah-border:        #E5E7EB;   --ah-outline:        #8F706D;
--ah-info:          #3B82F6;   --ah-success:        #10B981;   --ah-error: #BA1A1A;
--ah-radius-sm:     4px;       --ah-radius:         8px;       --ah-radius-lg: 12px;  --ah-radius-pill: 9999px;
--ah-shadow-2:      0px 4px 20px rgba(0,0,0,0.04);
--ah-font-head: "Hanken Grotesk"; --ah-font-body: "Inter";
```
