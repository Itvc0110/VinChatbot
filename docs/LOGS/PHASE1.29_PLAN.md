# Phase 1.29/1.30 — Golden-set expansion + general orchestration/entity/corpus fixes (LIVING PLAN)

> **Living source-of-truth for this phase.** As problems surface mid-execution, fit each new problem into the
> matching section below (Part A golden gap, or a Part B fix row). Each Part-B fix gets its own
> `PHASE1.3x_LOG.md`. References the D1–D9 design in [ADAPTIVE_ORCHESTRATION_ROADMAP.md](ADAPTIVE_ORCHESTRATION_ROADMAP.md)
> and the problem map in [NEW_SEED_INGESTION_PLAN.md](NEW_SEED_INGESTION_PLAN.md). Status: ✅ done · ⏳ partial · ◻️ todo.

## ⏭️ Phase 1.32 — NEXT STAGE (post-plateau, 2026-06-25) — START HERE
State: **0.98/199, guards 1.000, cw 2** (doc-pin + G7 prune + calendar fix all promoted). Retrieval/doc-
selection is strong; the residual tail is **generation-side number-disambiguation** + hard probes. Per the
saved memory, **re-measure each item's real gap before building**. Prioritized:

1. **P1 — Multi-run baseline `--runs 3` (ENABLER, do FIRST).** Single-run noise is ±3 cases (Build B's 0.98
   baked 2 flaky PASSes — `calendar-fall-grade-release-en`, `pol-thesis-days-vi`). A generation-side fix moves
   ~1–2 cases — **below the single-run noise floor**, so it cannot be A/B'd reliably without multi-run
   averaging. Adopt `--runs 3` for the baseline + all promotion gates (the worklog's top open eval-rigor item).
   Refresh `baseline.json` to a 3-run baseline. Cheap, unblocks everything below. **No app-code risk.**
2. **P2 — Generation-side number-disambiguation (the dominant residual class).** Targets: `nursing-vi`
   (86 vs program-total 126), `pol-thesis-days-vi` (3 months vs 15/30 working days — confirm it's stable not
   flaky first via P1). The right doc is already retrieved/pinned; the LLM picks the wrong *competing* number.
   **Mechanism:** a targeted answer/point-lookup prompt rule — "when context holds multiple candidate numbers
   for the asked quantity, pick the one matching the question's specific qualifier (program-total vs category
   subtotal; 'working days' vs 'months'); name the qualifier/doc used." **HIGH blast radius** (affects every
   answer) → gate via a settings-driven prompt suffix (flag-default-off), A/B on the **3-run** baseline (must
   hold ≥ baseline, guards 1.000, no new cw; expect nursing-vi flip). Add a few competing-number golden cases.
3. **P3 — Deferred / revisit-if-needed (measure ROI first, each its own plan + log):**
   - **G1 multi-domain orchestrator** — only if multi-domain regresses or payoff grows (27-case substrate ready).
   - **D5 web-search** (`out_of_scope_ranking` 0/2) — real production value; scope the reactive Tavily tool.
   - **D8 entity table + E6 content** — affirmative "current Rector" (flips `leadership_enum` from hedge).
     ⛔ **2026-06-25 INVESTIGATION — BLOCKED (content gap + role ambiguity, like D5).** Corpus does NOT cleanly
     support the target's premise: Rohit Verma = "Founding **Provost**" (EN) + signed "HIỆU TRƯỞNG" (VI, 2021);
     **Tan Yap Peng = "Prof. Provost" on `vinuni.edu.vn/governance/`, NOT "Rector/Hiệu trưởng"** (his /people/
     bio is degrees only). No doc asserts "Tan Yap Peng = current Rector 2025". So D8 needs (a) **E6 content**
     (a leadership-announcement page clearly stating the current head's title — a crawl/ingest task; the
     "dropped news slug") and (b) an **SME/data answer** on the actual title (Provost vs Rector — the corpus is
     inconsistent). Curating "Tan Yap Peng = Rector" in a role table = authoring an UNVERIFIED fact (forbidden).
     → **Defer with D5 to post-teammate-merge** (content + data-modeling, not code). D9's safe hedge stays correct
     until then. Possible interim: re-scope `leadership_enum` to what the corpus supports (Provost succession),
     pending SME confirmation.
   - **D6 VI over-refusal** (`ltp-recordprivacy-access-vi`, re-scoped to cross-lingual).
   - **Calendar**: on the next full `ingest_documents.py` run, the keyword fix auto-applies to the 3 older
     calendars too (build B regenerated only the current one) — rebuild `structured_index.json` then.

