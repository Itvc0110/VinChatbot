# Plan — Adaptive orchestration & answer-quality (post-benchmark roadmap)

## Context
Future intelligence/orchestration roadmap, grounded in an **evidence-based probe** of the live system
(13-question battery, 2026-06-23). Execute **AFTER** the in-flight data work (deepen-official crawl →
incremental ingest → re-benchmark vs 0.968/188 + guards), which is tracked separately. The prior plan's
"web-search for unofficial" is absorbed here as **D5**. Discipline unchanged: every direction is
`ENABLE_*`-flag-gated + default-off + fail-open, A/B'd vs baseline, guards (`adversarial`/`safety`/
`unanswerable`) stay **1.000**, promote only winners, log every trial.

## Failure-mode map (live evidence, current index)
| # | Failure | Probe evidence | Root cause |
|---|---|---|---|
| 1 | **Cross-domain compound → all-or-nothing** | "Medicine tuition AND Fall 2026 payment deadline" & "which comes first, add-drop or payment deadline" → **conf 0.0 full refusal**; "Spring 2027 start AND CS per-credit tuition" → answered but **wrong granularity**, conf 0.46 | single-intent route → other domain's tools/levers unreachable; output guard refuses the **whole** answer |
| 2 | **Underspecified → degrade not clarify** | "When is the tuition payment deadline?" (no term) → conf 0.0 | no clarification/default path |
| 3 | **External → confidently WRONG** | "How does VinUni rank in Asia?" → fabricated "top-20 QS" from a `vinuni.edu.vn` PR page | PR/news in index; no external channel |
| 4 | **Over-refusal of legit policy Q** | "Which staff can access my academic records?" → refused as private-data | input-guard false positive |
| 5 | **Confidence mis-calibrated** | correct multi-hop (drop→no refund) scored **0.39**; refusals score **1.0** | score tracks refusal, not quality |

