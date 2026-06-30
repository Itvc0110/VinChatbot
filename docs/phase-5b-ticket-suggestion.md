# Phase 5B: Vinnie-suggested support-ticket draft (review-before-send)

On **"Soạn phiếu hỗ trợ" / "Prepare support ticket"**, Vinnie now drafts the ticket — a concise **summary
(subject)**, a clear **description (body)**, and the right **category** — from the conversation, instead of
the old client-side heuristic (subject = raw question, body = whole answer, category always `other`). The
student reviews/edits it in `ReviewTicketDrawer` and sends; the draft is flagged `created_by_ai`. **General
chat is untouched** and the suggestion **fails open** to the old heuristic so the ticket flow never breaks.

## Separate small/fast model
A **dedicated LLM call** uses its own model `settings.ticket_suggest_model` (default `openai/gpt-4o-mini`),
still via OpenRouter — change only **`TICKET_SUGGEST_MODEL`** in `.env` to swap it (no other config change).
Kept off the main chat model so the draft tier stays cheap/fast independently.

## Backend
- `vinchatbot/app/agents/ticket_suggest.py` (NEW) — `suggest_ticket_draft(request)`: builds a tight,
  language-matched prompt and returns JSON `{subject, body, category}`; parses tolerant JSON, validates the
  category (→ `other` if unknown), clamps lengths. **Fail-open**: no key / LLM error / unparsable → a
  deterministic heuristic draft. Prompt specifics:
  - **subject** = a brief one-line TOPIC (short noun phrase, not a sentence, no trailing punctuation,
    ≤ ~80 chars) — e.g. "Vấn đề đăng nhập vào Canvas", "Dispute of final grade in Calculus".
  - **body** = formal first-person, 2–5 sentences, no invented facts. **Vietnamese uses the respectful
    "em" register** (student → university office: "Em xin trình bày…", "Em mong phòng ban hỗ trợ em…");
    English stays formal "I".
  - **category** is chosen against explicit per-category DEFINITIONS (academic / schedule /
    student_services [incl. housing, library, health, certificates, fees] / technical [IT/Canvas/portal/
    wifi/email] / other) — verified **10/10** on a live EN+VI battery.
- `vinchatbot/app/api/routes_tickets.py` — `POST /tickets/suggest` (student-auth) → `SuggestedTicketDraft`.
  Advisory only (no DB write).
- `vinchatbot/app/schemas/tickets.py` — `SuggestTicketRequest`, `SuggestedTicketDraft`, `TICKET_CATEGORIES`,
  and `created_by_ai: bool=False` on `CreateTicketRequest`.
- `vinchatbot/app/repositories/tickets.py` — `create_student_ticket` now persists `request.created_by_ai`
  (was hardcoded `false`); `confirmed_by_user` stays `true` (the drawer is the confirm step). So an
  AI-suggested, student-confirmed ticket → `created_by_ai=true, confirmed_by_user=true`.

## Frontend
- `lib/api.ts` — `suggestTicketDraft({origin_question, answer, context})` → `POST /api/tickets/suggest`;
  `created_by_ai` threaded through `submitTicket` → `CreateTicketPayload` → `POST /tickets`.
- `lib/portalTypes.ts` — `created_by_ai?: boolean` on `TicketDraft`.
- `lib/chat.tsx` — `prepareDraftFromAnswer` is async: opens the drawer instantly with the heuristic, then
  fetches Vinnie's suggestion and applies it (subject/body/category + `created_by_ai:true`) only if the same
  draft is still open; on error keeps the heuristic. New `draftSuggesting` state.
- `components/tickets/ReviewTicketDrawer.tsx` — **prominent disclaimer**: a warning-styled banner with an
  "AI-drafted" chip (when `created_by_ai`) and a "Vinnie is drafting…" line; fields + buttons are locked
  while suggesting. **Attachments stay deferred** (button still `disabled`).
- `lib/portalI18n.tsx` — strengthened `review.banner` ("…you're sending it, not Vinnie.") + new
  `review.aiDrafting` / `review.aiDraftedChip` (EN + VI).

## Out of scope (deferred)
- **Attachments** — no `ticket_attachments` table yet; the button stays disabled.
- **Severity/priority selector** — not in this ask; the draft keeps the existing `priority` default
  (`medium`); an admin can adjust. Easy to surface later.

## Verification
- **Backend**: `ruff` clean; **681 tests pass** — incl. `tests/test_ticket_suggest.py` (heuristic fallback
  with no key; valid-JSON use; invalid category → other; unparsable/model-error → heuristic; length clamp)
  and `tests/test_ticket_api.py` (suggest requires `student`; admin → 403; `created_by_ai` persists on
  create).
- **Live** (OpenRouter, `gpt-4o-mini`): `/suggest` produced a clean technical EN draft and an academic VI
  draft — correct language, category, and concise first-person body; no invented facts.
- **Frontend typecheck NOT run here** (Node/`npm` not available on this machine, deps not installed). Changes
  were written to match existing types — **run `cd frontend && npm run typecheck` to confirm.**

## Handoff / state (for teammate)

Branch `feat/personalization-tools`. Backend is fully verified here; the **frontend was NOT compiled or
run** in this environment (no Node), so please verify it on your side:

- **Backend — VERIFIED**: `ruff` clean, `pytest` 681 passing, `/tickets/suggest` exercised live (EN+VI,
  category 10/10), the bot demo (greeting / personal / GPA-projection / RAG+citation / out-of-scope refusal /
  catalog routing / ticket draft) all behaved correctly against Neon + OpenRouter + Qdrant.
- **Frontend — NEEDS YOUR CHECK**: run `npm run typecheck` and click through the Review Ticket drawer
  (open from a chat answer → it should show "Vinnie is drafting…", then fill subject/body/category, with the
  highlighted ⚠️ disclaimer + "AI-drafted" chip; Attachments button stays disabled). The drawer highlight
  uses inline styles (no new CSS).
- **Config**: optional `TICKET_SUGGEST_MODEL` in `.env` (defaults to `openai/gpt-4o-mini`); no other env
  change needed.
- **Known minor / open** (not blockers): a cosmetic `Nguồn: [personal], [calendar]` footer can appear on
  personal answers (one-line `PERSONAL_PROMPT` tweak fixes it); Part A issues #3–#5 in
  `docs/phase-5-personalization-tools.md`; data-model reconciliation in `docs/data-model-inconsistency.md`
  (deferred); broader pre-existing risks in `docs/pre-personalization-risk-register.md`.
