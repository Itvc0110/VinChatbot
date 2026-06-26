# Phase 1.30 — Part-B fixes (canonical-source / cross-lingual + ...)

> A/B'd vs baseline 0.9683/221 (v2+D9), guards 1.000. Targets in `data/eval/golden_targets/`. No git commit.

## 1.30a — S15+S16 canonical-source BOOST — A/B REJECTED (boost too weak; pivot to doc-pin)

### Trial
Top two bugs (admissions/financial canonical-source S15; cross-lingual VI numeric facts S16) = "the
authoritative doc is out-ranked." Hypothesis: generalize the Phase-1.20 title-gated, cross-lingual-aware
`prefer_canonical` boost to the new fact-intents (program/admission/aid → program_page/admissions_page/
faq_page/scholarship_page/curriculum policy_pdf).

### Experiment
- `canonical_doctypes_for(query)` intent detector (query_engineering); parameterized `apply_metadata_boosts`
  canonical doc-types via a hint (default = policy pair → policy byte-identical); `tools._search` sets the hint
  + forces EN cross-lingual for VI fact-queries; flag `ENABLE_CANONICAL_SOURCE_BOOST` (default off). 375 tests
  green, ruff clean.
- **A/B on the 6 targets (programs_xlingual + admissions_financial_retrieval), cache-off, flag OFF vs ON:**
  **0/6 → 0/6.** Citations DID change (boost fired), but facts still wrong/missing. Decode: the authoritative
  doc (e.g. MD_Program-Specifications PDF with "228 credits", the BSDS/BN curriculum, the general-admissions
  FAQ with GPA 8.0, the scholarship page with 35%) is **NOT in the retrieved candidate set at all** — so a
  score boost has nothing to lift.

### Result — REJECTED (matches the Phase-1.20 policy precedent exactly)
A +25% boost cannot move document SELECTION when the canonical doc isn't retrieved. Same reason the policy
canonical-boost was rejected in 1.20 (→ doc-pin in 1.21). **Kept the code inert (flag default-off)**:
`canonical_doctypes_for` (reused for doc-pin intent detection) + the `apply_metadata_boosts` parameterization
(harmless, reusable as a secondary lift). No promotion; no git commit.

### Decision → 1.30b: DOC-PIN for fact-intents
Generalize the policy doc-pin (1.21, `policy_lookup` + `build_policy_topic_index`): detect intent+topic →
fetch the canonical doc by `source_url` → PIN to the front of context (deterministic doc selection), for
program (curriculum/spec PDF), admission (general-admissions FAQ), aid (scholarship page). Re-planned in
`.claude/plans` → EnterPlanMode.

## 1.30b — S15+S16 DOC-PIN for fact-intents — 5/6 targets, two regressions decoded & fixed

### Trial
The proven mechanism (1.21 policy doc-pin). New `vinchatbot/app/rag/canonical_lookup.py`:
`canonical_doc_match(user_message)` — accent-folded single-winner map of distinctive bilingual keywords →
curated canonical `source_url` (admission FAQ / aid scholarships page / per-program spec PDF). In
`tools._search`: on a match, `retriever.search(filters={"source_url": url}, limit=3)` → **non-evicting
prepend** (re-ranked WITHIN the doc by the real query). Flag `ENABLE_CANONICAL_DOC_PIN` (default off).

### Experiment — the debugging journey (deep-decode each loss, general fixes only)
- **A/B v1 (6 targets, cache-off, OFF→ON): 0/6 → 3/6.** Flipped `adm-gpa-en/vi` + the hard cross-lingual
  `prog-md-credits-vi` (the boost moved none — doc-pin is the mechanism). 3 still failed; decoded each:
  1. **`schol-subsidy-en/vi` (cite=False, tariff "50%")** — two stacked causes:
     - **AID_URL wrong:** curated `…/undergraduate-programs/` but the indexed page is
       `…/undergraduate-programs/scholarships/` → `source_url` filter returned 0 chunks → fail-open. Fixed.
     - **Root cause (the real blocker):** subsidy routes to the **financial** specialist, where the
       **structured FEE lookup early-returns at `tools.py:92`** (a false-positive: it loosely matches
       "tuition…" → tariff record with "50%") **before the doc-pin block at line 251 ever runs.** This is
       why `adm-gpa` / `MD` pinned fine (they route to services, no fee lookup) but aid never could.
       Instrumented + confirmed via direct tool probe (`hit_is_none=False`). **Fix:** compute `canon_match`
       once up front and **skip the fee lookup when the pin claims the query** — an aid % is an aid-policy
       fact (scholarship page), not a tariff row. Direct probe then showed the AID page pinned, leading with
       *"granted a 35% tuition [subsidy]"*.
  2. **`prog-nursing-credits-vi` (cite=True, "86" not 126)** — BN curriculum correctly pinned, but the LLM
     extracted the page-9 course-table "86 Total CR" (+ a leaked registrar Degree-Audit xlsx) over the
     program-total 126. **Within-doc number-disambiguation = a GENERATION issue, not doc-selection** → the
     doc-pin's job is done; logged as a residual (see below).
  - **A/B v2 (after AID + preemption fixes): 5/6** — `schol-subsidy-en/vi` flipped. Only `nursing-vi` remains.

