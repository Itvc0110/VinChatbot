# Phase 1.21 — Deterministic policy doc-pin (the real VI magnet fix)

> Plan of record: `.claude/plans/can-we-try-to-merry-mango.md`. Follows Phase 1.20 (Lever 1 promoted;
> Lever 2 canonical-boost rejected). Status: **code + offline verification DONE; live A/B pending greenlight.**

## Problem (root-caused by probe, not guessed)
Lever 2 (canonical title-boost) was rejected: a ×1.25 score nudge never changed which *document* got cited
for any of the 6 dominant VI magnet cases. A read-only retrieval probe (`scratchpad/probe_magnet.py`,
soft-routing = unfiltered corpus + Lever 1 VI+EN fusion + VI-query rerank) proved **the canonical page IS in
the reranked pool for all 6 — it's a RANKING problem, not recall** — but the competitors are heterogeneous
and the gaps vary too much for any fixed boost:
- magnet PDFs `VU_TS03`/`VU_HT03` rank #0 (lib-loan, courseeval) or top-5 (loa-return, res-curfew);
- the canonical page's **own PDF twin** (POL-LLR-001, POL-CAID-001, POL-AQA-001, GDL-FAO-001) ranks at/above it;
- on-topic non-policy pages (registrar leave pages, career, campus-services) out-rank it.
- ranks observed: finaid #4, intern #0, lib #2, courseeval #3, **loa-return #9 (out of the top-8 context)**, res-curfew #6.

## Fix — deterministic topic→canonical-doc selection + decisive pin
Mirrors the proven `structured_lookup` (calendar/fee) single-winner pattern. New module
[policy_lookup.py](../vinchatbot/app/rag/policy_lookup.py): a curated bilingual keyword → canonical-slug map
for the 17 student-facing policies; `match(user_message)` returns a URL **only when exactly one** topic
matches (0 or >1 ⇒ None, fail-open). Pure dict/substring on folded text (reuses `context._fold`), no LLM.

Seam in [tools.py](../vinchatbot/app/agents/tools.py) `_search` (gated `ENABLE_POLICY_DOC_PIN`, default off):
for `subcat == "student_affairs"`, on a match, fetch the canonical page by `source_url`
(`retriever.search(filters={"source_url": url}, limit=2)` — source_url is a Qdrant keyword index) and
**prepend** it to the results (`dedup_by_text`, cap `retrieval_max_k`). Gap-proof: works even for the rank-9
case. Fail-open: any miss/error ⇒ byte-identical vector path. subcat gate keeps calendar/financial untouched.

Config + `.env.example`: `ENABLE_POLICY_DOC_PIN=false`. Same flag philosophy as the rest of the phase.

## Offline verification (all green)
- **Matcher precision dry-run** over the 34 golden policy questions: **34/34 map to the correct slug, 0 wrong,
  0 >1-collisions** (after tuning: genai keywords are *generative*-specific so the "AI minor" questions pin
  minor-fields not genai; exchange adds "exchange semester"/"hoc ky trao doi"). Even covers mdattend & genai-vi
  that the title-gate had missed.
- **Broader 172-case false-positive scan:** **0 matches on adversarial/safety** (guards structurally safe);
  calendar/financial matches route to their own subcats so the pin never fires; the only policy-domain
  "extras" are the *correct* library doc (`svc-library-*` → "Library Access & Services Policy") or benign
  (`unans-wifi` → library page has no wifi password ⇒ bot still refuses). To be confirmed by the A/B guard read.
- **Tests** [test_policy_lookup.py](../tests/test_policy_lookup.py): single-winner fires (VI/EN), MISS on
  ambiguous/none/empty, generative-vs-minor disambiguation, pin prepends canonical, pin off by default, pin
  skipped on no-match. **Full suite 307 green, ruff clean.**
