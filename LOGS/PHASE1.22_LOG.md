# Phase 1.22 (roadmap A1) — Eval de-noise / multi-run averaging

> Plan: `.claude/plans/can-we-try-to-merry-mango.md` + `UPDATE_PLAN.md`. Goal: make A/B verdicts
> trustworthy by separating real flips from run-to-run noise (the source of mis-judged levers this session).

## Trial
**Hypothesis/root-cause:** single-run A/Bs were muddied by run-to-run nondeterminism (generation-born — see
the determinism note in the roadmap). A case that flips between identical-config runs is **noise**, not a
real change, and must not gate promotion. **Attempt:** add multi-run averaging + per-case stability to the
eval, then quantify the actual noise floor of the promoted config.

## Experiment
**Code (offline):** `scripts/run_eval.py` — `--runs N` runs the suite N×; `_aggregate_runs` reports per-case
`passed_rate` + `stable` ∈ {pass, fail, **noisy**} and a mean summary; `_print_multi_diff` counts **only
stable flips as regressions**, listing noisy ones excluded from the gate. `--runs 1` is byte-identical to
before. **Stemming deliberately NOT added** (the matcher's substring `tok in answer` already covers
prefix-morphology; a stemmer would *loosen* matching = the score-padding the user vetoed). Unit tests in
`tests/test_eval_multirun.py`; **full suite 312 green, ruff clean.**

**Variance baseline** (`--runs 3`, k=24, SAME promoted config, no flag change; report
`eval_20260622T001214Z`, diff vs `baseline.json`):
- **mean passed 0.955** (per-run **0.965 / 0.948 / 0.953**) → overall swings ±~1.7 cases run-to-run.
  guards 1.000 every run.
- **stability over 3 runs: stable_pass=161, stable_fail=5, NOISY=6** (≈3.5% of the set flips).
- **Noisy (flip across identical runs):** `fin-library-overdue-fine-vi`, `pol-loa-return-en`,
  `pol-intern-feedback-en`, `pol-res-curfew-vi`, `pol-escalation-en`, `pol-thesis-days-vi`.
- **Stable-fail (the REAL consistent residuals):** `calendar-vietnam-culture-day-vi`, `pol-loa-return-vi`,
  `pol-courseeval-vi`, `calendar-source-inconsistency-en`, `calendar-source-inconsistency-vi`.
- **Stable-gained vs `baseline.json` (+2):** `conduct-disciplinary-tiers-en`, `pol-visa-travel-vi` —
  i.e. the single-run `baseline.json` was itself a slightly-low noisy sample (true mean ~0.955, not 0.953).

