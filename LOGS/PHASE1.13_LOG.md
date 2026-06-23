# Phase 1.13 + 1.14 — Calendar correctness + Embedding A/B (combined full re-ingest)

> Working log for the combined re-ingest effort (calendar parser hardening + multilingual embedding +
> full-scale re-crawl). Status board lives in [LIVE_FEEDBACK_TRACKER.md](LIVE_FEEDBACK_TRACKER.md).
> Production reference before this effort: **0.923 / 130** on the old polluted `vinuni_documents`.

## Goal
Fix the calendar year/row confusion at production scale AND test a stronger VI↔EN embedding, in ONE
clean re-crawl + re-ingest. Then return to the "drop the multilingual translation expansion" experiment.

## Decisions locked
- **Embedding = `intfloat/multilingual-e5-large` via OpenRouter** (`EMBEDDING_BACKEND=openrouter`,
  `OPENROUTER_EMBEDDING_MODEL=intfloat/multilingual-e5-large`). Cross-lingual probe (12 VI↔EN pairs):
  e5 **12/12** top-1 / MRR 1.000 vs 3-small 11/12 (0.944) and 3-large 11/12 (0.938 — English-first
  upgrade, no bilingual gain). OpenRouter serves e5 (1024-d) + bge-m3 — **no new key, fast API**.
  Local fastembed e5 also wired (`fastembed_local`) but **too slow** (12 min vs ~3 min/716 chunks).
- **No paid embedding worth it:** Cohere embed-v4 / gemini-embedding-001 / Voyage rank above e5 on MTEB
  but need native keys (not OpenRouter) and e5 already maxes our probe.
- Bug fixed: `build_embeddings` sets `check_embedding_ctx_length=False, tiktoken_enabled=False` for
  non-OpenAI models (LangChain tiktoken-tokenizes → e5/bge return "No embedding data received").

## Parser / crawler hardening (calendar correctness — embedding-independent)
1. `infer_academic_year`: prefer a *consecutive* year-range in the TITLE region; handle en-dash + `AY24-25`
   + URL hints; **no hardcoded guess**. (Old code took the first range anywhere + a 2025/2026 coin-flip →
   en-dash `2026–2027` was missed → AY=None → every event mis-yeared.)
2. `extract_calendar_events` keyword gate broadened: added evaluation/commencement/orientation/VN
   holidays, then **marking/appeal/grade/release/results/gradebook/timetable/schedule (+VN chấm điểm/
   phúc khảo/công bố điểm/điểm/lịch thi)** — the grade-release cycle rows were silently dropped.
3. `_date_token_to_iso`: return None instead of hardcoding 2025/2026 when no AY context.
4. Crawler scope: `_is_policy_allowed_path` now allows `"calendar" in path` (the AY2025-26 page was
   `policy_path_out_of_scope`).
- Tests: `tests/test_calendar_parser_hardening.py` (12), full suite 240 passed, ruff clean.
- **Validated on real crawl:** every calendar PDF now carries its correct AY; ISO years line up; the 3
  "Marking + Appeal + Grade release" rows now extract (Fall→2027-01-25, Spring→2027-06-21, Summer→2027-08-30).
- **DATA FINDING:** `policy.vinuni.edu.vn/vinuni-academic-calendar` 301-redirects to the AY2026-27 PDF →
  **AY2025-26 is gone** → June-2026 real events uncrawlable → honest no-data is the correct behavior.

## Full crawl + corpus hygiene
- `crawl_seed.py --seed-file core_seeds.json --max-pages 2000` → **1780 docs / 177-of-177 seeds**, but it
  wandered onto external domains via outbound links → **744 off-topic junk** (apps.apple.com 222,
  sheffield.ac.uk 142, sc.edu 164, aacrao.org 110, cornell, google/apple legal). Verified: none hold
  authoritative VinUni data; keeping them would risk **wrong-source answers** (Cornell/Sheffield policy).
- Added `ingest_documents.py --vinuni-only` → keep docs whose domain contains "vinuni" → **1045 docs**.
  Coverage verified comprehensive: 400 policy, calendar 7, financial 10, scholarship 7, integrity 28,
  library 7, registrar 49, career 74, health 15, visa 13, admission 8 (housing thin at 2).
- Full e5 ingest → **`vinuni_full_e5`: 1045 docs → 13,035 chunks → deduped 10,963 → indexed** (green).