Works well (don't touch): list/aggregation (list mode, conf 1.0), single-domain conditional reasoning,
negation, days-till arithmetic, correctly-routed policy.

---

## Phase 0 — Author the measurement set first (do before any code)
We can't A/B D1–D7 without cases that exercise them. Author ~5 small golden files from the battery seeds
(they already have known-good answers): `cross_domain.json` (compound financial+calendar, ~6 EN/VI),
`underspecified.json` (missing-slot, ~4), `multihop.json` (chained deadline→policy→fee, ~4),
`refusal_calibration.json` (legit-policy-about-sensitive-topic that must ANSWER + true private-data that must
REFUSE, ~6), and extend the out-of-scope guard set with the ranking case. `required_facts`/`forbidden_facts`
+ `expects_refusal` as today; held-out third per convention. **No model gating** — pure authoring. These also
become the regression guard for each direction.

---

## D1 — Part-aware degradation  *(cheapest, do first; fixes #1's worst symptom)*
**Goal:** replace whole-answer refusal with **answered parts + explicitly named gaps**.

**Mechanism.** Today `resolve_output_decision(answer, citations, retrieved_texts, require_grounding=True)`
([guardrails.py](vinchatbot/app/agents/guardrails.py)) makes a binary call; on faithfulness failure `chat()`
([vinuni_agent.py](vinchatbot/app/agents/vinuni_agent.py)) swaps in the full degrade message. Change it to a
**claim-grounding segmentation**:
1. Split the answer into atomic claims (sentence-level; the answers are already often bulleted).
2. One structured LLM call: given `{claims, retrieved_texts}` → label each `supported | unsupported`.
3. Assemble: keep supported claims verbatim + append *"I couldn't confirm in official sources: <unsupported>"*.
   Fully degrade **only if zero** claims are supported. Secret-leak still hard-blocks (unchanged).

**Design choice.** A *single* segmentation call (not N per-claim calls) keeps cost flat (~1 LLM call,
replacing the existing faithfulness call — roughly cost-neutral). Conservative labeling (keep a claim only on
clear evidence overlap) to avoid passing a hallucinated half.

**Couples with D2.** When D2 is on, partialness is even cleaner at the **sub-answer** level (each sub-answer
already carries its own grounding) — D1's claim-segmentation is the standalone path for a single-specialist
multi-part answer.

**Edge cases.** run-on sentences (segment conservatively); a numerically-partial claim ("per-semester" given
for "per-credit") → label unsupported if the *specific* asked value isn't in evidence. **Eval:** multidomain-1
should go from conf-0.0-refusal → "tuition is X; couldn't confirm the payment date." Guards unaffected (refusal
cases have zero supported claims → still refuse). Flag `ENABLE_PARTIAL_ANSWERS`.

---

## D2 — Reactive decompose → parallel fan-out → synthesis  *(the real cross-domain fix)*
**Trigger (when to escalate).** Start **reactive-only** to keep the 90% single-domain turns untouched: run the
normal single route; escalate **only** when it degrades (output-guard unhappy OR top coverage <
`reactive_expansion_min_score`). Later add a cheap up-front multi-domain detector (≥2 domain keyword-classes +
conjunction) to decompose proactively for obvious "X and Y" turns. Flag `ENABLE_CROSS_DOMAIN`.

**Decompose.** One planner LLM call (gpt-4o-mini, ~$0.0005): question → `[{sub_question, domain}]`, each
answerable by ONE domain; if already single-domain it returns the original unchanged (→ no fan-out). Cap at 4
sub-questions; cap recursion.

**Fan-out (the parallel router).** For each sub-question, invoke its specialist (the planner already assigned
the domain → skip re-routing) and run them **concurrently** with `asyncio.gather`. Orchestrate **in `chat()`**,
calling the existing single-specialist graph N times — **not** a LangGraph parallel-branch rewrite (simpler,
testable; the graph stays single-specialist). Each sub-result carries `{answer, citations, grounding, coverage}`.

**Synthesize.** One LLM call: original question + the grounded sub-results → unified answer, with D1's
part-aware handling (include grounded sub-answers; for an empty/ungrounded one, state *"couldn't find <sub-q>
in official sources"*). Faithfulness-check the synthesis against the **union** of sub-result evidence so it
can't fabricate the missing part.

**Independent vs dependent.** D2 handles **independent** sub-questions ("X *and* Y" — the common compound).
**Dependent multi-hop** ("the fee for the program I'm enrolled in" / "refund if I drop after *the* deadline")
needs sequential reasoning where one answer feeds the next — that's D8/sequential territory; note it, don't
force it into the parallel path.

**Cost/latency.** Only on escalated turns: +2 LLM calls (planner + synthesis); fan-out is **parallel** so
latency ≈ max(sub-question) + planner + synth ≈ **~2–3× a single turn**, not N×. `$0` when the flag is off or
the planner returns one sub-question.

**Edge cases.** bad split → reactive-only trigger limits blast radius + empty sub-answer handled by synthesis;
a sub-question that's out-of-scope → its specialist degrades → synthesis names it (no guard bypass; the input
guard already cleared the original turn). **Eval:** multidomain-1/temporal-order → correct combined answers;
guards 1.000; single-domain turns byte-identical when not escalated.

---

## D3 — Reactive re-route on low coverage  *(single-domain mis-route fix; composes with D2)*
**Mechanism.** Reuse the retriever's top post-boost rerank score as the coverage signal
([retriever.py](vinchatbot/app/rag/retriever.py)). If the routed specialist's top score <
threshold AND the answer degraded → **re-run once with an all-tools pass** (a specialist bound to all 4 search
tools) rather than degrading. Catches `courseeval`-class mis-routes generally without a stricter router (which
was A/B-rejected). Unify with D2: "on degrade → all-tools OR decompose." Flag `ENABLE_REACTIVE_REROUTE`.
**Edge:** adds latency only on already-failing turns. **Eval:** the mis-route residuals recover; no regression
on correctly-routed turns (they never hit the low-coverage branch).

---

## D4 — Clarification / sensible default  *(underspecified)*
**Mechanism.** The point-lookup detector already extracts term/program/year. If a **required** slot for the
domain is missing and multiple candidates exist: (a) **time-defaultable** slots (term/year) → default to the
current term via time-awareness and **state the assumption** ("Assuming Fall 2026: …") — one-shot; (b)
**non-defaultable** slots (program) → return a single targeted clarifying question with
`needs_clarification=True`. Coordinate with the teammate's vague-path merge. Flag `ENABLE_CLARIFY`.
**Tradeoff:** default+state = no round-trip but may assume wrong; clarify = correct but a turn cost → split by
slot type as above. **Eval:** `underspecified.json`.

---

## D5 — Official-only index + Tavily web-search  *(external channel; absorbs prior Part B; backed by #3)*
Finding #3 proves external facts must not live in the index. Build per the prior detailed sketch:
`tavily_api_key` (TAVILY_API_KEY, already in `.env`) + `enable_web_search` in [config.py](vinchatbot/app/core/config.py);
fail-open flag-gated `search_web` `@tool` in [tools.py](vinchatbot/app/agents/tools.py) tagged `web_unofficial`;
bound to `services` via `SPECIALIST_TOOLS` ([specialists.py](vinchatbot/app/agents/specialists.py)); reactive
(only on low official coverage); **scope-disciplined** (guards still refuse out-of-scope — web search is not an
escape hatch); dynamic results excluded from the deterministic golden (mocked in tests).
**Near-term tie-in (this re-benchmark):** measure whether the freshly-crawled `vinuni.edu.vn` PR/news dilutes
or adds confident-wrong answers; **decision rule** — if `confidently_wrong_rate` rises or overall regresses,
exclude news/PR from the index now (a `document_type`/path filter at ingest, mirroring the A3 official filter)
even before web-search ships.

---

## D6 — Refusal calibration  *(over-refusal)*
The `restricted_data` hybrid from [LOGS/PHASE1.26_PLAN.md](LOGS/PHASE1.26_PLAN.md): distinguish "asking what
the RULE is" (answer from the policy) from "asking for PRIVATE data" (refuse) at the input guard
([guardrails.py](vinchatbot/app/agents/guardrails.py)). Flag-gated; **guards must still stay 1.000** on genuine
adversarial/private-data cases — `refusal_calibration.json` encodes both directions so we catch over- and
under-refusal.

## D7 — Confidence calibration  *(measurement-led)*
**Measure first:** correlate the current confidence vs correctness across the golden (the score gives a good
multi-hop answer 0.39 and a refusal 1.0 — clearly mis-aligned). Then re-derive confidence from
**grounding coverage** (fraction of supported claims, from D1) + retrieval score, decoupled from refusal, so
`needs_human_review` + degradation fire on the right turns. No flag until measured.

## D8 — Lightweight entity graph  *(only if D2/eval demand it)*
Extend the existing deterministic layer (calendar events, fee programs, policy topics, offices — already
structured) into a small curated relation map (`governed-by` / `has-deadline` / `charged-by`) for
**dependent multi-hop lookups** + **decomposition routing** (which domains a question touches). Curated
proto-graph, **not** full GraphRAG. Graduate to full GraphRAG (LLM entity/relation extraction + community
summaries) **only** if the re-benchmark/eval shows a large relational/global-question tail that flat RAG + D2
can't cover — measure before paying that complexity + re-sync cost.

## D9 — Intent-satisfaction validation core  *(grounded-but-doesn't-answer; the "is this the answer the user asked for" check)*
**Motivation (live evidence, 2026-06-24).** After the filter rebuild, "VinUni có những hiệu trưởng nào?" →
**confidently** answers *"David Bangsberg / Laurent El Ghaoui / Lê Mai Lan"* (conf 0.82, `needs_review=False`).
Each claim **is grounded** — a chunk literally says "Lê Mai Lan, President of VinUniversity" — so the existing
groundedness critic ([output_audit.py](vinchatbot/app/agents/output_audit.py) `audit_output`) **passes** it.
The failure is that *grounded ≠ answers-the-question*: the user asked for the **Rector (Hiệu trưởng)**; the
evidence names a person whose role is **Council President (Chủ tịch Hội đồng)** — right topic, **wrong
specificity**. The data overloads "President" across ≥3 roles (Council-President = Lê Mai Lan; Rector = Rohit
Verma 2021 → Tan Yap Peng 2025; Vice-Rectors), so a topical/groundedness match is insufficient.

**Goal.** Upgrade the post-generation critic from a *groundedness-only* judge to a **groundedness +
intent-satisfaction** judge, and act on "grounded-but-doesn't-satisfy" the same way as ungrounded (degrade /
re-retrieve), so the bot **hedges instead of confidently-wrong**.

**Mechanism (extends the existing cascade — no new architecture):**
1. **Constraint extraction** — from the QUESTION, extract the *specific* requirement: entity-type + required
   attribute (`role = Rector`, not generic "leadership"), **cardinality** (single vs enumerate-all), **tense**
   (current vs historical).
2. **Alignment check** — for each candidate the evidence supports, compare its *stated* attribute to the
   *required* one. Different-but-similar (Council-President ≠ Rector) → **near-miss / insufficient**. For
   enumeration also check **authority/completeness** (authoritative list vs stitched-from-mentions).
3. **Verdict → action** — extend the current allow/degrade binary with `satisfies_intent` + `missing_constraints`:
   satisfied → allow; insufficient → **one corrective re-retrieve** with the disambiguating constraint added
   (composes with **D3**), re-judge; still insufficient → **hedge** ("I found people with President-like titles
   but couldn't confirm who holds the *Rector* role") via the existing `build_graceful_degradation_response`;
   escalate `needs_human_review`. Feeds **D7** (confidence from satisfaction, not just refusal).

**Where it slots.** Augment `AUDIT_SYSTEM` in [output_audit.py](vinchatbot/app/agents/output_audit.py) to also
return `satisfies_intent`/`missing_constraints` (keep fail-OPEN). Widen the call gate at
[vinuni_agent.py](vinchatbot/app/agents/vinuni_agent.py) beyond `is_point_lookup` to also fire on
identity/enumeration queries (a cheap `is_identity_query` mirroring `is_point_lookup`). Flag
`ENABLE_INTENT_AUDIT`, default-off, fail-open.

**Honest boundary (why this is one of THREE layers, not the whole fix).** This makes the bot **safe** (turns
confidently-wrong → hedge / refined search) but does **not** manufacture missing knowledge. Affirmatively
answering "the current Rector is Tan Yap Peng" still needs (a) the **content** (the leadership announcement /
about page — currently a dropped news slug) and (b) the **entity/role table** (D8: Rector vs Council-President
vs Vice-Rector alias+role map). D9 = safety/calibration; content + D8 = affirmative correctness. Each is
independently shippable and A/B-able.

**Eval.** New golden: "who is the Rector?" (role-specific), the role-mismatch trap (must NOT answer
"Lê Mai Lan" as Rector), enumeration ("who have been the Rectors" → both Rohit Verma + Tan Yap Peng once
content lands). Guards stay 1.000; `confidently_wrong_rate` must drop on the identity set.

---

## Worked example — "Medicine per-semester tuition AND the Fall 2026 payment deadline?"
- **Today:** route→financial → 4× financial search → can't reach calendar → **conf 0.0, full refusal** (even
  though it had the tuition).
- **With D1+D2:** single route degrades → **escalate** → planner splits into `[{tuition, financial},
  {payment-deadline, calendar/financial}]` → **parallel** fan-out (both specialists at once) → tuition grounded,
  payment-date maybe grounded/maybe not → **synthesis**: *"Medicine per-semester tuition is X (source: tariff).
  I couldn't confirm the Fall 2026 tuition payment date in official sources — check the Academic Calendar."*
  Latency ~2–3× a normal turn, paid only on this escalated turn.

## Cost & latency model
- Single-domain turns: **unchanged** (flags off / not escalated → byte-identical).
- Escalated multi-domain turn: planner + synthesis (~2 small LLM calls) + parallel sub-retrievals → ~2–3×
  latency, a few tenths of a cent. D5 web turns: +1 Tavily call (~1–2 s), reactive-gated. Validation spend:
  per direction ~1 A/B + 1 baseline refresh ≈ a few eval runs (~$2–4), one at a time.

## Risk register
- **Over-decomposition / bad splits** → reactive-only trigger + cap-4 + planner "return as-is if single-domain".
- **Synthesis fabrication** → faithfulness-check synthesis vs union evidence; conservative claim labeling (D1).
- **Latency creep** → escalation is reactive (only on degrade), fan-out is parallel.
- **Confidence regressions** → D7 is measurement-led, no premature flag.
- **Web-search scope creep / hallucination** → guards refuse out-of-scope; `web_unofficial` attribution;
  reactive gate; dynamic cases out of the golden.
- **Eval flakiness** → keep dynamic/web cases out of the deterministic baseline; `--runs N` for soft cases.

## Recommended sequence
**Phase 0 (golden authoring)** → **D1** (cheap win on #1) → **D5 dilution decision at this re-benchmark** →
**D2 (+D3)** (real cross-domain fix) → **D4** + **D6** (independent quality) → **D7** (measurement-led) →
**D8** (only if demanded). Each flag default-off → A/B → promote only if ≥ baseline, guards 1.000,
structured-lookup stable, `confidently_wrong` not up → refresh baseline.

## Files (anticipated)
- D1/D2 synthesis + part-aware: [guardrails.py](vinchatbot/app/agents/guardrails.py), [vinuni_agent.py](vinchatbot/app/agents/vinuni_agent.py).
- D2/D3 orchestration: [supervisor.py](vinchatbot/app/agents/supervisor.py) + `chat()`; coverage signal from [retriever.py](vinchatbot/app/rag/retriever.py).
- D5 web tool: [tools.py](vinchatbot/app/agents/tools.py), [specialists.py](vinchatbot/app/agents/specialists.py), [config.py](vinchatbot/app/core/config.py).
- D6: [guardrails.py](vinchatbot/app/agents/guardrails.py) (+ PHASE1.26_PLAN). Per-direction flags in `config.py`.
- Golden under `data/eval/golden/`; unit tests under `tests/` (mock the planner/synthesis/web LLM calls).

## Verification
Per direction: `pytest -q` + `ruff` green → `run_eval --diff baseline --runs 3` (≥ baseline, guards 1.000,
structured-lookup turns stable, `confidently_wrong` ≤ baseline) → decode every flip → promote + refresh
baseline only if clean. Worked-example questions re-run live to confirm the new partial/cross-domain behavior.
No git commit unless asked.

## NOT now
Execute only **after** the deepen-crawl ingest + re-benchmark. This file is the captured roadmap for that review.

---

## Logged failure cases (found during expansion testing — handle + add to golden)
### 2026-06-23 — VinUni presidents / entity-name handling
Observed on the live bot (current index). Two distinct, generalizable failures → golden-case candidates +
roadmap work; **re-test after the new combined index is built** (the new crawl pulls in `vinuni.edu.vn`
leadership/about + college pages, which may carry president info):
- **F-ENUM — incomplete entity enumeration.** "Who are VinUni's presidents/rectors?" → returns only
  *Tan Yap Peng*, **missing Rohit Verma** (VinUni has had two presidents). A "list-all-X / who are the X"
  question returns a single entity instead of enumerating all. Relates to the completeness/list failure family
  (roadmap D1/D2 + list-mode); the completeness nudge didn't surface the second entity. Golden: a "list all
  presidents" case with `required_facts=[both names]`.
- **F-NAME — entity-name order/alias sensitivity.** "Who is *Yap-Peng Tan*?" → doesn't know, but "Who is
  *Tan Yap Peng*?" → answers. (And "Rohit Verma" works alone but isn't surfaced by the plural question.)
  Retrieval/matching is sensitive to name **word-order** (Western "Given Family" vs stored "Family Given") and
  has no name-alias normalization. New failure mode → suggests an **entity-alias/name-order normalization**
  layer (ties to roadmap D8 entity graph: entities with alias sets) and/or query name-order expansion. Golden:
  the same person asked both name orders → both must resolve.

### 2026-06-24 — UPDATE after the ingest-filter fix + v2 rebuild (see [PHASE1.28_LOG.md](PHASE1.28_LOG.md))
Root cause of F-NAME/F-ENUM was **3 layers**, now partly resolved:
- **Layer 1 (filter) — RESOLVED.** The `--student-only` filter was dropping all 989 `/people/` bios (+forms,
  guides, curricula). The path-aware filter fix (see [INGEST_FILTER_AUDIT.md](INGEST_FILTER_AUDIT.md)) +
  v2 rebuild now indexes them → **F-NAME fixed**: both "Tan Yap Peng" and "Yap-Peng Tan" resolve to the same
  bio; over-refusal gone; Rohit Verma correctly identified as Founding Provost.
- **Layer 2 (content) — OPEN.** Bios state background, not the VinUni *Rector* title (that's in the dropped
  leadership announcement). → keep the announcement/about page (targeted) for affirmative title answers.
- **Layer 3 (entity) — OPEN, now D9 + D8.** F-ENUM is worse, not better: 993 bios + "President" overloaded
  across roles → enumeration **confidently lists wrong people**. Needs **D9** (intent-satisfaction validator →
  hedge instead of confidently-wrong) + **D8** (role/alias table). D9 is the next fix.
