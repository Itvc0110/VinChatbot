# Phase 1.4 — Chunking / retrieval / data-cleaning + markdown deep-inspect + coverage — Log

Baseline to beat: **92.5%** (Phase 1.2, 80 cases, serving collection `vinuni_documents`,
plain-text pipeline). Every change is `ENABLE_*`-gated and A/B-measured on a scratch
collection (or read-only on the serving collection) before promotion. Plan: the approved
Phase 1.4 plan (markdown deep-inspect + chunking/retrieval/data-cleaning improvements + coverage).

---

## Full comparison — every Phase 1.4 eval run (read this first)

All runs on `vinuni_documents` (serving), `gpt-4o-mini`, parent-doc off unless noted. Categories
that stayed **1.000** across all valid runs are omitted: `adversarial` (15), `safety` (8),
`multiturn` (4), `unanswerable` (5). The eval set grew from **80 → 86** when `conduct.json` (+6)
was added mid-phase, so compare the **80-subset** across rows.

| # | Run / config | Cases | **overall** | calendar | financial | policy_conduct | services | conduct | Decision |
|---|---|---|---|---|---|---|---|---|---|
| — | *Phase 1.2 proven baseline (historical)* | 80 | *0.925* | 0.929 | 0.875 | 0.714 | 0.800 | — | reference |
| — | *Phase 1.3 markdown (rejected)* | 80 | *0.738→0.812* | ↓ | — | ↓ | ↓ | — | reverted |
| 1 | Session baseline (pre-fix, parent-doc off) | 80 | **0.900** | 0.929 | 0.875 | 0.571 | 0.600 | — | reference |
| 2 | Parent-doc v1 (unscoped) | 80 | 0.900 | 0.857 ⬇ | 0.875 | 0.571 | 1.000 ⬆ | — | net-neutral |
| 3 | Parent-doc v2 (calendar-scoped) | 80 | 0.900 | 0.893 | 0.875 | 0.571 | 0.800 | — | **NOT promoted** (gated off) |
| 4 | **+ Faithfulness fix** (parent-doc off) | 80 | **0.925** ⬆ | 0.929 | 0.875 | 0.714 ⬆ | 0.800 | — | **SHIPPED** |
| 5 | gpt-4o (with fix) | 80 | 0.925 | 0.893 | 0.875 | 0.714 | 1.000 | — | rejected (wash, ~20× cost) → stay mini |
| 6 | Prompt tightening `phase4-v2` (with fix) | 80 | 0.912 ⬇ | 0.893 | 0.875 | 0.857 | 0.600 | — | reverted (net −1) |
| 7 | Coverage A/B (two evals **concurrent**) | 86 | ~~0.651 / 0.523~~ | ~~0.0–0.07~~ | — | — | — | 1.0 | **INVALID** — OpenRouter `403` quota mid-run |
| 8 | **Clean final** (fix on, prompt reverted, +conduct) | 86 | **0.919** | 0.893 | 0.875 | 0.714 | 0.800 | 1.000 | **current production state** |

**Reading it:** runs 1–3 are vs the *pre-fix* 0.900 baseline; runs 4–6 vs the *post-fix* proven
0.925. The only net mover was the **faithfulness fix (run 4, +0.025)** which shipped. Parent-doc,
gpt-4o, and prompt-tightening were all rejected. Run 8 is the honest current state: **0.919 on 86
cases (80-subset 0.912 = proven band)** with the +6 conduct cases passing 6/6. Per-run reports are
in `data/eval/results/eval_*.json` (timestamps cited in each section below).

---

## Track 2.1 — Parent-document retrieval (`ENABLE_PARENT_DOC`, default off)

**Idea (research-backed).** Match/rank on small precise chunks, but hand the LLM the *full
section* the matched chunk belongs to — small-chunk precision + full-section context. This is
the standard remedy for the over-fragmentation half of what sank the markdown pipeline
(Phase 1.3), and it's **retrieval-time only**, so it A/B-tests on the existing serving
collection with **no re-ingest**.

**Implementation.**
- `expand_to_parent_sections(chunks, fetch_siblings, max_chars, max_siblings)` in
  [context.py](../vinchatbot/app/rag/context.py): groups the post-dynamic-k chunks by
  `(parent_doc_id, section_id)`, and for each group stitches the section's chunks into one
  block (matched chunk first, remaining siblings in `page_number` order, deduped, bounded by
  `PARENT_DOC_MAX_CHARS`=4000 / `PARENT_DOC_MAX_SIBLINGS`=6). Chunks without a `section_id`
  (no heading structure) pass through unchanged; several top chunks from the same section
  collapse to one (kept at the highest rank). Frozen-`RetrievedChunk`-safe via `_retext`.
