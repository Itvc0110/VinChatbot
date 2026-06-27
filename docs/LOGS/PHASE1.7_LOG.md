# Phase 1.7 — Eval-set expansion + Adaptive retrieval (point-lookup routing) — Plan

Two linked workstreams, **Part A first** (it's the measuring stick for Part B):
- **Part A — Validation-set expansion.** 86 cases is too few to adjudicate small changes (see below);
  grow + harden it, non-circular and point-lookup-heavy.
- **Part B — Adaptive retrieval.** A cheap heuristic router (intent + regex) sends point-lookup
  queries to a domain-general target (full-section retrieval + strict LLM extraction), fixing the 1.6
  calendar wrong-date and the financial cross-lingual miss **without** per-domain structured schemas.

Legend: [ ] todo · [~] in progress · [x] done · [-] deferred.
House rules: `ENABLE_*`-gated; A/B before promotion; **one eval at a time** (PHASE1.4 quota lesson);
build on existing code; non-circular golden cases (validated vs source, not vs the agent's own answer).

> **Status: ✅ SHIPPED (2026-06-16).** Part A: eval set **86 → 130** + `run_eval.py --diff` +
> `baseline.json`. Part B: **adaptive retrieval deployed** (`ENABLE_ADAPTIVE_RETRIEVAL` default
> **true**) — point-lookups read the full section + strict prompt; calendar drops query expansion
> (precision), financial keeps it + a cross-lingual variant (recall). A/B (v3) **fixes the 1.6
> calendar wrong-date AND the persistent VI→EN fee misses; guards 1.000**. **Phase 1.8 (cross-lingual
> VI↔EN expansion, all domains) added + confirmed:** full 130-case eval **0.885** (production config,
> the best of the arc — calendar 0.929, financial 0.875, guards 1.000); `data/eval/baseline.json`
> re-snapshotted to it. Offline: ruff clean, 118 passed (2 pre-existing chunker fails). Reverts:
> `ENABLE_ADAPTIVE_RETRIEVAL=false` / `ENABLE_CROSSLINGUAL_EXPANSION=false`. ARCHITECTURE §2b flow
> chart done. Open: multi-run eval averaging (single-run noise ~±3 cases).

---

# Part A — Validation-set expansion (do first)

## Why (the statistics)
- Today: **86 cases** → each case = **1/86 ≈ 1.16%** of "overall". A single flip moves the headline by
  ~1.2% — **below** observed run-to-run nondeterminism (calendar alone swung ±2 cases / ~7% across 1.6
  runs). So a −1-case A/B result (like 1.6's 0.930→0.919) is **statistically indistinguishable from
  noise** at this size. We literally cannot tell if the calendar regression "really matters."
- Worse, the **point-lookup sub-class** that's actually fragile (adjacent-date/fee distractors) is a
  handful of cases buried in `calendar`/`financial` — too thin to measure a targeted fix.
- **Target:** grow **86 → ~130–150**, weighted to the fragile zones, so (a) each category has enough
  mass and (b) the point-lookup distractor class is ≥ ~20 cases — enough that a real Part-B
  improvement clears the noise floor.

## What to add (~45–60 new cases)
| Category | Now | Add | Focus |
|---|---|---|---|
| calendar | 28 | +15–20 | **point-lookups with adjacent-date distractors**: final/midterm exam schedules, publish/announce dates, add/drop deadlines, registration windows, holidays, convocation — Fall/Spring/Summer × EN/VI. Each gets `forbidden_facts` = the neighbouring date (catches over-share / wrong-adjacent-row). |
| financial | 8 | +8–10 | program × level fee disambiguation; per-semester vs per-year; refunds/fines; **VI query vs EN tariff** (the known cross-lingual miss). |
| services / library | 5 | +6–8 | thin domain that *benefits* from fusion: library hours/contact, registrar procedures, student gateway, IT help. |
| policy / conduct | 13 | +4–6 | multi-step procedures (LOA, appeals, transfer credit), EN/VI. |
| adversarial / safety | 23 | +4–6 | multilingual role-play / encoded / many-shot — keep **guard recall** measured (FUTURE §E). |

Keep proportions balanced so "overall" isn't dominated by one bucket; always read **per-category**,
not just the headline.

## How (non-circular, fair) — the careful part
1. **Draft questions in student phrasing**, paraphrased — *not* copied from source docs (avoids the
   circular-set trap, PHASE1.4). Vary EN/VI and surface form.
2. **Run each through the live agent** to see its answer (exploration only — not ground truth).
3. **Fact-check against the official source** (calendar PDF / tariff doc / policy). Lock
   `required_facts` to the **source-verified** value + `expected_source`. Ground truth comes from the
   document, never from the agent's own output.
4. For point-lookups, add `forbidden_facts` = the **distractor** value (neighbouring exam week, other
   program's fee) so the case specifically catches the wrong-adjacent-row failure.
5. Avoid scorer-unfair cases (token-match edges like "temporary"≠"temporarily"); tag new cases
   `held_out: true` (metadata only) to track non-circular provenance.

Schema = the existing [run_eval.py](../../scripts/run_eval.py) format (`id`, `question`,
`required_facts`, `forbidden_facts`, `expected_source`, optional `turns`, `expects_refusal`); files
under `data/eval/golden/` (+ `calendar_golden_qa.json` for calendar).

## Tooling (recommended, reusable — FUTURE §A)
- [ ] **Regression diff:** snapshot `baseline.json` + `run_eval.py --diff baseline.json` that prints
  per-case flips (pass→fail / fail→pass) + per-category deltas — automates the by-hand diff I did in
  1.6, making **every future A/B trustworthy**. Small, high-leverage.
- [-] (Later) retrieval-only metrics (recall@k via `expected_chunk`); LLM-judge tier behind `--judge`
  for semantic equivalence. Out of scope here.

## Part A — checklist
- [ ] Author + source-validate ~45–60 new cases per the table.
- [ ] (Opt) build `--diff` + `baseline.json`.
- [ ] Run one full eval → record the **new reference number** (composition changed → new baseline; OK).
- [ ] `pytest -m "not live"` + `ruff` green (golden JSON loads; no scorer breakage).

**Resolved:** target ~130–150; **I draft + live-validate in batches, you spot-check**; diff tooling
built as part of Part A.

## Proposed execution order (Part A)
1. **Build the diff tooling** (code only, no quota): `run_eval.py --diff <report.json>` printing
   per-case flips + per-category deltas.
2. **Draft + live-validate new cases in batches** (calendar → financial → services → policy →
   adversarial), source-checked; pause for your spot-check after the first batch to calibrate
   style/strictness before scaling.
3. **Full eval → record the new reference baseline**, snapshot `baseline.json` for Part B's A/B.

---

# Part B — Adaptive retrieval (point-lookup routing)

## Decided architecture
```
query → is_point_lookup(intent/category, query)         ← B: cheap heuristic, reuses existing signals
   ├─ point-lookup → expansion OFF (no distractor flooding)
   │                + full-section retrieval (reuse parent-doc)        ← general target, no schema
   │                + strict "answer the exact value asked" prompt (calendar/financial specialists)
   └─ prose        → expand + RRF-fuse + rerank-once                   ← the 1.6 path, unchanged
```
- **Router is near-free:** signal already exists — supervisor **intent** (`calendar`/`financial`),
  tool **category** via `enforced_filters` ([tools.py](../../vinchatbot/app/agents/tools.py)), and the
  **year/term regex** in `apply_metadata_boosts` ([context.py](../../vinchatbot/app/rag/context.py)).
  New domain later = add a keyword, not a schema.
- **Target reuses built code:** `expand_to_parent_sections` (parent-doc) already stitches a chunk's
  full section; it was shelved for calendar only because the model **over-shared** neighbours — a
  *prompt* problem, fixed by the strict instruction.

## Part B — checklist
- [ ] **Router:** `is_point_lookup(query, category)` helper — True if `category in {calendar,
  financial}` or query matches point-lookup regex (year/term/amount/deadline/exam/fee/policy-code).
- [ ] **Retrieval path:** in `_search`, when point-lookup → skip `expand_query` + request section
  expansion; plumb a per-call `expand_sections: bool` through `search()`/`_finalize`
  ([retriever.py](../../vinchatbot/app/rag/retriever.py)) so parent-doc turns on for *this* query
  (bypassing the global flag + calendar skip).
- [ ] **Strict prompt:** add "answer ONLY the exact value asked; don't volunteer adjacent
  dates/amounts" to the calendar + financial specialist prompts
  ([prompts.py](../../vinchatbot/app/agents/prompts.py)).
- [ ] **Gate:** `ENABLE_ADAPTIVE_RETRIEVAL` (default **false**), fail-open; add `point_lookup` to the
  1.5 `chat_turn` log.
- [ ] **Unit tests:** `is_point_lookup` truth table; point-lookup path skips expansion (reuse the
  counting-retriever in [test_retrieval.py](../../tests/test_retrieval.py)).
- [ ] **A/B on the Part-A set:** flag-off vs on. Win = recover the calendar point-lookups (incl. the
  Summer-2027 wrong-date) + ideally the financial cross-lingual case, no prose regression, guards 1.000.

## Risks
- **Prompt tightening backfired before** (PHASE1.4 `phase4-v2`, net −1) — keep the strict instruction
  *narrow* (date/amount exactness only); A/B and revert if synthesis/prose regresses.
- **Parent-doc over-share** is exactly why calendar was skipped — verify the strict prompt suppresses
  neighbour-volunteering (the Fall add-deadline `forbidden_facts: October 9` case).
- **Token cost** ↑ on point-lookup turns (full sections) — minority of traffic; prose keeps the 1.6 cut.
- **Router misclassification** — coarse by design; fail-open + A/B catch gross errors.

## Why not structured KB (A) now
O(domains) maintenance (extractor + schema + tool per data type). The general target handles any
tabular/list data with no schema. Keep A as a **targeted upgrade** only if the expanded eval shows
calendar/fees still missing after Part B.

---

## Result log

### 2026-06-16 — Part A shipped; Part B A/B done (decision pending)

**Part A — eval set 86 → 130** (`run_eval.py --diff` tooling + `baseline.json`). New
`calendar_pointlookup` category (30, adjacent-date distractors) + financial/adversarial/safety
additions; services/policy deferred (no local source). Offline: ruff clean, 116 passed (+ the 2
pre-existing chunker fails).

**New baseline (adaptive off), 130 cases — `eval_20260616T033051Z.json`:** overall **0.846**; guards
1.000; calendar 0.857; calendar_pointlookup 0.767; financial 0.688; policy_conduct 0.571.

**Part B candidate (adaptive on) — `eval_20260616T034922Z.json`, `--diff` vs baseline:** overall
**0.869 (+3 net, +7/−4)**. Guards 1.000 (unanswerable 0.8→1.0). calendar 0.857→0.893,
calendar_pointlookup 0.767→0.800, policy_conduct 0.571→0.714. **The 1.6 live wrong-date bug
(`calendar-summer-final-exams-vi`) is FIXED.** financial 0.688→0.625 (−1, noise-floor on 16 cases).

**Root cause of the 4 losses (report diff):**
- `calendar-graduation-vi`, `calendar-hung-king-vi`, `fin-library-overdue-fine-vi` → **refusals**:
  expansion-OFF cut recall for low-salience facts (holidays/library fine) the paraphrase variants used
  to surface.
- `fin-standard-credit-en` → **over-share**: answer volunteered the Nursing rate (9,780,000 =
  forbidden); the strict prompt is VI-only and didn't catch the EN answer.

**Insight:** the win comes from **full-section reading + strict prompt** (model picks the exact row),
NOT from disabling expansion — which only cost recall. Two cheap refinements: (1) keep query-expansion
ON for point-lookups; (2) bilingual strict prompt. Net is already +3 with the target bug fixed and
guards intact.

**v1 decision:** user chose refine + re-A/B.

### 2026-06-16 — Part B refined re-A/B (v2: expansion kept + bilingual prompt)

Refinements: keep query-expansion ON for point-lookups (full-section is the real fix) + bilingual
strict prompt. Re-A/B `eval_20260616T041727Z.json` vs the same baseline:

| Category | baseline | v1 (exp OFF) | v2 (exp ON) |
|---|---|---|---|
| overall | 0.846 | 0.869 | **0.877** |
| financial | 0.688 | 0.625 | **0.812** |
| calendar_pointlookup | 0.767 | **0.800** | 0.733 |
| calendar | 0.857 | 0.893 | 0.893 |
| guards (adv/safety/unans) | 1.000 | 1.000 | 1.000 |

**Key finding (verified):** the two point-lookup domains have **opposite optimal**. Calendar wants
expansion OFF — its date grid's neighbouring rows are pure distractors, and with expansion ON the
headline bug returns (`calendar-summer-final-exams-vi` again answers "16–20 Aug" — verified in the v2
report). Financial wants expansion ON — cross-lingual fee lookups need paraphrase recall to hit the
EN tariff (financial 0.688→0.812). So no uniform expansion setting wins both; full-section + strict
prompt help both but don't override the expansion effect.

**Decision: PENDING USER.** Recommended next = **domain-differentiated** (v3): skip expansion only
for *calendar* point-lookups, keep it for *financial*; full-section + strict prompt for both. Likely
captures v1's calendar wins + v2's financial wins (> 0.877, headline bug fixed). Costs one more A/B.
Alternatives: ship v1 (0.869, fixes calendar bug, financial regressed) or v2 (0.877, financial great,
calendar bug remains). `ENABLE_ADAPTIVE_RETRIEVAL` still default-off.

### 2026-06-16 — Deep analysis (persistent-core breakdown) → bigger levers

Cross-run analysis (baseline ∧ v1 ∧ v2). **10 persistent fails** (no expansion setting fixes them):
- 2 `calendar-source-inconsistency` + 2 `pol-loa-*` = known by-design / scorer-morphology edges
  (PHASE1.4); not retrieval-fixable.
- **4 calendar "period" cases** (`fall-evaluation-vi`, `spring/summer-grade-release`) =
  **wrong-document / cross-term retrieval**: `fall-evaluation-vi` cited a registrar *blog* (Summer-2026
  exams); `spring-grade-release-en` returned **Fall's** dates (25 Jan–12 Feb) for a Spring query. The
  calendar PDF loses to blogs and the model confuses term rows — not a rerank-on-the-table problem.
- **2 financial** (`fin-nursing-tuition-year-vi` refused; `fin-standard-credit-vi` → Nursing's
  9,780,000) = the long-standing **VI-query vs EN-tariff cross-lingual** gap (PHASE1.4).

**Levers identified (beyond the expansion toggle):**
1. **Cross-lingual query expansion** — add an EN variant for VI queries (today expansion is
   "same language" in [query_engineering.py](../../vinchatbot/app/rag/query_engineering.py)). Targets the
   persistent financial cross-lingual core.
2. **Calendar-source boost** — boost the Academic Calendar PDF over registrar blogs for
   calendar-routed queries (extend `apply_metadata_boosts` in
   [context.py](../../vinchatbot/app/rag/context.py)). Targets the wrong-document calendar fails.
3. **v3 domain-differentiated expansion** (calendar off / financial on) — the expansion-sensitive flips.
4. (Bigger, deferred) **structured calendar lookup** — the calendar_event records already exist
   (PHASE1.0); an exact (term, event) filter would definitively fix the calendar "period" core.

**Decision: PENDING USER** — choose the next A/B scope (v3 alone, or v3 + cross-lingual expansion, or
+ calendar-source boost). `ENABLE_ADAPTIVE_RETRIEVAL` still default-off.

### 2026-06-16 — v3 (domain-differentiated + cross-lingual) A/B — CONTAMINATED, re-running

Implemented v3: calendar point-lookups DROP expansion (precision); financial/other KEEP expansion +
an English cross-lingual variant ([query_engineering.py](../../vinchatbot/app/rag/query_engineering.py)
`cross_lingual`); full-section + bilingual strict prompt for both. ruff + 7 retrieval tests green.

**A/B `eval_20260616T084949Z.json` = 0.854 — NOT TRUSTWORTHY.** The run logged a mid-run
`httpx.ConnectError` (rerank fell back to original order) + a Langfuse export timeout → transient
network degraded some turns. Confirmed noise: `calendar_pointlookup` = 0.700 here vs 0.800 in v1
despite **identical** calendar logic (both expansion-off) — a ±3-case/±10% swing on a 30-case
category. **Lesson (again, cf. PHASE1.4): a run with network errors is invalid.**

**Robust signals still visible (per-case, mechanistic):** guards 1.000; calendar 0.857→0.893
(`calendar-summer-final-exams-vi` fixed via expansion-off); **cross-lingual lever worked** —
`fin-nursing-tuition-year-vi` + `fin-nursing-tuition-credit-vi` (both *persistent* VI→EN fails)
recovered; policy_conduct 0.571→0.714; unanswerable 0.8→1.0.

**Meta-finding:** single-run A/B at 130 cases is noise-dominated for <~3% deltas (overall band
0.846/0.869/0.877/0.854 across runs). Future eval-rigor item: multi-run averaging or a fixed-seed /
lower-variance harness (FUTURE §A). **Action: re-run v3 cleanly with `ENABLE_LANGFUSE=false`** (cuts
network load + the export timeout) to get an uncontaminated number before the promotion call.

### 2026-06-16 — OpenRouter outage, then clean v3 A/B

The first clean-attempt was blocked: OpenRouter became **unreachable** (~16:00–16:25; `httpx.ConnectError`
on connect, `/models` HEAD timed out). Stopped the contaminated run; user rotated to a new key;
verified `/key` → HTTP 200. Re-ran clean (`ENABLE_LANGFUSE=false`).

**Clean v3 A/B `eval_20260616T094657Z.json` (no network errors):** overall **0.854** (+1 net vs
baseline). calendar 0.893 (bug `calendar-summer-final-exams-vi` fixed), financial 0.688→0.750
(`fin-nursing-tuition-year-vi` + `-credit-vi` — persistent VI→EN — recovered), policy_conduct 0.714,
unanswerable 1.0, guards 1.000. Dips: calendar_pointlookup 0.700, multiturn 1.0→0.75
(`mt-followup-refusal-en`).

**Three-run comparison (all vs the 0.846 baseline):**

| variant | overall | calendar | cal_pointlookup | financial | calendar bug | x-lingual nursing |
|---|---|---|---|---|---|---|
| v1 (exp off all PL) | 0.869 | 0.893 | 0.800 | 0.625 | fixed | — |
| v2 (exp on all PL) | 0.877 | 0.893 | 0.733 | 0.812 | **not fixed** | — |
| **v3 (cal off / fin on)** | 0.854 | 0.893 | 0.700 | 0.750 | **fixed** | **fixed** |

**Decisive noise check:** v1 and v3 share identical calendar logic (expansion off) yet
calendar_pointlookup = 0.800 vs 0.700 — a 3-case nondeterministic swing. The overall band is noise;
single runs can't rank the candidates. v3's lower 0.854 is mostly that swing.

**Recommendation: deploy v3** — the design-correct option (fixes the headline calendar bug AND the
cross-lingual financial core, guards 1.000, flag-gated + one-flag revert). Ship on mechanistic merit
since effect < eval noise and risk is low; add **multi-run eval averaging** as a fast-follow
(eval-rigor) to confirm the overall.

### 2026-06-16 — DEPLOYED v3 (user approved)

`enable_adaptive_retrieval` default flipped **False → True** ([config.py](../../vinchatbot/app/core/config.py));
`ENABLE_ADAPTIVE_RETRIEVAL=true` added to [.env.example](../../.env.example). `ENABLE_RERANK_AFTER_FUSION`
stays true (1.6) — prose + financial point-lookups use fuse→rerank-once. Offline: `ruff` clean,
`pytest -m "not live"` **117 passed**, 2 pre-existing `test_chunker.py` fails (docx/markdown).
**Revert:** `ENABLE_ADAPTIVE_RETRIEVAL=false` → 1.6 behavior, byte-identical (retrieval + strict
prompt both flag-gated); no data migration.

### 2026-06-16 — Phase 1.8: cross-lingual (VI↔EN) expansion, all domains

Made cross-lingual its own lever, **independent** of same-language paraphrase expansion. `expand_query`
([query_engineering.py](../../vinchatbot/app/rag/query_engineering.py)) refactored into **3 clear modes**
(`paraphrase` / `cross_lingual` / both) in one LLM call; `_search`
([tools.py](../../vinchatbot/app/agents/tools.py)) now computes `paraphrase = ENABLE_QUERY_EXPANSION and
not (calendar point-lookup)` and `cross_lingual = ENABLE_CROSSLINGUAL_EXPANSION` (new flag,
[config.py](../../vinchatbot/app/core/config.py), default **true**). So calendar point-lookups get the
**translation variant but NOT the paraphrase flood**. Bidirectional (the failing direction was VI→EN
vs the English calendar/tariff). ruff clean; 8 retrieval tests (incl. calendar-xling-only & financial).

**Calendar-only live A/B (58 cases, cross-lingual ON) vs shipped v3 (`eval_20260616T164230Z.json` vs
`…094657Z.json`):** calendar **0.893→0.929**, calendar_pointlookup **0.700→0.767**, net **+5/−2**.
**Headline bug `summer-final-exams-vi` still PASSES** ("23–27 tháng 8"). Persistent `fall-evaluation-vi`
(had cited a registrar blog) **recovered** — the EN variant matched the English calendar, the predicted
mechanism. Losses: `summer-evaluation-vi` (eval-vs-exam near-tie) + `convocation-vi` (holiday refusal)
— known hard patterns / noise, not cross-lingual harm. **→ delivered (kept default-on).**

**Full 130-case eval (2026-06-17, production config) — `eval_20260616T171904Z.json`, `--diff` vs
shipped v3:** overall **0.854 → 0.885 (+6/−2)** — the **best of the whole 1.6/1.7/1.8 arc**. Guards
1.000; calendar 0.893→0.929; **financial 0.750→0.875** (cross-lingual recovered the VI fee cases
`fin-medicine-tuition-year-vi` + `fin-other-bachelor-year-vi`); multiturn 0.75→1.0. Losses:
`calendar-summer-grade-release-en` (hard persistent) + `pol-loa-applicability` (policy LOA, known-flaky
1/7). **Decision: Phase 1.8 CONFIRMED — cross-lingual kept default-on.** Re-snapshotted
`data/eval/baseline.json` to this run (new production reference, 0.885). Watch-item: cross-lingual on
prose occasionally churns the flaky policy LOA cases (noise-level; revert = `ENABLE_CROSSLINGUAL_EXPANSION=false`).

**Open follow-ups (not blocking):**
- **Eval-rigor:** multi-run averaging / lower-variance harness — the ±3-case noise prevents confident
  overall ranking (FUTURE §A).
- **Calendar "period" persistent fails** (evaluation/grade-release) + cross-term confusion → candidate
  for the deferred **structured calendar lookup** (calendar_event records already exist, PHASE1.0).
- **Calendar-source boost** (Academic Calendar PDF over registrar blogs) for the wrong-document fails.
- Services/policy eval cases (deferred in Part A — need source docs) to grow those thin categories.