**Discipline (unchanged):** measure-first → EnterPlanMode/plan-in-log per fix → implement behind `ENABLE_*`
default-off → `pytest`+`ruff` → `run_eval --runs 3` (scored + targets) → decode every flip (noise vs real;
empties = infra) → promote or revert → `PHASE1.3x_LOG.md` → update this doc. **No git commit unless asked.**
Honest read: the system is at a mature plateau — further eval gains are small and hard; the highest-value
moves may be P3 production-value items (D5/D8) the scored eval underweights, not more tail-chasing.

## Context
The v2 corpus (filter-fixed) + D9 intent-auditor are **promoted and live**. Remaining quality gaps were
scattered across the roadmap (failure-modes #1–#5, D1–D9), the ingestion plan (problem map A–F, golden Tracks
A/B/C), PHASE1.28 open items, UPDATE_PLAN (eval-rigor A, retrieval B), and chat. Some fixes (cross-domain D2,
clarification D4) were **deferred for lack of a measurement substrate** — so this phase does **golden first**,
which measures the recovered v2 content AND unblocks the A/B-gated fixes.

**Governing principle:** every fix is a **general mechanism for a problem CLASS**, never a per-case patch. Per
class: author golden probing the whole class (EN+VI, held-out third, `required_facts` from **source not bot
output**) → build one general mechanism → `--diff baseline --runs 3` (guards 1.000, `confidently_wrong` not up)
→ decode every flip → keep/revert + log (incl. rejects).

**Already shipped (do NOT re-do):** ingest-filter overhaul; D9 auditor (`ENABLE_INTENT_AUDIT`, promoted);
golden `expansion.json` (8) / `identity_intent.json` (7) / `recovered_content.json` (4); list-mode. Score-sorted
citations = **A/B-rejected** (reverted).

## Process (two standing rules)
1. **EnterPlanMode for EVERY Part-B fix** — a dedicated per-step plan (mechanism, edges, golden mapping, A/B)
   before code. Part-A golden authoring does not need per-item plan mode.
2. **Living doc** — keep this file current; new failures/surprises get appended into the matching Part as we hit them.

## Decisions (resolved)
- **Target-golden placement:** not-yet-fixed failure-mode cases live in a **separate `data/eval/golden_targets/`**
  (NOT in the scored `baseline.json`); run on demand; promoted into the scored set when their fix ships.
- Author from source; EN+VI; held-out third; guards `adversarial`/`safety`/`unanswerable` = 1.000.

---

## PART A — Golden-set expansion — DO FIRST

### A0. `golden_targets/` convention ◻️
New dir + one-line README; `run_eval --golden-dir data/eval/golden_targets` scores targets on demand.

### A1. New-content golden (scored set) ◻️ — author from source PDFs/pages (read the parsed text; tables are grep-resistant)
- **`programs.json`** ✅ — CS 4yr/120, MD 6yr/228, Nursing 4yr/126, BBA 4yr/120 (EN+VI, 7 cases, source-verified). **CAS omitted — coverage gap (see Emerging problems).** (cecs data-science ✅, bba-duration ✅.)
- **`admissions.json`** — GPA threshold, key deadlines, application steps; EN+VI. (IELTS ✅.)
- **`scholarships.json`** — a named scholarship amount/eligibility/deadline (e.g. Vingroup S&T); EN+VI. (PhD-CS ✅.)
- Recovered TYPES (registrar form / student guide / global-exchange) ✅ `recovered_content.json`.

### A2. Entity/role golden ⏳ (scored where passing; targets where not)
- Role-specific + role-mismatch traps (Provost / Dean of CHS / Board Chair — right role, not a different-role "President"). (rector-trap ✅.)
- Name-order both-orders resolve ✅.
- **Enumeration target** ("who are all the Rectors" → `required_facts=[Rohit Verma, Tan Yap Peng]`) → `golden_targets/` (passes after E6 content + D8). Safe-hedge version stays scored.

### A2 ✅ — `entity_roles.json` scored (Council-President = Lê Mai Lan, EN+VI) + `golden_targets/leadership_enum.json` (affirmative Rectors enumeration). rector-trap/provost/name-order already in identity_intent/expansion.