- `QdrantHybridRetriever._fetch_section_siblings` in
  [retriever.py](../vinchatbot/app/rag/retriever.py): scrolls the indexed
  `metadata.parent_doc_id` keyword field, filters the section client-side (section_id isn't
  separately indexed), reads `page_content` + `metadata`. Fails soft to `[]`.
- Wired after dynamic-k, before lost-in-the-middle reorder; only active for the Qdrant backend.
- Config: `enable_parent_doc` / `parent_doc_max_chars` / `parent_doc_max_siblings`
  ([config.py](../vinchatbot/app/core/config.py)).
- Tests: 4 new pure-function cases in [test_context.py](../tests/test_context.py) (expand,
  pass-through-without-section, same-section collapse, char-budget). 93 offline tests + ruff green.

**A/B result (serving collection `vinuni_documents`, read-only, same session).**

| Category        | Baseline (off) | Parent-doc (on, v1) | Parent-doc (scoped, v2) |
|-----------------|----------------|---------------------|-------------------------|
| **overall**     | **0.900**      | 0.900               | _running_               |
| adversarial     | 1.000          | 1.000               |                         |
| calendar (28)   | 0.929          | **0.857** ⬇         |                         |
| financial (8)   | 0.875          | 0.875               |                         |
| multiturn (4)   | 1.000          | 1.000               |                         |
| policy_conduct (7) | 0.571       | 0.571               |                         |
| safety (8)      | 1.000          | 1.000               |                         |
| services (5)    | 0.600          | **1.000** ⬆         |                         |
| unanswerable (5)| 1.000          | 1.000               |                         |

