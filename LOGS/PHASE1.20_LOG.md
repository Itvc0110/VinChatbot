# Phase 1.20 — Trustworthy policy golden set + VI cross-lingual policy fix

> Plan of record: `.claude/plans/can-we-try-to-merry-mango.md`. Follows Phase 1.19 (structured lookup).
> Status: **code + golden done OFFLINE; all LIVE evals deferred** (local host is memory-starved — see
> "Memory constraint"). Decision order (confirmed): expand policy golden FIRST → trustworthy baseline →
> then the fix, measured against it.

## Problem
`policy_conduct` was 0.727 (8/11) but **untrustworthy**: 11 cases over ~5 of the **155** canonical policy
pages, basically one topic (LOA). Live traces pinned the defect: **VI policy queries rank the (often EN)
canonical policy doc far below adjacent VI governance docs**, while the EN twin ranks it #1. Candidate
pool (k=40), VI: academic-integrity canonical **not in pool**; sexual-misconduct @28 (rerank lifts to #1);
loa procedure not in pool (VUNI.54 PDF @22). EN: all #1. Root: e5 matches a VI query to VI governance
PDFs over the EN canonical page; the reactive cross-lingual trigger only fires on a *weak* score, but VI
gets a *confident* score on the *wrong* doc.

## Phase A — Trustworthy policy golden set (DONE)
- Enumerated the corpus: **155 canonical policy pages**; selected **17 student-facing** policies.
- **Verification-backed authoring** (3 parallel agents read each policy's real chunk text → drafted
  grounded EN+VI cases with verbatim facts + OR-synonym required_facts + canonical `expected_source`).
- Wrote `data/eval/golden/policy.json` — **34 cases (17 policies × EN/VI)**, category `policy`. Reverted
  the ad-hoc VI twins from `policy_conduct.json` (back to its original 7).
- **PENDING (live):** the verification pass (run each EN twin; keep only `facts_ok && citation_ok`;
  record VI status) — blocked by OOM. A few cases may be revised/dropped after it runs.

## Phase C — The VI cross-lingual fix (CODE DONE, gated, A/B pending)
- **Lever 1 — cross-lingual policy escalation** ([tools.py](../vinchatbot/app/agents/tools.py) `_search`):
  for a VI question routed to the policy domain (`subcat == "student_affairs"`), force `cross_lingual=True`
  → existing reactive `_multi_search` retrieves the EN variant and **RRF-fuses** it → canonical doc
  surfaces. Matches the USER's raw question (`get_user_message()`), not the agent's reformulation.
  Calendar/financial excluded. Flag `ENABLE_CROSSLINGUAL_POLICY` (default off).
- **Lever 2 — canonical policy-page boost** ([context.py](../vinchatbot/app/rag/context.py)
  `apply_metadata_boosts`): ×1.15 when `document_type in {policy_html, financial_policy}` under a
  `prefer_canonical` hint (set in `_search` for the policy domain). Flag `ENABLE_CANONICAL_POLICY_BOOST`
  (default off). Lifts in-pool canonical pages over governance PDFs.
- Config + `.env.example` updated; **offline: 295 passed, ruff clean** (6 new tests in
  `tests/test_policy_retrieval.py`: Lever-1 fires only for VI policy / not EN / not when flag off /
  boost-hint passed; Lever-2 lifts policy_html over policy_pdf, no false boost without the hint).

## Lever assessment (from live traces)
Cross-lingual escalation = the only lever that fixes the *not-in-pool* case → primary. Reranker swap =
skip (cohere rerank-v3.5 already multilingual; can't help a doc absent from the pool). "Better RRF" = no
standalone change (only adds value with the cross-lingual variant). Metadata = Lever 2 (reinforcement).

## Memory constraint (blocks all live evals right now)
The host restarted (Python 3.11→3.12) with **~832 MB free RAM**. Live evals crash:
`qdrant_client … zstd decompressor error: Allocation error : not enough memory` (the agent + fastembed
sparse model + Qdrant response decompression exceed free RAM). Same root as the 1.19 structured-lookup
OOM. **No code issue.** When RAM is free, run, in order:
1. Phase A verification: `run_eval --golden-dir data/eval/_policy_only` → confirm EN twins pass; fix/drop.
2. Phase B baseline: full `run_eval` (flags as promoted) → save `data/eval/baseline.json`.
3. Phase C A/B: `ENABLE_CROSSLINGUAL_POLICY` / `ENABLE_CANONICAL_POLICY_BOOST` on, vs baseline. Gate:
   policy ↑ (target ≥ 0.90), guards 1.000, no non-policy regression, ≤1 translation on VI policy turns.

## Memory workaround (temporary, no permanent code change) + reduced-k A/B result
The OOM is host RAM (the qdrant client can't allocate the zstd decompression buffer at ~832 MB free).
**Workaround proven:** run with a smaller `RETRIEVAL_CANDIDATE_K` (env only, default 40 untouched) → shrinks
the Qdrant response → fits under the ceiling. (Other no-code options: free RAM; bump the Windows pagefile.
Optional reverted toggle: `prefer_grpc=True` to bypass the zstd path.)

**Policy-slice A/B at k=12 (cross-lingual + canonical-boost OFF → ON)** — both arms ran, zero OOM:
- Overall policy slice **0.561 → 0.707 (+14.6)**; `policy` 0.500 → **0.676** (citation_ok 0.618→0.735);
  `policy_conduct` citation_ok **0.857 → 1.0**.
- GAINED 8 (6 VI incl. the hardest **academic-integrity not-in-pool case fail→pass**; loa-fulltime-vi
  citation F→T). LOST 2 = `pol-intern-feedback-en/vi` (internship retrieval regressed — investigate at k=40).
- Verification confirmed: every policy **EN twin passes** (valid cases) even at k=12; VI twins were the gap.
- Caveat: k=12 ≠ production k=40 → directional proof only; the promotion baseline + final A/B need k=40.

## Full A/B at k=24 (trustworthy broad golden, n=172) — combined fix is NET-NEUTRAL
OFF (baseline) vs ON (both levers), k=24, both arms ran (no OOM): **overall 0.878 → 0.878, +4/−4**,
guards 1.000, cost flat, latency +14%.
- policy 0.559→0.588 (citation_ok 0.706→**0.794**); policy_conduct citation_ok 0.857→**1.0**.
- GAINED 4 (VI: acadint-report-vi [the hard not-in-pool case], conduct-scope-vi, sexmis-hotline-vi; +courseeval-en).
- LOST 4: **3 are EN** (intern-feedback-en, escalation-en, conduct-report-misconduct-en) + visa-travel-vi.
- **Attribution (by logic):** Lever 1 (cross-lingual) fires only for VI → it CANNOT cause the EN losses →
  **Lever 2 (canonical boost) caused them** — the blanket ×1.15 to all policy_html demotes the correct doc
  for internship/escalation/conduct EN queries. Lever 1 drives the VI gains.
- **The k=12 slice (+8/−2) was inflated** by a weaker OFF baseline (more headroom). The trustworthy
  broad/k=24 set correctly caught the net-neutral reality — the whole point of Phase A.
- **Decision:** do NOT promote the combo. Next: isolate **Lever 1 ON / Lever 2 OFF** (expected to keep VI
  gains, drop the boost regressions); redesign Lever 2 to be topic-targeted (boost the canonical page only
  when it matches the query's policy), not blanket. (k=40 confirmation still pending RAM.)

## Isolation A/B at k=24 (Lever 1 ONLY: cross-lingual ON, canonical boost OFF) — CLEAN WIN
vs OFF baseline (eval_20260621T060004Z), n=172:
- **Overall 0.878 → 0.913 (+3.5); policy 0.559 → 0.676 (+11.7); citation_ok 0.71 → 0.79; +6 / −0;
  guards 1.000; cost slightly down; latency +8%.**
- Real wins: pol-acadint-report-en/vi (the hard not-in-pool case, both langs), pol-conduct-scope-vi,
  pol-exchange-credits-en. (2 calendar gains = favorable noise; Lever 1 doesn't touch calendar.)
- **Confirms attribution:** the 3 EN regressions vanish with Lever 2 off → Lever 2 (canonical boost) caused
  them. Combo was net-neutral because Lever 2's losses cancelled Lever 1's gains.
- **DECISION: promote Lever 1 (`ENABLE_CROSSLINGUAL_POLICY=true`); keep `ENABLE_CANONICAL_POLICY_BOOST=false`
  (drop the blunt boost; redesign topic-targeted later).** Reports: OFF eval_20260621T060004Z, Lever1
  eval_20260621T064335Z (the promotion candidate; k=24 — a k=40 confirmation is still nice-to-have).

## PROMOTED (no git commit) + new baseline + residual analysis
- `.env`: `ENABLE_CROSSLINGUAL_POLICY=true`, `ENABLE_CANONICAL_POLICY_BOOST=false`. `baseline.json` ←
  Lever-1 k=24 run (eval_20260621T064335Z) = **0.913 / 172**. Git commit HELD per user.
- **15 residual failures** taxonomy (for next go):
  - **VI "magnet-doc" retrieval miss (6, the dominant class):** finaid/intern/lib/courseeval/loa-return/
    res-curfew (VI) keep citing `VU_TS03` (financial tariff) or `VU_HT03` (academic regs) — a few large VI
    governance docs over-rank the canonical policy page for unrelated VI topics. Lever 1 helped only where
    the EN canonical doc ranks strongly. **This is what Lever 2 was meant to fix — but blunt boost backfired.**
  - **Answer-content / extraction (cit=True, facts=False) (5):** loa-fulltime-vi ("toàn thời gian" not
    stated), sexmis-hotline-vi (exact phone), courseeval-en, progchange-vi, thesis-days-vi — right doc found,
    exact fact not extracted (prompt/extraction OR over-strict golden token).
  - **Golden-strictness (answer grounded in a valid sibling) (~1-2):** exchange-credits-vi (the 12-credit
    full-time rule legitimately lives in VU_HT03 academic regs) → expected_source arguably too strict.
  - **Non-policy (3):** calendar-source-inconsistency-en/vi (conflicting-source case), fin-library-overdue-fine-vi.
- **Next go (plan):** (1) **redesign Lever 2 as a TOPIC-TARGETED canonical preference** — boost the canonical
  policy page only when its topic matches the query, and/or demote the VU_TS03/VU_HT03 magnets for off-topic
  queries (the real fix for the 6 magnet-miss cases, without the EN regressions). (2) **golden-strictness pass**
  (accept valid sibling sources via expected_source lists; loosen over-specific facts like exact phone).
  (3) **answer-extraction** for cit=True/facts=False (specialist prompt or the deferred output-audit critic).
  (4) non-policy residuals separately. (5) k=40 confirmation when RAM allows.

## Lever 2 REDESIGN — topic-targeted canonical preference (code done, gated, A/B pending)
**Root-cause refinement.** Traced the precise mechanism the magnets exploit: in `_search._multi_search`,
RRF fusion *does* surface the canonical EN page (via Lever 1's EN variant), but `rerank_fused(query=<VI
original>, …)` then reranks the fused pool with the **VI** query — and the multilingual reranker's
**same-language bias** floats the VI governance PDF (VU_TS03/VU_HT03) back above the EN canonical page.
`apply_metadata_boosts` runs *after* rerank → the right place to restore the on-topic canonical page.

**Design (replaces the blanket ×1.15).** Lift `policy_html`/`financial_policy` by `_CANONICAL_TOPIC_BOOST`
(×1.25) **only when the page `document_title`'s topic overlaps the query** — a salient-token intersection
(folded VI/EN, ≥3 chars, minus a bilingual structural stoplist: policy/guideline/student/quy-dinh/…).
Cross-lingual is solved for free: `_multi_search` threads the expanded variants (incl. Lever 1's EN
translation) as a new `topic_terms` hint, so a VI query matches the EN title. Title-gating ⇒ OFF-topic
canonical pages are **not** boosted, and the `policy_pdf` magnets are **never** eligible — by construction
this removes the blanket v1's EN regressions (intern/escalation/conduct).
- Files: [context.py](../vinchatbot/app/rag/context.py) (`_fold`/`_salient_terms`/`_topic_matches_title`
  + gated boost in `apply_metadata_boosts`); [tools.py](../vinchatbot/app/agents/tools.py) (`topic_terms`
  threading in `_multi_search`, only when `prefer_canonical`). Same flag `ENABLE_CANONICAL_POLICY_BOOST`.
- Tests: `test_policy_retrieval.py` — fires on-topic, **skipped off-topic** (anti-regression), cross-lingual
  `topic_terms` lifts the EN title for a VI query, `topic_terms` threaded for VI. **Full suite 298 green, ruff clean.**

**Offline dry-run (read-only, scratchpad `dryrun_titlegate.py`) over the 34 golden cases × 155 real titles:**
- **Coverage 32/34**: the expected canonical title would be boosted for all cases EXCEPT `pol-mdattend`
  (genuine vocabulary mismatch — Q says "excused absences/percentage/Board of Examiners", title says
  "Attendance/Medical/Doctor"; **mdattend was never a magnet residual**, so not a regression). `loa-return`
  resolves once the slug maps (golden uses the short slug `procedure-for-requesting-a-leave-of-absence`;
  index has the long form — a possible golden expected_source mismatch = measurement, deprioritized).
- **All 6 dominant magnet-miss targets (finaid/intern/lib/courseeval/loa-return/res-curfew) ARE covered** —
  the gate fires on each; whether ×1.25 clears the magnet's rerank lead is what the live A/B measures.
- **Precision leaks** (a query also matching 4–9 OTHER titles) are **benign for the magnet problem**: the
  co-matched pages are other `policy_html` siblings (compete fairly; relative html order unchanged), never
  the `policy_pdf` magnets. The leak only means the lever doesn't help html-vs-html cases — which isn't its job.

**Open / next:**
- Live A/B (RAM-gated, user greenlight): Lever 2 ON (+ Lever 1 already promoted) vs the 0.913 baseline.
  Gate: policy ↑, guards 1.000, **no EN regression** (the v1 failure), ≤ noise elsewhere. Tunable: ×1.25 factor.
- Known limit: title-only matching misses vocab-mismatch titles (mdattend). A content/keyword fallback is a
  later option if needed — not added now (scope; mdattend isn't a magnet case).

## Lever 2 redesign — LIVE A/B @ k=24 (ON vs the k=24 baseline) — NOT A WINNER, do not promote
Run `eval_20260621T080514Z` (ENABLE_CANONICAL_POLICY_BOOST=on, k=24) vs `baseline.json` (k=24, OFF):
**overall 0.913 → 0.919 (+3 / −2), guards 1.000 held.** But per-case decode kills it:
- **The 6 dominant magnet targets are ALL UNCHANGED** (finaid/intern/lib/courseeval-vi citation_ok stays
  False; loa-return/res-curfew stay F/F). **The boost never changed which DOCUMENT got cited** → at ×1.25
  the canonical page still ranks below the VI magnet after rerank. Lever 2 missed its entire purpose.
- **The +3 gains (courseeval-en, sexmis-hotline-vi, loa-fulltime-vi) are a different effect:** all went
  `facts F→T` with **citation_ok already True** — the boost reordered chunks *within an already-correctly-
  cited page*, surfacing the fact-bearing chunk. Incidental, not the magnet fix.
- **escalation-en regressed (`facts T→F`, citation still True)** — the SAME chunk-reorder buried the
  fact-bearing chunk. So Lever 2's real observed effect is chunk-level reshuffle: +3/−1 on extraction.
- **calendar-vietnam-culture-day-vi (−1) is provably noise:** that case routes to `calendar`, where Lever 2
  never fires (gate `subcat=="student_affairs"`). It proves ~1 case/run of run-to-run nondeterminism → the
  +1 net is inside the noise band.
- **VERDICT: reject.** Misses its goal (document selection unmoved), trades a chunk-reorder gain for an EN
  regression, net change within noise. Flag stays OFF (.env unchanged; the run used an inline env override).
- **Root cause for the pivot:** the magnet problem is **document selection / recall**, not post-rerank
  scoring — a score boost can't fix it because the cited doc never changes (canonical page is either below
  the magnet by >25% or absent from the reranked pool). The principled fix is **deterministic doc selection**
  (extend the calendar/fee structured-lookup pattern to policy: query topic → canonical policy doc), and/or a
  retrieval probe to confirm in-pool-but-low (→ stronger/targeted rank fix) vs absent (→ recall fix). A bigger
  boost factor is rejected: it would multiply escalation-style chunk regressions without moving recall.

## Status
- [x] Phase A authoring — policy.json (34 grounded EN+VI), policy_conduct reverted to 7; EN twins verified.
- [x] Phase C code — Lever 1 PROMOTED; Lever 2 REDESIGNED topic-targeted (flag-gated, off), config/.env.
- [x] Tests: full suite **298 green**, ruff clean; offline title-gate dry-run = 32/34 coverage, 6/6 targets.
- [x] Memory workaround proven; reduced-k A/B shows Phase C lifts the VI policy gap (+14.6 on the slice).
- [ ] **Lever 2 live A/B** (needs RAM): ON vs 0.913 baseline — verify VI magnet cases ↑ with no EN regression.
- [ ] k=40 confirmation (needs RAM/pagefile).
- [ ] Promotion (flags + baseline) + commit — HELD per user.