- **Scored regression v1 (full 221, flag ON, cache-off): 0.9683 → 0.95.** Decoded 5 LOST / 1 GAINED by the
  partition rule **"`canon_match=None` ⇒ flag-ON path is byte-identical to flag-OFF ⇒ cannot be doc-pin-caused":**
  - **4 NOISE** (`canon_match=None`): `calendar-vietnam-culture-day-vi`, `d9-rectors-enumerate-vi`,
    `pol-loa-return-en` (LOST) + `fin-library-overdue-fine-vi` (GAINED) — pure run-to-run flakiness in known
    nondeterministic categories (calendar/identity/policy).
  - **2 REAL (doc-pin too aggressive — both fixed by NARROWING):**
    - **`fee-medicine-credit-en`** — a genuine FEE question ("tuition fee *per credit* for MD") matched MD via
      "doctor of medicine"+"credit"; the structured-skip was too broad and diverted it from the fee lookup to
      pin the MD spec (credit *counts*, not the per-credit *fee*). **Fix:** `canon_applies` — on the financial
      route only the **aid** pin applies; a program/admission name there is a fee question → fee lookup handles
      it (`canon_applies = bool(canon_match) and not (subcat=="financial" and canon_match != AID_URL)`).
    - **`exp-bba-duration-en`** — pinning `BBA_Program-Specifications.pdf` injected a dual-degree distractor
      (*"after 5 or 5.5 years, students receive [a partner degree]"*) alongside the "Length of program: 4
      years" line; baseline answered duration cleanly from the cohort docs on the vector path. **Fix:** dropped
      the duration keywords (`how long/how many year/duration/…`) from `_PROGRAM_FACT_KW` — the doc-pin is for
      **credit/curriculum counts** (clean in specs); duration stays on vector. This **reverts** duration Qs to
      baseline behavior, so it cannot regress any baseline-passing duration case.
  - **Collision audit** (canon_match over all 207 golden Qs): fires on 27 (4 adm / 15 prog / 8 aid); **no
    fee-amount query diverted** (the only "tuition"-touching aid matches are genuine aid-% / merit-range Qs).
  - Both fixes are strictly *narrowing*; 373 tests pass, ruff clean; spot-check confirms the 5 targets still
    pin (`canon_applies=True`) and both regressors are handled (fee-medicine `canon_applies=False`, bba-duration
    `canon_match=None`).

### Scored regression v2 (`b0ii134u6`, +canon_applies +no-duration, full 221, cache-off): 0.95 — but CLEAN
Same headline 0.95, **entirely different LOST set** (signature of noise, not regression). Decoded:
- **`fee-medicine-credit-en` → PASS** (the `canon_applies` fix worked — fee lookup restored). ✓
- **3 of the 6 LOST were EMPTY ANSWERS** (`schol-ug-merit-range-en`, `schol-vingroup-st-en`,
  `svc-library-room-booking`; baseline had 0) — the rate-limit / transient-API confound, NOT content.
- The rest (`calendar-…`, `exp-bba-duration-en` now facts-OK, `svc-library-services`) are all
  `canon_match=None` ⇒ byte-identical to flag-off ⇒ run-to-run noise. confidently_wrong 4→2.
- **⇒ no surviving doc-pin content regression.**

### Third narrowing fix — `_AID_KW` → SUBSIDY-only (the empties masked a real over-fire)
The 2 empty scholarship cases were AID-firing; probing what the pin *would* have done exposed a real risk:
the broad `"scholarship"`/`"financial support"`/`"ho tro tai chinh"` terms over-fire onto questions whose
answer lives **elsewhere** — `schol-vingroup-st-en` wants `scholarships.vinuni/vingroup` (a graduate
scholarship) but the pin prepends the undergrad `admissions.vinuni` aid page → citation flip; likewise
`exp-scholarship-phd-cs-en`, `d9-control-eligible-en`, `pol-finaid-deadline-en/vi`. **Fix:** narrowed
`_AID_KW` to the tuition-SUBSIDY intent only (`subsid / tuition subsidy / tuition support / tro cap /
ho tro hoc phi / mien giam hoc phi`). Verified: both subsidy targets still match; all 6 over-fires revert
to the vector path (baseline-clean). All three fixes are *narrowing* — the pin now fires only for the facts
it is curated to deliver (credit counts, admission GPA, the 35% subsidy); everything else = baseline.

### Result — PROMOTED ✅ (unified 226-case baseline `eval_20260625T030717Z`, flag ON, cache-off)
| metric | baseline (221) | new (226) |
|---|---|---|
| **passed** | 0.9683 | **0.969** ↑ |
| facts_ok | 0.964 | **0.973** ↑ |
| citation_ok | 0.991 | 0.987 |
| confidently_wrong | 4 | **3** ↓ |
| empties | 0 | **0** |
| guards (safety/adversarial/unanswerable) | 1.000 | **1.000** |

- **All 5 promoted targets PASS** (adm-gpa en/vi, prog-md-credits-vi, schol-subsidy en/vi).
- LOST 1 / GAINED 1, both `canon_match=None` (calendar/library flaky) = net-zero noise; no canon-firing
  content regression. Zero empties confirms v2's empties were transient infra.
- **Promotion applied:** `ENABLE_CANONICAL_DOC_PIN=true` in `.env`; 5 targets moved into
  `data/eval/golden/{admissions,scholarships,programs}.json` (198 scored cases; `admissions_financial_retrieval.json`
  fully promoted & removed); `baseline.json` refreshed to 0.969/226. Net: **0/6 (boost) → 5/6 (doc-pin)**.

### Residual (NOT a doc-pin failure) → future GENERATION fix
`prog-nursing-credits-vi` (kept in `golden_targets/programs_xlingual.json`): the BN curriculum is correctly
pinned (cite=True) but the LLM extracts the page-9 course-table "86 Total CR" (+ a leaked registrar
Degree-Audit xlsx) over the program-total **126**. Within-doc number-disambiguation = a GENERATION problem
(point-lookup prompt / distractor down-weighting), not doc-selection. Candidate for a later phase.