Reports: baseline `eval_20260614T073032Z.json`, v1 `eval_20260614T073116Z.json`. (Both 0.90
this session, not the historical 92.5% — LLM nondeterminism, mostly policy_conduct 4/7 and
the calendar swing; that's why baseline was re-run in-session rather than compared to the log.)

**Mechanism (exact, 4 cases flipped — not noise).**
- **Library +2** (`svc-library-services`, `svc-library-course-books`): the single library doc's
  matched chunk was too small to answer; stitching the full section gave enough context → pass.
  (Library is the journal's known thin domain — parent-doc is exactly its fix.)
- **Calendar −2** (`calendar-fall-add-transfer-deadline` EN+VI): the answer stayed *correct*
  ("October 1, 2026") but expanding the calendar **date grid** pulled the adjacent **course-drop
  date (October 9)** into context; the model volunteered it, tripping the case's
  `forbidden_facts: ["October 9, 2026"]`. Point-lookup tabular data lists similar-but-distinct
  facts where neighbours are *distractors*, not context.

**Refinement + v2.** `PARENT_DOC_SKIP_SUBCATEGORIES="calendar"` (default) opts the calendar grid
out of stitching while keeping it for prose. v2 (report `eval_20260614T074646Z.json`): overall
**0.900**, calendar 0.893, services 0.800. The scope recovered the EN calendar case but the VI
one still tripped (it expanded a non-`calendar`-subcategory registrar chunk that also carried the
adjacent date) — so scoping mitigates but doesn't fully eliminate the interaction.

**Three-run summary (all overall = 0.900).**

| Config                         | overall | calendar | services |
|--------------------------------|---------|----------|----------|
| Baseline (off)                 | 0.900   | 0.929    | 0.600    |
| Parent-doc v1 (unscoped)       | 0.900   | 0.857    | 1.000    |
| Parent-doc v2 (calendar-scoped)| 0.900   | 0.893    | 0.800    |

**Decision: NOT promoted — kept gated off (`ENABLE_PARENT_DOC=false`), code retained + scoped +
documented.** Parent-doc **reliably helps the thin services/library domain** (+1–2 cases, both
treated runs) — a real, mechanistic win — but is **net-neutral at the top line** because calendar
is a point-lookup domain it can hurt and the session's dominant weak spot (`policy_conduct` 0.571)
is content-driven, untouched by section stitching. Per "promote only winners," a wash doesn't flip
the default. It stays validated/available as (1) the enabling lever for a future **markdown
revisit** (rich sections, where over-fragmentation was the killer) and (2) a targeted improver once
**coverage** (library/services) grows. Eval categories of 5 cases are also too small to claim an
overall promotion on. Net production change: none.

---

## Faithfulness false-positive fix (found while diagnosing `policy_conduct`)

**How it surfaced.** `policy_conduct` was the session's weak spot (0.571). The failing cases were
all **LOA (leave-of-absence) questions the agent *refused*** ("could not find sufficiently clear
official information") despite `citation_ok=True`. A direct retrieval probe showed the **perfect
chunk is indexed and ranks #0** — section `fb49319b` literally contains "## 1. Purpose … structured
process … clarity, fairness, consistency" and "## 2. Scope: applicable for full-time students." So
neither recall nor chunking was at fault.

**Root cause.** Tracing the live agent, the model **generated a correct answer** that was overwritten
by graceful degradation because **`assess_faithfulness` returned False**. The grounding check extracts
every 2+digit token from the whole answer and requires it to appear in the retrieved evidence text.
The only such token was **`54`**, from the **policy code "VUNI.54"** in the answer's `**Source:**`
line — citation *metadata*, never present in chunk body text. One metadata digit was silently
destroying correct, grounded policy answers.

**Fix** ([guardrails.py](../vinchatbot/app/agents/guardrails.py)): `assess_faithfulness` now grounds
only the **substantive body** — `_grounding_body` strips markdown link targets, `Source:`/`Nguồn:`
attribution lines, and `(Policy Code: …)` before fact extraction. Body claims are still checked
(a hallucinated `12345 VND` still fails); citation identity is already validated by the citation
pipeline. Test: `test_faithfulness_ignores_citation_metadata_digits`. Live re-check: both LOA
questions now answer (confidence 0.97 / 0.57) instead of refusing.

**A/B result (serving collection, parent-doc off).** Report `eval_20260614T080855Z.json`.

| Category        | Baseline (this session) | + faithfulness fix |
|-----------------|-------------------------|--------------------|
| **overall**     | 0.900                   | **0.925** ⬆        |
| policy_conduct  | 0.571                   | **0.714** ⬆        |
| (others unchanged: adversarial/safety/multiturn/unanswerable 1.0, calendar 0.929, financial 0.875, services 0.8) |

`pol-loa-applicability` recovered (the exact case traced). The fix also **removes a
nondeterministic failure mode**: the false-positive only fired when the model happened to append
the policy code to its Source line, so these policy cases were *flaky* — now deterministically
grounded. The two residual `policy_conduct` fails are a different, benign class: `pol-loa-purpose`
answers correctly but its `required_facts:["temporary"]` vs the answer's "temporarily" is a golden
token-matching edge; `pol-loa-fulltime-vi` is a VI citation-source edge. Both are in the journal's
known "VI/phrasing edges" bucket, not system bugs.

**Decision: SHIP (no toggle).** This is a correctness fix to the output grounding gate, not a
tunable lever — it restores correct, grounded policy answers that were being refused. Overall back
to the proven **0.925** with reduced flakiness. 99 offline tests + ruff green.

---

## Generation-gate tuning (larger model + prompt) — both rejected, with reasons

User asked to enhance the generation gate (prompt, larger OpenAI model). Both tested on the
serving collection vs the 0.925 baseline; **neither won**, which is itself the finding.

**Larger model — `openai/gpt-4o` vs `gpt-4o-mini`** (report `eval_20260614T083739Z.json`):
overall **0.925 = 0.925**, at ~15–30× the cost. Flips: 4o *gained* library synthesis +
the calendar source-inconsistency case (smarter reasoning) but *lost* two VI calendar cases, and
**did not fix the fee disambiguation** (`fin-standard-credit-vi` still wrong). **Decision: stay on
`gpt-4o-mini`** — our losses are not model-capability-bound.

**Prompt tightening** (`phase4-v2`: "answer exactly what's asked / don't append neighbouring
facts" + program-row disambiguation; report `eval_20260614T090944Z.json`): overall **0.912**
(net −1). The terse-scoping principle made the library/calendar synthesis answers drop required
facts; the disambiguation principle didn't help because the fee miss is **retrieval-bound, not
reasoning-bound**. **Decision: fully reverted to proven `phase0-v1`.**

**Root-caused `fin-standard-credit-vi` (financial 7/8).** Golden verified **correct** (standard =
"Other Bachelor Programs" = 27,195,000; the model wrongly returned Nursing's 9,780,000). Two real
problems: (1) the EN **Financial Regulations & Tariff** doc ranks *below an irrelevant VN exchange
page* (raw rerank 0.266 vs 0.677) — a **cross-lingual gap** (VN query vs EN table); the ×1.21
routed-category boost can't close it. (2) Even with the doc, the model picked the wrong program
row. Aggressive boost (×2+) or a hard category filter could force it, but that risks overfitting one
noisy case / distorting retrieval — **logged as a known cross-lingual limitation, not over-tuned.**

**Net of generation-gate thread:** production unchanged at proven **0.925**; the evidence redirects
effort to **coverage** (library) and **eval hardening** (the residual fails are now mostly
measurement artifacts: VI/morphology like `temporary`≠`temporarily`, and one by-design
source-inconsistency case).

---

## Coverage extension — crawl was REDUNDANT (lesson) + a real eval-set enrichment

User wanted new seeds, but "carefully look through the content" and "enhance the golden set with
the new data" (scratch-first).

**What I did.** Verification crawl (4 student-facing hubs, depth 1) → 30 docs into scratch dirs.
It surfaced the **Student Code of Conduct cluster** (HTML + EN/VN `VU_CTSV02` PDFs + disciplinary
Appendices I–IV) and registrar academic pages. `experience.vinuni.edu.vn` returned only a JS stub,
so health/career/housing were **not** reached. Refined `infer_category` to group the conduct
cluster (disciplinary/violation/behaviour/`cong-tac-sinh-vien` → `student_affairs/conduct`; tested).
Built a scratch collection (`vinuni_cov_test` = 761-doc corpus re-embedded + 30 new docs).

**The finding: production already had it.** A Qdrant scroll (no embeddings) showed
`vinuni_documents` **already contains** `VU_CTSV02_Student-Code-of-Conduct` and **110 conduct
chunks — identical to the scratch build**. The journal's "student Code of Conduct missing" was
**stale** (a prior session had already crawled it; production = 7,957 pts vs a fresh corpus
re-ingest's 7,781). **Process mistake: I trusted the journal's gap list instead of scrolling the
live index first** — a 30-second check would have avoided the crawl and the re-embed.

**Quota incident.** Two evals were run **concurrently** + the unnecessary full re-embed exhausted
the OpenRouter key mid-run (`403 Key limit exceeded`), which corrupted those runs (empty
calendar/services citations were quota failures, not regressions). User issued a new key. **Lesson:
never run evals concurrently (API contention); don't re-embed to validate retrieval-time questions.**

**What survives as real value — eval-set enrichment.** Authored **6 Code-of-Conduct golden cases**
(EN+VN: scope, purpose, the 4 disciplinary tiers, reporting), with facts/sources **validated against
the live agent** so they are fair. They test genuinely-new-to-the-eval content that is in production
(non-circular). Clean single eval (`eval_20260614T104653Z.json`, production, 86 cases):
**overall 0.919**, **conduct 6/6**, **80-subset 0.912** (proven band — no regression). Scratch
collection deleted. `infer_category` conduct grouping kept (correct for future ingests).

**Net production change:** none to the index; **+6 validated golden cases** (eval set now 86).
Coverage to genuinely new domains (health/counseling/career/housing) remains open and needs
different seeds + new `infer_category` rules — a future step.

---

## Conversational handling fix (smalltalk · language · tone)

**Problem (user-reported, reproduced live).** Basic social turns were broken: "Xin chào" was greeted
**in English**; "OK"/"tạm biệt"/"cảm ơn"/"👍"/"bạn khỏe không" fell through to retrieval and returned
the cold graceful-degradation refusal; "bạn là gì?" couldn't explain the bot.

**Root causes** ([guardrails.py](../vinchatbot/app/agents/guardrails.py)):
1. `answer_language` only scanned the diacritic set `"ăâđêôơư"` (missing `à á ạ è é ệ …`) + a tiny
   word list → most Vietnamese (incl. accent-less "xin chao", "tam biet") was detected as English.
2. No conversational-intent tier — only an exact greeting; closings/thanks/acks, identity/capability,
   and social turns fell to `out_of_scope` → SLM (lenient) allowed → agent **retrieved** → degraded.

**Fix.**
- `answer_language` now uses the full `VIETNAMESE_MARKERS` accent set + a curated accent-less hint
  list (English-colliding words like "the"/"on" deliberately excluded).
- New confident rule-tier actions `smalltalk` (greeting/closing/thanks/ack/emoji) and `capability`
  (identity/what-can-you-do/social), classified **before the SLM and before any retrieval**.
- New async `build_conversational_response`: **canned** warm replies for smalltalk; **LLM persona**
  reply for capability/social (fail-open to canned). No source-link dump on social turns. Routed in
  [routes_chat.py](../vinchatbot/app/api/routes_chat.py) + [vinuni_agent.py](../vinchatbot/app/agents/vinuni_agent.py)
  via `CONVERSATIONAL_ACTIONS`.

**Result.** All 8 social inputs answer directly in the correct language, no retrieval/degradation;
real questions still flow to the agent. Tests in `test_guardrails.py` (incl. a regression that caught
the "the"/"on" English-collision). **102 offline tests + ruff green.** Full eval **0.919 — no
regression** (adversarial/safety/unanswerable all 1.0 → guards intact). Notes: "OK"/"👍"
(language-neutral) default to English; **graceful degradation remains the intended response for
genuine no-data questions**.