## Eval #1 — e5 + bilingual expansion ON vs 0.923  (`eval_20260620T081707Z`) = **0.900** (+3 / −6)
- Guards: adversarial 1.0, safety 1.0; **unanswerable 1.0→0.8** (regression). conduct/multiturn/services 1.0.
- **calendar GAINED** (the goal): pointlookup 0.8→0.833; graduation-vi + summer-evaluation-vi recovered.
- **financial 0.938→0.75** (regression); policy_conduct 0.857 held.
- Full failure landscape: **6 regressions** (3 financial, 1 calendar grade-release, pol-loa-fulltime-vi,
  unans), **7 persistent never-passed** (5 calendar grade-release/evaluation/source-inconsistency,
  fin-standard-credit-vi), **3 gained**.

### Root causes (per architectural layer)
- **Financial over-share (specialist generation):** the full crawl added the authoritative multi-program
  tariff PDFs; retrieval now prefers them over the old clean `experience.vinuni.edu.vn` page; the model
  **dumps the whole table** → leaks Nursing/MD rows → hits `forbidden_facts`. The **output-watcher cannot
  catch this** (answer is grounded/cited; `should_gracefully_degrade` only refuses *uncited* answers).
- **unans-future-tuition (specialist generation):** rich corpus gives a confident tariff → model lists
  current figures + hedges about 2031 instead of refusing. Baseline passed only because it had no
  confident tariff → graceful-degradation fired.
- **Calendar grade-release ×5 (parser + prompt):** the "Marking + Appeal + Grade release" rows weren't
  extracted (gate) AND carry **no term label**, and the calendar interleaves next-term's timetable-release
  before this-term's grade-release → term can't be inferred by position. (Summer asked → model returned
  Spring's Jun-Jul row.)

### Fixes applied
- `FINANCIAL_PROMPT`: (a) from a multi-program table report ONLY the asked program's figure, never
  volunteer others; (b) for a specific year with no tariff, give NO figures + suggest official sources.
- `extract_calendar_events`: keyword gate now captures the grade-release cycle (re-validated: 33 events).
- `CALENDAR_PROMPT`: grade-release/marking/appeal follows each term's exams (Fall→Jan-Feb, Spring→Jun-Jul,
  Summer→Aug-Sep); match by term or list each labelled — don't return another term's period.

### Cheap targeted re-test (prompt-only fixes, pre-re-ingest)
- ✅ unans-future-tuition-en now **refuses cleanly** (graceful-degradation) — guard recovered.
- ✅ fin-standard-credit-en, fin-other-bachelor-semester-vi PASS.
- ⚠️ fin-standard-credit-vi, fin-other-bachelor-year-vi still **intermittently leak** (VI) — prompt
  reduces but doesn't eliminate; robust fix = per-program fee chunks (retrieval layer, Phase 1.16).

## Eval #3 — e5 + fixes + expansion ON vs 0.923  (`eval_20260620T100314Z`) = **0.869** (+4 / −11)
- **Fixes landed:** unanswerable **1.0** (guard recovered ✓); calendar-fall-grade-release-vi GAINED;
  fin-standard-credit-en + fin-other-semester-vi recovered.
- **But overall DOWN** — and the tell: **10 of 11 losses are VIETNAMESE.** calendar 0.929→0.821,
  pointlookup 0.8→0.767, financial 0.75 (fixed 2, broke 2 different VI ones).
- **Per-case nature:** the new VI calendar losses are **retrieval REFUSALS** (graceful-degradation),
  not wrong answers — e.g. calendar-fall-course-drop-vi and calendar-hung-king-vi REFUSED even though
  the events exist (9-Oct, 16-Apr). So retrieval failed to surface existing events on VI queries.
- **Hypotheses (both point to translation):** (1) cross-lingual translation expansion injects a noisy
  EN variant that displaces the native VI match (expansion fighting e5); (2) `reactive_expansion_min_score
  =0.35` is calibrated to 3-small's score scale → misfires on e5's distribution → recall misses.
- calendar-summer-grade-release-en still fails (model grabs Spring's Jun row for Summer despite the
  term rule); fin-nursing-tuition-credit-vi borderline (value correct).