- **End-to-end pin probe** (`scratchpad/probe_pin.py`, real `search_policy_documents` tool, pin ON):
  **CANONICAL LEADS 6/6** — every magnet case now returns the canonical page as result #0, including
  loa-return (rank 9 → #1). The model will read + cite it.
- **Citation scoring** is substring (`run_eval.py:166`: `expected_slug in source_url`), so loa-return's short
  golden slug `procedure-for-requesting-a-leave-of-absence` is contained in the long canonical URL → it scores
  with the pin. **No golden edit needed** (the earlier "slug mismatch" was an exact-match artifact of the dry-run).

## LIVE A/B @ k=24 (pin ON vs baseline) — NET ZERO, not promotable as-is
Run `eval_20260621T090634Z` vs `baseline.json`: **overall 0.913 → 0.913 (+5 / −5), guards 1.000 held**
(adversarial/safety/unanswerable all 1.0 — the matcher's 0 guard-matches held up). Per-case decode is the
real story — the end-to-end probe ("canonical leads 6/6") was necessary but **not sufficient**, because the
outcome depends on where the MODEL cites + whether the fact survives, not just retrieval order:
- **5 of the 6 magnet targets did NOT flip** (finaid/intern/lib/courseeval-vi stay `facts=1, cit=0`): the bot
  ANSWERS CORRECTLY but cites the policy's **PDF twin** (POL-/GDL-, the governance form) where the
  student-facing fact actually lives. Pinning the html canonical to #0 doesn't move the citation — **the model
  cites the chunk it extracted the fact from.** loa-return: `cit 0→1` (pin fixed the citation) but `facts`
  still 0 (the figure isn't extractable from the page). res-curfew: unchanged.
- **Losses (−5):** `escalation-en`, `intern-feedback-en`, `visa-travel-vi` went `facts 1→0` — the pin's
  prepend+cap-to-max_k **EVICTED the fact-bearing chunk** (the twin) those cases relied on; `minor-ai-vi`
  `cit 1→0` (citation shifted off the right source); `calendar-vietnam-culture-day-vi` is **noise** (calendar
  subcat → pin never fires).
- **Gains (+5):** `courseeval-en`, `loa-fulltime-vi`, `progchange-vi`, `sexmis-hotline-vi` (`facts 0→1` — the
  fact IS on the canonical html and the pin surfaced it) + `exchange-credits-vi` (`cit 0→1`, full pass). Real.

**VERDICT: do not promote (net zero + fact-displacement regressions).** Flag stays OFF (.env unchanged; inline
override only). The probe's "leads 6/6" mispredicted because citation follows fact-location, not retrieval rank.

**Two real conclusions:**
1. The 6 magnet cases are largely a **citation-granularity** issue, not retrieval: 4/6 are `facts=1, cit=0` =
   right answer citing the policy's own PDF twin (a valid VinUni source). No retrieval lever fixes that — the
   model cites where the fact is. (Accepting the twin slug in `expected_source` would pass them, but that's the
   golden change the user deprioritized; not pursued unilaterally.)
2. The pin's prepend+**cap evicts fact chunks** → the −EN regressions. Salvage hypothesis: a **non-evicting**
   pin (keep the original top chunks, cap at `max_k + len(pinned)`) would likely keep the +5 gains and recover
   the eviction losses (escalation-en/intern-en/visa-vi) → a genuine net win (~+3 to +5), though still NOT the
   magnet-6. One more A/B would settle it.

## Non-evicting pin — A/B v2 @ k=24 (eval_20260621T093249Z) — modest REAL win, NOT clean
Tweak shipped: `chunks = dedup(pinned + chunks)[: max_k + len(pinned)]` (keep originals). **overall
0.913 → 0.919 (+5 / −4), guards 1.000, policy 0.676 → 0.735, policy_conduct 0.857 → 1.0.** Decode (base/v1/v2):
- **Hypothesis confirmed:** the 3 v1 eviction losses **recovered** (escalation-en, intern-feedback-en,
  visa-travel-vi all `p0→p1`); the **5 gains preserved** (courseeval-en, exchange-credits-vi, loa-fulltime-vi,
  progchange-vi, sexmis-hotline-vi).
- **2 losses are NOISE:** calendar-fall-grade-release-en + culture-day-vi route to `calendar` subcat → the pin
  never fires there (gate). Pure run-to-run nondeterminism (~2 cases/run; this is why overall reads +1 not +3).
- **2 REAL pin regressions:** `loa-return-en` (`f1→f0`, the added loa chunks misled EN extraction — note
  loa-return-VI's citation *improved* `c0→c1`, so the loa topic helps VI but hurts EN) and `minor-ai-vi`
  (`c1→c0`, citation shifted). Both are side-effects of injecting the canonical chunk, stable across v1/v2.
- **Magnet-6 still not passing:** loa-return-vi + res-curfew-vi got `c0→c1` (citation help) but facts stay 0;
  the other 4 cite the PDF twin (facts=1, cit=0). lib-loan-vi even lost facts (`f1→f0`). Confirms the magnet-6
  are citation-granularity, not retrieval — the pin can't fix them.

**True pin effect = +5 / −2 in the policy domain (net +3), guards 1.000.** The overall +1 is noise-dragged.
**Status: a modest, mechanistically-sound real win (policy +3), but NOT a clean +N/−0 (2 real regressions) and
it does not solve the magnet-6 it was built for.** Promotion is a judgment call (HELD for user decision); flag
stays OFF until decided. Cheaper tuning option before promoting: pin `limit=1` (less context pollution) to try
to shed the loa-return-en / minor-ai-vi regressions.

## Phase 1.21b — broaden the pin gate (the real magnet fix; code done, A/B pending)
Plan-mode root-cause: the magnet-4 **never got the pin** because they route to NON-policy specialists, and
the gate was `subcat == "student_affairs"`. Confirmed from citations: finaid-vi → financial (cites
GDL-/VU_TS03), intern-vi/lib-vi → general `search_vinuni` (subcat None), courseeval-vi → calendar. The lone
magnet case routed to the policy specialist (exchange-vi) flipped perfectly (cites canonical ×4). Also
re-derived: **citations = the retrieved set** (`_extract_citations` aggregates all `_search` payloads
deduped[:8]; `citation_ok` = expected slug ∈ any cited url) → a pinned canonical that lands in the set IS
cited, so **no citation-preference prompt is needed** — the only blocker was the gate. Verified the canonical
html **contains every required_fact** for finaid/intern/lib/courseeval (so facts will pass once pinned too).
- **Change ([tools.py](../vinchatbot/app/agents/tools.py)):** gate `subcat == "student_affairs"` →
  `subcat != "calendar"` — fire for student_affairs (keep the +5), **financial** (finaid-vi), **general/None**
  (intern-vi/lib-vi); exclude **calendar** so date point-lookups sharing a policy keyword stay untouched
  (structured calendar/fee lookups already early-return; courseeval-vi is a calendar *mis-route* → out of scope).
- Tests: pin now fires via search_financial_regulations + search_vinuni, NOT via search_academic_calendar;
  off-by-default + no-match fail-open unchanged. **Full suite 310 green, ruff clean.**
- **Known accepted risk:** loa-return-en (`f1→f0`) — the loa canonical page lacks the advance-notice figure
  (it's in the FRM09 form); pinning it displaces the fact. (minor-ai-vi's v2 flip was noise — routes away.)
- **A/B pending (RAM-gated):** ENABLE_POLICY_DOC_PIN=on (broadened) vs baseline @ k=24. Gate: finaid/intern/
  lib-vi flip + the 5 kept, guards 1.000 (watch services/unanswerable), no regression beyond loa-return-en+noise.

## Broadened-gate A/B @ k=24 (eval_20260621T*, pin ON vs baseline) — STRONG WIN, promote candidate
**overall 0.913 → 0.953 (+10 / −3), guards 1.000, policy 0.676 → 0.912, policy_conduct 0.857 → 1.0,
citation_ok 0.96 → 0.994, confidently_wrong steady.** Best result of the whole arc.
- **GAINED (+10), all mechanistically clean** (pin fired → canonical cited ×3 → facts present):
  **4 of the 6 magnet targets flipped** — finaid-deadline-vi, intern-feedback-vi, lib-loan-vi (each
  `f1 c0→f1 c1`, now cite the canonical) + res-curfew-vi (`f0 c0→f1 c1` — curfew time IS on the residential
  page); plus thesis-days-vi (`f0 c1→f1 c1`, bonus) and the 5 student_affairs gains kept (courseeval-en,
  exchange-vi, progchange-vi, sexmis-vi, loa-fulltime-vi).
- **LOST (−3) — 2 noise + 1 real:** calendar-vietnam-culture-day-vi (match=None, calendar — pin never fires;
  recurring noise) and conduct-disciplinary-tiers-en (**match=None, identical citations base vs new** → pure
  LLM nondeterminism) are NOISE. **pol-visa-travel-vi is the one real pin regression** (`f1→f0`): the pin
  pinned the study-visa *html*, which lacks the travel-permission detail (it's in the GDL-SAM-006 PDF /
  handbook it displaced) — same "canonical html lacks the operational fact" class as loa-return-en.
- **True pin effect = +10 / −1 real (−2 noise).** Guards held (adversarial/safety/unanswerable 1.000);
  **services stayed 1.000** (the general/None false-positive concern did NOT materialize — pinning the
  "Library Access & Services Policy" for library-services questions is correct/benign).
- **Two magnet misses remain (expected):** courseeval-vi (mis-routed to calendar → gate excludes it;
  a supervisor-routing issue) and loa-return-vi (canonical lacks the advance-notice figure).
- **VERDICT: PROMOTED** (user go-ahead). `.env` `ENABLE_POLICY_DOC_PIN=true`; `baseline.json` ←
  eval_20260621T131228Z = **0.953/172, guards 1.000**. No git commit (standing rule). The broadened gate
  is the magnet fix (+10/−1 real, policy 0.676→0.912).
  Residual class for Phase 1.22 output-audit critic: visa-travel-vi + loa-return (canonical-lacks-fact),
  fin-library-overdue-fine. courseeval-vi → supervisor-routing fix (separate). Generality/uploads → Phase 1.23.
