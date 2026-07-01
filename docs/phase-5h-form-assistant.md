# Phase 5H: Vinnie Form Assistant (find → cite → fill → return editable file)

Students constantly need official VinUni forms (đơn xin nghỉ học, course withdrawal, grade appeal,
transcript/certificate, deferred exam…) and then fill them by hand. Vinnie now (1) **finds** the right form
and **cites its exact official URL**, then (2) **offers to fill it** — pre-filling with the signed-in
student's data + their request and returning a **review-ready, editable file in chat** that the student edits
and downloads themselves. Built on a dedicated branch (`feat/form-assistant`); **department submission is out
of scope** (no submission backend — the student downloads and submits it).

Decisions (locked with the user):
- **Discovery** = ingest forms into the existing RAG (targeted re-crawl), not a hand catalog and not runtime
  websearch.
- **Fill fidelity** = fillable-PDF first, else clean .docx. Fillable AcroForm PDF → filled in-place
  (pixel-perfect); flat PDF / non-PDF → a clean, editable **.docx** generated from the recognized fields.
  ("No-flaw" PDF→docx of an arbitrary flat PDF is not reliably achievable — this is the agreed calibration.)
- **Track 2 (`question_trends`) deferred** to its own effort (see `can-we-try-to-merry-mango.md`).

## Phase A — Discovery (find + cite)
- **Seeds** (`vinchatbot/app/ingest/crawler.py`): added the registrar **"Biểu mẫu & Đơn từ"** page plus the
  leave/withdrawal and transcript/certificate pages to `SEED_URLS` as durable belt-and-suspenders for future
  full crawls (they were reachable before only past the depth cap).
- **Coverage check against the LIVE index (2026-07-01):** the production collection `vinuni_full_e5_v2`
  (14,216 pts, promoted 2026-06-24) **already indexes** the registrar forms hub (`academics/forms-petitions/`,
  `vi/hoc-thuat-dich-vu/bieu-mau-don-tu/`) and the key student forms — **FRM02** General Petition, **FRM06**
  Change of Program/Major/Minor, **FRM07** Defer/Withdraw, **FRM09** Return-from-LOA, **FRM10** Transfer
  Credit, **FRM11** Independent Study, **FRM.18** Double Degree, **Grade-Appeal-Form**, misconduct forms, etc.
  A live diff of the registrar forms hubs vs. the indexed set = **0 missing**. So **no re-crawl / re-ingest is
  required** for coverage (my earlier "hub never crawled" note came from a stale `data/processed_cov` snapshot,
  not production). If the registrar publishes NEW forms later, re-run `python scripts/crawl_seed.py --seed-url
  <forms page>` then `python scripts/ingest_documents.py --incremental --vinuni-only --student-only` (additive;
  the incremental reconcile aborts if it would delete >50%).
- **`search_forms` tool** (`vinchatbot/app/agents/tools.py`): a new `@tool` that augments the query with form
  cues, searches softly (covers registrar + policy forms), and returns the standard `results` **plus a
  `form_files` list**. `form_files` = a **deterministic catalog match FIRST** (see below), then official
  `.pdf/.docx` URLs pulled from chunk metadata (`asset_url`/`source_url`) and chunk text (`_extract_form_files`,
  deduped, capped at 8, each tagged `source: catalog|retrieved`). Bound to the `services` specialist
  (`SPECIALIST_TOOLS["services"]` in `agents/specialists.py`).
- **Forms catalog override** (`data/forms_catalog.json` + `vinchatbot/app/rag/forms_catalog.py`): a small,
  curated keyword→official-file map for the ~8 core student forms (FRM02/06/07/09/10/11/18, Grade-Appeal).
  **Why:** form PDFs are mostly blank fields → they embed weakly and rank below the forms-hub page, so
  "đơn xin nghỉ học" surfaced the hub, not FRM07. The catalog lets `search_forms` cite the exact file for
  high-traffic forms; **RAG still covers the long tail**. Matching is **accent-folded** (đ→d + diacritic
  strip) so "don xin nghi hoc" also hits. **Drawbacks (bounded):** it can go stale if a form is re-versioned
  — mitigated by keeping it to the stable core, **fail-open** to RAG on any miss/read error, a `verified_on`
  provenance date, and it only *adds* to `form_files` (never suppresses RAG). Config: `FORMS_CATALOG_PATH`.
- **Prompt** (`agents/prompts.py`, `SERVICES_PROMPT`): forms-guidance block — name the form, cite the exact
  official URL from `form_files`, and proactively offer to draft it. **No invented form names/URLs.**

## Phase B — Fill (pre-fill + return editable file)
- **`agents/form_suggest.py`** (NEW, clones `ticket_suggest.py`): a dedicated small/fast LLM
  (`settings.form_suggest_model`, default `openai/gpt-4o-mini`, OpenRouter — swap via `FORM_SUGGEST_MODEL`)
  maps the student's request + known personal facts onto the form's fields → `{field_key: value}` + a short
  narrative. Two guarantees: **personal identity fields** (name / student ID / program / email / date) are
  filled **deterministically and are authoritative** (a hallucinated name/ID can never win — they're applied
  *after* the LLM), and it is **fail-open** (no key / LLM error / bad JSON → a heuristic: personal prefilled +
  reason = the question). Vietnamese forms use the respectful "em"/formal register. Field matching normalizes
  `_`/`-` → space so an AcroForm key like `full_name` matches the "full name" cue.