## Deep loss analysis (eval #3, all 11 losses dissected)
Three failure modes — and a key measurement artifact:
- **CITATION-SLUG ARTIFACT (3): correct answer, penalized for citing a different valid source.**
  `_score_case` requires `expected_source` substring ⊂ a cited URL. EN financial queries cite the EN
  HTML policy page (`.../all-policies/financial-regulations-and-tariff-for-student-2/` → slug matches →
  PASS); VI queries cite the **VI-language tariff PDF** (`VU_TS03.VN_Quy-dinh-tai-chinh-va-Bieu-phi`
  → slug does NOT match → `cite_ok=False` → FAIL) **despite facts_ok=True** (fin-nursing-credit-vi
  9,780,000 ✓; fin-other-bachelor-year-vi 815,850,000 ✓; fin-standard-credit-vi ✓). The EN page and VI
  PDF are the SAME document (the EN page links the VI PDF). → **The eval UNDER-states true quality**;
  35/130 golden cases pin `expected_source`, so any corpus-driven source shift reads as a regression.
  Fix options: (a) broaden `expected_source` to accept the VI tariff PDF, or (b) accept any
  policy.vinuni tariff source. (Surface to user — don't silently game the eval.)
- **RETRIEVAL REFUSAL (4, VI-only):** fall/spring-course-drop-vi, hung-king-vi, library-fine-vi
  graceful-degraded though the event/fee EXISTS. → e5 score-scale vs `reactive_expansion_min_score=0.35`
  and/or translation-expansion noise. Eval #4 (expansion OFF) isolates this.
- **WRONG-FACT (4, genuinely hard):** fall/spring-final-schedule-vi (wrong dates; Spring'27 → "Jan 2028"
  wrong YEAR), summer-grade-release-en (returns Spring's Jun row), victory-day-vi (not found),
  pol-loa-fulltime-vi (wrong section). The keyword-gate broadening is **double-edged**: gained
  grade-release but added competing end-of-term events (Exam-Schedule-Release / Timetable-Release /
  Gradebook) on the same dates → likely worsened final-schedule lookups.

**Implication:** true quality is materially higher than 0.869 (≈ +3 from the citation artifact alone).
The genuine residuals are 4 VI refusals (likely expansion) + ~4 hard calendar term-attribution cases.

### Two more insights from the calendar dump
- **EN passes / VI fails — the dominant fingerprint.** Matched pairs in eval #3: fall-course-drop,
  fall-evaluation, hung-king, spring-course-drop, victory-day, fall-final-schedule, spring-final-schedule
  ALL pass in EN and fail in VI (same data/prompt, only query language differs). 7 calendar pairs +
  3 VI financial artifacts → the regression is **Vietnamese-specific** = the cross-lingual translation
  expansion fighting e5's native VI matching (e5 already matches VI→EN; the extra translated variant
  pollutes the fused pool → VI answers destabilize/refuse). Eval #4 (expansion OFF) is the decisive test.
- **SOURCE-DATA mislabel (real, in VinUni's calendar):** the AY2026-27 calendar lists `7-18-Jun Final
  Exam Period - Fall'26` — June exams labeled Fall'26 (should be Spring'27). Drives
  calendar-source-inconsistency-en/vi (flag-the-conflict behavior) + calendar-spring-final-schedule-vi
  (Spring exams ARE the mislabeled June ones). The bot can't fix a wrong source — only surface it.

## Eval #4 — e5 + expansion OFF vs 0.923  (`eval_20260620T102109Z`) = **0.854 raw**
- **Calendar RECOVERED:** 0.821→**0.893** (the VI calendar refusals from eval #3 — fall/spring-course-drop,
  hung-king, victory-day, fall-evaluation — all came back). Confirms translation was hurting VI calendar.
- **Financial cratered to 0.50 — but 7 of 8 fails are CITATION ARTIFACTS** (facts_ok=True, cite_ok=False):
  every financial VI case gives the CORRECT number, cites the VI tariff PDF (VU_TS03.VN…), and is
  penalized vs the EN slug. Only fin-library-overdue-fine-vi is a real fact error. (EN financial = all pass.)

## Citation artifact FIXED (golden maintenance, user-approved)
- `run_eval._score_case`: `expected_source` now accepts a **list** of acceptable slugs (backward-compat str).
- `data/eval/golden/financial.json`: 14 cases' `expected_source` →
  `["financial-regulations-and-tariff-for-student", "tai-chinh-va-bieu-phi"]` (EN page + VI PDF = same doc).
- **Offline re-score of the stored answers with the fixed golden (no re-run):**
  - **eval #4 (expansion OFF) = 0.908** (118/130) ✅  ← winner
  - eval #3 (expansion ON) = 0.892 (116/130)
- **DECISION: e5 + expansion OFF is the config** — best quality (0.908) + determinism (no translation call)
  + 10× corpus + correct calendar. Guards stay 1.000 (adversarial/safety/unanswerable).

## Remaining true residuals vs 0.923 (~2 cases, genuinely hard)
- calendar-source-inconsistency-en/vi + calendar-spring-final-schedule-vi — driven by the SOURCE mislabel
  (`7-18-Jun Final Exam Period - Fall'26`). Behavior = flag the inconsistency; can't fix the source.
- calendar-summer-grade-release-en — term-attribution (returns Spring's Jun row).
- fall/spring-final-schedule-vi — keyword-gate over-broadening added competing end-of-term events.
- pol-loa-fulltime-vi (wrong section), fin-library-overdue-fine-vi (1 real fact).

## Residual cleanup (Phase 1.13b) — event-type + term-inference + prompt
- `infer_event_type`: 4 distinct end-of-term types (exam_schedule_release / evaluation_period /
  exam_period / grade_release) — were collapsed to exam_period/academic_event.
- `extract_calendar_events`: term-inference fills a MISSING term for end-of-term events from the start
  month (Jan→Fall, Jun→Spring, Aug→Summer) → "Spring grade release" maps to the June row. The
  source-mislabeled June exam keeps its explicit `Fall'26` label (only missing terms are filled).
- `CALENDAR_PROMPT`: explicit 4-type disambiguation + must say "inconsistent / không nhất quán" on a
  label↔date conflict. 14 parser tests pass, ruff clean. Re-ingest → 10,967 chunks.

## Eval #5 — e5 + expansion OFF + ALL fixes vs 0.923  (`eval_20260620T120801Z`) = **0.923** (+6 / −6)
- **PARITY with baseline + guards 1.000** (adversarial/safety/unanswerable). calendar_pointlookup
  0.8→**0.9**; financial 0.938 (recovered via citation fix).
- **Gained (6):** fall-evaluation-vi, fall-grade-release-vi, spring-grade-release-vi, graduation-vi
  (event-type+term fixes), fin-standard-credit-vi (citation), pol-loa-purpose.
- **Lost (6):** 4 VI refusals (fall/spring-course-drop-vi, hung-king-vi, library-fine-vi) — the model
  graceful-degraded though the data exists/retrieves (library-fine retrieves at 0.909). These PASSED in
  eval #4 (same expansion-OFF, same retrieval) → **generation-layer nondeterminism**, oscillating in the
  noise band. + pol-loa-first-step (correct substance, missing literal "form") + pol-loa-fulltime-vi
  (hard cross-lingual: full-time eligibility is in an EN-only doc).
- `should_gracefully_degrade` has NO score threshold (refuses only on no-citation / unknown-marker), so
  the refusals are the model's own give-up decision, not a tunable knob.

## CONCLUSION
**0.923 parity on a far better system** (e5, 10× clean corpus, deterministic retrieval, correct calendar,
citation-fixed eval). The residual VI calendar cases flip run-to-run (generation nondeterminism that
expansion-OFF doesn't remove — it only fixed *retrieval* determinism). Practical eval ceiling reached;
further calendar chasing trades cases (whack-a-mole). → **Recommend promote.**

## Phase 1.13c — layer fixes for the VI residuals (NOT data-patches)
Per user direction ("fix losses that come from LAYERS, not from data; universal not case-patch"), the
VI losses were root-caused to **two systematic layer bugs + retrieval-orchestration**, all universal:
1. **`assess_faithfulness` was number-format-sensitive** — a correct VI answer ("10.000 đồng") scored
   ungrounded vs an EN source ("10,000 VND") → silently degraded to a refusal (library-fine: raw answer
   was correct with 7 citations, `degrade?=False` but `faithful?=False`). Fix: `_canon_numbers` collapses
   in-number separators so 10.000 / 10,000 / 10000 compare equal. +2 regression tests.
2. **Over-refusal without searching** — the model declined VinUni calendar holidays (Giỗ Tổ Hùng Vương)
   as "out of scope" with `tool_calls: []`, self-judging scope that already passed at the guard layer.
   Fix: BASE_PRINCIPLES "search-first; only refuse clearly out-of-scope (weather/code/celebrity)".
3. **Agent-decided cross-lingual** (Phase 1.17 pulled forward): `cross_lingual` is now a tool argument
   the specialist sets on a retry when its native-language search comes up short — translation fires only
   when needed (no always-on VI pollution). + answer-bias nudge + consolidated retrieval procedure
   (retry is cheap vs missing the answer) + bounded ReAct (`agent_recursion_limit=18`).
- **Smoke on the 6 loss cases: 5/6 recovered** (hung-king-vi, summer-grade-release-en, library-fine-vi,
  fall/spring-course-drop-vi). Only `pol-loa-fulltime-vi` remains = genuine DATA gap (full-time eligibility
  in an EN-only doc) → deferred to the fuller crawl, not patched. Full eval running to confirm net + guards.

## Eval #7 — e5 + expansion OFF + ALL layer fixes vs 0.923  (`eval_20260620T142958Z`) = **0.946** ✅
- **+6 / −3; ALL guards 1.000** (adversarial/safety/**unanswerable**). calendar_pointlookup 0.8→**0.933**,
  financial 0.938→**1.0**, calendar 0.929 held.
- **Layer fixes that landed:** (1) `assess_faithfulness` number-format (VI 10.000 = EN 10,000);
  (2) search-first (no refuse-without-search); (3) answer-bias + consolidated retrieval procedure;
  (4) exact-fact precedence (restored the `unanswerable` guard — answer only the EXACT asked scope, never
  substitute another year/program); (5) reactive cross-lingual = clean native first pass, multilingual
  SECOND loop when weak (deterministic, no always-on pollution); bounded ReAct (recursion_limit=18).
- **First-pass native recall measured = 86% (EN 98% / VI 71%)** → proves reactive is right (always-on
  would tax the 86% to help ~14%); the weak-trigger catches most VI misses (low native score → escalate).
- **3 residuals (deferred):** conduct-disciplinary-tiers-en + loa-fulltime-vi = "confident-WRONG content"
  (native retrieves wrong topic at HIGH score 0.819/1.015 → score-trigger can't fire → other-language
  chunk, which IS retrievable @0.974/0.915, never pulled). loa-first-step = nondeterministic (oscillates).
  → Fix = a relevance-aware escalation trigger ("escalate if top chunks lack the question's key terms",
  no extra LLM call) and/or #6/#7 structured lookup. NOT data-patched.
- **PROMOTABLE: 0.946 ≥ 0.923 + guards 1.000** on a 10× cleaner corpus + deterministic retrieval.

## PLANNED NEXT (this phase — do with whatever residuals remain)
- **#6 Structured calendar lookup (deterministic)** — for calendar point-lookups, query the structured
  `calendar_event` records directly with exact filters (`event_type` + `term` + `month/year`) instead of
  vector-retrieve→LLM-extract. Eliminates wrong-adjacent-row / wrong-term / nondeterministic-refusal for
  dates; fully deterministic. Data is READY (parser now emits clean event_type + inferred term + ISO) →
  mostly "add a lookup path + route point-lookups to it". (Codex P0; architecture: split knowledge access
  from agent reasoning.)
- **#7 Structured fee lookup** — financial analog: per-program/`fee_type`/period records queried
  deterministically → exact figure; kills adjacent-program-row leakage + fee point-lookup flakiness.
  Bigger: the multi-program tariff table must first be parsed into program-aware `fee_record` fields.
- **Clarification path (Phase 1.18a)** — ReAct rule to ask ONE clarifying question when a required scope
  is missing (which AY? which program? unresolved này/đó), no extra LLM call; tuned to avoid over-asking.
- **Data-gap residuals** (loa-fulltime-vi, etc.) — fix by crawling fuller VI policy data later, NOT by
  patching cases now.
- **Promote** — set `ENABLE_CROSSLINGUAL_EXPANSION=false` + e5 defaults; repoint production
  `QDRANT_COLLECTION` → `vinuni_full_e5`; update baseline.json. Infra: ingest embedding content-hash cache
  (skip unchanged chunks → re-index in seconds, not 40 min).