## Progress
- **A1 DONE** (code shipped + offline-green + noise floor measured). Verdict: the eval is now de-noisable.
- **Noise floor = 6 cases (~3.5%); true baseline mean ≈ 0.955** (baseline.json @ 0.953 was within noise).
- **Important correction to this session's single-run attributions:** four cases I credited/debited to the
  pin are actually **NOISY** — `pol-escalation-en` + `pol-intern-feedback-en` (I'd called these pin "eviction
  losses" then "recovered"), and `pol-res-curfew-vi` + `pol-thesis-days-vi` (I'd counted as pin "+gains").
  They flip regardless of the pin. **The pin promotion still stands** — its real, *deterministic* wins are
  the magnet citation flips `finaid/intern/lib-vi` (now stable_pass) via the citation=retrieved-set mechanism
  — but the exact per-case ±N from single runs was noise-contaminated. Lesson: trust the multi-run/stable view.
- **Refined residual targets** (from the de-noised view):
  - **A2b routing:** `pol-courseeval-vi` (stable-fail — mis-routed to calendar).
  - **A4 critic:** `pol-loa-return-vi` (canonical lacks the fact) + the noisy extraction cases
    (`fin-library-overdue-fine-vi`, `loa-return-en`, `thesis-days-vi`, …) — A2's cache will stabilize them,
    A4 should actually fix the extraction.
  - **Calendar:** `calendar-vietnam-culture-day-vi` (stable-fail — investigate why structured-lookup didn't
    catch the holiday) + `calendar-source-inconsistency-en/vi` (the *designed-hard* conflicting-source test).
- **Strongly motivates A2 (determinism):** 6 noisy cases is real measurement uncertainty; the Redis
  exact-match cache should collapse most of it — and make future multi-runs near-instant (this 3× run took ~60 min).
- **DONE:** `baseline.json` refreshed to the de-noised 3-run aggregate (mean 0.955 + per-case stability).
  No git commit.

## Stable-fail root-cause research (5 cases) — FOUR distinct causes (offline, confirmed)
Per the request to dig into the *genuine* (consistent) failures, decoded each from `baseline.json` + golden:

1. **`calendar-vietnam-culture-day-vi` → structured-lookup COVERAGE gap (data/ingest).** Q asks the
   tentative Vietnam Culture Day date (AY26-27 = "24 tháng 11 năm 2026"). The bot **declines** ("chưa tìm
   thấy"), cit=1 to the calendar PDF. Confirmed: the compact structured index has **0 culture-day records**
   → structured lookup MISSES → vector can't surface it → honest decline. This is the known calendar
   under-extraction (~21/59 events). **Fix: improve calendar event extraction** (capture Culture Day + other
   holidays) and rebuild the index. *Not a retrieval-ranking bug — an extraction-coverage gap.*

2. **`pol-loa-return-vi` (+ noisy `loa-return-en`) → SCORER false-negative, the bot is RIGHT.** Bot answers
   "ít nhất **1 tháng** trước" (correct: one month), cites the LOA procedure (cit=1). Required fact
   `"một tháng|one month"` — but the matcher does **not** equate numeral **"1 tháng"** with word "một tháng"
   / "one month" (confirmed: `_fact_matches("1 tháng", "một tháng|one month") = False`, but `"1 tháng"`
   alternative = True). So the answer is correct; the scorer mis-scores numeral-vs-word. This also explains
   `loa-return-en` being **noisy** (the LLM alternates "1 month" / "one month"). **Fix: numeral↔word
   normalization in `_fact_matches` (1↔one↔một, …) — a genuine matcher-bug fix (false-negative), NOT
   score-padding.** Converts loa-return-vi to pass + stabilizes loa-return-en.

3. **`pol-courseeval-vi` → routing mis-route (→ A2b).** Policy Q ("is there an end-of-course evaluation for
   each course?") routed to **calendar**: answered from the Academic Calendar (evaluation-period dates) and
   **cited the calendar PDF**, not the `course-evaluation` policy page → facts=1 but cit=0. Exactly the A2b
   target (route course-evaluation *policy* → policy specialist → pin fires → cites the policy page).

4. **`calendar-source-inconsistency-en/vi` → designed-hard meta-reasoning.** Bot correctly reports June 7 /
   June 18 / "Fall'26" (3 of 4 facts) but does NOT flag the 4th required fact — that a June exam period
   labeled "Fall'26" is **internally inconsistent**. The test wants the bot to *notice & flag* the source
   conflict; it reports faithfully instead. **Fix: a prompt instruction to flag internally-inconsistent /
   conflicting source data** — or accept as aspirational. Lowest priority (niche, by-design hard).

**Reframed residual map:** of 5 stable-fails → 1 scorer-bug (loa, bot already correct), 1 routing (A2b),
1 calendar-extraction-coverage (new data item), 2 designed-hard reasoning. The loa scorer fix + A2b together
clear/stabilize loa-return-vi/en + courseeval-vi; culture-day needs extraction; source-inconsistency is a prompt nicety.

## Scorer numeral↔word fix (A1 scorer-fairness) — SHIPPED + offline-validated
**Trial:** loa-return-vi/en are scorer **false-negatives** — the bot answers "1 tháng" / "1 month" (correct)
but the golden fact `"một tháng|one month"` (word form) doesn't match the numeral. Fix: numeral↔word
equivalence in `_fact_matches`.
**Experiment:** added `_number_match` (`scripts/run_eval.py`) — a fact number token (digit or EN/VI word)
matches ANY equivalent form of the **same** number, **boundary-checked** (a fact "two" is NOT satisfied by
the "2" in "2027"), VI homonyms **excluded** (`năm`=5/year, `tư`=4/Thursday). One unit test; **313 offline
green, ruff clean**. **Offline re-score of the saved baseline answers (old vs new scorer) → exactly 2 flips,
both CORRECT:**
- `pol-loa-return-vi` **F→T** — the intended false-negative fix (bot's "1 tháng" = required "one month").
- `pol-thesis-days-vi` **T→F** — the old pass was a **false POSITIVE**: "15"/"30" matched *inside the
  citation URL filename* `230515_...`; the bot's real answer is "tối đa 03 tháng" (3 months, wrong doc).
  Boundary-matching correctly rejects it.
**Progress:** the scorer is now strictly **more honest** — fixes a false-negative AND removes a
false-positive (the opposite of padding). Residual reclassification: **loa-return-vi → real pass** (and
loa-return-en's "1 month"/"one month" alternation now both match → de-noised); **thesis-days-vi → real fail**
(wrong doc/answer — a retrieval/extraction residual for A4, not noise). `baseline.json` NOT re-scored yet
(the multi-run aggregate only stores run-0 answers, can't be fully re-scored) → refresh via a fresh 3-run
baseline once A2a's Redis cache makes it cheap; the next A/B runs the new scorer on BOTH arms. No git commit.