- **`services/form_fill.py`** (NEW): fetch + analyze + render.
  - `fetch_form_bytes` — **SSRF-guarded**: only `https?` URLs on an official VinUni host (`*.vinuni.edu.vn` or
    `vinuni.edu.vn`) are fetched, size-capped at 25 MB (httpx, crawler UA/timeout).
  - `analyze_form` — fillable AcroForm PDF (`doc.is_form_pdf` + widgets via fitz) → `("pdf", widget_fields)`;
    flat PDF → `("docx", recognized "Label: ___" fields ∪ default personal set)`; non-PDF → `("docx",
    default fields)`.
  - `fill_pdf` (fitz widget values) / `build_docx` (python-docx) / `render_form_file` — picks the path and
    **fails open** to a generated .docx if a PDF fill errors.
- **`schemas/forms.py`** (NEW): `FormField`, `SuggestFormRequest`, `SuggestedFormFill`, `FillFormRequest`.
- **`api/routes_forms.py`** (NEW, student-auth, registered in `main.py`):
  - `POST /forms/suggest` → fetch + analyze + `suggest_form_fill` → `SuggestedFormFill` (advisory, nothing
    persisted). Disallowed URL → **400**; fetch failure → fails open to a default-field editable draft with a
    `notice`.
  - `POST /forms/fill` → **streams** the generated file (`StreamingResponse` + `Content-Disposition`) built
    from the (student-edited) fields.
- **Personal data / isolation**: `_personal_facts` reads only THIS user (auth user's name/email +
  `StudentRepository.get_current_student_profile(user.id)` for student_id/program/cohort/advisor); fail-soft.

## Frontend (flagged for the teammate's typecheck — no Node in this env)
- `lib/forms.ts` (NEW) `findFormLink(response)` — detects an official VinUni `.pdf/.docx` link in an answer.
- `components/portal/AnswerActions.tsx` — optional **"Draft this form / Soạn giúp mẫu này"** action, shown by
  `ConnectedAnswerActions.tsx` only when a form link is present; calls `chat.prepareFormFill`.
- `lib/chat.tsx` — `formDraft` state + `prepareFormFill` (opens the drawer, then fetches
  `/forms/suggest`), `updateFormField`, `cancelFormFill`, `downloadForm` (POST `/forms/fill` → blob download).
- `components/forms/ReviewFormDrawer.tsx` (NEW, clones `ReviewTicketDrawer`) — editable field grid, the
  prominent ⚠️ review-before-you-send banner + "AI-drafted" chip + generated-copy notice, official-source
  link, and a **Download** primary action. Mounted in `components/chat/StudentChatOverlays.tsx`.
- `lib/api.ts` — `suggestFormFill` + `downloadFilledForm`; `lib/portalTypes.ts` — `FormDraft`/`FormFieldDraft`;
  `lib/portalI18n.tsx` — `actDraftForm` + a `formReview` block (EN + VI); `components/shell/icons.tsx` —
  `IconFileText`.

## Experiment / results
- **Tests:** 27 new backend tests — `tests/test_form_fill.py` (SSRF allow/deny table incl. `vinuni.edu.vn.
  attacker.com` and metadata-IP; analyze paths; fill/render both formats; PDF-fail→docx fallback),
  `tests/test_form_suggest.py` (heuristic prefill, **personal fields authoritative over the LLM**, fail-open,
  no caller mutation, VI register note), `tests/test_forms_api.py` (route SSRF 400s, suggest happy path +
  fetch-fail fail-open, `/forms/fill` streams a `%PDF-`, `_extract_form_files`). **Full suite: 754 passed**,
  ruff clean. No classifier/scope change → **no over-fire audit needed** (only `SERVICES_PROMPT` text changed).
- **Golden** (per the add-golden rule): `data/eval/golden/services.json` — `svc-form-leave-of-absence-vi`,
  `svc-form-transcript-request-en` (route to services/forms knowledge + cite `registrar.vinuni.edu.vn`).
  (Scored by the live-retriever eval after the forms crawl+index is run.)

## Live verification (2026-07-01, against Qdrant Cloud `vinuni_full_e5_v2`)
`search_forms` cites the exact official form file for direct queries (catalog match first):
- "đơn xin nghỉ học một học kỳ" → **FRM07 Defer/Withdraw** `[catalog]` (previously surfaced only the hub — now fixed).
- "don xin nghi hoc" (no diacritics) → FRM07 `[catalog]` (accent-folding works).
- "form to appeal a grade" → Grade-Appeal-Form `[catalog]` + the procedure `[retrieved]`.
- "chuyển đổi tín chỉ" → FRM10 Transfer Credit `[catalog]`.
- "how much is tuition" (non-form control) → **0 form_files** (catalog does not over-fire).

## Collection design decision
Forms live in the **same** collection (`vinuni_full_e5_v2`), not a separate one: `search_forms` and the
`search_vinuni` fallback share one retriever/embedding (e5-large 1024-d) so forms are reachable with no extra
wiring, cross-references (a policy answer citing its linked form) work, and there's one index to reconcile. A
separate collection would only pay off for a different embedding / access-tier / rebuild cadence — none apply.

## Progress / follow-ups
- **Coverage: complete — no build needed** (verified above).
- **VI recall — RESOLVED** via the deterministic forms catalog: "đơn xin nghỉ học" now cites FRM07 directly
  (root cause: blank-field form PDFs embed weakly, so they lost the vector ranking to the hub page — a catalog
  override is the right fix, not retrieval tuning). Verified live above. Tests: `tests/test_forms_catalog.py`
  (8 cases: VI/EN/no-diacritics match, no-match, fail-open on missing file, limit).
- Frontend typecheck is the teammate's step (no Node here).
- Enhancement backlog: richer flat-PDF blank recognition; checkbox/date widget types; caching fetched form
  bytes between `/forms/suggest` and `/forms/fill`.