### A3 ✅ — `out_of_scope.json` (#3) scored (ranking must defer); `golden_targets/`: `cross_domain.json` (#1, 2),
`multihop.json` (2), `refusal_calibration.json` (#4, record-privacy must-answer, 2), `underspecified.json` (#2, 2).
**confidence (#5/D7) is NOT a golden file** — it's a calibration *analysis* (correlate confidence vs correctness
over the whole scored set), done when D7 is worked.

(original A3 note kept:) `cross_domain.json` · `underspecified.json` · `multihop.json` · `out_of_scope_ranking` (scored) · `refusal_calibration.json`.

**A verification:** validate JSON; run new scored golden on v2+D9 → new-content + entity-pass + out-of-scope PASS; measure `golden_targets` (expected red). Refresh `baseline.json` with the new **scored** cases.

---

## PART B — General fixes — walk one-by-one (EnterPlanMode each; golden gates each)

| # | Problem class | General mechanism (not a patch) | Gating golden | Status / notes |
|---|---|---|---|---|
| **D6** | Over-refusal of legit policy (#4) | rule-question-vs-private-data classifier at input guard (`guardrails.py`) | `refusal_calibration.json` | design in `PHASE1.26_PLAN.md`; was deferred for teammate merge — revisit (cheap) |
| **D1** | All-or-nothing whole-answer refusal (#1) | claim-grounding **segmentation** in `resolve_output_decision` (keep supported + name gaps) | `cross_domain`, `multihop` | `ENABLE_PARTIAL_ANSWERS`; cost-neutral |
| **S13** | Program ambiguity / metadata gaps (B2/D3) | derive `DocumentMetadata.college`/`.program` from subdomain+URL at ingest | `programs.json` | confirmed unpopulated today; enables D4/B2 |
| **D4** | Underspecified → degrade not clarify (#2) | slot-detector → default+state (time-defaultable) vs one clarifying Q (non-defaultable) | `underspecified.json` | clarification deferred to teammate UX — confirm scope first |
| **D2+D3** | Cross-domain compound (#1) | reactive decompose→parallel fan-out→synthesis + low-coverage re-route | `cross_domain.json` | `ENABLE_CROSS_DOMAIN`; was deferred for "no golden" → now unblocked |
| **D8** | Entity role/alias disambiguation (E4/E6, G9) | curated **entity/role+alias table** (Rector vs Council-Pres vs Provost vs Dean; name aliases/orders) | A2 + enum target | unlocks affirmative enumeration + name-order; pairs with D9 |
| **E6 content** | Affirmative "current Rector" | keep leadership-announcement/about page (targeted ingest keep) | enum target | content gap; pairs with D8 |
| **D5** | External → confidently wrong (#3) | official-only index + reactive Tavily `search_web`, scope-disciplined | `out_of_scope_ranking` | `ENABLE_WEB_SEARCH` |
| **D7** | Confidence mis-calibration (#5) | confidence from grounding-coverage (from D1) + retrieval score | `confidence_probes` | measurement-led; no flag until measured |
| **S16** | Cross-lingual citation dilution | ~~score normalization~~ → **DOC-PIN + forced VI→EN cross-lingual for fact-intents** | `programs_xlingual` | ✅ **DONE 1.30b** (doc-pin); MD-vi/subsidy-vi pass |
| **S14/S15** | FAQ/curricula canonical-doc selection | ~~chunking/boost~~ → **canonical DOC-PIN** (`canonical_lookup.py`) | `admissions_financial_retrieval`, `programs_xlingual` | ✅ **DONE 1.30b**: 0/6 (boost)→5/6; flag `ENABLE_CANONICAL_DOC_PIN=true`. Residual: nursing-vi (generation, not selection) |

**Order (REVISED 1.31 — S14/S15/S16 + D9 now DONE; see consolidated map below):**
Golden hygiene + Stage-0.5 expansion (BLOCKING) → D1 → **Group-1 orchestration (= D2+D3+D1-merge+D7-readout,
built ONCE)** → D7 → S13 → D8+E6 → D5 (+ dilution rule) → D6 (re-scoped to VI) → D4. Tail: nursing-vi
generation, CAS content, datascience-vi citation.
~~old order: D6 → D1 → S13 → D4 → D2+D3 → D8(+E6) → D5 → D7 → S16/S14/S15~~ (stale).

**Per-fix loop:** EnterPlanMode → deep per-step plan → ExitPlanMode → implement behind `ENABLE_*` (default off)
→ `pytest`+`ruff` → `run_eval --diff baseline --runs 3` (scored + relevant `golden_targets`) → decode flips →
promote (flip flag + move passing targets into scored set + refresh baseline) or revert → `PHASE1.3x_LOG.md`
(incl. rejects) → update this living doc.

## Phase 1.31 direction (2026-06-25) — multi-domain orchestration + golden hygiene (PLAN-FIRST; not yet built)
Decided with user: pursue multi-DOMAIN coverage via the CHEAP path, NOT a blind fan-out-to-all or audit-loop.
The router-auditor picks a SUBSET of specialists; the auditor SYNTHESIZES (single-shot), it does NOT loop.
- **Multi-label routing + single-shot synthesis** (COVERAGE fix): supervisor emits a subset of specialists
  (it already scores all 4 in `_score_intent` — threshold instead of argmax), dispatch in parallel, merge.
  ⚠️ Overlaps existing **D2+D3** (cross-domain decompose→fan-out→synthesis) — CONSOLIDATE, don't duplicate.
- **Decomposition** (MULTI-QUESTION fix): build only if the expanded golden shows multi-question fails that
  multi-label+synthesis does not catch. Audit-LOOP deferred (cost + nondeterminism; D9 already single-shot).
- **Stage 0.5 (BLOCKING)** — expand the multi-domain golden FIRST. Current substrate = 4 cases, **2/4** on
  the post-doc-pin system, exactly ONE true coverage miss (`cross-tuition-adddrop`; the other fail is
  facts-OK/cite-wrong). Noise floor (±2-3) > test set ⇒ cannot A/B an orchestrator. Author ~10-15
  `cross_domain` + ~10 `multihop` from VERIFIED corpus facts, tagged coverage / multi-question / chained.

### Two user considerations to fold in (read-only analysis workflow running 2026-06-25)
1. **Golden hygiene / compute waste:** prune always-pass redundant cases + over-represented problem areas
   (many near-identical Qs) — preserve regression-catching power + guard/edge coverage, cut the waste.
2. **Consolidate in-line plans:** review all LOGS plan/roadmap items (D1–D9, S13–S16, ingest), dedup fixes
   that solve the same problem, re-rank by leverage/cost, drop done/obsolete.
This section is finalized from the workflow's golden-prune proposal + consolidated fix map + multi-domain
design BEFORE any build (plan-first).

### Consolidated fix-map (2026-06-25, from the analysis subagents — supersedes the scattered Part-B rows)
- **G1 — Cross-domain / multi-domain orchestration** (D2 + D3 + the user's multi-label idea). **KEY:** the
  user's "multi-label routing + single-shot synthesis + decomposition" is **NOT new** — it = D2 (decompose/
  fan-out/synthesis) + D3 (low-coverage re-route) + D1's merge + D7's readout. **Build ONCE** in `chat()`,
  reusing: `_score_intent` (threshold instead of argmax → that IS multi-label routing), the existing single-
  specialist graph (call N× via `asyncio.gather`), D1 claim-segmentation for part-aware merge, D9 faithfulness
  for the synthesis check, retriever top-score as the D3 coverage signal. **Do NOT** also build D2's separate
  planner-LLM for the common "X and Y" case (the router subset replaces it); keep a planner only if
  decomposition (stage 3, multi-question) is later proven needed. One flag, one code path. **BLOCKED on G7.**
- **G2 — Partial-answer + confidence** (D1 → D7): D1 claim-segmentation (cost-neutral, standalone #1 win)
  produces grounding-coverage; D7 reads confidence from it (measure-first, no flag). Also feeds G1 synthesis.
- **G3 — Doc-pin / canonical-source** (S14+S15+S16): ✅ DONE/PROMOTED 1.30b. Drop from backlog.
- **G4 — Entity/role** (D9 ✅ done; remaining **D8 curated role/alias table + E6 keep leadership page** —
  co-dependent, ship together; flips `leadership_enum` from hedge to both-names).
- **G5 — Ingest/corpus** (filter overhaul/C1/C2 ✅ done; remaining **S13** college/program metadata —
  also sharpens G1 routing + G3 category match; **D5-dilution** news/PR exclusion rule gated on
  confidently_wrong; **CAS** content gap, low priority).
- **G6 — Refusal calibration** (D6): re-scoped — EN record-privacy now ANSWERS; only the **VI variant
  over-refuses** → folds into the cross-lingual cluster; confirm overlap before building the input classifier.
- **G7 — Golden hygiene + Stage-0.5 expansion (BLOCKING, do FIRST):** expand cross_domain/multihop AND prune
  redundancy in one pass. Gate for the whole G1 cluster.
- **Obsolete (drop the approach, keep the lesson):** S15+S16 BOOST (rejected 1.30a), score-sorted citations
  (rejected 1.28h), audit-LOOP orchestration (rejected → single-shot synthesis).

### G7a — Golden prune list (27 cases, strictly-safe; verified always-pass in 12 runs, EN twin kept)
All are the **VI half of an always-pass EN/VI fact pair** (EN twin retains the exact-fact + distractor test);
none are guards / sole-feature / ever-failed. ~12% eval compute saved. Cut from the named files:
- `calendar_pointlookup.json` (12): summer-evaluation-vi, fall-evaluation-vi, summer-enrollment-vi,
  lunar-new-year-vi, spring-final-schedule-vi, graduation-vi, spring-add-transfer-deadline-vi, hung-king-vi,
  convocation-vi, spring-grade-release-vi, summer-grade-release-vi, orientation-week-vi
- `financial.json` (7): fin-nursing-tuition-year-vi, fin-other-bachelor-semester-vi, fin-nursing-tuition-
  credit-vi, fin-standard-credit-vi, fin-other-bachelor-year-vi, fin-currency-vi, fin-medicine-tuition-year-vi
- `fee_list.json` (3): feelist-per-credit-all-vi, feelist-per-year-all-vi, feelist-per-semester-all-vi
- `conduct.json` (2): conduct-scope-vi, conduct-disciplinary-tiers-vi
- `calendar_list.json` (2): callist-add-transfer-all-vi, callist-course-drop-all-vi
- `fee_structured.json` (1): fee-nursing-semester-vi
KEEP-ALL: `policy` (34) + `calendar` (28) have 0 always-pass (real regression value); all guard categories.
⚠️ Prune is itself eval-gated: after cutting, re-run → baseline n drops by 27, pass-rate must stay ~flat
(we're removing only always-pass cases) → refresh baseline.

### G7 RESULT (2026-06-25) — DONE; Stage-0.5 baseline = 22/27 (the gap is SMALLER than feared)
- **G7a prune:** removed 27 always-pass VI duplicates → scored golden 198→171; `baseline.json` refreshed by
  filter+re-summarize (run_eval `_summarize`) to **0.965/199**, guards 1.000, cw 3 (the 0.969→0.965 dip is
  mechanical — removing always-pass cases de-inflates the metric).
- **G7b expansion:** 3 subagents authored **23 verified** cross_domain/multihop cases (evidence tables);
  validated + independently spot-verified facts; merged → `cross_domain.json` 16 (11 coverage + 3
  multi_question + 2 orig), `multihop.json` 11 (9 chained + 2 orig) = **27-case substrate**.
- **Stage-0.5 baseline (current single-intent system, cache-off): 22/27.** By type: coverage **9/11**,
  multi_question **3/3**, chained **8/9**, orig 2/4. **KEY FINDING:** the single-intent + ReAct system
  ALREADY handles most multi-domain (the `services` specialist searches unfiltered + ReAct multi-tool). The 4-
  case 2/4 over-stated the gap; the 27-case 22/27 is the truth. **G1's real target = ~3 coverage fails, all
  FINANCIAL+CALENDAR** (`cross-tuition-adddrop`, `cross-other-bachelor-tuition-fall-start`,
  `cross-late-payment-fee-adddrop`): routed to `financial`, got the fee, missed the calendar-date half. Plus
  1 VI-chained fail (cross-lingual, not coverage) + 1 citation-only fail. ⇒ **G1 ROI is modest (~3 cases) with
  a clean pattern; reassess priority vs D1/D8/D5 before building. Measuring-before-building paid off.**

### G1 DECISION (2026-06-25) — DEFERRED (not worth building now; evidence-based)
After G7's measurement, investigated the actual fix surface and decided NOT to build the multi-domain
orchestrator. Evidence:
- **ROI = 3 cases.** 22/27 already pass; the gap is 3 financial+calendar coverage fails (+1 VI-chained,
  +1 citation-only, both other root causes). multi_question 3/3 and chained 8/9 are already handled.
- **Cheap rule rejected (blast radius):** "route 2+-intent questions to the broad `services` specialist"
  re-routes **18 scored cases, 17 of which currently PASS** — mostly single-domain point-lookups with a
  STRAY cross-domain keyword (`fin-*`/`fee-*` score calendar=1 via "semester"/"year"; `pol-*` via a stray
  calendar hit). Keyword scores can't separate genuine compound (cross-tuition-adddrop cal=2/fin=1) from
  stray (fin-other-bachelor-year fin=2/cal=1) — same shape. Would near-certainly regress the 17 to fix 3.
- **Clean version = big build:** an LLM multi-label router (distinguishes "tuition AND deadline" from
  "tuition for the semester") + parallel fan-out + synthesis node = a graph-topology rewrite (new join/
  synthesis, MessagesState reducer, +cost/nondeterminism) — disproportionate to a 3-case payoff.
- **Kept:** the 27-case Stage-0.5 substrate + the routing decode (`_routing.txt`, `_blast.txt`) so G1 is
  instantly measurable IF multi-domain regresses later or the payoff grows. Decision: revisit only if the
  multi-domain gap widens or a cheaper clean signal appears. (Mechanism is sound; the timing/ROI isn't.)

### Residual-tail diagnosis (2026-06-25) — the remaining failures are GENERATION-side, not retrieval
Ranked the backlog and deep-dove the top items; the labels understate the difficulty. Findings:
- **`calendar-fall-grade-release-en` = NOISE** — the structured calendar lookup returns the exact answer
  (Jan 25→Feb 12 2027, score 1.0); the agent just hedged on that run (also the lone noise-LOST in the 226
  run). Not fixable; flaky.
- **`calendar-victory-day-vi` = real DATA bug** — structured index is MISSING Victory Day (`victory`/`30-apr`
  = absent; `hung king` present). Cause: the PDF row is glued `"...30-AprVictory Day"`, so calendar-event
  extraction dropped it. Fix = glued-date split in the calendar extractor + **re-ingest/rebuild** (general:
  recovers Victory Day + other glued holidays). Medium build, blast radius on the structured index.
- **`pol-thesis-days-vi` = GENERATION disambiguation, NOT doc-selection** — policy doc-pin is ON and
  `policy_match` correctly returns the thesis-guidelines URL (which has "15/30 working days"); the doc was
  pinned, but the LLM answered "3 months" from the co-present PhD-reg PDF. **Same class as `nursing-vi`
  (86 vs 126)** — right doc retrieved, wrong competing number chosen.
- **`calendar-source-inconsistency` (2 cw)** = deliberately-hard metacognition probe (detect a mislabeled
  source). Aspirational. **`pol-courseeval-vi` / `datascience-vi`** = citation-only, low value.

**STRATEGIC TAKEAWAY:** retrieval/doc-selection is now strong (doc-pin shipped); the residual tail is
dominated by **(a) generation-side number disambiguation** (pick the number matching the question's
qualifier — nursing-vi, thesis-days-vi) and **(b) VI cross-lingual + a calendar parser data gap**. The two
genuinely-worth-building next items are therefore: **(A)** a generation-side disambiguation prompt
(general — addresses the recurring class; high blast radius → careful A/B), and **(B)** the calendar
glued-date parser fix + re-ingest. Both are deliberate builds, NOT quick "before-closing" patches. System is
at a mature plateau (0.965, guards 1.000); no cheap clean win remains in the scored tail.

### G7b — Stage-0.5 multi-domain golden expansion (design)
~10-15 `cross_domain` + ~10 `multihop`, authored from VERIFIED corpus facts, tagged by failure type:
- **coverage** (two domains, one missing) — financial+calendar, policy+financial, calendar+registrar,
  services+financial; the case multi-label routing must fix.
- **multi-question** (two distinct asks) — the case decomposition would fix.
- **chained** (one answer, multiple hops) — ReAct often already handles; control.

### Build sequence (plan-first; EnterPlanMode per item, golden-gated, flag-default-off)
1. **G7** golden hygiene (prune 27) + Stage-0.5 expansion — BLOCKING, cheap, no app-code change.
2. **D1** part-aware degradation — cost-neutral standalone win + G1 building block.
3. **G1** multi-label routing + parallel fan-out + single-shot synthesis (one flag) — gated on G7's golden.
4. **D7** confidence calibration (measure-first) → **S13** metadata → **D8+E6** → **D5(+dilution)** →
   **D6 (VI-rescoped)** → **D4**. Tail: nursing-vi generation, CAS, datascience-vi citation.

## Design convergence (2026-06-24 — S15 + S16 → ONE mechanism)
The two top bugs share a fix. Cross-lingual expansion is **already on**, yet VI fact queries miss — the EN
query variant competes in RRF but the authoritative doc still loses to VI prose (FAQ/tariff/bio). The existing
**`prefer_canonical`** boost in `apply_metadata_boosts` ([context.py:230-243](vinchatbot/app/rag/context.py#L230-L243))
already lifts the canonical page over magnet PDFs **and is cross-lingual-aware** (`hints["topic_terms"]` carries
the EN translation so a VI query matches an EN title) — but it's gated to `policy_html`/`financial_policy` only.
**Convergent general fix (S15+S16):** extend `prefer_canonical` to the new authoritative doc-types per
fact-intent — program→`program_page`/curriculum PDF, admission→`admissions_page`/`faq_page`, fee→tariff
(exists) — and set the `prefer_canonical`/`topic_terms` hints for those intents (reuse `is_point_lookup` /
category routing). One universal canonical-source-preference lever (cross-lingual-aware), not per-case patches.
This is the **first Part-B EnterPlanMode** target. Pairs with S13 (college/program metadata) which sharpens the
category match.

## A-verify RESULT (2026-06-25, clean cache-off run)
**Scored: 0.9683 / 221, guards 1.000** (baseline.json refreshed). New content all passes (programs 5/5,
admissions 1/1, scholarships 2/2, entity_roles 2/2, expansion 8/8, recovered 4/4, identity 7/7). vs prior
baseline (0.957): **+3 / −1**; the only LOST = `fin-library-overdue-fine-vi` (known list-mode VI noise). No
real regression on the 188. **out_of_scope ranking moved to targets** (0/2 — bot fabricates a ranking → D5).
**Confirmed bug map (scored fails that are pre-existing/known):** calendar-source-inconsistency en/vi,
pol-courseeval-vi (cite), pol-thesis-days-vi, ltp-recordprivacy-access-vi (VI over-refusal → cross-lingual/D6),
calendar noise. Targets = the failure-mode substrate (cross-lingual #1, admissions-canonical #2, leadership
enum, cross-domain, out_of_scope ranking).

## Eval-rigor lesson #2 (2026-06-25) — run_eval is SILENT mid-run
`run_eval` prints nothing per-case (httpx/loguru silenced); output appears ONLY at the end (summary). A healthy
full run sits at ~137 bytes (the pre-logging transformers warning) for its entire ~35-min duration. **Do NOT
judge progress by byte count / kill on silence** — wait for the harness completion notification. (Several
costly in-progress runs were wrongly killed before this was understood.) Confirmed: bg captures output live
(buffer test), retriever loads 12s in bg (loadtest), `--limit 3` bg completed 3/3 real answers.

## Eval-rigor lesson (2026-06-24)
**Never run two evals in parallel.** The first scored+targets parallel launch rate-limited OpenRouter →
**106/223 cases returned EMPTY answers** → whole categories spuriously 0.0 (overall 0.511, confounded,
DISCARDED). Re-run **sequentially**. The targets-only run (5/16) was small enough to be mostly valid, but
re-confirm. (Matches the project's standing "never trust a run with network errors".)

## Comprehensive bug map (2026-06-24 — golden_targets run, 5/16 pass)
Priority-ranked from the find-all-bugs eval:
1. **Cross-lingual VI fact retrieval (S16) — HIGHEST leverage.** Nearly every VI fact case fails
   (prog-md-vi, prog-nursing-vi, adm-gpa-vi, schol-subsidy-vi, refcal-vi). VI queries don't surface the
   authoritative (often EN) doc → hedge/wrong. Subsumes much of S16 + the VI half of D6.
2. **Admissions/financial canonical-source (S15).** 4/4 fail; confidently-wrong GPA(8.0)/subsidy(35%) — the
   recovered admissions/scholarship pages lose to policy regs/tariff.
3. **Leadership enumeration (D8 + E6 content).** 2/2 fail; needs entity/role table + announcement content.
4. **Cross-domain compound (D1/D2).** financial+registrar compound fails (all-or-nothing); financial+financial passes.
5. **Multi-hop.** mostly OK (1 cite-miss). Low priority.
6. **D6 refusal — EN now ANSWERS the record-privacy rule** (good); only the VI variant fails → folds into #1.
7. **underspecified golden too loose** — a degrade trivially matches the markers; rework the probe before D4
   (e.g. require a clarifying question / explicit assumption, or expects a specific defaulted term).

## Emerging problems (append as we go)
- **2026-06-25 — S15+S16 DOC-PIN ✅ PROMOTED (0/6→5/6); baseline 0.969/226.** `canonical_lookup.py` +
  `tools._search` pin block + `ENABLE_CANONICAL_DOC_PIN=true`. Three debugging lessons worth keeping:
  (a) **Layer ordering** — the structured FEE lookup early-returns *before* the pin block, so financial-routed
  aid queries never reached the pin; fix = compute `canon_match` once and skip the fee lookup when the pin
  claims the query. (b) **Route-aware suppression** — on the financial route only the *aid* pin applies; a
  program/admission name there is a FEE question (`canon_applies`), else `fee-medicine-credit` regresses.
  (c) **Keyword narrowing beats breadth** — duration Qs (spec dual-degree "5/5.5 yr" distractor) and broad
  scholarship/financial-aid terms (answers live on `scholarships.vinuni` / policy pages) were dropped so the
  pin fires ONLY for the facts it's curated for; everything else reverts to the baseline-clean vector path.
  **Residual → future GENERATION fix:** `prog-nursing-credits-vi` — BN doc correctly pinned but LLM picks the
  page-9 "86 Total CR" over program-total 126 (within-doc number disambiguation, not doc-selection). Kept in
  `golden_targets/programs_xlingual.json`. See PHASE1.30_LOG 1.30b.
- **2026-06-25 — Canonical-source BOOST rejected (S15+S16) → DOC-PIN.** The boost (extend prefer_canonical to
  fact-intents) was A/B'd 0/6 on targets: the authoritative doc (curriculum/spec PDF, admissions FAQ,
  scholarship page) isn't even RETRIEVED, so a boost can't lift it — same wall as the policy 1.20 boost.
  **Pivot: doc-pin** (generalize policy 1.21 `policy_lookup`/`build_policy_topic_index`): detect intent+topic →
  fetch the canonical doc by URL → pin to front. `canonical_doctypes_for` + the boost parameterization kept
  inert (reused for intent detection). See PHASE1.30_LOG 1.30a.
- **2026-06-24 — Admissions/financial-aid retrieval out-ranked → CONFIDENTLY WRONG (new major Part-B item).**
  Recovered `admissions.vinuni` / scholarship pages lose retrieval to the older `policy.vinuni`
  academic-regulations / financial-tariff PDFs, so the bot answers admission-GPA and tuition-subsidy queries
  **wrong**: "no minimum GPA" / "6.5" (truth 8.0), "50% subsidy" (truth 35%). Worse than hedging — it's
  confidently wrong on the NEW official content. Class: *canonical-source priority / trust-boost for the new
  official sub-domains* (admissions/scholarship pages should win for admission/aid queries, like the
  policy doc-pin keeps the tariff authoritative for fees). **Target set:**
  `golden_targets/admissions_financial_retrieval.json` (4 cases). **Fix:** Part-B **S15** (canonical-source
  preference) + a source-trust/category boost for admissions/scholarship pages on admission/aid intents
  (mirror `context.py` boosts + the policy doc-pin). Pairs with D9 (which would at least hedge the wrong ones).
  Promote leverage: this is a confidently-wrong class → high priority alongside D6.
- **2026-06-24 — Cross-lingual program-fact under-retrieval (generalizes S16).** VI program-fact queries
  ("…bao nhiêu tín chỉ?") **hedge** because cross-lingual retrieval surfaces VI prose pages (FAQ / tariff /
  faculty bio) instead of the authoritative **English** curriculum/program-spec PDF that holds the number
  (MD-vi missed 228, Nursing-vi missed 126; CS-vi passed only because a VI CS page carries 120). Class:
  *cross-lingual retrieval precision* — broader than the single datascience-vi case; the EN curriculum PDF must
  out-rank VI prose for VI numeric-fact queries. **Target set:** `golden_targets/programs_xlingual.json`.
  **Fix:** folds into **S16/B** (per-tool-call score normalization / cross-lingual rerank / cite-what-used) —
  re-scope S16 from "1 citation case" to "VI→EN authoritative-doc retrieval for numeric facts."
- **2026-06-24 — CAS program content gap.** No College of Arts & Sciences program/credit content surfaced in
  v2 (the `cas.vinuni` crawl yielded mostly news/events; program pages thin or absent). → can't author a
  source-verified CAS program golden. Class: *recovered-content coverage gap*. Candidate fix: targeted re-crawl
  of `cas.vinuni` program pages OR confirm CAS programs exist publicly. Low priority; noted for the next crawl.

## Out of scope (this phase)
Platform Phase 3, Phase 2 personalization, the broader `UPDATE_PLAN.md` cost/observability/backend backlog.
